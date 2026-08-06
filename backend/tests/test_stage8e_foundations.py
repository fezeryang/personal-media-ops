from __future__ import annotations

from app.services.ai.context_builder import ContextBuilder
from app.services.ai.evals import (
    FIXED_EVAL_DATASET,
    evaluate_recorded_response,
    result_status_for_metrics,
)
from app.services.ai.prompt_registry import (
    PROMPT_ROLES,
    candidate_prompt_specs,
    default_prompt_specs,
    prompt_metadata,
)
from app.services.ai.tool_contract import TOOL_CONTRACT_VERSION, get_tool_contracts


def test_fixed_eval_dataset_is_answer_independent_and_covers_required_scenarios() -> None:
    assert len(FIXED_EVAL_DATASET) >= 12
    slugs = {case["slug"] for case in FIXED_EVAL_DATASET}
    assert {"product_exploration", "pain_point", "product_comparison", "platform_unavailable"} <= slugs
    for case in FIXED_EVAL_DATASET:
        assert case["expected_intent"]
        assert case["key_unknowns"]
        assert case["required_evidence_types"]
        assert "golden_answer" not in case


def test_eval_response_marks_uninstrumented_metrics_without_inventing_scores() -> None:
    result = evaluate_recorded_response(
        FIXED_EVAL_DATASET[0],
        {"intent": "discovery", "evidence": [{"content_id": "c1"}]},
    )
    assert result["intent_consistency"] == 1.0
    assert result["target_coverage"] == "not_instrumented"
    assert result["fact_evidence_binding"] == 1.0


def test_eval_response_treats_zero_drift_and_error_rates_as_good_metrics() -> None:
    result = evaluate_recorded_response(
        FIXED_EVAL_DATASET[0],
        {
            "intent": "discovery",
            "evidence": [{"content_id": "c1"}],
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
    )
    assert result_status_for_metrics(result) == "passed"


def test_prompt_registry_has_explicit_roles_and_call_metadata() -> None:
    specs = default_prompt_specs()
    assert {item["role"] for item in specs} == set(PROMPT_ROLES)
    candidates = candidate_prompt_specs()
    assert candidates == [
        {
            "prompt_key": "intent_interpreter",
            "role": "intent_interpreter",
            "version": "v2",
            "status": "candidate",
            "model_family": "gateway-default",
            "system_prompt": candidates[0]["system_prompt"],
            "task_template": candidates[0]["task_template"],
            "input_schema": {"type": "object"},
            "output_schema": {"type": "object"},
            "temperature": 0.1,
            "max_tokens": 800,
            "change_reason": "8E candidate: explicit monitoring unknowns and evidence boundaries",
        }
    ]
    metadata = prompt_metadata("intent_interpreter", "v1", "ctx-v1", "tools-v1")
    assert metadata == {
        "prompt_key": "intent_interpreter",
        "prompt_version": "v1",
        "context_version": "ctx-v1",
        "tool_contract_version": "tools-v1",
    }


def test_tool_contracts_are_explicit_and_versioned() -> None:
    contracts = get_tool_contracts()
    assert TOOL_CONTRACT_VERSION == "v1"
    assert {item["name"] for item in contracts} >= {
        "search_library",
        "submit_crawl",
        "save_finding",
    }
    assert all(item["input_schema"] and item["failure_types"] for item in contracts)


def test_context_builder_prioritizes_goal_and_evidence_and_preserves_lineage() -> None:
    context, stats = ContextBuilder().build(
        objective="持续关注个人 AI 工具的真实变化",
        intent={"primary_intent": "monitoring", "unknowns_to_discover": ["new features"]},
        findings=[
            {
                "id": "finding-1",
                "kind": "fact",
                "statement": "A feature changed",
                "evidence": [{"content_id": "content-1", "source": "bili", "published_at": "2026-08-01"}],
            }
        ],
        unknowns=["new features"],
        entities=[{"canonical_name": "Tool A"}],
        events=[{"id": "event-1", "title": "release"}],
        queries=[{"id": "query-1", "query": "Tool A update", "parent_unknown": "new features"}],
        raw_contents=[{"id": "content-1", "title": "Feature update", "source": "bili"}],
        max_items=8,
    )
    assert list(context["tiers"]) == ["tier_1", "tier_2", "tier_3", "tier_4", "tier_5", "tier_6"]
    assert context["tiers"]["tier_1"]["objective"] == "持续关注个人 AI 工具的真实变化"
    assert context["tiers"]["tier_2"]["findings"][0]["evidence"][0]["content_id"] == "content-1"
    assert context["tiers"]["tier_5"]["queries"][0]["parent_unknown"] == "new features"
    assert context["tiers"]["tier_6"]["contents"][0]["id"] == "content-1"
    assert stats["raw_content_count"] == 1
    assert stats["deduplicated_content_count"] == 1
