import json
import os
from core.config import SessionConfig, FINISH_TASK_SCHEMA
from core.runtime.bus import CorrectionBus, WorkerSnapshot
from core.llm import chat
from core.tools import execute_tool
from core.runtime.session import SessionController
from core.agents.base import BaseAgent
from display import (
    worker_header, worker_stream_start, worker_token, worker_stream_end,
    worker_tool_call, worker_tool_result, worker_ask_mentor,
    mentor_stream_start, mentor_stream_end, mentor_answer, error_msg, system_msg,
)

_COMPRESS_PROMPT = """Summarize the following conversation history into a compact paragraph that preserves all key decisions, code written, errors encountered, and current progress. Be factual and concise.

{history}"""

_COMPRESS_THRESHOLD = 30


class WorkerAgent(BaseAgent):
    def __init__(self, cfg: SessionConfig, bus: CorrectionBus, tool_handlers: dict, ctrl: SessionController,
                 ask_mentor_fn=None, history_path: str | None = None):
        self.cfg = cfg
        self.bus = bus
        self.tool_handlers = tool_handlers
        self.ctrl = ctrl
        self.ask_mentor_fn = ask_mentor_fn
        self.history_path = history_path
        self.messages: list[dict] = self._load() or [{"role": "system", "content": cfg.worker_system}]
        self.round = 0

    @staticmethod
    def _repair_messages(messages: list[dict]) -> list[dict]:
        repaired = []
        i = 0
        while i < len(messages):
            m = messages[i]
            if m.get("role") == "assistant" and m.get("tool_calls"):
                tc_ids = {tc.get("id") for tc in m["tool_calls"] if tc.get("id")}
                j = i + 1
                found_ids = set()
                while j < len(messages) and messages[j].get("role") == "tool":
                    found_ids.add(messages[j].get("tool_call_id"))
                    j += 1
                missing_ids = tc_ids - found_ids
                if missing_ids:
                    repaired.append(m)
                    for k in range(i + 1, j):
                        repaired.append(messages[k])
                    for tc in m["tool_calls"]:
                        tc_id = tc.get("id")
                        if tc_id in missing_ids:
                            name = tc.get("function", {}).get("name", "unknown")
                            repaired.append({
                                "role": "tool",
                                "tool_call_id": tc_id,
                                "name": name,
                                "content": "[REPAIRED] 此工具调用因历史数据损坏被自动补齐",
                            })
                    i = j
                else:
                    for k in range(i, j):
                        repaired.append(messages[k])
                    i = j
            else:
                repaired.append(m)
                i += 1
        return repaired

    def _load(self) -> list[dict] | None:
        if self.history_path and os.path.exists(self.history_path):
            try:
                with open(self.history_path, encoding="utf-8") as f:
                    msgs = json.load(f)
                return self._repair_messages(msgs)
            except Exception:
                pass
        return None

    def _save(self):
        if not self.history_path:
            return
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    async def _maybe_compress(self):
        non_system = [m for m in self.messages if m["role"] != "system"]
        if len(non_system) < _COMPRESS_THRESHOLD:
            return
        system = self.messages[0]

        keep_count = 6
        while keep_count < len(non_system):
            tail = non_system[-keep_count:]
            first = tail[0]
            if first.get("role") == "assistant" and first.get("tool_calls"):
                actual_tool_ids = set()
                for m in tail[1:]:
                    if m.get("role") == "tool":
                        actual_tool_ids.add(m.get("tool_call_id"))
                    else:
                        break
                expected_ids = {tc["id"] for tc in first["tool_calls"]}
                if actual_tool_ids == expected_ids:
                    break
                keep_count += 2
            else:
                break

        to_compress, keep = non_system[:-keep_count], non_system[-keep_count:]
        history = "\n".join(
            f"[{m['role'].upper()}]: {m.get('content') or json.dumps(m.get('tool_calls', ''))}"
            for m in to_compress
        )
        try:
            resp = await chat(self.cfg.worker_model,
                              [{"role": "user", "content": _COMPRESS_PROMPT.format(history=history[:8000])}])
            summary = resp.get("content", "")
            self.messages = [system, {"role": "user", "content": f"[HISTORY SUMMARY] {summary}"}] + keep
            system_msg(f"历史已压缩（{len(to_compress)} 条 → 1 条摘要）")
        except Exception:
            pass

    def _capture_file_snapshot(self, path: str, snapshots: dict[str, str | None]):
        if path in snapshots:
            return
        try:
            from core.tools.filesystem import _resolve_safe
            p = _resolve_safe(path, list(self.tool_handlers.get("_allowed_roots", [])))
            if p.exists():
                snapshots[path] = p.read_text(encoding="utf-8")
            else:
                snapshots[path] = None
        except Exception:
            snapshots[path] = None

    async def _apply_rollback(self, snapshot: WorkerSnapshot):
        from core.tools.filesystem import _resolve_safe
        allowed_roots = list(self.tool_handlers.get("_allowed_roots", []))
        for path, original in snapshot.file_snapshots.items():
            try:
                p = _resolve_safe(path, allowed_roots)
                if original is None:
                    if p.exists():
                        os.remove(p)
                else:
                    p.parent.mkdir(parents=True, exist_ok=True)
                    p.write_text(original, encoding="utf-8")
            except Exception as e:
                system_msg(f"回滚文件失败 {path}: {e}")
        self.messages = [m.copy() for m in snapshot.messages]
        system_msg(f"已回滚至第 {snapshot.round} 轮状态")

    async def run(self, initial_task: str):
        self.messages.append({"role": "user", "content": initial_task})

        pending_corrections: list[str] = []

        for _ in range(self.cfg.max_rounds):
            await self.ctrl.wait_resume()
            if self.ctrl.is_stopped:
                break

            await self._maybe_compress()

            await self.bus.wait_eval_done()

            rollback = self.bus.drain_rollback()
            if rollback:
                snapshot, reason = rollback
                await self._apply_rollback(snapshot)
                self.messages.append({"role": "user", "content": f"[MENTOR ROLLBACK] {reason}"})
                continue

            if pending_corrections:
                combined = "\n".join(f"[MENTOR CORRECTION] {c}" for c in pending_corrections)
                self.messages.append({"role": "user", "content": combined})
                pending_corrections.clear()

            corrections = self.bus.drain_corrections()
            if corrections:
                combined = "\n".join(f"[MENTOR CORRECTION] {c}" for c in corrections)
                self.messages.append({"role": "user", "content": combined})

            self.round += 1
            worker_header(self.round)
            worker_stream_start()

            try:
                self.messages = self._repair_messages(self.messages)
                response = await chat(
                    self.cfg.worker_model, self.messages, self.cfg.tool_schemas,
                    on_token=worker_token,
                )
            except Exception as e:
                worker_stream_end()
                error_msg("Worker", str(e))
                self.ctrl.set_error(f"Worker LLM error: {e}")
                break

            worker_stream_end()
            self.messages.append(response)

            current_snapshots: dict[str, str | None] = {}

            finish_requested = False
            if response.get("tool_calls"):
                pending_tcs = list(response["tool_calls"])
                for idx, tc in enumerate(pending_tcs):
                    name = tc.get("function", {}).get("name", "unknown")
                    raw_args = tc.get("function", {}).get("arguments", "")
                    tc_id = tc.get("id") or f"missing_id_{idx}"
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        error_msg("Worker", f"工具参数 JSON 截断（{name}），跳过此调用")
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": name,
                            "content": f"[ERROR] 工具参数 JSON 解析失败: {raw_args}",
                        })
                        continue

                    if name == "write_file" and "path" in args:
                        self._capture_file_snapshot(args["path"], current_snapshots)

                    worker_tool_call(name, args)

                    if name == "finish_task":
                        finish_requested = True
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc_id,
                            "name": name,
                            "content": "任务已完成",
                        })
                        continue

                    try:
                        if name == "ask_mentor" and self.ask_mentor_fn:
                            question = args.get("question", "")
                            worker_ask_mentor(question)
                            mentor_stream_start(self.round)
                            result = await self.ask_mentor_fn(question)
                            mentor_stream_end()
                            mentor_answer(result)
                        else:
                            result = execute_tool(name, args, self.tool_handlers)
                            worker_tool_result(name, result)
                    except Exception as e:
                        error_msg("Worker", f"工具 {name} 执行失败: {e}")
                        result = f"[ERROR] 工具执行失败: {e}"

                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc_id,
                        "name": name,
                        "content": result,
                    })

                if finish_requested:
                    system_msg("Worker 调用 finish_task，任务结束")
                    await self.bus.publish_snapshot(WorkerSnapshot(
                        round=self.round,
                        messages=list(self.messages),
                        last_response=response.get("content", ""),
                        file_snapshots=current_snapshots,
                    ))
                    self._save()
                    return

            await self.bus.publish_snapshot(WorkerSnapshot(
                round=self.round,
                messages=list(self.messages),
                last_response=response.get("content", ""),
                file_snapshots=current_snapshots,
            ))
            self._save()

            pending_corrections = self.bus.drain_corrections()

            if not response.get("tool_calls") and response.get("content"):
                self.messages.append({"role": "user", "content": "Continue or confirm task is complete with DONE."})

    async def chat_direct(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": f"[USER DIRECT] {user_input}"})
        try:
            response = await chat(self.cfg.worker_model, self.messages, self.cfg.tool_schemas,
                                  on_token=worker_token)
        except Exception as e:
            return f"Error: {e}"
        self.messages.append(response)
        return response.get("content", "")
