# Agents

`core/agents/` 提供两个内置 Agent。所有 Agent 共用 `core.config.SessionConfig` 和 `core.session.SessionController`，通过 `core.bus.CorrectionBus` 通信。

---

## WorkerAgent

专注执行单一任务的 Agent。拥有受限的文件系统视图（只能访问 `worker_subdirs`），通过工具读写文件。每轮生成完成后主动向 Butler 发布快照，等待审查结果再继续。

### 初始化

```python
from core.agents.worker import WorkerAgent

worker = WorkerAgent(
    cfg=cfg,                        # SessionConfig
    bus=bus,                        # CorrectionBus
    tool_handlers=worker_handlers,  # make_tools(allowed_roots)[1]
    ctrl=ctrl,                      # SessionController
    ask_butler_fn=butler.answer_question,  # 可选，注入后可使用 ask_butler 工具
)
```

### 运行

```python
await worker.run("你的任务描述")
```

任务描述中包含 `DONE` 时自动停止。

### ask_butler 工具

向 Worker 的 `tool_schemas` 中追加以下 schema，Worker 就能主动向 Butler 提问：

```python
ASK_BUTLER_SCHEMA = {
    "type": "function",
    "function": {
        "name": "ask_butler",
        "description": "向管家询问你不知道的设计信息",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
}
```

同时在创建 `WorkerAgent` 时传入 `ask_butler_fn=butler.answer_question`。

---

## ButlerAgent

全局监督 Agent。持有完整的项目上下文（`butler_system` 包含所有私有知识），每轮 Worker 完成后自动收到快照进行评估，发现问题时向 Worker 注入纠正消息。

### 初始化

```python
from core.agents.butler import ButlerAgent

butler = ButlerAgent(
    cfg=cfg,
    bus=bus,
    butler_tool_handlers=butler_handlers,  # make_tools([project_root])[1]
    ctrl=ctrl,
)
```

### 纠正协议

Butler 的评估回复遵循以下约定：

| 回复前缀 | 含义 | 行为 |
|---------|------|------|
| `OK` | 当前轮次正确 | 不干预 |
| `CORRECT:` | 发现问题 | 将后续内容注入 Worker 下一轮消息 |

在 `SessionConfig.butler_system` 中可以自定义评估标准和纠正触发条件。

### 私有知识注入

将 Butler 专有的背景信息（设计文档、规范、约束）写入 `butler_system`：

```python
cfg = SessionConfig(
    ...
    butler_system=f"""你是监督者，拥有以下私有信息：\n{private_docs}""",
)
```

Worker 的 `system` 不包含这些内容，只能通过 `ask_butler` 工具获取。

---

## 创建自定义 Agent

参照 `WorkerAgent` 结构创建新的 Agent 类：

1. 接收 `SessionConfig` 和 `SessionController`
2. 每轮调用前执行 `await ctrl.wait_resume()`，检查 `ctrl.is_stopped`
3. 捕获 LLM 异常后调用 `ctrl.set_error(msg)`
4. 调用 `bus.publish_snapshot()` 触发 Butler 审查（可选）
