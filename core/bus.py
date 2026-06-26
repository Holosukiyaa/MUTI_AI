import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable


@dataclass
class WorkerSnapshot:
    round: int
    messages: list[dict]
    last_response: str
    file_snapshots: dict[str, str | None] = field(default_factory=dict)
    # value=None 表示该文件是本轮新建的（回滚时删除）


CorrectionHandler = Callable[[str], Awaitable[None]]


class CorrectionBus:
    def __init__(self):
        self._correction_queue: asyncio.Queue[str] = asyncio.Queue()
        self._rollback_queue: asyncio.Queue[tuple[WorkerSnapshot, str]] = asyncio.Queue()
        self._snapshot_callbacks: list[Callable[[WorkerSnapshot], Awaitable[None]]] = []
        self._eval_done = asyncio.Event()
        self._eval_done.set()

    def on_snapshot(self, cb: Callable[[WorkerSnapshot], Awaitable[None]]):
        self._snapshot_callbacks.append(cb)

    async def publish_snapshot(self, snapshot: WorkerSnapshot):
        self._eval_done.clear()
        try:
            for cb in self._snapshot_callbacks:
                await cb(snapshot)
        finally:
            self._eval_done.set()

    async def wait_eval_done(self):
        await self._eval_done.wait()

    async def inject_correction(self, correction: str):
        await self._correction_queue.put(correction)

    def drain_corrections(self) -> list[str]:
        corrections = []
        while not self._correction_queue.empty():
            try:
                corrections.append(self._correction_queue.get_nowait())
            except asyncio.QueueEmpty:
                break
        return corrections

    async def inject_rollback(self, snapshot: WorkerSnapshot, reason: str):
        await self._rollback_queue.put((snapshot, reason))

    def drain_rollback(self) -> tuple[WorkerSnapshot, str] | None:
        if not self._rollback_queue.empty():
            try:
                return self._rollback_queue.get_nowait()
            except asyncio.QueueEmpty:
                pass
        return None
