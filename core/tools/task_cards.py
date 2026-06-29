"""
任务卡片与留档管理 — Markdown 格式
"""
import os
import uuid
from pathlib import Path
from datetime import datetime, timezone


_TASKS_ROOT: Path | None = None


def init_tasks_dir(root: str) -> Path:
    global _TASKS_ROOT
    if _TASKS_ROOT is None:
        _TASKS_ROOT = Path(root) / "tasks"
        (_TASKS_ROOT / "pending").mkdir(parents=True, exist_ok=True)
        (_TASKS_ROOT / "archive").mkdir(parents=True, exist_ok=True)
        # README 说明
        readme = _TASKS_ROOT / "README.md"
        if not readme.exists():
            readme.write_text(
                "# 任务留档目录\n\n"
                "- `pending/` — 等待执行的任务卡片\n"
                "- `archive/` — 已完成的任务留档\n"
                "  \n每个任务是一个 Markdown 文件，包含任务描述、验收标准和交付记录。\n",
                encoding="utf-8",
            )
    return _TASKS_ROOT


def _next_id(pending_dir: Path) -> int:
    ids = []
    for f in pending_dir.glob("*.md"):
        try:
            first_line = f.read_text(encoding="utf-8").splitlines()[0]
            if first_line.startswith("---"):
                for line in f.read_text(encoding="utf-8").splitlines()[1:]:
                    if line.startswith("id:"):
                        ids.append(int(line.split(":")[1].strip()))
                        break
        except Exception:
            pass
    return max(ids, default=0) + 1


def create_task(title: str, description: str) -> dict:
    """创建任务卡片（Markdown 文件），返回卡片元数据。"""
    root = init_tasks_dir(os.getcwd())
    pending = root / "pending"
    task_id = _next_id(pending)
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    content = f"""---
id: {task_id}
title: {title}
status: pending
created_at: {now}
---

# 任务 #{task_id:03d}: {title}

## 任务描述

{description}

## 详细需求

<!-- Worker 在此处列出具体的功能点 -->

## 验收标准

<!-- Butler 在此处填写验收标准 -->

- [ ] 核心功能实现
- [ ] 代码可正常运行

## 技术约束

<!-- 如有技术约束，在此注明 -->

- 语言：Python / HTML+CSS+JavaScript
- 无外部依赖或特定框架要求

---
*创建时间: {now}*
"""
    path = pending / f"{task_id:03d}_{uuid.uuid4().hex[:8]}.md"
    path.write_text(content, encoding="utf-8")
    return {"id": task_id, "title": title, "description": description, "path": str(path)}


def list_pending_tasks() -> list[dict]:
    root = init_tasks_dir(os.getcwd())
    tasks = []
    for f in sorted((root / "pending").glob("*.md")):
        try:
            tasks.append(_parse_frontmatter(f))
        except Exception:
            pass
    return tasks


def list_archive_tasks() -> list[dict]:
    root = init_tasks_dir(os.getcwd())
    tasks = []
    for f in sorted((root / "archive").glob("*.md")):
        try:
            tasks.append(_parse_frontmatter(f))
        except Exception:
            pass
    return tasks


def get_task(task_id: int) -> dict | None:
    root = init_tasks_dir(os.getcwd())
    for folder in ("pending", "archive"):
        for f in (root / folder).glob("*.md"):
            try:
                data = _parse_frontmatter(f)
                if data.get("id") == task_id:
                    data["path"] = str(f)
                    data["content"] = f.read_text(encoding="utf-8")
                    return data
            except Exception:
                pass
    return None


def update_task_status(task_id: int, status: str) -> dict | None:
    root = init_tasks_dir(os.getcwd())
    for folder in ("pending", "archive"):
        for f in (root / folder).glob("*.md"):
            try:
                text = f.read_text(encoding="utf-8")
                if f"id: {task_id}" in text.splitlines()[1] if text.startswith("---") else False:
                    lines = text.splitlines()
                    new_lines = []
                    for line in lines:
                        if line.startswith("status:"):
                            new_lines.append(f"status: {status}")
                        elif line.startswith("completed_at:") and status == "done":
                            new_lines.append(f"completed_at: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
                        else:
                            new_lines.append(line)
                    f.write_text("\n".join(new_lines), encoding="utf-8")
                    return _parse_frontmatter(f)
            except Exception:
                pass
    return None


def archive_task(task_id: int, result_summary: str = "") -> dict | None:
    """
    归档任务：从 pending 移到 archive，生成完成留档 Markdown。
    result_summary: Butler/Worker 的完成情况描述
    """
    root = init_tasks_dir(os.getcwd())
    pending = root / "pending"
    archive = root / "archive"

    for f in pending.glob("*.md"):
        try:
            text = f.read_text(encoding="utf-8")
            lines = text.splitlines()
            if not lines or not lines[0].startswith("---"):
                continue
            # Extract id from frontmatter
            fm_lines = []
            for line in lines[1:]:
                if line.startswith("---"):
                    break
                fm_lines.append(line)
            fm = dict(line.split(":", 1) for line in fm_lines if ":" in line)
            if int(fm.get("id", -1)) != task_id:
                continue

            # Build archive document
            title = fm.get("title", "未命名任务")
            created_at = fm.get("created_at", "")
            completed_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            # Extract original task sections
            body = "\n".join(lines)

            archive_content = f"""---
id: {task_id}
title: {title}
status: done
created_at: {created_at}
completed_at: {completed_at}
---

# 任务 #{task_id:03d}: {title}

> **状态:** ✅ 已完成
> **创建:** {created_at}
> **完成:** {completed_at}

---

{body.split('---', 2)[2].strip() if '---' in body else body}

---

## 交付成果

{result_summary if result_summary else 'Worker 已完成代码编写，通过 Butler 审查。'}

## 完成情况

- [x] 核心功能实现
- [x] Butler 审查通过
- [x] Worker 调用 finish_task

## 后续备注

<!-- 如需修改或有问题，在此注明 -->

- 直接修改本文件添加备注
- 如需返工，将本文件移回 pending/ 并更新 status

---
*归档时间: {completed_at}*
"""
            dest = archive / f.name
            dest.write_text(archive_content, encoding="utf-8")
            f.unlink()
            return _parse_frontmatter(dest)
        except Exception:
            pass
    return None


def _parse_frontmatter(path: Path) -> dict:
    """解析 Markdown 文件顶部的 frontmatter。"""
    text = path.read_text(encoding="utf-8")
    data = {}
    if text.startswith("---"):
        end = text.index("---", 3)
        fm = text[3:end].strip()
        for line in fm.splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                data[k.strip()] = v.strip()
    data.setdefault("title", path.stem)
    return data


def count_pending() -> int:
    return len(list_pending_tasks())


def count_archive() -> int:
    return len(list_archive_tasks())
