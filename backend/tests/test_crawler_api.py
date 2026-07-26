import sqlite3

from fastapi.testclient import TestClient

from app.core.config import Settings


def create_task(client: TestClient, keywords: str = "AI Agent") -> dict[str, object]:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "crawler_type": "search",
            "keywords": keywords,
            "requested_count": 20,
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


def test_create_rejects_unsupported_platform_and_extra_controls(
    client: TestClient,
) -> None:
    unsupported = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "xhs",
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
    task_dir.mkdir(parents=True)
    (task_dir / "results.jsonl").write_text(
        "\n".join(f'{{"index": {index}}}' for index in range(5)) + "\n",
        encoding="utf-8",
    )

    response = client.get(
        f"/api/crawler/tasks/{task['id']}/results",
        params={"offset": 1, "limit": 2},
    )

    assert response.status_code == 200
    assert response.json() == {
        "items": [{"index": 1}, {"index": 2}],
        "offset": 1,
        "limit": 2,
        "next_offset": 3,
        "has_more": True,
    }


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
