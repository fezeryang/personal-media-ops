import sqlite3
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.services.scheduling import next_scheduled_time


def subscription_payload(
    *,
    platforms: list[str] | None = None,
    enabled: bool = True,
    schedule_type: str = "manual",
) -> dict[str, object]:
    return {
        "name": "AI Agent 每日观察",
        "query": "AI Agent",
        "platforms": [
            {"platform": platform, "requested_count": 2}
            for platform in (platforms or ["bili", "xhs"])
        ],
        "enabled": enabled,
        "schedule_type": schedule_type,
        "schedule_config": (
            {"time_of_day": "09:00"}
            if schedule_type in {"daily", "weekdays"}
            else {}
        ),
        "timezone": "Asia/Shanghai",
    }


def test_schedule_calculation_handles_dst_gap_and_fold_once() -> None:
    spring = next_scheduled_time(
        schedule_type="daily",
        schedule_config={"time_of_day": "02:30"},
        timezone_name="America/Los_Angeles",
        after=datetime(2026, 3, 8, 8, 0, tzinfo=UTC),
    )
    fall = next_scheduled_time(
        schedule_type="daily",
        schedule_config={"time_of_day": "01:30"},
        timezone_name="America/Los_Angeles",
        after=datetime(2026, 11, 1, 7, 0, tzinfo=UTC),
    )

    assert spring == datetime(2026, 3, 8, 10, 0, tzinfo=UTC)
    assert fall == datetime(2026, 11, 1, 8, 30, tzinfo=UTC)


def test_subscription_create_edit_pause_resume_and_manual_run(
    client: TestClient,
) -> None:
    created = client.post("/api/subscriptions", json=subscription_payload())
    assert created.status_code == 201
    subscription = created.json()
    assert subscription["next_run_at"] is None
    assert [item["platform"] for item in subscription["platforms"]] == [
        "bili",
        "xhs",
    ]

    updated = client.put(
        f"/api/subscriptions/{subscription['id']}",
        json=subscription_payload(
            platforms=["bili"],
            schedule_type="daily",
        ),
    )
    assert updated.status_code == 200
    assert updated.json()["next_run_at"] is not None

    paused = client.post(f"/api/subscriptions/{subscription['id']}/pause")
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False
    assert paused.json()["next_run_at"] is None

    resumed = client.post(f"/api/subscriptions/{subscription['id']}/resume")
    assert resumed.status_code == 200
    assert resumed.json()["enabled"] is True

    run = client.post(f"/api/subscriptions/{subscription['id']}/run")
    assert run.status_code == 202
    assert run.json()["status"] == "queued"
    assert len(run.json()["platform_results"]) == 1
    assert run.json()["platform_results"][0]["task_id"]

    detail = client.get(f"/api/subscriptions/{subscription['id']}")
    assert detail.status_code == 200
    assert detail.json()["runs"][0]["id"] == run.json()["id"]


def test_subscription_rejects_deferred_search_platforms(client: TestClient) -> None:
    for platform in ("dy", "ks"):
        response = client.post(
            "/api/subscriptions",
            json=subscription_payload(platforms=[platform]),
        )
        assert response.status_code == 409
        assert "search" in response.json()["detail"]


def test_scheduler_is_idempotent_and_queues_platforms_in_order(
    client: TestClient,
) -> None:
    created = client.post(
        "/api/subscriptions",
        json=subscription_payload(schedule_type="every_6_hours"),
    )
    assert created.status_code == 201
    subscription_id = created.json()["id"]
    due_at = "2026-07-28T12:00:00Z"
    database_path = client.app.state.settings.database_path
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE subscriptions SET next_run_at = ? WHERE id = ?",
            (due_at, subscription_id),
        )

    now = datetime(2026, 7, 28, 12, 0, 1, tzinfo=UTC)
    first = client.app.state.automation_coordinator.schedule_due(now)
    second = client.app.state.automation_coordinator.schedule_due(now)

    assert first == 1
    assert second == 0
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM subscription_runs
                WHERE subscription_id = ? AND scheduled_for = ?
                """,
                (subscription_id, due_at),
            ).fetchone()[0]
            == 1
        )
        platforms = [
            row[0]
            for row in connection.execute(
                """
                SELECT platform
                FROM subscription_run_tasks
                WHERE run_id = (
                    SELECT id FROM subscription_runs
                    WHERE subscription_id = ? AND scheduled_for = ?
                )
                ORDER BY sequence
                """,
                (subscription_id, due_at),
            )
        ]
    assert platforms == ["bili", "xhs"]


def test_scheduler_restart_reconciles_interrupted_run(
    client: TestClient,
) -> None:
    subscription = client.post(
        "/api/subscriptions",
        json=subscription_payload(platforms=["bili"]),
    ).json()
    run = client.post(f"/api/subscriptions/{subscription['id']}/run").json()
    task_id = run["platform_results"][0]["task_id"]
    repository = client.app.state.crawler_repository
    claimed = repository.claim_next()
    assert claimed is not None and claimed["id"] == task_id

    assert repository.fail_interrupted_tasks() == 1
    client.app.state.automation_coordinator.reconcile_runs()

    detail = client.get(f"/api/subscriptions/{subscription['id']}").json()
    assert detail["runs"][0]["status"] == "failed"
    assert detail["consecutive_failures"] == 1
    assert detail["next_run_at"] is None
