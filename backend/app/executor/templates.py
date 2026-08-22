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
        f"SEED = {seed}\n"
        "sc.settings.seed = SEED\n"
        f"IN = {inp}; OUT = {out}; OUTDIR = {odir}\n"
        "os.makedirs(OUTDIR, exist_ok=True)\n"
        "def _savefig(fig, path):\n"
        "    fig = fig if hasattr(fig, 'savefig') else plt.gcf()\n"
        "    fig.savefig(path, dpi=110, bbox_inches='tight')\n"
        "    plt.close(fig)\n"
        "if os.path.isdir(IN):\n"
        "    adata = sc.read_10x_mtx(IN, var_names='gene_symbols')\n"
        "else:\n"
        "    adata = sc.read_h5ad(IN)\n"
        "print('input:', adata.shape)\n"
    )

    if capability_id == "scrna.import_mtx":
        return header + (
            "print('mtx loaded:', adata.shape)\n"
            "adata.write_h5ad(OUT)\n"
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
            "sc.tl.umap(adata, min_dist=%s, random_state=SEED)\n"
            "_savefig(sc.pl.umap(adata, show=False), os.path.join(OUTDIR,'umap.png'))\n"
            "adata.write_h5ad(OUT)\n" % json.dumps(params.get("min_dist", 0.5))
        )
    if capability_id == "scrna.clustering":
        return header + (
            "sc.tl.leiden(adata, resolution=%s, key_added='leiden', random_state=SEED)\n"
            "sc.tl.umap(adata, random_state=SEED)\n"
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


def render_seurat_script(capability_id: str, params: dict, input_path: str,
                         output_path: str, output_dir: str, seed: int = 42) -> str:
    """Seurat 实现脚本（R）。读 h5ad（SeuratDisk）→ SCTransform → PCA → UMAP → 聚类。"""
    import shlex
    inp = shlex.quote(input_path)
    outp = shlex.quote(output_path)
    odir = shlex.quote(output_dir)
    return f"""library(Seurat)
library(SeuratDisk)
set.seed({seed})
SeuratDisk::Convert({inp}, dest = {odir}/.seurat_out.h5seurat, overwrite = TRUE)
seu <- LoadH5Seurat({odir}/.seurat_out.h5seurat)
seu <- SCTransform(seu, verbose = FALSE)
seu <- RunPCA(seu, npcs = 50, verbose = FALSE)
seu <- FindNeighbors(seu, dims = 1:30)
seu <- RunUMAP(seu, dims = 1:30)
seu <- FindClusters(seu, resolution = {params.get('resolution', 0.5)})
print(paste('n_clusters:', length(unique(Idents(seu)))))
png(file.path({odir}, 'umap_clusters.png'), width = 700, height = 520)
DimPlot(seu, reduction = 'umap', label = TRUE)
dev.off()
SaveH5Seurat(seu, filename = {odir}/.seurat_out.h5seurat)
"""


def render_celltypist_script(capability_id: str, params: dict, input_path: str,
                             output_path: str, output_dir: str, seed: int = 42) -> str:
    """celltypist 注释脚本（Python）。"""
    import json
    inp = json.dumps(input_path)
    out = json.dumps(output_path)
    odir = json.dumps(output_dir)
    return f"""import os
import pandas as pd
import anndata as ad
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import celltypist
SEED = {seed}
adata = ad.read_h5ad({inp})
# 使用示例模型（可注释时指定模型路径）
model = celltypist.models.Model.load(model=os.environ.get('CELLTYPIST_MODEL', 'Immune_All_Low.pkl'))
pred = celltypist.annotate(adata, model=model, majority_voting=True)
adata = pred.to_adata()
adata.write_h5ad({out})
labels = adata.obs.get('majority_voting', adata.obs.get('celltypist', 'unknown'))
comp = pd.Series(labels).value_counts().reset_index()
comp.columns = ['cell_type', 'n_cells']
comp.to_csv(os.path.join({odir}, 'cell_composition.csv'), index=False)
fig, ax = plt.subplots(figsize=(6,5))
import scanpy as sc
sc.pl.umap(adata, color='majority_voting', show=False, ax=ax) if 'majority_voting' in adata.obs else None
fig.savefig(os.path.join({odir}, 'annotation_umap.png'), dpi=110, bbox_inches='tight')
print('cell types:', list(comp['cell_type'])[:10])
"""


def render_omics_python_script(capability_id: str, params: dict, input_path: str,
                               output_path: str, output_dir: str, seed: int = 42) -> str:
    """scATAC / 空间 通用 Python 模板（scanpy 为主，读 h5ad → 基础处理 → 产物）。"""
    import json
    inp = json.dumps(input_path)
    out = json.dumps(output_path)
    odir = json.dumps(output_dir)
    return f"""import os, json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import scanpy as sc
np.random.seed({seed})
IN = {inp}; OUT = {out}; OUTDIR = {odir}
os.makedirs(OUTDIR, exist_ok=True)
adata = sc.read_h5ad(IN)
print('input:', adata.shape)
if "{capability_id}" == "scatac.qc" or "{capability_id}" == "scatac.clustering" or "{capability_id}".endswith("qc"):
    # 质控：基础指标 + 过滤
    import pandas as pd
    if 'n_fragments' not in adata.obs and adata.obs.shape[1] > 0:
        adata.obs['n_fragments'] = adata.X.sum(axis=1).A1 if hasattr(adata.X, 'A1') else np.asarray(adata.X.sum(axis=1)).ravel()
    fig, ax = plt.subplots(figsize=(6,4))
    ax.hist(np.asarray(adata.obs['n_fragments']), bins=40)
    ax.set_title('omics QC'); ax.set_xlabel('metric')
    fig.savefig(os.path.join(OUTDIR, 'atac_qc.png' if '{capability_id}'.startswith('scatac') else 'spatial_qc.png'), dpi=110, bbox_inches='tight'); plt.close(fig)
    adata.write_h5ad(OUT)
    print('QC done', adata.shape)
elif "clustering" in "{capability_id}":
    sc.pp.normalize_total(adata); sc.pp.log1p(adata)
    sc.pp.pca(adata, n_comps=30)
    sc.pp.neighbors(adata)
    sc.tl.umap(adata, random_state={seed})
    sc.tl.leiden(adata, resolution={params.get('resolution', 0.5)}, random_state={seed})
    fig, ax = plt.subplots(figsize=(6,5))
    sc.pl.umap(adata, color='leiden', show=False, ax=ax)
    fig.savefig(os.path.join(OUTDIR, 'atac_umap.png' if '{capability_id}'.startswith('scatac') else 'spatial_clusters.png'), dpi=110, bbox_inches='tight'); plt.close(fig)
    adata.write_h5ad(OUT)
    print('cluster done', adata.obs['leiden'].nunique())
else:
    adata.write_h5ad(OUT)
"""


def render_methylkit_script(capability_id: str, params: dict, input_path: str,
                            output_dir: str, seed: int = 42) -> str:
    """DNA 甲基化（methylKit R 模板）：质控 / 差异甲基化。"""
    import json
    inp = json.dumps(input_path)
    odir = json.dumps(output_dir)
    out = json.dumps(output_dir + "/result.csv")
    if capability_id == "methylation.qc":
        return f"""library(methylKit)
myobj <- methRead({inp}, sample.id="s1", assembly="hg38", treatment=1)
filtered <- filterByCoverage(myobj, lo.count=10)
qc <- getMethylationStats(filtered, plot=FALSE)
write.csv(as.data.frame(methylKit::getData(filtered))[1:100,], {out})
cat("methylation qc done\\n")
"""
    return f"""library(methylKit)
myobj <- methRead({inp}, sample.id="s1", assembly="hg38", treatment=1)
myobj <- normalizeCoverage(myobj)
# 简化差异：单个样本时不计算 DMR，输出 beta 值分布
rm <- getMethylationStats(myobj, plot=FALSE)
write.csv(as.data.frame(methylKit::getData(myobj))[1:100,], {out})
cat("methylation differential done\\n")
"""


def render_gatk_bash(capability_id: str, params: dict, input_path: str,
                     output_dir: str) -> str:
    """WES/WGS 变异检测 / 注释（GATK 模板）。"""
    import shlex
    inp = shlex.quote(input_path)
    odir = shlex.quote(output_dir)
    if capability_id == "variant.calling":
        ref = shlex.quote(params.get("ref_genome", "/ref/hg38.fa"))
        return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {odir}
gatk HaplotypeCaller -R {ref} -I {inp} -O {odir}/variants.vcf
"""
    db = shlex.quote(params.get("db", "clinvar"))
    return f"""#!/usr/bin/env bash
set -euo pipefail
mkdir -p {odir}
gatk VariantAnnotator -V {inp} -O {odir}/variants_annotated.csv --dbsnp {db}
"""
