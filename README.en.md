<p align="center"><a href="README.en.md"><img src="https://img.shields.io/badge/English-README-blue?style=for-the-badge" alt="English"></a> <a href="README.zh.md"><img src="https://img.shields.io/badge/中文-简体中文-blue?style=for-the-badge" alt="中文版"></a> · <a href="README.md">🏠 Home</a></p>

# BioAgent · Bioinformatics Analysis Agent Platform (v0.1 MVP)

> An AI Agent work platform for bioinformatics: users collaborate with an agent that
> understands analysis workflows, drives real compute environments, executes analyses,
> and records the full process — via natural language.

Technical design & data model: [`docs/TECHNICAL_DESIGN.md`](docs/TECHNICAL_DESIGN.md).

## Implemented (MVP vertical slice + M5/M6)

```
Local machine → Environment Discovery → Environment Manifest → Capability Resolver
  → Agent (rules / LLM) understands "cluster this data" → structured Task
  → Executor (mock / local real / remote Connector + Slurm)
  → Analysis Event + Artifact + context pointer update → UI (chat / DAG / artifacts)
```

- **Data model**: Project → Conversation (one analysis thread with context pointers)
  → intent → AnalysisEvent → DAG; immutable Dataset version chain; Artifacts owned by events
- **Capability Registry**: 19 language-agnostic capabilities with multiple implementations
  (scanpy / Seurat / DESeq2 / edgeR / clusterProfiler / STAR-bash templated commands)
- **Environment Discovery**: conda envs / Python / R / in-repo venvs (`.venv*`) /
  CLI tools / Slurm / GPU → standardized Manifest; single-point failures never abort
- **Executor**: async state machine (queued → running → succeeded/failed/cancelled)
  - `mock`: pre-generates real files (matplotlib figures, CSV, HTML reports) for dev/demo/CI
  - `local`: real scanpy / R / bash template execution (**auto mode probes candidate
    runtimes one by one, skips broken envs, auto-selects a working Python 3.11 venv**)
  - `remote`: Local Connector protocol (token auth + /discover + /execute)
  - `slurm`: SlurmExecutor inside the Connector (sbatch template + sacct polling)
- **Agent Runtime**:
  - v0.1 rule engine: intent parsing, parameter extraction ("resolution 1.0"),
    automatic prerequisite chains ("cluster" auto-runs QC→Normalize→PCA→Neighbors),
    "continue" advancement, "re-cluster with another resolution" → `re_run` edge (fork)
  - v0.2 **LLM** (OpenAI-compatible, DeepSeek endpoint by default): intent parsing +
    reply generation; three modes `off/echo/real`; any failure falls back to rules
- **Conversation context**: pointer-based (current_dataset / current_phase /
  analysis_state) — "keep clustering" needs no repeated context
- **Frontend**: project list → workspace (chat panel + analysis DAG + dataset chain +
  artifact gallery + environment/capabilities + Agent status badge + compute env
  switcher + remote Connector registration)

## Quick Start

```bash
# 1. Initialize environments (first time)
bash scripts/dev.sh setup

# 2. Start everything (backend :8000 + frontend :5173)
bash scripts/dev.sh start

# Open http://localhost:5173
# Backend API docs: http://127.0.0.1:8000/docs
```

### Manual steps

```bash
# Backend
cd backend
.venv/bin/uvicorn app.main:app --port 8000          # create .venv first (see below)

# Frontend
cd frontend
npm install --cache ../.npm-cache
npx vite --port 5173                                 # /api proxied to :8000

# Demo data (HCC single-cell full flow, mock mode)
backend/.venv/bin/python scripts/seed_demo.py
```

### Backend environments (Python 3.12 + Python 3.11 scanpy, via uv)

```bash
uv venv --python 3.12 backend/.venv
UV_CACHE_DIR=$(pwd)/.uv-cache uv pip install --python backend/.venv/bin/python \
  fastapi "uvicorn[standard]" sqlalchemy pydantic pydantic-settings matplotlib

# Real scanpy runtime (optional; auto mode probes and picks a working one)
uv venv --python 3.11 backend/.venv311
UV_CACHE_DIR=$(pwd)/.uv-cache uv pip install --python backend/.venv311/bin/python \
  scanpy anndata leidenalg
```

## Executor Modes

| Mode | Behavior |
|---|---|
| `mock` | No real tools; pre-generates plausible artifacts (full demo without bioinformatics env) |
| `auto` | **Probes candidate runtimes one by one**: skips broken envs (e.g. py3.8 scanpy), runs real execution on the first working runtime; falls back to mock if all fail (recommended) |
| `local` | Real execution only; structured failure when tools are missing |

Config: env var `BIOAGENT_EXECUTOR_MODE` (prefix `BIOAGENT_`), or edit `backend/app/config.py`.

> Note: the local conda scanpy cannot import due to a Python 3.8 compatibility bug.
> `auto` mode skips it and selects `backend/.venv311` (Python 3.11 + scanpy 1.11.5)
> for real execution.

## LLM Agent (v0.2)

| Mode | Behavior |
|---|---|
| `off` (default) | Rule engine; no configuration needed |
| `echo` | Simulated LLM response; end-to-end verification of the integration path |
| `real` | OpenAI-compatible Chat Completions (DeepSeek endpoint by default) |

```bash
BIOAGENT_LLM_MODE=real \
BIOAGENT_LLM_API_KEY=sk-xxx \
BIOAGENT_LLM_MODEL=deepseek-chat \
  backend/.venv/bin/uvicorn app.main:app --port 8000
```

Intent parsing / reply generation **falls back to the rule engine** on any failure.
Debug: `POST /api/agent/intent`.

## Local Connector (remote execution)

```bash
# Start on the machine holding the user's SSH identity
CONNECTOR_TOKEN=<shared-token> CONNECTOR_EXECUTOR_MODE=auto \
  backend/.venv/bin/uvicorn connector.main:app --port 8765

# Register in backend: POST /api/projects/{id}/environments/register-remote
# Frontend: Environment/Capabilities panel → "Register remote Connector" →
#           switch compute env from the workspace top bar
```

Modes: `mock | local | slurm | auto` (auto: Slurm if available → local, else mock).

## Directory Layout

```
docs/TECHNICAL_DESIGN.md    # Technical design & data model (blueprint)
backend/
  app/
    models.py               # SQLAlchemy models (DAG edges, context pointers)
    capabilities/           # Language-agnostic capability contracts + param domains
    env/                    # Environment Discovery + Manifest
    executor/               # mock / local / remote + script templates + runtime probing
    services/               # agent(rules+LLM) · llm · execution · dag
    api/router.py           # REST API
  data/                     # SQLite + project artifacts (runtime-generated)
connector/                  # Local Connector service (/health /discover /execute + Slurm)
frontend/                   # React + Vite + TS
scripts/seed_demo.py        # Demo data: full HCC single-cell flow
scripts/dev.sh              # setup / start scripts
```

## Key APIs

| Method | Path | Description |
|---|---|---|
| POST | `/api/projects` | Create project (data location / compute location independent) |
| POST | `/api/projects/{id}/conversations` | Create conversation |
| POST | `/api/conversations/{id}/messages` | Send message (`wait=true/false`, async polling) |
| POST | `/api/projects/{id}/environments/discover` | Environment discovery → Manifest |
| GET | `/api/capabilities/resolve?capability_id=&environment_id=` | Tool→Capability resolution |
| GET | `/api/projects/{id}/dag` | Analysis DAG |
| POST | `/api/events/{id}/rerun` | Re-run (re_run edge, fork) |
| GET | `/api/artifacts/{id}/content` | Artifact content |
| GET | `/api/agent/status` | Agent mode (off/echo/real) |
| POST | `/api/agent/intent` | Intent dry-run |
| POST | `/api/projects/{id}/environments/register-remote` | Register remote Connector |
| POST | `/api/conversations/{id}/set-environment` | Switch conversation compute env |

## Roadmap

- [x] Real scanpy chain (Python 3.11 venv, verified end-to-end)
- [x] LLM Agent v0.2 (OpenAI-compatible, graceful fallback)
- [x] Remote Connector / Slurm Executor (Local Connector security model)
- [ ] R/DESeq2 & STAR real-run verification (requires R packages on target machine)
- [ ] Remote path mapping layer (cross-machine file access)
- [ ] Analysis history comparison / parameter comparison views
- [ ] More omics: spatial transcriptomics / scATAC / multiomics / methylation / WES-WGS

## Security Model (v0.1)

The Executor only accepts structured Tasks; commands are built from templates and
parameters pass domain validation; inputs are restricted to registered Dataset paths
and outputs to the project directory; no free shell channel. See docs §11.
