import asyncio
import os
import sys

from core.config import SessionConfig, ModelConfig
from core.bus import CorrectionBus
from core.session import SessionController
from core.agents.planner import PlannerAgent
from core.tools.task_cards import init_tasks_dir
import display


HELP_TEXT = """
可用指令：
  stop          - 停止所有任务
  pause         - 暂停执行
  resume        - 恢复执行
  status        - 查看任务状态
  help          - 显示帮助
"""


async def input_loop(ctrl: SessionController, planner: PlannerAgent):
    display.system_msg("Planner 已就绪，输入 [bold]help[/bold] 查看可用指令")
    while not ctrl.is_stopped:
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
            display.system_msg("已停止所有任务。")
            break
        elif cmd == "pause":
            if ctrl.state.value == "running":
                ctrl.pause()
                display.system_msg("已暂停。输入 resume 继续。")
            else:
                display.system_msg(f"当前已是 {ctrl.state.value} 状态。")
        elif cmd == "resume":
            if ctrl.state.value != "running":
                ctrl.resume()
                display.system_msg("已恢复运行。")
            else:
                display.system_msg("任务正在运行中。")
        elif cmd == "status":
            pending = planner.task_count
            done = planner.done_count
            display.system_msg(f"状态：[cyan]{ctrl.state.value}[/cyan]  任务：[cyan]{done}/{pending} 完成[/cyan]")
        elif cmd == "help":
            display.system_msg(HELP_TEXT)
        else:
            display.system_msg("未知指令，输入 [bold]help[/bold] 查看帮助。")


async def main():
    display.welcome()
    display.planner_header()
    display.system_msg("请输入你的项目需求，Planner 将自动拆解为任务并执行：")

    display.user_prompt()
    try:
        user_input = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
    except (EOFError, KeyboardInterrupt):
        return
    user_input = user_input.strip()
    if not user_input:
        display.system_msg("未输入需求，退出。")
        return

    # Load env
    ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
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

    init_tasks_dir(ROOT)

    ctrl = SessionController()
    bus = CorrectionBus()

    cfg = SessionConfig(
        task=user_input,
        project_root=ROOT,
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
        planner_model=ModelConfig(
            provider="openai",
            model="deepseek-v4-pro",
            api_key=API_KEY,
            base_url=BASE_URL,
        ),
    )

    planner = PlannerAgent(cfg, bus, ctrl)

    planner_task = asyncio.create_task(planner.run(user_input))
    asyncio.create_task(input_loop(ctrl, planner))

    await planner_task

    if ctrl.state.value == "stopped":
        display.system_msg("任务已终止。")


if __name__ == "__main__":
    asyncio.run(main())
