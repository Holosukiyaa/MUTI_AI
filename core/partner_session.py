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


def push_event(event: dict):
    try:
        from server.main import push_event as _pe
        _pe(event)
    except Exception:
        pass


def _build_report(partner_name: str, task: str, worker_dir: str) -> str:
    files = []
    if os.path.exists(worker_dir):
        for f in os.listdir(worker_dir):
            if not f.startswith("history"):
                files.append(f)
    file_list = "、".join(files) if files else "无"
    return f"Partner [{partner_name}] 已完成任务：{task[:100]}\n生成文件：{file_list}"

_ASK_BUTLER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_butler",
        "description": "向管家询问你不知道的设计信息或需求细节",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
}

_HELP = """
  stop          - 停止任务
  pause worker  - 暂停并与 Worker 对话
  pause butler  - 暂停并与 Butler 对话
  resume        - 恢复运行
  status        - 查看状态
  help          - 帮助
"""


async def _input_loop(ctrl: SessionController, worker: WorkerAgent, butler: ButlerAgent):
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
        elif cmd in ("pause worker", "pause butler", "pause"):
            if ctrl.state != State.RUNNING:
                display.system_msg(f"当前已是 {ctrl.state.value} 状态。")
                continue
            target = cmd.replace("pause", "").strip() or None
            ctrl.pause(target)
            label = {"worker": "Worker", "butler": "Butler"}.get(target, "全部 AI")
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
            if target in ("butler", None):
                display.butler_stream_start(worker.round)
                await butler.chat_direct(line.strip())
                display.butler_stream_end()
        else:
            display.system_msg("未知指令，输入 help 查看。")


async def run_partner_session(partner: dict, model: ModelConfig, task: str, headless: bool = False, log_path: str | None = None):
    partner_dir = partner["_dir"]
    butler_dir = os.path.join(partner_dir, "butler")
    worker_dir = os.path.join(partner_dir, "worker")
    os.makedirs(butler_dir, exist_ok=True)
    os.makedirs(worker_dir, exist_ok=True)

    blueprint_path = os.path.join(butler_dir, "blueprint.md")
    blueprint = ""
    if os.path.exists(blueprint_path):
        with open(blueprint_path, encoding="utf-8") as f:
            blueprint = f.read()

    butler_system = (
        f"你是 Butler（管家），是本 Partner 的唯一知识持有者。\n"
        f"以下蓝图和设计信息只有你能看到，Worker 对此一无所知：\n\n{blueprint}\n\n"
        f"你的职责：\n"
        f"1. 当 Worker 通过 ask_butler 工具提问时，根据蓝图详细、准确地回答，给出具体数值和细节\n"
        f"2. 每轮审查 Worker 的工作，偏离规范时用 CORRECT: 纠正，严重错误用 ROLLBACK: 回滚\n"
        f"3. 不需要主动发起对话，等待 Worker 提问或审查快照\n"
        f"回答提问时要具体直接，不要说'请参考文档'，直接告诉 Worker 答案。"
    ) if blueprint else (
        "你是 Butler，负责监督 Worker 执行任务，是设计信息的唯一来源。"
        "Worker 会通过 ask_butler 向你提问，请据实回答。发现错误时用 CORRECT: 纠正。"
    )

    worker_system = (
        "你是 Worker，负责编写代码完成任务。\n"
        "重要：你对当前项目的设计一无所知。你必须通过 ask_butler 工具向管家（Butler）提问来获取所有设计信息。\n"
        "工作流程：\n"
        "1. 先用 ask_butler 询问任务的整体设计、需求和技术细节\n"
        "2. 收到回答后继续追问，直到掌握足够信息\n"
        "3. 了解清楚后用 write_file 编写代码\n"
        "4. 完成后调用 finish_task\n"
        "收到 [BUTLER CORRECTION] 消息时，这是高优先级指令，必须立即按照纠正内容修改。\n"
        "写文件规则：单次 write_file 内容不得超过 300 行。超过时，先用 write_file 写前半部分，再用 append_file 追加后续内容。"
    )

    ctrl = SessionController()
    bus = CorrectionBus()

    if log_path:
        display.set_log_path(log_path)

    worker_schemas, worker_handlers = make_tools([worker_dir])
    _, butler_handlers = make_tools([butler_dir])

    cfg = SessionConfig(
        task=task,
        project_root=partner_dir,
        worker_subdirs=["worker"],
        butler_model=model,
        worker_model=model,
        butler_system=butler_system,
        worker_system=worker_system,
        tool_schemas=worker_schemas + [_ASK_BUTLER_SCHEMA, FINISH_TASK_SCHEMA],
    )

    butler = ButlerAgent(cfg, bus, butler_handlers, ctrl,
                         history_path=os.path.join(butler_dir, "history.json"))
    worker = WorkerAgent(cfg, bus, worker_handlers, ctrl,
                         ask_butler_fn=butler.answer_question,
                         history_path=os.path.join(worker_dir, "history.json"))

    display.session_start(
        task=task,
        worker_scope=worker_dir,
        butler_scope=butler_dir,
        model_info=f"{model.model}（双端）",
    )
    display.init_progress_bar(task_desc=f"{partner['_name']} 任务进度")

    worker_task = asyncio.create_task(worker.run(task))
    if not headless:
        asyncio.create_task(_input_loop(ctrl, worker, butler))

    await worker_task
    display.stop_progress_bar()

    if ctrl.state == State.ERROR:
        display.error_msg("Session", ctrl.error_msg or "未知错误")
        push_event({"type": "session_done", "partner": partner["_name"], "status": "error", "report": ctrl.error_msg or "未知错误"})
    else:
        display.session_end()
        report = _build_report(partner["_name"], task, worker_dir)
        push_event({"type": "session_done", "partner": partner["_name"], "status": "ok", "report": report})
