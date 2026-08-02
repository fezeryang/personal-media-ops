from app.services.ai.research_quality import (
    classify_query,
    evaluate_query,
    expected_value_score,
    marginal_stop_decision,
    noise_risk_score,
    normalize_query,
    novelty_score,
    parse_relevance_batch,
    parse_structured_json,
    platform_query_variants,
    query_priority_score,
    specificity_score,
)


def test_query_normalization_and_generic_gate_are_deterministic() -> None:
    assert normalize_query("  AI-Agent，工作流！ ") == "ai agent 工作流"

    rejected = evaluate_query(
        "agent",
        generation_reason="planner candidate",
        source_type="user_goal",
        historical_queries=[],
    )
    assert rejected.accepted is False
    assert rejected.query_type == "generic_topic"
    assert rejected.rejection_reason == "仅包含泛化词，必须与具体实体或限定场景组合"

    accepted = evaluate_query(
        "Claude Code 个人工作流",
        generation_reason="从内容实体 Claude Code 生成体验查询",
        source_type="content_entity",
        historical_queries=[],
        parent_query_id="parent-query",
        source_content_id="content-1",
    )
    assert accepted.accepted is True
    assert accepted.query_type in {"product", "scenario", "technology"}
    assert accepted.noise_risk_score < 0.85


def test_query_history_rejects_exact_and_approximate_duplicates() -> None:
    exact = evaluate_query(
        "WorkBuddy 使用体验",
        generation_reason="from source",
        source_type="content_entity",
        historical_queries=["workbuddy 使用体验"],
        parent_query_id="parent-query",
        source_content_id="content-1",
    )
    assert exact.rejection_reason == "与本任务或历史任务查询重复"

    approximate = evaluate_query(
        "WorkBuddy 使用体验 评价",
        generation_reason="from source",
        source_type="content_entity",
        historical_queries=["WorkBuddy 使用体验 评价"],
        parent_query_id="parent-query",
        source_content_id="content-1",
    )
    assert approximate.novelty_score == 0.0
    assert approximate.accepted is False

    missing_chain = evaluate_query(
        "WorkBuddy 使用体验",
        generation_reason="from source",
        source_type="content_entity",
        historical_queries=[],
    )
    assert missing_chain.rejection_reason == "后续查询必须绑定 parent_query_id 与来源内容或 Finding"


def test_batch_relevance_parser_is_bounded() -> None:
    assert parse_relevance_batch('{"relevance_scores":[0.2, 1.2]}', 2) == [0.2, 1.0]
    assert parse_relevance_batch("[0.2]", 2) is None
    assert parse_relevance_batch('{"relevance_scores":[true]}', 1) is None
    assert expected_value_score(0.8, 0.5, 1.0) == 0.4


def test_query_quality_covers_empty_reason_and_query_type_rules() -> None:
    assert classify_query("") == "generic_topic"
    assert classify_query("用户 痛点") == "need"
    assert classify_query("自动化 工作流") == "scenario"
    assert classify_query("MCP 长期 记忆") == "technology"
    assert classify_query("腾讯 公司") == "company"
    assert classify_query("作者 博主") == "creator"
    assert classify_query("专家 人物") == "person"
    assert classify_query("WorkBuddy 工作台") == "product"
    assert classify_query("软件") == "generic_topic"
    assert specificity_score("AI") == 0.0
    assert noise_risk_score("") == 1.0
    assert noise_risk_score("AI 产品") == 1.0
    assert novelty_score("", []) == 0.0
    assert expected_value_score(None, 1.0, 1.0) is None

    assert evaluate_query(
        "x",
        generation_reason="reason",
        source_type="user_goal",
        historical_queries=[],
    ).rejection_reason == "query 过短或为空"
    assert evaluate_query(
        "WorkBuddy",
        generation_reason=None,
        source_type="user_goal",
        historical_queries=[],
    ).rejection_reason == "缺少 generation_reason"
    assert evaluate_query(
        "AI app api",
        generation_reason="reason",
        source_type="user_goal",
        historical_queries=[],
    ).rejection_reason == "仅包含泛化词，必须与具体实体或限定场景组合"
    assert evaluate_query(
        "AI 产品 WorkBuddy",
        generation_reason="reason",
        source_type="user_goal",
        historical_queries=[],
    ).noise_risk_score >= 0.45


def test_platform_strategy_priority_and_marginal_stop_are_deterministic() -> None:
    assert platform_query_variants("WorkBuddy", "zhihu")[:2] == [
        "WorkBuddy 深度分析",
        "WorkBuddy 需求讨论",
    ]
    assert platform_query_variants("WorkBuddy", "tieba", negative=True)[:3] == [
        "WorkBuddy 问题",
        "WorkBuddy 缺点",
        "WorkBuddy 不好用",
    ]
    assert query_priority_score(
        relevance_score=0.9,
        specificity_score=0.8,
        novelty_score=1.0,
        noise_risk_score=0.1,
        expected_value_score=0.72,
        entity_diversity_bonus=0.8,
        platform_diversity_bonus=0.8,
        negative_evidence_bonus=0.8,
    ) > query_priority_score(
        relevance_score=0.9,
        specificity_score=0.8,
        novelty_score=1.0,
        noise_risk_score=0.1,
        expected_value_score=0.72,
    )
    assert marginal_stop_decision(
        rounds_below_threshold=2,
        threshold=0.1,
        round_limit=2,
        has_new_entity=False,
        has_negative_evidence=False,
    ) == "skipped_saturation"
    assert marginal_stop_decision(
        rounds_below_threshold=2,
        threshold=0.2,
        round_limit=2,
        has_new_entity=True,
        has_negative_evidence=False,
    ) is None


def test_structured_output_has_one_bounded_repair_path() -> None:
    assert parse_structured_json('{"ok": true}').strategy == "strict_json"
    assert parse_structured_json("```json\n{\"ok\": true}\n```").strategy == "tool_schema"
    repaired = parse_structured_json("not json", repair_value='["fixed"]')
    assert repaired.strategy == "json_repair_once"
    assert repaired.value == ["fixed"]
    assert parse_structured_json("still not json").strategy == "failed"
