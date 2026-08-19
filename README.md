<p align="center">
  <a href="README.zh.md"><img src="https://img.shields.io/badge/中文-简体中文-blue?style=for-the-badge" alt="中文版"></a>
  <a href="README.en.md"><img src="https://img.shields.io/badge/English-README-blue?style=for-the-badge" alt="English"></a>
</p>

# 🧬 BioAgent · 生信分析 Agent 工作平台

> 让用户通过自然语言，与一个能够理解生物信息学分析流程、调用真实计算环境、
> 执行分析并记录全过程的 AI Agent 协作完成科研分析。
>
> Let users collaborate via natural language with an AI Agent that understands
> bioinformatics workflows, drives real compute environments, executes analyses,
> and records the full process.

## 🌏 选择语言 / Choose Language

| | |
|---|---|
| <a href="README.zh.md"><b>🇨🇳 中文版</b></a> | 完整中文文档：快速开始、架构、API、安全模型 |
| <a href="README.en.md"><b>🇬🇧 English</b></a> | Full English docs: quick start, architecture, API, security model |

## ✨ 项目亮点 / Highlights

- **自然语言分析**：Agent 理解「帮我聚类」「继续分析」等意图，自动补全前置步骤
- **Tool ≠ Capability**：19 个语言无关分析能力，scanpy / Seurat / DESeq2 / edgeR / STAR 多实现
- **真实计算环境**：本地 venv / Conda / R / Slurm / 远程 Connector（Agent 不持有 SSH 凭据）
- **可追溯可复现**：Analysis Event + Artifact + 分析 DAG + 数据集不可变版本链
- **LLM Agent (v0.2)**：OpenAI 兼容（默认 DeepSeek），失败自动回退规则引擎
- **异步状态机**：queued → running → succeeded/failed/cancelled，mock/本地/远程三级执行

## 快速体验 / Quick Start

```bash
bash scripts/dev.sh setup    # 初始化环境（首次）
bash scripts/dev.sh start    # 启动后端 :8000 + 前端 :5173
# 打开 http://localhost:5173
```

详细文档见 <a href="README.zh.md">中文版</a> / <a href="README.en.md">English</a>；
技术方案与数据模型见 <a href="docs/TECHNICAL_DESIGN.md">docs/TECHNICAL_DESIGN.md</a>。
