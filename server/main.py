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

PLANNERS_DIR = os.path.join(ROOT, ".data", "planners")
SQUADS_DIR = os.path.join(ROOT, ".data", "squads")

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

    # 扫描磁盘，恢复已有 Squad 列表
    _registry().scan()


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
    if "401" in msg or "Authentication" in msg or "invalid" in msg.lower() and "key" in msg.lower():
        return "API Key 无效，请在设置中更新 DEEPSEEK_API_KEY"
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
    from core.config import ModelConfig
    return ModelConfig(
        provider="openai",
        model="deepseek-chat",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


# ── Squad Registry 单例 ──────────────────────────────────────
_squad_registry = None


def _registry():
    global _squad_registry
    if _squad_registry is None:
        from core.squad.registry import SquadRegistry
        _squad_registry = SquadRegistry(SQUADS_DIR)
    return _squad_registry


# ── Planner REST ───────────────────────────────────────────────

def _list_planners():
    if not os.path.exists(PLANNERS_DIR):
        return []
    result = []
    for name in sorted(os.listdir(PLANNERS_DIR)):
        meta = os.path.join(PLANNERS_DIR, name, "meta.json")
        if os.path.isfile(meta):
            try:
                with open(meta, encoding="utf-8") as f:
                    d = json.load(f)
                    d["id"] = name
                    result.append(d)
            except Exception:
                pass
    return result


@app.get("/api/planners")
def get_planners():
    return _list_planners()


class PlannerCreate(BaseModel):
    name: str
    description: str = ""
    icon: str = ""


@app.post("/api/planners")
def create_planner(body: PlannerCreate):
    p_dir = os.path.join(PLANNERS_DIR, body.name)
    os.makedirs(p_dir, exist_ok=True)
    with open(os.path.join(p_dir, "meta.json"), "w", encoding="utf-8") as f:
        json.dump(
            {"name": body.name, "description": body.description, "icon": body.icon},
            f, ensure_ascii=False, indent=2,
        )
    return {"id": body.name}


@app.delete("/api/planners/{name}")
def delete_planner(name: str):
    p_dir = os.path.join(PLANNERS_DIR, name)
    if not os.path.exists(p_dir):
        raise HTTPException(404)
    shutil.rmtree(p_dir, ignore_errors=True)
    return {"ok": True}


@app.get("/api/planners/{name}/history")
def get_history(name: str):
    h = os.path.join(PLANNERS_DIR, name, "history.json")
    if not os.path.exists(h):
        return []
    with open(h, encoding="utf-8") as f:
        msgs = json.load(f)
    return [m for m in msgs if m.get("role") in ("user", "assistant") and m.get("content")]


class ChatMsg(BaseModel):
    message: str


@app.post("/api/planners/{name}/chat/stream")
async def planner_chat_stream(name: str, body: ChatMsg):
    p_dir = os.path.join(PLANNERS_DIR, name)
    if not os.path.exists(p_dir):
        raise HTTPException(404)

    async def generate():
        from core.planner import PlannerAgent
        queue: asyncio.Queue = asyncio.Queue()
        loop = asyncio.get_event_loop()

        def on_token(t: str):
            loop.call_soon_threadsafe(queue.put_nowait, t)

        planner = PlannerAgent(
            model=_make_model(),
            history_path=os.path.join(p_dir, "history.json"),
            name=name,
        )

        chat_task = asyncio.create_task(planner.chat(body.message, on_token=on_token))

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

        log_dir = os.path.join(PLANNERS_DIR, name, "logs")
        squads_launched = []

        for tc in planner.last_tool_calls:
            fn = tc.get("function", {})
            if fn.get("name") != "assign_to_squad":
                continue
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                continue

            pname = args.get("squad_name", "squad")
            blueprint = args.get("blueprint", "")
            task = args.get("task", "")

            # 通过 Registry 创建 Squad（含清除旧历史）
            squad = _registry().create(
                name=pname,
                task=task,
                blueprint=blueprint,
                log_dir=log_dir,
            )
            squads_launched.append({"squad": pname, "task": task})

            # 异步启动
            await _registry().start(pname, _make_model(), push_event)

        planner.last_tool_calls = []
        yield f"data: {json.dumps({'done': True, 'squads': squads_launched})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Squad REST ───────────────────────────────────────────────

@app.get("/api/squads")
def list_squads():
    """列出所有 Squad（含状态），用于刷新页面后恢复列表。"""
    return [p.to_dict() for p in _registry().all()]


@app.get("/api/squads/{name}")
def get_squad(name: str):
    p = _registry().get(name)
    if not p:
        raise HTTPException(404)
    return p.to_dict()


@app.delete("/api/squads/{name}")
def delete_squad(name: str):
    ok = _registry().delete(name)
    if not ok:
        raise HTTPException(404)
    return {"ok": True}


@app.post("/api/squads/{name}/stop")
def stop_squad(name: str):
    """停止正在运行的 Squad。"""
    p = _registry().get(name)
    if not p:
        raise HTTPException(404)
    p.stop()
    return {"ok": True}


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


@app.get("/api/planners/{name}/open")
def open_planner_folder(name: str):
    import subprocess
    p = os.path.normpath(os.path.join(PLANNERS_DIR, name))
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}


@app.get("/api/squads/{name}/open")
def open_squad_folder(name: str):
    import subprocess
    reg = _registry()
    squad = reg.get(name)
    if squad:
        p = os.path.normpath(squad._dir)
    else:
        p = os.path.normpath(os.path.join(SQUADS_DIR, name))
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}


# ── Settings ───────────────────────────────────────────────────

class ApiKeyBody(BaseModel):
    api_key: str


@app.post("/api/settings/apikey")
def set_apikey(body: ApiKeyBody):
    key = body.api_key.strip()
    if not key.startswith("sk-"):
        key = f"sk-{key}"
    os.environ["DEEPSEEK_API_KEY"] = key
    base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
    with open(os.path.join(ROOT, ".env"), "w", encoding="utf-8") as f:
        f.write(f"DEEPSEEK_API_KEY={key}\n")
        f.write(f"DEEPSEEK_BASE_URL={base_url}\n")
    return {"ok": True}


@app.get("/api/settings")
def get_settings():
    key = os.environ.get("DEEPSEEK_API_KEY", "")
    return {
        "has_key": bool(key),
        "key_preview": f"sk-...{key[-4:]}" if key else "",
        "planners_dir": PLANNERS_DIR,
        "squads_dir": SQUADS_DIR,
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
