from __future__ import annotations

import secrets
import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.research import ResearchTaskCreate, ResearchTaskDetail
from app.repositories.auth import AuthRepository
from app.repositories.discovery import DiscoveryRepository
from app.repositories.research import ResearchTaskRepository
from app.security.passwords import hash_password
from app.services.ai.discovery import DiscoveryEngine
from app.services.ai.intent_interpreter import build_default_intent
from tests.alembic_utils import run_alembic_command


def _content(database: Path, *, content_id: str, title: str, platform: str, description: str) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO library_contents (
                id, platform, source_content_id, content_type, title,
                description, source_url, author_source_id, author_name,
                published_at, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, 'video', ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
            """,
            (
                content_id,
                platform,
                f"source-{content_id}",
                title,
                description,
                f"https://example.test/{content_id}",
                f"author-{content_id}",
                f"作者-{content_id}",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
            ),
        )


def _task(
    database: Path,
    owner_id: str,
    *,
    platforms: list[str] | None = None,
    objective: str = "探索值得关注的个人 AI 工具",
) -> dict[str, object]:
    repository = ResearchTaskRepository(database)
    request = ResearchTaskCreate(
        objective=objective,
        platforms=platforms or ["bili"],
    )
    task = repository.create(
        user_id=owner_id,
        objective=objective,
        platforms=list(request.platforms or ["bili"]),
        crawl_limit=request.budget.crawl_limit,
        content_limit=request.budget.content_limit,
        duration_seconds=request.budget.duration_seconds,
        token_limit=request.budget.token_limit,
        cost_limit=request.budget.cost_limit,
        cost_currency=request.budget.cost_currency,
        coverage=request.coverage.model_dump(),
        max_input_tokens=request.budget.max_input_tokens,
        max_output_tokens=request.budget.max_output_tokens,
        max_model_calls=request.budget.max_model_calls,
        route_policy=request.budget.route_policy,
        max_total_tokens=request.budget.max_total_tokens,
        max_crawl_tasks=request.budget.max_crawl_tasks,
        max_new_contents=request.budget.max_new_contents,
        max_runtime_seconds=request.budget.max_runtime_seconds,
        max_payg_amount=request.budget.max_payg_amount,
        budget_currency=request.budget.currency,
    )
    repository.save_intent(
        str(task["id"]),
        build_default_intent(objective, list(request.platforms or ["bili"])).model_dump(mode="json"),
    )
    return task


def test_bounded_discovery_generates_explainable_source_bound_candidates(
    test_settings,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="discovery-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    task = _task(test_settings.database_path, str(owner["id"]))
    _content(
        test_settings.database_path,
        content_id="content-discovery-1",
        title="Local AI workspace review",
        platform="bili",
        description="真实使用体验与个人 AI 工作台工具分析。",
    )
    research = ResearchTaskRepository(test_settings.database_path)
    entity = research.save_entity_candidate(
        task_id=str(task["id"]),
        entity_type="product",
        normalized_name="Local AI Workspace",
        source_content_id="content-discovery-1",
        relevance_to_intent=0.92,
        novelty=0.95,
        confidence=0.88,
        suggested_next_action="寻找跨平台独立用户反馈",
    )
    research.record_information_utility(
        task_id=str(task["id"]),
        content_id="content-discovery-1",
        utility_type="discovery_seed",
        rationale="来源内容提供了新的产品实体和使用场景。",
        confidence=0.9,
    )
    result = DiscoveryEngine(
        discovery=DiscoveryRepository(test_settings.database_path),
        research=research,
    ).generate_for_task(str(task["id"]))

    assert result["run"]["depth"] == 1
    assert result["run"]["status"] == "completed"
    candidates = result["candidates"]
    assert isinstance(candidates, list)
    assert candidates[0]["candidate_type"] == "entity"
    assert candidates[0]["source_seed_id"]
    assert candidates[0]["final_score"] > 0.5
    assert candidates[0]["score_explanation"]["why_relevant"]
    detail = DiscoveryRepository(test_settings.database_path).get_candidate(
        owner_id=str(owner["id"]), candidate_id=str(candidates[0]["id"])
    )
    assert detail is not None
    assert detail["sources"][0]["content_id"] == "content-discovery-1"
    assert str(entity["id"])


def test_discovery_feedback_is_reversible_and_spaces_are_owner_scoped(
    client: TestClient,
    owner_id: str,
) -> None:
    task = _task(client.app.state.settings.database_path, owner_id)
    discovery = client.app.state.discovery_repository
    run = discovery.create_run(task_id=str(task["id"]))
    candidate = discovery.upsert_candidate(
        owner_id=owner_id,
        task_id=str(task["id"]),
        run_id=str(run["id"]),
        candidate_type="entity",
        title="Feedback candidate",
        summary="需要用户判断的候选。",
        normalized_key="feedback candidate",
        parent_candidate_id=None,
        source_seed_id=None,
        source_content_id=None,
        source_platform="bili",
        scores={
            "relevance_score": 0.7,
            "novelty_score": 0.8,
            "evidence_strength_score": 0.4,
            "source_independence_score": 0.5,
            "cross_platform_score": 0.5,
            "counterevidence_score": 0.2,
            "actionability_score": 0.6,
            "feedback_score": 0.5,
            "noise_risk_score": 0.1,
            "marketing_risk_score": 0.1,
            "saturation_score": 0.1,
            "resource_cost_score": 0.2,
            "final_score": 0.58,
        },
        score_explanation={"recommendation": "继续研究"},
        counts={"content_count": 0, "independent_source_count": 0, "platform_count": 0, "suspected_repost_count": 0},
        depth=1,
        state="queued",
        suggested_next_action="继续研究",
        experimental_status=None,
    )
    candidate_id = str(candidate["id"])
    invalid_scope_response = client.post(
        f"/api/research/discoveries/{candidate_id}/feedback",
        json={"feedback_type": "follow", "scope": "platform"},
    )
    assert invalid_scope_response.status_code == 409
    feedback_response = client.post(
        f"/api/research/discoveries/{candidate_id}/feedback",
        json={"feedback_type": "irrelevant", "reason": "与当前目标无关"},
    )
    assert feedback_response.status_code == 200, feedback_response.text
    feedback_payload = feedback_response.json()
    assert feedback_payload["state"] == "ignored"
    feedback_id = feedback_payload["feedback"][0]["id"]
    assert feedback_payload["score_explanation"]["feedback"]
    assert feedback_payload["final_score"] < candidate["final_score"]

    undo_response = client.post(
        f"/api/research/discoveries/{candidate_id}/feedback",
        json={"undo_feedback_id": feedback_id},
    )
    assert undo_response.status_code == 200, undo_response.text
    undo_payload = undo_response.json()
    assert undo_payload["feedback"][0]["undone_at"]
    assert undo_payload["final_score"] > feedback_payload["final_score"]
    assert discovery.list_preferences(owner_id=owner_id) == []

    continue_response = client.post(
        f"/api/research/discoveries/{candidate_id}/continue",
        json={"request": "继续验证这个候选的真实使用限制"},
    )
    assert continue_response.status_code == 200, continue_response.text
    follow_up = continue_response.json()
    assert follow_up["id"] != task["id"]
    assert follow_up["context"]["discovery_parent_candidate_id"] == candidate_id
    assert follow_up["context"]["discovery_source_task_id"] == task["id"]
    assert follow_up["context"]["discovery_source_candidate_type"] == "entity"
    assert follow_up["context"]["discovery_source_content_ids"] == []
    assert client.get(f"/api/research/tasks/{follow_up['id']}").status_code == 200
    original_detail = client.get(f"/api/research/tasks/{task['id']}")
    assert original_detail.status_code == 200, original_detail.text
    validated_detail = ResearchTaskDetail.model_validate(original_detail.json())
    assert validated_detail.discovery_candidates

    space_response = client.post(
        "/api/research/spaces",
        json={"name": "AI 工具研究空间", "description": "用于验证候选"},
    )
    assert space_response.status_code == 201, space_response.text
    space_id = space_response.json()["id"]
    add_response = client.post(
        f"/api/research/discoveries/{candidate_id}/add-to-space",
        json={"space_id": space_id},
    )
    assert add_response.status_code == 200, add_response.text
    detail_response = client.get(f"/api/research/spaces/{space_id}")
    assert detail_response.status_code == 200, detail_response.text
    assert detail_response.json()["items"][0]["item_type"] == "discovery_candidate"
    assert any(
        rule["scope"] == "research_space" and rule["scope_key"] == space_id
        for rule in discovery.list_preferences(owner_id=owner_id)
    )


def test_candidate_feedback_does_not_leak_to_unrelated_candidates(
    test_settings,
) -> None:
    """A candidate action must not silently mute every future candidate."""

    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="feedback-scope-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    owner_id = str(owner["id"])
    task = _task(test_settings.database_path, owner_id)
    discovery = DiscoveryRepository(test_settings.database_path)
    run = discovery.create_run(task_id=str(task["id"]))
    score_values = {
        "relevance_score": 0.7,
        "novelty_score": 0.8,
        "evidence_strength_score": 0.5,
        "source_independence_score": 0.5,
        "cross_platform_score": 0.5,
        "counterevidence_score": 0.2,
        "actionability_score": 0.6,
        "feedback_score": 0.5,
        "noise_risk_score": 0.1,
        "marketing_risk_score": 0.1,
        "saturation_score": 0.1,
        "resource_cost_score": 0.2,
        "final_score": 0.58,
    }

    def create_candidate(normalized_key: str) -> dict[str, object]:
        return discovery.upsert_candidate(
            owner_id=owner_id,
            task_id=str(task["id"]),
            run_id=str(run["id"]),
            candidate_type="entity",
            title=normalized_key.title(),
            summary="需要用户判断的候选。",
            normalized_key=normalized_key,
            parent_candidate_id=None,
            source_seed_id=None,
            source_content_id=None,
            source_platform="bili",
            scores=score_values,
            score_explanation={"recommendation": "继续研究"},
            counts={
                "content_count": 0,
                "independent_source_count": 0,
                "platform_count": 0,
                "suspected_repost_count": 0,
            },
            depth=1,
            state="queued",
            suggested_next_action="继续研究",
            experimental_status=None,
        )

    first = create_candidate("first candidate")
    second = create_candidate("second candidate")
    discovery.record_feedback(
        owner_id=owner_id,
        candidate_id=str(first["id"]),
        feedback_type="irrelevant",
        scope="global",
        scope_key=None,
        weight=1,
        reason="只针对这一条候选",
    )

    first_adjustment, _ = discovery.active_feedback_adjustment(
        owner_id=owner_id,
        candidate_type="entity",
        platform="bili",
        topic_key=str(first["normalized_key"]),
        intent_id=None,
        candidate_id=str(first["id"]),
    )
    second_adjustment, second_rules = discovery.active_feedback_adjustment(
        owner_id=owner_id,
        candidate_type="entity",
        platform="bili",
        topic_key=str(second["normalized_key"]),
        intent_id=None,
        candidate_id=str(second["id"]),
    )

    assert first_adjustment < 0
    assert second_adjustment == 0
    assert second_rules == []


def test_discovery_collects_favorite_accepted_space_and_confirmed_event_seeds(
    test_settings,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="discovery-seed-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    owner_id = str(owner["id"])
    task = _task(test_settings.database_path, owner_id)
    previous_task = _task(
        test_settings.database_path,
        owner_id,
        objective="验证过去的研究发现",
    )
    _content(
        test_settings.database_path,
        content_id="favorite-seed-content",
        title="收藏的个人 AI 工作台体验",
        platform="bili",
        description="收藏内容记录了真实使用场景和后续需求。",
    )
    _content(
        test_settings.database_path,
        content_id="accepted-seed-content",
        title="已采纳的 AI 工具候选",
        platform="bili",
        description="已采纳候选的来源证据。",
    )
    _content(
        test_settings.database_path,
        content_id="event-seed-content",
        title="个人 AI 工具发布事件",
        platform="bili",
        description="记录一次真实发布变化。",
    )
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE library_contents SET is_favorite = 1 WHERE id = ?",
            ("favorite-seed-content",),
        )

    research = ResearchTaskRepository(test_settings.database_path)
    entity = research.save_entity_candidate(
        task_id=str(previous_task["id"]),
        entity_type="product",
        normalized_name="Saved AI Workspace",
        source_content_id="favorite-seed-content",
        relevance_to_intent=0.8,
        novelty=0.8,
        confidence=0.9,
        suggested_next_action="继续验证",
    )
    event = research.save_event_candidate(
        task_id=str(previous_task["id"]),
        event_type="release",
        title="个人 AI 工具发布事件",
        summary="一次可验证的产品变化。",
        source_content_id="event-seed-content",
        confidence=0.9,
    )
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE research_event_candidates SET status = 'accepted' WHERE id = ?",
            (event["id"],),
        )

    discovery = DiscoveryRepository(test_settings.database_path)
    space = discovery.create_space(
        owner_id=owner_id,
        name="种子聚焦空间",
        description="用于验证空间焦点种子",
    )
    discovery.add_space_item(
        owner_id=owner_id,
        space_id=str(space["id"]),
        item_type="entity",
        item_id=str(entity["id"]),
        position=0,
        note=None,
    )
    run = discovery.create_run(task_id=str(previous_task["id"]))
    accepted = discovery.upsert_candidate(
        owner_id=owner_id,
        task_id=str(previous_task["id"]),
        run_id=str(run["id"]),
        candidate_type="entity",
        title="Accepted AI Workspace",
        summary="已采纳的跨任务候选。",
        normalized_key="accepted ai workspace",
        parent_candidate_id=None,
        source_seed_id=None,
        source_content_id="accepted-seed-content",
        source_platform="bili",
        scores={
            "relevance_score": 0.8,
            "novelty_score": 0.8,
            "evidence_strength_score": 0.5,
            "source_independence_score": 0.5,
            "cross_platform_score": 0.5,
            "counterevidence_score": 0.2,
            "actionability_score": 0.7,
            "feedback_score": 0.5,
            "noise_risk_score": 0.1,
            "marketing_risk_score": 0.1,
            "saturation_score": 0.1,
            "resource_cost_score": 0.2,
            "final_score": 0.7,
        },
        score_explanation={"recommendation": "继续研究"},
        counts={
            "content_count": 1,
            "independent_source_count": 1,
            "platform_count": 1,
            "suspected_repost_count": 0,
        },
        depth=1,
        state="accepted",
        suggested_next_action="继续研究",
        experimental_status=None,
    )
    assert accepted["state"] == "accepted"

    result = DiscoveryEngine(
        discovery=discovery,
        research=research,
        production_verified_platforms=("bili",),
    ).generate_for_task(str(task["id"]))

    seed_types = {str(seed["seed_type"]) for seed in result["seeds"]}
    assert {"favorite", "accepted_candidate", "space_entity", "confirmed_event"} <= seed_types
    candidate_types = {str(candidate["candidate_type"]) for candidate in result["candidates"]}
    assert "event" in candidate_types
    event_candidate = next(
        candidate for candidate in result["candidates"] if candidate["candidate_type"] == "event"
    )
    assert event_candidate["score_explanation"]["event_aggregation"]["platforms"] == ["bili"]


def test_discovery_does_not_promote_title_only_content_to_a_candidate(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="discovery-body-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    task = _task(test_settings.database_path, str(owner["id"]))
    _content(
        test_settings.database_path,
        content_id="title-only-content",
        title="只有标题的记录",
        platform="bili",
        description="",
    )
    research = ResearchTaskRepository(test_settings.database_path)
    research.record_information_utility(
        task_id=str(task["id"]),
        content_id="title-only-content",
        utility_type="discovery_seed",
        rationale="验证正文质量门禁",
        confidence=0.8,
    )

    result = DiscoveryEngine(
        discovery=DiscoveryRepository(test_settings.database_path),
        research=research,
    ).generate_for_task(str(task["id"]))

    assert result["run"]["status"] == "partial"
    assert result["candidates"] == []


def test_related_content_empty_platform_allowlist_is_fail_closed(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    _content(
        test_settings.database_path,
        content_id="platform-gate-content",
        title="平台门禁内容",
        platform="bili",
        description="有正文的门禁测试记录。",
    )

    repository = DiscoveryRepository(test_settings.database_path)

    assert repository.find_related_contents("平台门禁", platforms=[]) == []


def test_discovery_generates_typed_opportunity_candidates_and_respects_platform_gate(
    test_settings,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="discovery-type-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    owner_id = str(owner["id"])
    task = _task(test_settings.database_path, owner_id)
    _content(
        test_settings.database_path,
        content_id="typed-bili-content",
        title="个人 AI 工作台真实使用反馈",
        platform="bili",
        description="用户需要更稳定的工作流，但现在难用、失败且有明显问题；希望找到更好的工具。",
    )
    _content(
        test_settings.database_path,
        content_id="typed-xhs-content",
        title="个人 AI 工作台真实使用反馈",
        platform="xhs",
        description="用户需要更稳定的工作流，但现在难用、失败且有明显问题；希望找到更好的工具。",
    )
    research = ResearchTaskRepository(test_settings.database_path)
    research.save_entity_candidate(
        task_id=str(task["id"]),
        entity_type="product",
        normalized_name="个人 AI 工作台",
        source_content_id="typed-bili-content",
        relevance_to_intent=0.95,
        novelty=0.9,
        confidence=0.9,
        suggested_next_action="寻找独立用户反馈",
    )
    research.record_information_utility(
        task_id=str(task["id"]),
        content_id="typed-bili-content",
        utility_type="discovery_seed",
        rationale="内容提供产品、痛点和需求的来源证据。",
        confidence=0.9,
    )

    result = DiscoveryEngine(
        discovery=DiscoveryRepository(test_settings.database_path),
        research=research,
        production_verified_platforms=("bili", "xhs"),
    ).generate_for_task(str(task["id"]))

    candidate_types = {str(item["candidate_type"]) for item in result["candidates"]}
    assert {
        "entity",
        "topic",
        "query",
        "pain_point",
        "need",
        "product_opportunity_signal",
        "content_opportunity_signal",
    } <= candidate_types
    for item in result["candidates"]:
        detail = DiscoveryRepository(test_settings.database_path).get_candidate(
            owner_id=owner_id,
            candidate_id=str(item["id"]),
        )
        assert detail is not None
        assert {str(source["platform"]) for source in detail["sources"]} <= {"bili"}


def test_discovery_event_explanation_contains_lightweight_aggregation(
    test_settings,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="discovery-event-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    owner_id = str(owner["id"])
    task = _task(
        test_settings.database_path,
        owner_id,
        platforms=["bili", "xhs"],
        objective="验证一个产品发布事件的多平台变化",
    )
    _content(
        test_settings.database_path,
        content_id="event-old",
        title="AI 工作台发布新版本",
        platform="bili",
        description="用户反馈功能提升，体验更好。",
    )
    _content(
        test_settings.database_path,
        content_id="event-new",
        title="AI 工作台发布新版本",
        platform="xhs",
        description="用户反馈功能失败，仍有问题。",
    )
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE library_contents SET published_at = ? WHERE id = ?",
            ("2026-07-01T00:00:00Z", "event-old"),
        )
        connection.execute(
            "UPDATE library_contents SET published_at = ? WHERE id = ?",
            ("2026-08-02T00:00:00Z", "event-new"),
        )
    research = ResearchTaskRepository(test_settings.database_path)
    event = research.save_event_candidate(
        task_id=str(task["id"]),
        event_type="release",
        title="AI 工作台发布新版本",
        summary="产品发布事件",
        source_content_id="event-old",
        confidence=0.9,
    )
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE research_event_candidates SET status = 'accepted' WHERE id = ?",
            (event["id"],),
        )

    result = DiscoveryEngine(
        discovery=DiscoveryRepository(test_settings.database_path),
        research=research,
        production_verified_platforms=("bili", "xhs"),
    ).generate_for_task(str(task["id"]))
    event_candidate = next(
        item for item in result["candidates"] if item["candidate_type"] == "event"
    )
    explanation = event_candidate["score_explanation"]
    aggregation = explanation["event_aggregation"]
    assert aggregation["first_seen"] == "2026-07-01T00:00:00Z"
    assert aggregation["latest_seen"] == "2026-08-02T00:00:00Z"
    assert set(aggregation["platforms"]) == {"bili", "xhs"}
    assert aggregation["positive_evidence_count"] >= 1
    assert aggregation["negative_evidence_count"] >= 1


def test_discovery_marks_cross_platform_near_duplicate_as_repost(
    test_settings,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="discovery-repost-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    owner_id = str(owner["id"])
    task = _task(
        test_settings.database_path,
        owner_id,
        platforms=["bili", "xhs"],
        objective="验证跨平台转载识别",
    )
    _content(
        test_settings.database_path,
        content_id="repost-source",
        title="AI 工作台真实使用体验",
        platform="bili",
        description="用户介绍了产品的核心工作流、实际使用场景和限制问题。",
    )
    _content(
        test_settings.database_path,
        content_id="repost-copy",
        title="AI 工作台真实使用体验（复盘）",
        platform="xhs",
        description="用户介绍了产品的核心工作流、实际使用场景和限制问题，补充了跨平台体验。",
    )
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE library_contents SET author_name = ? WHERE id IN (?, ?)",
            ("同一作者", "repost-source", "repost-copy"),
        )

    research = ResearchTaskRepository(test_settings.database_path)
    research.save_entity_candidate(
        task_id=str(task["id"]),
        entity_type="product",
        normalized_name="AI 工作台",
        source_content_id="repost-source",
        relevance_to_intent=0.9,
        novelty=0.8,
        confidence=0.9,
        suggested_next_action="验证独立用户来源",
    )
    research.record_information_utility(
        task_id=str(task["id"]),
        content_id="repost-source",
        utility_type="discovery_seed",
        rationale="来源内容提供了产品体验证据。",
        confidence=0.9,
    )

    result = DiscoveryEngine(
        discovery=DiscoveryRepository(test_settings.database_path),
        research=research,
        production_verified_platforms=("bili", "xhs"),
    ).generate_for_task(str(task["id"]))
    candidate = next(item for item in result["candidates"] if item["candidate_type"] == "entity")
    detail = DiscoveryRepository(test_settings.database_path).get_candidate(
        owner_id=owner_id,
        candidate_id=str(candidate["id"]),
    )

    assert detail is not None
    sources = {str(item["content_id"]): item for item in detail["sources"]}
    assert set(sources) == {"repost-source", "repost-copy"}
    assert sources["repost-copy"]["is_repost"] is True
    assert sources["repost-copy"]["similarity_score"] is not None
    assert sources["repost-copy"]["similarity_score"] >= 0.8
    assert sources["repost-source"]["independent_group"] == sources["repost-copy"]["independent_group"]
    assert detail["independent_source_count"] == 1
    assert detail["suspected_repost_count"] == 1
    repost_detection = detail["score_explanation"]["repost_detection"]
    assert repost_detection["suspected_repost_count"] == 1
    assert repost_detection["reasons"]


def test_phase_8d_acceptance_objectives_produce_bounded_product_and_pain_discoveries(
    test_settings,
) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    owner = AuthRepository(test_settings.database_path).create_owner(
        username="phase-8d-acceptance-owner",
        password_hash=hash_password(secrets.token_urlsafe(32)),
    )
    owner_id = str(owner["id"])
    research = ResearchTaskRepository(test_settings.database_path)
    discovery = DiscoveryRepository(test_settings.database_path)

    product_task = _task(
        test_settings.database_path,
        owner_id,
        platforms=["bili", "zhihu"],
        objective="最近有哪些值得关注的个人 AI 工具？",
    )
    products = ["LocalFlow", "NotePilot", "TaskWeave"]
    for index, product in enumerate(products):
        primary_id = f"acceptance-product-primary-{index}"
        secondary_id = f"acceptance-product-secondary-{index}"
        _content(
            test_settings.database_path,
            content_id=primary_id,
            title=f"{product} AI 工具真实体验",
            platform="bili",
            description="用户记录了真实使用场景、工作流收益和当前限制，内容来自独立体验者。",
        )
        _content(
            test_settings.database_path,
            content_id=secondary_id,
            title=f"{product} 使用分析与适用人群",
            platform="zhihu",
            description="另一位用户分析了产品定位、实际工作流和适用边界，并提出了不同的使用反馈。",
        )
        entity = research.save_entity_candidate(
            task_id=str(product_task["id"]),
            entity_type="product",
            normalized_name=product,
            source_content_id=primary_id,
            relevance_to_intent=0.92,
            novelty=0.86,
            confidence=0.9,
            suggested_next_action="继续验证真实用户反馈",
        )
        assert entity["source_content_id"] == primary_id
        research.record_information_utility(
            task_id=str(product_task["id"]),
            content_id=primary_id,
            utility_type="discovery_seed",
            rationale="来源记录了真实产品体验和使用场景。",
            confidence=0.9,
        )

    product_result = DiscoveryEngine(
        discovery=discovery,
        research=research,
        production_verified_platforms=("bili", "zhihu"),
    ).generate_for_task(str(product_task["id"]))
    product_candidates = [
        item
        for item in product_result["candidates"]
        if item["candidate_type"] == "entity" and item["final_score"] >= 0.55
    ]
    assert len(product_candidates) >= 3
    assert all(item["depth"] == 1 for item in product_candidates)
    product_details = [
        discovery.get_candidate(owner_id=owner_id, candidate_id=str(item["id"]))
        for item in product_candidates[:3]
    ]
    assert all(detail is not None for detail in product_details)
    assert all(detail["score_explanation"]["why_relevant"] for detail in product_details if detail)
    assert all(detail["sources"] for detail in product_details if detail)
    assert any(
        detail["platform_count"] >= 2 and detail["independent_source_count"] >= 2
        for detail in product_details
        if detail
    )

    pain_task = _task(
        test_settings.database_path,
        owner_id,
        platforms=["xhs", "zhihu"],
        objective="小红书和知乎用户在抱怨哪些 AI 工具不好用？",
    )
    _content(
        test_settings.database_path,
        content_id="acceptance-pain-xhs",
        title="AI 工具不好用的用户吐槽",
        platform="xhs",
        description="小红书账号当前不可作为生产验证来源；这条内容不应进入本次 Discovery。",
    )
    _content(
        test_settings.database_path,
        content_id="acceptance-pain-zhihu",
        title="AI 工具真实踩坑记录",
        platform="zhihu",
        description="用户直接描述工具不好用、经常失败、结果不稳定和工作流问题，属于负向体验证据。",
    )
    pain_entity = research.save_entity_candidate(
        task_id=str(pain_task["id"]),
        entity_type="product",
        normalized_name="Painful AI Tool",
        source_content_id="acceptance-pain-zhihu",
        relevance_to_intent=0.94,
        novelty=0.8,
        confidence=0.88,
        suggested_next_action="寻找其他作者的直接负向证据",
    )
    assert pain_entity["source_content_id"] == "acceptance-pain-zhihu"
    research.record_information_utility(
        task_id=str(pain_task["id"]),
        content_id="acceptance-pain-zhihu",
        utility_type="discovery_seed",
        rationale="来源包含直接负向体验和可复核的使用限制。",
        confidence=0.88,
    )

    pain_result = DiscoveryEngine(
        discovery=discovery,
        research=research,
        production_verified_platforms=("zhihu",),
    ).generate_for_task(str(pain_task["id"]))
    pain_candidates = [
        item for item in pain_result["candidates"] if item["candidate_type"] == "pain_point"
    ]
    assert pain_candidates
    assert pain_result["run"]["depth"] == 1
    for item in pain_candidates:
        detail = discovery.get_candidate(owner_id=owner_id, candidate_id=str(item["id"]))
        assert detail is not None
        assert {str(source["platform"]) for source in detail["sources"]} == {"zhihu"}
        assert "不好用" in detail["summary"] or "负向" in detail["summary"]
