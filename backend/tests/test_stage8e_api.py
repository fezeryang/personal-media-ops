from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.repositories.ai import AIRepository
from app.repositories.monitoring import MonitoringConflict, MonitoringRepository


def _mission_payload() -> dict[str, object]:
    return {
        "goal": "持续关注个人 AI 工具的功能变化和真实用户反馈。",
        "mission_type": "research_question",
        "platforms": [],
        "schedule_type": "manual",
        "confirmed": False,
    }


def test_monitoring_mission_two_step_flow_baseline_and_silent_repeat(
    client: TestClient,
) -> None:
    draft = client.post("/api/monitoring/missions", json=_mission_payload())
    assert draft.status_code == 201
    mission = draft.json()
    assert mission["status"] == "draft"
    assert mission["understanding"]["known_baseline"].startswith("首次运行")

    mission_id = mission["id"]
    confirmed = client.post(f"/api/monitoring/missions/{mission_id}/confirm")
    assert confirmed.status_code == 200
    assert confirmed.json()["status"] == "active"
    listing = client.get("/api/monitoring/missions")
    assert listing.status_code == 200
    assert listing.json()[0]["id"] == mission_id
    assert "targets" not in listing.json()[0]

    first = client.post(f"/api/monitoring/missions/{mission_id}/run")
    assert first.status_code == 200
    assert first.json()["outcome"] == "baseline_created"
    assert first.json()["baseline_created"] is True

    second = client.post(f"/api/monitoring/missions/{mission_id}/run")
    assert second.status_code == 200
    assert second.json()["outcome"] == "no_meaningful_change"
    assert second.json()["notification_count"] == 0

    baseline = client.get(f"/api/monitoring/missions/{mission_id}/baseline")
    assert baseline.status_code == 200
    assert baseline.json()["version"] == 2
    runs = client.get(f"/api/monitoring/missions/{mission_id}/runs")
    assert runs.status_code == 200
    assert len(runs.json()) == 2

    paused = client.post(f"/api/monitoring/missions/{mission_id}/pause")
    assert paused.status_code == 200
    assert paused.json()["status"] == "paused"
    resumed = client.post(f"/api/monitoring/missions/{mission_id}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["status"] == "active"


@pytest.mark.parametrize("research_status", ["Done", "AwaitingReview"])
def test_platform_run_uses_existing_research_runtime_bridge(
    client: TestClient,
    research_status: str,
) -> None:
    payload = {**_mission_payload(), "platforms": ["bili"], "confirmed": True}
    created = client.post("/api/monitoring/missions", json=payload)
    assert created.status_code == 201
    mission_id = created.json()["id"]

    queued = client.post(f"/api/monitoring/missions/{mission_id}/run")
    assert queued.status_code == 200
    result = queued.json()
    assert result["outcome"] == "research_task_queued"
    assert result["status"] == "running"
    assert result["research_task_id"]
    assert result["baseline_created"] is True

    from app.repositories.research import ResearchTaskRepository

    research = ResearchTaskRepository(client.app.state.settings.database_path)
    queued_task = research.get_for_runtime(result["research_task_id"], detail=True)
    assert queued_task is not None
    assert queued_task["intent_contract"]["intent_source"] == "fallback_default"
    research.transition(
        result["research_task_id"],
        status=research_status,
        reason=f"test_research_runtime_{research_status.casefold()}",
        finished=research_status == "Done",
    )
    assert client.app.state.monitoring_service.reconcile_linked_runs() == 1
    runs = client.get(f"/api/monitoring/missions/{mission_id}/runs").json()
    assert runs[0]["status"] == "no_meaningful_change"


def test_monitoring_run_lock_is_owner_scoped(
    client: TestClient,
    owner_id: str,
) -> None:
    repository = MonitoringRepository(client.app.state.settings.database_path)
    mission = repository.create_mission(
        owner_id=owner_id,
        goal="锁测试监控目标",
        title="锁测试",
        mission_type="topic",
        targets=[],
        platforms=[],
        schedule_type="manual",
        schedule_config={},
        importance_rule=None,
        ignored_content_rule=None,
        budget={},
        understanding={"known_baseline": "test"},
        confirmed=True,
    )
    first = repository.claim_run(
        owner_id=owner_id,
        mission_id=str(mission["id"]),
        trigger="manual",
    )
    with pytest.raises(MonitoringConflict):
        repository.claim_run(
            owner_id=owner_id,
            mission_id=str(mission["id"]),
            trigger="manual",
        )
    assert first["status"] == "running"


def test_prompt_registry_eval_read_view_and_explicit_rollback(
    client: TestClient,
) -> None:
    prompts = client.get("/api/ai/prompts")
    assert prompts.status_code == 200
    assert len(prompts.json()) >= 9
    assert all(item["active_version"] == "v1" for item in prompts.json())
    intent_prompt = next(item for item in prompts.json() if item["prompt_key"] == "intent_interpreter")
    assert intent_prompt["candidate_version"] == "v2"

    evals = client.get("/api/ai/evals")
    assert evals.status_code == 200
    assert len(evals.json()) >= 12
    assert all("golden_answer" not in item for item in evals.json())

    replay = AIRepository(client.app.state.settings.database_path).replay_recorded_task(
        prompt_key="intent_interpreter",
        prompt_version="v1",
        recorded_task_id="recorded-task-1",
        recorded_response={
            "product_exploration": {
                "intent": "discovery",
                "evidence": [{"content_id": "recorded-content-1"}],
            }
        },
    )
    assert replay["case_count"] >= 12
    assert replay["status_counts"]["partial"] >= 1
    refreshed_evals = client.get("/api/ai/evals").json()
    assert any(item["last_result"] is not None for item in refreshed_evals)

    activated = client.post(
        "/api/ai/prompts/intent_interpreter/activate",
        json={"version": "v2"},
    )
    assert activated.status_code == 200
    assert activated.json()["active_version"] == "v2"
    rolled_back = client.post("/api/ai/prompts/intent_interpreter/rollback")
    assert rolled_back.status_code == 200
    assert rolled_back.json()["active_version"] == "v1"
    assert rolled_back.json()["candidate_version"] == "v2"


def test_recorded_eval_replay_runs_fixed_cases_and_requires_csrf(
    client: TestClient,
) -> None:
    replay = client.post(
        "/api/ai/evals/replay",
        json={"prompt_key": "intent_interpreter", "prompt_version": "v2"},
    )
    assert replay.status_code == 200
    result = replay.json()
    assert result["case_count"] >= 12
    assert result["status_counts"]["passed"] >= 2
    assert result["prompt_version"] == "v2"

    evals = client.get("/api/ai/evals")
    assert evals.status_code == 200
    assert sum(item["last_result"] is not None for item in evals.json()) >= 2

    denied = client.post(
        "/api/ai/evals/replay",
        json={"prompt_key": "intent_interpreter", "prompt_version": "v2"},
        headers={"Origin": "http://testserver", "X-CSRF-Token": "invalid"},
    )
    assert denied.status_code == 403


def test_prompt_mutation_requires_csrf(client: TestClient) -> None:
    response = client.post(
        "/api/ai/prompts/intent_interpreter/activate",
        json={"version": "v1"},
        headers={"Origin": "http://testserver", "X-CSRF-Token": "invalid"},
    )
    assert response.status_code == 403
