import json
from pathlib import Path

from app.repositories.auth import AuthRepository
from app.repositories.research import ResearchTaskRepository
from app.security.passwords import hash_password
from app.services.ai.information_value import (
    classify_information_utility,
    event_type_for_content,
)
from app.services.ai.intent_interpreter import (
    build_default_intent,
    execution_query_directions,
    interpret_model_text,
    model_request,
    repair_model_request,
)
from app.services.ai.research_quality import evaluate_query
from tests.alembic_utils import run_alembic_command


def create_research_task(database: Path) -> tuple[ResearchTaskRepository, str]:
    owner = AuthRepository(database).create_owner(
        username="intent-owner",
        password_hash=hash_password("password"),
    )
    repository = ResearchTaskRepository(database)
    task = repository.create(
        user_id=str(owner["id"]),
        objective="最近有哪些值得关注的个人 AI 工具？",
        platforms=["bili", "xhs"],
        crawl_limit=2,
        content_limit=100,
        duration_seconds=3_600,
        token_limit=50_000,
        cost_limit=None,
        cost_currency=None,
    )
    return repository, str(task["id"])


def test_default_intent_covers_exploration_and_multiple_intents(tmp_path: Path) -> None:
    discovery = build_default_intent("最近有哪些值得关注的个人 AI 工具？", ["bili", "xhs"])
    assert discovery.primary_intent == "discovery"
    assert "trend_tracking" in discovery.secondary_intents
    assert "product_opportunity" in discovery.secondary_intents
    assert "product_names" in discovery.unknowns_to_discover
    assert discovery.time_scope == {"type": "recent", "default_days": 30}
    assert discovery.confidence >= 0.75

    creator = build_default_intent("小红书美食博主常用哪些 AI 工具？", ["xhs"])
    assert creator.primary_intent == "creator_scan"
    assert "discovery" in creator.secondary_intents
    assert creator.target_audience is not None

    comparison = build_default_intent(
        "比较 Codex 与 WorkBuddy 在长期记忆、Skills 和自动化任务方面的差异。",
        ["bili"],
    )
    assert comparison.primary_intent == "comparison"
    assert {"Codex", "WorkBuddy"}.issubset(
        {str(item["name"]) for item in comparison.known_entities if isinstance(item, dict)}
    )
    assert len(execution_query_directions(comparison)) >= 3


def test_low_confidence_intent_has_one_clarification_question() -> None:
    intent = build_default_intent("帮我研究一下市场", ["bili"])
    assert intent.confidence < 0.45
    assert intent.clarification_question == "你主要想研究哪个产品或行业？"
    assert len(intent.ambiguities) == 1


def test_intent_interpreter_covers_time_scopes_intent_families_and_unknowns() -> None:
    year = build_default_intent("2026年个人知识管理有什么新趋势？", ["zhihu"])
    assert year.time_scope == {"type": "calendar_year", "year": 2026}
    assert year.primary_intent == "trend_tracking"
    assert "emerging_topics" in year.unknowns_to_discover

    days = build_default_intent("近14天有哪些新的AI软件？")
    assert days.time_scope == {"type": "recent", "default_days": 14}
    assert "tool_names" in days.unknowns_to_discover

    ongoing = build_default_intent("持续监控AI产品的用户问题")
    assert ongoing.time_scope == {"type": "ongoing", "default_days": 90}
    assert ongoing.primary_intent == "pain_point_research"

    all_families = build_default_intent(
        "比较 Notion 竞品、博主常用哪些工具，用户为什么抱怨不好用；"
        "趋势、选题、市场、产品机会和监控都要看。"
    )
    assert all_families.primary_intent == "comparison"
    assert {
        "pain_point_research",
        "competitor_scan",
        "creator_scan",
        "trend_tracking",
        "monitoring",
        "content_opportunity",
        "market_mapping",
        "product_opportunity",
        "discovery",
    }.issubset(set(all_families.secondary_intents))
    assert {
        "relevant_creators",
        "tools_used",
        "emerging_topics",
        "user_complaints",
        "competitor_names",
        "dimension_by_dimension_facts",
        "market_segments",
        "unserved_needs",
    }.issubset(set(all_families.unknowns_to_discover))
    assert all_families.evidence_requirements
    assert all_families.negative_evidence_requirements
    assert all_families.desired_output

    competitor_reason = build_default_intent("Notion在小红书上的竞品，用户为什么选择它们？")
    assert competitor_reason.primary_intent == "competitor_scan"
    assert {"pain_point_research", "comparison", "product_opportunity"}.issubset(
        set(competitor_reason.secondary_intents)
    )

    subject = build_default_intent("面向开发者的AI工具选题机会")
    assert subject.primary_intent == "content_opportunity"
    assert subject.target_audience is not None
    assert subject.assumptions
    assert subject.platform_preferences == ["bili", "xhs", "zhihu"]

    short = build_default_intent("研究")
    assert short.confidence == 0.4


def test_intent_interpreter_model_contract_and_bounded_requests() -> None:
    request = model_request("比较 Codex 和 WorkBuddy", ["bili"])
    assert request.temperature == 0.1
    assert request.max_tokens == 900
    assert request.metadata["runtime_step"] == "intent_interpretation"
    assert request.tool_choice == "none"

    repair = repair_model_request("比较 Codex 和 WorkBuddy", "{broken", ["bili"])
    assert repair.metadata["runtime_step"] == "intent_interpretation_repair"
    assert "Required JSON keys" in repair.messages[0].content

    valid = interpret_model_text(
        "比较 Codex 和 WorkBuddy",
        json.dumps(
            {
                "interpreted_goal": "比较两个工具",
                "primary_intent": "comparison",
                "secondary_intents": ["verification"],
                "confidence": 0.9,
                "unknowns_to_discover": ["tradeoffs"],
                "ignored_model_key": "must not override fallback shape",
                "original_request": "must remain the owner request",
                "target_audience": None,
            }
        ),
        ["bili"],
    )
    assert valid.intent_source == "model"
    assert valid.primary_intent == "comparison"
    assert valid.interpreted_goal == "比较两个工具"

    malformed = interpret_model_text("比较 Codex 和 WorkBuddy", "not json", ["bili"])
    assert malformed.intent_source == "fallback_default"
    invalid_contract = interpret_model_text(
        "比较 Codex 和 WorkBuddy",
        json.dumps({"primary_intent": "not_a_stable_intent", "confidence": "bad"}),
        ["bili"],
    )
    assert invalid_contract.intent_source == "fallback_default"


def test_execution_directions_cover_discovery_roles() -> None:
    intent = build_default_intent(
        "Notion竞品有哪些，博主常用什么工具，用户抱怨哪些问题，最近趋势和内容机会？",
        ["xhs", "bili"],
    )
    roles = {item["query_role"] for item in execution_query_directions(intent)}
    assert {
        "competitor_scan",
        "creator_scan",
        "seed_discovery",
        "pain_point_probe",
        "counterevidence",
        "trend_probe",
    }.issubset(roles)

    monitoring = build_default_intent("监控AI工具的变化")
    assert execution_query_directions(monitoring)


def test_user_goal_is_not_rejected_by_execution_query_gate() -> None:
    user_goal = evaluate_query(
        "最近有哪些值得关注的个人 AI 工具？",
        generation_reason="原始用户目标",
        source_type="user_goal",
        historical_queries=[],
        record_type="user_goal",
        query_role="seed_discovery",
    )
    assert user_goal.accepted is True

    unbound_seed = evaluate_query(
        "个人 AI 工具 近期真实使用体验",
        generation_reason="Intent Contract 转换",
        source_type="intent_plan",
        historical_queries=[],
        record_type="execution_query",
        query_role="seed_discovery",
        intent_bound=False,
    )
    assert unbound_seed.accepted is False
    assert "Intent Contract" in (unbound_seed.rejection_reason or "")

    bound_seed = evaluate_query(
        "个人 AI 工具 近期真实使用体验",
        generation_reason="Intent Contract 转换",
        source_type="intent_plan",
        historical_queries=[],
        record_type="execution_query",
        query_role="seed_discovery",
        intent_bound=True,
    )
    assert bound_seed.accepted is True


def test_information_utility_is_multi_label_and_preserves_counterevidence() -> None:
    intent = build_default_intent("哪些 AI 工具值得关注，哪些不好用？", ["bili"])
    assessments = classify_information_utility(
        {
            "title": "NewTool 发布新版本，但用户反馈不好用",
            "description": "有人记录了真实使用场景、限制和替代方案。",
        },
        intent=intent,
        extracted_entities=["NewTool"],
    )
    utility_types = {item.utility_type for item in assessments}
    assert "discovery_seed" in utility_types
    assert "counterevidence" in utility_types
    assert "event_signal" in utility_types
    assert "memory_update" in utility_types


def test_information_utility_handles_duplicate_noise_action_and_memory_paths() -> None:
    opportunity_intent = build_default_intent("哪些AI工具存在需求和产品机会？")
    duplicate = classify_information_utility(
        {"title": "转载"},
        intent=opportunity_intent,
        is_repost=True,
    )
    assert [item.utility_type for item in duplicate] == ["duplicate"]

    empty = classify_information_utility({}, intent=opportunity_intent)
    assert [item.utility_type for item in empty] == ["noise"]

    marketing = classify_information_utility(
        {"title": "限时优惠，购买课程扫码领取"},
        intent=opportunity_intent,
    )
    assert [item.utility_type for item in marketing] == ["noise"]

    action = classify_information_utility(
        {"title": "用户希望有更好的AI工具替代方案"},
        intent=opportunity_intent,
    )
    action_types = {item.utility_type for item in action}
    assert "action_trigger" in action_types

    known = classify_information_utility(
        {"title": "ExistingTool 的 AI工具真实使用体验和更新"},
        intent=opportunity_intent,
        extracted_entities=["ExistingTool"],
        known_memory_keys=["ExistingTool"],
    )
    known_types = {item.utility_type for item in known}
    assert "discovery_seed" not in known_types
    assert "memory_update" in known_types

    adopted = classify_information_utility(
        {"title": "NewTool 发布新版本，真实使用体验"},
        intent=opportunity_intent,
        extracted_entities=["NewTool"],
        adopted=True,
    )
    assert "core_evidence" in {item.utility_type for item in adopted}

    assert event_type_for_content({"title": "产品更新新版本"}) == "new_version"
    assert event_type_for_content({"title": "服务涨价调整定价"}) == "new_pricing"
    assert event_type_for_content({"title": "系统故障崩溃"}) == "failure"
    assert event_type_for_content({"title": "公司合作联名"}) == "partnership"
    assert event_type_for_content({"title": "产品上线发布"}) == "launch"
    assert event_type_for_content({"title": "平静的背景介绍"}) is None


def test_intent_and_8d0_artifacts_are_durable(tmp_path: Path) -> None:
    database = tmp_path / "mediaops.db"
    run_alembic_command(database, "upgrade", "head")
    repository, task_id = create_research_task(database)
    contract = build_default_intent("最近有哪些值得关注的个人 AI 工具？", ["bili", "xhs"])
    saved = repository.save_intent(
        task_id,
        contract.model_dump(mode="json"),
        change_reason="test_initial_intent",
    )
    assert saved["primary_intent"] == "discovery"
    assert saved["version"] == 1

    revised = dict(contract.model_dump(mode="json"))
    revised["interpreted_goal"] = "优先发现近期真实使用的个人 AI 工具，并记录限制。"
    revised["intent_source"] = "owner_revised"
    revised_saved = repository.save_intent(
        task_id,
        revised,
        change_reason="test_owner_revision",
    )
    assert revised_saved["version"] == 2

    current = repository.get_intent(task_id)
    assert current["version"] == 2
    detail = repository.get_for_runtime(task_id, detail=True)
    assert detail is not None
    assert len(detail["intent_versions"]) == 2
    assert len(detail["unknowns"]) >= 1

    entity = repository.save_entity_candidate(
        task_id=task_id,
        entity_type="product",
        normalized_name="NewTool",
        source_content_id=None,
        relevance_to_intent=0.9,
        novelty=1.0,
        confidence=0.8,
        suggested_next_action="绑定来源内容进行验证",
    )
    event = repository.save_event_candidate(
        task_id=task_id,
        event_type="new_version",
        title="NewTool 新版本",
        summary="候选事件",
        source_content_id=None,
        confidence=0.7,
    )
    memory = repository.save_memory_item(
        task_id=task_id,
        memory_type="observed_entity",
        memory_key="NewTool",
        value={"source": "test"},
        confidence=0.7,
    )
    review = repository.save_alignment_review(
        task_id=task_id,
        alignment_score=0.6,
        covered_requirements=["unknown_entities_or_topics"],
        missing_requirements=["independent_evidence"],
        scope_drift={"detected": False},
        recommended_next_step="继续验证",
        review_status="partial_completion",
    )
    assert entity["status"] == "candidate_discovery"
    assert event["status"] == "candidate"
    assert memory["is_current"] is True
    assert review["review_status"] == "partial_completion"
