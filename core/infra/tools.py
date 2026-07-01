"""
core/infra/tools.py — 文件系统工具

提供沙箱化的文件读写工具供 Agent 使用。
_resolve_safe() 确保 Agent 只能访问被允许的目录。
"""
from pathlib import Path


# ── 路径安全校验 ─────────────────────────────────────────────────

def _resolve_safe(path: str, allowed_roots: list[str]) -> Path:
    roots = [Path(r).resolve() for r in allowed_roots]
    candidates = [Path(path).resolve()]
    if not Path(path).is_absolute():
        candidates += [(r / path).resolve() for r in roots]
    for candidate in candidates:
        for root in roots:
            if candidate.is_relative_to(root):
                return candidate
    raise PermissionError(f"Path '{path}' is outside allowed directories: {allowed_roots}")


# ── 文件系统处理器 ────────────────────────────────────────────────

def _make_file_handlers(allowed_roots: list[str]) -> dict:
    def read_file(path: str) -> str:
        p = _resolve_safe(path, allowed_roots)
        return p.read_text(encoding="utf-8")

    def write_file(path: str, content: str) -> str:
        p = _resolve_safe(path, allowed_roots)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written {len(content)} chars to {p}"

    def append_file(path: str, content: str) -> str:
        p = _resolve_safe(path, allowed_roots)
        p.parent.mkdir(parents=True, exist_ok=True)
        with p.open("a", encoding="utf-8") as f:
            f.write(content)
        return f"Appended {len(content)} chars to {p}"

    def list_dir(path: str) -> str:
        p = _resolve_safe(path, allowed_roots)
        entries = sorted(p.iterdir(), key=lambda x: (x.is_file(), x.name))
        return "\n".join(("[dir] " if e.is_dir() else "[file] ") + e.name for e in entries)

    return {"read_file": read_file, "write_file": write_file, "append_file": append_file, "list_dir": list_dir}


# ── 工具 Schema ──────────────────────────────────────────────────

_TOOL_SCHEMAS = [
    {
        "type": "function",
        "function": {
            "name": "read_file",
            "description": "Read file contents",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "write_file",
            "description": "Write content to a file (creates directories if needed)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "append_file",
            "description": "Append content to an existing file (use for writing large files in chunks)",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string"},
                    "content": {"type": "string"},
                },
                "required": ["path", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "list_dir",
            "description": "List directory contents",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
            },
        },
    },
]


# ── 公开入口 ─────────────────────────────────────────────────────

def make_tools(allowed_roots: list[str]) -> tuple[list[dict], dict]:
    handlers = _make_file_handlers(allowed_roots)
    handlers["_allowed_roots"] = allowed_roots
    return list(_TOOL_SCHEMAS), handlers


def execute_tool(name: str, arguments: dict, handlers: dict) -> str:
    if name not in handlers:
        return f"Unknown tool: {name}"
    try:
        return handlers[name](**arguments)
    except PermissionError as e:
        return f"[BLOCKED] {e}"
    except Exception as e:
        return f"[ERROR] {e}"
