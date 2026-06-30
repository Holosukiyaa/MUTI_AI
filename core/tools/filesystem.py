import os
from pathlib import Path


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


def make_file_handlers(allowed_roots: list[str]) -> dict:
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
