import asyncio
import os
import sys

from core.config import SessionConfig, ModelConfig, FINISH_TASK_SCHEMA
from core.bus import CorrectionBus
from core.tools import make_tools
from core.agents.worker import WorkerAgent
from core.agents.butler import ButlerAgent
from core.session import SessionController, State
import display

EXAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(EXAMPLE_DIR))

# 加载 .env
env_path = os.path.join(ROOT, ".env")
if os.path.exists(env_path):
    with open(env_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

TASK = """Use read_file to read "spec.txt".
Then implement "todo.py" with these rules:
- complete(id) should DELETE the item from storage (mark it as done by removing it)
- list_all() can return the internal list directly, no need for a copy
- IDs can start at 0
Write the file with write_file using filename "todo.py" only.
When done, call the finish_task tool."""

BUTLER_SYSTEM = """You are Butler. You have full access to the example directory including spec.txt.
ALWAYS read spec.txt first with read_file to know the real requirements.
Worker has been given WRONG instructions. The real spec says:
- complete() must set done=True, NOT delete the item
- list_all() must return a COPY, not the internal list
- IDs must start at 1, not 0
If Worker writes code that violates any of these, respond with CORRECT: followed by the specific fix needed."""

HELP_TEXT = """
可用指令：
  stop          - 立即停止所有 AI
  pause worker  - 暂停并单独与 Worker 对话
  pause butler  - 暂停并单独与 Butler 对话
  pause         - 暂停所有 AI
  resume        - 恢复运行
  status        - 查看当前状态
  help          - 显示帮助
"""


async def input_loop(ctrl: SessionController, worker: WorkerAgent, butler: ButlerAgent):
    display.system_msg("任务启动中… 输入 [bold]help[/bold] 查看可用指令")
    while not ctrl.is_stopped:
        if ctrl.state == State.ERROR:
            display.system_msg(f"任务因错误中断：{ctrl.error_msg}（输入 stop 退出或 resume 重试）")

        display.user_prompt()
        try:
            line = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        except EOFError:
            break

        if not line:
            break

        cmd = line.strip().lower()
        if not cmd:
            continue

        if cmd == "stop":
            ctrl.stop()
            display.system_msg("已停止所有 AI。")
            break
        elif cmd in ("pause worker", "pause butler", "pause"):
            if ctrl.state != State.RUNNING:
                display.system_msg(f"当前已是 {ctrl.state.value} 状态。")
                continue
            target = cmd.replace("pause", "").strip() or None
            ctrl.pause(target)
            label = {"worker": "Worker", "butler": "Butler"}.get(target, "全部 AI")
            display.system_msg(f"已暂停 {label}。直接输入消息与其对话，或输入 [bold]resume[/bold] 继续。")
        elif cmd == "resume":
            if ctrl.state == State.RUNNING:
                display.system_msg("任务正在运行中。")
            else:
                ctrl.resume()
                display.system_msg("已恢复运行。")
        elif cmd == "status":
            state_map = {"running": "运行中", "paused": "已暂停", "stopped": "已停止", "error": "错误"}
            s = state_map.get(ctrl.state.value, ctrl.state.value)
            display.system_msg(f"状态：[cyan]{s}[/cyan]  当前轮次：[cyan]{worker.round}[/cyan]  暂停对象：{ctrl.paused_target or '无'}")
        elif cmd == "help":
            display.system_msg(HELP_TEXT)
        elif ctrl.state == State.PAUSED:
            target = ctrl.paused_target
            if target in ("worker", None):
                display.system_msg("→ 发送给 Worker：")
                display.worker_stream_start()
                await worker.chat_direct(line.strip())
                display.worker_stream_end()
            if target in ("butler", None):
                display.system_msg("→ 发送给 Butler：")
                display.butler_stream_start(worker.round)
                await butler.chat_direct(line.strip())
                display.butler_stream_end()
        else:
            display.system_msg("未知指令，输入 [bold]help[/bold] 查看帮助。")


async def main():
    display.welcome()
    ctrl = SessionController()
    bus = CorrectionBus()

    worker_schemas, worker_handlers = make_tools([EXAMPLE_DIR])
    _, butler_handlers = make_tools([EXAMPLE_DIR])

    cfg = SessionConfig(
        task=TASK,
        project_root=EXAMPLE_DIR,
        worker_subdirs=[],
        butler_model=ModelConfig(
            provider="openai",
            model="deepseek-v4-pro",
            api_key=API_KEY,
            base_url=BASE_URL,
        ),
        worker_model=ModelConfig(
            provider="openai",
            model="deepseek-v4-pro",
            api_key=API_KEY,
            base_url=BASE_URL,
        ),
        butler_system=BUTLER_SYSTEM,
        tool_schemas=worker_schemas + [FINISH_TASK_SCHEMA],
    )

    butler = ButlerAgent(cfg, bus, butler_handlers, ctrl)
    worker = WorkerAgent(cfg, bus, worker_handlers, ctrl)

    display.session_start(
        task="Implement todo.py  (Worker gets wrong instructions — Butler will intercept)",
        worker_scope=EXAMPLE_DIR,
        butler_scope=EXAMPLE_DIR,
        model_info="deepseek-v4-pro（双端）",
    )

    worker_task = asyncio.create_task(worker.run(TASK))
    asyncio.create_task(input_loop(ctrl, worker, butler))

    await worker_task

    if ctrl.state == State.ERROR:
        display.error_msg("Session", ctrl.error_msg or "unknown error")
    else:
        display.session_end()


if __name__ == "__main__":
    asyncio.run(main())
