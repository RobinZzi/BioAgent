# BioAgent 技术方案与数据模型设计

> 版本：v0.1（MVP 蓝图）
> 依据：《BioAgent 产品概念与架构说明》及架构评审结论
> 状态：已与产品负责人确认，作为编码蓝图

---

## 0. 文档目的

本文档把《架构说明》与评审结论固化为可编码的技术方案，覆盖：

1. 核心领域模型（已确认的 Project → Conversation → 需求 → Event → DAG）
2. 会话上下文机制（指针式上下文）
3. 语言无关的 Capability 契约（Python / R / bash 多实现）
4. Environment Discovery 与 Manifest
5. Executor 协议与异步状态机（含 mock 执行模式）
6. API 面与前端结构
7. MVP 最小纵向切片与里程碑

---

## 1. 总体架构

```
Frontend (React)
   │  REST API
Agent Runtime (规则引擎 v0.1 → LLM v0.2)
   │  理解 → 规划 → 选择
Capability Registry (语言无关契约)
   │  Resolver: Capability × Environment Manifest
Environment Manager (Discovery → Manifest → Health)
   │
Executor (结构化 Task 状态机)
   ├── Mock Executor   (开发/演示，预生成结果)
   ├── Local Executor  (本机，模板化命令)
   └── Remote Executor (v0.2，Local Connector 协议)
```

**核心原则（不可违背）：**

- Agent / LLM **不直接执行 Shell**；Executor 只接受结构化 Task（`capability_id + implementation + runtime_id + inputs + parameters`）。
- 安全边界是**协议白名单**，不是 OS 沙箱：本地执行以用户权限运行，但 Executor 只按模板构造命令、只读输入路径、只写项目输出目录。
- bash 场景一律包装为**受控 Capability + 模板化命令**，不允许自由 bash。
- 数据模型、Capability 契约、Event 记录均带 **schema_version**，为演进留后路。

---

## 2. 核心领域模型（已确认）

### 2.1 关系总览

```
User (v0.1 单用户，模型预留)
 └── Project            ← 一个数据来源 / 一个科研课题
       └── Conversation ← 一条连贯分析线索（当前一个 Project 一条，对象独立）
             ├── 需求 (UserMessage → 触发 1..n 个 AnalysisEvent)
             └── AnalysisEvent → Analysis DAG
                    └── Artifact
       ├── Dataset（版本链：Raw → QC → Normalized → Clustered → Annotated）
       └── ComputeEnvironment（Runtimes / Tools / Compute + Manifest）
```

**语义约定（评审结论）：**

- **Conversation = 一条分析线索（case）**，是上下文容器；**AnalysisEvent = 一次实际执行**；**DAG = case 内的完整分析历史**。一对多。
- 对话消息标注其**触发了哪些 Event**（可多条），Event 记录**对应的对话消息 id**，双向可追溯。
- 一个 Project 下可有多个 Conversation（主流程 + 探索分支），共享 Dataset 版本链，各自持有独立的上下文指针。

### 2.2 会话上下文（指针式上下文）

「继续聚类」能工作的凭据——Conversation 挂一组指针指向 DAG 当前位置，**不复制分析结果**：

```json
{
  "conversation_id": "conv_001",
  "project_id": "proj_hcc",
  "current_dataset_id": "dataset_004a",
  "current_phase": "clustered",
  "active_environment_id": "env_local",
  "active_runtime_id": "runtime_scanpy",
  "analysis_state": "dataset_004a 已含 leiden 聚类 (res=0.5)，尚未注释"
}
```

每次 Event 成功完成后更新一次指针。意图解析（v0.1 规则引擎）基于该指针确定默认输入与前置条件。

### 2.3 数据表设计（SQLite + SQLAlchemy 2.0）

| 表 | 关键字段 |
|---|---|
| `users` | id, name, created_at（预留） |
| `projects` | id, name, description, data_source(enum: local/remote), compute_location(enum: local/remote), created_at |
| `conversations` | id, project_id(FK), title, current_dataset_id, current_phase, active_environment_id, active_runtime_id, analysis_state(JSON), created_at |
| `messages` | id, conversation_id(FK), role(enum: user/assistant), content, triggered_event_ids(JSON), created_at |
| `datasets` | id, project_id(FK), name, dtype(enum: rna_seq/scrna/...), format, location(不可变路径), parent_dataset_id(self-FK), source_event_id(FK, nullable), metadata(JSON), schema_version |
| `environments` | id, project_id(FK, nullable=全局), name, env_type(enum: local/remote), manifest(JSON), status(enum: unknown/healthy/degraded/unreachable), discovered_at |
| `analysis_events` | id, project_id(FK), conversation_id(FK), message_id(FK, nullable), capability_id, implementation, runtime_id, environment_id, inputs(JSON: dataset_ids), parameters(JSON), status(enum: queued/running/succeeded/failed/cancelled), error(JSON, nullable), started_at, finished_at, output(JSON: dataset_ids/artifact_ids), log_path, schema_version |
| `event_links` | id, parent_event_id(FK), child_event_id(FK), relation(enum: depends_on/re_run/fork) —— DAG 边 |
| `artifacts` | id, project_id(FK), event_id(FK), kind(enum: figure/csv/pdf/html/h5ad/log/report), name, path, mime, size_bytes, metadata(JSON), created_at |

**Dataset 不可变 + 引用语义**：每个 Dataset 指向一个不可变文件，版本链只是指针关系；分析从不修改原始数据。

**Event schema_version**：Capability 与 Event 记录带 schema 版本，防止历史无法解析。

---

## 3. Capability 契约（语言无关）

### 3.1 Capability 定义

```json
{
  "capability_id": "scrna.clustering",
  "name": "单细胞聚类",
  "domain": "scrna",
  "input_schema": {
    "type": "object",
    "required": ["dataset"],
    "properties": {
      "dataset": {"type": "string", "format": "dataset_ref", "dtype": "scrna"},
      "n_top_genes": {"type": "integer", "minimum": 1, "maximum": 5000, "default": 2000}
    }
  },
  "output_schema": {
    "dataset": {"type": "scrna", "adds": ["leiden_clusters"]},
    "figures": ["umap_clusters.png"]
  },
  "parameter_domains": {
    "resolution": {"type": "number", "enum": [0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0]}
  },
  "preconditions": ["scrna.normalization", "scrna.pca", "scrna.neighbors"],
  "implementations": [
    {"id": "scanpy",   "language": "python", "runtime_hint": "conda"},
    {"id": "seurat",   "language": "r",      "runtime_hint": "renv"}
  ],
  "default_implementation": "scanpy",
  "schema_version": 1
}
```

**要点：**

- `input_schema` / `output_schema` / `parameter_domains` **语言无关** —— Agent 只选 Capability + Implementation，不关心底层语言。
- 参数用**定义域约束**（enum / min-max）而非自由填空，防止 LLM/规则给出非法参数；Executor 执行前二次校验。
- `preconditions` 用于依赖检查（先 Normalization 才能 Clustering）。

### 3.2 v0.1 Capability 清单（首批）

**scRNA-seq（Scanpy 实现为主）：**

| capability_id | 输入 | 输出 |
|---|---|---|
| `scrna.inspect` | h5ad | 报告 + 基础统计图 |
| `scrna.qc` | h5ad | 过滤后 h5ad + QC 图 |
| `scrna.normalization` | h5ad | normalized h5ad |
| `scrna.hvg` | h5ad | h5ad + hvg 图 |
| `scrna.pca` | h5ad | h5ad + 方差图 |
| `scrna.neighbors` | h5ad | h5ad |
| `scrna.umap` | h5ad | h5ad + umap.png |
| `scrna.clustering` | h5ad | h5ad(leiden) + umap_clusters.png |
| `scrna.marker_genes` | h5ad | CSV + heatmap |
| `scrna.annotation` | h5ad | annotated h5ad + 图 |

**Bulk RNA-seq（R 实现为主）：**

| capability_id | 输入 | 输出 |
|---|---|---|
| `bulk_rna.inspect` | count matrix + metadata | 报告 |
| `bulk_rna.qc` | count matrix + metadata | 过滤后矩阵 + 图 |
| `bulk_rna.normalization` | count matrix | normalized 矩阵 |
| `bulk_rna.differential_expression` | counts + design | DE 表（DESeq2 / edgeR） |
| `bulk_rna.volcano` | DE 表 | volcano.png |
| `bulk_rna.heatmap` | DE 表 + counts | heatmap.png |
| `bulk_rna.go_enrichment` | DE 表 | GO 表 + 图 |
| `bulk_rna.gsea` | ranked list | GSEA 表 + 图 |

**bash/CLI 工具型（模板化命令）：**

| capability_id | 输入 | 输出 |
|---|---|---|
| `bulk_rna.alignment` | fastq + 参考基因组 | bam（STAR + samtools 模板） |

### 3.3 Implementation ↔ Runtime 绑定

Resolver 判断逻辑统一为：

```
Capability 可用 ⟺ 存在 implementation，其 runtime 在环境 Manifest 中 status=healthy
```

不关心实现语言。每个 implementation 在 Executor 侧注册为「模板 + 参数校验」，例如：

- `scanpy` → Python 脚本模板（由参数 schema 拼装，执行于 conda env）
- `seurat` / `DESeq2` → R 脚本模板（执行于 R/renv）
- `STAR` → bash 模板（严格白名单参数）

---

## 4. Environment Discovery 与 Manifest

### 4.1 发现流程

```
Connection Check → System Discovery → Runtime Discovery → Tool Discovery → Compute Discovery → Health Check
```

v0.1 本地发现实现：

- Runtime：`conda env list`（枚举 conda 环境）、`python --version`、`R --version`、`which` 探测
- Tool：对每个 conda env 执行 `conda list` 匹配工具清单（scanpy/anndata/leidenalg/scvi-tools/pandas…）；系统级 `which` 匹配（STAR/samtools/…）
- Compute：`uname`、CPU/内存、GPU（`nvidia-smi`/`system_profiler` 可选）、Slurm（`which sbatch`）
- 任何探测失败 → 该项标记 `unknown`，不中断，Manifest 仍生成（status=degraded）

### 4.2 Environment Manifest（标准化输出）

```json
{
  "environment_id": "env_local",
  "environment_type": "local",
  "system": {"os": "darwin", "arch": "arm64", "cpu_cores": 10, "memory_gb": 32, "gpu": null},
  "compute": {"scheduler": null, "notes": []},
  "runtimes": [
    {"id": "runtime_base", "type": "python", "python_version": "3.12", "path": "..."},
    {"id": "runtime_scanpy", "type": "conda", "name": "scanpy", "python_version": "3.11", "path": "/opt/anaconda3/envs/scanpy"},
    {"id": "runtime_R", "type": "r", "name": "R", "version": "4.3.x", "path": "/usr/local/bin/R"}
  ],
  "tools": [
    {"tool_id": "scanpy", "runtime_id": "runtime_scanpy", "version": "1.10.x", "status": "healthy"},
    {"tool_id": "anndata", "runtime_id": "runtime_scanpy", "version": "0.10.x", "status": "healthy"},
    {"tool_id": "DESeq2", "runtime_id": "runtime_R", "version": "1.44.x", "status": "healthy"},
    {"tool_id": "star", "runtime_id": null, "version": "2.7.x", "status": "healthy"}
  ],
  "schema_version": 1
}
```

Manifest 落库（environments 表），发现可随时重跑（`POST /api/environments/{id}/rediscover`）。

---

## 5. Executor 协议与状态机

### 5.1 结构化 Task

Executor 唯一接受的输入：

```json
{
  "task_id": "task_001",
  "capability_id": "scrna.clustering",
  "implementation": "scanpy",
  "runtime_id": "runtime_scanpy",
  "inputs": {"dataset": "dataset_004"},
  "parameters": {"resolution": 0.5, "n_top_genes": 2000},
  "output_dir": "/data/project_001/output/task_001"
}
```

### 5.2 状态机（异步，第一版即实现）

```
queued → running → succeeded | failed | cancelled
```

- 前端轮询事件状态 + 增量日志；失败时返回**结构化错误**（阶段、异常类型、日志尾部），供 Agent 修正重跑。
- 长任务友好：`POST /api/tasks` 立即返回 `task_id`，`GET /api/events/{id}` 查询状态。

### 5.3 三个实现

| Executor | 用途 | 行为 |
|---|---|---|
| `MockExecutor` | 开发/演示/CI | 不调真实工具，按 capability 预生成合理产物（h5ad 用合成 AnnData 或占位文件、PNG 用 matplotlib 生成真图、CSV 合成统计表），记录模拟日志 |
| `LocalExecutor` | 真实本机执行 | 校验参数 → 按 implementation 模板生成脚本 → 在指定 runtime 中执行 → 收集产物 → 写 Event 日志；工具缺失时返回结构化错误并建议 mock |
| `RemoteExecutor` | v0.2 | Local Connector 协议（Agent 不持有凭据，见架构说明 §10） |

**mock 模式的战略价值**：Agent 逻辑、前端、DAG 记录的开发完全独立于真实环境；未装 scanpy 的机器也能完整演示纵向切片。`环境 → Executor 选择` 由 manifest + 配置决定（`EXECUTOR_MODE=mock|auto`）。

---

## 6. Agent Runtime（v0.1 规则引擎 → v0.2 LLM）

v0.1 不做自由问答，做**受限对话闭环**：意图识别 → 计划 → 选择 → 执行 → 反馈。

```
用户消息
  ↓ 意图解析（v0.1 规则 / v0.2 LLM，接口一致，可回退）
  ↓ 上下文补全（current_dataset_id 作为默认输入；preconditions 检查）
  ↓ Capability Resolver（× manifest → 可用 implementation 列表，选 default 或用户指定）
  ↓ 生成 Task → 校验 → 交 Executor
  ↓ 执行 → AnalysisEvent + Artifacts → 更新上下文指针 → 回复用户
```

- 规则引擎表：`{"聚类": ("scrna.clustering", {...}), "聚类 分辨率 1.0": (...), "qc": (...), "差异表达": (...), "de": (...), "比对": (...) ...}`，支持「继续…」「重新…」前缀识别（re-run 语义 → DAG `re_run` 边）。
- **v0.2 LLM 模式**（已实现，`services/llm.py`）：
  - 三模式：`off`（规则引擎）/ `echo`（模拟 LLM 返回，端到端验证集成链路）/ `real`（OpenAI 兼容 Chat Completions，默认 DeepSeek 端点）
  - 意图解析：能力目录 + 会话上下文注入 prompt → 结构化 JSON（capability_id + 参数）→ 按定义域校验
  - **任何 LLM 失败自动回退规则引擎**；回复生成同样可切换
  - 配置：`BIOAGENT_LLM_MODE` / `BIOAGENT_LLM_API_KEY` / `BIOAGENT_LLM_BASE_URL` / `BIOAGENT_LLM_MODEL`
  - 接口与规则引擎一致（返回 capability + params + note），Executor 与数据模型无感

---

## 7. API 面（v0.1）

| Method | Path | 说明 |
|---|---|---|
| GET | `/api/projects` | 项目列表 |
| POST | `/api/projects` | 创建项目（data_source / compute_location） |
| GET | `/api/projects/{id}` | 项目详情（含 conversations / datasets / events / dag） |
| POST | `/api/projects/{id}/conversations` | 创建对话 |
| GET | `/api/conversations/{id}` | 对话详情（含 messages + 上下文指针 + DAG） |
| POST | `/api/conversations/{id}/messages` | 发消息（触发 Agent Runtime，可同步或异步） |
| POST | `/api/projects/{id}/datasets` | 注册数据集（路径 + 类型 + 格式） |
| GET | `/api/projects/{id}/datasets` | 数据集列表（版本链） |
| POST | `/api/projects/{id}/environments/discover` | 环境发现（本地）→ 生成 Manifest |
| GET | `/api/projects/{id}/environments` | 环境列表 |
| POST | `/api/environments/{id}/rediscover` | 重新发现 |
| GET | `/api/capabilities` | Capability 清单 |
| GET | `/api/capabilities/resolve?env_id=&capability_id=` | Resolver 结果 |
| GET | `/api/events/{id}` | 事件详情（状态/日志/产物） |
| GET | `/api/events/{id}/logs` | 增量日志 |
| GET | `/api/projects/{id}/dag` | 完整分析 DAG |
| GET | `/api/artifacts/{id}/content` | 产物内容（图/CSV/文本） |
| POST | `/api/events/{id}/rerun` | 重跑（参数可改）→ re_run 边 |
| **Agent / LLM（v0.2）** | | |
| GET | `/api/agent/status` | Agent 模式（off/echo/real）与模型配置 |
| POST | `/api/agent/intent` | 意图解析 dry-run（LLM → 规则 → none） |
| **远程 Connector（v0.1）** | | |
| POST | `/api/projects/{id}/environments/register-remote` | 注册远程 Connector（握手 /discover） |
| POST | `/api/environments/{id}/test` | 环境连通性测试 |
| POST | `/api/conversations/{id}/set-environment` | 切换对话的计算环境 |

---

## 8. 前端结构（React + Vite + TS）

```
frontend/src/
  api.ts               # fetch 封装
  types.ts             # 与后端 schema 对应
  App.tsx              # 路由：项目列表 → 项目工作台
  components/
    ProjectList.tsx     # 项目选择（对应「先选 project」）
    Workspace.tsx       # 左：对话面板；右：分析视图
    ConversationPanel.tsx  # 消息流 + 输入框 + 上下文状态条
    AnalysisDAG.tsx     # 事件节点 DAG（状态着色、fork 展示）
    EventDetail.tsx     # 事件详情（参数/日志/产物）
    ArtifactGallery.tsx # 图/表/文件展示
    DatasetChain.tsx    # 数据集版本链
```

**关键交互**：进入 Project → 看到对话 + 当前上下文状态（当前数据集/阶段）→ 发消息 → 事件在 DAG 面板出现并流转 → 产物可点击查看。这正是第十五节的最小纵向切片的前端形态。

---

## 9. MVP 最小纵向切片（验收路径）

```
启动后端 → 创建 Project(HCC) → 环境发现(本机 conda → Manifest)
  → 注册数据集 → 对话发「帮我看看数据质量」→ 规则引擎 → scrna.inspect
  → Resolver × Manifest → scanpy(或 mock) → Executor → AnalysisEvent
  → Artifact(图+报告) → 更新上下文指针 → 前端展示
  → 继续「聚类，分辨率 0.5」→ preconditions 检查 → 自动补全中间步骤或报缺前置
  → DAG 面板出现 QC → Clustering 节点 → 产物可查看
```

**验收标准**：在未装任何生信工具的机器上（mock 模式）和已装 scanpy 的机器上（auto 模式），上述链路均可完整走通；DAG 正确记录依赖与 fork；数据集版本链不被破坏。

---

## 10. 里程碑拆分

| 里程碑 | 内容 | 验收 |
|---|---|---|
| M0 | 本文档 + 仓库骨架 + 数据模型 | 建表可迁移，seed 可跑 |
| M1 | 环境发现 + Manifest + Capability Registry + Resolver | `curl` 可返回 resolver 结果 |
| M2 | Executor（mock + local）+ 事件状态机 | mock 跑通全流程 |
| M3 | Agent 规则引擎 + 上下文指针 | 「继续聚类」无需重复上下文 |
| M4 | 前端全链路 | 对话 → DAG → 产物 可视化 |
| M5 | 真实 scanpy 链路（auto 模式）+ R/DESeq2 模板 + bash 模板 | 真实环境跑通 bulk DE 与 alignment 模板 |
| M6 | **LLM Agent（v0.2）+ Local Connector + Slurm** | 三模式可回退；远程协议端到端 |

> 已实现状态：M0–M6 全部落地。M5 在本机通过 `backend/.venv311`（Python 3.11 + scanpy 1.11.5）验证真实全链；M6 的 Connector 协议在同机双端口验证（含 slurm 结构化错误传播），真实远程部署待办。

---

## 10.5 Local Connector 协议（v0.1 已实现）

```
Cloud Agent（后端）
     │  结构化 Task + 共享令牌（X-Connector-Token）
     ▼
Local Connector（持有用户 SSH 身份的机器）
     │  用户身份 / Slurm
     ▼
Remote Server / HPC
```

**连接模型**（`connector/` 独立 FastAPI 服务，复用 `app.executor.templates` / `app.env.discovery`）：

| 端点 | 说明 |
|---|---|
| `GET /health` | 连通性 + 模式（mock/local/slurm/auto） |
| `GET /discover` | 远程 Environment Discovery → Manifest（注册时握手） |
| `POST /execute` | 执行结构化 Task → ExecutionResult JSON |

- **鉴权**：请求头 `X-Connector-Token` == 部署环境变量 `CONNECTOR_TOKEN`；未设置仅限本机演示。
- **后端侧**：`LocalConnectorExecutor`（`app/executor/remote.py`）把 Task 序列化投递、解析结构化结果；Environment 行保存 `connector_url + connector_token`（**令牌非 SSH 凭据**）。
- **Slurm 支持**（Connector 内 `SlurmExecutor`）：sbatch 模板（threads/partition/mem 白名单）→ 提交 → `sacct/squeue` 轮询 → 产物收集；调度器缺失返回结构化 `SchedulerUnavailable`。
- **执行模式**：`CONNECTOR_EXECUTOR_MODE=mock|local|slurm|auto`（auto：Slurm 可用→slurm，否则本地探测，失败回退 mock）。
- **已知限制（真实远程部署前必读）**：产物路径目前为 Connector 本地绝对路径，后端按原样入库；远端文件系统不可达时需引入路径映射层（v0.2 计划）。当前同机部署不受影响。

---

## 11. 安全模型（v0.1 落地版）

1. **协议白名单**：Executor 只接受结构化 Task；命令一律由模板构造，参数经 schema/domain 二次校验。
2. **路径白名单**：输入仅允许解析自注册 Dataset 的路径；输出仅允许项目 `output/` 目录。Executor 拒绝越界路径（`..`、绝对路径逃逸）。
3. **无自由 Shell**：Agent 无任何 shell 通道；bash 能力走模板。
4. **远程（Local Connector，已实现）**：Connector 持有用户身份/SSH 凭据，后端只保存 `connector_url + 共享令牌`；权限模型（读数据/写输出/提交任务/查看任务/取消自己任务，禁止改删原始数据、禁止任意 shell）由 Connector 侧模板化执行保证。
