# MUTI_AI

多智能体协作框架 — Planner 规划，Butler 监督，Worker 执行。

## 它是什么？

Echelon AI 让你用自然语言描述任务，自动调度 AI 智能体团队完成：

- **Planner** — 与你对话，理解需求，拆解任务
- **Butler** — 持有设计蓝图，监督执行质量，纠正偏差
- **Worker** — 编写代码，交付成果

一个 **Partner** = 一个 Butler + 一个 Worker。Planner 可以同时创建多个 Partner 并行工作。

## 快速开始

### 前置要求

- Python 3.12+
- Node.js 18+
- DeepSeek API Key（或兼容 OpenAI 的 API）

### 安装

```bash
git clone https://github.com/Holosukiyaa/MUTI_AI.git
cd MUTI_AI/MUTI_AI-beta.1.0.0-p

# Python 依赖
pip install fastapi uvicorn openai anthropic

# 前端依赖
cd web && npm install && cd ..

# 配置 API Key
cp .env.example .env
# 编辑 .env，填入你的 DEEPSEEK_API_KEY
```

### 启动

**Windows 一键启动：**
```bash
run.bat
```

**手动启动：**
```bash
# 开发模式（前后端分离，前端热更新）
python launch.py --dev

# 生产模式（前端由后端托管）
python launch.py
```

访问 http://localhost:8765 开始使用。

## 使用流程

1. 点击 **＋** 创建一个 Planner
2. 在对话框中描述你想要完成的任务
3. Planner 自动创建 Partner（Butler + Worker）开始执行
4. 右侧面板实时显示执行进度和日志
5. 任务完成后，点击 📁 查看生成的文件

## 架构

```
用户 ──→ Planner ──→ Partner 1 (Butler × Worker)
                   ──→ Partner 2 (Butler × Worker)
                   ──→ ...
```

| 角色 | 职责 | 知识 |
|------|------|------|
| Planner | 理解需求、拆解任务、分配 Partner | 用户对话 |
| Butler | 持有蓝图、监督质量、纠正/回滚 | 完整设计规范 |
| Worker | 编写代码、交付文件 | 仅通过 ask_butler 获取 |

### 核心机制

- **知识隔离**：Worker 看不到蓝图，必须向 Butler 提问，避免"偷看答案"
- **纠正总线**：Butler 发现偏差时注入 CORRECT（轻微纠正）或 ROLLBACK（回滚文件）
- **进度评估**：Butler 独立评估任务完成度，实时推送到前端
- **历史修复**：Worker 自动修复损坏的对话历史，防止 API 报错

## 技术栈

| 层级 | 技术 |
|------|------|
| 后端 | Python / FastAPI / asyncio |
| LLM | OpenAI 兼容 API（默认 DeepSeek） |
| 前端 | React 19 / Vite 8 |
| 实时通信 | SSE + WebSocket |

## 项目结构

```
├── core/                  # 核心逻辑
│   ├── planner.py         # Planner Agent
│   ├── partner_session.py # Partner 会话编排
│   ├── agents/worker.py   # Worker Agent
│   ├── agents/butler.py   # Butler Agent
│   ├── bus.py             # 纠正总线 + 进度状态
│   ├── session.py         # 会话控制器
│   ├── llm/               # LLM 抽象层
│   └── tools/             # 工具系统（文件读写）
├── server/main.py         # FastAPI 后端
├── web/src/               # React 前端
│   ├── App.jsx            # 主应用
│   ├── themes.js          # 主题配置
│   └── components.jsx     # UI 组件
├── display/               # 输出/日志系统
├── .data/                 # 用户数据（自动生成）
└── launch.py              # 启动脚本
```

## 配置

### 环境变量

```env
DEEPSEEK_API_KEY=sk-your-key-here
DEEPSEEK_BASE_URL=https://api.deepseek.com
```

### 切换 LLM

修改 `server/main.py` 中的 `_make_model()` 函数，支持任何 OpenAI 兼容 API。

### 主题

前端支持三套主题：Light / Dark / Midnight，点击左上角图标切换。可在 `web/src/themes.js` 中自定义配色。

## 开发

详细的开发文档请参阅 [DEVELOPMENT.md](./DEVELOPMENT.md)，包含：

- 完整架构设计
- 核心模块详解
- API 接口文档
- 前端开发指南
- 调试技巧
- 常见问题

## License

MIT
