"""LLM Agent 服务（v0.2）。

模式（settings.llm_mode）:
  off  —— 不调用 LLM，走规则引擎（默认；未配置 Key 时）
  echo —— 测试模式：不调 API，用规则引擎生成"模拟 LLM 结果"，
          用于端到端验证 LLM 集成链路（提示词构建→解析→校验→执行）
  real —— OpenAI 兼容 Chat Completions API（DeepSeek / OpenAI / 任意兼容端点）

意图解析返回结构化 IntentResult；回复生成返回自然语言。任何失败返回 None，
由上层回退规则引擎。零第三方依赖（urllib）。
"""
import json
import urllib.error
import urllib.request

from ..capabilities.definitions import (
    CAPABILITIES_BY_ID, get_capability, list_capabilities, validate_parameters,
)
from ..config import settings

_SYSTEM_PROMPT = """你是 BioAgent 的生物信息学分析助手。BioAgent 是一个面向 Bulk RNA-seq 与单细胞 RNA-seq 的 AI 分析工作平台。

你的任务：把用户的自然语言分析请求解析为平台能力调用。
规则：
1. 从给定的能力清单中选择一个最匹配的 capability_id。
2. 参数必须符合该能力的参数 schema（枚举值/范围/默认值），未提及的参数省略（平台会补默认值）。
3. 只输出一个 JSON 对象，不要输出任何其他文字，格式：
   {"capability_id": "...", "parameters": {...}, "note": "一句话说明你打算做什么"}
4. 如果用户请求不是任何能力能覆盖的分析操作（闲聊、提问、无关内容），输出：
   {"capability_id": null, "parameters": {}, "note": "无法识别的请求"}
"""


class IntentResult:
    def __init__(self, capability_id: str | None, parameters: dict, note: str, source: str):
        self.capability_id = capability_id
        self.parameters = parameters
        self.note = note
        self.source = source


def llm_status() -> dict:
    if settings.llm_mode == "real":
        return {
            "mode": "real", "configured": bool(settings.llm_api_key),
            "model": settings.llm_model, "base_url": settings.llm_base_url,
            "description": "OpenAI 兼容 API",
        }
    if settings.llm_mode == "echo":
        return {"mode": "echo", "configured": True, "model": "echo",
                "description": "测试模式：模拟 LLM 返回，不调用真实 API"}
    return {"mode": "off", "configured": False, "model": None,
            "description": "规则引擎（未启用 LLM；设置 BIOAGENT_LLM_MODE=real 并配置 Key）"}


def enabled() -> bool:
    return settings.llm_mode in ("real", "echo")


# ---------------------------------------------------------------- 上下文构建

def _capability_catalog() -> list[dict]:
    out = []
    for c in list_capabilities():
        out.append({
            "capability_id": c["capability_id"],
            "name": c["name"],
            "domain": c["domain"],
            "requires_phase": c["requires_phase"],
            "resulting_phase": c["resulting_phase"],
            "description": c["description"],
            "parameters": {k: {kk: vv for kk, vv in v.items() if kk != "description"}
                           for k, v in c["parameters"].items()},
        })
    return out


def build_context(conversation, datasets: list | None = None) -> dict:
    ctx = {
        "current_phase": conversation.current_phase,
        "current_dataset_id": conversation.current_dataset_id,
        "analysis_state": conversation.analysis_state or {},
    }
    if datasets:
        ctx["datasets"] = [{"id": d.id, "name": d.name, "phase": d.phase, "dtype": str(d.dtype)}
                           for d in datasets[-12:]]
    return ctx


# ---------------------------------------------------------------- 意图解析

def parse_intent_llm(content: str, context: dict) -> IntentResult | None:
    """LLM 意图解析。失败返回 None（上层回退规则引擎）。"""
    try:
        if settings.llm_mode == "echo":
            return _echo_intent(content, context)
        return _real_intent(content, context)
    except Exception:  # noqa: BLE001
        return None


def _echo_intent(content: str, context: dict) -> IntentResult | None:
    """echo 模式：用规则引擎充当"模拟 LLM"，验证集成链路。"""
    from .agent import parse_intent  # 延迟导入避免循环
    res = parse_intent(content)
    if res is None:
        return IntentResult(None, {}, "无法识别的请求", "echo")
    cap_id, params, note = res
    return IntentResult(cap_id, params, note, "echo")


def _real_intent(content: str, context: dict) -> IntentResult | None:
    if not settings.llm_api_key:
        return None
    prompt = json.dumps({
        "capability_catalog": _capability_catalog(),
        "context": context,
        "user_message": content,
    }, ensure_ascii=False)
    text = _chat([{"role": "system", "content": _SYSTEM_PROMPT},
                  {"role": "user", "content": prompt}])
    data = _parse_json_response(text)
    if data is None:
        return None
    cap_id = data.get("capability_id")
    if not cap_id or cap_id not in CAPABILITIES_BY_ID:
        return IntentResult(None, {}, data.get("note", "无法识别的请求"), "real")
    cap = get_capability(cap_id)
    validated, errs = validate_parameters(cap, data.get("parameters") or {})
    if errs:
        # 参数不合法 → 交回规则引擎或按默认值执行（这里用默认值）
        validated, _ = validate_parameters(cap, {})
    return IntentResult(cap_id, validated, data.get("note", cap["name"]), "real")


# ---------------------------------------------------------------- 回复生成

def generate_reply_llm(user_content: str, event_summary: str, context: dict) -> str | None:
    """用 LLM 生成自然语言回复。失败/echo 返回 None（模板回复兜底）。"""
    if settings.llm_mode != "real" or not settings.llm_api_key:
        return None
    try:
        prompt = json.dumps({
            "context": context,
            "user_message": user_content,
            "execution_result": event_summary,
        }, ensure_ascii=False)
        text = _chat([
            {"role": "system", "content":
             "你是 BioAgent 的分析助手。用户刚请求了分析，执行结果如下。"
             "请用简洁中文回复：总结执行结果，给出对结果的一句话解读，并建议下一步（如果结果异常则指出）。"
             "200 字以内，不要用 markdown 标题。"},
            {"role": "user", "content": prompt},
        ])
        text = text.strip()
        return text or None
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------- HTTP

def _chat(messages: list[dict]) -> str:
    payload = {
        "model": settings.llm_model,
        "messages": messages,
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    req = urllib.request.Request(
        settings.llm_base_url.rstrip("/") + "/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {settings.llm_api_key}"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=settings.llm_timeout) as resp:
        body = json.loads(resp.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def _parse_json_response(text: str) -> dict | None:
    """从模型输出中提取 JSON（容忍代码块包裹 / 前后杂文）。"""
    if not text:
        return None
    text = text.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(l for l in lines if not l.startswith("```"))
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        return None
    try:
        return json.loads(text[start:end + 1])
    except json.JSONDecodeError:
        return None
