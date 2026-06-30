"""
core/squad/strategy.py — Squad 工作策略抽象层

定义 Squad 内部 Mentor+Worker 的组合方式和协作模式。
当前默认策略：1 Mentor + 1 Worker（SinglePairStrategy）

扩展方式：
    class MyStrategy(SquadStrategy):
        async def build(self, cfg, bus, ctrl):
            mentors = [MentorAgent(...), MentorAgent(...)]  # N 个 Mentor
            workers = [WorkerAgent(...), WorkerAgent(...)]  # N 个 Worker
            return mentors, workers
"""
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.config import SessionConfig
    from core.runtime.bus import CorrectionBus
    from core.runtime.session import SessionController
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
    ) -> tuple[list["BaseAgent"], list["BaseAgent"]]:
        """
        实例化并返回 (mentors, workers)。
        Squad 编排层负责启动和协调它们。
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
        )
        worker = WorkerAgent(
            cfg=cfg,
            bus=bus,
            tool_handlers=_make_handlers([worker_dir]),
            ctrl=ctrl,
            ask_mentor_fn=mentor.answer_question,
            history_path=os.path.join(worker_dir, "history.json"),
        )
        return [mentor], [worker]


def _make_handlers(roots: list[str]) -> dict:
    from core.tools import make_tools
    _, handlers = make_tools(roots)
    return handlers
