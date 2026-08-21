"""失败诊断与参数修正建议（错误恢复循环）。

给定失败的 AnalysisEvent（含结构化错误 + 日志 + 参数），分析失败原因，
并基于 capability 参数定义域生成修正参数建议，供一键重跑（re_run 边）。
"""
from ..capabilities.definitions import get_capability
from ..models import AnalysisEvent

# 环境类失败：不建议调参，应换实现/环境/凭据
_ENV_FAILURE_TYPES = {
    "RuntimeNotFound", "SchedulerUnavailable", "SSHConnectError",
    "UnsupportedImplementation", "Timeout",
}

# 手动修正建议：针对常见分析失败放宽/调整参数
_MANUAL_SUGGESTIONS = {
    "scrna.qc": {"min_genes": 100, "max_mito_pct": 30},          # 放宽细胞质控
    "bulk_rna.qc": {"min_counts": 5},
    "scrna.hvg": {"n_top_genes": 1000},
    "scrna.pca": {"n_comps": 20},
    "scrna.neighbors": {"n_neighbors": 10},
    "scrna.clustering": {"resolution": 0.5},
    "scrna.annotation": {"method": "marker_based"},
    "bulk_rna.differential_expression": {"padj_cutoff": 0.1},
    "bulk_rna.volcano": {"padj_cutoff": 0.1, "log2fc_cutoff": 0.5},
    "bulk_rna.trimming": {"min_length": 15},
    "bulk_rna.quantification": {"feature_type": "gene"},
}


def diagnose_failure(event: AnalysisEvent) -> dict:
    """分析失败事件，返回结构化诊断 + 参数修正建议。"""
    error = event.error or {}
    etype = error.get("type", "Unknown")
    stage = error.get("stage", "unknown")
    log_tail = error.get("log_tail") or []
    log_text = "\n".join(log_tail).lower()

    # 判定失败类别与人类可读原因
    category, reason = _categorize(etype, stage, log_text)

    # 生成修正参数建议
    suggested = _suggest_params(event.capability_id, event.parameters, etype, log_text)

    message = _compose_message(event.capability_id, category, reason, suggested)
    return {
        "event_id": event.id,
        "capability_id": event.capability_id,
        "failure_type": etype,
        "stage": stage,
        "category": category,
        "reason": reason,
        "suggested_params": suggested,
        "message": message,
    }


def _categorize(etype: str, stage: str, log_text: str) -> tuple[str, str]:
    if etype in _ENV_FAILURE_TYPES:
        return "environment", _env_reason(etype)
    if "import" in log_text or "locator" in log_text or "modulenotfound" in log_text:
        return "environment", "运行时依赖缺失或损坏（如 scanpy 导入失败），建议切换实现或环境"
    if "filenotfound" in log_text or "no such file" in log_text or "unable to open file" in log_text:
        return "data", "输入数据文件不存在或路径错误，请检查数据集路径是否有效"
    if etype == "ScriptError" or "traceback" in log_text:
        return "script", "分析脚本执行出错（多为数据/参数问题），可调整参数重跑"
    if etype == "RemoteScriptError":
        return "remote", "远程服务器脚本执行失败，请检查远程工具环境"
    return "unknown", f"执行失败（{etype}），建议检查后重跑"


def _env_reason(etype: str) -> str:
    return {
        "RuntimeNotFound": "未找到所需运行时/解释器，请切换计算环境或安装工具",
        "SchedulerUnavailable": "调度器（Slurm）不可用，请改用本地执行",
        "SSHConnectError": "SSH 连接失败，请检查服务器地址/账号/凭据",
        "UnsupportedImplementation": "当前实现不支持，请切换实现或环境",
        "Timeout": "执行超时，请减少数据量或提高资源限制",
    }.get(etype, "环境/资源问题")


def _suggest_params(capability_id: str, params: dict, etype: str, log_text: str) -> dict:
    """生成修正参数：环境问题不调参；否则手动建议 + 枚举换值兜底。"""
    if etype in _ENV_FAILURE_TYPES or "import" in log_text or "locator" in log_text:
        return {}

    cap = get_capability(capability_id)
    suggested = dict(params or {})
    # 手动建议
    manual = _MANUAL_SUGGESTIONS.get(capability_id)
    if manual:
        suggested.update(manual)
    # 枚举换值兜底（仅当手动未覆盖该参数时）
    if cap:
        for key, spec in cap.get("parameters", {}).items():
            enum = spec.get("enum")
            if enum and len(enum) > 1 and key not in manual:
                cur = suggested.get(key)
                if cur in enum:
                    suggested[key] = enum[(enum.index(cur) + 1) % len(enum)]
    return suggested


def _compose_message(capability_id: str, category: str, reason: str, suggested: dict) -> str:
    if not suggested:
        return f"【{category}】{reason}"
    params_str = ", ".join(f"{k}={v}" for k, v in suggested.items())
    return f"【{category}】{reason}。建议修正参数后重跑：{params_str}"
