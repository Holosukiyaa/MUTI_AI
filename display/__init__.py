import os
import contextvars
import datetime
from typing import Callable

_log_path_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("log_path", default=None)
_squad_name_var: contextvars.ContextVar[str | None] = contextvars.ContextVar("squad_name", default=None)
_token_buf: list[str] = []

# 事件推送回调，由外部（server/main.py 或任意前端）在启动时注入
_push_handler: Callable[[dict], None] | None = None


def register_push_handler(fn: Callable[[dict], None]) -> None:
    """注册事件推送回调。fn 接收一个 event dict，负责将其发送到前端。"""
    global _push_handler
    _push_handler = fn


def set_log_path(path: str):
    _log_path_var.set(path)


def set_squad_name(name: str):
    """设置当前 Squad 上下文，所有后续事件都会带上此名称。"""
    _squad_name_var.set(name)


def _push(event: dict):
    # 自动附加当前 Squad 名
    squad = _squad_name_var.get()
    if squad and "squad" not in event:
        event = {**event, "squad": squad}

    if _push_handler is not None:
        _push_handler(event)

    log_path = _log_path_var.get()
    if log_path and event.get("type") == "session_line":
        try:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
            ts = datetime.datetime.now().strftime("%H:%M:%S")
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"[{ts}] {event['line']}\n")
        except Exception:
            pass


def worker_header(round: int):
    _push({"type": "session_line", "line": f"━━━  Worker 工作中  ·  第 {round} 轮  ━━━"})

def worker_stream_start():
    _token_buf.clear()

def worker_token(token: str):
    _token_buf.append(token)

def worker_stream_end():
    if _token_buf:
        text = "".join(_token_buf).strip()
        _token_buf.clear()
        if text:
            _push({"type": "session_line", "line": text})

def worker_tool_call(name: str, args: dict):
    labels = {
        "read_file": "读取文件", "write_file": "写入文件",
        "append_file": "追加文件", "list_dir": "查看目录",
    }
    label = labels.get(name, name)
    arg = next(iter(args.values()), "")
    if isinstance(arg, str) and len(arg) > 80:
        arg = arg[:80] + "…"
    _push({"type": "session_line", "line": f"  ⚙ {label}  {arg}"})

def worker_tool_result(name: str, result: str):
    preview = result[:200].replace("\n", " ↵ ")
    _push({"type": "session_line", "line": f"  └ {preview}"})

def mentor_ok(round: int):
    _push({"type": "session_line", "line": f"  ✓ Mentor 审查第 {round} 轮：通过"})

def mentor_interrupt(round: int, correction: str):
    _push({"type": "session_line", "line": f"⚡ Mentor 纠正介入 · 第 {round} 轮: {correction}"})

def mentor_stream_start(round: int):
    _push({"type": "session_line", "line": f"━━━  Mentor 正在审查第 {round} 轮  ━━━"})

def mentor_token(token: str):
    pass

def mentor_stream_end():
    pass

def worker_ask_mentor(question: str):
    _push({"type": "session_line", "line": f"❓ Worker 向 Mentor 提问：{question}"})

def mentor_answer(answer: str):
    _push({"type": "session_line", "line": f"📖 Mentor 回答：{answer[:200]}"})

def session_start(task: str, worker_scope: str, mentor_scope: str, model_info: str = ""):
    _push({"type": "session_line", "line": f"🚀 Squad 启动  |  模型：{model_info}"})
    _push({"type": "session_line", "line": f"📋 任务：{task[:120]}"})

def session_end():
    _push({"type": "session_line", "line": "✓ 任务完成"})

def system_msg(msg: str):
    _push({"type": "session_line", "line": f"[系统] {msg}"})

def error_msg(who: str, err: str):
    _push({"type": "session_line", "line": f"[{who} 错误] {err}"})

def user_prompt():
    pass

def welcome():
    pass

def init_progress_bar(total_steps: int = 5, task_desc: str = "任务进度"):
    pass

def update_progress_bar(percent: float, status: str = ""):
    _push({"type": "session_progress", "percent": percent, "status": status})

def stop_progress_bar(final_status: str = "已完成"):
    _push({"type": "session_progress", "percent": 100, "status": final_status})
