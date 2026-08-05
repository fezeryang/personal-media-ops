"""Answer-independent fixed eval cases and recorded-response replay helpers."""

from __future__ import annotations

from collections.abc import Mapping

FIXED_EVAL_DATASET: tuple[dict[str, object], ...] = (
    {"slug": "product_exploration", "task": "最近有哪些值得关注的个人AI工具？", "expected_intent": "discovery", "key_unknowns": ["product names", "meaningful differences"], "required_evidence_types": ["direct", "independent", "counterevidence"], "forbidden_scope_drift": ["generic history", "single marketing source"], "minimum_sources": 3, "partial_completion_allowed": True},
    {"slug": "pain_point", "task": "用户在抱怨哪些AI工具不好用？", "expected_intent": "pain_point_research", "key_unknowns": ["pain points", "severity", "independent confirmation"], "required_evidence_types": ["negative", "independent"], "forbidden_scope_drift": ["positive feature roundup"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "product_comparison", "task": "比较Codex与WorkBuddy的长期记忆、Skills和自动化差异。", "expected_intent": "comparison", "key_unknowns": ["memory", "skills", "automation"], "required_evidence_types": ["direct", "comparison"], "forbidden_scope_drift": ["unrelated pricing"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "trend_change", "task": "最近个人AI工作台发生了什么趋势变化？", "expected_intent": "trend_tracking", "key_unknowns": ["new signals", "persistence"], "required_evidence_types": ["event", "independent"], "forbidden_scope_drift": ["all-time background"], "minimum_sources": 3, "partial_completion_allowed": True},
    {"slug": "fact_verification", "task": "验证某AI工具是否真的支持本地自动化。", "expected_intent": "verification", "key_unknowns": ["capability", "version", "scope"], "required_evidence_types": ["direct", "versioned"], "forbidden_scope_drift": ["unverified comments"], "minimum_sources": 1, "partial_completion_allowed": True},
    {"slug": "creator_monitoring", "task": "持续关注一个AI创作者的研究方向变化。", "expected_intent": "creator_scan", "key_unknowns": ["new themes", "repeated themes"], "required_evidence_types": ["creator", "timeline"], "forbidden_scope_drift": ["creator popularity ranking"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "product_monitoring", "task": "持续关注一个AI产品的功能和用户评价变化。", "expected_intent": "monitoring", "key_unknowns": ["feature changes", "feedback changes"], "required_evidence_types": ["baseline", "change", "independent"], "forbidden_scope_drift": ["basic introduction"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "event_tracking", "task": "持续跟踪一个AI产品的重要事件。", "expected_intent": "monitoring", "key_unknowns": ["event status", "latest update"], "required_evidence_types": ["event", "timestamp"], "forbidden_scope_drift": ["unrelated company news"], "minimum_sources": 1, "partial_completion_allowed": True},
    {"slug": "negative_change", "task": "关注AI工具不稳定、复杂或价格高的真实反馈变化。", "expected_intent": "pain_point_research", "key_unknowns": ["negative evidence", "severity", "persistence"], "required_evidence_types": ["negative", "independent", "timeline"], "forbidden_scope_drift": ["marketing claims"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "content_signal", "task": "识别真实用户讨论中值得继续研究的内容信号。", "expected_intent": "content_opportunity", "key_unknowns": ["recurrence", "unmet need"], "required_evidence_types": ["user signal", "source bound"], "forbidden_scope_drift": ["automatic publishing"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "insufficient_evidence", "task": "验证一个目前只有单一来源的AI工具说法。", "expected_intent": "verification", "key_unknowns": ["independent confirmation"], "required_evidence_types": ["counterevidence", "source independence"], "forbidden_scope_drift": ["market consensus"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "platform_unavailable", "task": "监控一个需要验证码的平台上的AI工具变化。", "expected_intent": "monitoring", "key_unknowns": ["platform availability", "change evidence"], "required_evidence_types": ["platform status", "partial evidence"], "forbidden_scope_drift": ["synthetic result"], "minimum_sources": 0, "partial_completion_allowed": True},
)


def _instrumented_or_unknown(value: object) -> object:
    return value if value is not None else "not_instrumented"


def evaluate_recorded_response(
    case: Mapping[str, object],
    response: Mapping[str, object],
) -> dict[str, object]:
    """Score only facts present in a recorded response; never infer missing ratios."""

    intent = response.get("intent") or response.get("primary_intent")
    evidence = response.get("evidence")
    evidence_items = evidence if isinstance(evidence, list) else []
    bindings = [
        item
        for item in evidence_items
        if isinstance(item, Mapping) and isinstance(item.get("content_id"), str)
    ]
    metrics = response.get("metrics")
    metrics = metrics if isinstance(metrics, Mapping) else {}
    expected_intent = case.get("expected_intent")
    return {
        "case_slug": case.get("slug"),
        "intent_consistency": 1.0 if intent == expected_intent else 0.0 if intent is not None else "not_instrumented",
        "target_coverage": _instrumented_or_unknown(metrics.get("target_coverage")),
        "scope_drift": _instrumented_or_unknown(metrics.get("scope_drift")),
        "query_acceptance": _instrumented_or_unknown(metrics.get("query_acceptance")),
        "novel_information_rate": _instrumented_or_unknown(metrics.get("novel_information_rate")),
        "independent_evidence_rate": _instrumented_or_unknown(metrics.get("independent_evidence_rate")),
        "duplicate_rate": _instrumented_or_unknown(metrics.get("duplicate_rate")),
        "fact_evidence_binding": 1.0 if bindings and len(bindings) == len(evidence_items) else 0.0 if evidence_items else "not_instrumented",
        "error_inference_rate": _instrumented_or_unknown(metrics.get("error_inference_rate")),
        "candidate_adoption_rate": _instrumented_or_unknown(metrics.get("candidate_adoption_rate")),
        "model_call_count": _instrumented_or_unknown(response.get("model_call_count")),
        "input_tokens": _instrumented_or_unknown(response.get("input_tokens")),
        "output_tokens": _instrumented_or_unknown(response.get("output_tokens")),
        "runtime_ms": _instrumented_or_unknown(response.get("runtime_ms")),
    }


def replay_recorded_task(
    cases: tuple[Mapping[str, object], ...],
    recorded_response: Mapping[str, object],
) -> list[dict[str, object]]:
    return [
        evaluate_recorded_response(case, recorded_response.get(str(case.get("slug")), {}))
        for case in cases
    ]
