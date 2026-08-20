"""Mock Executor：不调用真实工具，按 capability 预生成合理产物。

用途：开发 / 演示 / CI。产物是真实的文件（matplotlib PNG、CSV、HTML 报告），
h5ad 为占位文件 + JSON sidecar 元数据。确定性：同一 event id 结果可复现。
"""
import csv
import hashlib
import json
import random
from pathlib import Path

from .base import ArtifactOut, BaseExecutor, DatasetOut, ExecutionResult, TaskSpec

_MIME = {
    "png": "image/png", "csv": "text/csv", "html": "text/html",
    "h5ad": "application/x-hdf5", "bam": "application/octet-stream",
    "log": "text/plain", "pdf": "application/pdf",
}

GENE_POOL = [
    "CD3D", "CD3E", "CD4", "CD8A", "CD8B", "CD14", "CD68", "LYZ", "FCGR3A",
    "NKG7", "GNLY", "MS4A1", "CD79A", "CD79B", "JCHAIN", "MZB1", "IGKC",
    "CST3", "FCER1A", "CLEC9A", "LILRA4", "IL3RA", "GZMB", "PRF1", "KLRB1",
    "CCL5", "GZMK", "CX3CR1", "SELL", "CCR7", "LEF1", "TCF7", "IL7R",
]


def _seed_for(task_id: str) -> int:
    return int(hashlib.md5(task_id.encode()).hexdigest()[:8], 16)


def _mime(name: str) -> str:
    return _MIME.get(Path(name).suffix.lstrip("."), "application/octet-stream")


def _write_fig(path: Path, title: str, draw) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(6.5, 4.5))
    draw(ax)
    ax.set_title(title, fontsize=11)
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _write_html(path: Path, title: str, sections: list[tuple[str, str]]) -> None:
    body = "\n".join(
        f"<h3>{h}</h3><div class='sec'>{b}</div>" for h, b in sections)
    path.write_text(f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>{title}</title><style>
body{{font-family:-apple-system,'PingFang SC',sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222}}
h1{{font-size:20px}}h3{{margin-top:20px;color:#0b5cad}}
.sec{{background:#f7f9fc;border:1px solid #e3e8f0;border-radius:8px;padding:12px;font-size:13px;line-height:1.7}}
table{{border-collapse:collapse;width:100%;font-size:12px;margin:6px 0}}
th,td{{border:1px solid #dde3ec;padding:4px 8px;text-align:left}}
th{{background:#eef3fb}}
.badge{{display:inline-block;background:#e6f4ea;color:#137333;border-radius:10px;padding:1px 8px;font-size:12px}}
</style></head><body><h1>{title}</h1>{body}</body></html>""")


def _html_table(headers: list[str], rows: list[list]) -> str:
    h = "".join(f"<th>{c}</th>" for c in headers)
    r = "".join("<tr>" + "".join(f"<td>{c}</td>" for c in row) + "</tr>" for row in rows)
    return f"<table><tr>{h}</tr>{r}</table>"


class MockExecutor(BaseExecutor):
    """预置产物执行器。"""

    def execute(self, task: TaskSpec, capability: dict) -> ExecutionResult:
        rng = random.Random(_seed_for(task.task_id))
        log: list[str] = []
        artifacts: list[ArtifactOut] = []
        datasets: list[DatasetOut] = []
        outdir = Path(task.output_dir)
        outdir.mkdir(parents=True, exist_ok=True)

        cap_id = task.capability_id
        params = task.parameters
        input_name = Path(task.input_dataset_path or "input").name
        input_stem = Path(input_name).stem
        log.append(f"[mock] capability={cap_id} implementation={task.implementation}")
        log.append(f"[mock] input={task.input_dataset_path} params={json.dumps(params, ensure_ascii=False)}")

        def add_file(kind: str, name: str) -> ArtifactOut:
            p = outdir / name
            art = ArtifactOut(kind=kind, name=name, path=str(p), mime=_mime(name))
            artifacts.append(art)
            return art

        def add_dataset(name: str, dtype: str, fmt: str, phase: str, meta: dict) -> None:
            loc = outdir / f"{name}"
            loc.write_bytes(b"\x89HDF placeholder (mock)")   # 占位文件
            meta = {**meta, "mock": True}
            (outdir / f"{name}.meta.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2))
            datasets.append(DatasetOut(name=name, dtype=dtype, format=fmt, phase=phase,
                                       location=str(loc), metadata=meta))

        metrics: dict = {}

        # ------------------------------------------------------------ scRNA
        if cap_id == "scrna.import_10x":
            cells = params.get("expect_cells", 5000)
            genes = rng.randint(15000, 25000)
            mean_reads = rng.randint(20000, 50000)
            metrics = {"cells": cells, "genes": genes, "sample_id": params.get("sample_id"),
                       "mean_reads_per_cell": mean_reads}
            add_dataset(f"{input_stem}_{params.get('sample_id','sample')}_filtered.h5ad",
                        "scrna", "h5ad", "raw",
                        {"cells": cells, "genes": genes, "source": "cellranger count"})
            _write_html(outdir / "cellranger_report.html", "Cell Ranger 导入报告",
                        [("导入结果", _html_table(["指标", "数值"], [
                            ["样本", params.get("sample_id", "sample1")],
                            ["过滤后细胞数", f"{cells:,}"], ["基因数", f"{genes:,}"],
                            ["平均每细胞 reads", f"{mean_reads:,}"]])),
                         ("说明", "Cell Ranger count 输出已转为 h5ad，可进入单细胞分析链。")])
            add_file("report", "cellranger_report.html")
            log.append(f"[mock] cellranger: {cells:,} cells x {genes:,} genes")

        elif cap_id == "scrna.inspect":
            n_cells = rng.randint(8000, 15000)
            n_genes = rng.randint(12000, 22000)
            n_samples = rng.randint(2, 6)
            metrics = {"n_cells": n_cells, "n_genes": n_genes, "n_samples": n_samples,
                       "sparsity": round(rng.uniform(0.85, 0.97), 3)}
            cells_per_sample = [n_cells // n_samples] * n_samples
            cells_per_sample[-1] += n_cells - sum(cells_per_sample)

            def draw(ax):
                ax.bar([f"S{i+1}" for i in range(n_samples)], cells_per_sample, color="#4c8bf5")
                ax.set_ylabel("cells")

            _write_fig(outdir / "inspect_summary.png", "Cells per sample", draw)
            add_file("figure", "inspect_summary.png")
            _write_html(outdir / "inspect_report.html", "数据检查报告",
                        [("基本信息", _html_table(["指标", "数值"], [
                            ["细胞数", f"{n_cells:,}"], ["基因数", f"{n_genes:,}"],
                            ["样本数", n_samples], ["稀疏度", f"{metrics['sparsity']*100:.1f}%"]])),
                         ("说明", "该数据可直接进入 QC 流程。")])
            add_file("report", "inspect_report.html")
            log.append(f"[mock] inspected {n_cells} cells x {n_genes} genes")

        elif cap_id == "scrna.qc":
            before = rng.randint(8000, 15000)
            keep = int(before * rng.uniform(0.86, 0.95))
            median_genes = rng.randint(800, 1400)
            mito = round(rng.uniform(4.0, 12.0), 1)
            metrics = {"cells_before": before, "cells_after": keep,
                       "median_genes": median_genes, "median_mito_pct": mito,
                       "min_genes": params.get("min_genes"), "max_mito_pct": params.get("max_mito_pct")}

            def draw1(ax):
                ax.boxplot([[rng.randint(300, 3000) for _ in range(200)],
                            [rng.randint(200, 2600) for _ in range(200)]],
                           tick_labels=["before", "after"])
                ax.set_ylabel("n_genes")

            _write_fig(outdir / "qc_metrics.png", "QC metrics (n_genes)", draw1)
            add_file("figure", "qc_metrics.png")

            def draw2(ax):
                x = [rng.uniform(1000, 40000) for _ in range(400)]
                y = [min(rng.uniform(0, 45), params.get("max_mito_pct", 20) * 1.5) for _ in range(400)]
                ax.scatter(x, y, s=3, alpha=0.5)
                ax.axhline(params.get("max_mito_pct", 20), color="r", ls="--", lw=1)
                ax.set_xlabel("total counts"); ax.set_ylabel("mito %")

            _write_fig(outdir / "qc_filtering.png", "QC filtering (mito threshold)", draw2)
            add_file("figure", "qc_filtering.png")
            _write_html(outdir / "qc_report.html", "QC 质控报告",
                        [("质控指标", _html_table(["指标", "数值"], [
                            ["过滤前细胞数", f"{before:,}"], ["过滤后细胞数", f"{keep:,}"],
                            ["过滤比例", f"{(before-keep)/before*100:.1f}%"],
                            ["中位基因数", median_genes], ["中位线粒体占比", f"{mito}%"]])),
                         ("结论", f"保留 {keep:,} 个细胞（过滤 {before-keep:,} 个）。线粒体占比阈值 {params.get('max_mito_pct', 20)}%。")])
            add_file("report", "qc_report.html")
            add_dataset(f"{input_stem}_qc.h5ad", "scrna", "h5ad", "qc",
                        {"n_cells": keep, "n_genes": rng.randint(12000, 20000),
                         "filtered_from": before, "params": params})
            log.append(f"[mock] QC: {before} -> {keep} cells")

        elif cap_id == "scrna.normalization":
            metrics = {"target_sum": params.get("target_sum")}
            add_dataset(f"{input_stem}_normalized.h5ad", "scrna", "h5ad", "normalized",
                        {"target_sum": params.get("target_sum"), "method": "log1p"})
            log.append("[mock] normalized + log1p")

        elif cap_id == "scrna.hvg":
            n = params.get("n_top_genes", 2000)
            metrics = {"n_hvg": n}

            def draw(ax):
                xs = [rng.uniform(0, 1) for _ in range(2000)]
                ys = [rng.uniform(0, 2) for _ in range(2000)]
                ax.scatter(xs, ys, s=1, alpha=0.3, color="#999")
                ax.axvline(0.3, color="r", ls="--", lw=1)
                ax.set_xlabel("mean expression"); ax.set_ylabel("dispersion")

            _write_fig(outdir / "hvg_dispersion.png", f"HVG (top {n})", draw)
            add_file("figure", "hvg_dispersion.png")
            add_dataset(f"{input_stem}_hvg.h5ad", "scrna", "h5ad", "normalized",
                        {"n_hvg": n})
            log.append(f"[mock] selected {n} HVGs")

        elif cap_id == "scrna.pca":
            n_comps = params.get("n_comps", 50)
            metrics = {"n_comps": n_comps}

            def draw(ax):
                ratios = [rng.uniform(0.005, 0.06) for _ in range(n_comps)]
                ratios.sort(reverse=True)
                ax.plot(range(1, n_comps + 1), ratios, marker="o", ms=3)
                ax.set_xlabel("PC"); ax.set_ylabel("variance ratio")

            _write_fig(outdir / "pca_variance.png", "PCA variance ratio", draw)
            add_file("figure", "pca_variance.png")
            add_dataset(f"{input_stem}_pca.h5ad", "scrna", "h5ad", "pca", {"n_comps": n_comps})
            log.append(f"[mock] PCA with {n_comps} components")

        elif cap_id == "scrna.neighbors":
            metrics = {"n_neighbors": params.get("n_neighbors"), "n_pcs": params.get("n_pcs")}
            add_dataset(f"{input_stem}_neighbors.h5ad", "scrna", "h5ad", "neighbors",
                        {"n_neighbors": params.get("n_neighbors")})
            log.append(f"[mock] KNN graph k={params.get('n_neighbors')}")

        elif cap_id == "scrna.umap":
            metrics = {"min_dist": params.get("min_dist")}

            def draw(ax):
                n = 3000
                ax.scatter([rng.uniform(-8, 8) for _ in range(n)],
                           [rng.uniform(-8, 8) for _ in range(n)], s=1, alpha=0.25)
                ax.set_xlabel("UMAP1"); ax.set_ylabel("UMAP2")

            _write_fig(outdir / "umap.png", "UMAP", draw)
            add_file("figure", "umap.png")
            add_dataset(f"{input_stem}_umap.h5ad", "scrna", "h5ad", "umap", {})
            log.append("[mock] UMAP embedding")

        elif cap_id == "scrna.clustering":
            res = params.get("resolution", 0.5)
            n_clusters = max(2, int(round(2 + res * 6)))
            metrics = {"resolution": res, "n_clusters": n_clusters}
            sizes = [rng.randint(300, 2500) for _ in range(n_clusters)]
            total = sum(sizes)
            sizes = [round(s / total * 100, 1) for s in sizes]

            def draw(ax):
                n = 3000
                centers = [(rng.uniform(-7, 7), rng.uniform(-7, 7)) for _ in range(n_clusters)]
                for i, (cx, cy) in enumerate(centers):
                    ax.scatter([rng.gauss(cx, 1.5) for _ in range(n // n_clusters)],
                               [rng.gauss(cy, 1.5) for _ in range(n // n_clusters)],
                               s=1.5, alpha=0.4, label=f"c{i}")
                ax.legend(markerscale=6, fontsize=8)
                ax.set_xlabel("UMAP1"); ax.set_ylabel("UMAP2")

            _write_fig(outdir / "umap_clusters.png", f"Leiden clusters (res={res})", draw)
            add_file("figure", "umap_clusters.png")
            _write_html(outdir / "clustering_report.html", "聚类报告",
                        [("聚类参数", _html_table(["参数", "值"], [["resolution", res]])),
                         ("簇大小", _html_table(["Cluster", "占比 (%)"], [
                             [f"c{i}", s] for i, s in enumerate(sizes)])),
                         ("说明", f"共 {n_clusters} 个簇。建议下一步进行标记基因分析或细胞注释。")])
            add_file("report", "clustering_report.html")
            add_dataset(f"{input_stem}_clustered.h5ad", "scrna", "h5ad", "clustered",
                        {"resolution": res, "n_clusters": n_clusters})
            log.append(f"[mock] leiden clustering -> {n_clusters} clusters")

        elif cap_id == "scrna.marker_genes":
            n = params.get("n_markers", 20)
            metrics = {"n_markers": n}
            rows = []
            for i in range(5):
                genes = rng.sample(GENE_POOL, min(n, len(GENE_POOL)))
                for g in genes:
                    rows.append([f"c{i}", g, round(rng.uniform(0, 6), 2),
                                 round(rng.uniform(1e-60, 0.05), 6)])
            with open(outdir / "marker_genes.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["cluster", "gene", "logfoldchanges", "pvals_adj"])
                w.writerows(rows)
            add_file("csv", "marker_genes.csv")

            def draw(ax):
                import numpy as np
                data = np.random.RandomState(_seed_for(task.task_id) % 2**31).rand(8, 20)
                ax.imshow(data, aspect="auto", cmap="viridis")
                ax.set_yticks(range(8)); ax.set_yticklabels([f"c{i}" for i in range(8)], fontsize=7)
                ax.set_xticks([])
                ax.set_xlabel("top genes")

            _write_fig(outdir / "marker_heatmap.png", "Marker genes heatmap", draw)
            add_file("figure", "marker_heatmap.png")
            log.append(f"[mock] computed marker genes (top {n}/cluster)")

        elif cap_id == "scrna.annotation":
            cell_types = ["T cell", "B cell", "NK cell", "Monocyte", "DC", "Macrophage"]
            n_types = rng.randint(3, len(cell_types))
            chosen = rng.sample(cell_types, n_types)
            metrics = {"method": params.get("method"), "cell_types": chosen}
            comp = [[ct, rng.randint(200, 4000)] for ct in chosen]
            with open(outdir / "cell_composition.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["cell_type", "n_cells"])
                w.writerows(comp)
            add_file("csv", "cell_composition.csv")

            def draw(ax):
                n = 3000
                centers = [(rng.uniform(-7, 7), rng.uniform(-7, 7)) for _ in chosen]
                for ct, (cx, cy) in zip(chosen, centers):
                    ax.scatter([rng.gauss(cx, 1.6) for _ in range(n // n_types)],
                               [rng.gauss(cy, 1.6) for _ in range(n // n_types)],
                               s=1.5, alpha=0.4, label=ct)
                ax.legend(markerscale=6, fontsize=7)
                ax.set_xlabel("UMAP1"); ax.set_ylabel("UMAP2")

            _write_fig(outdir / "annotation_umap.png", "Cell type annotation", draw)
            add_file("figure", "annotation_umap.png")
            _write_html(outdir / "annotation_report.html", "细胞注释报告",
                        [("注释方法", params.get("method", "marker_based")),
                         ("细胞组成", _html_table(["细胞类型", "细胞数"], comp)),
                         ("说明", "基于标记基因表达矩阵注释。")])
            add_file("report", "annotation_report.html")
            add_dataset(f"{input_stem}_annotated.h5ad", "scrna", "h5ad", "annotated",
                        {"cell_types": chosen})
            log.append(f"[mock] annotated -> {chosen}")

        # ------------------------------------------------------------ Bulk RNA
        elif cap_id == "bulk_rna.inspect":
            metrics = {"n_genes": rng.randint(15000, 25000), "n_samples": rng.randint(6, 30)}
            _write_fig(outdir / "inspect_summary.png", "Sample counts", 
                       lambda ax: ax.bar(range(metrics["n_samples"]),
                                         [rng.randint(5e6, 3e7) for _ in range(metrics["n_samples"])]))
            add_file("figure", "inspect_summary.png")
            _write_html(outdir / "inspect_report.html", "Bulk 数据检查",
                        [("基本信息", _html_table(["指标", "数值"], [
                            ["基因数", metrics["n_genes"]], ["样本数", metrics["n_samples"]]]))])
            add_file("report", "inspect_report.html")

        elif cap_id == "bulk_rna.qc":
            before, keep = rng.randint(15000, 25000), 0
            keep = int(before * rng.uniform(0.7, 0.9))
            metrics = {"genes_before": before, "genes_after": keep}

            def draw(ax):
                ax.boxplot([[rng.uniform(0, 1) for _ in range(300)]])
                ax.set_xticks([]); ax.set_ylabel("fraction of samples with count>0")

            _write_fig(outdir / "qc_metrics.png", "Bulk QC", draw)
            add_file("figure", "qc_metrics.png")
            add_dataset(f"{input_stem}_qc.csv", "bulk_rna", "csv", "qc", {"genes_after": keep})

        elif cap_id == "bulk_rna.normalization":
            metrics = {"method": params.get("method")}
            add_dataset(f"{input_stem}_normalized.csv", "bulk_rna", "csv", "normalized",
                        {"method": params.get("method")})

        elif cap_id == "bulk_rna.differential_expression":
            n_genes = rng.randint(15000, 25000)
            rows = []
            n_up = n_down = 0
            for i in range(2000):
                lfc = rng.gauss(0, 1.4)
                padj = 10 ** -rng.uniform(0, 6)
                sig = padj < params.get("padj_cutoff", 0.05) and abs(lfc) > 1
                if sig:
                    if lfc > 0:
                        n_up += 1
                    else:
                        n_down += 1
                rows.append([f"GENE{i}", round(rng.uniform(1, 50000), 1),
                             round(lfc, 3), f"{padj:.3e}"])
            rows.sort(key=lambda r: float(r[3]))
            with open(outdir / "deseq2_results.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["gene", "baseMean", "log2FoldChange", "padj"])
                w.writerows(rows)
            add_file("csv", "deseq2_results.csv")
            metrics = {"n_genes_tested": n_genes, "n_up": n_up, "n_down": n_down,
                       "padj_cutoff": params.get("padj_cutoff")}
            _write_html(outdir / "de_report.html", "差异表达报告",
                        [("结果", _html_table(["指标", "数值"], [
                            ["上调基因", n_up], ["下调基因", n_down],
                            ["检验基因数", n_genes]])),
                         ("说明", f"DESeq2，padj < {params.get('padj_cutoff', 0.05)}，|log2FC| > 1。")])
            add_file("report", "de_report.html")
            log.append(f"[mock] DE: {n_up} up / {n_down} down")

        elif cap_id == "bulk_rna.volcano":
            padj_cut = params.get("padj_cutoff", 0.05)
            lfc_cut = params.get("log2fc_cutoff", 1.0)

            def draw(ax):
                for _ in range(3000):
                    lfc = rng.gauss(0, 1.4)
                    padj = 10 ** -rng.uniform(0, 6)
                    sig = padj < padj_cut and abs(lfc) > lfc_cut
                    ax.scatter(lfc, -10 * (padj and __import__("math").log10(padj)),
                               s=2, c="#d33" if sig else "#bbb", alpha=0.6)
                ax.axhline(-10 * __import__("math").log10(padj_cut), color="gray", ls="--", lw=1)
                ax.axvline(lfc_cut, color="gray", ls="--", lw=1)
                ax.axvline(-lfc_cut, color="gray", ls="--", lw=1)
                ax.set_xlabel("log2FC"); ax.set_ylabel("-log10(padj)")

            _write_fig(outdir / "volcano.png", "Volcano plot", draw)
            add_file("figure", "volcano.png")

        elif cap_id == "bulk_rna.heatmap":
            n = params.get("n_top_genes", 50)

            def draw(ax):
                import numpy as np
                data = np.random.RandomState(_seed_for(task.task_id) % 2**31).rand(n, 8)
                ax.imshow(data, aspect="auto", cmap="RdBu_r")
                ax.set_yticks([]); ax.set_xticks(range(8))
                ax.set_xticklabels([f"S{i+1}" for i in range(8)], fontsize=7)
                ax.set_ylabel(f"top {n} DE genes")

            _write_fig(outdir / "de_heatmap.png", "DE genes heatmap", draw)
            add_file("figure", "de_heatmap.png")

        elif cap_id == "bulk_rna.go_enrichment":
            ont = params.get("ontology", "BP")
            rows = []
            for i in range(15):
                rows.append([f"GO:00{1000+i}", f"biological process {i+1}",
                             round(rng.uniform(0.01, 0.1), 4),
                             round(rng.uniform(5, 80), 1),
                             f"{10 ** -rng.uniform(0, 8):.2e}"])
            rows.sort(key=lambda r: float(r[4]))
            with open(outdir / "go_enrichment.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["go_id", "term", "ratio", "count", "pvalue"])
                w.writerows(rows)
            add_file("csv", "go_enrichment.csv")
            metrics = {"ontology": ont, "n_terms": len(rows)}

            def draw(ax):
                ax.barh([r[1][:24] for r in rows[:8]][::-1],
                        [float(r[3]) for r in rows[:8]][::-1], color="#4c8bf5")
                ax.set_xlabel("gene count")

            _write_fig(outdir / "go_barplot.png", f"GO enrichment ({ont})", draw)
            add_file("figure", "go_barplot.png")

        elif cap_id == "bulk_rna.gsea":
            rows = []
            for i in range(10):
                rows.append([f"HALLMARK_PATHWAY_{i+1}", round(rng.uniform(-2, 2), 2),
                             f"{10 ** -rng.uniform(0, 6):.2e}", round(rng.uniform(0, 1), 2)])
            rows.sort(key=lambda r: float(r[2]))
            with open(outdir / "gsea_results.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["pathway", "NES", "padj", "leading_edge"])
                w.writerows(rows)
            add_file("csv", "gsea_results.csv")
            metrics = {"n_pathways": len(rows)}

            def draw(ax):
                es = [rng.uniform(-1, 1) for _ in range(100)]
                ax.plot(range(100), es, color="#0b5cad")
                ax.axhline(0, color="gray", lw=0.8)
                ax.set_xlabel("rank"); ax.set_ylabel("enrichment score")

            _write_fig(outdir / "gsea_plot.png", "GSEA", draw)
            add_file("figure", "gsea_plot.png")

        elif cap_id == "bulk_rna.fastqc":
            reads = rng.randint(20_000_000, 60_000_000)
            q30 = round(rng.uniform(88, 96), 1)
            gc = round(rng.uniform(40, 52), 1)
            metrics = {"reads": reads, "q30_pct": q30, "gc_pct": gc}
            _write_html(outdir / "fastqc_report.html", "FastQC 质控报告",
                        [("基本指标", _html_table(["指标", "数值"], [
                            ["reads", f"{reads:,}"], ["Q30 占比", f"{q30}%"],
                            ["GC 含量", f"{gc}%"], ["碱基质量", ">30（良好）"]])),
                         ("结论", "质量良好，可进入去接头/裁切步骤。")])
            add_file("report", "fastqc_report.html")
            log.append(f"[mock] fastqc: {reads:,} reads, Q30={q30}%")

        elif cap_id == "bulk_rna.trimming":
            before = rng.randint(20_000_000, 60_000_000)
            after = int(before * rng.uniform(0.9, 0.97))
            metrics = {"reads_before": before, "reads_after": after,
                       "adapters": params.get("adapters", "auto"),
                       "min_length": params.get("min_length")}
            add_file("other", f"{input_stem}_trimmed.fastq.gz")
            _write_html(outdir / "trimming_report.html", "去接头裁切报告",
                        [("裁切结果", _html_table(["指标", "数值"], [
                            ["裁切前 reads", f"{before:,}"], ["裁切后 reads", f"{after:,}"],
                            ["保留比例", f"{after/before*100:.1f}%"],
                            ["接头模式", params.get("adapters", "auto")]])),
                         ("说明", "cutadapt 模板化裁切，min_length=" + str(params.get("min_length", 20)) + "。")])
            add_file("report", "trimming_report.html")
            add_dataset(f"{input_stem}_trimmed.fastq.gz", "fastq", "fastq.gz", "trimmed",
                        {"reads_after": after, "min_length": params.get("min_length")})
            log.append(f"[mock] trimming: {before:,} -> {after:,} reads")

        elif cap_id == "bulk_rna.alignment":
            threads = params.get("threads", 4)
            reads = rng.randint(20_000_000, 60_000_000)
            mapped = int(reads * rng.uniform(0.85, 0.97))
            metrics = {"reads": reads, "mapped": mapped,
                       "unique_mapping_rate": round(mapped / reads, 3)}
            bam = outdir / f"{input_stem}_Aligned.sortedByCoord.out.bam"
            bam.write_bytes(b"\x1f\x8b placeholder bam (mock)")
            add_file("bam", bam.name)
            _write_html(outdir / "alignment_report.html", "比对报告",
                        [("比对结果", _html_table(["指标", "数值"], [
                            ["reads", f"{reads:,}"], ["mapped", f"{mapped:,}"],
                            ["mapping rate", f"{metrics['unique_mapping_rate']*100:.1f}%"]])),
                         ("说明", f"STAR 模板化比对，threads={threads}。")])
            add_file("report", "alignment_report.html")
            add_dataset(f"{input_stem}_aligned.bam", "fastq", "bam", "aligned",
                        {"mapping_rate": metrics["unique_mapping_rate"]})

        elif cap_id == "bulk_rna.quantification":
            n_genes = rng.randint(15000, 25000)
            n_samples = rng.randint(3, 10)
            rows = []
            for i in range(n_genes):
                row = [f"GENE{i}"] + [str(rng.randint(0, 3000)) for _ in range(n_samples)]
                rows.append(row)
            with open(outdir / "counts.csv", "w", newline="") as f:
                w = csv.writer(f)
                w.writerow(["gene"] + [f"S{j+1}" for j in range(n_samples)])
                w.writerows(rows)
            add_file("csv", "counts.csv")
            metrics = {"genes": n_genes, "samples": n_samples,
                       "feature_type": params.get("feature_type")}
            _write_html(outdir / "quantification_report.html", "基因定量报告",
                        [("定量结果", _html_table(["指标", "数值"], [
                            ["基因数", n_genes], ["样本数", n_samples],
                            ["特征类型", params.get("feature_type", "exon")]])),
                         ("说明", "featureCounts 输出 count matrix，可作为差异表达分析的输入。")])
            add_file("report", "quantification_report.html")
            add_dataset(f"{input_stem}_counts.csv", "bulk_rna", "csv", "raw",
                        {"genes": n_genes, "samples": n_samples, "from": "featurecounts"})
            log.append(f"[mock] quantified {n_genes} genes x {n_samples} samples")

        else:
            log.append(f"[mock] capability {cap_id} 无 mock 实现，返回空结果")
            metrics = {"note": f"no mock implementation for {cap_id}"}

        # 写执行日志
        log_path = outdir / "execution.log"
        log_path.write_text("\n".join(log) + "\n", encoding="utf-8")
        log.append(f"[mock] completed; {len(artifacts)} artifacts, {len(datasets)} datasets")

        return ExecutionResult(ok=True, metrics=metrics, artifacts=artifacts,
                               datasets=datasets, log_lines=log)
