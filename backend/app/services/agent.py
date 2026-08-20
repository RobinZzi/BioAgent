"""Agent Runtime（v0.1 规则引擎）。

受限对话闭环：意图解析 → 上下文补全 → 前置链规划 → 执行。
接口与 v0.2 LLM 版一致（parse_intent 返回 capability + params + 说明）。

见 docs/TECHNICAL_DESIGN.md §6。
"""
import re

from sqlalchemy.orm import Session

from ..capabilities.definitions import (
    PREREQ, get_capability, phase_rank, validate_parameters,
)
from ..models import AnalysisEvent, Conversation, Dataset, EventStatus
from .execution import create_and_run_event
from . import llm as llm_svc

# ---------------------------------------------------------------- 意图规则
# (关键词列表, capability_id, 参数缺省, 说明)。顺序即优先级（先匹配先得）。
INTENT_RULES: list[tuple[list[str], str, dict, str]] = [
    (["fastqc", "下机质量", "碱基质量"], "bulk_rna.fastqc", {}, "FastQC 质控"),
    (["cellranger", "10x", "单细胞下机", "下机单细胞"], "scrna.import_10x", {}, "10x 下机导入"),
    (["trim", "裁切", "去接头", "cutadapt", "接头"], "bulk_rna.trimming", {}, "去接头裁切"),
    (["定量", "quantification", "featurecounts", "count matrix"], "bulk_rna.quantification", {}, "基因定量"),
    (["注释", "annotation", "annotate", "细胞类型"], "scrna.annotation", {}, "细胞注释"),
    (["标记基因", "marker gene", "marker"], "scrna.marker_genes", {}, "标记基因分析"),
    (["聚类", "cluster", "clustering", "leiden", "louvain"], "scrna.clustering", {}, "Leiden 聚类"),
    (["umap"], "scrna.umap", {}, "UMAP 可视化"),
    (["neighbors", "邻接"], "scrna.neighbors", {}, "构建邻接图"),
    (["pca"], "scrna.pca", {}, "PCA 降维"),
    (["高变基因", "hvg"], "scrna.hvg", {}, "高变基因"),
    (["标准化", "归一化", "normalize", "normalization"], "scrna.normalization", {}, "标准化"),
    (["qc", "质控", "质量"], "scrna.qc", {}, "细胞 QC"),
    (["检查", "看看", "inspect", "概况", "数据长什么样"], "scrna.inspect", {}, "数据检查"),
    (["gsea"], "bulk_rna.gsea", {}, "GSEA 富集"),
    (["go 富集", "go enrichment", "富集分析"], "bulk_rna.go_enrichment", {}, "GO 富集"),
    (["heatmap", "热图"], "bulk_rna.heatmap", {}, "差异基因热图"),
    (["volcano", "火山图"], "bulk_rna.volcano", {}, "火山图"),
    (["差异表达", "差异基因", "deseq", "edger", "diff exp"], "bulk_rna.differential_expression", {}, "差异表达分析"),
    (["bulk 标准化"], "bulk_rna.normalization", {}, "Bulk 标准化"),
    (["bulk qc", "bulk 质控"], "bulk_rna.qc", {}, "Bulk QC"),
    (["比对", "alignment", "star", "bam"], "bulk_rna.alignment", {}, "序列比对"),
]

# 参数解析：支持 "分辨率 1.0" / "resolution=0.8" / "res 2.0" / "min_genes 300" 等
_PARAM_PATTERNS: dict[str, list[str]] = {
    "resolution": [r"分辨率\s*[:=]?\s*([\d.]+)", r"res(?:olution)?\s*[:=]?\s*([\d.]+)"],
    "n_top_genes": [r"n_top_genes\s*[:=]?\s*(\d+)", r"top(\d+)", r"高变基因数\s*[:=]?\s*(\d+)"],
    "min_genes": [r"min_genes\s*[:=]?\s*(\d+)"],
    "max_mito_pct": [r"max_mito_pct\s*[:=]?\s*(\d+)", r"线粒体\s*[:=]?\s*(\d+)"],
    "padj_cutoff": [r"padj\s*[:=]?\s*([\d.]+)"],
    "threads": [r"threads?\s*[:=]?\s*(\d+)"],
}

# "继续" 自动推进映射：当前阶段 → 下一步能力
CONTINUE_MAP = {
    "raw": "scrna.qc",
    "qc": "scrna.normalization",
    "normalized": "scrna.pca",
    "pca": "scrna.neighbors",
    "neighbors": "scrna.umap",
    "umap": "scrna.clustering",
    "clustered": "scrna.annotation",
    "annotated": "scrna.marker_genes",
    "de": "bulk_rna.volcano",
}


def _extract_params(text: str) -> dict:
    params: dict = {}
    for key, patterns in _PARAM_PATTERNS.items():
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                raw = m.group(1)
                try:
                    params[key] = float(raw) if "." in raw else int(raw)
                except ValueError:
                    pass
                break
    return params


def parse_intent(text: str) -> tuple[str, dict, str] | None:
    """把用户消息解析为 (capability_id, 参数, 说明)。无法识别返回 None。"""
    low = text.lower().strip()
    params = _extract_params(text)

    # 重新/换个 → 由上层按 capability 重跑（这里只返回 capability）
    for keywords, cap_id, defaults, desc in INTENT_RULES:
        if any(k in low for k in keywords):
            merged = {**defaults, **params}
            return cap_id, merged, desc
    return None


# ---------------------------------------------------------------- 规划

class PlanError(Exception):
    """规划失败（结构化消息给用户）。"""


def find_dataset(db: Session, project_id: str, dtype: str, phase: str) -> Dataset | None:
    return (
        db.query(Dataset)
        .filter(Dataset.project_id == project_id, Dataset.dtype == dtype, Dataset.phase == phase)
        .order_by(Dataset.created_at.desc())
        .first()
    )


def _needed_chain(capability_id: str, current_phase: str) -> list[str]:
    """返回从当前阶段到目标 capability 所需的前置能力链（不含目标，按阶段升序）。"""
    cap = get_capability(capability_id)
    if cap is None:
        raise PlanError(f"未知分析能力: {capability_id}")
    domain = cap["domain"]
    needed: list[str] = []
    visited: set[str] = set()

    def walk(cid: str) -> None:
        c = get_capability(cid)
        if c is None:
            return
        # 该能力的结果阶段是否已满足当前阶段
        resulting = c.get("resulting_phase")
        if resulting and phase_rank(domain, resulting) <= phase_rank(domain, current_phase):
            return
        for pre in PREREQ.get(cid, []):
            walk(pre)
        if cid not in visited:
            visited.add(cid)
            needed.append(cid)

    walk(capability_id)
    # 按结果阶段排序，保证执行顺序
    needed.sort(key=lambda c: phase_rank(domain, get_capability(c).get("resulting_phase") or 0))
    return needed


def plan_capability(db: Session, conversation: Conversation, capability_id: str,
                    params: dict) -> list[dict]:
    """规划执行步骤。返回 [{"capability_id", "params", "dataset_id"}]。

    dataset_id 为每一步的输入数据集；链式步骤之间的输入由调用方顺序衔接。
    """
    cap = get_capability(capability_id)
    if cap is None:
        raise PlanError(f"未知分析能力: {capability_id}")

    current_phase = conversation.current_phase
    dtype = cap["dataset_dtype"]
    requires_phase = cap["requires_phase"]

    # 目标能力需要的前置链（含目标自身，去重）
    chain = _needed_chain(capability_id, current_phase)
    if phase_rank(cap["domain"], requires_phase) > phase_rank(cap["domain"], current_phase):
        chain.append(capability_id)
    chain = list(dict.fromkeys(chain))

    # 直接执行目标（当前阶段已满足前置）
    if capability_id not in chain:
        ds = find_dataset(db, conversation.project_id, dtype, requires_phase)
        if ds is None:
            raise PlanError(
                f"当前项目缺少 {requires_phase} 阶段的 {dtype} 数据集，无法执行 {cap['name']}。"
                f"当前状态：{current_phase}。")
        validated, errs = validate_parameters(cap, params)
        if errs:
            raise PlanError("参数校验失败: " + "; ".join(errs))
        return [{"capability_id": capability_id, "params": validated, "dataset_id": ds.id}]

    # 链式执行：首步输入 = 对应阶段数据集；后续步骤输入 = 上一步输出
    steps: list[dict] = []
    first = True
    for cid in chain:
        c = get_capability(cid)
        if cid == capability_id:
            step_params, errs = validate_parameters(c, params)
        else:
            step_params, errs = validate_parameters(c, {})
        if errs:
            raise PlanError("参数校验失败: " + "; ".join(errs))

        ds_id = None
        if first:
            ds = find_dataset(db, conversation.project_id, c["dataset_dtype"], c["requires_phase"])
            if ds is None:
                # dtype 桥接：需要 scrna 数据集但只有 fastq → 自动补 10x 导入
                if c["dataset_dtype"] == "scrna":
                    fastq_ds = find_dataset(db, conversation.project_id, "fastq", "raw")
                    if fastq_ds is not None:
                        imp = get_capability("scrna.import_10x")
                        imp_params, _ = validate_parameters(imp, {})
                        steps.append({"capability_id": "scrna.import_10x",
                                      "params": imp_params, "dataset_id": fastq_ds.id})
                        steps.append({"capability_id": cid, "params": step_params,
                                      "dataset_id": None})  # 输入 = import 输出
                        first = False
                        continue
                raise PlanError(f"缺少 {c['requires_phase']} 阶段的 {c['dataset_dtype']} 数据集，无法开始 {c['name']}。")
            ds_id = ds.id
        steps.append({"capability_id": cid, "params": step_params, "dataset_id": ds_id})
        first = False
    return steps


# ---------------------------------------------------------------- 执行

def execute_plan(db: Session, conversation: Conversation, steps: list[dict],
                 message_id: str | None = None) -> list[AnalysisEvent]:
    """按序执行计划，衔接输入数据集（前一步输出 → 下一步输入），返回事件列表。"""
    events: list[AnalysisEvent] = []
    project = conversation.project
    for step in steps:
        cap_id = step["capability_id"]
        input_ds: Dataset | None = None
        if step.get("dataset_id"):
            input_ds = db.get(Dataset, step["dataset_id"])
        elif events:
            # 前一步的输出数据集（取最新）
            prev = events[-1]
            out_ids = prev.output.get("datasets") or []
            if out_ids:
                input_ds = db.get(Dataset, out_ids[-1])
        if input_ds is None:
            input_ds = find_dataset(db, conversation.project_id, "scrna", "raw") or \
                find_dataset(db, conversation.project_id, "bulk_rna", "raw") or \
                find_dataset(db, conversation.project_id, "fastq", "raw")
        ev = create_and_run_event(
            db, project, conversation, cap_id, step["params"], input_ds,
            message_id=message_id)
        events.append(ev)
        # 链中断：某步失败立即停止，避免后续步骤静默用错误输入继续
        if ev.status == EventStatus.failed:
            break
    return events


def rerun_event(db: Session, conversation: Conversation, original: AnalysisEvent,
                params: dict | None = None) -> AnalysisEvent:
    """重跑事件（re_run 边）。用于「重新聚类」「换个分辨率」等。"""
    project = conversation.project
    input_ds = None
    if original.inputs.get("dataset"):
        input_ds = db.get(Dataset, original.inputs["dataset"])
    if input_ds is None:
        raise PlanError("原事件输入数据集不存在，无法重跑。")
    cap = get_capability(original.capability_id)
    merged = {**original.parameters, **(params or {})}
    return create_and_run_event(
        db, project, conversation, original.capability_id, merged, input_ds,
        message_id=original.message_id,
        relation_parent_id=original.id, relation="re_run",
        force_impl=original.implementation)


def last_event_by_capability(db: Session, conversation_id: str,
                             capability_id: str) -> AnalysisEvent | None:
    return (
        db.query(AnalysisEvent)
        .filter(AnalysisEvent.conversation_id == conversation_id,
                AnalysisEvent.capability_id == capability_id)
        .order_by(AnalysisEvent.created_at.desc())
        .first()
    )


def handle_message(db: Session, conversation: Conversation, content: str,
                   user_msg: "Message | None" = None,
                   assistant_msg: "Message | None" = None) -> dict:
    """处理一条用户消息：解析 → 规划 → 执行 → 生成回复。

    user_msg / assistant_msg：异步模式下由调用方预创建（用户消息立即可见、
    助手消息占位），本函数填充内容；None 时自动创建。
    """
    from ..models import Message, MessageRole

    # 异步模式下传入的对象可能属于其他会话（游离态），按 id 重新加载到当前会话
    if user_msg is not None:
        fresh = db.get(Message, user_msg.id)
        if fresh is not None:
            user_msg = fresh
    if assistant_msg is not None:
        fresh = db.get(Message, assistant_msg.id)
        if fresh is not None:
            assistant_msg = fresh

    if user_msg is None:
        user_msg = Message(conversation_id=conversation.id, role=MessageRole.user,
                           content=content)
        db.add(user_msg)
        db.flush()

    def reply(text: str, events: list) -> dict:
        if assistant_msg is None:
            assistant = Message(conversation_id=conversation.id,
                                role=MessageRole.assistant, content=text)
            db.add(assistant)
        else:
            assistant = assistant_msg
            assistant.content = text
        db.flush()
        db.commit()
        return {"user_message": user_msg, "assistant_message": assistant, "events": events}

    intent = None
    llm_ctx = None
    if llm_svc.enabled():
        datasets = (db.query(Dataset)
                    .filter(Dataset.project_id == conversation.project_id)
                    .order_by(Dataset.created_at.desc()).all())
        llm_ctx = llm_svc.build_context(conversation, datasets)
        llm_res = llm_svc.parse_intent_llm(content, llm_ctx)
        if llm_res is not None and llm_res.capability_id:
            intent = (llm_res.capability_id, llm_res.parameters, llm_res.note)

    if intent is None:
        intent = parse_intent(content)

    if intent is None:
        # 识别「继续」
        if "继续" in content or "下一步" in content:
            nxt = CONTINUE_MAP.get(conversation.current_phase)
            if nxt:
                intent = (nxt, {}, f"继续分析（当前阶段 {conversation.current_phase}）")
            else:
                return reply("当前阶段没有自动推进的下一步。你可以试试：聚类 / QC / 注释 / UMAP / 差异表达。", [])
        else:
            return reply(
                "我暂时无法理解这个请求（v0.1 规则引擎）。\n"
                "可用的分析能力：\n"
                "- scRNA：数据检查 / QC / 标准化 / PCA / UMAP / 聚类 / 标记基因 / 细胞注释\n"
                "- Bulk：差异表达 / 火山图 / 热图 / GO / GSEA\n"
                "- 试试直接说：\u201c聚类，分辨率 1.0\u201d、\u201c继续\u201d", [])

    cap_id, params, note = intent

    # 「重新」语义：重跑同能力最近一次事件
    if re.search(r"(重新|再|换个|换一个)", content):
        last = last_event_by_capability(db, conversation.id, cap_id)
        if last:
            try:
                ev = rerun_event(db, conversation, last, params)
            except PlanError as e:
                return reply(f"无法重跑：{e}", [])
            user_msg.triggered_event_ids = [ev.id]
            return reply(f"已按新参数重跑 {note}（事件 {ev.id}）。" + _event_summary(ev), [ev])

    try:
        steps = plan_capability(db, conversation, cap_id, params)
    except PlanError as e:
        return reply(f"无法执行：{e}", [])

    events = execute_plan(db, conversation, steps, message_id=user_msg.id)
    user_msg.triggered_event_ids = [e.id for e in events]
    db.flush()

    lines = [f"已执行 {note}："]
    for ev in events:
        lines.append(_event_summary(ev))
    final_reply = "\n".join(lines)
    if llm_svc.enabled() and llm_ctx is not None:
        enhanced = llm_svc.generate_reply_llm(content, final_reply, llm_ctx)
        if enhanced:
            final_reply = enhanced
    return reply(final_reply, events)


def _event_summary(ev: AnalysisEvent) -> str:
    if ev.status == EventStatus.failed:
        err = (ev.error or {}).get("message", "未知错误")
        return f"- {ev.capability_id} 失败：{err}"
    metrics = ev.metrics
    detail = ""
    if ev.capability_id == "scrna.clustering":
        detail = f"（resolution={metrics.get('resolution')}，{metrics.get('n_clusters')} 簇）"
    elif ev.capability_id == "scrna.qc":
        detail = f"（{metrics.get('cells_before')} → {metrics.get('cells_after')} 细胞）"
    elif ev.capability_id == "bulk_rna.differential_expression":
        detail = f"（上调 {metrics.get('n_up')} / 下调 {metrics.get('n_down')}）"
    out = ev.output
    n_art = len(out.get("artifacts") or [])
    n_ds = len(out.get("datasets") or [])
    return f"- {ev.capability_id}{detail}（产物 {n_art} 个，数据集 {n_ds} 个，{ev.id}）"
