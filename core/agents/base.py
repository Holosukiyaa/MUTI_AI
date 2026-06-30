"""
core/agents/base.py — Agent 抽象基类

所有 Agent（Mentor、Worker 及未来扩展）都继承此类。
约定：
  - run()       主执行入口，子类必须实现
  - chat_direct() 人工介入时的直接对话接口
"""
from abc import ABC, abstractmethod


class BaseAgent(ABC):

    @abstractmethod
    async def run(self, task: str) -> None:
        """Agent 主循环，执行直到完成、停止或出错。"""
        ...

    @abstractmethod
    async def chat_direct(self, user_input: str) -> str:
        """暂停状态下与用户直接对话，返回 Agent 回复。"""
        ...
