from dataclasses import dataclass, field
from typing import Literal

Provider = Literal["openai", "anthropic"]

FINISH_TASK_SCHEMA = {
    "type": "function",
    "function": {
        "name": "finish_task",
        "description": "Call this when the task is fully complete.",
        "parameters": {"type": "object", "properties": {}, "required": []},
    },
}

@dataclass
class ModelConfig:
    provider: Provider
    model: str
    api_key: str
    base_url: str | None = None
    temperature: float = 0.7
    max_tokens: int = 8192

@dataclass
class SessionConfig:
    task: str
    project_root: str
    worker_subdirs: list[str]
    mentor_model: ModelConfig
    worker_model: ModelConfig
    planner_model: ModelConfig | None = None
    max_rounds: int = 20
    mentor_system: str = (
        "You are Mentor, an AI project manager with full visibility of the project. "
        "You observe Worker's progress and inject corrections when Worker goes off-track. "
        "Be concise and surgical in corrections."
    )
    worker_system: str = (
        "You are Worker, a specialist AI. You only see files in your designated subdirectories. "
        "Before each response you may receive a [MENTOR CORRECTION] message — treat it as a high-priority directive. "
        "Use the available tools to read/write code. Be focused and precise."
    )
    tool_schemas: list[dict] = field(default_factory=list)
