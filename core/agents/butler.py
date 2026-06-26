import json
from core.config import SessionConfig
from core.bus import CorrectionBus, WorkerSnapshot
from core.llm import chat
from core.tools import execute_tool
from core.session import SessionController
from display import butler_token, butler_interrupt, butler_ok, error_msg


BUTLER_EVAL_PROMPT = """You are observing Worker's full conversation history on a task.
Task: {task}
Round: {round}

=== Worker's complete context ===
{worker_context}
=== End of Worker context ===

If Worker has written wrong files or gone severely off-track, respond with "ROLLBACK: <reason>".
If Worker is going slightly off-track, respond with "CORRECT: <fix needed>".
If Worker is on track, respond with "OK".
Be concise. Only intervene when necessary."""

_MAX_ERRORS = 3


class ButlerAgent:
    def __init__(self, cfg: SessionConfig, bus: CorrectionBus, butler_tool_handlers: dict, ctrl: SessionController):
        self.cfg = cfg
        self.bus = bus
        self.butler_tool_handlers = butler_tool_handlers
        self.ctrl = ctrl
        self.messages: list[dict] = [{"role": "system", "content": cfg.butler_system}]
        self._consecutive_errors = 0
        bus.on_snapshot(self._on_worker_snapshot)

    async def _on_worker_snapshot(self, snapshot: WorkerSnapshot):
        if self.ctrl.is_stopped:
            return

        visible = [m for m in snapshot.messages if m["role"] != "system"]
        context_lines = []
        char_budget = 6000
        for m in reversed(visible):
            line = f"[{m['role'].upper()}]: {m.get('content') or json.dumps(m.get('tool_calls', ''))}"
            if char_budget - len(line) < 0:
                context_lines.append("[... earlier history truncated ...]")
                break
            context_lines.append(line)
            char_budget -= len(line)
        worker_context = "\n".join(reversed(context_lines))
        eval_prompt = BUTLER_EVAL_PROMPT.format(
            task=self.cfg.task[:1000],
            round=snapshot.round,
            worker_context=worker_context,
        )
        self.messages.append({"role": "user", "content": eval_prompt})

        try:
            response = await chat(self.cfg.butler_model, self.messages, self.cfg.tool_schemas)
        except Exception as e:
            self._consecutive_errors += 1
            if self._consecutive_errors >= _MAX_ERRORS:
                error_msg("Butler", str(e))
                self.ctrl.set_error(f"Butler LLM error: {e}")
            else:
                error_msg("Butler", f"{e} （连续错误 {self._consecutive_errors}/{_MAX_ERRORS}，跳过本轮评估）")
            return

        self._consecutive_errors = 0
        self.messages.append(response)
        content = response.get("content", "")

        if response.get("tool_calls"):
            for tc in response["tool_calls"]:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                result = execute_tool(name, args, self.butler_tool_handlers)
                self.messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "name": name,
                    "content": result,
                })

        stripped = content.strip()
        upper = stripped.upper()
        if upper.startswith("ROLLBACK:"):
            reason = stripped[len("ROLLBACK:"):].strip()
            butler_interrupt(snapshot.round, f"[ROLLBACK] {reason}")
            await self.bus.inject_rollback(snapshot, reason)
        elif upper.startswith("CORRECT:"):
            correction = stripped[len("CORRECT:"):].strip()
            butler_interrupt(snapshot.round, correction)
            await self.bus.inject_correction(correction)
        else:
            butler_ok(snapshot.round)

    async def answer_question(self, question: str) -> str:
        prompt = f"[WORKER QUESTION] {question}\nAnswer based on your private knowledge. Be specific and helpful."
        self.messages.append({"role": "user", "content": prompt})
        try:
            response = await chat(self.cfg.butler_model, self.messages, None,
                                  on_token=butler_token)
        except Exception as e:
            return f"[Butler错误] {e}"
        self.messages.append(response)
        return response.get("content", "")

    async def chat_direct(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": f"[USER DIRECT] {user_input}"})
        try:
            response = await chat(self.cfg.butler_model, self.messages, self.cfg.tool_schemas)
        except Exception as e:
            return f"Error: {e}"
        self.messages.append(response)
        return response.get("content", "")
