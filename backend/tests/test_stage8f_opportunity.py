from __future__ import annotations

import sqlite3
from pathlib import Path

from fastapi.testclient import TestClient

from app.models.research import ResearchTaskCreate
from app.repositories.auth import AuthRepository
from app.repositories.research import ResearchTaskRepository
from app.security.passwords import hash_password
from app.services.ai.intent_interpreter import build_default_intent
from tests.alembic_utils import run_alembic_command


def _content(database: Path, *, content_id: str, platform: str, author: str, title: str, description: str) -> None:
    with sqlite3.connect(database) as connection:
        connection.execute(
            """
            INSERT INTO library_contents (
                id, platform, source_content_id, content_type, title,
                description, source_url, author_source_id, author_name,
                published_at, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            ) VALUES (?, ?, ?, 'article', ?, ?, ?, ?, ?, ?, ?, ?, '{}', ?, ?)
            """,
            (
                content_id,
                platform,
                f"source-{content_id}",
                title,
                description,
                f"https://example.test/{content_id}",
                f"author-source-{content_id}",
                author,
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
                "2026-08-01T00:00:00Z",
            ),
        )


def _task(database: Path, owner_id: str, objective: str = "从真实用户反馈中验证 AI 工具机会") -> dict[str, object]:
    repository = ResearchTaskRepository(database)
    request = ResearchTaskCreate(objective=objective, platforms=["bili", "zhihu"])
    task = repository.create(
        user_id=owner_id,
        objective=objective,
        platforms=list(request.platforms or []),
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
        build_default_intent(objective, list(request.platforms or [])).model_dump(mode="json"),
    )
    return task


def _finding(repository: ResearchTaskRepository, task_id: str, content_id: str, *, contradictory: bool = False) -> dict[str, object]:
    return repository.save_finding(
        task_id=task_id,
        round_number=1,
        kind="fact",
        statement="用户反馈显示首次配置复杂且难以稳定使用。",
        derivation=None,
        content_ids=[content_id],
        evidence_links=[
            {
                "content_id": content_id,
                "support_type": "contradictory" if contradictory else "direct",
                "support_strength": "strong" if not contradictory else "medium",
                "support_explanation": "用户原文直接描述了当前工作流体验。",
            }
        ],
        counterevidence_status="found" if contradictory else "not_found",
        counterevidence_explanation="存在一条不支持该痛点的用户反馈。" if contradictory else "尚未找到反向证据。",
    )


def _seed_two_source_research(client: TestClient, owner_id: str) -> dict[str, object]:
    database = client.app.state.settings.database_path
    task = _task(database, owner_id)
    research = ResearchTaskRepository(database)
    _content(database, content_id="8f-content-bili", platform="bili", author="用户甲", title="AI 工具配置太复杂", description="第一次安装要改很多配置，用户很难完成。")
    _content(database, content_id="8f-content-zhihu", platform="zhihu", author="用户乙", title="AI 工具不稳定又难部署", description="同样的工作流在另一个平台被描述为难用且不稳定。")
    _finding(research, str(task["id"]), "8f-content-bili")
    _finding(research, str(task["id"]), "8f-content-zhihu")
    return task


def test_blank_head_contains_stage_8f_tables_and_nullable_memory_source(test_settings) -> None:
    run_alembic_command(test_settings.database_path, "upgrade", "head")
    with sqlite3.connect(test_settings.database_path) as connection:
        tables = {
            str(row[0])
            for row in connection.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        assert {"opportunity_signals", "opportunities", "opportunity_versions", "validation_plans", "validation_results", "opportunity_actions", "action_outcomes"} <= tables
        memory_columns = {str(row[1]): row[3] for row in connection.execute("PRAGMA table_info(research_memory_items)")}
        assert memory_columns["research_task_id"] == 0
        assert {"source_opportunity_id", "source_action_id", "source_outcome_id"} <= memory_columns.keys()


def test_opportunity_analysis_is_evidence_bound_and_rejects_single_source(client: TestClient, owner_id: str) -> None:
    database = client.app.state.settings.database_path
    task = _task(database, owner_id)
    research = ResearchTaskRepository(database)
    _content(database, content_id="8f-single", platform="bili", author="营销作者", title="一个 AI 工具宣传新功能", description="营销文章声称大家都需要这个功能。")
    _finding(research, str(task["id"]), "8f-single")

    result = client.post(
        "/api/opportunities/analyze",
        json={"source_type": "research_task", "source_id": task["id"], "opportunity_type": "business_opportunity"},
    )
    assert result.status_code == 200, result.text
    payload = result.json()
    assert payload["status"] == "needs_more_evidence"
    assert payload["opportunities"] == []
    assert payload["signal_count"] == 1
    assert client.get("/api/opportunities").json() == []


def test_opportunity_validation_action_outcome_and_memory_loop(client: TestClient, owner_id: str) -> None:
    task = _seed_two_source_research(client, owner_id)
    analysis = client.post(
        "/api/opportunities/analyze",
        json={"source_type": "research_task", "source_id": task["id"], "opportunity_type": "product_opportunity"},
    )
    assert analysis.status_code == 200, analysis.text
    analysis_payload = analysis.json()
    assert analysis_payload["status"] == "opportunity_identified"
    opportunity = analysis_payload["opportunities"][0]
    assert opportunity["readiness"] == "review_ready"
    opportunity_id = str(opportunity["id"])

    detail = client.get(f"/api/opportunities/{opportunity_id}")
    assert detail.status_code == 200, detail.text
    sources = detail.json()["sources"]
    assert len(sources) == 2
    assert len({source["independent_group"] for source in sources}) == 2
    assert all(source["evidence_id"] for source in sources)

    feedback = client.post(f"/api/opportunities/{opportunity_id}/feedback", json={"feedback_type": "valuable"})
    assert feedback.status_code == 201, feedback.text
    assert client.get(f"/api/opportunities/{opportunity_id}").json()["readiness"] != "validated"

    plan_response = client.post(f"/api/opportunities/{opportunity_id}/validation-plan", json={})
    assert plan_response.status_code == 201, plan_response.text
    plan = plan_response.json()
    plan_id = str(plan["id"])
    assert plan["status"] == "draft"
    approved = client.post(f"/api/opportunities/validation-plans/{plan_id}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "ready"

    action = client.post(
        "/api/actions",
        json={
            "opportunity_id": opportunity_id,
            "validation_plan_id": plan_id,
            "source_type": "opportunity",
            "source_id": opportunity_id,
            "action_type": "validate",
            "title": "比较两个替代方案的配置成本",
            "why": "先验证用户是否真的承担配置成本。",
            "expected_result": "形成支持或否定记录。",
            "success_criteria": "完成一次有来源的对比。",
        },
    )
    assert action.status_code == 201, action.text
    action_id = str(action.json()["id"])
    assert action.json()["status"] == "proposed"
    for next_status in ("approved", "in_progress", "completed"):
        transition = client.patch(f"/api/actions/{action_id}", json={"status": next_status})
        assert transition.status_code == 200, transition.text
        assert transition.json()["status"] == next_status

    outcome = client.post(
        f"/api/actions/{action_id}/outcome",
        json={
            "what_happened": "完成了两个平台的配置成本对比。",
            "result": "问题在两个独立来源中均得到部分支持。",
            "evidence": [{"content_id": "8f-content-bili"}],
            "metrics": {},
            "lesson": "先验证配置成本，再判断是否值得做产品改进。",
            "next_step": "继续收集反向用户反馈。",
        },
    )
    assert outcome.status_code == 201, outcome.text
    assert outcome.json()["memory_update_id"]
    memory_updates = client.get("/api/opportunities/memory/updates", params={"opportunity_id": opportunity_id})
    assert memory_updates.status_code == 200, memory_updates.text
    assert memory_updates.json()[0]["source_action_id"] == action_id

    result = client.post(
        f"/api/opportunities/validation-plans/{plan_id}/result",
        json={
            "outcome": "partially_supported",
            "what_happened": "补充研究找到支持与反向证据。",
            "result": "问题存在，但严重度因用户类型不同而不同。",
            "evidence": [{"content_id": "8f-content-zhihu"}],
            "next_step": "降低范围并继续观察。",
        },
    )
    assert result.status_code == 201, result.text
    refreshed = client.get(f"/api/opportunities/{opportunity_id}")
    assert refreshed.status_code == 200, refreshed.text
    refreshed_payload = refreshed.json()
    assert refreshed_payload["version"] == 2
    assert len(refreshed_payload["versions"]) == 2
    assert refreshed_payload["validation_plans"][0]["status"] == "completed"

    space = client.post("/api/research/spaces", json={"name": "8F机会验证", "description": "证据到行动"})
    assert space.status_code == 201, space.text
    space_item = client.post(
        f"/api/research/spaces/{space.json()['id']}/items",
        json={"item_type": "opportunity", "item_id": opportunity_id, "note": "保留机会与验证历史"},
    )
    assert space_item.status_code == 200, space_item.text
    assert space_item.json()["item_type"] == "opportunity"


def test_opportunity_writes_require_csrf_and_owner_scope(client: TestClient, owner_id: str) -> None:
    database = client.app.state.settings.database_path
    task = _task(database, owner_id)
    no_csrf = client.post(
        "/api/opportunities/analyze",
        json={"source_type": "research_task", "source_id": task["id"], "opportunity_type": "research_opportunity"},
        headers={"X-CSRF-Token": ""},
    )
    assert no_csrf.status_code == 403

    other = AuthRepository(database).create_owner(username="other-8f-owner", password_hash=hash_password("other-8f-password"))
    assert str(other["id"]) != owner_id
    assert client.get(f"/api/opportunities/{task['id']}").status_code == 404
