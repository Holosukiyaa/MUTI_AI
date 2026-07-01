# Echelon AI — 开发文档

## 目录

1. [项目概述](#项目概述)
2. [技术栈](#技术栈)
3. [项目结构](#项目结构)
4. [架构设计](#架构设计)
5. [核心模块详解](#核心模块详解)
6. [API 接口文档](#api-接口文档)
7. [前端开发指南](#前端开发指南)
8. [数据存储](#数据存储)
9. [开发环境搭建](#开发环境搭建)
10. [调试技巧](#调试技巧)
11. [扩展指南](#扩展指南)
12. [常见问题](#常见问题)

---

## 项目概述

Echelon AI 是一个多智能体协作框架，采用 **Director → Squad（Mentor × Worker）** 分层架构：

- **Director（导演）**：直接与用户对话，理解需求，将任务拆解并分配给 Squad。支持四种角色：`executor`（项目执行者）、`architect`（蓝图规划师）、`manager`（项目管理员）、`custom`（自定义）。
- **Mentor（导师）**：持有设计蓝图（blueprint），是知识的唯一来源；监督 Worker 的工作，必要时纠正或回滚。
- **Worker（工人）**：从零开始执行任务，通过 `ask_mentor` 向 Mentor 获取信息，使用文件工具编写代码。

一个 Squad = 一个 Mentor + 一个 Worker（由 SquadStrategy 决定，默认 `RollingStrategy` 支持 token 阈值触发角色轮换）。Director 可以同时创建多个 Squad 并行执行不同子任务。

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Python 3.12+ / FastAPI | 异步 Web 框架，提供 REST + SSE + WebSocket |
| LLM | OpenAI 兼容 API（DeepSeek）/ Anthropic Claude | 通过 `core/llm/` 抽象，运行时按 `AI_PROVIDER` 切换 |
| 前端 | React 19 + Vite 8 | SPA，内联样式，无 CSS 框架依赖 |
| 实时通信 | SSE（流式对话）+ WebSocket（Squad 进度）| |
| 代码质量 | oxlint（前端）| |

---

## 项目结构

```
MUTI_AI-main/
├── .data/                              # 用户数据（已 gitignore）
│   └── groups/
│       └── {group_id}/
│           ├── meta.json               # 组元信息（名称、描述）
│           ├── blueprints/             # 蓝图规划师保存的蓝图文档
│           ├── directors/
│           │   └── {name}/
│           │       ├── meta.json       # Director 元信息（名称、角色等）
│           │       ├── history.json    # Director 对话历史
│           │       └── logs/           # Squad 运行日志
│           └── squads/
│               └── {name}/
│                   ├── config.json     # Squad 配置
│                   ├── mentor/
│                   │   ├── blueprint.md    # Mentor 私有蓝图
│                   │   ├── history.json    # Mentor 对话历史
│                   │   └── handover.md     # RollingStrategy 交接大纲
│                   └── worker/
│                       ├── history.json    # Worker 对话历史
│                       └── *               # Worker 生成的文件
├── core/
│   ├── config.py                       # 第0层：全局数据结构
│   ├── infra/                          # 第1层：基础设施（无 LLM）
│   │   ├── bus.py                      # CorrectionBus + WorkerSnapshot + ProgressState
│   │   ├── session.py                  # SessionController（暂停/恢复/停止）
│   │   ├── token_tracker.py            # Token 用量追踪器
│   │   └── tools.py                    # 文件系统工具（read/write/append/list）
│   ├── llm/                            # 第2层：LLM 抽象
│   │   ├── __init__.py                 # chat() 统一入口
│   │   ├── base.py                     # 路由到 provider
│   │   ├── openai_provider.py          # OpenAI 兼容实现（含流式）
│   │   └── anthropic_provider.py       # Anthropic Claude 实现
│   ├── agents/                         # 第3层：执行 Agent
│   │   ├── base.py                     # BaseAgent 抽象基类
│   │   ├── mentor.py                   # MentorAgent
│   │   ├── worker.py                   # WorkerAgent
│   │   └── handover.py                 # 任务交接大纲生成器
│   ├── director/                       # 第3层：对话 Agent
│   │   ├── __init__.py
│   │   └── director.py                 # DirectorAgent（四种角色）
│   └── squad/                          # 第4层：编排层
│       ├── __init__.py
│       ├── squad.py                    # Squad 生命周期编排
│       ├── registry.py                 # SquadRegistry 全局注册表
│       └── strategy.py                 # SquadStrategy 可插拔策略
├── display/
│   └── __init__.py                     # 事件推送适配器（注入式回调）
├── server/
│   └── main.py                         # FastAPI 后端（REST + SSE + WebSocket）
├── web/                                # React 前端
│   ├── src/
│   │   ├── main.jsx
│   │   ├── App.jsx                     # 主应用（布局、状态管理、主题切换）
│   │   ├── api.js                      # API 客户端 + SSE 流 + WebSocket
│   │   ├── themes.js                   # 三套主题配置（dark/light/midnight）
│   │   ├── components.jsx              # 通用组件
│   │   └── index.css                   # 全局样式 + 动画关键帧
│   ├── dist/                           # 构建产物（Vite 生成）
│   ├── vite.config.js
│   └── package.json
├── devtools/
│   ├── check_env.py                    # 环境检测脚本
│   ├── install_deps.py                 # 一键安装依赖
│   └── DEVELOPMENT.md                  # 本文档
├── .env                                # API 密钥（已 gitignore）
├── .env.example
├── launch.py                           # 启动脚本
└── run.bat                             # Windows 一键启动
```

---

## 架构设计

### 分层依赖关系

```
第0层  config.py          全局数据结构，所有层共用
第1层  infra/             基础设施：bus / session / token_tracker / tools
                          不依赖任何内部模块
第2层  llm/               LLM 抽象，仅依赖 config
第3层  agents/ director/  执行和对话 Agent，依赖 infra + llm
第4层  squad/             编排层，依赖 agents + infra
接入层 server/main.py     FastAPI，依赖 squad + director
适配层 display/           事件推送适配器，由 server 启动时注入回调
```

**依赖方向严格单向，上层依赖下层，下层不知道上层的存在。**

### 整体数据流

```
用户浏览器
  │
  │  SSE（流式文本）
  ▼
server/main.py ──► DirectorAgent.chat()
  │
  │  assign_to_squad 工具调用
  ▼
SquadRegistry.create() → Squad.start()
  │
  │  strategy.build()
  ├──► MentorAgent（被动，监听快照）
  └──► WorkerAgent（主动，执行循环）
          │
          │  每轮：publish_snapshot → Mentor 评估 → 纠正注入
          ▼
       CorrectionBus（bus.py）
          │
          │  进度推送
          ▼
       display/__init__.py → push_handler（server.push_event）
          │
          │  WebSocket
          ▼
       用户浏览器（Squad 日志面板）
```

### Director 角色系统

| 角色 | 可用工具 | 职责 |
|------|---------|------|
| `executor`（项目执行者）| `assign_to_squad` | 理解需求，创建 Squad 执行 |
| `architect`（蓝图规划师）| `save_blueprint` | 深度需求分析，生成结构化蓝图 |
| `manager`（项目管理员）| `save_blueprint` | 归档文件，管理蓝图版本 |
| `custom`（自定义）| 两个工具都有 | 自定义系统提示词 |

**蓝图工作流（推荐双 Director 协作）**：
1. 创建 `architect` Director → 与用户深度讨论 → 调用 `save_blueprint` 保存到 `blueprints/`
2. 创建 `executor` Director → 自动读取蓝图列表 → 基于蓝图创建 Squad

### CorrectionBus 机制

`CorrectionBus` 是 Mentor 和 Worker 之间的异步通信管道：

- **Worker → Mentor**：`publish_snapshot()` — 每轮结束后发布 WorkerSnapshot，触发 Mentor 评估
- **Mentor → Worker（轻微）**：`inject_correction()` — 下一轮开头以 `[MENTOR CORRECTION]` 注入
- **Mentor → Worker（严重）**：`inject_rollback()` — 回滚文件到快照状态，恢复消息上下文
- **进度**：`update_progress()` — Mentor 评估后推送 ProgressState

### RollingStrategy 角色轮换

当 Worker 的 token 消耗达到阈值（默认 176K 输入 / 24K 输出）时自动触发：

```
1. 当前 Mentor 生成结构化交接大纲（agents/handover.py → mentor_dir/handover.md）
2. 旧 Worker 停止，旧 Mentor 晋升为新 Worker（携带大纲作为初始上下文）
3. 召唤新 Mentor，读取大纲后预热就绪
4. TokenTracker 重置，新一代继续任务
```

优势：不压缩、不丢信息，晋升的 Mentor 本来就了解全局状态。

---

## 核心模块详解

### core/config.py

```python
@dataclass
class ModelConfig:
    provider: Literal["openai", "anthropic", "claude"]
    model: str                     # 如 "deepseek-chat"
    api_key: str
    base_url: str | None = None    # 如 "https://api.deepseek.com"
    temperature: float = 0.7
    max_tokens: int = 8192

@dataclass
class SessionConfig:
    task: str
    project_root: str
    worker_subdirs: list[str]      # Worker 可写的子目录
    mentor_model: ModelConfig
    worker_model: ModelConfig
    max_rounds: int = 20
    mentor_system: str             # Mentor 系统提示词
    worker_system: str             # Worker 系统提示词
    tool_schemas: list[dict]       # 可用工具的 JSON Schema
```

### core/infra/ — 基础设施层

**bus.py — CorrectionBus**

```python
bus = CorrectionBus()
bus.on_snapshot(mentor._on_worker_snapshot)  # 注册 Mentor 回调
bus.on_progress(lambda state: ...)           # 注册进度回调

# Worker 每轮调用
await bus.publish_snapshot(WorkerSnapshot(...))

# Mentor 在回调中调用
await bus.inject_correction("...")   # 轻微纠正
await bus.inject_rollback(snapshot, reason)  # 严重错误，回滚

# Worker 在每轮开始前调用
corrections = bus.drain_corrections()
rollback = bus.drain_rollback()
```

**session.py — SessionController**

状态机：`RUNNING` → `PAUSED` / `STOPPED` / `ERROR`

```python
ctrl = SessionController()
ctrl.pause("worker")   # 精确暂停某个角色
ctrl.resume()
ctrl.stop()
ctrl.set_error("msg")

# Worker 每轮开始前等待
await ctrl.wait_resume()
if ctrl.is_stopped:
    break
```

**token_tracker.py — TokenTracker**

```python
tracker = TokenTracker(input_limit=176_000, output_limit=24_000)
tracker.on_threshold(lambda t: ...)   # 注册阈值回调（只触发一次）
tracker.record("worker_g0", inp=1000, out=200)  # LLM 调用后记录
tracker.reset_threshold()              # 角色轮换后重置
tracker.to_dict()                      # 供前端展示的序列化格式
```

**tools.py — 工具系统**

四个沙箱化文件工具（Worker 可用）：

| 工具 | 说明 |
|------|------|
| `read_file(path)` | 读取文件内容 |
| `write_file(path, content)` | 写入文件（覆盖） |
| `append_file(path, content)` | 追加内容（大文件分块写入） |
| `list_dir(path)` | 列出目录 |

所有路径经 `_resolve_safe()` 校验，禁止访问 `allowed_roots` 以外的目录。

```python
schemas, handlers = make_tools([worker_dir])
result = execute_tool("write_file", {"path": "x.py", "content": "..."}, handlers)
```

### core/llm/ — LLM 抽象层

```
chat(cfg, messages, tools?, on_token?, on_usage?) → dict
  ├── provider="openai"              → _openai_chat()     # 含流式累积
  └── provider="anthropic"/"claude" → _anthropic_chat()  # 工具调用转换
```

`on_token(str)` — 每个流式 token 的回调，用于 SSE 推送。
`on_usage(input_tokens, output_tokens)` — 调用完成后的 token 统计回调。

### core/agents/ — Agent 层

**base.py — BaseAgent（抽象契约）**

```python
class BaseAgent(ABC):
    @abstractmethod
    async def run(self, task: str) -> None: ...     # 主执行入口
    @abstractmethod
    async def chat_direct(self, user_input: str) -> str: ...  # 暂停时直接对话
```

**worker.py — WorkerAgent 执行循环**

```
for each round (最多 max_rounds):
  1. wait_resume()              # 支持暂停/恢复
  2. _maybe_compress()          # 历史超 30 条时用 LLM 摘要压缩
  3. drain rollback / corrections
  4. _repair_messages()         # 修复孤立 tool_calls，防止 API 400
  5. chat() → response
  6. 处理 tool_calls:
     - finish_task  → 发布最终快照后返回
     - ask_mentor   → 调用 mentor.answer_question()
     - 其他工具    → execute_tool()
  7. publish_snapshot()         # 等 Mentor 评估（阻塞点）
  8. _save()                    # 持久化历史
```

**mentor.py — MentorAgent（被动驱动）**

- 注册 `bus.on_snapshot()`，每轮 Worker 完成后自动收到快照
- LLM 评估返回：`OK` / `CORRECT: <fix>` / `ROLLBACK: <reason>`
- 独立的 `_update_progress()` — 返回 JSON 格式进度，失败不影响主评估
- `answer_question(question)` — 响应 Worker 的 `ask_mentor` 工具调用
- `run()` 为空实现——Mentor 是被动驱动的，不需要主循环

**handover.py — 交接大纲生成器**

由 `RollingStrategy` 在 token 阈值触发时调用：

```python
handover = await generate_handover(
    task=cfg.task,
    worker_messages=mentor._last_worker_messages,
    model=cfg.mentor_model,
    save_path=os.path.join(mentor_dir, "handover.md"),
)
```

大纲格式固定（已完成/进行中/待完成/重要约束/已知问题），确保新 Mentor 可靠解析。

### core/director/ — Director 对话层

**director.py — DirectorAgent**

- 维护对话历史，持久化到 `history.json`
- `chat(user_input, on_token)` — 流式对话
- `handle_save_blueprint(tc)` — 处理 `save_blueprint` 工具调用，写入 `blueprints/` 目录
- `accept(task, file_list)` — 对 Squad 完成的任务进行 LLM 验收，返回验收报告
- 启动时若 `blueprints/` 目录存在蓝图文件，自动在系统提示词中附加文件列表

### core/squad/ — 编排层

**squad.py — Squad 生命周期**

```python
# 创建（初始化目录、写蓝图、清除旧历史）
squad = Squad.create(name, task, blueprint, squads_dir, log_dir)

# 从磁盘恢复（进程重启后重建列表）
squad = Squad.load(squads_dir, name)

# 异步启动（立即返回，后台运行）
await squad.start(model, push_event_fn, accept_fn=director.accept)

# 停止
squad.stop()

# 序列化（供 API 返回）
squad.to_dict()  # {"name", "task", "status", "progress", "report", "error"}
```

**strategy.py — SquadStrategy**

```python
class SquadStrategy(ABC):
    @abstractmethod
    async def build(cfg, bus, ctrl, mentor_dir, worker_dir, tracker) -> (mentors, workers): ...

# 内置策略
SinglePairStrategy   # 1 Mentor + 1 Worker，无轮换
RollingStrategy      # 智能轮换（默认），token 达阈值时自动切换
```

### display/ — 事件推送适配器

`display/__init__.py` 是核心代码和前端之间的解耦层：

```python
# server/main.py 启动时注入
import display
display.register_push_handler(push_event)

# 以后换任意前端只需替换 handler
display.register_push_handler(my_new_frontend.send)
```

**Squad 上下文机制**：`_push()` 通过 `contextvars` 自动附加当前 Squad 名，多 Squad 并行时日志不会串台。

```python
display.set_squad_name("my_squad")
# 之后所有事件自动带 {"squad": "my_squad"}
```

关键函数：

| 函数 | 事件 type | 用途 |
|------|-----------|------|
| `register_push_handler(fn)` | — | 注入推送回调 |
| `set_squad_name(name)` | — | 设置 Squad 上下文 |
| `worker_header(round)` | session_line | 轮次标题 |
| `worker_tool_call(name, args)` | session_line | 工具调用 |
| `mentor_ok(round)` | session_line | Mentor 审查通过 |
| `mentor_interrupt(round, msg)` | session_line | Mentor 纠正介入 |
| `error_msg(who, err)` | session_line | 错误信息 |
| `update_progress_bar(%, status)` | session_progress | 进度推送 |
| `set_log_path(path)` | — | 开启文件日志 |

---

## API 接口文档

### Group（项目组）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/groups` | 列出所有项目组 |
| POST | `/api/groups` | 创建组 `{id, name, description}` |
| DELETE | `/api/groups/{group_id}` | 删除组 |
| GET | `/api/groups/{group_id}/open` | 打开组目录 |

### Director

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/groups/{group_id}/directors` | 列出组内所有 Director |
| POST | `/api/groups/{group_id}/directors` | 创建 Director `{name, description, role, icon, custom_system}` |
| DELETE | `/api/groups/{group_id}/directors/{name}` | 删除 |
| GET | `/api/groups/{group_id}/directors/{name}/history` | 获取对话历史 |
| POST | `/api/groups/{group_id}/directors/{name}/chat/stream` | 发送消息（SSE 流式）`{message}` |
| GET | `/api/groups/{group_id}/directors/{name}/open` | 打开目录 |

*兼容旧路由 `/api/planners/...` 指向 default 组。*

### Squad

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/groups/{group_id}/squads` | 列出组内所有 Squad（含状态）|
| GET | `/api/groups/{group_id}/squads/{name}` | 查询单个 Squad |
| DELETE | `/api/groups/{group_id}/squads/{name}` | 删除 |
| POST | `/api/groups/{group_id}/squads/{name}/stop` | 停止运行中的 Squad |
| GET | `/api/groups/{group_id}/squads/{name}/open` | 打开目录 |

*兼容旧路由 `/api/squads/...` 指向 default 组。*

### Settings

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取当前配置（provider、key preview、model）|
| POST | `/api/settings/provider` | 设置 provider `{provider, api_key, base_url, model}` |
| POST | `/api/settings/apikey` | 兼容旧接口，仅设置 openai key |
| POST | `/api/open-folder` | 打开任意目录 `{path}` |
| WebSocket | `/ws` | 实时事件推送 |

### SSE 流式格式（Director 对话）

```
data: {"token": "Hello"}
data: {"token": " world"}
data: {"done": true, "squads": [{"squad": "snake_game", "task": "..."}], "blueprints": [...]}
data: {"error": "API Key 无效，请在设置中更新"}
```

`done` 事件包含本轮启动的 Squad 列表和保存的蓝图列表。`error` 表示 LLM 调用失败。

### WebSocket 事件格式

```json
{"type": "session_line",     "line": "⚙ 写入文件  index.html",  "squad": "snake_game"}
{"type": "session_progress", "percent": 45.0, "status": "第2/5步: 编写核心逻辑", "squad": "snake_game"}
{"type": "session_done",     "squad": "snake_game", "status": "ok",    "report": "验收报告..."}
{"type": "session_done",     "squad": "snake_game", "status": "error", "report": "错误详情..."}
{"type": "token_update",     "squad": "snake_game", "input": 12000, "output": 3000, "input_percent": 6.8, ...}
```

`token_update` 在每次进度更新时推送 Token 用量统计（供前端显示进度条）。

---

## 前端开发指南

### 主题系统

`themes.js` 导出三套主题，通过 `ThemeCtx` Context 在组件树传递：

```javascript
const THEMES = {
  dark:     { accent: "#a1a1aa", ... },
  light:    { accent: "#71717a", ... },
  midnight: { accent: "#94a3b8", ... },
};
```

**添加新主题**：在 `themes.js` 中添加新 key，在 `App.jsx` 的 `cycleTheme` 中加入轮换列表。

### 样式约定

- 全部使用内联样式（`style={{...}}`），无 CSS 框架
- 颜色统一引用 `C.xxx`，不硬编码色值
- 特殊语义色（错误红 `#ef4444`、警告黄 `#f59e0b`）允许硬编码
- 动画定义在 `index.css` 的 `@keyframes` 中

### 构建命令

```bash
cd web
npm install
npm run dev      # 开发服务器 (port 5173，含热更新)
npm run build    # 构建到 web/dist/
npm run lint     # oxlint 检查
```

---

## 数据存储

```
.data/
└── groups/
    └── {group_id}/
        ├── meta.json                   # {"id": "...", "name": "...", "description": "..."}
        ├── blueprints/
        │   └── *.md                    # 蓝图规划师生成的蓝图文档
        ├── directors/
        │   └── {name}/
        │       ├── meta.json           # {"name", "description", "role", "icon", "custom_system"}
        │       ├── history.json        # Director 完整对话历史（OpenAI Messages 格式）
        │       └── logs/
        │           └── {squad}.log     # Squad 运行日志（时间戳 + 每行事件）
        └── squads/
            └── {name}/
                ├── config.json         # {"name": "...", "description": "..."}
                ├── mentor/
                │   ├── blueprint.md    # Mentor 私有蓝图（Director 写入）
                │   ├── history.json    # Mentor 对话历史（或 history_g{n}.json）
                │   └── handover.md     # RollingStrategy 生成的交接大纲
                └── worker/
                    ├── history.json    # Worker 对话历史（或 history_g{n}.json）
                    └── *               # Worker 生成的所有文件
```

RollingStrategy 每代使用 `history_g{n}.json`（n=0,1,2,...），保留所有代的历史便于回溯。

---

## 开发环境搭建

### 前置要求

- Python 3.12+
- Node.js 18+
- npm

### 一键安装

```bash
python devtools/check_env.py     # 检测环境
python devtools/install_deps.py  # 安装所有依赖（Python + 前端）
```

### 手动安装

```bash
pip install fastapi "uvicorn[standard]" openai anthropic

cd web && npm install && cd ..

cp .env.example .env
# 编辑 .env，填入 API Key
```

### 启动

```bash
# Windows 一键启动
run.bat

# 手动启动（前后端分离，前端热更新）
python launch.py

# 前端: http://localhost:5173
# 后端: http://localhost:8765
```

### 配置 LLM Provider

编辑 `.env` 或在前端设置面板中配置：

```env
# DeepSeek（默认，OpenAI 兼容）
AI_PROVIDER=openai
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# Anthropic Claude
AI_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-xxx
CLAUDE_MODEL=claude-opus-4-5
```

---

## 调试技巧

### 查看 Squad 运行日志

日志存储在 `.data/groups/{group_id}/directors/{name}/logs/{squad}.log`：

```
[14:30:01] 🚀 Squad [snake_game] 已启动
[14:30:01] 📋 任务：写一个贪吃蛇游戏
[14:30:05]   ⚙ 写入文件  index.html
[14:30:05]   └ Written 1234 chars to ...
[14:30:08]   ✓ Mentor 审查第 1 轮：通过
```

### 查看 Agent 对话历史

```
.data/groups/default/directors/{name}/history.json      # Director 历史
.data/groups/default/squads/{name}/mentor/history.json  # Mentor 历史
.data/groups/default/squads/{name}/worker/history.json  # Worker 历史
```

历史格式为 OpenAI Messages 格式：`[{"role": "system/user/assistant/tool", "content": "..."}]`

### 常见错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `insufficient tool messages following tool_calls` | 历史中有孤立 tool_calls | Worker 内置 `_repair_messages()` 自动修复；仍报错则删除对应 `history.json` |
| 前端显示"API Key 无效" | API Key 未配置或已失效 | 在前端设置面板更新 Key 或编辑 `.env` |
| 前端显示"请求频率超限" | DeepSeek 限流（429） | 稍等后重试 |
| Squad 日志一直显示"等待启动" | WebSocket 未连接 | 刷新页面重连；查看后端控制台是否有异常 |
| 进度一直 0% | Mentor 进度评估 JSON 解析失败 | 查看 Squad 日志确认 Mentor 是否正常运行 |
| `PermissionError: Path outside allowed directories` | Worker 尝试写入非授权目录 | 正常安全拦截，Worker 应只写 `worker/` 目录 |
| `No module named 'core.runtime'` | 代码引用了旧模块路径 | 已迁移到 `core.infra`，更新 import 路径 |

---

## 扩展指南

### 添加新工具

在 `core/infra/tools.py` 中：

1. 在 `_make_file_handlers()` 中添加新函数
2. 在 `_TOOL_SCHEMAS` 中添加对应 JSON Schema

```python
def delete_file(path: str) -> str:
    p = _resolve_safe(path, allowed_roots)
    p.unlink()
    return f"Deleted {p}"
```

### 添加新 Agent 类型

```python
# core/agents/my_agent.py
class MyAgent(BaseAgent):
    async def run(self, task: str) -> None:
        # 实现主循环
        ...
    async def chat_direct(self, user_input: str) -> str:
        ...
```

### 添加新 Squad 策略

```python
# core/squad/strategy.py
class MultiPairStrategy(SquadStrategy):
    @property
    def name(self): return "multi_pair"

    async def build(self, cfg, bus, ctrl, mentor_dir, worker_dir, tracker=None):
        # 实例化 N 个 Mentor 和 N 个 Worker
        mentor1 = MentorAgent(cfg=cfg, bus=bus, ...)
        worker1 = WorkerAgent(cfg=cfg, bus=bus, ...)
        return [mentor1], [worker1]
```

### 替换前端

只需实现一个接收 `event: dict` 的函数并注入：

```python
# 任意启动入口
import display

def my_frontend_push(event: dict):
    # gRPC / Electron IPC / CLI 输出 / 等
    my_transport.send(event)

display.register_push_handler(my_frontend_push)
```

`core/` 和 `display/` 完全不需要修改。

### 切换 LLM 模型

修改 `server/main.py` 中的 `_make_model()` 函数，或通过前端设置面板动态切换。支持任何 OpenAI 兼容 API 端点。

---

## 常见问题

**Q: 如何给 Mentor 和 Worker 使用不同模型？**

修改 `squad.py` 的 `_run()` 中构建 `SessionConfig` 时分别指定 `mentor_model` 和 `worker_model`，或在 `server/main.py` 的 `_make_model()` 后分别创建两个 ModelConfig。

**Q: 如何自定义 Mentor/Worker 的系统提示词？**

修改 `core/squad/squad.py` 中的 `_MENTOR_SYSTEM_WITH_BLUEPRINT` 和 `_WORKER_SYSTEM` 常量。

**Q: 数据目录在哪？可以迁移吗？**

所有用户数据在 `.data/groups/` 下，每个项目组独立存储。可以直接复制目录迁移，进程重启时会自动扫描恢复。

**Q: 旧版 `.data/planners/` 和 `.data/squads/` 数据怎么办？**

服务启动时会自动迁移到 `.data/groups/default/`，只执行一次，旧目录不会删除。

**Q: RollingStrategy 和 SinglePairStrategy 怎么选？**

- 短任务（< 50 轮）：`SinglePairStrategy` 更简单
- 长任务、大型项目：`RollingStrategy`，token 耗尽后无缝继续，不丢失进度

**Q: 前端如何添加新页面/组件？**

1. 在 `web/src/components.jsx` 中创建组件
2. 在 `web/src/App.jsx` 中引入和使用
3. 全部使用内联样式 + `C` 主题对象，不引入 CSS 框架
