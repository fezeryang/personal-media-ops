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


def _task(database: Path, owner_id: str) -> dict[str, object]:
    repository = ResearchTaskRepository(database)
    request = ResearchTaskCreate(objective="探索值得关注的个人 AI 工具", platforms=["bili"])
    task = repository.create(
        user_id=owner_id,
        objective=request.objective,
        platforms=["bili"],
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
        build_default_intent("探索值得关注的个人 AI 工具", ["bili"]).model_dump(mode="json"),
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
    feedback_response = client.post(
        f"/api/research/discoveries/{candidate_id}/feedback",
        json={"feedback_type": "irrelevant", "reason": "与当前目标无关"},
    )
    assert feedback_response.status_code == 200, feedback_response.text
    feedback_payload = feedback_response.json()
    assert feedback_payload["state"] == "ignored"
    feedback_id = feedback_payload["feedback"][0]["id"]
    assert feedback_payload["score_explanation"]["feedback"]

    undo_response = client.post(
        f"/api/research/discoveries/{candidate_id}/feedback",
        json={"undo_feedback_id": feedback_id},
    )
    assert undo_response.status_code == 200, undo_response.text
    assert undo_response.json()["feedback"][0]["undone_at"]
    assert discovery.list_preferences(owner_id=owner_id) == []

    continue_response = client.post(
        f"/api/research/discoveries/{candidate_id}/continue",
        json={"request": "继续验证这个候选的真实使用限制"},
    )
    assert continue_response.status_code == 200, continue_response.text
    follow_up = continue_response.json()
    assert follow_up["id"] != task["id"]
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
