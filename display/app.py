import os
import sys
import json
import shutil
import asyncio

from textual.app import App, ComposeResult
from textual.screen import Screen, ModalScreen
from textual.widgets import (
    Static, ListView, ListItem, Label, Input,
    RichLog, Header, Footer, ProgressBar,
)
from textual.containers import Vertical, Horizontal, ScrollableContainer
from textual.binding import Binding
from textual import on, work
from rich.text import Text

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PLANNERS_DIR = os.path.join(ROOT, ".data", "planners")
SQUADS_DIR = os.path.join(ROOT, "squads")

_LOGO = (
    " [bold bright_red]███████╗ ██████╗██╗  ██╗███████╗██╗      ██████╗ ███╗   ██╗[/bold bright_red]\n"
    " [bold bright_red]██╔════╝██╔════╝██║  ██║██╔════╝██║     ██╔═══██╗████╗  ██║[/bold bright_red]\n"
    " [bold bright_red]█████╗  ██║     ███████║█████╗  ██║     ██║   ██║██╔██╗ ██║[/bold bright_red]\n"
    " [bold bright_red]██╔══╝  ██║     ██╔══██║██╔══╝  ██║     ██║   ██║██║╚██╗██║[/bold bright_red]\n"
    " [bold bright_red]███████╗╚██████╗██║  ██║███████╗███████╗╚██████╔╝██║ ╚████║[/bold bright_red]\n"
    " [bold bright_red]╚══════╝ ╚═════╝╚═╝  ╚═╝╚══════╝╚══════╝ ╚═════╝╚═╝  ╚═══╝[/bold bright_red]"
    "  [dim]─── ai[/dim]"
)

CSS = """
Screen { background: #0d1117; }
#logo { padding: 1 2; }
#subtitle { padding: 0 2; color: #8b949e; }
ListView { background: #0d1117; border: none; padding: 1 2; }
ListItem { background: #0d1117; padding: 0 1; }
ListItem:focus-within, ListItem.--highlight { background: #1a1f2e; }
ListItem > Label { color: #8b949e; }
ListItem.--highlight > Label { color: #ff7b72; text-style: bold; }
#hint { padding: 1 2; color: #484f58; }
RichLog { background: #0d1117; border: none; padding: 0 1; scrollbar-color: #30363d; }
Input { background: #161b22; border: tall #30363d; color: yellow; padding: 0 1; }
#input-bar { height: 3; padding: 0 1; }
#chat-log { border: none; }
#session-log { border: none; }
#progress-bar-container { height: 3; padding: 0 2; }
ProgressBar { width: 1fr; }
#session-header { height: 3; background: #161b22; padding: 0 2; color: cyan; text-style: bold; }
Header { background: #161b22; color: #8b949e; }
Footer { background: #161b22; color: #8b949e; }
"""


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


def _list_planners():
    if not os.path.exists(PLANNERS_DIR):
        return []
    result = []
    for name in sorted(os.listdir(PLANNERS_DIR)):
        meta = os.path.join(PLANNERS_DIR, name, "meta.json")
        if os.path.isfile(meta):
            try:
                with open(meta, encoding="utf-8") as f:
                    d = json.load(f)
                    d["_name"] = name
                    d["_dir"] = os.path.join(PLANNERS_DIR, name)
                    d["_history"] = os.path.join(PLANNERS_DIR, name, "history.json")
                    result.append(d)
            except Exception:
                pass
    return result


class SettingsScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "返回")]

    def compose(self) -> ComposeResult:
        key = os.environ.get("DEEPSEEK_API_KEY", "")
        status = f"当前：sk-...{key[-4:]}" if key else "当前：未设置"
        with Vertical(id="settings-modal"):
            yield Static(" ⚙  设置 API Key", id="modal-title")
            yield Static(f" {status}", id="modal-status")
            yield Input(placeholder="输入新的 API Key（sk- 开头）", id="api-input", password=True)
            yield Static(" [dim]Enter 保存  Esc 返回[/dim]", id="modal-hint")

    def on_input_submitted(self, event: Input.Submitted):
        val = event.value.strip()
        if val:
            full = val if val.startswith("sk-") else f"sk-{val}"
            os.environ["DEEPSEEK_API_KEY"] = full
            base_url = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")
            with open(os.path.join(ROOT, ".env"), "w", encoding="utf-8") as f:
                f.write(f"DEEPSEEK_API_KEY={full}\n")
                f.write(f"DEEPSEEK_BASE_URL={base_url}\n")
        self.dismiss()

    DEFAULT_CSS = """
    SettingsScreen { align: center middle; }
    #settings-modal { background: #161b22; border: round #30363d; padding: 1 2; width: 60; height: auto; }
    #modal-title { color: bright_white; text-style: bold; padding-bottom: 1; }
    #modal-status { color: grey50; padding-bottom: 1; }
    #modal-hint { color: grey35; padding-top: 1; }
    """


class WelcomeScreen(Screen):
    BINDINGS = [Binding("q", "quit", "退出")]

    _ITEMS = [
        ("1.  与 Planner 对话", "planner"),
        ("2.  示例 · Todo 纠正实验", "todo"),
        ("3.  示例 · 地下城 RPG 开发", "rpg"),
        ("4.  ⚙  设置", "settings"),
        ("5.  退出", "exit"),
    ]

    def compose(self) -> ComposeResult:
        yield Static(_LOGO, id="logo", markup=True)
        yield Static("  Multi-Agent Collaborative Framework  v0.1.0", id="subtitle")
        lv = ListView(*[ListItem(Label(label), id=f"item-{val}") for label, val in self._ITEMS])
        yield lv
        yield Static("  ↑ ↓ 移动  Enter 确认  Q 退出", id="hint")

    def on_list_view_selected(self, event: ListView.Selected):
        item_id = event.item.id.replace("item-", "") if event.item.id else ""
        self._handle(item_id)

    def _handle(self, choice: str):
        if choice == "settings":
            self.app.push_screen(SettingsScreen())
        elif choice == "exit":
            self.app.exit()
        elif choice == "planner":
            self.app.push_screen(PlannerListScreen())
        elif choice in ("todo", "rpg"):
            import subprocess, shutil as sh
            py = sh.which("python") or sys.executable
            mods = {"todo": "examples.todo_correction.run", "rpg": "examples.dungeon_rpg.run"}
            self.app.suspend()
            subprocess.run([py, "-m", mods[choice]], cwd=ROOT)

    def action_quit(self):
        self.app.exit()


class NewPlannerScreen(ModalScreen):
    BINDINGS = [Binding("escape", "dismiss", "取消")]

    def compose(self) -> ComposeResult:
        with Vertical(id="new-planner-modal"):
            yield Static(" ＋ 新建 Planner", id="modal-title")
            yield Input(placeholder="名称（唯一标识，英文/拼音）", id="name-input")
            yield Input(placeholder="职责描述（一句话）", id="desc-input")
            yield Static(" [dim]先输入名称，再输描述，Enter 确认  Esc 取消[/dim]", id="modal-hint")

    def on_mount(self):
        self.query_one("#name-input").focus()

    def on_input_submitted(self, event: Input.Submitted):
        if event.input.id == "name-input":
            self.query_one("#desc-input").focus()
        elif event.input.id == "desc-input":
            name = self.query_one("#name-input").value.strip()
            desc = self.query_one("#desc-input").value.strip()
            if name:
                p_dir = os.path.join(PLANNERS_DIR, name)
                os.makedirs(p_dir, exist_ok=True)
                with open(os.path.join(p_dir, "meta.json"), "w", encoding="utf-8") as f:
                    json.dump({"name": name, "description": desc}, f, ensure_ascii=False, indent=2)
            self.dismiss(name if name else None)

    DEFAULT_CSS = """
    NewPlannerScreen { align: center middle; }
    #new-planner-modal { background: #161b22; border: round #30363d; padding: 1 2; width: 60; height: auto; }
    #modal-title { color: bright_white; text-style: bold; padding-bottom: 1; }
    #modal-hint { color: grey35; padding-top: 1; }
    Input { margin-bottom: 1; }
    """


class PlannerListScreen(Screen):
    BINDINGS = [
        Binding("escape", "back", "返回"),
        Binding("n", "new_planner", "新建"),
        Binding("delete", "delete_planner", "删除"),
    ]

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield ListView(id="planner-list")
        yield Footer()

    def on_mount(self):
        self.sub_title = "Planner 管理"
        self._refresh_list()

    def _refresh_list(self):
        lv = self.query_one("#planner-list", ListView)
        lv.clear()
        planners = _list_planners()
        if not planners:
            lv.append(ListItem(Label("[dim]  暂无 Planner，按 N 新建[/dim]"), id="empty"))
        for p in planners:
            desc = p.get("description", "")
            lv.append(ListItem(Label(f"  {p['_name']}  [dim]{desc}[/dim]"), id=f"p-{p['_name']}"))

    def on_list_view_selected(self, event: ListView.Selected):
        if not event.item.id or event.item.id == "empty":
            return
        name = event.item.id.replace("p-", "", 1)
        planners = {p["_name"]: p for p in _list_planners()}
        if name in planners:
            p = planners[name]
            self._open_planner(p)

    def _open_planner(self, p: dict):
        from core.planner import PlannerAgent
        from core.config import ModelConfig
        model = ModelConfig(
            provider="openai", model="deepseek-chat",
            api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
            base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
        )
        planner = PlannerAgent(model=model, history_path=p["_history"], name=p["_name"])
        def model_factory():
            return ModelConfig(
                provider="openai", model="deepseek-chat",
                api_key=os.environ.get("DEEPSEEK_API_KEY", ""),
                base_url=os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            )
        self.app.push_screen(PlannerChatScreen(planner, model_factory))

    def action_back(self):
        self.app.pop_screen()

    def action_new_planner(self):
        def _done(name):
            if name:
                self._refresh_list()
        self.app.push_screen(NewPlannerScreen(), _done)

    def action_delete_planner(self):
        lv = self.query_one("#planner-list", ListView)
        highlighted = lv.highlighted_child
        if not highlighted or highlighted.id == "empty":
            return
        name = highlighted.id.replace("p-", "", 1)
        p_dir = os.path.join(PLANNERS_DIR, name)
        shutil.rmtree(p_dir, ignore_errors=True)
        self._refresh_list()
        self.notify(f"已删除 {name}", severity="warning")


class PlannerChatScreen(Screen):
    BINDINGS = [Binding("escape", "back", "返回")]

    def __init__(self, planner, model_factory):
        super().__init__()
        self.planner = planner
        self.model_factory = model_factory

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield RichLog(id="chat-log", markup=True, wrap=True, highlight=False)
        with Horizontal(id="input-bar"):
            yield Input(placeholder="输入消息… /clear 清空  Esc 返回", id="chat-input")
        yield Footer()

    def on_mount(self):
        self.sub_title = f"Planner · {self.planner.name}"
        log = self.query_one("#chat-log", RichLog)
        for m in self.planner.history():
            role, content = m.get("role"), (m.get("content") or "")
            if not content:
                continue
            if role == "user":
                log.write(f"[bold yellow]你[/bold yellow]  {content}")
            elif role == "assistant":
                log.write(f"[bold magenta]Planner[/bold magenta]  {content}")
        self.query_one("#chat-input").focus()

    def on_input_submitted(self, event: Input.Submitted):
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text == "/clear":
            self.planner.clear()
            self.query_one("#chat-log", RichLog).clear()
            return
        log = self.query_one("#chat-log", RichLog)
        log.write(f"[bold yellow]你[/bold yellow]  {text}")
        self._do_chat(text)

    @work(exclusive=False)
    async def _do_chat(self, text: str):
        log = self.query_one("#chat-log", RichLog)
        buf = []

        def on_token(tok):
            buf.append(tok)
            self.app.call_from_thread(log.write, "[bold magenta]Planner[/bold magenta]  " + "".join(buf) if len(buf) == 1 else "".join(buf[-1:]))

        await self.planner.chat(text, on_token=None)
        reply = (self.planner.messages[-1].get("content") or "").strip()
        if reply:
            log.write(f"[bold magenta]Planner[/bold magenta]  {reply}")

        for tc in self.planner.last_tool_calls:
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
            log.write(f"\n[bold cyan]▶ 启动 Squad · {name}[/bold cyan]  {task}\n")
            self.app.push_screen(SessionScreen(squad, self.model_factory, task, self.planner, tc.get("id", "")))

        self.planner.last_tool_calls = []

    def action_back(self):
        self.app.pop_screen()


class SessionScreen(Screen):
    BINDINGS = [
        Binding("ctrl+c", "stop_session", "停止"),
        Binding("escape", "back", "返回"),
    ]

    def __init__(self, squad, model_factory, task, planner=None, tool_call_id=""):
        super().__init__()
        self.squad = squad
        self.model_factory = model_factory
        self.task = task
        self.planner = planner
        self.tool_call_id = tool_call_id
        self._ctrl = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=False)
        yield RichLog(id="session-log", markup=True, wrap=True, highlight=False)
        with Horizontal(id="progress-bar-container"):
            yield ProgressBar(id="session-progress", show_eta=False, show_percentage=True)
        yield Footer()

    def on_mount(self):
        self.sub_title = f"Squad · {self.squad['_name']}"
        _set_session_screen(self)
        self._run_session()

    def on_unmount(self):
        _set_session_screen(None)

    @work(exclusive=False)
    async def _run_session(self):
        from core.squad.session import run_squad_session
        await run_squad_session(self.squad, self.model_factory(), self.task)
        if self.planner and self.tool_call_id:
            self.planner.confirm_tool_result(self.tool_call_id, f"Squad '{self.squad['_name']}' 已完成。")
        log = self.query_one("#session-log", RichLog)
        log.write("\n[bold green]✓ 任务完成[/bold green]  按 Esc 返回")

    def action_stop_session(self):
        if self._ctrl:
            self._ctrl.stop()

    def action_back(self):
        self.app.pop_screen()

    def write_log(self, markup: str):
        try:
            self.query_one("#session-log", RichLog).write(markup)
        except Exception:
            pass

    def set_progress(self, percent: float):
        try:
            self.query_one("#session-progress", ProgressBar).update(progress=percent, total=100)
        except Exception:
            pass


_active_session: "SessionScreen | None" = None


def _set_session_screen(screen):
    global _active_session
    _active_session = screen


def get_session_screen() -> "SessionScreen | None":
    return _active_session


class EchelonApp(App):
    CSS = CSS

    def on_mount(self):
        _load_env()
        self.push_screen(WelcomeScreen())
