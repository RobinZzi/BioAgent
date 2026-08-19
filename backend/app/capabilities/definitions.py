"""Capability 定义（v0.1）。

Capability 是语言无关的分析意图契约：
  - input/output/dataset 语义与语言无关
  - implementations 绑定具体语言与运行时（python / r / bash）
  - 参数使用定义域约束（enum / min-max），Executor 执行前二次校验

见 docs/TECHNICAL_DESIGN.md §3。
"""

# ---------------------------------------------------------------- 阶段序
# scrna 数据集阶段（用于前置条件判定与上下文指针）
SCRNA_PHASE_RANK = {
    "raw": 0, "qc": 1, "normalized": 2, "pca": 3, "neighbors": 4,
    "umap": 5, "clustered": 6, "annotated": 7, "marker_genes": 7,
}
BULK_PHASE_RANK = {
    "raw": 0, "qc": 1, "normalized": 2, "de": 3,
}

# 前置依赖（capability → 所需前置 capability 列表）
PREREQ = {
    # scRNA
    "scrna.inspect": [],
    "scrna.qc": [],
    "scrna.normalization": ["scrna.qc"],
    "scrna.hvg": ["scrna.normalization"],
    "scrna.pca": ["scrna.normalization"],
    "scrna.neighbors": ["scrna.pca"],
    "scrna.umap": ["scrna.neighbors"],
    "scrna.clustering": ["scrna.neighbors"],
    "scrna.marker_genes": ["scrna.clustering"],
    "scrna.annotation": ["scrna.clustering"],
    # Bulk RNA
    "bulk_rna.inspect": [],
    "bulk_rna.qc": [],
    "bulk_rna.normalization": ["bulk_rna.qc"],
    "bulk_rna.differential_expression": ["bulk_rna.normalization"],
    "bulk_rna.volcano": ["bulk_rna.differential_expression"],
    "bulk_rna.heatmap": ["bulk_rna.differential_expression"],
    "bulk_rna.go_enrichment": ["bulk_rna.differential_expression"],
    "bulk_rna.gsea": ["bulk_rna.differential_expression"],
    # bash/CLI
    "bulk_rna.alignment": [],
}


def _impl(impl_id: str, language: str, runtime_hint: str, tools: list[str], default: bool = False) -> dict:
    return {"id": impl_id, "language": language, "runtime_hint": runtime_hint,
            "tools": tools, "default": default}


def _cap(
    capability_id: str,
    name: str,
    domain: str,
    dataset_dtype: str,
    requires_phase: str,
    resulting_phase: str | None,
    produces_dataset: bool,
    implementations: list[dict],
    parameters: dict,
    outputs: dict | None = None,
    description: str = "",
    keywords: list[str] | None = None,
) -> dict:
    """构造一个 Capability 定义。resulting_phase=None 表示不改变数据集阶段（纯分析型）。"""
    return {
        "capability_id": capability_id,
        "name": name,
        "domain": domain,
        "dataset_dtype": dataset_dtype,
        "requires_phase": requires_phase,
        "resulting_phase": resulting_phase,
        "produces_dataset": produces_dataset,
        "implementations": implementations,
        "parameters": parameters,
        "outputs": outputs or {"figures": [], "tables": [], "reports": []},
        "description": description,
        "keywords": keywords or [],
        "schema_version": 1,
    }


def _p(type_: str, default=None, enum=None, minimum=None, maximum=None, description: str = "") -> dict:
    d = {"type": type_, "description": description}
    if default is not None:
        d["default"] = default
    if enum is not None:
        d["enum"] = enum
    if minimum is not None:
        d["minimum"] = minimum
    if maximum is not None:
        d["maximum"] = maximum
    return d


SCANPY = _impl("scanpy", "python", "conda", ["scanpy", "anndata"], default=True)
SEURAT = _impl("seurat", "r", "renv", ["Seurat"])
DESEQ2 = _impl("DESeq2", "r", "r", ["DESeq2"], default=True)
EDGER = _impl("edgeR", "r", "r", ["edgeR"])
STAR_BASH = _impl("star", "bash", "shell", ["star", "samtools"], default=True)
PY_BULK = _impl("python-bulk", "python", "conda", ["pandas", "matplotlib"], default=True)
R_CLUSTERPROFILER = _impl("clusterProfiler", "r", "r", ["clusterProfiler"], default=True)

CAPABILITIES: list[dict] = [
    # ================================================================ scRNA
    _cap(
        "scrna.inspect", "数据检查", "scrna", "scrna", "raw", "raw", False,
        [SCANPY],
        {"n_cells_sample": _p("integer", 500, minimum=10, description="采样细胞数")},
        {"figures": ["inspect_summary.png"], "reports": ["inspect_report.html"]},
        "检查单细胞数据基本结构：细胞数、基因数、样本组成、稀疏度。",
        keywords=["检查", "看看", "inspect", "数据质量", "概况"],
    ),
    _cap(
        "scrna.qc", "细胞 QC", "scrna", "scrna", "raw", "qc", True,
        [SCANPY],
        {
            "min_genes": _p("integer", 200, minimum=1, description="最少基因数"),
            "max_genes": _p("integer", 5000, minimum=1, description="最多基因数"),
            "max_mito_pct": _p("number", 20, minimum=0, maximum=100, description="线粒体基因占比上限"),
        },
        {"figures": ["qc_metrics.png", "qc_filtering.png"], "reports": ["qc_report.html"]},
        "细胞质控：按基因数/线粒体占比过滤低质量细胞，生成质控报告。",
        keywords=["qc", "质控", "质量"],
    ),
    _cap(
        "scrna.normalization", "标准化", "scrna", "scrna", "qc", "normalized", True,
        [SCANPY],
        {"target_sum": _p("number", 1e4, description="缩放目标（CPM 类归一化）")},
        {"figures": [], "reports": []},
        "对数归一化与缩放（scanpy.pp.normalize_total + log1p）。",
        keywords=["标准化", "normalize", "normalization", "归一化"],
    ),
    _cap(
        "scrna.hvg", "高变基因", "scrna", "scrna", "normalized", "normalized", True,
        [SCANPY],
        {"n_top_genes": _p("integer", 2000, minimum=1, maximum=5000, description="高变基因数")},
        {"figures": ["hvg_dispersion.png"], "reports": []},
        "识别高变基因（HVG）。",
        keywords=["hvg", "高变基因"],
    ),
    _cap(
        "scrna.pca", "PCA 降维", "scrna", "scrna", "normalized", "pca", True,
        [SCANPY],
        {"n_comps": _p("integer", 50, minimum=2, maximum=100, description="主成分数")},
        {"figures": ["pca_variance.png"], "reports": []},
        "PCA 降维。",
        keywords=["pca"],
    ),
    _cap(
        "scrna.neighbors", "邻接图", "scrna", "scrna", "pca", "neighbors", True,
        [SCANPY],
        {"n_neighbors": _p("integer", 15, minimum=2, maximum=100, description="邻居数"),
         "n_pcs": _p("integer", 30, minimum=2, maximum=100, description="使用的 PC 数")},
        {"figures": [], "reports": []},
        "构建 KNN 邻接图。",
        keywords=["neighbors", "邻接"],
    ),
    _cap(
        "scrna.umap", "UMAP 可视化", "scrna", "scrna", "neighbors", "umap", True,
        [SCANPY],
        {"min_dist": _p("number", 0.5, enum=[0.1, 0.3, 0.5, 0.8, 1.0], description="UMAP min_dist")},
        {"figures": ["umap.png"], "reports": []},
        "UMAP 二维可视化。",
        keywords=["umap"],
    ),
    _cap(
        "scrna.clustering", "聚类", "scrna", "scrna", "neighbors", "clustered", True,
        [SCANPY, SEURAT],
        {"resolution": _p("number", 0.5, enum=[0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0], description="Leiden 分辨率")},
        {"figures": ["umap_clusters.png"], "reports": ["clustering_report.html"]},
        "Leiden 聚类（scanpy）或 Louvain（Seurat）。",
        keywords=["聚类", "cluster", "clustering", "leiden"],
    ),
    _cap(
        "scrna.marker_genes", "标记基因", "scrna", "scrna", "clustered", "marker_genes", False,
        [SCANPY],
        {"n_markers": _p("integer", 20, minimum=1, maximum=200, description="每簇标记基因数")},
        {"figures": ["marker_heatmap.png"], "tables": ["marker_genes.csv"], "reports": []},
        "计算各簇标记基因（rank_genes_groups）。",
        keywords=["marker", "标记基因"],
    ),
    _cap(
        "scrna.annotation", "细胞注释", "scrna", "scrna", "clustered", "annotated", True,
        [SCANPY],
        {"method": _p("string", "marker_based", enum=["marker_based", "celltypist"], description="注释方法")},
        {"figures": ["annotation_umap.png"], "tables": ["cell_composition.csv"], "reports": ["annotation_report.html"]},
        "基于标记基因的细胞类型注释。",
        keywords=["注释", "annotation", "annotate", "细胞类型"],
    ),
    # ================================================================ Bulk RNA
    _cap(
        "bulk_rna.inspect", "数据检查", "bulk_rna", "bulk_rna", "raw", "raw", False,
        [PY_BULK],
        {},
        {"figures": ["inspect_summary.png"], "reports": ["inspect_report.html"]},
        "检查 bulk RNA 表达矩阵与样本元数据。",
        keywords=["bulk 检查"],
    ),
    _cap(
        "bulk_rna.qc", "QC", "bulk_rna", "bulk_rna", "raw", "qc", True,
        [PY_BULK],
        {"min_counts": _p("integer", 10, minimum=1, description="基因最小总计数")},
        {"figures": ["qc_metrics.png"], "reports": []},
        "bulk RNA 质控：低表达基因过滤、样本检查。",
        keywords=["bulk qc", "bulk 质控"],
    ),
    _cap(
        "bulk_rna.normalization", "标准化", "bulk_rna", "bulk_rna", "qc", "normalized", True,
        [PY_BULK],
        {"method": _p("string", "tmm", enum=["tmm", "cpm", "vst"], description="标准化方法")},
        {"figures": [], "reports": []},
        "bulk RNA 标准化（TMM/CPM/VST）。",
        keywords=["bulk 标准化"],
    ),
    _cap(
        "bulk_rna.differential_expression", "差异表达", "bulk_rna", "bulk_rna", "normalized", "de", False,
        [DESEQ2, EDGER],
        {"design": _p("string", "condition", description="比较设计（如 condition）"),
         "padj_cutoff": _p("number", 0.05, minimum=0.0, maximum=1.0, description="校正 p 值阈值")},
        {"tables": ["deseq2_results.csv"], "reports": ["de_report.html"]},
        "DESeq2 / edgeR 差异表达分析。",
        keywords=["差异表达", "de", "deseq", "edgeR", "差异基因"],
    ),
    _cap(
        "bulk_rna.volcano", "火山图", "bulk_rna", "bulk_rna", "de", "de", False,
        [PY_BULK],
        {"padj_cutoff": _p("number", 0.05, minimum=0.0, maximum=1.0, description="显著性阈值"),
         "log2fc_cutoff": _p("number", 1.0, description="log2FC 阈值")},
        {"figures": ["volcano.png"], "reports": []},
        "差异表达火山图。",
        keywords=["volcano", "火山图"],
    ),
    _cap(
        "bulk_rna.heatmap", "热图", "bulk_rna", "bulk_rna", "de", "de", False,
        [PY_BULK],
        {"n_top_genes": _p("integer", 50, minimum=5, maximum=500, description="展示基因数")},
        {"figures": ["de_heatmap.png"], "reports": []},
        "显著差异基因热图。",
        keywords=["heatmap", "热图"],
    ),
    _cap(
        "bulk_rna.go_enrichment", "GO 富集", "bulk_rna", "bulk_rna", "de", "de", False,
        [R_CLUSTERPROFILER],
        {"ontology": _p("string", "BP", enum=["BP", "MF", "CC"], description="GO 本体")},
        {"figures": ["go_barplot.png"], "tables": ["go_enrichment.csv"], "reports": []},
        "GO 功能富集分析。",
        keywords=["go", "富集", "enrichment"],
    ),
    _cap(
        "bulk_rna.gsea", "GSEA", "bulk_rna", "bulk_rna", "de", "de", False,
        [R_CLUSTERPROFILER],
        {"n_permutations": _p("integer", 1000, minimum=100, maximum=10000, description="置换次数")},
        {"figures": ["gsea_plot.png"], "tables": ["gsea_results.csv"], "reports": []},
        "基因集富集分析（GSEA）。",
        keywords=["gsea"],
    ),
    # ================================================================ bash/CLI
    _cap(
        "bulk_rna.alignment", "序列比对", "bulk_rna", "fastq", "raw", "raw", True,
        [STAR_BASH],
        {"genome_dir": _p("string", "", description="STAR 基因组索引目录"),
         "threads": _p("integer", 4, minimum=1, maximum=64, description="线程数")},
        {"reports": ["alignment_report.html"]},
        "STAR 序列比对 + samtools 排序（模板化 bash 命令，白名单参数）。",
        keywords=["比对", "alignment", "star", "bam"],
    ),
]

CAPABILITIES_BY_ID: dict[str, dict] = {c["capability_id"]: c for c in CAPABILITIES}


def get_capability(capability_id: str) -> dict | None:
    return CAPABILITIES_BY_ID.get(capability_id)


def list_capabilities(domain: str | None = None) -> list[dict]:
    if domain is None:
        return CAPABILITIES
    return [c for c in CAPABILITIES if c["domain"] == domain]


def phase_rank(domain: str, phase: str) -> int:
    table = SCRNA_PHASE_RANK if domain == "scrna" else BULK_PHASE_RANK
    return table.get(phase, -1)


def validate_parameters(capability: dict, params: dict) -> tuple[dict, list[str]]:
    """按定义域校验并补默认值。返回 (校验后的参数, 错误列表)。"""
    spec = capability["parameters"]
    validated: dict = {}
    errors: list[str] = []
    for key, pspec in spec.items():
        value = params.get(key, pspec.get("default"))
        if value is None:
            errors.append(f"缺少参数 {key}")
            continue
        if pspec.get("enum") is not None and value not in pspec["enum"]:
            errors.append(f"参数 {key}={value} 不在允许范围 {pspec['enum']}")
            continue
        if pspec.get("minimum") is not None and value < pspec["minimum"]:
            errors.append(f"参数 {key}={value} 小于最小值 {pspec['minimum']}")
            continue
        if pspec.get("maximum") is not None and value > pspec["maximum"]:
            errors.append(f"参数 {key}={value} 大于最大值 {pspec['maximum']}")
            continue
        validated[key] = value
    return validated, errors
