# Echelon AI 开发文档

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
11. [常见问题](#常见问题)

---

## 项目概述

Echelon AI 是一个多智能体协作框架，采用 **Planner → Butler × Worker** 三层架构：

- **Planner（规划者）**：与用户对话，理解需求，将任务拆解并分配给 Partner
- **Butler（管家）**：持有设计蓝图（blueprint），是知识的唯一来源；监督 Worker 的工作，必要时纠正或回滚
- **Worker（工人）**：从零开始执行任务，通过 `ask_butler` 向 Butler 获取信息，使用 `write_file` / `read_file` 等工具编写代码

一个 Partner = 一个 Butler + 一个 Worker。Planner 可以同时创建多个 Partner 并行执行不同子任务。

---

## 技术栈

| 层级 | 技术 | 说明 |
|------|------|------|
| 后端 | Python 3.12+ / FastAPI | 异步 Web 框架，提供 REST + SSE + WebSocket |
| LLM | OpenAI 兼容 API（DeepSeek） | 通过 `core/llm/` 抽象，支持 OpenAI / Anthropic |
| 前端 | React 19 + Vite 8 | SPA，内联样式，无 CSS 框架依赖 |
| 实时通信 | SSE（流式对话）+ WebSocket（Partner 进度） | |
| 代码质量 | oxlint（前端） | |

---

## 项目结构

```
MUTI_AI-beta.1.0.0-p/
├── .data/                    # 用户数据（已 gitignore）
│   ├── planners/             # 每个 Planner 一个目录
│   │   └── {name}/
│   │       ├── meta.json     # Planner 元信息（名称、描述、图标）
│   │       ├── history.json  # Planner 对话历史
│   │       └── logs/         # Partner 运行日志
│   └── partners/             # 每个 Partner 一个目录
│       └── {name}/
│           ├── config.json   # Partner 配置
│           ├── butler/
│           │   ├── blueprint.md  # Butler 私有蓝图
│           │   └── history.json  # Butler 对话历史
│           └── worker/
│               ├── history.json  # Worker 对话历史
│               └── *.html/js/py  # Worker 生成的文件
├── core/                     # 核心逻辑
│   ├── __init__.py
│   ├── config.py             # 数据模型：ModelConfig, SessionConfig
│   ├── planner.py            # PlannerAgent
│   ├── partner_session.py    # Partner 会话编排
│   ├── bus.py                # CorrectionBus + WorkerSnapshot + ProgressState
│   ├── session.py            # SessionController（暂停/恢复/停止）
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── worker.py         # WorkerAgent
│   │   └── butler.py         # ButlerAgent
│   ├── llm/
│   │   ├── __init__.py       # chat() 统一入口
│   │   ├── base.py           # 路由到 provider
│   │   ├── openai_provider.py    # OpenAI 兼容实现（含流式）
│   │   └── anthropic_provider.py # Anthropic 实现
│   └── tools/
│       ├── __init__.py       # make_tools, execute_tool
│       ├── registry.py       # 工具 schema 定义
│       └── filesystem.py     # 文件系统工具（read/write/list）
├── display/                  # 输出/日志系统
│   ├── __init__.py           # 所有 display 函数的统一导出
│   ├── app.py
│   ├── partner_ui.py
│   ├── planner_ui.py
│   ├── terminal.py
│   └── welcome.py
├── server/
│   └── main.py               # FastAPI 后端（REST + SSE + WebSocket）
├── web/                      # React 前端
│   ├── src/
│   │   ├── main.jsx          # 入口
│   │   ├── App.jsx           # 主应用（布局、状态管理、主题切换）
│   │   ├── api.js            # API 客户端 + SSE 流 + WebSocket
│   │   ├── themes.js         # 三套主题配置（dark/light/midnight）
│   │   ├── components.jsx    # 通用组件（Spinner, Modal, Chip, LogLine, Bubble, ChatInput）
│   │   └── index.css         # 全局样式 + 动画关键帧
│   ├── dist/                 # 构建产物（由 Vite 生成）
│   ├── index.html
│   ├── vite.config.js
│   └── package.json
├── .env                      # API 密钥（已 gitignore）
├── .env.example              # 环境变量模板
├── .gitignore
├── launch.py                 # 启动脚本
└── run.bat                   # Windows 一键启动
```

---

## 架构设计

### 整体数据流

```
用户 → [前端 React] → [FastAPI REST/SSE] → [PlannerAgent]
                                                    │
                                          assign_to_partner
                                                    │
                                                    ▼
                                          [partner_session.py]
                                           ┌────────┴────────┐
                                           │                 │
                                      [ButlerAgent]    [WorkerAgent]
                                           │                 │
                                     审查/纠正 ←─── CorrectionBus ───→ 执行/写文件
                                           │                 │
                                     answer_question    ask_butler
                                           │                 │
                                           └──── 问答通道 ────┘
                                                    │
                                              [display/]
                                                    │
                                          WebSocket → 前端进度面板
```

### 三层 Agent 职责

| Agent | 输入 | 输出 | 工具 | 知识范围 |
|-------|------|------|------|----------|
| Planner | 用户消息 | 回复 + assign_to_partner | assign_to_partner | 用户需求 |
| Butler | Worker 快照 | CORRECT / ROLLBACK / OK + 进度评估 | read/write/list | 完整蓝图 |
| Worker | 任务描述 + Butler 纠正 | 代码文件 | read/write/list + ask_butler + finish_task | 仅通过 ask_butler 获取 |

### CorrectionBus 机制

`CorrectionBus` 是 Butler 和 Worker 之间的异步通信管道：

- **Butler → Worker**：
  - `inject_correction()`：轻微纠正，下一轮开头以 `[BUTLER CORRECTION]` 消息注入
  - `inject_rollback()`：严重错误，回滚文件到快照状态，恢复消息上下文
- **Worker → Butler**：
  - `publish_snapshot()`：每轮结束后发布 WorkerSnapshot，触发 Butler 评估
- **进度**：
  - `update_progress()`：Butler 评估进度后更新 ProgressState

### Worker 历史修复机制

Worker 在加载历史和每次调用 LLM 前都会执行 `_repair_messages()`，确保：
- 每个 `assistant` 消息的 `tool_calls` 都有对应的 `role: "tool"` 回复
- 缺失的 tool 消息会被自动补齐，避免 API 400 错误

---

## 核心模块详解

### core/config.py

```python
@dataclass
class ModelConfig:
    provider: Literal["openai", "anthropic"]
    model: str                    # 如 "deepseek-chat"
    api_key: str
    base_url: str | None = None   # 如 "https://api.deepseek.com"
    temperature: float = 0.7
    max_tokens: int = 4096

@dataclass
class SessionConfig:
    task: str
    project_root: str
    worker_subdirs: list[str]     # Worker 可写的子目录
    butler_model: ModelConfig
    worker_model: ModelConfig
    max_rounds: int = 20
    butler_system: str            # Butler 系统提示词
    worker_system: str            # Worker 系统提示词
    tool_schemas: list[dict]      # 可用工具的 JSON Schema
```

### core/planner.py — PlannerAgent

- 对话式交互，使用 `assign_to_partner` 工具创建 Partner
- `last_tool_calls` 存储最近一次的工具调用，由 server/main.py 解析并执行
- 历史持久化到 `.data/planners/{name}/history.json`

### core/agents/worker.py — WorkerAgent

核心执行循环：

```
for each round:
  1. wait_resume()           # 支持暂停/恢复
  2. _maybe_compress()       # 历史超过 30 条时压缩
  3. _repair_messages()      # 修复孤立 tool_calls
  4. chat() → response       # 调用 LLM
  5. 处理 tool_calls:
     - json 解析失败 → 补 error tool 消息
     - finish_task → 补 tool 消息后标记完成
     - ask_butler → 调用 butler.answer_question()
     - 其他工具 → execute_tool()
     - 执行异常 → 补 error tool 消息
  6. publish_snapshot()       # 发布给 Butler 审查
  7. _save()                  # 持久化历史
```

关键设计：
- **每个 tool_call 都保证有对应 tool 消息**，不会出现 API 400 错误
- **finish_task 不提前 return**，等所有 tool 消息补齐后再退出
- **历史压缩**保留尾部完整的 tool_calls 序列，避免截断

### core/agents/butler.py — ButlerAgent

- 注册 `bus.on_snapshot()` 回调，每轮自动评估 Worker
- 评估逻辑：检查 Worker 上下文，返回 CORRECT / ROLLBACK / OK
- 独立的进度评估调用 `_update_progress()`，失败不影响主评估
- `answer_question()`：响应 Worker 的 ask_butler 提问

### core/partner_session.py — 会话编排

- 创建 Butler 和 Worker 实例
- 配置系统提示词（从 blueprint.md 注入 Butler 知识）
- `headless=True` 时跳过终端交互（Web 模式）
- 运行日志写入 `.data/planners/{name}/logs/{partner}.log`

### core/tools/ — 工具系统

**registry.py** 定义三个基础工具的 JSON Schema：
- `read_file(path)` — 读取文件
- `write_file(path, content)` — 写入文件
- `list_dir(path)` — 列出目录

**filesystem.py** 实现：
- `_resolve_safe()` — 安全路径解析，确保不越界
- `make_file_handlers()` — 创建工具函数字典
- `make_tools()` — 返回 (schemas, handlers) 元组

**扩展工具**：在 `registry.py` 的 `_TOOL_SCHEMAS` 中添加 schema，在 `filesystem.py` 中添加实现即可。

### core/llm/ — LLM 抽象层

```
chat(cfg, messages, tools?, on_token?) → dict
  ├── provider="openai" → _openai_chat()
  └── provider="anthropic" → _anthropic_chat()
```

- 流式响应：`on_token` 回调逐 token 输出
- tool_calls 累积：流式模式下按 index 累积 tool_calls 片段

### display/ — 输出系统

所有 display 函数通过 `_push()` 发送事件：
- WebSocket 推送到前端
- 写入日志文件（如果设置了 log_path）

关键函数：
| 函数 | 事件类型 | 用途 |
|------|----------|------|
| `worker_header(round)` | session_line | 轮次标题 |
| `worker_tool_call(name, args)` | session_line | 工具调用 |
| `worker_tool_result(name, result)` | session_line | 工具结果 |
| `butler_ok(round)` | session_line | Butler 审查通过 |
| `butler_interrupt(round, correction)` | session_line | Butler 纠正 |
| `error_msg(who, err)` | session_line | 错误信息 |
| `update_progress_bar(percent, status)` | session_progress | 进度更新 |

---

## API 接口文档

### Planner

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/planners` | 列出所有 Planner |
| POST | `/api/planners` | 创建 Planner `{name, description, icon}` |
| DELETE | `/api/planners/{name}` | 删除 Planner |
| GET | `/api/planners/{name}/history` | 获取对话历史 |
| POST | `/api/planners/{name}/chat` | 发送消息（非流式） |
| POST | `/api/planners/{name}/chat/stream` | 发送消息（SSE 流式） |
| GET | `/api/planners/{name}/open` | 打开 Planner 文件夹 |

### Partner

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/partners/{name}/open` | 打开 Partner 文件夹 |
| DELETE | `/api/partners/{name}` | 删除 Partner |

### 其他

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/settings` | 获取设置（API Key 状态） |
| POST | `/api/settings/apikey` | 设置 API Key `{api_key}` |
| POST | `/api/open-folder` | 打开任意文件夹 `{path}` |
| WebSocket | `/ws` | 实时事件推送 |

### SSE 流式格式

```
data: {"token": "Hello"}          # 逐 token
data: {"token": " world"}         # 逐 token
data: {"done": true, "partners": [{"partner": "snake_game", "task": "..."}]}
```

### WebSocket 事件格式

```json
{"type": "session_line", "line": "⚙ 写入文件  index.html"}
{"type": "session_progress", "percent": 45.0}
{"type": "session_done", "partner": "snake_game", "status": "ok", "report": "..."}
```

---

## 前端开发指南

### 主题系统

`themes.js` 导出 `THEMES` 对象，包含三套主题：

```javascript
const THEMES = {
  dark: { accent: "#a1a1aa", ... },     // 深色 + 灰色强调
  light: { accent: "#71717a", ... },    // 浅色 + 灰色强调
  midnight: { accent: "#94a3b8", ... }, // 午夜蓝 + 灰色强调
};
```

通过 `ThemeCtx` Context 在组件树中传递，`useC()` 获取当前主题。

**添加新主题**：在 `themes.js` 中添加新 key，在 `App.jsx` 的 `cycleTheme` 函数中添加到轮换列表。

### 组件说明

| 组件 | 文件 | 用途 |
|------|------|------|
| `Spinner` | components.jsx | 加载动画 |
| `Modal` | components.jsx | 模态框 |
| `Chip` | components.jsx | 标签（工具调用、状态） |
| `LogLine` | components.jsx | Partner 日志行（自动识别类型着色） |
| `Bubble` | components.jsx | 对话气泡 |
| `ChatInput` | components.jsx | 输入框 + 发送按钮 |

### 样式约定

- 全部使用内联样式（`style={{...}}`），无 CSS 框架
- 颜色统一引用 `C.xxx`，不硬编码色值
- 特殊语义色（错误红 `#ef4444`、警告黄 `#f59e0b`）允许硬编码
- 动画定义在 `index.css` 的 `@keyframes` 中

### 前端构建

```bash
cd web
npm install
npm run dev      # 开发服务器 (port 5173)
npm run build    # 构建到 web/dist/
npm run lint     # oxlint 检查
```

---

## 数据存储

所有用户数据在 `.data/` 目录下，已加入 `.gitignore`：

```
.data/
├── planners/
│   └── {name}/
│       ├── meta.json         # {"name":"...", "description":"...", "icon":"🤖"}
│       ├── history.json      # Planner 完整对话历史
│       └── logs/
│           └── {partner}.log # Partner 运行日志
└── partners/
    └── {name}/
        ├── config.json       # {"name":"...", "description":"..."}
        ├── butler/
        │   ├── blueprint.md  # Butler 私有蓝图
        │   └── history.json  # Butler 对话历史
        └── worker/
            ├── history.json  # Worker 对话历史
            └── *             # Worker 生成的文件
```

---

## 开发环境搭建

### 前置要求

- Python 3.12+
- Node.js 18+
- npm

### 步骤

```bash
# 1. 克隆项目
git clone <repo-url>
cd MUTI_AI-beta.1.0.0-p

# 2. 安装 Python 依赖
pip install fastapi uvicorn openai anthropic

# 3. 安装前端依赖
cd web && npm install && cd ..

# 4. 配置 API Key
cp .env.example .env
# 编辑 .env，填入 DEEPSEEK_API_KEY

# 5. 启动（开发模式，前后端分离）
python launch.py --dev
# 后端: http://localhost:8765
# 前端: http://localhost:5173（热更新）

# 6. 启动（生产模式，前端由后端托管）
python launch.py
# 访问: http://localhost:8765

# 7. Windows 一键启动
run.bat
```

### 切换 LLM Provider

编辑 `.env`：

```env
# DeepSeek（默认）
DEEPSEEK_API_KEY=sk-xxx
DEEPSEEK_BASE_URL=https://api.deepseek.com

# OpenAI
OPENAI_API_KEY=sk-xxx
OPENAI_BASE_URL=https://api.openai.com/v1
```

然后修改 `server/main.py` 中的 `_make_model()` 函数。

---

## 调试技巧

### 查看 Partner 运行日志

日志存储在 `.data/planners/{name}/logs/{partner}.log`，格式：

```
[14:30:01] ━━━  Worker 工作中  ·  第 1 轮  ━━━
[14:30:05]   ⚙ 写入文件  index.html
[14:30:05]   └ Written 1234 chars to ...
[14:30:08]   ✓ Butler 审查第 1 轮：通过
```

### 查看 Agent 对话历史

- Planner: `.data/planners/{name}/history.json`
- Butler: `.data/partners/{name}/butler/history.json`
- Worker: `.data/partners/{name}/worker/history.json`

历史格式为 OpenAI Messages 格式：`[{"role": "system/user/assistant/tool", "content": "...", ...}]`

### 常见错误排查

| 错误 | 原因 | 解决 |
|------|------|------|
| `insufficient tool messages following tool_calls` | 历史中有孤立的 tool_calls | Worker 已内置 `_repair_messages()` 自动修复；如仍有问题，删除对应 Partner 的 history.json |
| `Worker LLM error: 401` | API Key 无效 | 检查 `.env` 中的 `DEEPSEEK_API_KEY` |
| `Partner 一直是 0%` | Butler 进度评估失败 | 检查日志，确认 Butler 是否正常评估 |
| 前端标题变成色块 | 渐变文字兼容性 | 已添加 `backgroundClip: "text"` + `color: "transparent"` 兜底 |

### 终端模式调试

直接运行 `partner_session.py` 可以进入终端交互模式：

```bash
python -m core.partner_session
```

可用命令：`stop` / `pause worker` / `pause butler` / `resume` / `status` / `help`

---

## 常见问题

### Q: 如何添加新的工具？

1. 在 `core/tools/registry.py` 的 `_TOOL_SCHEMAS` 中添加 JSON Schema
2. 在 `core/tools/filesystem.py` 中添加实现函数
3. 在 `make_file_handlers()` 中注册

### Q: 如何更换 LLM 模型？

修改 `server/main.py` 中的 `_make_model()` 函数，更改 `model` 和 `base_url` 参数。

### Q: 如何自定义 Butler/Worker 的系统提示词？

修改 `core/partner_session.py` 中的 `butler_system` 和 `worker_system` 字符串。

### Q: 前端如何添加新页面/组件？

1. 在 `web/src/components.jsx` 中创建组件
2. 在 `web/src/App.jsx` 中引入和使用
3. 所有样式使用内联 + `C` 主题对象

### Q: 如何修改主题配色？

编辑 `web/src/themes.js`，修改对应主题的 `accent`、`accentEnd`、`accentGrad` 等字段。

### Q: 数据目录在哪？

所有用户数据在项目根目录的 `.data/` 下：
- `.data/planners/` — Planner 数据
- `.data/partners/` — Partner 数据（Butler + Worker + 生成文件）
