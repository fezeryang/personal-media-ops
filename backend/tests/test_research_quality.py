from app.services.ai.research_quality import (
    classify_query,
    evaluate_query,
    expected_value_score,
    noise_risk_score,
    normalize_query,
    novelty_score,
    parse_relevance_batch,
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
