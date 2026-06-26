import asyncio
import os
import sys

from core.config import SessionConfig, ModelConfig
from core.bus import CorrectionBus
from core.tools import make_tools
from core.agents.worker import WorkerAgent
from core.agents.butler import ButlerAgent
from core.session import SessionController, State
import display

EXAMPLE_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(EXAMPLE_DIR, "src")

API_KEY = os.environ.get("DEEPSEEK_API_KEY", "")
BASE_URL = os.environ.get("DEEPSEEK_BASE_URL", "https://api.deepseek.com")

TASK = """你是一名Python程序员，你的任务是开发一个地下城RPG游戏。
但你目前对游戏设计一无所知——没有文档，没有规格。

你必须通过 ask_butler 工具主动向管家（Butler）询问设计细节，然后根据回答编写代码。

建议的提问顺序：
1. 先问游戏的整体概念和目标
2. 再问玩家属性和角色系统
3. 再问怪物和战斗系统
4. 再问地图结构
5. 最后问代码结构要求

所有信息了解清楚后，使用 write_file 将完整游戏写入 "dungeon.py"，然后回复 DONE。"""

ASK_BUTLER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_butler",
        "description": "向管家（Butler）询问游戏设计信息。管家拥有完整的设计蓝图，你可以问任何关于游戏规则、数据、结构的问题。",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string", "description": "你的具体问题"}},
            "required": ["question"],
        },
    },
}

BUTLER_SYSTEM = """你是游戏项目的管家（Butler），拥有地下城RPG游戏的完整设计蓝图。
蓝图内容如下：

{blueprint}

你的职责：
1. 当Worker通过工具提问时，根据蓝图详细、准确地回答
2. 监督Worker编写的代码是否符合蓝图规范
3. 如果Worker的代码与蓝图不符，用 CORRECT: 开头发出纠正

回答提问时要具体，给出数值和细节。不要说"请参考文档"，直接告诉Worker答案。"""

WORKER_SYSTEM = """你是一名Python程序员。你对当前项目一无所知，但你可以通过 ask_butler 工具向管家询问设计细节。
收到回答后，将信息记在心里，继续提问直到了解所有必要信息，然后编写代码。
编写完成后用 write_file 保存，最后回复 DONE。"""

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
            display.system_msg(f"任务因错误中断：{ctrl.error_msg}")

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
            ctrl.resume() if ctrl.state != State.RUNNING else display.system_msg("任务正在运行中。")
            if ctrl.state == State.RUNNING:
                display.system_msg("已恢复运行。")
        elif cmd == "status":
            display.system_msg(f"状态：[cyan]{ctrl.state.value}[/cyan]  当前轮次：[cyan]{worker.round}[/cyan]")
        elif cmd == "help":
            display.system_msg(HELP_TEXT)
        elif ctrl.state == State.PAUSED:
            target = ctrl.paused_target
            if target in ("worker", None):
                display.worker_stream_start()
                await worker.chat_direct(line.strip())
                display.worker_stream_end()
            if target in ("butler", None):
                display.butler_stream_start(worker.round)
                await butler.chat_direct(line.strip())
                display.butler_stream_end()
        else:
            display.system_msg("未知指令，输入 [bold]help[/bold] 查看帮助。")


async def main():
    blueprint_path = os.path.join(EXAMPLE_DIR, "blueprint.md")
    with open(blueprint_path, encoding="utf-8") as f:
        blueprint = f.read()

    os.makedirs(SRC_DIR, exist_ok=True)

    ctrl = SessionController()
    bus = CorrectionBus()

    worker_schemas, worker_handlers = make_tools([SRC_DIR])
    _, butler_handlers = make_tools([EXAMPLE_DIR])

    worker_schemas_with_ask = worker_schemas + [ASK_BUTLER_SCHEMA]

    cfg = SessionConfig(
        task=TASK,
        project_root=EXAMPLE_DIR,
        worker_subdirs=["src"],
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
        butler_system=BUTLER_SYSTEM.format(blueprint=blueprint),
        worker_system=WORKER_SYSTEM,
        tool_schemas=worker_schemas_with_ask,
    )

    butler = ButlerAgent(cfg, bus, butler_handlers, ctrl)
    worker = WorkerAgent(cfg, bus, worker_handlers, ctrl,
                         ask_butler_fn=butler.answer_question)

    display.session_start(
        task="地下城RPG游戏开发（Worker从零开始向Butler问询设计蓝图）",
        worker_scope=SRC_DIR,
        butler_scope=EXAMPLE_DIR,
        model_info="deepseek-v4-pro（双端）",
    )

    worker_task = asyncio.create_task(worker.run(TASK))
    asyncio.create_task(input_loop(ctrl, worker, butler))

    await worker_task

    if ctrl.state == State.ERROR:
        display.error_msg("Session", ctrl.error_msg or "未知错误")
    else:
        display.session_end()


if __name__ == "__main__":
    asyncio.run(main())
