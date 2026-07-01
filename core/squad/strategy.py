"""
core/squad/strategy.py — Squad 工作策略抽象层

定义 Squad 内部 Mentor+Worker 的组合方式和协作模式。

策略列表：
  SinglePairStrategy — 默认：1 Mentor + 1 Worker，不轮换
  RollingStrategy    — 智能轮换：Worker token 达阈值时 Mentor 晋升为 Worker，
                       同时召唤新 Mentor 接管监督职能

扩展方式：
    class MyStrategy(SquadStrategy):
        async def build(self, cfg, bus, ctrl, mentor_dir, worker_dir, tracker=None):
            ...
            return mentors, workers
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import SessionConfig
    from core.infra.bus import CorrectionBus
    from core.infra.session import SessionController
    from core.infra.token_tracker import TokenTracker
    from core.agents.base import BaseAgent


class SquadStrategy(ABC):
    """Squad 策略基类，定义 Mentor+Worker 的组合方式。"""

    @abstractmethod
    async def build(
        self,
        cfg: "SessionConfig",
        bus: "CorrectionBus",
        ctrl: "SessionController",
        mentor_dir: str,
        worker_dir: str,
        tracker: "TokenTracker | None" = None,
    ) -> tuple[list["BaseAgent"], list["BaseAgent"]]:
        """
        实例化并返回 (mentors, workers)。
        Squad 编排层负责启动和协调它们。
        tracker 可选：用于需要感知 token 用量的策略。
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        """策略名称，用于日志和配置标识。"""
        ...


class SinglePairStrategy(SquadStrategy):
    """
    默认策略：1 Mentor + 1 Worker。
    Mentor 持有蓝图，Worker 通过 ask_mentor 获取信息。
    """

    @property
    def name(self) -> str:
        return "single_pair"

    async def build(
        self,
        cfg: "SessionConfig",
        bus: "CorrectionBus",
        ctrl: "SessionController",
        mentor_dir: str,
        worker_dir: str,
        tracker: "TokenTracker | None" = None,
    ) -> tuple[list["BaseAgent"], list["BaseAgent"]]:
        import os
        from core.agents.mentor import MentorAgent
        from core.agents.worker import WorkerAgent

        mentor = MentorAgent(
            cfg=cfg,
            bus=bus,
            mentor_tool_handlers=_make_handlers([mentor_dir]),
            ctrl=ctrl,
            history_path=os.path.join(mentor_dir, "history.json"),
            tracker=tracker,
            agent_name="mentor",
        )
        worker = WorkerAgent(
            cfg=cfg,
            bus=bus,
            tool_handlers=_make_handlers([worker_dir]),
            ctrl=ctrl,
            ask_mentor_fn=mentor.answer_question,
            history_path=os.path.join(worker_dir, "history.json"),
            tracker=tracker,
            agent_name="worker",
        )
        return [mentor], [worker]


class RollingStrategy(SquadStrategy):
    """
    智能轮换策略：Worker token 消耗达到阈值时触发角色轮换。

    轮换流程：
      1. Mentor 生成结构化交接大纲（handover.md）
      2. 当前 Mentor 晋升为新 Worker（携带蓝图 + 大纲，全新对话历史）
      3. 召唤新 Mentor，读取大纲后就绪
      4. TokenTracker 重置，下一代重新计数

    优势：
      - 不压缩，不损失信息
      - 晋升的 Mentor 本来就了解全局状态，无需任何摘要
      - 新 Mentor 只需读大纲（轻量），快速进入监督状态
    """

    @property
    def name(self) -> str:
        return "rolling"

    async def build(
        self,
        cfg: "SessionConfig",
        bus: "CorrectionBus",
        ctrl: "SessionController",
        mentor_dir: str,
        worker_dir: str,
        tracker: "TokenTracker | None" = None,
    ) -> tuple[list["BaseAgent"], list["BaseAgent"]]:
        import os
        from core.agents.mentor import MentorAgent
        from core.agents.worker import WorkerAgent

        generation = getattr(self, "_generation", 0)

        mentor = MentorAgent(
            cfg=cfg,
            bus=bus,
            mentor_tool_handlers=_make_handlers([mentor_dir]),
            ctrl=ctrl,
            history_path=os.path.join(mentor_dir, f"history_g{generation}.json"),
            tracker=tracker,
            agent_name=f"mentor_g{generation}",
        )
        worker = WorkerAgent(
            cfg=cfg,
            bus=bus,
            tool_handlers=_make_handlers([worker_dir]),
            ctrl=ctrl,
            ask_mentor_fn=mentor.answer_question,
            history_path=os.path.join(worker_dir, f"history_g{generation}.json"),
            tracker=tracker,
            agent_name=f"worker_g{generation}",
            on_threshold=lambda w=None, m=mentor: self._schedule_roll(cfg, bus, ctrl, mentor_dir, worker_dir, m, tracker, w),
        )
        # 把 worker 引用注入 on_threshold（闭包延迟绑定）
        _worker_ref = worker
        worker._on_threshold = lambda: self._schedule_roll(cfg, bus, ctrl, mentor_dir, worker_dir, mentor, tracker, _worker_ref)
        return [mentor], [worker]

    def _schedule_roll(
        self,
        cfg: "SessionConfig",
        bus: "CorrectionBus",
        ctrl: "SessionController",
        mentor_dir: str,
        worker_dir: str,
        current_mentor: "BaseAgent",
        tracker: "TokenTracker | None",
        old_worker: "BaseAgent | None" = None,
    ):
        """在 asyncio 事件循环中调度角色轮换任务。"""
        import asyncio
        asyncio.create_task(
            self._do_roll(cfg, bus, ctrl, mentor_dir, worker_dir, current_mentor, tracker, old_worker)
        )

    async def _do_roll(
        self,
        cfg: "SessionConfig",
        bus: "CorrectionBus",
        ctrl: "SessionController",
        mentor_dir: str,
        worker_dir: str,
        current_mentor: "BaseAgent",
        tracker: "TokenTracker | None",
        old_worker: "BaseAgent | None" = None,
    ):
        """执行角色轮换：生成大纲 → 晋升 Mentor → 召唤新 Mentor。"""
        import os
        from core.agents.mentor import MentorAgent
        from core.agents.worker import WorkerAgent
        from core.agents.handover import generate_handover
        from display import system_msg

        self._generation = getattr(self, "_generation", 0) + 1
        gen = self._generation
        system_msg(f"[RollingStrategy] Token 阈值触发，开始第 {gen} 代角色轮换")

        # 立即停止旧 Worker（不影响全局 ctrl，新 Worker 会接管）
        if old_worker is not None and hasattr(old_worker, "stop_self"):
            old_worker.stop_self()
            system_msg(f"[RollingStrategy] 旧 Worker 已停止")

        # 步骤 1：Mentor 生成交接大纲
        handover_path = os.path.join(mentor_dir, "handover.md")
        worker_messages = getattr(current_mentor, "_last_worker_messages", [])
        handover = await generate_handover(
            task=cfg.task,
            worker_messages=worker_messages,
            model=cfg.mentor_model,
            save_path=handover_path,
        )
        system_msg(f"[RollingStrategy] 交接大纲已生成（{len(handover)} 字符）")

        # 步骤 2：取消旧 Mentor 的 bus 订阅（停止监听快照）
        if current_mentor is not None and hasattr(current_mentor, "_on_worker_snapshot"):
            bus.remove_snapshot_listener(current_mentor._on_worker_snapshot)

        # 步骤 3：重置 TokenTracker，分配新代号
        if tracker:
            import random
            _MENTOR_NAMES = ["Athena","Socrates","Plato","Kant","Hegel","Leibniz","Descartes","Spinoza"]
            _WORKER_NAMES = ["Atlas","Hephaestus","Vulcan","Prometheus","Hermes","Ares","Kronos","Titan"]
            new_mentor_name = random.choice(_MENTOR_NAMES)
            new_worker_name = random.choice(_WORKER_NAMES)
            tracker.update_codenames(new_mentor_name, new_worker_name)
            tracker.reset_threshold()
            system_msg(f"[RollingStrategy] 第 {gen} 代代号：Mentor={new_mentor_name} · Worker={new_worker_name}")
        else:
            new_mentor_name = f"Mentor-G{gen}"
            new_worker_name = f"Worker-G{gen}"
            if tracker:
                tracker.reset_threshold()

        # 步骤 4：新 Worker 系统提示 = 原 Worker 系统提示 + 大纲
        promoted_system = (
            cfg.worker_system
            + f"\n\n# 任务交接大纲（上一代 Mentor 生成）\n{handover}\n\n"
            "以上大纲描述了已完成的工作、当前进度和重要约束，你必须在此基础上继续工作。"
        )
        promoted_cfg = _clone_cfg(cfg, worker_system=promoted_system)

        # 步骤 5：创建新 Worker（前 Mentor 晋升，全新历史）
        new_worker_hist = os.path.join(worker_dir, f"history_g{gen}.json")
        new_worker = WorkerAgent(
            cfg=promoted_cfg,
            bus=bus,
            tool_handlers=_make_handlers([worker_dir]),
            ctrl=ctrl,
            ask_mentor_fn=None,  # 新 Mentor 创建后补绑
            history_path=new_worker_hist,
            tracker=tracker,
            agent_name=f"worker_g{gen}",
        )

        # 步骤 6：召唤新 Mentor，携带大纲
        new_mentor_system = (
            cfg.mentor_system
            + f"\n\n# 任务交接大纲（请仔细阅读后才能开始监督）\n{handover}"
        )
        new_mentor_cfg = _clone_cfg(cfg, mentor_system=new_mentor_system)
        new_mentor_hist = os.path.join(mentor_dir, f"history_g{gen}.json")
        new_mentor = MentorAgent(
            cfg=new_mentor_cfg,
            bus=bus,
            mentor_tool_handlers=_make_handlers([mentor_dir]),
            ctrl=ctrl,
            history_path=new_mentor_hist,
            tracker=tracker,
            agent_name=f"mentor_g{gen}",
        )

        # 步骤 7：把新 Mentor 的 answer_question 注入新 Worker，同时绑定下一轮轮换回调
        new_worker.ask_mentor_fn = new_mentor.answer_question
        new_worker._on_threshold = lambda: self._schedule_roll(
            cfg, bus, ctrl, mentor_dir, worker_dir, new_mentor, tracker, new_worker
        )

        # 步骤 8：新 Mentor 预热（确认读懂大纲）
        warmup_prompt = (
            "你已收到任务交接大纲。请确认你已了解当前任务进度，回复'已就绪'即可开始监督工作。"
        )
        try:
            await new_mentor.answer_question(warmup_prompt)
            system_msg(f"[RollingStrategy] 第 {gen} 代 Mentor 预热完成，开始监督")
        except Exception as e:
            system_msg(f"[RollingStrategy] Mentor 预热失败（{e}），仍继续执行")

        # 步骤 9：启动新 Worker 继续任务（继承旧 Worker 轮次，避免归零）
        import asyncio
        old_round = getattr(old_worker, "round", 0) if old_worker else 0
        new_worker.round = old_round
        asyncio.create_task(new_worker.run(
            f"[继续执行] 请阅读系统提示中的交接大纲，从上次中断处继续完成任务。"
        ))
        system_msg(f"[RollingStrategy] 第 {gen} 代 Worker 已启动（从第 {old_round} 轮继续）")


def _clone_cfg(cfg, **overrides):
    """浅克隆 SessionConfig，覆盖指定字段。"""
    import copy
    c = copy.copy(cfg)
    for k, v in overrides.items():
        setattr(c, k, v)
    return c


def _make_handlers(roots: list[str]) -> dict:
    from core.infra.tools import make_tools
    _, handlers = make_tools(roots)
    return handlers
