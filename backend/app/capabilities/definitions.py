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
    "raw": 0, "trimmed": 1, "aligned": 2, "qc": 1, "normalized": 2, "de": 3,
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
    # Bulk RNA（fastq 下机流水线）
    "bulk_rna.fastqc": [],
    "bulk_rna.trimming": ["bulk_rna.fastqc"],
    "bulk_rna.alignment": ["bulk_rna.trimming"],
    "bulk_rna.quantification": ["bulk_rna.alignment"],
    # Bulk RNA（count matrix 分析链）
    "bulk_rna.inspect": [],
    "bulk_rna.qc": [],
    "bulk_rna.normalization": ["bulk_rna.qc"],
    "bulk_rna.differential_expression": ["bulk_rna.normalization"],
    "bulk_rna.volcano": ["bulk_rna.differential_expression"],
    "bulk_rna.heatmap": ["bulk_rna.differential_expression"],
    "bulk_rna.go_enrichment": ["bulk_rna.differential_expression"],
    "bulk_rna.gsea": ["bulk_rna.differential_expression"],
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
CELLTYPIST = _impl("celltypist", "python", "conda", ["celltypist"])
PY_OMICS = _impl("omics-python", "python", "conda", ["scanpy", "anndata"], default=True)
METHYLATION_R = _impl("methylKit", "r", "r", ["methylKit"], default=True)
GATK_BASH = _impl("gatk", "bash", "shell", ["gatk"], default=True)
DESEQ2 = _impl("DESeq2", "r", "r", ["DESeq2"], default=True)
EDGER = _impl("edgeR", "r", "r", ["edgeR"])
STAR_BASH = _impl("star", "bash", "shell", ["star", "samtools"], default=True)
FASTQC_BASH = _impl("fastqc", "bash", "shell", ["fastqc"], default=True)
CUTADAPT_BASH = _impl("cutadapt", "bash", "shell", ["cutadapt"], default=True)
FEATURECOUNTS_BASH = _impl("featureCounts", "bash", "shell", ["featureCounts"], default=True)
CELLRANGER_BASH = _impl("cellranger", "bash", "shell", ["cellranger"], default=True)
PY_BULK = _impl("python-bulk", "python", "conda", ["pandas", "matplotlib"], default=True)
R_CLUSTERPROFILER = _impl("clusterProfiler", "r", "r", ["clusterProfiler"], default=True)

CAPABILITIES: list[dict] = [
    # ================================================================ scRNA
    _cap(
        "scrna.import_10x", "10x 下机导入", "scrna", "fastq", "raw", "raw", True,
        [CELLRANGER_BASH],
        {"sample_id": _p("string", "sample1", description="样本 ID（cellranger --sample）"),
         "reference": _p("string", "", description="cellranger 参考基因组路径"),
         "expect_cells": _p("integer", 5000, minimum=100, maximum=100000, description="预期细胞数")},
        {"reports": ["cellranger_report.html"]},
        "Cell Ranger count：10x 下机 fastq → count matrix / h5ad，接入单细胞分析链。",
        keywords=["cellranger", "10x", "单细胞下机", "下机单细胞", "cell count"],
    ),
    _cap(
        "scrna.import_mtx", "10x 矩阵导入", "scrna", "other", "raw", "raw", True,
        [SCANPY],
        {},
        {"reports": ["import_report.html"]},
        "读取 10x 矩阵市场格式目录（matrix.mtx + genes.tsv + barcodes.tsv）→ h5ad。",
        keywords=["mtx", "10x 矩阵", "矩阵导入", "matrix market", "读入矩阵"],
    ),
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
        [SCANPY, CELLTYPIST],
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
        "bulk_rna.differential_expression", "差异表达", "bulk_rna", "bulk_rna", "normalized", "de", True,
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
    # ================================================================ fastq 下机流水线
    _cap(
        "bulk_rna.fastqc", "FastQC 质控", "bulk_rna", "fastq", "raw", "raw", False,
        [FASTQC_BASH],
        {},
        {"reports": ["fastqc_report.html"]},
        "下机 fastq 质量检查（FastQC：碱基质量、GC 含量、接头等）。",
        keywords=["fastqc", "下机质量", "碱基质量"],
    ),
    _cap(
        "bulk_rna.trimming", "去接头裁切", "bulk_rna", "fastq", "raw", "trimmed", True,
        [CUTADAPT_BASH],
        {"adapters": _p("string", "auto", description="接头序列（auto=自动识别，或具体序列）"),
         "min_length": _p("integer", 20, minimum=10, maximum=100, description="最短保留长度")},
        {"reports": ["trimming_report.html"]},
        "cutadapt 去接头与低质量裁切（模板化 bash 命令）。",
        keywords=["trimming", "trim", "裁切", "去接头", "cutadapt"],
    ),
    _cap(
        "bulk_rna.alignment", "序列比对", "bulk_rna", "fastq", "trimmed", "aligned", True,
        [STAR_BASH],
        {"genome_dir": _p("string", "", description="STAR 基因组索引目录"),
         "threads": _p("integer", 4, minimum=1, maximum=64, description="线程数")},
        {"reports": ["alignment_report.html"]},
        "STAR 序列比对 + samtools 排序（模板化 bash 命令，白名单参数）。",
        keywords=["比对", "alignment", "star", "bam"],
    ),
    _cap(
        "bulk_rna.quantification", "基因定量", "bulk_rna", "fastq", "aligned", "raw", True,
        [FEATURECOUNTS_BASH],
        {"gtf": _p("string", "", description="GTF 注释文件路径"),
         "feature_type": _p("string", "exon", enum=["exon", "gene", "transcript"], description="定量特征")},
        {"tables": ["counts.csv"], "reports": ["quantification_report.html"]},
        "featureCounts 基因计数（输出 count matrix，接入后续差异表达分析）。",
        keywords=["定量", "quantification", "featurecounts", "counts", "count matrix"],
    ),
    # ================================================================ 更多组学
    _cap(
        "scatac.qc", "ATAC 质控", "scatac", "scrna", "raw", "qc", True,
        [PY_OMICS],
        {"min_fragments": _p("integer", 1000, minimum=100, description="最少片段数"),
         "max_tss_enrichment": _p("number", 5, minimum=1, maximum=30, description="TSS 富集阈值")},
        {"figures": ["atac_qc.png"], "reports": ["atac_qc_report.html"]},
        "scATAC-seq 质控：TSS 富集、片段数、双细胞率检查。",
        keywords=["atac", "scatac", "atac 质控", "染色质开放性"],
    ),
    _cap(
        "scatac.clustering", "ATAC 聚类", "scatac", "scrna", "qc", "clustered", True,
        [PY_OMICS],
        {"resolution": _p("number", 0.8, enum=[0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0], description="聚类分辨率")},
        {"figures": ["atac_umap.png"], "reports": []},
        "scATAC-seq 峰值聚类（基于染色质开放性特征）。",
        keywords=["atac 聚类", "scatac 聚类"],
    ),
    _cap(
        "spatial.qc", "空间质控", "spatial", "scrna", "raw", "qc", True,
        [PY_OMICS],
        {"min_genes_per_spot": _p("integer", 100, minimum=10, description="每 spot 最少基因数")},
        {"figures": ["spatial_qc.png"], "reports": []},
        "空间转录组质控：spot 基因数、组织覆盖检查。",
        keywords=["空间", "spatial", "空间质控"],
    ),
    _cap(
        "spatial.clustering", "空间聚类", "spatial", "scrna", "qc", "clustered", True,
        [PY_OMICS],
        {"resolution": _p("number", 0.5, enum=[0.1, 0.3, 0.5, 0.8, 1.0, 1.5, 2.0], description="聚类分辨率")},
        {"figures": ["spatial_clusters.png"], "reports": []},
        "空间转录组 spot 聚类（结合空间位置与表达）。",
        keywords=["空间聚类", "spatial 聚类"],
    ),
    _cap(
        "methylation.qc", "甲基化质控", "methylation", "bulk_rna", "raw", "qc", True,
        [METHYLATION_R],
        {"min_coverage": _p("integer", 5, minimum=1, description="最小覆盖度")},
        {"figures": ["methylation_qc.png"], "reports": ["methylation_qc_report.html"]},
        "DNA 甲基化质控：CpG 覆盖、beta 值分布检查。",
        keywords=["甲基化", "methylation", "甲基化质控"],
    ),
    _cap(
        "methylation.differential", "差异甲基化", "methylation", "bulk_rna", "qc", "de", False,
        [METHYLATION_R],
        {"padj_cutoff": _p("number", 0.05, minimum=0, maximum=1, description="校正 p 值阈值")},
        {"figures": ["dmp_volcano.png"], "tables": ["dmp.csv"], "reports": []},
        "差异甲基化位点/区域（DMP/DMR）分析。",
        keywords=["差异甲基化", "dmr", "dmp", "甲基化差异"],
    ),
    _cap(
        "variant.calling", "变异检测", "variant", "fastq", "aligned", "variants", True,
        [GATK_BASH],
        {"ref_genome": _p("string", "", description="参考基因组路径"),
         "min_qual": _p("integer", 30, minimum=10, maximum=90, description="最小质量值")},
        {"tables": ["variants.vcf"], "reports": ["variant_calling_report.html"]},
        "WES/WGS 变异检测（GATK HaplotypeCaller 模板）。",
        keywords=["变异检测", "variant", "wes", "wgs", "gatk", "vcf"],
    ),
    _cap(
        "variant.annotation", "变异注释", "variant", "fastq", "variants", "annotated", False,
        [GATK_BASH],
        {"db": _p("string", "clinvar", enum=["clinvar", "gnomad", "dbsnp"], description="注释数据库")},
        {"tables": ["variants_annotated.csv"], "reports": []},
        "变异注释（ClinVar/gnomAD/dbSNP，VEP 模板）。",
        keywords=["变异注释", "annotation", "vep", "clinvar"],
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
