# Agents

`core/agents/` 提供两个内置 Agent。所有 Agent 共用 `core.config.SessionConfig` 和 `core.runtime.session.SessionController`，通过 `core.runtime.bus.CorrectionBus` 通信。

---

## WorkerAgent

专注执行单一任务的 Agent。拥有受限的文件系统视图（只能访问 `worker_subdirs`），通过工具读写文件。每轮生成完成后主动向 Mentor 发布快照，等待审查结果再继续。

### 初始化

```python
from core.agents.worker import WorkerAgent

worker = WorkerAgent(
    cfg=cfg,                        # SessionConfig
    bus=bus,                        # CorrectionBus
    tool_handlers=worker_handlers,  # make_tools(allowed_roots)[1]
    ctrl=ctrl,                      # SessionController
    ask_mentor_fn=mentor.answer_question,  # 可选，注入后可使用 ask_mentor 工具
)
```

### 运行

```python
await worker.run("你的任务描述")
```

### ask_mentor 工具

向 Worker 的 `tool_schemas` 中追加以下 schema，Worker 就能主动向 Mentor 提问：

```python
ASK_MENTOR_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_mentor",
        "description": "向管家询问你不知道的设计信息",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
}
```

同时在创建 `WorkerAgent` 时传入 `ask_mentor_fn=mentor.answer_question`。

---

## MentorAgent

全局监督 Agent。持有完整的项目上下文（`mentor_system` 包含所有私有知识），每轮 Worker 完成后自动收到快照进行评估，发现问题时向 Worker 注入纠正消息。

### 初始化

```python
from core.agents.mentor import MentorAgent

mentor = MentorAgent(
    cfg=cfg,
    bus=bus,
    mentor_tool_handlers=mentor_handlers,  # make_tools([project_root])[1]
    ctrl=ctrl,
)
```

### 纠正协议

Mentor 的评估回复遵循以下约定：

| 回复前缀 | 含义 | 行为 |
|---------|------|------|
| `OK` | 当前轮次正确 | 不干预 |
| `CORRECT:` | 发现问题 | 将后续内容注入 Worker 下一轮消息 |
| `ROLLBACK:` | 严重错误 | 恢复文件到上一轮快照状态 |

在 `SessionConfig.mentor_system` 中可以自定义评估标准和纠正触发条件。

### 私有知识注入

将 Mentor 专有的背景信息（设计文档、规范、约束）写入 `mentor_system`：

```python
cfg = SessionConfig(
    ...
    mentor_system=f"""你是监督者，拥有以下私有信息：\n{private_docs}""",
)
```

Worker 的 `system` 不包含这些内容，只能通过 `ask_mentor` 工具获取。

---

## 创建自定义 Agent

参照 `WorkerAgent` 结构创建新的 Agent 类：

1. 继承 `BaseAgent`，实现 `run()` 和 `chat_direct()`
2. 每轮调用前执行 `await ctrl.wait_resume()`，检查 `ctrl.is_stopped`
3. 捕获 LLM 异常后调用 `ctrl.set_error(msg)`
4. 调用 `bus.publish_snapshot()` 触发 Mentor 审查（可选）
