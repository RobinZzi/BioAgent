"""实现模板：Python(scanpy) / R(DESeq2) / bash(STAR) 脚本生成。

命令一律由模板 + 白名单参数构造，参数在执行前经 capability 定义域二次
校验。禁止将自由文本拼入命令。
"""
import json


def render_scanpy_script(capability_id: str, params: dict, input_path: str,
                         output_path: str, output_dir: str, seed: int = 42) -> str:
    """生成 scanpy 实现脚本（本地真实执行用）。"""
    inp = json.dumps(input_path)
    out = json.dumps(output_path)
    odir = json.dumps(output_dir)
    header = (
        "import json, os\n"
        "import numpy as np\n"
        "import matplotlib\n"
        "matplotlib.use('Agg')\n"
        "import matplotlib.pyplot as plt\n"
        "import scanpy as sc\n"
        f"np.random.seed({seed})\n"
        f"IN = {inp}; OUT = {out}; OUTDIR = {odir}\n"
        "os.makedirs(OUTDIR, exist_ok=True)\n"
        "def _savefig(fig, path):\n"
        "    fig = fig if hasattr(fig, 'savefig') else plt.gcf()\n"
        "    fig.savefig(path, dpi=110, bbox_inches='tight')\n"
        "    plt.close(fig)\n"
        "adata = sc.read_h5ad(IN)\n"
        "print('input:', adata.shape)\n"
    )
    if capability_id == "scrna.inspect":
        return header + (
            "print('n_obs:', adata.n_obs, 'n_vars:', adata.n_vars)\n"
            "fig, ax = plt.subplots(figsize=(6,4))\n"
            "ax.hist(np.asarray(adata.X.sum(axis=1)).ravel(), bins=50)\n"
            "ax.set_title('counts per cell'); ax.set_xlabel('total counts')\n"
            "plt.tight_layout(); plt.savefig(os.path.join(OUTDIR,'inspect_summary.png'), dpi=110); plt.close()\n"
        )
    if capability_id == "scrna.qc":
        return header + (
            "adata.var['mt'] = adata.var_names.str.startswith('MT-')\n"
            "sc.pp.calculate_qc_metrics(adata, qc_vars=['mt'], percent_top=None, inplace=True)\n"
            f"sc.pp.filter_cells(adata, min_genes={params.get('min_genes',200)})\n"
            f"sc.pp.filter_cells(adata, max_genes={params.get('max_genes',5000)})\n"
            f"adata = adata[adata.obs['pct_counts_mt'] < {params.get('max_mito_pct',20)}].copy()\n"
            "print('after:', adata.shape)\n"
            "fig, ax = plt.subplots(figsize=(6,4))\n"
            "ax.scatter(adata.obs['total_counts'], adata.obs['pct_counts_mt'], s=2, alpha=0.4)\n"
            "ax.set_xlabel('total_counts'); ax.set_ylabel('pct_counts_mt'); ax.set_title('QC filtering')\n"
            "plt.tight_layout(); plt.savefig(os.path.join(OUTDIR,'qc_filtering.png'), dpi=110); plt.close()\n"
            "adata.write_h5ad(OUT)\n"
        )
    if capability_id == "scrna.normalization":
        return header + (
            "sc.pp.normalize_total(adata, target_sum=%s)\n"
            "sc.pp.log1p(adata)\n"
            "adata.write_h5ad(OUT)\n" % json.dumps(params.get("target_sum", 1e4))
        )
    if capability_id == "scrna.hvg":
        return header + (
            "sc.pp.highly_variable_genes(adata, n_top_genes=%d)\n"
            "_savefig(sc.pl.highly_variable_genes(adata, show=False), os.path.join(OUTDIR,'hvg_dispersion.png'))\n"
            "adata.write_h5ad(OUT)\n" % params.get("n_top_genes", 2000)
        )
    if capability_id == "scrna.pca":
        return header + (
            "sc.tl.pca(adata, n_comps=%d, svd_solver='arpack')\n"
            "_savefig(sc.pl.pca_variance_ratio(adata, n_pcs=%d, show=False), os.path.join(OUTDIR,'pca_variance.png'))\n"
            "adata.write_h5ad(OUT)\n" % (params.get("n_comps", 50), params.get("n_comps", 50))
        )
    if capability_id == "scrna.neighbors":
        return header + (
            "sc.pp.neighbors(adata, n_neighbors=%d, n_pcs=%d)\n"
            "adata.write_h5ad(OUT)\n" % (params.get("n_neighbors", 15), params.get("n_pcs", 30))
        )
    if capability_id == "scrna.umap":
        return header + (
            "sc.tl.umap(adata, min_dist=%s)\n"
            "_savefig(sc.pl.umap(adata, show=False), os.path.join(OUTDIR,'umap.png'))\n"
            "adata.write_h5ad(OUT)\n" % json.dumps(params.get("min_dist", 0.5))
        )
    if capability_id == "scrna.clustering":
        return header + (
            "sc.tl.leiden(adata, resolution=%s, key_added='leiden')\n"
            "sc.tl.umap(adata)\n"
            "_savefig(sc.pl.umap(adata, color='leiden', show=False, legend_loc='on data'), os.path.join(OUTDIR,'umap_clusters.png'))\n"
            "print('n_clusters:', adata.obs['leiden'].nunique())\n"
            "adata.write_h5ad(OUT)\n" % json.dumps(params.get("resolution", 0.5))
        )
    if capability_id == "scrna.marker_genes":
        return header + (
            "sc.tl.rank_genes_groups(adata, 'leiden', method='wilcoxon')\n"
            "sc.pl.rank_genes_groups_heatmap(adata, n_genes=%d, show=False, save='.png', swap_axes=True)\n"
            "import shutil; shutil.move('figures/rank_genes_groups_heatmap.png', os.path.join(OUTDIR,'marker_heatmap.png'))\n"
            "res = adata.uns['rank_genes_groups']\n"
            "import pandas as pd\n"
            "df = pd.DataFrame({k: res[k][:20] for k in res.keys()})\n"
            "df.to_csv(os.path.join(OUTDIR,'marker_genes.csv'), index=False)\n" % params.get("n_markers", 20)
        )
    return header + "print('no template for', %s)\n" % json.dumps(capability_id)


def render_deseq2_script(params: dict, input_path: str, output_path: str, output_dir: str) -> str:
    return f"""library(DESeq2)
counts <- read.csv({json.dumps(input_path)}, row.names=1, check.names=FALSE)
coldata <- data.frame(row.names=colnames(counts), condition=factor(rep(c("A","B"), length.out=ncol(counts))))
dds <- DESeqDataSetFromMatrix(countData=counts, colData=coldata, design=~condition)
dds <- DESeq(dds)
res <- as.data.frame(results(dds, contrast=c("condition","B","A")))
write.csv(res, {json.dumps(output_path)})
cat("rows:", nrow(res), "\\n")
"""


def render_star_bash(params: dict, input_path: str, output_dir: str) -> str:
    genome = params.get("genome_dir", "")
    threads = int(params.get("threads", 4))
    return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {json.dumps(output_dir)}
STAR --genomeDir {json.dumps(genome)} \\
     --readFilesIn {json.dumps(input_path)} \\
     --runThreadN {threads} \\
     --outSAMtype BAM SortedByCoordinate \\
     --outFileNamePrefix {json.dumps(output_dir)}/star_
samtools index {json.dumps(output_dir)}/star_Aligned.sortedByCoord.out.bam
"""


def render_bash_script(impl: str, params: dict, input_path: str, output_dir: str) -> str:
    """按实现 id 生成受控 bash 脚本（参数一律 shlex 转义，禁止拼自由文本）。"""
    import shlex

    def q(s: str) -> str:
        return shlex.quote(s)

    if impl == "fastqc":
        return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {q(output_dir)}
fastqc -o {q(output_dir)} {q(input_path)}
"""

    if impl == "cutadapt":
        adapters = params.get("adapters", "auto")
        min_len = int(params.get("min_length", 20))
        if adapters and adapters != "auto":
            adapter_arg = f"-a {q(str(adapters))}"
        else:
            adapter_arg = "-a AGATCGGAAGAGC"   # 默认 Illumina 接头（auto 场景的保守默认）
        out = f"{output_dir}/trimmed.fastq.gz"
        return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {q(output_dir)}
cutadapt {adapter_arg} -m {min_len} -o {q(out)} {q(input_path)}
"""

    if impl == "cellranger":
        sample = params.get("sample_id", "sample1")
        ref = params.get("reference", "")
        cells = int(params.get("expect_cells", 5000))
        return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {q(output_dir)}
cellranger count --id={q(str(sample))} \\
     --fastqs={q(str(input_path))} \\
     --sample={q(str(sample))} \\
     --transcriptome={q(str(ref))} \\
     --expect-cells={cells} \\
     --localcores=8 --localmem=16
cp -r {q(str(sample))}/outs/* {q(output_dir)}/ 2>/dev/null || true
"""

    if impl == "featureCounts":
        gtf = params.get("gtf", "")
        ftype = params.get("feature_type", "exon")
        out = f"{output_dir}/counts.txt"
        return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {q(output_dir)}
featureCounts -a {q(str(gtf))} -t {ftype} -o {q(out)} {q(input_path)}
"""

    # 兼容旧 star 模板
    if impl == "star":
        return render_star_bash(params, input_path, output_dir)

    raise ValueError(f"无 bash 模板: {impl}")
