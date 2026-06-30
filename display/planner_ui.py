import asyncio
import os
import sys
import json
import shutil
import msvcrt
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule

SQUADS_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "squads")

console = Console()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANNERS_DIR = os.path.join(ROOT, ".data", "planners")


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
        console.print(Rule(f"[bold magenta]{title}[/bold magenta]", style="magenta"))
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


def _list_planners() -> list[dict]:
    if not os.path.exists(PLANNERS_DIR):
        return []
    result = []
    for name in sorted(os.listdir(PLANNERS_DIR)):
        meta_path = os.path.join(PLANNERS_DIR, name, "meta.json")
        if os.path.isfile(meta_path):
            try:
                with open(meta_path, encoding="utf-8") as f:
                    d = json.load(f)
                    d["_name"] = name
                    d["_dir"] = os.path.join(PLANNERS_DIR, name)
                    d["_history"] = os.path.join(PLANNERS_DIR, name, "history.json")
                    result.append(d)
            except Exception:
                pass
    return result


def select_planner(model_factory) -> object | None:
    """方向键选择或新建 Planner，返回 PlannerAgent 或 None（返回主菜单）。"""
    from core.planner import PlannerAgent

    while True:
        planners = _list_planners()
        labels = [f"{p['_name']}  —  {p.get('description', '')}" for p in planners]
        labels += ["＋  新建 Planner", "← 返回主菜单"]

        sel = _menu("选择 Planner", labels)

        if sel == len(labels) - 1:
            return None

        if sel == len(labels) - 2:
            os.system('cls')
            console.print()
            console.print(Rule("[bold magenta]新建 Planner[/bold magenta]", style="magenta"))
            console.print()
            console.print("  名称（唯一标识，英文/拼音）：", end="", highlight=False)
            name = sys.stdin.readline().strip()
            if not name:
                continue
            console.print("  职责描述（一句话）：", end="", highlight=False)
            desc = sys.stdin.readline().strip()
            p_dir = os.path.join(PLANNERS_DIR, name)
            os.makedirs(p_dir, exist_ok=True)
            with open(os.path.join(p_dir, "meta.json"), "w", encoding="utf-8") as f:
                json.dump({"name": name, "description": desc}, f, ensure_ascii=False, indent=2)
            console.print(f"\n  [green]✓ 已创建[/green]  按任意键继续...")
            msvcrt.getwch()
            continue

        p = planners[sel]
        action = _menu(f"Planner · {p['_name']}", ["进入对话", "删除", "← 返回"])
        if action == 0:
            return PlannerAgent(model=model_factory(), history_path=p["_history"], name=p["_name"])
        elif action == 1:
            confirm = _menu(f"确认删除 {p['_name']}？", ["取消", "确认删除（不可恢复）"])
            if confirm == 1:
                shutil.rmtree(p["_dir"], ignore_errors=True)
                console.print(f"\n  [green]✓ 已删除 {p['_name']}[/green]  按任意键继续...")
                msvcrt.getwch()
            continue


def _replay_history(history: list[dict]):
    if not history:
        console.print("[dim]  （暂无历史记录）[/dim]\n")
        return
    for m in history:
        role = m.get("role", "")
        content = m.get("content") or ""
        if not content:
            continue
        if role == "user":
            console.print(f"\n[bold yellow]  你[/bold yellow]  {content}")
        elif role == "assistant":
            console.print(f"\n[bold magenta]  Planner[/bold magenta]  {content}")


async def run_planner_ui(planner, model_factory):
    os.system('cls')
    console.print()
    console.print(Rule(f"[bold magenta]Planner · {planner.name}[/bold magenta]", style="magenta"))
    console.print("[dim]  与 Planner 对话，Planner 会自动创建 Squad 并启动 Mentor+Worker 执行任务[/dim]")
    console.print("[dim]  /clear 清空记录   /back 返回[/dim]\n")

    _replay_history(planner.history())

    loop = asyncio.get_event_loop()
    while True:
        console.print("\n[bold yellow]你[/bold yellow] > ", end="", highlight=False)
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except (EOFError, KeyboardInterrupt):
            break
        text = line.strip()
        if not text:
            continue
        if text == "/back":
            break
        if text == "/clear":
            planner.clear()
            os.system('cls')
            console.print()
            console.print(Rule(f"[bold magenta]Planner · {planner.name}[/bold magenta]", style="magenta"))
            console.print("[dim]  记录已清空。/back 返回[/dim]\n")
            continue

        console.print("\n[bold magenta]Planner[/bold magenta] > ", end="", highlight=False)

        def on_token(tok):
            console.print(tok, end="", highlight=False)

        await planner.chat(text, on_token=on_token)
        console.print()

        for tc in planner.last_tool_calls:
            fn = tc.get("function", {})
            if fn.get("name") != "assign_to_squad":
                continue
            try:
                args = json.loads(fn.get("arguments", "{}"))
            except Exception:
                continue

            name = args.get("squad_name", "squad")
            blueprint = args.get("blueprint", "")
            task = args.get("task", "")

            squad_dir = os.path.join(SQUADS_DIR, name)
            mentor_dir = os.path.join(squad_dir, "mentor")
            worker_dir = os.path.join(squad_dir, "worker")
            os.makedirs(mentor_dir, exist_ok=True)
            os.makedirs(worker_dir, exist_ok=True)
            with open(os.path.join(squad_dir, "config.json"), "w", encoding="utf-8") as f:
                json.dump({"name": name, "description": task[:60]}, f, ensure_ascii=False, indent=2)
            with open(os.path.join(mentor_dir, "blueprint.md"), "w", encoding="utf-8") as f:
                f.write(blueprint)

            squad = {"_name": name, "_dir": squad_dir}

            console.print()
            console.print(Panel(
                f"[cyan]Squad · {name}[/cyan] 已创建\n[dim]{task}[/dim]",
                border_style="cyan", title="[bold]启动 Squad[/bold]"
            ))

            from core.squad.session import run_squad_session
            await run_squad_session(squad, model_factory(), task)

            planner.confirm_tool_result(tc.get("id", ""), f"Squad '{name}' 已完成任务执行。")
            console.print(f"\n[dim]Squad · {name} 已结束，返回 Planner 对话...[/dim]")

        planner.last_tool_calls = []
