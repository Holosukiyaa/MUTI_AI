import os
import json
import sys
import shutil
import msvcrt
from rich.console import Console
from rich.rule import Rule

console = Console()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SQUADS_DIR = os.path.join(ROOT, "squads")


def _read_key():
    ch = msvcrt.getwch()
    if ch in ('\x00', '\xe0'):
        ch2 = msvcrt.getwch()
        if ch2 == 'H': return 'up'
        if ch2 == 'P': return 'down'
        return None
    if ch in ('\r', '\n'):
        return 'enter'
    return ch


def _menu(title: str, items: list[str]) -> int:
    sel = 0
    while True:
        os.system('cls')
        console.print()
        console.print(Rule(f"[bold cyan]{title}[/bold cyan]", style="cyan"))
        console.print()
        for i, label in enumerate(items):
            if i == sel:
                console.print(f"  [bold red]  {i+1}.  {label}[/bold red]")
            else:
                console.print(f"  [dim]  {i+1}.  {label}[/dim]")
        console.print()
        console.print("[dim]  ↑ ↓ 移动   Enter 确认[/dim]")
        key = _read_key()
        if key == 'up':
            sel = (sel - 1) % len(items)
        elif key == 'down':
            sel = (sel + 1) % len(items)
        elif key == 'enter':
            return sel


def _list_squads() -> list[dict]:
    if not os.path.exists(SQUADS_DIR):
        return []
    result = []
    for name in sorted(os.listdir(SQUADS_DIR)):
        cfg_path = os.path.join(SQUADS_DIR, name, "config.json")
        if os.path.isfile(cfg_path):
            try:
                with open(cfg_path, encoding="utf-8") as f:
                    d = json.load(f)
                    d["_name"] = name
                    d["_dir"] = os.path.join(SQUADS_DIR, name)
                    result.append(d)
            except Exception:
                pass
    return result


def _create_squad():
    os.system('cls')
    console.print()
    console.print(Rule("[bold cyan]新建 Squad[/bold cyan]", style="cyan"))
    console.print()
    console.print("  名称（英文/拼音，用作目录名）：", end="", highlight=False)
    name = sys.stdin.readline().strip()
    if not name:
        return
    console.print("  职责描述（一句话）：", end="", highlight=False)
    desc = sys.stdin.readline().strip()

    squad_dir = os.path.join(SQUADS_DIR, name)
    mentor_dir = os.path.join(squad_dir, "mentor")
    worker_dir = os.path.join(squad_dir, "worker")
    os.makedirs(mentor_dir, exist_ok=True)
    os.makedirs(worker_dir, exist_ok=True)

    with open(os.path.join(squad_dir, "config.json"), "w", encoding="utf-8") as f:
        json.dump({"name": name, "description": desc}, f, ensure_ascii=False, indent=2)

    with open(os.path.join(mentor_dir, "blueprint.md"), "w", encoding="utf-8") as f:
        f.write(f"# {name}\n\n{desc}\n\n## Mentor 职责\n\n监督 Worker 执行任务，确保符合蓝图设计。\n")

    console.print(f"\n  [green]✓ 已创建 Squad：{name}[/green]  按任意键继续...")
    msvcrt.getwch()


def _delete_squad(squad: dict):
    name = squad["_name"]
    action = _menu(f"确认删除 {name}？", ["取消", "确认删除（不可恢复）"])
    if action == 1:
        shutil.rmtree(squad["_dir"], ignore_errors=True)
        os.system('cls')
        console.print(f"\n  [green]✓ 已删除 {name}[/green]  按任意键继续...")
        msvcrt.getwch()


def run_squad_ui() -> dict | None:
    """返回选中的 squad dict，或 None（返回主菜单）。"""
    while True:
        squads = _list_squads()
        labels = [f"{p['_name']}  —  {p.get('description', '')}" for p in squads]
        labels += ["＋  新建 Squad", "← 返回主菜单"]

        sel = _menu("Squad 管理", labels)

        if sel == len(labels) - 1:
            return None
        if sel == len(labels) - 2:
            _create_squad()
            continue

        squad = squads[sel]
        action = _menu(f"Squad · {squad['_name']}", ["启动任务会话", "删除", "← 返回"])
        if action == 0:
            return squad
        elif action == 1:
            _delete_squad(squad)
