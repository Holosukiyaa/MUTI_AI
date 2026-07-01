"""
core/agents/handover.py — 任务交接大纲生成器

当 Worker 的 token 消耗接近阈值时，由 Mentor 生成结构化交接大纲。
大纲用于：
  1. 新 Mentor 上任时快速了解任务全貌
  2. 晋升为 Worker 的前任 Mentor 作为初始上下文

设计原则：
  - 大纲由 Mentor 生成（监督视角，比 Worker 更客观准确）
  - 使用固定结构模板，而非自由文本，确保新 Mentor 可靠解析
  - 生成完成后写入磁盘（mentor_dir/handover.md），持久化备查
"""
import os
from core.config import ModelConfig
from core.llm import chat

_HANDOVER_PROMPT = """你是本次任务的 Mentor（监督者），现在需要生成一份结构化的任务交接大纲。

原始任务：
{task}

Worker 的完整执行历史（最近若干轮）：
{worker_context}

请生成以下格式的交接大纲（严格遵守格式，不要添加额外内容）：

# 任务交接大纲
## 原始任务
{task_placeholder}

## 已完成（含文件路径）
- [x] <已完成的工作，每项一行，说明文件路径和实现内容>

## 当前进行中
- [ ] <正在进行的工作，说明完成度百分比>

## 待完成
- [ ] <尚未开始的工作>

## 重要约束（Mentor 纠正记录）
- <所有已发出的 CORRECT / ROLLBACK 指令摘要，新 Worker 必须遵守>

## 已知问题
- <已发现但未完全解决的问题，无则写"无">

---
大纲结束。新 Worker 必须先阅读完整大纲，再通过 ask_mentor 获取更多细节。"""


async def generate_handover(
    task: str,
    worker_messages: list[dict],
    model: ModelConfig,
    save_path: str | None = None,
) -> str:
    """
    由 Mentor 根据 Worker 的历史消息生成结构化交接大纲。

    Args:
        task: 原始任务描述
        worker_messages: Worker 的完整对话历史
        model: 使用的模型配置（通常用 Mentor 的模型）
        save_path: 大纲保存路径（如 mentor_dir/handover.md）

    Returns:
        大纲文本
    """
    visible = [m for m in worker_messages if m.get("role") != "system"]

    anchor_tags = ["[MENTOR CORRECTION]", "[MENTOR ROLLBACK]", "finish_task"]
    anchor_lines = []
    normal_lines = []

    for m in visible:
        content = str(m.get("content") or "")
        role = m.get("role", "")
        line = f"[{role.upper()}]: {content[:300]}"
        if any(tag in content for tag in anchor_tags):
            anchor_lines.append(line)
        else:
            normal_lines.append(line)

    budget = 8000
    selected_normal = []
    for line in reversed(normal_lines):
        if budget - len(line) < 0:
            break
        selected_normal.insert(0, line)
        budget -= len(line)

    worker_context = "\n".join(anchor_lines + selected_normal)

    prompt = _HANDOVER_PROMPT.format(
        task=task[:500],
        worker_context=worker_context,
        task_placeholder=task[:500],
    )

    try:
        response = await chat(
            model,
            [{"role": "user", "content": prompt}],
            None,
        )
        handover = response.get("content", "").strip()
    except Exception as e:
        handover = f"# 任务交接大纲\n## 原始任务\n{task}\n\n## 备注\n大纲自动生成失败：{e}\n请通过 ask_mentor 获取详情。"

    if save_path:
        try:
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(handover)
        except Exception:
            pass

    return handover
