from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich import box

console = Console()

# 进度条状态
_progress_state = {
    "desc": "任务进度",
    "percent": 0.0,
    "status": "初始化...",
    "active": False,
    "last_printed": "",
}

_TOOL_NAMES = {
    "read_file":  "读取文件",
    "write_file": "写入文件",
    "list_dir":   "查看目录",
}


def worker_header(round: int):
    console.print(Rule(f"[bold cyan]Worker 工作中  ·  第 {round} 轮[/bold cyan]", style="cyan"))


def worker_stream_start():
    console.print("[cyan]●[/cyan] ", end="")


def worker_token(token: str):
    console.print(token, end="", style="white")


def worker_stream_end():
    console.print()


def worker_tool_call(name: str, args: dict):
    label = _TOOL_NAMES.get(name, name)
    main_arg = next(iter(args.values()), "")
    if isinstance(main_arg, str) and len(main_arg) > 80:
        main_arg = main_arg[:80] + "…"
    console.print(f"  [cyan]⚙[/cyan] [bold]{label}[/bold]  [dim]{main_arg}[/dim]")


def worker_tool_result(name: str, result: str):
    preview = result[:200].replace("\n", " ↵ ")
    console.print(f"  [bright_black]  └ {preview}[/bright_black]")


def butler_ok(round: int):
    console.print(f"  [green]Butler 审查第 {round} 轮：通过 ✓[/green]")


def butler_interrupt(round: int, correction: str):
    console.print()
    console.print(Panel(
        f"[bold white]{correction}[/bold white]",
        title=f"[bold red]⚡ Butler 纠正介入  ·  第 {round} 轮[/bold red]",
        border_style="red",
        box=box.HEAVY,
        padding=(0, 1),
    ))
    console.print()


def butler_stream_start(round: int):
    console.print(Rule(f"[bold magenta]Butler 正在审查第 {round} 轮[/bold magenta]", style="magenta"))
    console.print("[magenta]●[/magenta] ", end="")


def butler_token(token: str):
    console.print(token, end="", style="magenta")


def butler_stream_end():
    console.print()


def welcome():
    # 橙色大字 ASCII 艺术（Claude Code 风格）
    logo = (
        "[bold bright_red] ██████╗ ██╗   ██╗████████╗██╗     ███████╗██████╗ [/bold bright_red]\n"
        "[bold bright_red] ██╔══██╗██║   ██║╚══██╔══╝██║     ██╔════╝██╔══██╗[/bold bright_red]\n"
        "[bold bright_red] ██████╔╝██║   ██║   ██║   ██║     █████╗  ██████╔╝[/bold bright_red]\n"
        "[bold bright_red] ██╔══██╗██║   ██║   ██║   ██║     ██╔══╝  ██╔══██╗[/bold bright_red]\n"
        "[bold bright_red] ██████╔╝╚██████╔╝   ██║   ███████╗███████╗██║  ██║[/bold bright_red]\n"
        "[bold bright_red] ╚═════╝  ╚═════╝    ╚═╝   ╚══════╝╚══════╝╚═╝  ╚═╝[/bold bright_red]\n"
        "[bold bright_red]                                                     [/bold bright_red]\n"
        "[bold bright_red] ██╗    ██╗ ██████╗ ██████╗ ██╗  ██╗███████╗██████╗ [/bold bright_red]\n"
        "[bold bright_red] ██║    ██║██╔═══██╗██╔══██╗██║ ██╔╝██╔════╝██╔══██╗[/bold bright_red]\n"
        "[bold bright_red] ██║ █╗ ██║██║   ██║██████╔╝█████╔╝ █████╗  ██████╔╝[/bold bright_red]\n"
        "[bold bright_red] ██║███╗██║██║   ██║██╔══██╗██╔═██╗ ██╔══╝  ██╔══██╗[/bold bright_red]\n"
        "[bold bright_red] ╚███╔███╔╝╚██████╔╝██║  ██║██║  ██╗███████╗██║  ██║[/bold bright_red]\n"
        "[bold bright_red]  ╚══╝╚══╝  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═╝[/bold bright_red]"
    )
    console.print()
    console.print(logo)

def _load_version() -> str:
    try:
        version_file = Path(__file__).resolve().parent.parent / "VERSION"
        return version_file.read_text(encoding="utf-8").strip()
    except Exception:
        return "0.1.0"

_VERSION = _load_version()
    console.print("[dim]  Multi-Agent Collaborative Framework  v" + _VERSION + "[/dim]")
    console.print()
    console.print(Panel(
        "[cyan]Butler[/cyan]  拥有私有知识、全局视角，实时监督并纠正 Worker\n"
        "[green]Worker[/green]  专注执行任务，只能访问指定目录，可主动向 Butler 提问\n\n"
        "[dim]可用指令：stop / pause worker / pause butler / resume / status / help[/dim]",
        border_style="bright_red",
        box=box.ROUNDED,
        padding=(1, 2),
    ))
    console.print()


def _render_bar(percent: float, width: int = 30) -> str:
    filled = int(width * percent / 100)
    empty = width - filled
    return "━" * filled + "╺" + "━" * (empty - 1) if empty > 0 else "━" * width


def _format_progress() -> str:
    bar = _render_bar(_progress_state["percent"])
    return (
        f"[bold green]▶[/bold green] [cyan]{_progress_state['desc']}[/cyan] {bar} "
        f"[bold]{_progress_state['percent']:>3.0f}%[/bold] [dim]{_progress_state['status']}[/dim]"
    )


def init_progress_bar(total_steps: int = 5, task_desc: str = "任务进度"):
    global _progress_state
    _progress_state["desc"] = task_desc
    _progress_state["percent"] = 0.0
    _progress_state["status"] = "初始化..."
    _progress_state["active"] = True
    _progress_state["last_bucket"] = -1
    _progress_state["last_status"] = ""


def update_progress_bar(percent: float, status: str = ""):
    global _progress_state
    if not _progress_state["active"]:
        return
    _progress_state["percent"] = min(max(percent, 0), 100)
    if status:
        _progress_state["status"] = status
    # 只在进度跨 10% 整数阈值或状态变化时打印（避免刷屏）
    prev_bucket = int(_progress_state.get("last_bucket", -1))
    curr_bucket = int(_progress_state["percent"] // 10)
    if curr_bucket > prev_bucket or status != _progress_state.get("last_status", ""):
        _progress_state["last_bucket"] = curr_bucket
        _progress_state["last_status"] = status
        console.print(_format_progress())


def stop_progress_bar(final_status: str = "已完成"):
    global _progress_state
    if not _progress_state["active"]:
        return
    _progress_state["percent"] = 100
    _progress_state["status"] = final_status
    console.print(_format_progress())
    _progress_state["active"] = False


def session_start(task: str, worker_scope: str, butler_scope: str, model_info: str = ""):
    console.print(Panel(
        f"[bold]任务：[/bold]{task}\n\n"
        f"[bold]Worker 工作目录：[/bold][cyan]{worker_scope}[/cyan]\n"
        f"[bold]Butler 监管目录：[/bold][magenta]{butler_scope}[/magenta]\n"
        f"[bold]模型：[/bold]{model_info}",
        title="[bold green]Butler × Worker  协同工作台[/bold green]",
        border_style="green",
        box=box.DOUBLE_EDGE,
    ))
    console.print()


def worker_ask_butler(question: str):
    console.print(f"\n  [bold cyan]❓ Worker 向 Butler 提问：[/bold cyan]{question}")


def butler_answer(answer: str):
    console.print(Panel(
        f"[bold white]{answer}[/bold white]",
        title="[bold magenta]📖 Butler 回答[/bold magenta]",
        border_style="magenta",
        box=box.ROUNDED,
        padding=(0, 1),
    ))
    console.print()


def session_end():
    console.print()
    console.print(Panel("[bold green]任务已完成[/bold green]", border_style="green"))


def system_msg(msg: str):
    console.print(f"[bold magenta][系统][/bold magenta] {msg}")


def error_msg(who: str, err: str):
    label = {"Worker": "Worker 报错", "Butler": "Butler 报错", "Session": "会话异常"}.get(who, who)
    console.print(Panel(f"[white]{err}[/white]", title=f"[bold red]{label}[/bold red]", border_style="red"))


def user_prompt():
    console.print("\n[bold yellow]>[/bold yellow] ", end="")


def planner_header():
    console.print(Rule("[bold gold1]Planner  大管家[/bold gold1]", style="gold1"))


def planner_task_start(task_id: int, title: str):
    console.print(f"  [gold1]▶[/gold1] 开始执行任务 [bold]#{task_id}[/bold]: {title}")


def planner_task_done(task_id: int, title: str):
    console.print(f"  [green]✓[/green] 任务 [bold]#{task_id}[/bold] 完成: {title}")


def planner_archive(task_id: int):
    console.print(f"  [dim]  已归档至 tasks/archive/{task_id:03d}_*.json[/dim]")


def planner_summary(total: int, done: int):
    console.print()
    console.print(Panel(
        f"共 [bold]{total}[/bold] 个任务，已完成 [bold green]{done}[/bold green] 个",
        title="[bold gold1]Planner 汇总[/bold gold1]",
        border_style="gold1",
    ))
