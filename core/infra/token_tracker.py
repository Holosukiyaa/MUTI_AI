"""
core/infra/token_tracker.py — Token 用量追踪器

每个 Squad 持有一个 TokenTracker 实例，追踪所有 Agent 的累计 token 消耗。
达到阈值时设置 needs_roll 标志，通知 RollingStrategy 触发角色轮换。
"""
from dataclasses import dataclass
from typing import Callable


# 默认阈值：输入 176K，输出 24K（总计 200K 上下文窗口）
DEFAULT_INPUT_LIMIT = 176_000
DEFAULT_OUTPUT_LIMIT = 24_000


@dataclass
class TokenUsage:
    input_tokens: int = 0
    output_tokens: int = 0

    @property
    def total(self) -> int:
        return self.input_tokens + self.output_tokens

    def to_dict(self) -> dict:
        return {
            "input": self.input_tokens,
            "output": self.output_tokens,
            "total": self.total,
        }


class TokenTracker:
    """
    追踪 Squad 内所有 Agent 的 token 消耗。
    线程安全：asyncio 单线程模型下无需锁。
    """

    def __init__(
        self,
        input_limit: int = DEFAULT_INPUT_LIMIT,
        output_limit: int = DEFAULT_OUTPUT_LIMIT,
        mentor_name: str = "Mentor",
        worker_name: str = "Worker",
    ):
        self.input_limit = input_limit
        self.output_limit = output_limit
        self.mentor_name = mentor_name
        self.worker_name = worker_name
        self.generation = 0  # 当前代数，轮换时递增

        self._by_agent: dict[str, TokenUsage] = {}
        self._total = TokenUsage()
        self._threshold_callbacks: list[Callable[["TokenTracker"], None]] = []
        self._threshold_fired = False  # 只触发一次

    def on_threshold(self, cb: Callable[["TokenTracker"], None]):
        """注册阈值回调，输入或输出任意一个超标时触发（只触发一次）。"""
        self._threshold_callbacks.append(cb)

    def record(self, agent_name: str, input_tokens: int, output_tokens: int):
        """记录一次 LLM 调用的 token 用量。"""
        if agent_name not in self._by_agent:
            self._by_agent[agent_name] = TokenUsage()
        self._by_agent[agent_name].input_tokens += input_tokens
        self._by_agent[agent_name].output_tokens += output_tokens
        self._total.input_tokens += input_tokens
        self._total.output_tokens += output_tokens

        if not self._threshold_fired:
            if (
                self._total.input_tokens >= self.input_limit
                or self._total.output_tokens >= self.output_limit
            ):
                self._threshold_fired = True
                for cb in self._threshold_callbacks:
                    try:
                        cb(self)
                    except Exception:
                        pass

    def reset_threshold(self):
        """角色轮换后重置阈值标志，允许下一轮再次触发。"""
        self._threshold_fired = False
        self.generation += 1
        self._total = TokenUsage()
        self._by_agent.clear()

    def update_codenames(self, mentor_name: str, worker_name: str):
        """轮换时更新代号。"""
        self.mentor_name = mentor_name
        self.worker_name = worker_name

    @property
    def total(self) -> TokenUsage:
        return self._total

    @property
    def needs_roll(self) -> bool:
        """是否已触发过阈值（等待角色轮换）。"""
        return self._threshold_fired

    def input_percent(self) -> float:
        return min(self._total.input_tokens / self.input_limit * 100, 100)

    def output_percent(self) -> float:
        return min(self._total.output_tokens / self.output_limit * 100, 100)

    def to_dict(self) -> dict:
        mentor_usage = TokenUsage()
        worker_usage = TokenUsage()
        for name, usage in self._by_agent.items():
            if "mentor" in name.lower():
                mentor_usage.input_tokens += usage.input_tokens
                mentor_usage.output_tokens += usage.output_tokens
            elif "worker" in name.lower():
                worker_usage.input_tokens += usage.input_tokens
                worker_usage.output_tokens += usage.output_tokens

        return {
            "input": self._total.input_tokens,
            "output": self._total.output_tokens,
            "input_limit": self.input_limit,
            "output_limit": self.output_limit,
            "input_percent": round(self.input_percent(), 1),
            "output_percent": round(self.output_percent(), 1),
            "mentor_name": self.mentor_name,
            "worker_name": self.worker_name,
            "generation": self.generation,
            "mentor": mentor_usage.to_dict(),
            "worker": worker_usage.to_dict(),
            "by_agent": {k: v.to_dict() for k, v in self._by_agent.items()},
        }
