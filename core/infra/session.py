import asyncio
from enum import Enum


class State(Enum):
    RUNNING = "running"
    PAUSED = "paused"
    STOPPED = "stopped"
    ERROR = "error"


class SessionController:
    def __init__(self):
        self.state = State.RUNNING
        self.paused_target: str | None = None
        self.error_msg: str | None = None
        self._resume_event = asyncio.Event()
        self._resume_event.set()

    def stop(self):
        self.state = State.STOPPED
        self._resume_event.set()

    def pause(self, target: str | None = None):
        self.state = State.PAUSED
        self.paused_target = target
        self._resume_event.clear()

    def resume(self):
        self.state = State.RUNNING
        self.paused_target = None
        self._resume_event.set()

    def set_error(self, msg: str):
        self.state = State.ERROR
        self.error_msg = msg
        self._resume_event.set()

    @property
    def is_running(self) -> bool:
        return self.state == State.RUNNING

    @property
    def is_stopped(self) -> bool:
        return self.state in (State.STOPPED, State.ERROR)

    async def wait_resume(self):
        await self._resume_event.wait()
