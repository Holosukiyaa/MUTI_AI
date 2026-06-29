from core.tools.filesystem import make_file_handlers

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


def make_tools(allowed_roots: list[str]) -> tuple[list[dict], dict]:
    handlers = make_file_handlers(allowed_roots)
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
