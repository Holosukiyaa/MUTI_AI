import asyncio
from dataclasses import dataclass, field
from typing import Callable, Awaitable


@dataclass
class WorkerSnapshot:
    round: int
    messages: list[dict]
    last_response: str


CorrectionHandler = Callable[[str], Awaitable[None]]


class CorrectionBus:
    def __init__(self):
        self._correction_queue: asyncio.Queue[str] = asyncio.Queue()
        self._snapshot_callbacks: list[Callable[[WorkerSnapshot], Awaitable[None]]] = []

    def on_snapshot(self, cb: Callable[[WorkerSnapshot], Awaitable[None]]):
        self._snapshot_callbacks.append(cb)

    async def publish_snapshot(self, snapshot: WorkerSnapshot):
        for cb in self._snapshot_callbacks:
            await cb(snapshot)

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
