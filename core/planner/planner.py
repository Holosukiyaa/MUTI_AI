import json
import os
from core.config import ModelConfig
from core.llm import chat

_ASSIGN_TOOL = {
    "type": "function",
    "function": {
        "name": "assign_to_squad",
        "description": "创建一个新的 Mentor+Worker 搭档（Squad）并分配任务。Mentor 会持有蓝图，Worker 从零开始执行。",
        "parameters": {
            "type": "object",
            "properties": {
                "squad_name": {
                    "type": "string",
                    "description": "Squad 的唯一名称（英文/拼音，用作目录名）"
                },
                "blueprint": {
                    "type": "string",
                    "description": "Mentor 的私有知识：完整的蓝图、设计规范、技术约束。Worker 看不到这些内容，必须通过 ask_mentor 获取。"
                },
                "task": {
                    "type": "string",
                    "description": "分配给 Worker 的任务描述（不包含设计细节，细节在 blueprint 里）"
                }
            },
            "required": ["squad_name", "blueprint", "task"]
        }
    }
}

_SYSTEM = """你是 Echelon 框架的 Planner（规划者），直接与用户对话。
你的核心能力是将用户目标拆解为具体任务，并通过 assign_to_squad 工具创建 Mentor+Worker 搭档来执行。

工作流程：
1. 与用户对话，理解目标，主动追问关键细节
2. 制定完整计划后，调用 assign_to_squad 创建 Squad
   - blueprint：给 Mentor 的完整设计蓝图（详细！包含所有规范、数值、约束）
   - task：给 Worker 的任务描述（不含设计细节，Worker 需要问 Mentor）
3. 一次可以创建多个 Squad 并行执行不同子任务

重要：blueprint 必须足够详细，Mentor 是 Worker 获取信息的唯一渠道。"""


class PlannerAgent:
    def __init__(self, model: ModelConfig, history_path: str, name: str = "Planner"):
        self.model = model
        self.name = name
        self.history_path = history_path
        self.messages: list[dict] = self._load()
        self.last_tool_calls: list[dict] = []
        if not self.messages:
            self.messages = [{"role": "system", "content": _SYSTEM}]

    def _load(self) -> list[dict]:
        if os.path.exists(self.history_path):
            try:
                with open(self.history_path, encoding="utf-8") as f:
                    return json.load(f)
            except Exception:
                pass
        return []

    def save(self):
        os.makedirs(os.path.dirname(self.history_path), exist_ok=True)
        with open(self.history_path, "w", encoding="utf-8") as f:
            json.dump(self.messages, f, ensure_ascii=False, indent=2)

    async def chat(self, user_input: str, on_token=None) -> str:
        self.messages.append({"role": "user", "content": user_input})
        response = await chat(self.model, self.messages, [_ASSIGN_TOOL], on_token=on_token)
        self.last_tool_calls = response.get("tool_calls") or []
        self.messages.append(response)
        self.save()
        return response.get("content", "")

    def confirm_tool_result(self, tool_call_id: str, result: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })
        self.save()

    def history(self) -> list[dict]:
        return [m for m in self.messages if m["role"] != "system"]

    def clear(self):
        self.messages = [self.messages[0]]
        self.last_tool_calls = []
        self.save()
