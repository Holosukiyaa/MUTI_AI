from typing import Callable
import json
import httpx
import anthropic
from core.config import ModelConfig


async def _anthropic_chat(
    cfg: ModelConfig,
    messages: list[dict],
    tools: list[dict] | None,
    on_token: Callable[[str], None] | None = None,
    on_usage: Callable[[int, int], None] | None = None,
) -> dict:
    api_key = cfg.api_key
    base_url = cfg.base_url.rstrip("/") if cfg.base_url else None

    if api_key.startswith("clp_"):
        # 第三方代理（clp_ token）：完全绕开 anthropic SDK，直接用 httpx 发请求
        # 原因：SDK 在底层强制设置 User-Agent，代理会据此拦截
        return await _httpx_chat(
            api_key, base_url, cfg.model, cfg.max_tokens,
            messages, tools, on_token, on_usage,
        )
    else:
        client_kwargs: dict = {"api_key": api_key}
        if base_url:
            client_kwargs["base_url"] = base_url
        client = anthropic.AsyncAnthropic(**client_kwargs)
        return await _sdk_chat(client, cfg.model, cfg.max_tokens, messages, tools, on_token, on_usage)


async def _httpx_chat(
    api_key: str,
    base_url: str | None,
    model: str,
    max_tokens: int,
    messages: list[dict],
    tools: list[dict] | None,
    on_token: Callable[[str], None] | None,
    on_usage: Callable[[int, int], None] | None,
) -> dict:
    """直接用 httpx 调用 Anthropic 格式的 API，绕开 SDK 的 User-Agent。
    有 on_token 时走流式 SSE，否则走非流式。
    """
    url = (base_url or "https://api.anthropic.com") + "/v1/messages"

    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    filtered = [m for m in messages if m["role"] != "system"]

    payload: dict = {"model": model, "max_tokens": max_tokens, "messages": filtered}
    if system:
        payload["system"] = system
    if tools:
        payload["tools"] = [
            {"name": t["function"]["name"],
             "description": t["function"].get("description", ""),
             "input_schema": t["function"]["parameters"]}
            for t in tools
        ]

    headers = {
        "Content-Type": "application/json",
        "anthropic-version": "2023-06-01",
        "Authorization": f"Bearer {api_key}",
    }

    if on_token:
        return await _httpx_stream(url, payload, headers, on_token, on_usage)
    else:
        return await _httpx_blocking(url, payload, headers, on_usage)


async def _httpx_blocking(
    url: str,
    payload: dict,
    headers: dict,
    on_usage: Callable[[int, int], None] | None,
) -> dict:
    """非流式请求。"""
    async with httpx.AsyncClient(timeout=120) as client:
        r = await client.post(url, json=payload, headers=headers)

    if r.status_code != 200:
        raise Exception(f"HTTP {r.status_code}: {r.text[:300]}")

    data = r.json()
    if on_usage and "usage" in data:
        on_usage(data["usage"].get("input_tokens", 0), data["usage"].get("output_tokens", 0))

    return _parse_response_body(data)


async def _httpx_stream(
    url: str,
    payload: dict,
    headers: dict,
    on_token: Callable[[str], None],
    on_usage: Callable[[int, int], None] | None,
) -> dict:
    """SSE 流式请求，实时调用 on_token 回调。"""
    payload = {**payload, "stream": True}
    stream_headers = {**headers, "Accept": "text/event-stream"}

    full_content = ""
    tool_calls_acc: dict[int, dict] = {}   # index → {id, name, input_str}
    announced: set[int] = set()
    input_tokens = 0
    output_tokens = 0

    async with httpx.AsyncClient(timeout=120) as client:
        async with client.stream("POST", url, json=payload, headers=stream_headers) as resp:
            if resp.status_code != 200:
                body = await resp.aread()
                raise Exception(f"HTTP {resp.status_code}: {body[:300]}")

            async for line in resp.aiter_lines():
                if not line.startswith("data:"):
                    continue
                raw = line[5:].strip()
                if not raw or raw == "[DONE]":
                    continue

                try:
                    ev = json.loads(raw)
                except Exception:
                    continue

                ev_type = ev.get("type", "")

                if ev_type == "content_block_start":
                    # 工具调用开始：记录 id 和名称
                    block = ev.get("content_block", {})
                    if block.get("type") == "tool_use":
                        idx = ev.get("index", 0)
                        tool_calls_acc[idx] = {
                            "id": block.get("id", ""),
                            "name": block.get("name", ""),
                            "input_str": "",
                        }
                        if idx not in announced:
                            on_token(f"\n[正在调用工具: {block.get('name', '')}...]\n")
                            announced.add(idx)

                elif ev_type == "content_block_delta":
                    delta = ev.get("delta", {})
                    delta_type = delta.get("type", "")

                    if delta_type == "text_delta":
                        # 普通文本增量
                        chunk = delta.get("text", "")
                        full_content += chunk
                        on_token(chunk)

                    elif delta_type == "input_json_delta":
                        # 工具参数增量：只累积，不推送给用户（原始 JSON 不应显示在聊天中）
                        idx = ev.get("index", 0)
                        partial = delta.get("partial_json", "")
                        if idx in tool_calls_acc:
                            tool_calls_acc[idx]["input_str"] += partial

                # usage
                elif ev_type == "message_delta":
                    usage = ev.get("usage", {})
                    output_tokens = usage.get("output_tokens", 0)
                elif ev_type == "message_start":
                    msg = ev.get("message", {})
                    usage = msg.get("usage", {})
                    input_tokens = usage.get("input_tokens", 0)

    if on_usage and (input_tokens or output_tokens):
        on_usage(input_tokens, output_tokens)

    result: dict = {"role": "assistant", "content": full_content}
    if tool_calls_acc:
        tool_calls = []
        for idx in sorted(tool_calls_acc):
            tc = tool_calls_acc[idx]
            try:
                parsed = json.loads(tc["input_str"]) if tc["input_str"] else {}
            except Exception:
                parsed = {}
            tool_calls.append({
                "id": tc["id"],
                "type": "function",
                "function": {
                    "name": tc["name"],
                    "arguments": json.dumps(parsed, ensure_ascii=False),
                }
            })
        result["tool_calls"] = tool_calls
    return result


def _parse_response_body(data: dict) -> dict:
    """解析非流式响应体。"""
    result: dict = {"role": "assistant", "content": ""}
    tool_calls = []
    for block in data.get("content", []):
        if block.get("type") == "text":
            result["content"] += block.get("text", "")
        elif block.get("type") == "tool_use":
            tool_calls.append({
                "id": block["id"],
                "type": "function",
                "function": {
                    "name": block["name"],
                    "arguments": json.dumps(block.get("input", {}), ensure_ascii=False),
                }
            })
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result


async def _sdk_chat(
    client: anthropic.AsyncAnthropic,
    model: str,
    max_tokens: int,
    messages: list[dict],
    tools: list[dict] | None,
    on_token: Callable[[str], None] | None,
    on_usage: Callable[[int, int], None] | None,
) -> dict:
    """标准 Anthropic SDK 调用路径；有 on_token 时走流式输出。"""
    system = next((m["content"] for m in messages if m["role"] == "system"), None)
    filtered = [m for m in messages if m["role"] != "system"]
    kwargs: dict = dict(model=model, messages=filtered, max_tokens=max_tokens)
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = [
            {"name": t["function"]["name"],
             "description": t["function"].get("description", ""),
             "input_schema": t["function"]["parameters"]}
            for t in tools
        ]

    if on_token:
        async with client.messages.stream(**kwargs) as stream:
            async for text in stream.text_stream:
                on_token(text)
            resp = await stream.get_final_message()
    else:
        resp = await client.messages.create(**kwargs)

    if on_usage and resp.usage:
        on_usage(resp.usage.input_tokens, resp.usage.output_tokens)

    result: dict = {"role": "assistant", "content": ""}
    tool_calls = []
    announced: set[str] = set()
    for block in resp.content:
        if block.type == "text":
            result["content"] += block.text
        elif block.type == "tool_use":
            if on_token and block.name not in announced:
                on_token(f"\n[正在调用工具: {block.name}...]\n")
                announced.add(block.name)
            tool_calls.append({
                "id": block.id,
                "type": "function",
                "function": {
                    "name": block.name,
                    "arguments": json.dumps(block.input, ensure_ascii=False),
                }
            })
    if tool_calls:
        result["tool_calls"] = tool_calls
    return result
