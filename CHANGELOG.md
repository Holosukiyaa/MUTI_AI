# Changelog

## v0.5.1 — 2026-07-02

### 功能新增

#### Squad 流式输出与工具调用提示（`core/llm/anthropic_provider.py`）

- Anthropic SDK 调用路径新增 `on_token` 回调，支持流式逐字输出
- 调用工具时向前端推送 `[正在调用工具: xxx...]` 提示，执行过程更透明

#### 执行者 Director 实时监控（`core/director/director.py`、`core/squad/squad.py`）

- 新增 `DirectorAgent.monitor()`：执行者 Director 定期查看 Squad 状态并生成简短进度报告
- Squad 运行时每 20 秒触发一次监控回调，向前端推送 `director_report` 与 `session_line` 事件
- 新增 `session_progress` 事件，Worker 启动即上报初始进度

#### Squad 继续执行（`core/squad/squad.py`、`server/main.py`）

- 新增 `Squad.continue_run()`：Squad 完成或中断后可携带用户补充要求重新启动
- 新增接口 `POST /api/groups/{group_id}/squads/{name}/continue` 及默认组兼容路由

#### 新增服务端接口（`server/main.py`）

- `GET /api/groups/{group_id}/squads/{name}/log`：读取 Squad 运行日志
- `GET /api/groups/{group_id}/tree`：返回项目组文件树（最多 6 层）
- Director 创建支持自动去重命名（`_unique_director_name`），名称为空时回退为 `Director`

### 优化

- 验收总结提示词改为 3-5 条 bullet，限制在 300 字以内，避免冗长报告
- Squad 配置写入完整 `task` 与 `log_path`，加载时可正确恢复日志路径
- `_build_report` 改为列出交付物文件并给出本地运行建议
- `SessionController` 新增 `clear_error()`，Squad 重启时自动清除错误状态
- 修正多个源文件的 BOM / 编码问题

### 前端

- `web/` 界面重写与交互优化（App.jsx / components.jsx / themes.js / index.css）
- 新增文件树、Squad 日志查看、继续执行等界面能力

## v0.5.0 — 2026-07-01

### 架构重构

#### 新增：四层分层架构（`core/`）

将原来结构混乱的 `core/` 目录重组为严格单向依赖的四层结构：

```
第0层  config.py       全局配置
第1层  infra/          基础设施（bus / session / token_tracker / tools）
第2层  llm/            LLM 抽象
第3层  agents/         执行 Agent（mentor / worker / handover）
       director/       对话 Agent
第4层  squad/          编排层
```

#### 新增：`core/infra/` 包

将原 `core/runtime/`（bus、session、token_tracker）和 `core/tools/`（filesystem + registry）合并重组为 `core/infra/`，单文件按职责命名：

- `infra/bus.py` — CorrectionBus + WorkerSnapshot + ProgressState
- `infra/session.py` — SessionController 状态机
- `infra/token_tracker.py` — Token 用量追踪器
- `infra/tools.py` — 沙箱化文件工具（read / write / append / list）

#### 新增：`core/director/` — Director 角色系统

用 `DirectorAgent` 取代旧版单一 `PlannerAgent`，支持四种角色：

| 角色 | 职责 |
|------|------|
| `executor`（项目执行者）| 与用户对话，创建 Squad 执行 |
| `architect`（蓝图规划师）| 深度需求分析，生成结构化蓝图文档 |
| `manager`（项目管理员）| 归档文件，管理蓝图版本 |
| `custom`（自定义）| 用户自定义系统提示词 |

**蓝图工作流**：`architect` Director 调用 `save_blueprint` 将蓝图保存到 `blueprints/` 目录；`executor` Director 启动时自动读取蓝图列表，基于蓝图指导 Squad 执行。

#### 新增：`core/agents/handover.py` — 交接大纲生成器

支持 `RollingStrategy` 角色轮换时由 Mentor 生成结构化任务交接大纲（`handover.md`），格式包含：已完成工作、进行中任务、待完成项、重要约束、已知问题。

### 功能新增

#### `RollingStrategy` — 智能角色轮换

Worker token 消耗达到阈值（默认 176K 输入 / 24K 输出）时自动触发无损轮换：

1. 当前 Mentor 生成交接大纲
2. 旧 Worker 停止，旧 Mentor 晋升为新 Worker（携带完整上下文）
3. 召唤新 Mentor 预热后接管监督
4. TokenTracker 重置，新一代继续任务

优势：不压缩历史、不丢失信息，支持任意长度任务。

#### Group 项目组管理

新增 Group 概念，将 Director 和 Squad 按项目组隔离：

```
.data/groups/{group_id}/
    ├── directors/       # Director 对话历史
    ├── squads/          # Squad 数据
    └── blueprints/      # 蓝图文档
```

API 全面升级为 `/api/groups/{group_id}/directors/...` 和 `/api/groups/{group_id}/squads/...`，保留旧路由兼容。

#### `display/` 注入式架构

移除 `display/__init__.py` 对 `server.main` 的硬编码依赖，改为注入回调模式：

```python
# server/main.py 启动时注入
display.register_push_handler(push_event)

# 替换前端只需替换 handler，core/ 无需任何修改
display.register_push_handler(my_new_frontend.send)
```

#### Director 验收机制

Squad 完成后，Director 自动对输出文件进行 LLM 验收并生成验收报告，推送到前端展示。

### 代码清理

#### 删除遗留代码（共 15+ 个文件）

| 文件 | 替代 |
|------|------|
| `core/bus.py` | `core/infra/bus.py` |
| `core/session.py` | `core/infra/session.py` |
| `core/partner_session.py` | `core/squad/` |
| `core/planner.py` | `core/director/` |
| `core/planner/planner.py` | `core/director/director.py` |
| `core/runtime/` 整包 | `core/infra/` |
| `core/tools/` 整包 | `core/infra/tools.py` |
| `core/agents/butler.py` | `core/agents/mentor.py` |
| `core/agents/planner.py` | `core/director/director.py` |
| `display/terminal.py` | `display/__init__.py`（Web 模式） |
| `display/app.py` | Web 前端替代 TUI |
| `display/welcome.py` | Web 前端替代 TUI |
| `display/planner_ui.py` | Web 前端替代 TUI |
| `display/squad_ui.py` | Web 前端替代 TUI |
| `display/partner_ui.py` | 已废弃 |
| `core/squad/session.py` (TUI) | 已废弃 |
| `core/tools/task_cards.py` | 已废弃（无调用者） |

#### 删除无用字段

- 移除 `SessionConfig.planner_model`（无任何调用者）

### 文档

- 全面重写 `devtools/DEVELOPMENT.md`，反映新架构和全部模块变更

---

## v0.4.0

- 架构重构 + 多项 Bug 修复（见 v0.4.0 提交记录）

## v0.3.0

- 初始发布

