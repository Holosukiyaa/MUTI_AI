import os
import sys
import json
import asyncio
import shutil
from typing import Optional

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

# ── Group 数据目录结构 ─────────────────────────────────────────
# .data/groups/{group_id}/directors/  ← director 历史
# .data/groups/{group_id}/squads/     ← squad 数据
# .data/groups/{group_id}/blueprints/ ← 蓝图文档
# .data/groups/{group_id}/meta.json   ← 组名/描述
GROUPS_DIR = os.path.join(ROOT, ".data", "groups")

# ── WebSocket 广播 ─────────────────────────────────────────────
_ws_clients: list[WebSocket] = []
_event_queue: asyncio.Queue | None = None


async def broadcast(event: dict):
    dead = []
    for ws in list(_ws_clients):
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


def push_event(event: dict):
    if _event_queue is None:
        return
    try:
        _event_queue.put_nowait(event)
    except Exception:
        pass


@app.on_event("startup")
async def _startup():
    global _event_queue
    _event_queue = asyncio.Queue()

    async def _worker():
        while True:
            event = await _event_queue.get()
            await broadcast(event)

    asyncio.create_task(_worker())

    # 将 push_event 注入到 display 层，解除硬编码依赖
    import display
    display.register_push_handler(push_event)

    # 确保 default 组存在，并迁移旧数据
    _migrate_legacy_data()
    # 扫描所有 group 的 squads，恢复已有 Squad 列表
    for gid in _list_group_ids():
        _registry(gid).scan()


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ── 工具函数 ───────────────────────────────────────────────────

def _load_env():
    env_path = os.path.join(ROOT, ".env")
    if os.path.exists(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    k, v = line.split("=", 1)
                    os.environ.setdefault(k.strip(), v.strip())
    os.environ.setdefault("DEEPSEEK_BASE_URL", "https://api.deepseek.com")


_load_env()


def _classify_llm_error(e: Exception) -> str:
    """将 LLM 异常转换为用户可读的错误信息。"""
    msg = str(e)
    if "401" in msg or "Authentication" in msg or ("invalid" in msg.lower() and "key" in msg.lower()):
        return "API Key 无效，请在设置中更新"
    if "429" in msg or "rate limit" in msg.lower() or "quota" in msg.lower():
        return "请求频率超限（Rate Limit），请稍后重试"
    if "timeout" in msg.lower() or "timed out" in msg.lower():
        return "请求超时，请检查网络连接或稍后重试"
    if "connection" in msg.lower() or "ECONNREFUSED" in msg:
        return "无法连接到 AI 服务，请检查网络或 BASE_URL 配置"
    if "insufficient_quota" in msg or "402" in msg:
        return "账户余额不足，请充值后重试"
    return f"LLM 请求失败：{msg[:200]}"


def _make_model():
    """根据 .env 中的 PROVIDER 配置构建 ModelConfig。"""
    from core.config import ModelConfig
    provider = os.environ.get("AI_PROVIDER", "openai")
    if provider == "claude":
        return ModelConfig(
            provider="claude",
            model=os.environ.get("CLAUDE_MODEL", "claude-opus-4-5"),
            api_key=os.environ.get("CLAUDE_API_KEY", ""),
            base_url=os.environ.get("CLAUDE_BASE_URL", ""),
        )
    # 默认 openai 兼容（DeepSeek / OpenAI / 任意兼容端点）
    return ModelConfig(
        provider="openai",
        model=os.environ.get("OPENAI_MODEL", "deepseek-chat"),
        api_key=os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", "")),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", os.environ.get("OPENAI_BASE_URL", "https://api.deepseek.com")),
    )


# ── Group 工具函数 ───────────────────────────────────────────────

def _list_group_ids() -> list[str]:
    """列出所有组 ID（目录名）。"""
    if not os.path.isdir(GROUPS_DIR):
        return []
    return [d for d in os.listdir(GROUPS_DIR) if os.path.isdir(os.path.join(GROUPS_DIR, d))]


def _group_directors_dir(group_id: str) -> str:
    return os.path.join(GROUPS_DIR, group_id, "directors")


def _group_squads_dir(group_id: str) -> str:
    return os.path.join(GROUPS_DIR, group_id, "squads")


def _ensure_group(group_id: str, name: str = "", description: str = "") -> str:
    """确保组目录存在，返回组目录路径。"""
    g_dir = os.path.join(GROUPS_DIR, group_id)
    os.makedirs(os.path.join(g_dir, "directors"), exist_ok=True)
    os.makedirs(os.path.join(g_dir, "squads"), exist_ok=True)
    meta_path = os.path.join(g_dir, "meta.json")
    if not os.path.exists(meta_path):
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump({"id": group_id, "name": name or group_id, "description": description}, f, ensure_ascii=False, indent=2)
    return g_dir


def _migrate_legacy_data():
    """
    将旧版 .data/planners/ 和 .data/squads/ 迁移到 .data/groups/default/directors 和 squads。
    只在 default 组不存在且旧目录存在时执行一次。
    """
    legacy_planners = os.path.join(ROOT, ".data", "planners")
    legacy_squads = os.path.join(ROOT, ".data", "squads")
    default_dir = os.path.join(GROUPS_DIR, "default")

    has_legacy = os.path.isdir(legacy_planners) or os.path.isdir(legacy_squads)
    if not has_legacy:
        _ensure_group("default", "默认项目组", "自动创建的默认项目组")
        return

    if os.path.isdir(default_dir):
        # default 已存在，跳过迁移（防止重复）
        return

    _ensure_group("default", "默认项目组", "从旧版本自动迁移的数据")

    # 迁移 planners → directors
    if os.path.isdir(legacy_planners):
        dest = os.path.join(default_dir, "directors")
        shutil.copytree(legacy_planners, dest, dirs_exist_ok=True)

    # 迁移 squads
    if os.path.isdir(legacy_squads):
        dest = os.path.join(default_dir, "squads")
        shutil.copytree(legacy_squads, dest, dirs_exist_ok=True)


# ── Squad Registry（按 group 缓存）────────────────────────────
_squad_registries: dict[str, object] = {}


def _registry(group_id: str = "default"):
    if group_id not in _squad_registries:
        from core.squad.registry import SquadRegistry
        _squad_registries[group_id] = SquadRegistry(_group_squads_dir(group_id))
    return _squad_registries[group_id]


# ── Group REST ────────────────────────────────────────────────

class GroupCreate(BaseModel):
    id: str
    name: str = ""
    description: str = ""


@app.get("/api/groups")
def list_groups():
    """列出所有项目组。"""
    result = []
    for gid in sorted(_list_group_ids()):
        meta_path = os.path.join(GROUPS_DIR, gid, "meta.json")
        try:
            with open(meta_path, encoding="utf-8") as f:
                d = json.load(f)
        except Exception:
            d = {"id": gid, "name": gid, "description": ""}
        d["id"] = gid
        result.append(d)
    return result


@app.post("/api/groups")
def create_group(body: GroupCreate):
    _ensure_group(body.id.strip(), body.name.strip(), body.description.strip())
    return {"id": body.id}


@app.delete("/api/groups/{group_id}")
def delete_group(group_id: str):
    g_dir = os.path.join(GROUPS_DIR, group_id)
    if not os.path.isdir(g_dir):
        raise HTTPException(404)
    shutil.rmtree(g_dir, ignore_errors=True)
    _squad_registries.pop(group_id, None)
    return {"ok": True}


# ── Director REST（group 作用域）────────────────────────────────

def _list_directors(group_id: str = "default"):
    p_dir = _group_directors_dir(group_id)
    if not os.path.exists(p_dir):
        return []
    result = []
    for name in sorted(os.listdir(p_dir)):
        meta = os.path.join(p_dir, name, "meta.json")
        if os.path.isfile(meta):
            try:
                with open(meta, encoding="utf-8") as f:
                    d = json.load(f)
                    d["id"] = name
                    d["group_id"] = group_id
                    result.append(d)
            except Exception:
                pass
    return result


@app.get("/api/groups/{group_id}/directors")
def get_directors(group_id: str):
    _ensure_group(group_id)
    return _list_directors(group_id)


# 兼容旧路由（默认组）
@app.get("/api/planners")
def get_planners_compat():
    return _list_directors("default")


class DirectorCreate(BaseModel):
    name: str = ""
    description: str = ""
    icon: str = ""
    role: str = "executor"      # executor | architect | manager | custom
    custom_system: str = ""     # 仅 role=custom 时有效


def _unique_director_name(group_id: str, requested: str) -> str:
    base = "".join(ch for ch in requested.strip() if ch.isalnum() or ch in "-_") or "Director"
    existing = {d["id"] for d in _list_directors(group_id)}
    if base not in existing:
        return base
    idx = 2
    while f"{base}-{idx}" in existing:
        idx += 1
    return f"{base}-{idx}"


def _group_blueprints_dir(group_id: str) -> str:
    return os.path.join(GROUPS_DIR, group_id, "blueprints")


@app.post("/api/groups/{group_id}/directors")
def create_director(group_id: str, body: DirectorCreate):
    _ensure_group(group_id)
    director_name = _unique_director_name(group_id, body.name)
    p_dir = os.path.join(_group_directors_dir(group_id), director_name)
    os.makedirs(p_dir, exist_ok=True)
    with open(os.path.join(p_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {
                "name": director_name,
                "description": body.description,
                "icon": body.icon,
                "role": body.role,
                "custom_system": body.custom_system,
            },
            f, ensure_ascii=False, indent=2,
        )
    return {"id": director_name, "group_id": group_id}


# 兼容旧路由（默认组）
@app.post("/api/planners")
def create_planner_compat(body: DirectorCreate):
    return create_director("default", body)


@app.delete("/api/groups/{group_id}/directors/{name}")
def delete_director(group_id: str, name: str):
    p_dir = os.path.join(_group_directors_dir(group_id), name)
    if not os.path.exists(p_dir):
        raise HTTPException(404)
    shutil.rmtree(p_dir, ignore_errors=True)
    return {"ok": True}


# 兼容旧路由
@app.delete("/api/planners/{name}")
def delete_planner_compat(name: str):
    return delete_director("default", name)


@app.get("/api/groups/{group_id}/directors/{name}/history")
def get_director_history(group_id: str, name: str):
    h = os.path.join(_group_directors_dir(group_id), name, "history.json")
    if not os.path.exists(h):
        return []
    with open(h, encoding="utf-8") as f:
        msgs = json.load(f)
    return [m for m in msgs if m.get("role") in ("user", "assistant") and m.get("content")]


# 兼容旧路由
@app.get("/api/planners/{name}/history")
def get_history_compat(name: str):
    return get_director_history("default", name)


class ChatMsg(BaseModel):
    message: str


@app.post("/api/groups/{group_id}/directors/{name}/chat/stream")
async def director_chat_stream(group_id: str, name: str, body: ChatMsg):
    p_dir = os.path.join(_group_directors_dir(group_id), name)
    if not os.path.exists(p_dir):
        raise HTTPException(404)

    async def generate():
        from core.director import DirectorAgent
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_token(t: str):
            loop.call_soon_threadsafe(queue.put_nowait, t)

        # 读取 director meta（role / custom_system）
        meta_path = os.path.join(p_dir, "meta.json")
        director_meta = {}
        try:
            with open(meta_path, encoding="utf-8") as f:
                director_meta = json.load(f)
        except Exception:
            pass

        blueprints_dir = _group_blueprints_dir(group_id)

        director = DirectorAgent(
            model=_make_model(),
            history_path=os.path.join(p_dir, "history.json"),
            name=name,
            role=director_meta.get("role", "executor"),
            custom_system=director_meta.get("custom_system", ""),
            blueprints_dir=blueprints_dir,
        )

        chat_task = asyncio.create_task(director.chat(body.message, on_token=on_token))

        while not chat_task.done() or not queue.empty():
            try:
                token = await asyncio.wait_for(queue.get(), timeout=0.05)
                yield f"data: {json.dumps({'token': token})}\n\n"
            except asyncio.TimeoutError:
                continue

        try:
            await chat_task
        except Exception as e:
            err_msg = _classify_llm_error(e)
            yield f"data: {json.dumps({'error': err_msg})}\n\n"
            return

        log_dir = os.path.join(p_dir, "logs")
        squads_launched = []
        blueprints_saved = []

        for tc in director.last_tool_calls:
            fn = tc.get("function", {})
            fn_name = fn.get("name")

            if fn_name == "assign_to_squad":
                try:
                    args = json.loads(fn.get("arguments", "{}"))
                except Exception:
                    continue

                pname = args.get("squad_name", "squad")
                blueprint = args.get("blueprint", "")
                task = args.get("task", "")

                _registry(group_id).create(
                    name=pname, task=task, blueprint=blueprint, log_dir=log_dir,
                )
                squads_launched.append({"squad": pname, "task": task, "group_id": group_id})

                async def _make_accept_fn(d=director, t=task):
                    async def _accept(task_desc: str, file_list: str) -> str:
                        return await d.accept(task_desc, file_list)
                    return _accept

                async def _make_monitor_fn(d=director):
                    async def _monitor(status: dict) -> str:
                        return await d.monitor(status)
                    return _monitor

                await _registry(group_id).start(pname, _make_model(), push_event,
                                                 accept_fn=await _make_accept_fn(),
                                                 director_report_fn=await _make_monitor_fn())

            elif fn_name == "save_blueprint":
                result = director.handle_save_blueprint(tc)
                # 回传工具结果到 director 历史
                director.confirm_tool_result(tc.get("id", ""), result)
                blueprints_saved.extend(director.last_blueprint_saves)
                bp_token = "\n\n[蓝图] " + result
                yield f"data: {json.dumps({'token': bp_token})}\n\n"

        director.last_tool_calls = []
        yield f"data: {json.dumps({'done': True, 'squads': squads_launched, 'blueprints': blueprints_saved})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# 兼容旧路由（默认组）
@app.post("/api/planners/{name}/chat/stream")
async def planner_chat_stream_compat(name: str, body: ChatMsg):
    return await director_chat_stream("default", name, body)


# ── Squad REST（group 作用域）────────────────────────────────

@app.get("/api/groups/{group_id}/squads")
def list_squads(group_id: str):
    """列出指定组内所有 Squad（含状态）。"""
    return [p.to_dict() for p in _registry(group_id).all()]


# 兼容旧路由（默认组）
@app.get("/api/squads")
def list_squads_default():
    return list_squads("default")


@app.get("/api/groups/{group_id}/squads/{name}")
def get_squad(group_id: str, name: str):
    p = _registry(group_id).get(name)
    if not p:
        raise HTTPException(404)
    return p.to_dict()


@app.get("/api/groups/{group_id}/squads/{name}/log")
def get_squad_log(group_id: str, name: str):
    p = _registry(group_id).get(name)
    log_path = None
    if p:
        log_path = p._log_path
    if not log_path:
        log_path = os.path.join(_group_directors_dir(group_id), name, "logs", f"{name}.log")
    if not os.path.exists(log_path):
        return {"lines": []}
    with open(log_path, encoding="utf-8", errors="replace") as f:
        lines = [line.rstrip("\n") for line in f]
    return {"lines": lines}


@app.get("/api/squads/{name}")
def get_squad_default(name: str):
    return get_squad("default", name)


@app.delete("/api/groups/{group_id}/squads/{name}")
def delete_squad(group_id: str, name: str):
    ok = _registry(group_id).delete(name)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@app.delete("/api/squads/{name}")
def delete_squad_default(name: str):
    return delete_squad("default", name)


@app.post("/api/groups/{group_id}/squads/{name}/stop")
def stop_squad(group_id: str, name: str):
    p = _registry(group_id).get(name)
    if not p:
        raise HTTPException(404)
    p.stop()
    return {"ok": True}


@app.post("/api/squads/{name}/stop")
def stop_squad_default(name: str):
    return stop_squad("default", name)


class ContinueBody(BaseModel):
    message: str = ""


@app.post("/api/groups/{group_id}/squads/{name}/continue")
async def continue_squad(group_id: str, name: str, body: ContinueBody):
    p = _registry(group_id).get(name)
    if not p:
        raise HTTPException(404)
    await p.continue_run(_make_model(), body.message, push_event)
    push_event({"type": "session_line", "squad": name, "line": "▶ 继续请求已接收，正在重新启动 Worker…"})
    push_event({"type": "session_progress", "squad": name, "percent": p.progress, "status": "继续运行中"})
    return {"ok": True}


@app.post("/api/squads/{name}/continue")
async def continue_squad_default(name: str, body: ContinueBody):
    return await continue_squad("default", name, body)


@app.get("/api/groups/{group_id}/tree")
def get_group_tree(group_id: str):
    root = os.path.normpath(os.path.join(GROUPS_DIR, group_id))
    if not os.path.isdir(root):
        return {"name": group_id, "type": "dir", "children": []}

    def build(path: str, depth: int = 0) -> dict:
        name = os.path.basename(path) or group_id
        if os.path.isfile(path):
            return {"name": name, "type": "file", "path": os.path.relpath(path, root)}
        node = {"name": name, "type": "dir", "path": os.path.relpath(path, root), "children": []}
        if depth >= 6:
            return node
        try:
            entries = sorted(os.listdir(path), key=lambda x: (not os.path.isdir(os.path.join(path, x)), x.lower()))[:200]
        except Exception:
            entries = []
        for entry in entries:
            if entry.startswith("__pycache__"):
                continue
            node["children"].append(build(os.path.join(path, entry), depth + 1))
        return node

    return build(root)


@app.get("/api/groups/{group_id}/file")
def get_group_file(group_id: str, path: str):
    root = os.path.normpath(os.path.join(GROUPS_DIR, group_id))
    target = os.path.normpath(os.path.join(root, path))
    if not target.startswith(root) or not os.path.isfile(target):
        raise HTTPException(404)
    if os.path.getsize(target) > 512_000:
        return {"path": path, "content": "文件超过 512KB，暂不在内置查看器中打开。", "truncated": True}
    with open(target, encoding="utf-8", errors="replace") as f:
        return {"path": path, "content": f.read(), "truncated": False}


# ── 文件夹快捷操作 ─────────────────────────────────────────────

class OpenFolderBody(BaseModel):
    path: str


@app.post("/api/open-folder")
def open_folder(body: OpenFolderBody):
    import subprocess
    p = body.path
    if not p:
        return {"ok": False}
    p = os.path.normpath(p)
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}


@app.get("/api/groups/{group_id}/directors/{name}/open")
def open_director_folder(group_id: str, name: str):
    import subprocess
    p = os.path.normpath(os.path.join(_group_directors_dir(group_id), name))
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}


@app.get("/api/planners/{name}/open")
def open_planner_folder_compat(name: str):
    return open_director_folder("default", name)


@app.get("/api/groups/{group_id}/squads/{name}/open")
def open_squad_folder(group_id: str, name: str):
    import subprocess
    squad = _registry(group_id).get(name)
    if squad:
        p = os.path.normpath(squad._dir)
    else:
        p = os.path.normpath(os.path.join(_group_squads_dir(group_id), name))
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}


@app.get("/api/squads/{name}/open")
def open_squad_folder_default(name: str):
    return open_squad_folder("default", name)


@app.get("/api/groups/{group_id}/open")
def open_group_folder(group_id: str):
    import subprocess
    p = os.path.normpath(os.path.join(GROUPS_DIR, group_id))
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}


# ── Settings ───────────────────────────────────────────────────

class ProviderConfig(BaseModel):
    provider: str          # "openai" | "claude"
    api_key: str
    base_url: str = ""
    model: str = ""


@app.post("/api/settings/provider")
def set_provider(body: ProviderConfig):
    """保存 AI provider 配置到 .env。"""
    provider = body.provider.strip()
    key = body.api_key.strip()
    base_url = body.base_url.strip()
    model = body.model.strip()

    lines = []
    if provider == "claude":
        lines.append(f"AI_PROVIDER=claude\n")
        lines.append(f"CLAUDE_API_KEY={key}\n")
        if base_url:
            lines.append(f"CLAUDE_BASE_URL={base_url}\n")
        if model:
            lines.append(f"CLAUDE_MODEL={model}\n")
        os.environ["AI_PROVIDER"] = "claude"
        os.environ["CLAUDE_API_KEY"] = key
        if base_url:
            os.environ["CLAUDE_BASE_URL"] = base_url
        if model:
            os.environ["CLAUDE_MODEL"] = model
    else:
        # openai 兼容（DeepSeek 等）
        if not key.startswith("sk-"):
            key = f"sk-{key}"
        lines.append(f"AI_PROVIDER=openai\n")
        lines.append(f"DEEPSEEK_API_KEY={key}\n")
        lines.append(f"DEEPSEEK_BASE_URL={base_url or 'https://api.deepseek.com'}\n")
        if model:
            lines.append(f"OPENAI_MODEL={model}\n")
        os.environ["AI_PROVIDER"] = "openai"
        os.environ["DEEPSEEK_API_KEY"] = key
        os.environ["DEEPSEEK_BASE_URL"] = base_url or "https://api.deepseek.com"
        if model:
            os.environ["OPENAI_MODEL"] = model

    with open(os.path.join(ROOT, ".env"), "w", encoding="utf-8") as f:
        f.writelines(lines)
    return {"ok": True}


# 兼容旧接口（只传 api_key，默认 openai/DeepSeek）
class ApiKeyBody(BaseModel):
    api_key: str


@app.post("/api/settings/apikey")
def set_apikey(body: ApiKeyBody):
    return set_provider(ProviderConfig(provider="openai", api_key=body.api_key))


@app.get("/api/settings")
def get_settings():
    provider = os.environ.get("AI_PROVIDER", "openai")
    if provider == "claude":
        key = os.environ.get("CLAUDE_API_KEY", "")
        base_url = os.environ.get("CLAUDE_BASE_URL", "")
        model = os.environ.get("CLAUDE_MODEL", "claude-opus-4-5")
    else:
        key = os.environ.get("DEEPSEEK_API_KEY", os.environ.get("OPENAI_API_KEY", ""))
        base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
        model = os.environ.get("OPENAI_MODEL", "deepseek-chat")
    return {
        "provider": provider,
        "has_key": bool(key),
        "key_preview": f"...{key[-4:]}" if len(key) > 4 else ("●●●●" if key else ""),
        "base_url": base_url,
        "model": model,
        "groups_dir": GROUPS_DIR,
    }


# ── 静态资源（生产模式）────────────────────────────────────────
_dist = os.path.join(ROOT, "web", "dist")
if os.path.exists(_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(
            os.path.join(_dist, "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
