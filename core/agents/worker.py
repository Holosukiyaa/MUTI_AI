import json
from core.config import SessionConfig
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
        to_compress, keep = non_system[:-6], non_system[-6:]
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

    async def run(self, initial_task: str):
        self.messages.append({"role": "user", "content": initial_task})

        for _ in range(self.cfg.max_rounds):
            await self.ctrl.wait_resume()
            if self.ctrl.is_stopped:
                break

            await self._maybe_compress()

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

            if response.get("tool_calls"):
                for tc in response["tool_calls"]:
                    name = tc["function"]["name"]
                    raw_args = tc["function"]["arguments"]
                    try:
                        args = json.loads(raw_args) if isinstance(raw_args, str) else raw_args
                    except json.JSONDecodeError:
                        error_msg("Worker", f"工具参数 JSON 截断（{name}），跳过此调用")
                        continue
                    worker_tool_call(name, args)
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
            ))

            if not response.get("tool_calls") and response.get("content"):
                self.messages.append({"role": "user", "content": "Continue or confirm task is complete with DONE."})
                if "DONE" in response.get("content", "").upper():
                    break

    async def chat_direct(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": f"[USER DIRECT] {user_input}"})
        try:
            response = await chat(self.cfg.worker_model, self.messages, self.cfg.tool_schemas,
                                  on_token=worker_token)
        except Exception as e:
            return f"Error: {e}"
        self.messages.append(response)
        return response.get("content", "")
