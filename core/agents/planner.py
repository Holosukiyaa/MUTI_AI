import json
import os
import sys
import asyncio
from core.config import SessionConfig, ModelConfig, FINISH_TASK_SCHEMA
from core.bus import CorrectionBus
from core.tools import make_tools
from core.agents.worker import WorkerAgent
from core.agents.butler import ButlerAgent
from core.session import SessionController, State
from core.llm import chat
from core.tools.task_cards import (
    create_task, list_pending_tasks, archive_task,
    init_tasks_dir, count_pending,
)
import display


_BREAKDOWN_SYSTEM = """你是 Planner，负责将用户需求拆解为可执行的任务卡片。

规则：
1. 控制任务数量：简单项目（1-2天工作量）拆 1-2 个任务，中等项目拆 2-4 个
2. 每个任务必须是完整的、可独立交付的成果，而不是一个步骤
3. 将逻辑相关的步骤合并到同一个任务中（如"创建页面结构+样式"合并为一个）
4. description 要足够具体，包含功能点和技术要求
5. 只输出 JSON，不要输出其他内容

输出格式（严格 JSON 数组）：
[
  {"title": "任务标题", "description": "详细描述，包含具体功能点和交付要求"},
  ...
]

示例对比：
❌ 错误（太碎）：创建 HTML 文件、创建 CSS 文件、绘制背景、绘制蛇、处理食物...
✓ 正确（合并）：实现贪吃蛇游戏前端 — 包含 HTML 结构、Canvas 绘制（蛇/食物/背景）、游戏循环渲染"""

_PLANNER_SYSTEM = """你是 Planner（大管家），负责管理和调度任务执行。

你的职责：
1. 向用户汇报当前任务进度
2. 回答用户关于项目进度的提问
3. 当所有任务完成后，向用户做最终汇报

工作流程：
- 你不需要直接编码
- 你管理任务卡片（已存储在 tasks/pending/）
- 每个任务由一个 Butler+Worker 对执行
- 任务完成后自动归档
- 你只需要监控进度并汇报"""


class PlannerAgent:
    def __init__(self, cfg: SessionConfig, bus: CorrectionBus, ctrl: SessionController):
        self.cfg = cfg
        self.bus = bus
        self.ctrl = ctrl
        self.messages: list[dict] = [{"role": "system", "content": _PLANNER_SYSTEM}]
        self.task_count = 0
        self.done_count = 0

    async def run(self, user_request: str):
        """主入口：接收用户需求，拆解并执行所有任务。"""
        # Phase 1: Break down into task cards (user confirms)
        task_cards = await self._break_down(user_request)
        if not task_cards:
            display.system_msg("未确认任何任务，退出。")
            return

        display.system_msg(f"已确认 [bold]{len(task_cards)}[/bold] 个任务卡片，开始执行...")
        display.init_progress_bar(total_steps=len(task_cards), task_desc="总进度")

        # Phase 2: Execute each task
        for card in task_cards:
            await self.ctrl.wait_resume()
            if self.ctrl.is_stopped:
                display.system_msg("任务已被用户终止。")
                break

            self.task_count += 1
            display.planner_task_start(card["id"], card["title"])
            display.update_progress_bar(
                ((self.task_count - 1) / max(len(task_cards), 1)) * 100,
                f"执行: {card['title']}",
            )

            success = await self._execute_task(card)

            if success:
                archive_task(card["id"])
                display.planner_archive(card["id"])
                display.planner_task_done(card["id"], card["title"])
                self.done_count += 1
            else:
                display.system_msg(f"任务 #{card['id']} 执行失败，已跳过。")

            display.update_progress_bar(
                (self.task_count / max(len(task_cards), 1)) * 100,
                f"已完成 {self.done_count}/{len(task_cards)}",
            )

        display.stop_progress_bar("全部完成")
        display.planner_summary(len(task_cards), self.done_count)

    async def _break_down(self, user_request: str) -> list[dict]:
        """Planner 以 user role 调用 LLM 拆解需求，展示给用户确认后生成卡片。"""
        prompt = (
            f"用户需求：\n{user_request}\n\n"
            "请将需求拆解为独立的任务卡片，输出 JSON 数组。"
        )
        resp = await chat(
            self.cfg.planner_model,
            [{"role": "user", "content": _BREAKDOWN_SYSTEM + "\n\n" + prompt}],
        )
        raw = resp.get("content", "")

        items = self._parse_breakdown(raw)
        if not items:
            items = [{"title": "完成用户需求", "description": user_request}]

        # Show breakdown to user for confirmation
        display.system_msg("\n[bold]Planner 拆解的任务列表：[/bold]")
        for i, item in enumerate(items, 1):
            display.system_msg(f"  {i}. [cyan]{item['title']}[/cyan]\n     {item['description'][:100]}")
        display.system_msg(f"\n共 {len(items)} 个任务。按回车确认并开始执行，输入 [bold]r[/bold] 重新拆解，输入 [bold]cancel[/bold] 取消。")

        cmd = await asyncio.get_event_loop().run_in_executor(None, sys.stdin.readline)
        cmd = cmd.strip().lower()
        if cmd == "cancel":
            return []
        if cmd == "r":
            return await self._break_down(user_request)

        init_tasks_dir(os.getcwd())
        cards = []
        for item in items:
            card = create_task(
                title=item.get("title", "未命名任务"),
                description=item.get("description", ""),
            )
            cards.append(card)
        return cards

    def _parse_breakdown(self, raw: str) -> list[dict]:
        """从 LLM 回复中解析任务 JSON 数组。"""
        try:
            json_str = raw
            if "```json" in raw:
                json_str = raw.split("```json")[1].split("```")[0].strip()
            elif "```" in raw:
                json_str = raw.split("```")[1].split("```")[0].strip()
            start = json_str.index("[")
            end = json_str.rindex("]") + 1
            return json.loads(json_str[start:end])
        except (json.JSONDecodeError, ValueError):
            return []

    async def _execute_task(self, card: dict) -> bool:
        """为单个任务创建 Butler+Worker 对并执行。"""
        task_dir = os.path.join(os.getcwd(), "tasks", "work", f"task_{card['id']}")
        os.makedirs(task_dir, exist_ok=True)

        bus = CorrectionBus()
        ctrl = SessionController()

        worker_schemas, worker_handlers = make_tools([task_dir])
        _, butler_handlers = make_tools([task_dir])

        cfg = SessionConfig(
            task=card["description"],
            project_root=task_dir,
            worker_subdirs=[],
            butler_model=self.cfg.butler_model,
            worker_model=self.cfg.worker_model,
            planner_model=self.cfg.planner_model,
            tool_schemas=worker_schemas + [FINISH_TASK_SCHEMA],
        )

        butler = ButlerAgent(cfg, bus, butler_handlers, ctrl)
        worker = WorkerAgent(cfg, bus, worker_handlers, ctrl)

        try:
            await worker.run(card["description"])
            return not ctrl.is_stopped
        except Exception as e:
            display.error_msg("Planner", f"任务 #{card['id']} 执行异常: {e}")
            return False

    async def chat_direct(self, user_input: str) -> str:
        """用户直接与 Planner 对话。"""
        self.messages.append({"role": "user", "content": f"[USER] {user_input}"})
        try:
            resp = await chat(self.cfg.planner_model, self.messages)
        except Exception as e:
            return f"[Planner 错误] {e}"
        self.messages.append(resp)
        return resp.get("content", "")
