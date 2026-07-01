"""
core/squad.py — Squad 生命周期封装

一个 Squad = 一个 Mentor + 一个 Worker。
该模块负责：
  - 目录结构管理
  - Agent 实例化与编排
  - 状态追踪（PENDING → RUNNING → DONE / ERROR）
  - 进度推送（通过注入的 push_event 回调，不依赖 server 模块）
"""
import asyncio
import os
import json
from enum import Enum
from typing import Callable

from core.config import SessionConfig, ModelConfig, FINISH_TASK_SCHEMA
from core.infra.bus import CorrectionBus
from core.infra.tools import make_tools
from core.infra.session import SessionController, State
from core.agents.base import BaseAgent
import display


class SquadStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    DONE = "done"
    ERROR = "error"


_ASK_MENTOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_mentor",
        "description": "向管家询问你不知道的设计信息或需求细节",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
}

_MENTOR_SYSTEM_WITH_BLUEPRINT = (
    "你是 Mentor（管家），是本 Squad 的唯一知识持有者。\n"
    "以下蓝图和设计信息只有你能看到，Worker 对此一无所知：\n\n{blueprint}\n\n"
    "你的职责：\n"
    "1. 当 Worker 通过 ask_mentor 工具提问时，根据蓝图详细、准确地回答，给出具体数值和细节\n"
    "2. 每轮审查 Worker 的工作，偏离规范时用 CORRECT: 纠正，严重错误用 ROLLBACK: 回滚\n"
    "3. 不需要主动发起对话，等待 Worker 提问或审查快照\n"
    "回答提问时要具体直接，不要说'请参考文档'，直接告诉 Worker 答案。"
)

_MENTOR_SYSTEM_DEFAULT = (
    "你是 Mentor，负责监督 Worker 执行任务，是设计信息的唯一来源。"
    "Worker 会通过 ask_mentor 向你提问，请据实回答。发现错误时用 CORRECT: 纠正。"
)

_WORKER_SYSTEM = (
    "你是 Worker，负责编写代码完成任务。\n"
    "重要：你对当前项目的设计一无所知。你必须通过 ask_mentor 工具向管家（Mentor）提问来获取所有设计信息。\n"
    "工作流程：\n"
    "1. 先用 ask_mentor 询问任务的整体设计、需求和技术细节\n"
    "2. 收到回答后继续追问，直到掌握足够信息\n"
    "3. 了解清楚后用 write_file 编写代码\n"
    "4. 完成后调用 finish_task\n"
    "收到 [MENTOR CORRECTION] 消息时，这是高优先级指令，必须立即按照纠正内容修改。\n"
    "写文件规则：单次 write_file 内容不得超过 300 行。超过时，先用 write_file 写前半部分，再用 append_file 追加后续内容。\n\n"
    "【调用 finish_task 前必须逐一确认以下全部条件】\n"
    "- 所有要求的文件均已用 write_file / append_file 写入完整可运行内容\n"
    "- 文件中不存在任何 TODO、占位符、骨架代码或省略号\n"
    "- 代码在目标环境中可直接运行，无需额外补全\n"
    "- 如有多个文件，每个文件的功能逻辑均已完整实现\n"
    "违反上述任一条件即不得调用 finish_task，应继续编写直到真正完成。"
)


class Squad:
    """
    封装单个 Mentor+Worker 搭档的完整生命周期。

    使用方式：
        p = Squad.create(name, task, blueprint, squads_dir, log_dir)
        await p.start(model, push_event_fn)
    """

    def __init__(
        self,
        name: str,
        task: str,
        squad_dir: str,
        log_path: str | None = None,
        strategy: "SquadStrategy | None" = None,
    ):
        self.name = name
        self.task = task
        self.status = SquadStatus.PENDING
        self.progress: float = 0.0
        self.report: str = ""
        self.error: str = ""

        self._dir = squad_dir
        self._mentor_dir = os.path.join(squad_dir, "mentor")
        self._worker_dir = os.path.join(squad_dir, "worker")
        self._log_path = log_path

        # 工作策略，默认 RollingStrategy（智能轮换）
        from core.squad.strategy import RollingStrategy
        self.strategy: "SquadStrategy" = strategy or RollingStrategy()

        # 公开属性，TUI 层可直接访问（默认策略下取第一个）
        self.ctrl = SessionController()
        self.mentors: list[BaseAgent] = []
        self.workers: list[BaseAgent] = []
        self._agents_ready = asyncio.Event()
        self._asyncio_task: asyncio.Task | None = None

    @property
    def mentor(self) -> "BaseAgent | None":
        """兼容属性：返回第一个 Mentor（单策略场景）。"""
        return self.mentors[0] if self.mentors else None

    @property
    def worker(self) -> "BaseAgent | None":
        """兼容属性：返回第一个 Worker（单策略场景）。"""
        return self.workers[0] if self.workers else None

    # ── 工厂方法 ────────────────────────────────────────────────

    @classmethod
    def create(
        cls,
        name: str,
        task: str,
        blueprint: str,
        squads_dir: str,
        log_dir: str | None = None,
        clear_history: bool = True,
    ) -> "Squad":
        """
        在磁盘上初始化目录结构，写入 blueprint，返回 Squad 实例。
        clear_history=True 时清除旧的 Worker/Mentor 对话历史（防止同名重建污染）。
        """
        squad_dir = os.path.join(squads_dir, name)
        mentor_dir = os.path.join(squad_dir, "mentor")
        worker_dir = os.path.join(squad_dir, "worker")
        os.makedirs(mentor_dir, exist_ok=True)
        os.makedirs(worker_dir, exist_ok=True)

        # 写入蓝图
        with open(os.path.join(mentor_dir, "blueprint.md"), "w", encoding="utf-8") as f:
            f.write(blueprint)

        # 写入 Squad 配置
        with open(os.path.join(squad_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"name": name, "description": task[:60]}, f, ensure_ascii=False, indent=2)

        # 清除旧历史（Bug #2 修复）
        if clear_history:
            for hist in [
                os.path.join(mentor_dir, "history.json"),
                os.path.join(worker_dir, "history.json"),
            ]:
                if os.path.exists(hist):
                    os.remove(hist)

        log_path = None
        if log_dir:
            os.makedirs(log_dir, exist_ok=True)
            log_path = os.path.join(log_dir, f"{name}.log")

        return cls(name=name, task=task, squad_dir=squad_dir, log_path=log_path)

    @classmethod
    def load(cls, squads_dir: str, name: str) -> "Squad | None":
        """从磁盘加载已有 Squad（用于刷新页面后恢复列表）。"""
        squad_dir = os.path.join(squads_dir, name)
        config_path = os.path.join(squad_dir, "config.json")
        if not os.path.isfile(config_path):
            return None
        try:
            with open(config_path, encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            return None
        return cls(name=name, task=cfg.get("description", ""), squad_dir=squad_dir)

    # ── 生命周期 ────────────────────────────────────────────────

    async def start(self, model: ModelConfig, push_event: Callable[[dict], None] | None = None,
                    accept_fn: Callable[[str, str], "asyncio.Future"] | None = None):
        """异步启动 Mentor+Worker，立即返回（任务在后台运行）。
        accept_fn: 可选验收回调，签名为 async (task, file_list) -> str，由 Planner 执行验收。
        """
        self.status = SquadStatus.RUNNING
        self._asyncio_task = asyncio.create_task(
            self._run(model, push_event or (lambda _: None), accept_fn)
        )

    def stop(self):
        """请求停止（发信号给 SessionController）。"""
        self.ctrl.stop()

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "task": self.task,
            "status": self.status.value,
            "progress": self.progress,
            "report": self.report,
            "error": self.error,
        }

    # ── 内部编排 ────────────────────────────────────────────────

    async def _run(self, model: ModelConfig, push_event: Callable[[dict], None],
                   accept_fn: Callable | None = None):
        import traceback

        if self._log_path:
            display.set_log_path(self._log_path)

        # 设置 display 上下文，所有后续 _push() 自动带上 squad 名
        display.set_squad_name(self.name)

        # 立即推送启动确认，让用户知道 Squad 已开始工作
        push_event({"type": "session_line", "squad": self.name, "line": f"🚀 Squad [{self.name}] 已启动"})
        push_event({"type": "session_line", "squad": self.name, "line": f"📋 任务：{self.task[:120]}"})

        # 读取蓝图
        blueprint_path = os.path.join(self._mentor_dir, "blueprint.md")
        blueprint = ""
        if os.path.exists(blueprint_path):
            with open(blueprint_path, encoding="utf-8") as f:
                blueprint = f.read()

        mentor_system = (
            _MENTOR_SYSTEM_WITH_BLUEPRINT.format(blueprint=blueprint)
            if blueprint
            else _MENTOR_SYSTEM_DEFAULT
        )

        bus = CorrectionBus()
        from core.infra.token_tracker import TokenTracker
        import random
        _MENTOR_NAMES = ["Athena","Socrates","Plato","Kant","Hegel","Leibniz","Descartes","Spinoza"]
        _WORKER_NAMES = ["Atlas","Hephaestus","Vulcan","Prometheus","Hermes","Ares","Kronos","Titan"]
        mentor_codename = random.choice(_MENTOR_NAMES)
        worker_codename = random.choice(_WORKER_NAMES)
        tracker = TokenTracker(mentor_name=mentor_codename, worker_name=worker_codename)

        push_event({"type": "session_line", "squad": self.name,
                    "line": f"🎭 Mentor: {mentor_codename}  ·  Worker: {worker_codename}"})

        # 注册进度回调 → 推送到前端
        def _on_progress(state):
            self.progress = state.percent
            push_event({"type": "session_progress", "squad": self.name, "percent": state.percent})

        bus.on_progress(_on_progress)

        # 注册 token 阈值回调 → 推送统计到前端
        def _on_token_threshold(t: TokenTracker):
            push_event({"type": "token_update", "squad": self.name, **t.to_dict()})
            display.system_msg(
                f"[Token] 阈值触发：输入 {t.total.input_tokens:,} / {t.input_limit:,}，"
                f"输出 {t.total.output_tokens:,} / {t.output_limit:,}"
            )

        tracker.on_threshold(_on_token_threshold)

        # 每轮结束也推送 token 统计
        def _push_token_stats():
            push_event({"type": "token_update", "squad": self.name, **tracker.to_dict()})

        bus.on_progress(lambda _: _push_token_stats())

        worker_schemas, _ = make_tools([self._worker_dir])

        cfg = SessionConfig(
            task=self.task,
            project_root=self._dir,
            worker_subdirs=["worker"],
            mentor_model=model,
            worker_model=model,
            mentor_system=mentor_system,
            worker_system=_WORKER_SYSTEM,
            tool_schemas=worker_schemas + [_ASK_MENTOR_SCHEMA, FINISH_TASK_SCHEMA],
        )

        # 委托策略实例化 Agent（支持 N×Mentor + N×Worker）
        self.mentors, self.workers = await self.strategy.build(
            cfg, bus, self.ctrl, self._mentor_dir, self._worker_dir, tracker
        )
        self._agents_ready.set()  # 通知 TUI 层 Agent 已就绪

        display.session_start(
            task=self.task,
            worker_scope=self._worker_dir,
            mentor_scope=self._mentor_dir,
            model_info=f"{model.model}（{self.strategy.name}）",
        )
        display.init_progress_bar(task_desc=f"{self.name} 任务进度")

        try:
            # 并发启动所有 Worker（单策略下只有一个）
            await asyncio.gather(*[w.run(self.task) for w in self.workers])
        except Exception:
            tb = traceback.format_exc()
            self.status = SquadStatus.ERROR
            self.error = tb[-300:]
            push_event({"type": "session_done", "squad": self.name, "status": "error", "report": self.error})
            return
        finally:
            display.stop_progress_bar()

        if self.ctrl.state == State.ERROR:
            self.status = SquadStatus.ERROR
            self.error = self.ctrl.error_msg or "未知错误"
            display.error_msg("Session", self.error)
            push_event({"type": "session_done", "squad": self.name, "status": "error", "report": self.error})
        else:
            self.status = SquadStatus.DONE
            self.progress = 100.0
            file_list = self._get_file_list()
            # 验收报告由 Planner 生成（有 accept_fn 时）
            if accept_fn:
                try:
                    self.report = await accept_fn(self.task, file_list)
                except Exception:
                    self.report = self._build_report(file_list)
            else:
                self.report = self._build_report(file_list)
            display.session_end()
            push_event({"type": "session_done", "squad": self.name, "status": "ok", "report": self.report})

    def _get_file_list(self) -> str:
        """返回 worker 目录下所有文件的名称及内容（每文件限 3000 字符，总量限 12000 字符）。"""
        if not os.path.exists(self._worker_dir):
            return "无"
        files = sorted(f for f in os.listdir(self._worker_dir) if not f.startswith("history"))
        if not files:
            return "无"
        parts = []
        total = 0
        for fname in files:
            fpath = os.path.join(self._worker_dir, fname)
            try:
                with open(fpath, encoding="utf-8", errors="replace") as f:
                    content = f.read(3000)
                entry = f"=== {fname} ===\n{content}"
            except Exception:
                entry = f"=== {fname} === [无法读取]"
            if total + len(entry) > 12000:
                parts.append(f"=== {fname} === [已省略，总内容过长]")
                break
            parts.append(entry)
            total += len(entry)
        return "\n\n".join(parts)

    def _build_report(self, file_list: str | None = None) -> str:
        if file_list is None:
            file_list = self._get_file_list()
        return f"Squad [{self.name}] 已完成任务：{self.task[:100]}\n生成文件：{file_list}"
