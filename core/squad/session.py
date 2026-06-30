"""
core/squad_session.py — TUI 终端交互层

仅用于终端模式（display/app.py、display/planner_ui.py）。
所有编排逻辑委托给 core.squad.Squad，这里只负责交互循环。
"""
import asyncio
import sys

from core.config import ModelConfig
from core.runtime.session import State
from core.squad.squad import Squad
import display

_HELP = """
  stop          - 停止任务
  pause worker  - 暂停并与 Worker 对话
  pause mentor  - 暂停并与 Mentor 对话
  resume        - 恢复运行
  status        - 查看状态
  help          - 帮助
"""


async def _input_loop(squad: Squad):
    """TUI 交互循环，等待 Agent 就绪后才开始响应命令。"""
    await squad._agents_ready.wait()
    worker = squad.worker
    mentor = squad.mentor
    ctrl = squad.ctrl

    display.system_msg("任务运行中… 输入 [bold]help[/bold] 查看指令")
    loop = asyncio.get_event_loop()
    while not ctrl.is_stopped:
        display.user_prompt()
        try:
            line = await loop.run_in_executor(None, sys.stdin.readline)
        except (EOFError, KeyboardInterrupt):
            break
        if not line:
            break
        cmd = line.strip().lower()
        if not cmd:
            continue
        if cmd == "stop":
            ctrl.stop()
            display.system_msg("已停止。")
            break
        elif cmd in ("pause worker", "pause mentor", "pause"):
            if ctrl.state != State.RUNNING:
                display.system_msg(f"当前已是 {ctrl.state.value} 状态。")
                continue
            target = cmd.replace("pause", "").strip() or None
            ctrl.pause(target)
            label = {"worker": "Worker", "mentor": "Mentor"}.get(target, "全部 AI")
            display.system_msg(f"已暂停 {label}。直接输入消息，或 resume 继续。")
        elif cmd == "resume":
            if ctrl.state == State.RUNNING:
                display.system_msg("任务运行中。")
            else:
                ctrl.resume()
                display.system_msg("已恢复。")
        elif cmd == "status":
            display.system_msg(
                f"状态：[cyan]{ctrl.state.value}[/cyan]  轮次：[cyan]{worker.round}[/cyan]"
            )
        elif cmd == "help":
            display.system_msg(_HELP)
        elif ctrl.state == State.PAUSED:
            target = ctrl.paused_target
            if target in ("worker", None):
                display.worker_stream_start()
                await worker.chat_direct(line.strip())
                display.worker_stream_end()
            if target in ("mentor", None):
                display.mentor_stream_start(worker.round)
                await mentor.chat_direct(line.strip())
                display.mentor_stream_end()
        else:
            display.system_msg("未知指令，输入 help 查看。")


async def run_squad_session(
    squad_dict: dict,
    model: ModelConfig,
    task: str,
    headless: bool = False,
    log_path: str | None = None,
):
    """
    TUI 入口：从已有目录加载或直接构造 Squad，然后运行。

    squad_dict 格式：{"_name": str, "_dir": str}
    """
    import os
    from core.squad.squad import Squad

    name = squad_dict["_name"]
    squad_dir = squad_dict["_dir"]

    # 构造 Squad（不清除历史，TUI 模式复用已有目录）
    squad = Squad(name=name, task=task, squad_dir=squad_dir, log_path=log_path)

    # 启动编排（后台异步）
    await squad.start(model, push_event=_noop_push)

    if not headless:
        asyncio.create_task(_input_loop(squad))

    # 等待 worker task 完成
    if squad._asyncio_task:
        await squad._asyncio_task


def _noop_push(event: dict):
    """TUI 模式不需要 WebSocket 推送，尝试转发到 server（如果可用）。"""
    try:
        from server.main import push_event as _pe
        _pe(event)
    except Exception:
        pass
