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
    {"slug": "opportunity_strong_pain", "task": "从多个独立来源判断一个重复痛点是否值得形成机会候选。", "expected_intent": "opportunity_analysis", "key_unknowns": ["severity", "frequency", "counterevidence"], "required_evidence_types": ["pain", "independent", "counterevidence"], "forbidden_scope_drift": ["guaranteed revenue"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "opportunity_single_marketing", "task": "只有一篇营销文章时，判断是否可以形成商业机会。", "expected_intent": "opportunity_analysis", "key_unknowns": ["independence", "user demand"], "required_evidence_types": ["source independence"], "forbidden_scope_drift": ["market size claim"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "opportunity_repost_noise", "task": "合并重复转载，避免把内容数量当作机会证据。", "expected_intent": "opportunity_analysis", "key_unknowns": ["original source", "independent count"], "required_evidence_types": ["repost grouping"], "forbidden_scope_drift": ["viral claim"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "opportunity_insufficient", "task": "证据不足时明确返回需要更多证据，而不是强行生成机会。", "expected_intent": "opportunity_analysis", "key_unknowns": ["independent confirmation"], "required_evidence_types": ["unknown"], "forbidden_scope_drift": ["unsupported opportunity"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "opportunity_competition", "task": "高热度但高竞争的方向是否仍值得验证。", "expected_intent": "opportunity_analysis", "key_unknowns": ["saturation", "differentiation"], "required_evidence_types": ["saturation", "counterevidence"], "forbidden_scope_drift": ["high score equals success"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "opportunity_novel_weak_demand", "task": "新颖但需求弱的想法应当如何降级。", "expected_intent": "opportunity_analysis", "key_unknowns": ["demand", "actionability"], "required_evidence_types": ["direct demand"], "forbidden_scope_drift": ["model imagination"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "opportunity_counterevidence", "task": "强反向证据出现时更新机会成熟度和解释。", "expected_intent": "opportunity_analysis", "key_unknowns": ["contradiction", "readiness"], "required_evidence_types": ["contradictory", "version history"], "forbidden_scope_drift": ["silent overwrite"], "minimum_sources": 2, "partial_completion_allowed": True},
    {"slug": "content_gap", "task": "从重复困惑和真实案例缺失中识别内容缺口，不把它称为全网热点。", "expected_intent": "content_opportunity", "key_unknowns": ["audience", "content gap", "saturation"], "required_evidence_types": ["user signal", "source bound"], "forbidden_scope_drift": ["automatic publishing"], "minimum_sources": 2, "partial_completion_allowed": True},
)

# Recorded responses are replay fixtures, not product answers or live research
# results. They exercise two fixed cases while leaving the remaining cases
# explicitly uninstrumented.
RECORDED_EVAL_RESPONSE: dict[str, dict[str, object]] = {
    "product_exploration": {
        "intent": "discovery",
        "evidence": [
            {"content_id": "recorded-product-content-1"},
            {"content_id": "recorded-product-content-2"},
        ],
        "model_call_count": 2,
        "input_tokens": 100,
        "output_tokens": 80,
        "runtime_ms": 1200,
        "metrics": {
            "target_coverage": 1.0,
            "scope_drift": 0.0,
            "query_acceptance": 1.0,
            "novel_information_rate": 0.8,
            "independent_evidence_rate": 1.0,
            "duplicate_rate": 0.0,
            "error_inference_rate": 0.0,
            "candidate_adoption_rate": 0.5,
        },
    },
    "product_monitoring": {
        "intent": "monitoring",
        "evidence": [
            {"content_id": "recorded-monitoring-content-1"},
            {"content_id": "recorded-monitoring-content-2"},
        ],
        "model_call_count": 2,
        "input_tokens": 120,
        "output_tokens": 90,
        "runtime_ms": 1400,
        "metrics": {
            "target_coverage": 1.0,
            "scope_drift": 0.0,
            "query_acceptance": 1.0,
            "novel_information_rate": 0.7,
            "independent_evidence_rate": 1.0,
            "duplicate_rate": 0.0,
            "error_inference_rate": 0.0,
            "candidate_adoption_rate": 0.5,
        },
    },
}


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
    result = {
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
    if expected_intent in {"opportunity_analysis", "content_opportunity"}:
        result.update(
            {
                "opportunity_evidence_coverage": _instrumented_or_unknown(metrics.get("opportunity_evidence_coverage")),
                "opportunity_source_independence": _instrumented_or_unknown(metrics.get("opportunity_source_independence")),
                "counterevidence_presence": _instrumented_or_unknown(metrics.get("counterevidence_presence")),
                "opportunity_to_validation_conversion": _instrumented_or_unknown(metrics.get("opportunity_to_validation_conversion")),
                "validation_completion": _instrumented_or_unknown(metrics.get("validation_completion")),
                "action_completion_rate": _instrumented_or_unknown(metrics.get("action_completion_rate")),
                "content_opportunity_accept_rate": _instrumented_or_unknown(metrics.get("content_opportunity_accept_rate")),
            }
        )
    return result


def result_status_for_metrics(metrics: Mapping[str, object]) -> str:
    """Classify metrics without treating valid zero-valued rates as failures."""

    blocking_metrics = ("intent_consistency", "fact_evidence_binding")
    if any(metrics.get(key) == 0.0 for key in blocking_metrics):
        return "failed"
    if any(value == "not_instrumented" for value in metrics.values()):
        return "partial"
    return "passed"


def replay_recorded_task(
    cases: tuple[Mapping[str, object], ...],
    recorded_response: Mapping[str, object],
) -> list[dict[str, object]]:
    return [
        evaluate_recorded_response(case, recorded_response.get(str(case.get("slug")), {}))
        for case in cases
    ]
