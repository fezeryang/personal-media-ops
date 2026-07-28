import sqlite3
from dataclasses import replace

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.alembic_utils import run_alembic_command


def create_task(
    client: TestClient,
    keywords: str = "AI Agent",
    *,
    platform: str = "bili",
    requested_count: int = 20,
) -> dict[str, object]:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": platform,
            "crawler_type": "search",
            "keywords": keywords,
            "requested_count": requested_count,
        },
    )
    assert response.status_code == 201
    return response.json()


def test_create_and_list_crawler_tasks(client: TestClient) -> None:
    first = create_task(client, "first")
    second = create_task(client, "second")

    detail = client.get(f"/api/crawler/tasks/{first['id']}")
    listing = client.get("/api/crawler/tasks")

    assert detail.status_code == 200
    assert detail.json()["status"] == "pending"
    assert detail.json()["login_type"] == "qrcode"
    assert listing.status_code == 200
    assert [task["id"] for task in listing.json()] == [second["id"], first["id"]]


def test_capabilities_report_registry_and_global_limit(
    client: TestClient,
) -> None:
    response = client.get("/api/crawler/capabilities")

    assert response.status_code == 200
    assert response.json()["max_concurrent_tasks"] == 1
    assert [
        (
            item["platform"],
            item["enabled"],
            item["verification_status"],
            item["availability_status"],
        )
        for item in response.json()["platforms"]
    ] == [
        ("bili", True, "production_verified", "enabled"),
        ("xhs", True, "production_verified", "enabled"),
        ("dy", False, "code_ready", "deferred_resource_constrained"),
        ("zhihu", False, "production_verified", "disabled"),
        ("wb", False, "production_verified", "disabled"),
        ("tieba", False, "code_ready", "disabled"),
        ("ks", False, "code_ready", "disabled"),
    ]
    assert all(item["icon_label"] for item in response.json()["platforms"])
    assert all(item["login_prompt"] for item in response.json()["platforms"])


def test_create_supports_enabled_xhs(
    client: TestClient,
) -> None:
    xhs = create_task(client, platform="xhs")

    assert xhs["platform"] == "xhs"


def test_create_supports_each_configured_remaining_platform(
    test_settings: Settings,
) -> None:
    enabled = replace(
        test_settings,
        enabled_platforms=("bili", "xhs", "zhihu", "wb", "tieba", "ks"),
    )
    run_alembic_command(enabled.database_path, "upgrade", "head")
    with TestClient(create_app(enabled)) as client:
        created = [
            create_task(client, platform=platform)
            for platform in ("zhihu", "wb", "tieba", "ks")
        ]

    assert [task["platform"] for task in created] == [
        "zhihu",
        "wb",
        "tieba",
        "ks",
    ]


def test_create_rejects_disabled_platform(
    test_settings: Settings,
) -> None:
    bili_only = replace(test_settings, enabled_platforms=("bili",))
    run_alembic_command(bili_only.database_path, "upgrade", "head")
    with TestClient(create_app(bili_only)) as client:
        response = client.post(
            "/api/crawler/tasks",
            json={
                "platform": "xhs",
                "crawler_type": "search",
                "keywords": "test",
                "requested_count": 1,
            },
        )

    assert response.status_code == 409
    assert "not enabled" in response.json()["detail"].lower()


def test_create_rejects_unsupported_platform_and_extra_controls(
    client: TestClient,
) -> None:
    unsupported = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "youtube",
            "crawler_type": "search",
            "keywords": "test",
            "requested_count": 1,
        },
    )
    injected = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "crawler_type": "search",
            "keywords": "test",
            "requested_count": 1,
            "command": "rm -rf /",
        },
    )
    control_characters = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "crawler_type": "search",
            "keywords": "line one\nline two",
            "requested_count": 1,
        },
    )

    assert unsupported.status_code == 422
    assert injected.status_code == 422
    assert control_characters.status_code == 422


def test_cancel_pending_task_is_immediate(client: TestClient) -> None:
    task = create_task(client)

    response = client.post(f"/api/crawler/tasks/{task['id']}/cancel")

    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"
    assert response.json()["cancel_requested"] is True
    assert response.json()["finished_at"] is not None
    assert client.post(f"/api/crawler/tasks/{task['id']}/cancel").status_code == 409


def test_results_are_paginated_without_loading_every_line(
    client: TestClient,
    test_settings: Settings,
) -> None:
    task = create_task(client)
    task_dir = test_settings.output_root / "tasks" / str(task["id"])
    result_dir = task_dir / "bilibili" / "jsonl"
    result_dir.mkdir(parents=True)
    (result_dir / "search_contents_2026-07-26.jsonl").write_text(
        "\n".join(
            (
                '{"video_id": "'
                f'{index}", "title": "Video {index}", '
                f'"video_play_count": "{index}"'
                "}"
            )
            for index in range(5)
        )
        + "\n",
        encoding="utf-8",
    )

    response = client.get(
        f"/api/crawler/tasks/{task['id']}/results",
        params={"offset": 1, "limit": 2},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [
            {
                "platform": "bili",
                "content_id": "1",
                "content_type": "video",
                "title": "Video 1",
                "description": None,
                "author_name": None,
                "content_url": None,
                "cover_url": None,
                "published_at": None,
                "source_keyword": None,
                "raw_payload": {
                    "video_id": "1",
                    "title": "Video 1",
                    "video_play_count": "1",
                },
                "metrics": {
                    "play_count": 1,
                    "like_count": None,
                    "favorite_count": None,
                    "comment_count": None,
                    "share_count": None,
                },
            },
            {
                "platform": "bili",
                "content_id": "2",
                "content_type": "video",
                "title": "Video 2",
                "description": None,
                "author_name": None,
                "content_url": None,
                "cover_url": None,
                "published_at": None,
                "source_keyword": None,
                "raw_payload": {
                    "video_id": "2",
                    "title": "Video 2",
                    "video_play_count": "2",
                },
                "metrics": {
                    "play_count": 2,
                    "like_count": None,
                    "favorite_count": None,
                    "comment_count": None,
                    "share_count": None,
                },
            },
        ],
        "offset": 1,
        "limit": 2,
        "next_offset": 3,
        "has_more": True,
    }


def test_results_are_capped_at_requested_count(
    client: TestClient,
    test_settings: Settings,
) -> None:
    task = create_task(client, requested_count=2)
    result_dir = (
        test_settings.output_root / "tasks" / str(task["id"]) / "bilibili" / "jsonl"
    )
    result_dir.mkdir(parents=True)
    (result_dir / "search_contents_2026-07-26.jsonl").write_text(
        "\n".join(
            f'{{"video_id": "{index}", "title": "Video {index}"}}' for index in range(5)
        )
        + "\n",
        encoding="utf-8",
    )

    response = client.get(
        f"/api/crawler/tasks/{task['id']}/results",
        params={"offset": 0, "limit": 20},
    )

    assert response.status_code == 200
    assert len(response.json()["items"]) == 2
    assert response.json()["has_more"] is False


def test_result_path_traversal_in_database_is_rejected(
    client: TestClient,
    test_settings: Settings,
) -> None:
    task = create_task(client)
    outside = test_settings.output_root.parent / "outside"
    outside.mkdir()
    (outside / "stolen.jsonl").write_text('{"secret": true}\n', encoding="utf-8")
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE crawler_tasks SET output_dir = ? WHERE id = ?",
            (str(outside), task["id"]),
        )

    response = client.get(f"/api/crawler/tasks/{task['id']}/results")

    assert response.status_code == 409
    assert "secret" not in response.text


def test_logs_support_offset_and_tail(
    client: TestClient,
    test_settings: Settings,
) -> None:
    task = create_task(client)
    log_path = test_settings.log_root / "crawler" / f"{task['id']}.log"
    log_path.parent.mkdir(parents=True)
    log_path.write_text("first\nsecond\nthird\n", encoding="utf-8")

    offset_response = client.get(
        f"/api/crawler/tasks/{task['id']}/logs",
        params={"offset": 6},
    )
    tail_response = client.get(
        f"/api/crawler/tasks/{task['id']}/logs",
        params={"tail": 2},
    )

    assert offset_response.status_code == 200
    assert offset_response.text == "second\nthird\n"
    assert offset_response.headers["x-next-offset"] == "19"
    assert tail_response.status_code == 200
    assert tail_response.text == "second\nthird\n"


def test_log_path_traversal_in_database_is_rejected(
    client: TestClient,
    test_settings: Settings,
) -> None:
    task = create_task(client)
    outside = test_settings.log_root.parent / "secret.log"
    outside.write_text("do not expose\n", encoding="utf-8")
    with sqlite3.connect(test_settings.database_path) as connection:
        connection.execute(
            "UPDATE crawler_tasks SET log_path = ? WHERE id = ?",
            (str(outside), task["id"]),
        )

    response = client.get(f"/api/crawler/tasks/{task['id']}/logs")

    assert response.status_code == 409
    assert "do not expose" not in response.text


def test_qrcode_returns_status_until_generated_then_png(
    client: TestClient,
    test_settings: Settings,
) -> None:
    task = create_task(client)

    unavailable = client.get(f"/api/crawler/tasks/{task['id']}/qrcode")

    qrcode_path = test_settings.qrcode_root / f"{task['id']}.png"
    qrcode_path.parent.mkdir(parents=True)
    qrcode_path.write_bytes(b"\x89PNG\r\n\x1a\nfake")
    available = client.get(f"/api/crawler/tasks/{task['id']}/qrcode")

    assert unavailable.status_code == 404
    assert unavailable.json()["status"] == "pending"
    assert available.status_code == 200
    assert available.headers["content-type"] == "image/png"
    assert available.content.startswith(b"\x89PNG")
