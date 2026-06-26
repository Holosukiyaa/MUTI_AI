from typing import Callable
from openai import AsyncOpenAI
from core.config import ModelConfig


async def _openai_chat(cfg: ModelConfig, messages: list[dict], tools: list[dict] | None, on_token: Callable | None) -> dict:
    client = AsyncOpenAI(api_key=cfg.api_key, base_url=cfg.base_url)
    kwargs = dict(model=cfg.model, messages=messages, temperature=cfg.temperature, max_tokens=cfg.max_tokens)
    if tools:
        kwargs["tools"] = tools
        kwargs["tool_choice"] = "auto"

    if on_token:
        kwargs["stream"] = True
        stream = await client.chat.completions.create(**kwargs)
        full_content = ""
        tool_calls_acc: dict[int, dict] = {}
        announced: set[int] = set()
        async for chunk in stream:
            if not chunk.choices:
                continue
            delta = chunk.choices[0].delta
            if delta.content:
                full_content += delta.content
                on_token(delta.content)
            if delta.tool_calls:
                for tc in delta.tool_calls:
                    idx = tc.index
                    if idx not in tool_calls_acc:
                        tool_calls_acc[idx] = {"id": "", "type": "function", "function": {"name": "", "arguments": ""}}
                    if tc.id:
                        tool_calls_acc[idx]["id"] = tc.id
                    if tc.function and tc.function.name:
                        tool_calls_acc[idx]["function"]["name"] += tc.function.name
                    if tc.function and tc.function.arguments:
                        tool_calls_acc[idx]["function"]["arguments"] += tc.function.arguments
                    if idx not in announced and tool_calls_acc[idx]["function"]["name"]:
                        on_token(f"\n[正在调用工具: {tool_calls_acc[idx]['function']['name']}...]")
                        announced.add(idx)
        result = {"role": "assistant", "content": full_content}
        if tool_calls_acc:
            result["tool_calls"] = [tool_calls_acc[i] for i in sorted(tool_calls_acc)]
        return result

    resp = await client.chat.completions.create(**kwargs)
    msg = resp.choices[0].message
    result = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        result["tool_calls"] = [
            {"id": tc.id, "type": "function", "function": {"name": tc.function.name, "arguments": tc.function.arguments}}
            for tc in msg.tool_calls
        ]
    return result
