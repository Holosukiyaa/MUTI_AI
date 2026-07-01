import json
import os
from core.config import SessionConfig
from core.infra.bus import CorrectionBus, WorkerSnapshot, ProgressState
from core.llm import chat
from core.infra.tools import execute_tool
from core.infra.session import SessionController
from core.agents.base import BaseAgent
from display import mentor_token, mentor_interrupt, mentor_ok, error_msg, update_progress_bar


MENTOR_EVAL_PROMPT = """You are observing Worker's full conversation history on a task.
Task: {task}
Round: {round}

=== Worker's complete context ===
{worker_context}
=== End of Worker context ===

Evaluate Worker's progress and respond with ONE of:
- "ROLLBACK: <reason>" — Worker has written wrong files or gone severely off-track
- "CORRECT: <fix needed>" — Worker is slightly off-track, or is about to call finish_task prematurely
- "OK" — Worker is on track

Special rule for finish_task:
If Worker is calling or about to call finish_task but any of the following is true, respond with CORRECT:
- Files contain TODO, placeholders, stubs, or skeleton code
- Not all required files have been written with complete, runnable content
- The implementation is incomplete or cannot run without further editing
Example: "CORRECT: 文件内容不完整，请先完成所有核心功能再调用 finish_task。"

Be concise. Only intervene when necessary."""

_PROGRESS_EVAL_PROMPT = """Based on Worker's current progress on the task, estimate the completion status.

Task: {task}
Current round: {round}
Worker's recent actions: {actions}

Respond with a JSON object in this exact format:
{{"total_steps": 5, "current_step": 2, "step_name": "正在编写核心逻辑", "percent": 40}}

Rules:
- total_steps: total number of major phases for this task (typically 3-7)
- current_step: which phase Worker is currently in (0-based)
- step_name: brief description of current phase in Chinese (max 10 chars)
- percent: estimated completion percentage (0-100)
- Be realistic. If Worker is just starting, percent should be low.
- If Worker is almost done, percent should be high."""

_MAX_ERRORS = 3


class MentorAgent(BaseAgent):
    def __init__(self, cfg: SessionConfig, bus: CorrectionBus, mentor_tool_handlers: dict, ctrl: SessionController,
                 history_path: str | None = None, tracker=None, agent_name: str = "mentor"):
        self.cfg = cfg
        self.bus = bus
        self.mentor_tool_handlers = mentor_tool_handlers
        self.ctrl = ctrl
        self.history_path = history_path
        self._tracker = tracker
        self._agent_name = agent_name
        self._consecutive_errors = 0
        self._last_worker_messages: list[dict] = []  # RollingStrategy 生成大纲时使用
        self.messages: list[dict] = self._load() or [{"role": "system", "content": cfg.mentor_system}]
        bus.on_snapshot(self._on_worker_snapshot)

    def _load(self) -> list[dict] | None:
        if self.history_path and os.path.exists(self.history_path):
            try:
                with open(self.history_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return None

    def _save(self):
        if not self.history_path:
            return
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    def _on_usage(self, inp: int, out: int):
        if self._tracker:
            self._tracker.record(self._agent_name, inp, out)

    async def _on_worker_snapshot(self, snapshot: WorkerSnapshot):
        if self.ctrl.is_stopped:
            return

        # 保存最新 Worker 消息供 RollingStrategy 生成大纲使用
        self._last_worker_messages = snapshot.messages

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

        eval_prompt = MENTOR_EVAL_PROMPT.format(
            task=self.cfg.task[:1000],
            round=snapshot.round,
            worker_context=worker_context,
        )
        self.messages.append({"role": "user", "content": eval_prompt})

        try:
            response = await chat(self.cfg.mentor_model, self.messages, self.cfg.tool_schemas,
                                  on_usage=self._on_usage)
        except Exception as e:
            self._consecutive_errors += 1
            if self._consecutive_errors >= _MAX_ERRORS:
                error_msg("Mentor", str(e))
                self.ctrl.set_error(f"Mentor LLM error: {e}")
            else:
                error_msg("Mentor", f"{e} （连续错误 {self._consecutive_errors}/{_MAX_ERRORS}，跳过本轮评估）")
            return

        self._consecutive_errors = 0
        self.messages.append(response)
        self._save()
        content = response.get("content", "")

        if response.get("tool_calls"):
            for tc in response["tool_calls"]:
                name = tc["function"]["name"]
                args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
                result = execute_tool(name, args, self.mentor_tool_handlers)
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
            mentor_interrupt(snapshot.round, f"[ROLLBACK] {reason}")
            await self.bus.inject_rollback(snapshot, reason)
        elif upper.startswith("CORRECT:"):
            correction = stripped[len("CORRECT:"):].strip()
            mentor_interrupt(snapshot.round, correction)
            await self.bus.inject_correction(correction)
        else:
            mentor_ok(snapshot.round)

        await self._update_progress(snapshot, visible)

    async def _update_progress(self, snapshot: WorkerSnapshot, visible_messages: list[dict]):
        recent_actions = []
        for m in visible_messages[-6:]:
            if m.get("role") == "assistant" and m.get("tool_calls"):
                for tc in m["tool_calls"]:
                    recent_actions.append(tc["function"]["name"])
            elif m.get("role") == "assistant" and m.get("content"):
                recent_actions.append(m["content"][:60])
        actions_str = "; ".join(recent_actions[-4:]) if recent_actions else "无"

        progress_prompt = _PROGRESS_EVAL_PROMPT.format(
            task=self.cfg.task[:200],
            round=snapshot.round,
            actions=actions_str,
        )

        try:
            progress_resp = await chat(
                self.cfg.mentor_model,
                [{"role": "user", "content": progress_prompt}],
                None,
                on_usage=self._on_usage,
            )
            raw = progress_resp.get("content", "")
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
            data = json.loads(json_str)

            state = ProgressState(
                total_steps=data.get("total_steps", 5),
                current_step=data.get("current_step", 0),
                step_name=data.get("step_name", "进行中"),
                percent=float(data.get("percent", 0)),
                status="running",
            )
            self.bus.update_progress(state)
            update_progress_bar(state.percent, f"第{state.current_step + 1}/{state.total_steps}步: {state.step_name}")
        except Exception:
            fallback = min(snapshot.round * 10, 90)
            update_progress_bar(fallback, f"第{snapshot.round}轮")

    async def answer_question(self, question: str) -> str:
        prompt = f"[WORKER QUESTION] {question}\nAnswer based on your private knowledge. Be specific and helpful."
        self.messages.append({"role": "user", "content": prompt})
        try:
            response = await chat(self.cfg.mentor_model, self.messages, None,
                                  on_token=mentor_token, on_usage=self._on_usage)
        except Exception as e:
            return f"[Mentor错误] {e}"
        self.messages.append(response)
        return response.get("content", "")

    async def run(self, task: str) -> None:
        """Mentor 是被动驱动的，不需要主循环。
        Worker 每轮调用 publish_snapshot，触发 bus.on_snapshot → _on_worker_snapshot。
        此方法仅满足 BaseAgent 契约。
        """
        pass

    async def chat_direct(self, user_input: str) -> str:
        self.messages.append({"role": "user", "content": f"[USER DIRECT] {user_input}"})
        try:
            response = await chat(self.cfg.mentor_model, self.messages, self.cfg.tool_schemas)
        except Exception as e:
            return f"Error: {e}"
        self.messages.append(response)
        return response.get("content", "")
