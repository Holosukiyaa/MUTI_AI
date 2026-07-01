import json
import os
from core.config import ModelConfig
from core.llm import chat

# ── 工具定义 ────────────────────────────────────────────────────

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

_SAVE_BLUEPRINT_TOOL = {
    "type": "function",
    "function": {
        "name": "save_blueprint",
        "description": "将完整的蓝图文档保存到当前项目组的 blueprints/ 目录，供执行者 Director 后续调用。",
        "parameters": {
            "type": "object",
            "properties": {
                "filename": {
                    "type": "string",
                    "description": "蓝图文件名（英文/拼音，.md 结尾），例如 dungeon_game_v1.md"
                },
                "content": {
                    "type": "string",
                    "description": "完整的蓝图 Markdown 内容，必须包含：项目目标、技术选型、模块划分、每个模块的详细规格和数值约束"
                }
            },
            "required": ["filename", "content"]
        }
    }
}

# ── Director 角色类型 ─────────────────────────────────────────────

# 可用角色枚举
DIRECTOR_ROLES = ["executor", "architect", "manager", "custom"]

# 各角色的显示名称
ROLE_DISPLAY_NAMES = {
    "executor": "项目执行者",
    "architect": "蓝图规划师",
    "manager": "项目管理员",
    "custom": "自定义",
}

# ── 各角色系统提示词 ─────────────────────────────────────────────

_SYSTEM_EXECUTOR = """你是 Echelon 框架的【项目执行者】，直接与用户对话，将任务交给 Squad 执行。

你的职责：
1. 与用户对话，理解目标，主动追问关键细节
2. 如果项目组中有蓝图规划师生成的蓝图文档（在 blueprints/ 目录下），请先阅读并基于蓝图制定执行计划
3. 制定完整计划后，调用 assign_to_squad 创建 Squad
   - blueprint：给 Mentor 的完整设计蓝图（详细！包含所有规范、数值、约束）
   - task：给 Worker 的任务描述（不含设计细节，Worker 需要问 Mentor）
4. 一次可以创建多个 Squad 并行执行不同子任务

重要：blueprint 必须足够详细，Mentor 是 Worker 获取信息的唯一渠道。"""

_SYSTEM_ARCHITECT = """你是 Echelon 框架的【蓝图规划师】，专注于深度需求分析和系统设计。

你的职责：
1. 与用户进行深入对话，充分理解项目目标、技术要求、约束条件
2. 主动追问关键决策点：技术选型、功能优先级、性能指标、交付标准
3. 基于讨论结果，生成一份详细、结构化的蓝图文档
4. 调用 save_blueprint 工具将蓝图保存到项目组，供执行者 Director 后续使用

蓝图文档必须包含：
- 项目目标与验收标准
- 技术选型与理由
- 模块划分与依赖关系
- 每个模块的详细规格（接口、数据结构、算法、数值约束）
- 已知风险与约束

注意：你只负责规划，不直接启动 Squad 执行任务。"""

_SYSTEM_MANAGER = """你是 Echelon 框架的【项目管理员】，专职管理项目文件、归档记录和项目状态。

你的职责：
1. 帮助用户整理和归档项目文件
2. 维护项目进度记录和版本历史
3. 管理蓝图文档的版本（调用 save_blueprint 保存更新的蓝图）
4. 提供项目状态报告和文件索引

你不直接启动 Squad 执行任务，专注于项目的组织和管理工作。"""

_SYSTEMS = {
    "executor": _SYSTEM_EXECUTOR,
    "architect": _SYSTEM_ARCHITECT,
    "manager": _SYSTEM_MANAGER,
    "custom": "",
}

# 各角色可用的工具
_TOOLS_BY_ROLE = {
    "executor": [_ASSIGN_TOOL],
    "architect": [_SAVE_BLUEPRINT_TOOL],
    "manager": [_SAVE_BLUEPRINT_TOOL],
    "custom": [_ASSIGN_TOOL, _SAVE_BLUEPRINT_TOOL],
}

# ── 验收提示词 ───────────────────────────────────────────────────

_ACCEPTANCE_PROMPT = """你是 Echelon 框架的 Director，Squad 刚刚完成了一项任务，请你做最终验收。

原始任务：
{task}

Squad 生成的文件及内容：
{file_list}

请简洁地评估完成情况（2-4句话），指出是否达成目标，以及主要成果。格式：
✓ 验收通过 / ✗ 验收未通过
[评估内容]"""


# ── DirectorAgent ─────────────────────────────────────────────────

class DirectorAgent:
    def __init__(
        self,
        model: ModelConfig,
        history_path: str,
        name: str = "Director",
        role: str = "executor",
        custom_system: str = "",
        blueprints_dir: str | None = None,
    ):
        self.model = model
        self.name = name
        self.role = role if role in DIRECTOR_ROLES else "executor"
        self.history_path = history_path
        self.blueprints_dir = blueprints_dir
        self.last_tool_calls: list[dict] = []
        self.last_blueprint_saves: list[dict] = []

        # 决定系统提示词
        if self.role == "custom":
            system_content = custom_system or "你是一个 AI 助手，直接与用户对话帮助完成任务。"
        else:
            system_content = _SYSTEMS[self.role]

            # 执行者：如果有蓝图目录，附加蓝图列表到系统提示词
            if self.role == "executor" and blueprints_dir and os.path.isdir(blueprints_dir):
                blueprint_files = [f for f in os.listdir(blueprints_dir) if f.endswith(".md")]
                if blueprint_files:
                    bp_list = "\n".join(f"  - {f}" for f in sorted(blueprint_files))
                    system_content += f"\n\n当前项目组已有以下蓝图文档（位于 blueprints/ 目录）：\n{bp_list}\n请在制定计划前先阅读相关蓝图。"

        self.messages: list[dict] = self._load()
        if not self.messages:
            self.messages = [{"role": "system", "content": system_content}]

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

    def _get_tools(self) -> list[dict]:
        return _TOOLS_BY_ROLE.get(self.role, [_ASSIGN_TOOL])

    async def chat(self, user_input: str, on_token=None) -> str:
        self.messages.append({"role": "user", "content": user_input})
        tools = self._get_tools()
        response = await chat(self.model, self.messages, tools or None, on_token=on_token)
        self.last_tool_calls = response.get("tool_calls") or []
        self.last_blueprint_saves = []
        self.messages.append(response)
        self.save()
        return response.get("content", "")

    def handle_save_blueprint(self, tc: dict) -> str:
        """处理 save_blueprint 工具调用，将蓝图写入 blueprints_dir。"""
        try:
            args = json.loads(tc["function"]["arguments"]) if isinstance(tc["function"]["arguments"], str) else tc["function"]["arguments"]
        except Exception:
            return "参数解析失败"

        filename = args.get("filename", "blueprint.md")
        content = args.get("content", "")

        if not filename.endswith(".md"):
            filename += ".md"

        if self.blueprints_dir:
            os.makedirs(self.blueprints_dir, exist_ok=True)
            path = os.path.join(self.blueprints_dir, filename)
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self.last_blueprint_saves.append({"filename": filename, "path": path})
            return f"蓝图已保存：{filename}（{len(content)} 字符）"
        else:
            return "未配置蓝图目录，无法保存"

    def confirm_tool_result(self, tool_call_id: str, result: str):
        self.messages.append({
            "role": "tool",
            "tool_call_id": tool_call_id,
            "content": result
        })
        self.save()

    async def accept(self, task: str, file_list: str) -> str:
        """由 Director 对 Squad 完成的任务做 LLM 验收，返回验收报告。"""
        prompt = _ACCEPTANCE_PROMPT.format(task=task[:500], file_list=file_list)
        try:
            resp = await chat(self.model, [{"role": "user", "content": prompt}])
            return resp.get("content", "验收完成")
        except Exception as e:
            return f"验收失败：{e}"

    def history(self) -> list[dict]:
        return [m for m in self.messages if m["role"] != "system"]

    def clear(self):
        self.messages = [self.messages[0]]
        self.last_tool_calls = []
        self.last_blueprint_saves = []
        self.save()


# 向后兼容别名
PlannerAgent = DirectorAgent
