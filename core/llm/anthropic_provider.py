import anthropic
from core.config import ModelConfig


async def _anthropic_chat(cfg: ModelConfig, messages: list[dict], tools: list[dict] | None) -> dict:
    client = anthropic.AsyncAnthropic(api_key=cfg.api_key)
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    filtered = [m for m in messages if m["role"] != "system"]
    kwargs = dict(model=cfg.model, messages=filtered, max_tokens=cfg.max_tokens)
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = [
            {"name": t["function"]["name"], "description": t["function"].get("description", ""),
             "input_schema": t["function"]["parameters"]}
            for t in tools
        ]
    resp = await client.messages.create(**kwargs)
    result = {"role": "assistant", "content": ""}
    tool_calls = []
    for block in resp.content:
        if block.type == "text":
            result["content"] += block.text
        elif block.type == "tool_use":
            tool_calls.append({"id": block.id, "name": block.name, "arguments": block.input})
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result
