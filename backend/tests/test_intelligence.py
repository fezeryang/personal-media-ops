import sqlite3
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.services.intelligence.coordinator import IntelligenceCoordinator
from app.services.intelligence.trends import calculate_trend_scores


class _FailingBriefGenerator:
    def generate(self, **_: object) -> dict[str, object]:
        raise RuntimeError("synthetic generator failure")


def _insert_content(
    client: TestClient,
    *,
    identifier: str,
    platform: str,
    collected_at: str,
    views: int,
) -> None:
    with sqlite3.connect(client.app.state.settings.database_path) as connection:
        connection.execute(
            """
            INSERT INTO library_contents (
                id, platform, source_content_id, content_type, title,
                description, source_url, cover_url, author_source_id,
                author_name, published_at, first_collected_at,
                last_collected_at, source_keyword, view_count, like_count,
                favorite_count, comment_count, share_count, raw_payload,
                created_at, updated_at, is_favorite
            )
            VALUES (
                ?, ?, ?, 'article', ?, 'evidence',
                'https://example.com/source', NULL, NULL, NULL, ?, ?, ?,
                'AI Agent', ?, 10, NULL, 1, NULL, '{}', ?, ?, 0
            )
            """,
            (
                identifier,
                platform,
                f"source-{identifier}",
                f"Evidence {identifier}",
                collected_at,
                collected_at,
                collected_at,
                views,
                collected_at,
                collected_at,
            ),
        )


def test_trend_formula_is_deterministic_and_bounded() -> None:
    first = calculate_trend_scores(
        current_volume=6,
        previous_volume=3,
        platform_count=2,
        engagement_change=0.5,
    )
    second = calculate_trend_scores(
        current_volume=6,
        previous_volume=3,
        platform_count=2,
        engagement_change=0.5,
    )

    assert first == second
    assert 0 <= first.score <= 100
    assert first.score == round(
        0.35 * first.volume_score
        + 0.30 * first.velocity_score
        + 0.20 * first.cross_platform_score
        + 0.15 * first.engagement_score,
        2,
    )


def test_trends_report_insufficient_data_and_real_evidence(
    client: TestClient,
) -> None:
    _insert_content(
        client,
        identifier="only",
        platform="bili",
        collected_at="2026-07-28T08:00:00Z",
        views=10,
    )
    generated = client.post(
        "/api/intelligence/trends/generate",
        json={
            "window_end": "2026-07-29T00:00:00Z",
            "window_hours": 24,
        },
    )
    assert generated.status_code == 200
    signal = generated.json()[0]
    assert signal["topic"] == "AI Agent"
    assert signal["status"] == "insufficient_data"
    assert signal["content_ids"] == ["only"]
    assert signal["evidence"]["current_volume"] == 1


def test_manual_brief_has_typed_items_and_evidence(client: TestClient) -> None:
    for index, platform in enumerate(("bili", "xhs", "zhihu"), start=1):
        _insert_content(
            client,
            identifier=f"brief-{index}",
            platform=platform,
            collected_at=f"2026-07-28T0{index}:00:00Z",
            views=100 * index,
        )
    client.post(
        "/api/intelligence/trends/generate",
        json={
            "window_end": "2026-07-29T00:00:00Z",
            "window_hours": 24,
        },
    )

    brief = client.post(
        "/api/intelligence/briefs",
        json={
            "window_start": "2026-07-28T00:00:00Z",
            "window_end": "2026-07-29T00:00:00Z",
            "timezone": "Asia/Shanghai",
            "regenerate": False,
        },
    )
    assert brief.status_code == 201
    payload = brief.json()
    assert payload["generator"] == "deterministic"
    assert payload["ai_provider"] == "disabled"
    assert payload["evidence_count"] >= 3
    assert {item["conclusion_type"] for item in payload["items"]}.issubset(
        {"fact", "calculation", "rule", "insufficient_data", "unknown"}
    )
    assert all(
        item["content_ids"] or item["trend_ids"] or item["section"] == "data_gaps"
        for item in payload["items"]
    )

    latest = client.get("/api/intelligence/briefs/latest")
    assert latest.status_code == 200
    assert latest.json()["id"] == payload["id"]

    conflict = client.post(
        "/api/intelligence/briefs",
        json={
            "window_start": "2026-07-28T00:00:00Z",
            "window_end": "2026-07-29T00:00:00Z",
            "timezone": "Asia/Shanghai",
            "regenerate": False,
        },
    )
    assert conflict.status_code == 409
    regenerated = client.post(
        "/api/intelligence/briefs",
        json={
            "window_start": "2026-07-28T00:00:00Z",
            "window_end": "2026-07-29T00:00:00Z",
            "timezone": "Asia/Shanghai",
            "regenerate": True,
        },
    )
    assert regenerated.status_code == 201
    assert regenerated.json()["version"] == 2


def test_daily_brief_schedule_claims_once_and_recovers_after_restart(
    client: TestClient,
    owner_id: str,
) -> None:
    schedule = client.put(
        "/api/intelligence/briefs/schedule",
        json={
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "time_of_day": "09:00",
        },
    )
    assert schedule.status_code == 200
    database_path = client.app.state.settings.database_path
    due_at = "2026-07-29T01:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE brief_schedules SET next_run_at = ? WHERE user_id = ?",
            (due_at, owner_id),
        )
    coordinator = IntelligenceCoordinator(
        client.app.state.intelligence_repository,
        client.app.state.trend_service,
        client.app.state.brief_generator,
    )
    current = datetime(2026, 7, 29, 1, 0, 1, tzinfo=UTC)

    assert coordinator.schedule_due(current) == 1
    restarted = IntelligenceCoordinator(
        client.app.state.intelligence_repository,
        client.app.state.trend_service,
        client.app.state.brief_generator,
    )
    assert restarted.schedule_due(current) == 0
    latest = client.get("/api/intelligence/briefs/latest")
    assert latest.status_code == 200
    assert latest.json()["generator"] == "deterministic"
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM briefs
                WHERE user_id = ? AND window_end = ?
                """,
                (owner_id, due_at),
            ).fetchone()[0]
            == 1
        )


def test_daily_brief_failure_is_recorded_without_stopping_scheduler(
    client: TestClient,
    owner_id: str,
) -> None:
    schedule = client.put(
        "/api/intelligence/briefs/schedule",
        json={
            "enabled": True,
            "timezone": "Asia/Shanghai",
            "time_of_day": "09:00",
        },
    )
    assert schedule.status_code == 200
    database_path = client.app.state.settings.database_path
    due_at = "2026-07-29T01:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE brief_schedules SET next_run_at = ? WHERE user_id = ?",
            (due_at, owner_id),
        )
    coordinator = IntelligenceCoordinator(
        client.app.state.intelligence_repository,
        client.app.state.trend_service,
        _FailingBriefGenerator(),
    )

    assert coordinator.schedule_due(
        datetime(2026, 7, 29, 1, 0, 1, tzinfo=UTC)
    ) == 0
    persisted = client.get("/api/intelligence/briefs/schedule")
    assert persisted.status_code == 200
    assert persisted.json()["consecutive_failures"] == 1
    assert (
        persisted.json()["last_error"]
        == "brief generation failed: synthetic generator failure"
    )
