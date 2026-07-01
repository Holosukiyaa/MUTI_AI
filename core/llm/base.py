from typing import Callable
from core.config import ModelConfig
from core.llm.openai_provider import _openai_chat
from core.llm.anthropic_provider import _anthropic_chat


async def chat(
    cfg: ModelConfig,
    messages: list[dict],
    tools: list[dict] | None = None,
    on_token: Callable[[str], None] | None = None,
    on_usage: Callable[[int, int], None] | None = None,
) -> dict:
    if cfg.provider == "openai":
        return await _openai_chat(cfg, messages, tools, on_token, on_usage)
    # "anthropic" 和 "claude" 都走 anthropic provider
    # claude provider 会使用用户填写的 base_url（SDK 自动补 /v1/messages）
    return await _anthropic_chat(cfg, messages, tools, on_token, on_usage)
