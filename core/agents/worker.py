import json
import os
from core.config import SessionConfig, FINISH_TASK_SCHEMA
from core.bus import CorrectionBus, WorkerSnapshot
from core.llm import chat
from core.tools import execute_tool
from core.session import SessionController
from display import (
    worker_header, worker_stream_start, worker_token, worker_stream_end,
    worker_tool_call, worker_tool_result, worker_ask_butler,
    butler_stream_start, butler_stream_end, butler_answer, error_msg, system_msg,
)

_COMPRESS_PROMPT = """Summarize the following conversation history into a compact paragraph that preserves all key decisions, code written, errors encountered, and current progress. Be factual and concise.

{history}"""

_COMPRESS_THRESHOLD = 30


class WorkerAgent:
    def __init__(self, cfg: SessionConfig, bus: CorrectionBus, tool_handlers: dict, ctrl: SessionController,
                 ask_butler_fn=None):
        self.cfg = cfg
        self.bus = bus
        self.tool_handlers = tool_handlers
        self.ctrl = ctrl
        self.ask_butler_fn = ask_butler_fn
        self.messages: list[dict] = [{"role": "system", "content": cfg.worker_system}]
        self.round = 0

    async def _maybe_compress(self):
        non_system = [m for m in self.messages if m["role"] != "system"]
        if len(non_system) < _COMPRESS_THRESHOLD:
            return
        system = self.messages[0]

        # 确保保留的尾部不会截断不完整的 tool_calls 序列
        keep_count = 6
        while keep_count < len(non_system):
            tail = non_system[-keep_count:]
            first = tail[0]
            if first.get("role") == "assistant" and first.get("tool_calls"):
                needed = len(first["tool_calls"])
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
        """在写入文件前采集原始内容。None 表示文件是新建的。"""
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
        """回滚文件并恢复消息上下文。"""
        from core.tools.filesystem import _resolve_safe
        allowed_roots = list(self.tool_handlers.get("_allowed_roots", []))
        for path, original in snapshot.file_snapshots.items():
            try:
                p = _resolve_safe(path, allowed_roots)
                if original is None:
                    # 新建的文件，回滚时删除
                    if p.exists():
                        os.remove(p)
                else:
                    # 恢复原始内容
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

            # 1. 等上轮 Butler 评估完
            await self.bus.wait_eval_done()

            # 2. 检查回滚信号
            rollback = self.bus.drain_rollback()
            if rollback:
                snapshot, reason = rollback
                await self._apply_rollback(snapshot)
                self.messages.append({"role": "user", "content": f"[BUTLER ROLLBACK] {reason}"})
                continue

            # 3. 插入上一轮 Butler 的纠正
            if pending_corrections:
                combined = "\n".join(f"[BUTLER CORRECTION] {c}" for c in pending_corrections)
                self.messages.append({"role": "user", "content": combined})
                pending_corrections.clear()

            # 4. drain 本轮新收到的纠正
            corrections = self.bus.drain_corrections()
            if corrections:
                combined = "\n".join(f"[BUTLER CORRECTION] {c}" for c in corrections)
                self.messages.append({"role": "user", "content": combined})

            self.round += 1
            worker_header(self.round)
            worker_stream_start()

            try:
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

            # 本轮文件快照
            current_snapshots: dict[str, str | None] = {}

            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        error_msg("Worker", f"工具参数 JSON 截断（{name}），跳过此调用")
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tc["id"],
                            "name": name,
                            "content": f"[ERROR] 工具参数 JSON 解析失败: {raw_args}",
                        })
                        continue

                    # 写入文件前采集快照
                    if name == "write_file" and "path" in args:
                        self._capture_file_snapshot(args["path"], current_snapshots)

                    worker_tool_call(name, args)

                    if name == "finish_task":
                        system_msg("Worker 调用 finish_task，任务结束")
                        self.bus.signal_task_done()
                        return

                    if name == "ask_butler" and self.ask_butler_fn:
                        question = args.get("question", "")
                        worker_ask_butler(question)
                        butler_stream_start(self.round)
                        result = await self.ask_butler_fn(question)
                        butler_stream_end()
                        butler_answer(result)
                    else:
                        result = execute_tool(name, args, self.tool_handlers)
                        worker_tool_result(name, result)
                    self.messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "name": name,
                        "content": result,
                    })

            await self.bus.publish_snapshot(WorkerSnapshot(
                round=self.round,
                messages=list(self.messages),
                last_response=response.get("content", ""),
                file_snapshots=current_snapshots,
            ))

            # 收集 Butler 纠正，延迟到下一轮开头插入
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
