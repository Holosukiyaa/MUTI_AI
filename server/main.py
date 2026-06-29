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
PARTNERS_DIR = os.path.join(ROOT, ".data", "partners")

_ws_clients: list[WebSocket] = []
_event_queue: asyncio.Queue | None = None


async def broadcast(event: dict):
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(event)
        except Exception:
            dead.append(ws)
    for ws in dead:
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


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        _ws_clients.remove(ws)


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


async def _run_partner(pname: str, task: str, planner_name: str):
    import traceback
    try:
        from core.partner_session import run_partner_session
        partner = {"_dir": os.path.join(PARTNERS_DIR, pname), "_name": pname}
        log_dir = os.path.join(PLANNERS_DIR, planner_name, "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_path = os.path.join(log_dir, f"{pname}.log")
        await run_partner_session(partner, _make_model(), task, headless=True, log_path=log_path)
    except Exception:
        traceback.print_exc()
        push_event({"type": "session_line", "line": f"[Partner 错误] {traceback.format_exc()[-300:]}"})



def _make_model():
    from core.config import ModelConfig
    return ModelConfig(
        provider="openai", model="deepseek-chat",
        api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
        base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
    )


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


# ── Planner REST ──────────────────────────────────────────────
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
        json.dump({"name": body.name, "description": body.description, "icon": body.icon}, f, ensure_ascii=False, indent=2)
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


@app.post("/api/planners/{name}/chat")
async def planner_chat(name: str, body: ChatMsg):
    p_dir = os.path.join(PLANNERS_DIR, name)
    if not os.path.exists(p_dir):
        raise HTTPException(404)
    from core.planner import PlannerAgent
    planner = PlannerAgent(
        model=_make_model(),
        history_path=os.path.join(p_dir, "history.json"),
        name=name,
    )
    await planner.chat(body.message, on_token=None)
    reply = (planner.messages[-1].get("content") or "").strip()

    partners_launched = []
    for tc in planner.last_tool_calls:
        fn = tc.get("function", {})
        if fn.get("name") != "assign_to_partner":
            continue
        try:
            args = json.loads(fn.get("arguments", "{}"))
        except Exception:
            continue
        pname = args.get("partner_name", "partner")
        blueprint = args.get("blueprint", "")
        task = args.get("task", "")
        partner_dir = os.path.join(PARTNERS_DIR, pname)
        butler_dir = os.path.join(partner_dir, "butler")
        worker_dir = os.path.join(partner_dir, "worker")
        os.makedirs(butler_dir, exist_ok=True)
        os.makedirs(worker_dir, exist_ok=True)
        with open(os.path.join(partner_dir, "config.json"), "w", encoding="utf-8") as f:
            json.dump({"name": pname, "description": task[:60]}, f, ensure_ascii=False, indent=2)
        with open(os.path.join(butler_dir, "blueprint.md"), "w", encoding="utf-8") as f:
            f.write(blueprint)
        partners_launched.append({"partner": pname, "task": task})

    planner.last_tool_calls = []
    if not reply and partners_launched:
        reply = "已创建 " + "、".join(p["partner"] for p in partners_launched) + " 搭档，Butler × Worker 开始执行。"
    return {"reply": reply, "partners": partners_launched}


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

        await chat_task

        partners_launched = []
        for tc in planner.last_tool_calls:
            fn = tc.get("function", {})
            if fn.get("name") != "assign_to_partner":
                continue
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                continue
            pname = args.get("partner_name", "partner")
            blueprint = args.get("blueprint", "")
            task = args.get("task", "")
            partner_dir = os.path.join(PARTNERS_DIR, pname)
            os.makedirs(os.path.join(partner_dir, "butler"), exist_ok=True)
            os.makedirs(os.path.join(partner_dir, "worker"), exist_ok=True)
            with open(os.path.join(partner_dir, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"name": pname, "description": task[:60]}, f, ensure_ascii=False, indent=2)
            with open(os.path.join(partner_dir, "butler", "blueprint.md"), "w", encoding="utf-8") as f:
                f.write(blueprint)
            partners_launched.append({"partner": pname, "task": task})

        for p in partners_launched:
            asyncio.create_task(_run_partner(p["partner"], p["task"], name))

        yield f"data: {json.dumps({'done': True, 'partners': partners_launched})}\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream")


# ── Open folder ───────────────────────────────────────────────
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

@app.get("/api/partners/{name}/open")
def open_partner_folder(name: str):
    import subprocess
    p = os.path.normpath(os.path.join(PARTNERS_DIR, name))
    if os.path.exists(p):
        subprocess.Popen(["explorer", p])
    return {"ok": True}

@app.delete("/api/partners/{name}")
def delete_partner(name: str):
    p = os.path.join(PARTNERS_DIR, name)
    if not os.path.exists(p):
        raise HTTPException(404)
    shutil.rmtree(p, ignore_errors=True)
    return {"ok": True}


# ── Settings ──────────────────────────────────────────────────
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
        "partners_dir": PARTNERS_DIR,
    }


# ── Serve React build ─────────────────────────────────────────
_dist = os.path.join(ROOT, "web", "dist")
if os.path.exists(_dist):
    app.mount("/assets", StaticFiles(directory=os.path.join(_dist, "assets")), name="assets")

    @app.get("/{full_path:path}")
    def serve_spa(full_path: str):
        return FileResponse(
            os.path.join(_dist, "index.html"),
            headers={"Cache-Control": "no-cache, no-store, must-revalidate"},
        )
