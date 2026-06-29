import os
import sys
import msvcrt
from rich.console import Console
from rich.panel import Panel
from rich import box

console = Console()

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

_LOGO = (
    "[bold bright_red] ███████╗ ██████╗██╗  ██╗███████╗██╗      ██████╗ ███╗   ██╗[/bold bright_red]\n"
    "[bold bright_red] ██╔════╝██╔════╝██║  ██║██╔════╝██║     ██╔═══██╗████╗  ██║[/bold bright_red]\n"
    "[bold bright_red] █████╗  ██║     ███████║█████╗  ██║     ██║   ██║██╔██╗ ██║[/bold bright_red]\n"
    "[bold bright_red] ██╔══╝  ██║     ██╔══██║██╔══╝  ██║     ██║   ██║██║╚██╗██║[/bold bright_red]\n"
    "[bold bright_red] ███████╗╚██████╗██║  ██║███████╗███████╗╚██████╔╝██║ ╚████║[/bold bright_red]\n"
    "[bold bright_red] ╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝╚═╝  ╚═══╝[/bold bright_red][dim]  ─── ai[/dim]"
)

_MAIN_MENU = [
    ("与 Planner 对话", "planner"),
    ("示例 · Todo 纠正实验", "todo"),
    ("示例 · 地下城 RPG 开发", "rpg"),
    ("⚙  设置", "settings"),
    ("退出", "exit"),
]


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


def _render(items, selected, subtitle=None):
    os.system('cls')
    console.print()
    console.print(_LOGO)
    console.print()
    console.print("[dim]  Multi-Agent Collaborative Framework  v0.1.0[/dim]")
    console.print()
    if subtitle:
        console.print(f"  [bold white]{subtitle}[/bold white]")
        console.print()
    for i, (lbl, _) in enumerate(items):
        if i == selected:
            console.print(f"  [bold red]  {i+1}.  {lbl}[/bold red]")
        else:
            console.print(f"  [dim]  {i+1}.  {lbl}[/dim]")
    console.print()
    console.print("[dim]  ↑ ↓ 移动   Enter 确认[/dim]")


def _navigate(items, subtitle=None) -> str:
    sel = 0
    while True:
        _render(items, sel, subtitle)
        key = _read_key()
        if key == 'up':
            sel = (sel - 1) % len(items)
        elif key == 'down':
            sel = (sel + 1) % len(items)
        elif key == 'enter':
            return items[sel][1]


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


def _settings():
    while True:
        key_val = os.environ.get("DEEPSEEK_API_KEY", "")
        status = f"sk-...{key_val[-4:]}" if key_val else "[red]未设置[/red]"
        items = [
            (f"设置 API Key  ({status})", "set_key"),
            ("← 返回", "back"),
        ]
        choice = _navigate(items, subtitle="⚙  设置")
        if choice == "back":
            return
        console.clear()
        console.print(_LOGO)
        console.print("\n  请输入 DeepSeek API Key（直接回车取消）：\n")
        console.print("  sk-", end="", highlight=False)
        raw = sys.stdin.readline().strip()
        if raw:
            full = f"sk-{raw}"
            os.environ["DEEPSEEK_API_KEY"] = full
            env_path = os.path.join(ROOT, ".env")
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            with open(env_path, "w", encoding="utf-8") as f:
                f.write(f"DEEPSEEK_API_KEY={full}\n")
                f.write(f"DEEPSEEK_BASE_URL={base_url}\n")
            console.print("  [green]✓ 已保存[/green]  按任意键继续...")
            msvcrt.getwch()


def run_welcome() -> tuple[str, dict | None]:
    """返回 (choice, partner_or_None)。choice: 'planner'|'partner'|'todo'|'rpg'"""
    _load_env()
    while True:
        choice = _navigate(_MAIN_MENU)
        if choice == "settings":
            _settings()
        elif choice == "exit":
            os.system('cls')
            sys.exit(0)
        else:
            os.system('cls')
            return choice, None
