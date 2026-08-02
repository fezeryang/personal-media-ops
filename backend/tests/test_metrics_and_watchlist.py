import sqlite3
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.crawler.results import TaskEntityBatch
from app.models.library import NormalizedContent, NormalizedCreator
from app.repositories.library import LibraryRepository


def _seed_active_task(client: TestClient, task_id: str) -> None:
    settings = client.app.state.settings
    repository = client.app.state.crawler_repository
    repository.create(
        task_id=task_id,
        platform="bili",
        crawler_type="search",
        keywords="AI Agent",
        login_type="qrcode",
        requested_count=1,
        output_dir=str(settings.output_root / "tasks" / task_id),
        log_path=str(settings.log_root / "crawler" / f"{task_id}.log"),
        qrcode_path=str(settings.qrcode_root / f"{task_id}.png"),
    )
    assert repository.claim_next()["id"] == task_id


def _batch(
    *,
    views: int | None,
    followers: int | None,
    title: str = "Metric content",
) -> TaskEntityBatch:
    return TaskEntityBatch(
        contents=[
            NormalizedContent(
                platform="bili",
                source_content_id="BV-metric",
                content_type="video",
                title=title,
                description=None,
                source_url="https://www.bilibili.com/video/BV-metric",
                cover_url=None,
                author_source_id="creator-metric",
                author_name="Metric creator",
                published_at=1_722_124_800,
                source_keyword="AI Agent",
                view_count=views,
                like_count=10,
                favorite_count=None,
                comment_count=2,
                share_count=None,
                raw_payload={},
            )
        ],
        creators=[
            NormalizedCreator(
                platform="bili",
                source_creator_id="creator-metric",
                display_name="Metric creator",
                profile_url="https://space.bilibili.com/creator-metric",
                avatar_url=None,
                description=None,
                follower_count=followers,
                following_count=None,
                content_count=4,
                raw_payload={},
            )
        ],
        comments=[],
        actual_count=1,
    )


def test_ingestion_classifies_incremental_results_and_snapshots(
    client: TestClient,
) -> None:
    library = LibraryRepository(client.app.state.settings.database_path)
    _seed_active_task(client, "metric-one")
    first = library.ingest_task(
        task_id="metric-one",
        batch=_batch(views=100, followers=20),
    )
    _seed_active_task(client, "metric-two")
    second = library.ingest_task(
        task_id="metric-two",
        batch=_batch(views=125, followers=None),
    )
    _seed_active_task(client, "metric-three")
    third = library.ingest_task(
        task_id="metric-three",
        batch=_batch(views=125, followers=None, title="Metric content updated"),
    )

    assert first.new_content_count == 1
    assert first.existing_content_count == 0
    assert second.new_content_count == 0
    assert second.existing_content_count == 1
    assert second.changed_content_count == 1
    assert second.updated_content_count == 0
    assert third.existing_content_count == 1
    assert third.changed_content_count == 0
    assert third.updated_content_count == 1

    database_path = client.app.state.settings.database_path
    with sqlite3.connect(database_path) as connection:
        content_snapshots = connection.execute(
            "SELECT COUNT(*) FROM content_metric_snapshots"
        ).fetchone()[0]
        creator_snapshots = connection.execute(
            "SELECT COUNT(*) FROM creator_metric_snapshots"
        ).fetchone()[0]
        follower_count = connection.execute(
            """
            SELECT follower_count FROM library_creators
            WHERE platform = 'bili' AND source_creator_id = 'creator-metric'
            """
        ).fetchone()[0]
        research_counts = connection.execute(
            """
            SELECT id, research_new_content_count,
                   research_existing_content_count,
                   research_updated_content_count
            FROM crawler_tasks
            WHERE id IN ('metric-one', 'metric-two', 'metric-three')
            ORDER BY id
            """
        ).fetchall()
    assert content_snapshots == 2
    assert creator_snapshots == 1
    assert follower_count == 20
    assert research_counts == [
        ("metric-one", 1, 0, 0),
        ("metric-three", 0, 1, 1),
        ("metric-two", 0, 1, 0),
    ]

    content_id = library.list_contents(
        platform="bili",
        content_type=None,
        keyword=None,
        creator=None,
        date_from=None,
        date_to=None,
        has_comments=None,
        tag_id=None,
        is_favorite=None,
        sort="last_collected_desc",
        offset=0,
        limit=10,
    )["items"][0]["id"]
    history = client.get(f"/api/library/contents/{content_id}/metrics")
    assert history.status_code == 200
    snapshots = history.json()["items"]
    assert len(snapshots) == 2
    assert snapshots[0]["delta_from_previous"]["view_count"] is None
    assert snapshots[1]["delta_from_previous"]["view_count"] == 25


def test_creator_watchlist_manual_run_and_capability_gate(
    client: TestClient,
) -> None:
    now = "2026-07-28T00:00:00Z"
    database_path = client.app.state.settings.database_path
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO library_creators (
                id, platform, source_creator_id, display_name, profile_url,
                avatar_url, description, follower_count, following_count,
                content_count, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (
                'creator-bili', 'bili', '42', 'Verified creator',
                'https://space.bilibili.com/42', NULL, NULL, 100, NULL, 5,
                ?, ?, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )
        connection.execute(
            """
            INSERT INTO library_creators (
                id, platform, source_creator_id, display_name, profile_url,
                avatar_url, description, follower_count, following_count,
                content_count, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (
                'creator-xhs', 'xhs', 'xhs-42', 'Deferred creator',
                'https://www.xiaohongshu.com/user/profile/xhs-42',
                NULL, NULL, 100, NULL, 5, ?, ?, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )

    created = client.post(
        "/api/watchlist",
        json={
            "creator_id": "creator-bili",
            "enabled": False,
            "check_frequency": "daily",
            "requested_count": 3,
            "timezone": "Asia/Shanghai",
        },
    )
    assert created.status_code == 201
    watch = created.json()
    run = client.post(f"/api/watchlist/{watch['id']}/run")
    assert run.status_code == 202
    assert run.json()["task_id"]
    task = client.get(
        f"/api/crawler/tasks/{run.json()['task_id']}"
    ).json()
    assert task["mode"] == "creator"
    assert task["requested_count"] == 3

    deferred = client.post(
        "/api/watchlist",
        json={
            "creator_id": "creator-xhs",
            "enabled": False,
            "check_frequency": "daily",
            "requested_count": 3,
            "timezone": "Asia/Shanghai",
        },
    )
    assert deferred.status_code == 409


def test_creator_watch_reuses_provenance_target_for_privacy_safe_id(
    client: TestClient,
) -> None:
    now = "2026-07-28T00:00:00Z"
    settings = client.app.state.settings
    crawler = client.app.state.crawler_repository
    crawler.create(
        task_id="creator-source-task",
        platform="bili",
        crawler_type="creator",
        keywords=None,
        login_type="qrcode",
        creator_ids=("3546860755093522",),
        requested_count=1,
        output_dir=str(settings.output_root / "tasks" / "creator-source-task"),
        log_path=str(settings.log_root / "crawler" / "creator-source-task.log"),
        qrcode_path=str(settings.qrcode_root / "creator-source-task.png"),
    )
    assert crawler.claim_next()["id"] == "creator-source-task"
    crawler.complete_success("creator-source-task", 1)

    with sqlite3.connect(settings.database_path) as connection:
        connection.execute(
            """
            INSERT INTO library_creators (
                id, platform, source_creator_id, display_name, profile_url,
                avatar_url, description, follower_count, following_count,
                content_count, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (
                'creator-private', 'bili', '33bf99b7e01f4ab4',
                'Privacy-safe creator', NULL, NULL, NULL, 100, NULL, 5,
                ?, ?, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )
        connection.execute(
            """
            INSERT INTO crawl_task_entities (
                task_id, entity_type, entity_id, collected_at
            )
            VALUES ('creator-source-task', 'creator', 'creator-private', ?)
            """,
            (now,),
        )
        connection.execute(
            """
            INSERT INTO library_creators (
                id, platform, source_creator_id, display_name, profile_url,
                avatar_url, description, follower_count, following_count,
                content_count, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (
                'creator-private-unresolved', 'bili', '0123456789abcdef',
                'Unresolved creator', NULL, NULL, NULL, NULL, NULL, NULL,
                ?, ?, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )

    created = client.post(
        "/api/watchlist",
        json={
            "creator_id": "creator-private",
            "enabled": False,
            "check_frequency": "daily",
            "requested_count": 2,
            "timezone": "Asia/Shanghai",
        },
    )
    assert created.status_code == 201
    run = client.post(f"/api/watchlist/{created.json()['id']}/run")
    assert run.status_code == 202
    task = client.get(
        f"/api/crawler/tasks/{run.json()['task_id']}"
    ).json()
    assert task["creator_ids"] == ["3546860755093522"]
    assert crawler.claim_next()["id"] == run.json()["task_id"]
    crawler.complete_success(run.json()["task_id"], 1)
    client.app.state.automation_coordinator.reconcile_runs()
    with sqlite3.connect(settings.database_path) as connection:
        reconciled = connection.execute(
            """
            SELECT status, started_at, finished_at
            FROM creator_watch_runs
            WHERE id = ?
            """,
            (run.json()["id"],),
        ).fetchone()
    assert reconciled[0] == "succeeded"
    assert reconciled[1] is not None
    assert reconciled[2] is not None
    unresolved = client.post(
        "/api/watchlist",
        json={
            "creator_id": "creator-private-unresolved",
            "enabled": False,
            "check_frequency": "daily",
            "requested_count": 2,
            "timezone": "Asia/Shanghai",
        },
    )
    assert unresolved.status_code == 409
    assert "collect it through creator mode first" in unresolved.json()["detail"]


def test_creator_watch_schedule_is_idempotent_and_can_be_paused(
    client: TestClient,
) -> None:
    now = "2026-07-28T00:00:00Z"
    database_path = client.app.state.settings.database_path
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO library_creators (
                id, platform, source_creator_id, display_name, profile_url,
                avatar_url, description, follower_count, following_count,
                content_count, first_collected_at, last_collected_at,
                raw_payload, created_at, updated_at
            )
            VALUES (
                'creator-scheduled', 'bili', 'scheduled-42',
                'Scheduled creator', NULL, NULL, NULL, 100, NULL, 5,
                ?, ?, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )
    watch = client.post(
        "/api/watchlist",
        json={
            "creator_id": "creator-scheduled",
            "enabled": True,
            "check_frequency": "every_6_hours",
            "requested_count": 2,
            "timezone": "Asia/Shanghai",
        },
    ).json()
    due_at = "2026-07-28T12:00:00Z"
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "UPDATE creator_watchlist SET next_check_at = ? WHERE id = ?",
            (due_at, watch["id"]),
        )

    current = datetime(2026, 7, 28, 12, 0, 1, tzinfo=UTC)
    assert client.app.state.automation_coordinator.schedule_due(current) == 1
    assert client.app.state.automation_coordinator.schedule_due(current) == 0
    with sqlite3.connect(database_path) as connection:
        assert (
            connection.execute(
                """
                SELECT COUNT(*) FROM creator_watch_runs
                WHERE watch_id = ? AND scheduled_for = ?
                """,
                (watch["id"], due_at),
            ).fetchone()[0]
            == 1
        )

    paused = client.patch(
        f"/api/watchlist/{watch['id']}",
        json={"enabled": False},
    )
    assert paused.status_code == 200
    assert paused.json()["enabled"] is False
    assert paused.json()["next_check_at"] is None
