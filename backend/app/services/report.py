"""分析报告自动生成：汇总项目的分析流程、事件指标、关键产物 → 科研报告 HTML。

报告为项目级动态产物，通过 GET /api/projects/{id}/report 直接返回 HTML，
不占用 Artifact 事件外键约束。
"""
import html
from pathlib import Path

from ..config import settings
from ..models import AnalysisEvent, Dataset, EventStatus, Project, utcnow

_CAP_LABEL = {
    "scrna.import_10x": "10x 下机导入", "scrna.import_mtx": "10x 矩阵导入",
    "scrna.inspect": "数据检查", "scrna.qc": "细胞 QC", "scrna.normalization": "标准化",
    "scrna.hvg": "高变基因", "scrna.pca": "PCA", "scrna.neighbors": "邻接图",
    "scrna.umap": "UMAP", "scrna.clustering": "聚类", "scrna.marker_genes": "标记基因",
    "scrna.annotation": "细胞注释",
    "bulk_rna.fastqc": "FastQC", "bulk_rna.trimming": "去接头裁切",
    "bulk_rna.alignment": "序列比对", "bulk_rna.quantification": "基因定量",
    "bulk_rna.inspect": "数据检查", "bulk_rna.qc": "QC", "bulk_rna.normalization": "标准化",
    "bulk_rna.differential_expression": "差异表达", "bulk_rna.volcano": "火山图",
    "bulk_rna.heatmap": "热图", "bulk_rna.go_enrichment": "GO 富集", "bulk_rna.gsea": "GSEA",
}


def _esc(s) -> str:
    return html.escape(str(s))


def build_report_html(db, project: Project, host: str = "http://127.0.0.1:8000") -> str:
    """构建项目分析报告 HTML。"""
    events = (db.query(AnalysisEvent)
              .filter(AnalysisEvent.project_id == project.id)
              .order_by(AnalysisEvent.created_at.asc()).all())
    datasets = (db.query(Dataset)
                .filter(Dataset.project_id == project.id)
                .order_by(Dataset.created_at.asc()).all())
    from ..models import Artifact
    artifacts = (db.query(Artifact)
                 .filter(Artifact.project_id == project.id)
                 .order_by(Artifact.created_at.desc()).all())

    n_ok = sum(1 for e in events if e.status == EventStatus.succeeded)
    n_fail = sum(1 for e in events if e.status == EventStatus.failed)

    overview = (
        f"<div class='stat'><b>{len(events)}</b><span>分析事件</span></div>"
        f"<div class='stat'><b>{n_ok}</b><span>成功</span></div>"
        f"<div class='stat'><b>{n_fail}</b><span>失败</span></div>"
        f"<div class='stat'><b>{len(datasets)}</b><span>数据集</span></div>"
        f"<div class='stat'><b>{len(artifacts)}</b><span>产物</span></div>"
    )

    rows = []
    for e in events:
        cap = _CAP_LABEL.get(e.capability_id, e.capability_id)
        status = "成功" if e.status == EventStatus.succeeded else (
            "失败" if e.status == EventStatus.failed else str(e.status))
        cls = "ok" if e.status == EventStatus.succeeded else "bad" if e.status == EventStatus.failed else "run"
        params = ", ".join(f"{k}={v}" for k, v in (e.parameters or {}).items()) or "—"
        metrics = ", ".join(f"{k}={v}" for k, v in (e.metrics or {}).items()
                            if k not in ("executor_mode", "env_snapshot")) or "—"
        seed = (e.metrics or {}).get("seed", "")
        seed_s = f"<span class='mono'>seed={seed}</span>" if seed else "—"
        rows.append(
            f"<tr><td>{_esc(cap)}</td><td><span class='badge {cls}'>{status}</span></td>"
            f"<td class='mono'>{_esc(params)}</td><td class='mono'>{_esc(metrics)}</td><td>{seed_s}</td></tr>")

    figures = [a for a in artifacts if a.kind == "figure"]
    fig_html = "".join(
        f"<figure><img src='{host}/api/artifacts/{a.id}/content' alt='{_esc(a.name)}' />"
        f"<figcaption>{_esc(a.name)}</figcaption></figure>"
        for a in figures[:12])

    ds_rows = "".join(
        f"<tr><td class='mono'>{_esc(d.name)}</td>"
        f"<td><span class='badge'>{_esc(d.dtype)}</span></td>"
        f"<td><span class='badge'>{_esc(d.phase)}</span></td></tr>"
        for d in datasets)

    generated = utcnow().strftime("%Y-%m-%d %H:%M")

    return f"""<!DOCTYPE html><html lang="zh-CN"><head><meta charset="utf-8">
<title>BioAgent 分析报告 - {_esc(project.name)}</title>
<style>
body {{ font-family: -apple-system,'PingFang SC','Segoe UI',sans-serif; max-width: 960px; margin: 40px auto; padding: 0 24px; color:#18181b; line-height:1.6; }}
h1 {{ font-size: 22px; border-bottom: 2px solid #4f46e5; padding-bottom: 10px; }}
h2 {{ font-size: 16px; color:#4f46e5; margin-top: 32px; }}
.meta {{ color:#71717a; font-size: 12px; }}
.stats {{ display:flex; gap:14px; flex-wrap:wrap; margin: 16px 0; }}
.stat {{ background:#f6f7f9; border:1px solid #e7e9ee; border-radius:10px; padding:12px 20px; text-align:center; }}
.stat b {{ display:block; font-size:20px; color:#4f46e5; }}
.stat span {{ color:#71717a; font-size:12px; }}
table {{ width:100%; border-collapse:collapse; font-size:12.5px; margin:12px 0; }}
th,td {{ border:1px solid #e7e9ee; padding:6px 9px; text-align:left; }}
th {{ background:#f6f7f9; font-weight:600; }}
.badge {{ border-radius:999px; padding:1px 9px; font-size:11px; font-weight:600; }}
.badge.ok {{ background:#e8f7ee; color:#16a34a; }}
.badge.bad {{ background:#fdeaea; color:#dc2626; }}
.badge.run {{ background:#fdf3e1; color:#d97706; }}
.mono {{ font-family:Menlo,Consolas,monospace; font-size:11px; }}
figure {{ margin:12px 0; }}
figure img {{ max-width:100%; border:1px solid #e7e9ee; border-radius:10px; }}
figcaption {{ color:#71717a; font-size:11px; margin-top:4px; }}
footer {{ margin-top:40px; color:#9aa0ab; font-size:11px; text-align:center; }}
</style></head><body>
<h1>BioAgent 分析报告</h1>
<div class="meta">项目：{_esc(project.name)} · 生成时间：{generated} · BioAgent v0.1</div>
<div class="stats">{overview}</div>

<h2>分析流程</h2>
<table><thead><tr><th>分析步骤</th><th>状态</th><th>参数</th><th>关键指标</th><th>可复现</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table>

<h2>数据集版本链</h2>
<table><thead><tr><th>数据集</th><th>类型</th><th>阶段</th></tr></thead>
<tbody>{ds_rows}</tbody></table>

<h2>关键产物</h2>
{fig_html or '<div class="meta">暂无图产物</div>'}

<footer>由 BioAgent 自动生成 · 分析过程可追溯、可复现（每个事件记录参数/指标/随机种子/环境快照）</footer>
</body></html>"""


def render_report_to_file(db, project: Project) -> Path:
    """生成报告 HTML 文件，返回路径。"""
    import time
    html_text = build_report_html(db, project)
    reports_dir = settings.data_dir / "projects" / project.id / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    fname = f"analysis_report_{int(time.time())}.html"
    path = reports_dir / fname
    path.write_text(html_text, encoding="utf-8")
    return path
