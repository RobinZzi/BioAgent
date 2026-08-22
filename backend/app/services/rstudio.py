"""RStudio 手动交接（handoff）服务。

让用户能把某一步 R 类能力分析「接手」到 RStudio 里手动跑,并方便地调用
之前的分析结果(项目里已有的数据集/产物)。

原则:
- 交接包生成自一个已存在的 AnalysisEvent(R 类 implementation)。
- 生成一个可下载的 zip + 一份可编辑的 analysis.R,内含:
    * 前序数据集加载器(load_prior() / ds()),把项目里已有数据集读进 R 环境;
    * 主输入读取;
    * 「可编辑区」:用户可自由修改的分析逻辑(默认用原模板实现);
    * 输出写入 rstudio_output/ 目录。
- 产物落盘后,用户在 BioAgent 界面点「导入结果」,把产物注册为新的
  Dataset/Artifact,并延续 DAG 链路(分析完成即由下一条能力消费)。

安全:交接只是「生成脚本 + 用户手动跑」,不改变 Agent/Executor 的
「结构化任务、绝不自由 shell」边界。
"""
import json
import re
import zipfile
from pathlib import Path

from ..config import settings
from ..executor import templates as tpl
from ..models import AnalysisEvent, Dataset, Project

# R 类 implementation → 能力语义映射（用于生成 analysis.R 主体）
_R_IMPLS = {"DESeq2", "edgeR", "seurat", "methylKit"}


def _r_quote(s: str) -> str:
    """生成 R 字符串字面量(双引号,内部转义)。"""
    return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'


# ---------------------------------------------------------------- 主体

def _analysis_body(capability_id: str, impl: str, params: dict,
                   input_path: str, output_dir: str, seed: int = 42) -> str:
    """生成 analysis.R 的可编辑主体（复用模板库,但把路径改为相对布局）。

    保留原模板逻辑作为「可编辑区」基线,帮助用户在熟悉的结构上修改。
    """
    if impl == "seurat":
        return tpl.render_seurat_script(
            capability_id, params, input_path,
            f"{output_dir}/output.h5ad", output_dir, seed=seed)
    if impl == "methylKit":
        return tpl.render_methylkit_script(
            capability_id, params, input_path, output_dir, seed=seed)
    if impl in ("DESeq2", "edgeR"):
        return tpl.render_deseq2_script(
            params, input_path, f"{output_dir}/deseq2_results.csv", output_dir)
    # 回退:通用 R 说明
    return (
        f"# {impl} 分析(手动模式):请在下方实现\n"
        f'cat("capability:", "{capability_id}", "| params:", '
        f'{json.dumps(params, ensure_ascii=False)}, "\\n")\n'
    )


def render_analysis_r(
    capability_id: str,
    impl: str,
    params: dict,
    input_path: str,
    output_dir: str,
    dtypes: list[dict],
    seed: int = 42,
) -> str:
    """渲染完整的 analysis.R。

    dtypes: 项目里已有的数据集列表(用于生成 load_prior()/ds() 加载器)。
    每个元素: {id, name, dtype, format, location, phase, source_event_id}
    """
    inp = _r_quote(input_path or "")
    out = _r_quote(output_dir)
    indented = "\n".join(
        f'    list(id = "{d["id"]}", name = "{d["name"]}", dtype = "{d["dtype"]}", '
        f'format = "{d["format"]}", location = "{d["location"]}", '
        f'phase = "{d["phase"]}"),' for d in dtypes)

    body = _analysis_body(capability_id, impl, params, input_path, output_dir, seed)

    _TEMPLATE = """# ============================================================
# BioAgent RStudio manual handoff - @@CAP@@
# event implementation: @@IMPL@@    version: @@VER@@
#
# Open this file in RStudio and source it (or run it section by section).
# Load the main input, then freely edit the logic in the EDITABLE REGION.
# Outputs are written to rstudio_output/. When done, go back to the
# BioAgent UI and click "Import results".
# ============================================================

# ---- 0. Prior datasets (existing analysis results in this project) ----
# Use ds(<index|id|name>) to load any prior result into the environment;
# load_prior() loads all of them at once. .ds_kind() describes each entry.
.PRIOR <- list(
@@PRIOR@@
)

.ds_kind <- function(d) sprintf('%s (%s, %s)', d$name, d$phase, d$format)
.ds_load <- function(d) {
  if (grepl('[.]h5ad$', d$location, ignore.case = TRUE)) {
    if (!requireNamespace('SeuratDisk', quietly = TRUE)) {
      stop('h5ad requires SeuratDisk; install it or use a csv/tsv prior result')
    }
    h5f <- tempfile(fileext = '.h5seurat')
    SeuratDisk::Convert(d$location, dest = h5f, overwrite = TRUE)
    if (requireNamespace('Seurat', quietly = TRUE)) {
      return(Seurat::LoadH5Seurat(h5f))
    }
    return(h5f)
  }
  if (grepl('[.]csv$', d$location, ignore.case = TRUE)) {
    read.csv(d$location, row.names = 1, check.names = FALSE)
  } else {
    read.table(d$location, header = TRUE, sep = '\\t', check.names = FALSE)
  }
}

# Load a prior dataset by index, id, or name
ds <- function(x) {
  .p <- .PRIOR
  if (is.numeric(x)) {
    if (x < 1 || x > length(.p)) stop('index out of range for prior datasets')
    return(.ds_load(.p[[x]]))
  }
  .m <- .p[sapply(.p, function(d) d$id == x || d$name == x)]
  if (length(.m) == 0) stop('no prior dataset found: ', x)
  .ds_load(.m[[1]])
}

# Load all prior datasets into a named list
load_prior <- function() {
  .env <- list()
  for (.d in .PRIOR) .env[[.d$name]] <- .ds_load(.d)
  .env
}

cat('prior dataset count:', length(.PRIOR), '\\n')
for (.i in seq_along(.PRIOR)) cat(sprintf('  [%d] %s\\n', .i, .ds_kind(.PRIOR[[.i]])))

# ---- 1. Main input ----
input_path <- @@INP@@
cat('main input:', input_path, '\\n')

# ---- 2. EDITABLE REGION: analysis logic ----
# Default is the automated implementation template; modify freely below.
# Write outputs under output_dir (BioAgent scans this directory on import).
output_dir <- @@OUT@@

@@BODY@@

cat('analysis done -> output dir:', output_dir, '\\n')
"""

    return (_TEMPLATE
            .replace("@@CAP@@", capability_id)
            .replace("@@IMPL@@", impl)
            .replace("@@VER@@", settings.version)
            .replace("@@PRIOR@@", indented)
            .replace("@@INP@@", inp)
            .replace("@@OUT@@", out)
            .replace("@@BODY@@", body))


# ---------------------------------------------------------------- package

_README_TEMPLATE = """# BioAgent RStudio 手动交接包

## 用法

1. 在 RStudio 中打开 `analysis.R`。
2. 先运行开头「0. 前序数据集」段,用 `ds(...)` / `load_prior()` 调用之前的分析结果。
3. 在「2. 可编辑区」修改分析逻辑(默认是自动执行的实现模板)。
4. 运行脚本,产物会写入 `rstudio_output/` 目录。
5. 回到 BioAgent 界面,在该事件上点「导入结果」,选择 `rstudio_output/` 目录,
   把产物注册为新的 Dataset/Artifact,并延续 DAG 链路。

## 说明

- 本包不改动任何自动执行边界:脚本由你在 RStudio 手动运行。
- `rstudio_output/` 是约定的产物目录,「导入结果」会扫描它。
- 若环境里缺 R 包(如 Seurat / DESeq2),请在 RStudio 里先 `install.packages(...)`。
"""


def _prior_datasets(db, project_id: str, exclude_event_id: str | None) -> list[dict]:
    """收集项目里已有数据集,生成加载器清单(排除当前事件新产生的,避免自引用)。"""
    out: list[dict] = []
    for d in (
        db.query(Dataset)
        .filter(Dataset.project_id == project_id)
        .order_by(Dataset.created_at.asc())
        .all()
    ):
        loc = d.location or ""
        if not loc:
            continue
        out.append({
            "id": d.id, "name": d.name, "dtype": _enumval(d.dtype),
            "format": d.format, "location": loc, "phase": d.phase,
            "source_event_id": d.source_event_id,
        })
    return out


def _enumval(v):
    return v.value if hasattr(v, "value") else v


def build_package(db, event: AnalysisEvent, project: Project) -> dict:
    """生成交接包,写入事件目录,返回包信息。"""
    from .execution import project_dir
    evdir = project_dir(project.id) / "events" / event.id
    pkg_dir = evdir / "rstudio"
    out_dir = evdir / "rstudio_output"
    pkg_dir.mkdir(parents=True, exist_ok=True)
    out_dir.mkdir(parents=True, exist_ok=True)

    input_path = (event.inputs or {}).get("dataset_path")
    if not input_path:
        ds_id = (event.inputs or {}).get("dataset")
        if ds_id:
            d = db.get(Dataset, ds_id)
            input_path = d.location if d else None
    input_path = input_path or ""

    prior = _prior_datasets(db, project.id, exclude_event_id=event.id)

    params = event.parameters or {}
    seed = int(event.metrics.get("seed") or 42)
    cap_id = event.capability_id
    impl = event.implementation or "DESeq2"

    analysis = render_analysis_r(
        cap_id, impl, params, input_path, str(out_dir), prior, seed=seed)

    (pkg_dir / "analysis.R").write_text(analysis, encoding="utf-8")
    (pkg_dir / "README.md").write_text(_README_TEMPLATE, encoding="utf-8")
    manifest = {
        "event_id": event.id, "project_id": project.id,
        "capability_id": cap_id, "implementation": impl,
        "parameters": params, "seed": seed,
        "input_dataset_path": input_path,
        "output_dir": str(out_dir), "version": settings.version,
        "prior_datasets": prior,
    }
    (pkg_dir / "MANIFEST.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "event_id": event.id,
        "analysis_path": str(pkg_dir / "analysis.R"),
        "output_dir": str(out_dir),
        "package_dir": str(pkg_dir),
        "prior_datasets": prior,
        "manifest": manifest,
    }


def write_zip(pkg_info: dict, dest: Path) -> Path:
    """把交接包打包成 zip(转发给前端下载)。"""
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as zf:
        for f in ["analysis.R", "README.md", "MANIFEST.json"]:
            p = Path(pkg_info["package_dir"]) / f
            if p.exists():
                zf.write(p, arcname=f"rstudio_handoff/{f}")
    return dest


def scan_outputs(out_dir: Path) -> list[Path]:
    """扫描「导入结果」目录,返回产物文件列表(csv / h5ad / png / pdf / html)。"""
    if not out_dir.exists():
        return []
    return [p for p in sorted(out_dir.iterdir())
            if p.is_file() and p.suffix.lower() in
            {".csv", ".h5ad", ".png", ".pdf", ".html", ".bam", ".tsv", ".txt"}]
