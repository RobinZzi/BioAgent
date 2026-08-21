<p align="center"><a href="README.zh.md"><img src="https://img.shields.io/badge/中文-简体中文-blue?style=for-the-badge" alt="中文版"></a> <a href="README.en.md"><img src="https://img.shields.io/badge/English-README-blue?style=for-the-badge" alt="English"></a> · <a href="README.md">🏠 入口页</a></p>

# BioAgent · 生信分析 Agent 工作平台（v0.1 MVP）

> 让用户通过自然语言，与一个能够理解生物信息学分析流程、调用真实计算环境、
> 执行分析并记录全过程的 AI Agent 协作完成科研分析。

技术方案与数据模型见 [`docs/TECHNICAL_DESIGN.md`](docs/TECHNICAL_DESIGN.md)。

## 已实现（MVP 纵向切片 + M5/M6）

```
用户本机 → 环境发现 → Environment Manifest → Capability Resolver
  → Agent(规则引擎 / LLM) 理解「帮我聚类」 → 结构化 Task
  → Executor(mock / 本地真实 / 远程 Connector+Slurm)
  → Analysis Event + Artifact + 上下文指针更新 → 前端展示（对话 / DAG / 产物）
```

- **数据模型**：Project → Conversation（一条分析线索，含上下文指针）→ 需求
  → AnalysisEvent → DAG；Dataset 不可变版本链；Artifact 归属事件
- **Capability Registry**：19 个能力，语言无关契约，多实现（scanpy / Seurat /
  DESeq2 / edgeR / clusterProfiler / STAR-bash 模板化命令）
- **环境发现**：conda envs / Python / R / 项目内 venv（`.venv*`）/ CLI 工具 /
  Slurm / GPU，生成 Manifest，任何探测失败不中断
- **Executor**：异步状态机（queued → running → succeeded/failed/cancelled）
  - `mock`：预生成真实文件产物（matplotlib 图、CSV、HTML 报告），开发/演示用
  - `local`：scanpy / R / bash 模板脚本真实执行（**auto 模式逐个探测候选
    runtime，跳过损坏环境，自动命中可用的 Python 3.11 venv**）
  - `remote`：Local Connector 协议（token 鉴权 + /discover + /execute）
  - `slurm`：Connector 内 SlurmExecutor（sbatch 模板 + sacct 轮询）
- **Agent Runtime**：
  - v0.1 规则引擎：意图解析、参数提取（「分辨率 1.0」）、前置链自动补全
    （说「聚类」自动先跑 QC→标准化→PCA→邻接图）、「继续」推进、
    「换个分辨率重新聚类」→ re_run 边（fork）
  - v0.2 **LLM**（OpenAI 兼容，默认 DeepSeek 端点）：意图解析 + 回复生成，
    三模式 `off/echo/real`，任何失败自动回退规则引擎
- **会话上下文**：指针式（current_dataset / current_phase / analysis_state），
  「继续聚类」无需重复交代背景
- **前端**：项目列表 → 工作台（对话面板 + 分析 DAG + 数据集链 + 产物画廊 +
  环境/能力 + Agent 状态徽标 + 计算环境切换 + 远程 Connector 注册）

## 快速开始

```bash
# 1. 初始化环境（首次）
bash scripts/dev.sh setup

# 2. 一键启动（后端 :8000 + 前端 :5173）
bash scripts/dev.sh start

# 打开 http://localhost:5173
# 后端 API 文档: http://127.0.0.1:8000/docs
```

### 手动步骤

```bash
# 后端
cd backend
.venv/bin/uvicorn app.main:app --port 8000          # 需先创建 .venv（见下）

# 前端
cd frontend
npm install --cache ../.npm-cache
npx vite --port 5173                                 # 已配置 /api 代理到 :8000

# 演示数据（HCC 单细胞全流程，mock 模式）
backend/.venv/bin/python scripts/seed_demo.py
```

### 后端环境（Python 3.12 + Python 3.11 scanpy，uv）

```bash
uv venv --python 3.12 backend/.venv
UV_CACHE_DIR=$(pwd)/.uv-cache uv pip install --python backend/.venv/bin/python \
  fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings matplotlib

# 真实 scanpy 执行环境（可选，auto 模式自动探测可用 runtime）
uv venv --python 3.11 backend/.venv311
UV_CACHE_DIR=$(pwd)/.uv-cache uv pip install --python backend/.venv311/bin/python \
  scanpy anndata leidenalg
```

## 执行器模式

| 模式 | 行为 |
|---|---|
| `mock` | 不调真实工具，预生成合理产物（无生信环境也能完整演示） |
| `auto` | **逐个探测候选 runtime**：跳过损坏环境（如 py3.8 scanpy），命中可用 runtime 真实执行；全部失败回退 mock（推荐） |
| `local` | 只走真实执行，工具缺失即结构化失败 |

设置：环境变量 `BIOAGENT_EXECUTOR_MODE`（前缀 `BIOAGENT_`），或修改 `backend/app/config.py`。

> 注：本机 conda 环境的 scanpy 因 Python 3.8 兼容问题无法导入，`auto` 模式
> 会自动跳过并命中 `backend/.venv311`（Python 3.11 + scanpy 1.11.5）真实执行。

## LLM Agent（v0.2）

| 模式 | 行为 |
|---|---|
| `off`（默认） | 规则引擎，无需配置 |
| `echo` | 模拟 LLM 返回，端到端验证集成链路 |
| `real` | OpenAI 兼容 Chat Completions（默认 DeepSeek 端点） |

```bash
BIOAGENT_LLM_MODE=real \
BIOAGENT_LLM_API_KEY=sk-xxx \
BIOAGENT_LLM_MODEL=deepseek-chat \
  backend/.venv/bin/uvicorn app.main:app --port 8000
```

意图解析 / 回复生成失败时**自动回退规则引擎**。调试：`POST /api/agent/intent`。

## Docker 部署

```bash
docker compose up -d --build
# 前端 http://localhost:5173（Nginx 代理 /api → 后端 :8000）
# 后端 API http://localhost:8000/docs
# 数据持久化在 docker volume bioagent-data
```

## Local Connector（远程执行）

```bash
# 在持有用户身份（SSH Key）的机器上启动
CONNECTOR_TOKEN=<共享令牌> CONNECTOR_EXECUTOR_MODE=auto \
  backend/.venv/bin/uvicorn connector.main:app --port 8765

# 后端注册：POST /api/projects/{id}/environments/register-remote
# 前端：环境/能力 面板 →「注册远程 Connector」→ 工作台顶栏切换计算环境
```

模式：`mock | local | slurm | auto`（auto：Slurm 可用→slurm，否则本地，失败回退 mock）。

## 目录结构

```
docs/TECHNICAL_DESIGN.md    # 技术方案与数据模型设计（蓝图）
backend/
  app/
    models.py               # SQLAlchemy 数据模型（含 DAG 边、上下文指针）
    capabilities/           # Capability 契约（语言无关）+ 参数定义域
    env/                    # Environment Discovery + Manifest
    executor/               # mock / local / remote + 脚本模板 + 运行时探测
    services/               # agent(规则+LLM) · llm · execution · dag
    api/router.py           # REST API
  data/                     # SQLite + 项目产物（运行时生成）
connector/                  # Local Connector 服务（/health /discover /execute + Slurm）
frontend/                   # React + Vite + TS
scripts/seed_demo.py        # 演示数据：HCC 单细胞全流程
scripts/dev.sh              # setup / start 脚本
```

## 常用 API

| 方法 | 路径 | 说明 |
|---|---|---|
| POST | `/api/projects` | 创建项目（数据位置 / 计算位置独立） |
| POST | `/api/projects/{id}/conversations` | 创建对话 |
| POST | `/api/conversations/{id}/messages` | 发消息（`wait=true/false`，异步轮询） |
| POST | `/api/projects/{id}/environments/discover` | 环境发现 → Manifest |
| GET | `/api/capabilities/resolve?capability_id=&environment_id=` | Tool→Capability 解析 |
| GET | `/api/projects/{id}/dag` | 分析 DAG |
| POST | `/api/events/{id}/rerun` | 重跑（re_run 边，fork） |
| GET | `/api/artifacts/{id}/content` | 产物内容 |
| GET | `/api/agent/status` | Agent 模式（off/echo/real） |
| POST | `/api/agent/intent` | 意图解析 dry-run |
| POST | `/api/projects/{id}/environments/register-remote` | 注册远程 Connector |
| POST | `/api/conversations/{id}/set-environment` | 切换对话计算环境 |

## 路线图

- [x] 真实 scanpy 链路（Python 3.11 venv，端到端验证通过）
- [x] LLM Agent v0.2（OpenAI 兼容，失败自动回退）
- [x] 远程 Connector / Slurm Executor（Local Connector 安全模型）
- [ ] R/DESeq2 与 STAR 真实运行验证（目标机器需安装 R 包）
- [ ] 远程文件路径映射层（跨机器文件访问）
- [ ] 分析历史对比 / 参数比较视图
- [ ] 更多组学：空间转录组 / scATAC / 多组学 / 甲基化 / WES-WGS

## 安全模型（v0.1）

Executor 只接受结构化 Task；命令由模板构造、参数经定义域二次校验；输入仅限
注册 Dataset 路径，输出仅限项目目录；无自由 Shell 通道。见文档 §11。
