# Echelon AI

多智能体协作框架 — Director 规划，Mentor 监督，Worker 执行。

## 它是什么？

Echelon AI 让你用自然语言描述任务，自动调度 AI 智能体团队完成：

- **Director** — 直接与你对话，理解需求，将任务分配给 Squad 执行。支持四种角色：执行者、蓝图规划师、项目管理员、自定义
- **Mentor** — 持有设计蓝图，是知识的唯一来源；监督 Worker 执行质量，纠正偏差或回滚错误
- **Worker** — 编写代码，交付成果；通过 `ask_mentor` 向 Mentor 获取设计信息

一个 **Squad** = 一个 Mentor + 一个 Worker。Director 可以同时创建多个 Squad 并行执行不同子任务。

## 快速开始

### 前置要求

- Python 3.12+
- Node.js 18+
- DeepSeek API Key 或 Anthropic Claude API Key

### 安装

```bash
git clone https://github.com/Holosukiyaa/MUTI_AI.git
cd MUTI_AI

# Python 依赖
pip install fastapi "uvicorn[standard]" openai anthropic

# 前端依赖
cd web && npm install && cd ..

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 API Key
```

### 启动

**Windows 一键启动：**
```bash
run.bat
```

**手动启动：**
```bash
python launch.py
```

访问 http://localhost:5173 开始使用（后端运行在 http://localhost:8765）。

## 使用流程

1. 点击 **＋** 创建一个 Director
2. 在对话框中描述你想要完成的任务
3. Director 自动创建 Squad（Mentor + Worker）开始执行
4. 右侧面板实时显示执行进度和日志
5. 任务完成后，点击 📁 查看生成的文件

### 推荐工作流（蓝图模式）

1. 创建一个 **蓝图规划师** Director，深度讨论需求，生成结构化蓝图
2. 创建一个 **项目执行者** Director，自动读取蓝图，将任务分配给 Squad 执行

## 架构

```
用户 ──→ Director ──→ Squad 1 (Mentor × Worker)
                    ──→ Squad 2 (Mentor × Worker)
                    ──→ ...
```

| 角色 | 职责 | 知识来源 |
|------|------|---------|
| Director | 与用户对话、制定计划、分配 Squad | 用户对话 + 蓝图文档 |
| Mentor | 持有蓝图、监督质量、纠正/回滚 | 完整设计规范（私有）|
| Worker | 编写代码、交付文件 | 仅通过 ask_mentor 获取 |

### 核心机制

- **知识隔离**：Worker 看不到蓝图，必须向 Mentor 提问，避免"偷看答案"
- **纠正总线**：Mentor 发现偏差时注入 CORRECT（轻微纠正）或 ROLLBACK（回滚文件）
- **进度评估**：Mentor 独立评估任务完成度，实时推送到前端
- **历史修复**：Worker 自动修复损坏的对话历史，防止 API 报错
- **RollingStrategy**：token 消耗达到阈值时自动无损轮换角色，支持任意长度任务

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python 3.12+ / FastAPI / asyncio |
| LLM | OpenAI 兼容 API（DeepSeek）/ Anthropic Claude |
| 前端 | React 19 / Vite 8 |
| 实时通信 | SSE（流式对话）+ WebSocket（Squad 进度）|

## 项目结构

```
├── core/
│   ├── config.py          # 全局数据结构
│   ├── infra/             # 基础设施（bus / session / token_tracker / tools）
│   ├── llm/               # LLM 抽象层（OpenAI + Anthropic）
│   ├── agents/            # Mentor / Worker Agent
│   ├── director/          # DirectorAgent（四种角色）
│   └── squad/             # Squad 生命周期编排
├── server/main.py         # FastAPI 后端
├── web/src/               # React 前端
│   ├── App.jsx            # 主应用
│   ├── themes.js          # 主题配置
│   └── components.jsx     # UI 组件
├── display/__init__.py    # 事件推送适配器
├── .data/                 # 用户数据（自动生成）
└── launch.py              # 启动脚本
```

## 配置

### 环境变量

```env
# DeepSeek（默认）
AI_PROVIDER=openai
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
OPENAI_MODEL=deepseek-chat

# Anthropic Claude
AI_PROVIDER=claude
CLAUDE_API_KEY=sk-ant-your-key-here
CLAUDE_MODEL=claude-opus-4-5
```

也可以在前端设置面板中直接切换 Provider 和 API Key，无需重启。

### 切换 LLM

修改 `.env` 中的 `AI_PROVIDER` 字段，或在前端设置面板中切换。支持任何 OpenAI 兼容 API 端点。

### 主题

前端支持三套主题：Light / Dark / Midnight，点击左上角图标切换。可在 `web/src/themes.js` 中自定义配色。

## 开发

详细的开发文档请参阅 [devtools/DEVELOPMENT.md](./devtools/DEVELOPMENT.md)，包含：

- 完整架构设计与分层说明
- 核心模块详解（infra / agents / director / squad）
- API 接口文档（Group / Director / Squad）
- 前端开发指南
- 调试技巧
- 扩展指南（添加工具、新 Agent、替换前端）
- 常见问题

## License

MIT
