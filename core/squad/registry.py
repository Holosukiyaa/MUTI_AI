"""
core/squad_registry.py — Squad 全局注册表

负责：
  - 持有所有 Squad 实例（内存中）
  - 从磁盘扫描已有 Squad（刷新页面后可恢复列表）
  - 为 server 层提供统一的创建 / 查询 / 删除入口
"""
import os
import shutil
from typing import Callable

from core.squad.squad import Squad, SquadStatus
from core.config import ModelConfig


class SquadRegistry:
    def __init__(self, squads_dir: str):
        self._squads_dir = squads_dir
        self._instances: dict[str, Squad] = {}

    # ── 初始化：扫描磁盘 ────────────────────────────────────────

    def scan(self):
        """
        扫描 squads_dir，将已有目录加载为 DONE 状态的 Squad 占位实例。
        只在进程启动时调用一次；运行中的 Squad 会通过 register() 加入。
        """
        if not os.path.isdir(self._squads_dir):
            return
        for name in os.listdir(self._squads_dir):
            if name in self._instances:
                continue
            p = Squad.load(self._squads_dir, name)
            if p:
                p.status = SquadStatus.DONE  # 遗留数据视为已完成
                self._instances[name] = p

    # ── CRUD ────────────────────────────────────────────────────

    def create(
        self,
        name: str,
        task: str,
        blueprint: str,
        log_dir: str | None = None,
    ) -> Squad:
        """创建并注册新 Squad，清除同名旧历史。"""
        p = Squad.create(
            name=name,
            task=task,
            blueprint=blueprint,
            squads_dir=self._squads_dir,
            log_dir=log_dir,
            clear_history=True,
        )
        self._instances[name] = p
        return p

    def get(self, name: str) -> Squad | None:
        return self._instances.get(name)

    def all(self) -> list[Squad]:
        return list(self._instances.values())

    def delete(self, name: str) -> bool:
        """从内存和磁盘删除 Squad，若正在运行则先停止。"""
        p = self._instances.pop(name, None)
        if p:
            p.stop()
        squad_dir = os.path.join(self._squads_dir, name)
        if os.path.isdir(squad_dir):
            shutil.rmtree(squad_dir, ignore_errors=True)
            return True
        return p is not None

    # ── 启动 ────────────────────────────────────────────────────

    async def start(
        self,
        name: str,
        model: ModelConfig,
        push_event: Callable[[dict], None] | None = None,
    ):
        """启动已注册的 Squad（异步，立即返回）。"""
        p = self._instances.get(name)
        if p:
            await p.start(model, push_event)
