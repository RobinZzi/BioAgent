<p align="center"><img src="logo.svg" alt="BioAgent" width="72" /></p>

<p align="center">
  <a href="README.zh.md"><img src="https://img.shields.io/badge/中文-简体中文-blue?style=for-the-badge" alt="中文版"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/English-README-blue?style=for-the-badge" alt="English"></a>
</p>

# BioAgent · 生信分析 Agent 工作平台

> 让用户通过自然语言，与一个能够理解生物信息学分析流程、调用真实计算环境、
> 执行分析并记录全过程的 AI Agent 协作完成科研分析。
>
> Let users collaborate via natural language with an AI Agent that understands
> bioinformatics workflows, drives real compute environments, executes analyses,
> and records the full process.

## 选择语言 / Choose Language

| | |
|---|---|
| <a href="README.zh.md"><b>中文版</b></a> | 完整中文文档：快速开始、架构、API、安全模型 |
| <a href="README.en.md"><b>English</b></a> | Full English docs: quick start, architecture, API, security model |

## 项目亮点 / Highlights

- **自然语言分析** / Natural language analysis：Agent 理解「帮我聚类」「做完整分析」等意图，自动补全前置步骤 / understands "cluster this data" / "run full analysis" and auto-fills prerequisites
- **多用户可选** / Optional multi-user：默认单机免登录，认证可选（共享/部署）/ standalone (no login) by default; optional auth for shared/hosted deployments
- **Tool ≠ Capability**：32 个语言无关分析能力，scanpy / Seurat / DESeq2 / edgeR / STAR / cellranger 等多实现，覆盖 scRNA / Bulk / scATAC / 空间 / 甲基化 / WES-WGS / 32 language-agnostic capabilities with multiple implementations (scanpy / Seurat / DESeq2 / edgeR / STAR / cellranger) covering scRNA / Bulk / scATAC / spatial / methylation / WES-WGS
- **真实计算环境** / Real compute environments：本地 venv / Conda / R / Slurm / 远程 Connector（Agent 不持有 SSH 凭据）/ local venv / Conda / R / Slurm / remote Connector (Agent never holds SSH credentials)
- **可追溯可复现** / Traceable & reproducible：Analysis Event + Artifact + 分析 DAG + 数据集不可变版本链 / Analysis Event + Artifact + analysis DAG + immutable dataset version chain
- **LLM Agent**：OpenAI 兼容（默认 DeepSeek），失败自动回退规则引擎 / OpenAI-compatible (DeepSeek by default), falls back to the rule engine on failure
- **一键标准分析 / 可复现 / 错误恢复 / 异常检测 / 报告生成** / One-click standard analysis / reproducibility / error recovery / anomaly detection / report generation：完整科研闭环 / complete research loop
- **异步状态机** / Async state machine：queued → running → succeeded/failed/cancelled，mock/本地/远程三级执行 / mock / local / remote execution

## 快速体验 / Quick Start

```bash
bash scripts/dev.sh setup    # 初始化环境（首次）/ initialize environments (first time)
bash scripts/dev.sh start    # 启动后端 :8000 + 前端 :5173 / start backend :8000 + frontend :5173
# 打开 http://localhost:5173 / open http://localhost:5173
```

详细文档见 <a href="README.zh.md">中文版</a> / <a href="README.en.md">English</a>；
技术方案与数据模型见 <a href="docs/TECHNICAL_DESIGN.md">docs/TECHNICAL_DESIGN.md</a>。
