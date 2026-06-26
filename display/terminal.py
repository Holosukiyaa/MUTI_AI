from rich.console import Console
from rich.panel import Panel
from rich.rule import Rule
from rich import box

console = Console()

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
    console.print(Panel(
        "[bold white]Butler × Worker[/bold white]  双 Agent 协同框架\n\n"
        "[cyan]Butler[/cyan]  拥有私有知识、全局视角，实时监督并纠正 Worker\n"
        "[green]Worker[/green]  专注执行任务，只能访问指定目录，可主动向 Butler 提问\n\n"
        "[dim]可用指令：stop / pause worker / pause butler / resume / status / help[/dim]",
        title="[bold green]欢迎使用 MUTI_AI[/bold green]",
        border_style="green",
        box=box.DOUBLE_EDGE,
        padding=(1, 2),
    ))
    console.print()


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
