from typing import Callable
from core.config import ModelConfig
from core.llm.openai_provider import _openai_chat
from core.llm.anthropic_provider import _anthropic_chat


async def chat(
    cfg: ModelConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    on_token: Callable[[str], None] | None = None,
) -> dict:
    if cfg.provider == "openai":
        return await _openai_chat(cfg, messages, tools, on_token)
    return await _anthropic_chat(cfg, messages, tools)
