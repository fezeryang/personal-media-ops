from dataclasses import replace

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from tests.alembic_utils import run_alembic_command


def enabled_client(test_settings: Settings) -> TestClient:
    settings = replace(
        test_settings,
        enabled_platforms=("bili", "xhs", "zhihu", "wb", "tieba", "ks"),
    )
    run_alembic_command(settings.database_path, "upgrade", "head")
    return TestClient(create_app(settings))


def test_capabilities_expose_seven_by_five_mode_matrix(
    client: TestClient,
) -> None:
    response = client.get("/api/crawler/capabilities")

    assert response.status_code == 200
    platforms = response.json()["platforms"]
    assert len(platforms) == 7
    assert {
        (platform["platform"], mode["mode"])
        for platform in platforms
        for mode in platform["modes"]
    } == {
        (platform, mode)
        for platform in ("bili", "xhs", "dy", "zhihu", "wb", "tieba", "ks")
        for mode in ("search", "detail", "creator", "comments", "sub_comments")
    }
    douyin = next(item for item in platforms if item["platform"] == "dy")
    assert {
        mode["status"] for mode in douyin["modes"]
    } == {"deferred_resource_constrained"}
    kuaishou = next(item for item in platforms if item["platform"] == "ks")
    assert next(
        mode for mode in kuaishou["modes"] if mode["mode"] == "search"
    )["status"] == "deferred_upstream_breakage"


@pytest.mark.parametrize(
    ("payload", "expected_mode"),
    [
        (
            {
                "platform": "bili",
                "mode": "search",
                "keywords": "AI Agent",
                "requested_count": 2,
            },
            "search",
        ),
        (
            {
                "platform": "bili",
                "mode": "detail",
                "target_urls": ["https://www.bilibili.com/video/BV1xx"],
                "requested_count": 1,
            },
            "detail",
        ),
        (
            {
                "platform": "bili",
                "mode": "creator",
                "creator_ids": ["123"],
                "requested_count": 1,
            },
            "creator",
        ),
        (
            {
                "platform": "bili",
                "mode": "comments",
                "parent_content_id": "BV1xx",
                "requested_comment_count": 10,
            },
            "comments",
        ),
        (
            {
                "platform": "bili",
                "mode": "sub_comments",
                "parent_content_id": "BV1xx",
                "parent_comment_id": "456",
                "requested_sub_comment_count": 5,
            },
            "sub_comments",
        ),
    ],
)
def test_create_accepts_each_task_mode(
    client: TestClient,
    payload: dict[str, object],
    expected_mode: str,
) -> None:
    response = client.post("/api/crawler/tasks", json=payload)

    assert response.status_code == 201
    task = response.json()
    assert task["mode"] == expected_mode
    assert task["crawler_type"] == expected_mode
    assert task["keywords"] == payload.get("keywords")


@pytest.mark.parametrize(
    "payload",
    [
        {"platform": "bili", "mode": "search", "requested_count": 1},
        {
            "platform": "bili",
            "mode": "detail",
            "keywords": "wrong",
            "target_ids": ["1"],
        },
        {
            "platform": "bili",
            "mode": "detail",
            "target_ids": ["1", "2"],
            "requested_count": 1,
        },
        {"platform": "bili", "mode": "creator", "requested_count": 1},
        {
            "platform": "bili",
            "mode": "creator",
            "creator_ids": ["1", "2"],
            "requested_count": 1,
        },
        {
            "platform": "bili",
            "mode": "comments",
            "target_ids": ["1", "2"],
            "requested_comment_count": 10,
        },
        {
            "platform": "bili",
            "mode": "comments",
            "target_ids": ["1"],
            "requested_comment_count": 11,
        },
        {
            "platform": "bili",
            "mode": "sub_comments",
            "target_ids": ["1"],
            "requested_sub_comment_count": 5,
        },
        {
            "platform": "bili",
            "mode": "sub_comments",
            "target_ids": ["1"],
            "parent_comment_id": "2",
            "requested_sub_comment_count": 6,
        },
    ],
)
def test_create_rejects_invalid_mode_field_combinations(
    client: TestClient,
    payload: dict[str, object],
) -> None:
    response = client.post("/api/crawler/tasks", json=payload)

    assert response.status_code == 422


def test_mode_and_legacy_crawler_type_must_match(client: TestClient) -> None:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "mode": "detail",
            "crawler_type": "search",
            "target_ids": ["1"],
        },
    )

    assert response.status_code == 422


def test_platform_adapter_rejects_deferred_xiaohongshu_detail(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "xhs",
            "mode": "detail",
            "target_ids": ["note-1"],
        },
    )

    assert response.status_code == 409
    assert "deferred_login_required" in response.json()["detail"]


def test_platform_adapter_requires_full_zhihu_content_url(
    test_settings: Settings,
) -> None:
    with enabled_client(test_settings) as client:
        response = client.post(
            "/api/crawler/tasks",
            json={
                "platform": "zhihu",
                "mode": "detail",
                "target_ids": ["123"],
                "requested_count": 1,
            },
        )

    assert response.status_code == 422
    assert "requires a full target URL" in response.json()["detail"]


def test_platform_adapter_rejects_target_url_credentials(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "mode": "detail",
            "target_urls": ["https://user:password@example.test/content"],
            "requested_count": 1,
        },
    )

    assert response.status_code == 422
    assert "HTTP or HTTPS" in response.json()["detail"]


def test_platform_adapter_rejects_non_platform_target_hostname(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "mode": "detail",
            "target_urls": ["https://example.test/video/BV1xx"],
            "requested_count": 1,
        },
    )

    assert response.status_code == 422
    assert "approved platform hostname" in response.json()["detail"]


def test_task_model_rejects_url_smuggled_through_identifier_field(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "mode": "detail",
            "target_ids": ["https://user:password@example.test/content"],
            "requested_count": 1,
        },
    )

    assert response.status_code == 422
    assert "URL field" in response.text


def test_deferred_mode_is_visible_but_not_submittable(
    test_settings: Settings,
) -> None:
    with enabled_client(test_settings) as client:
        response = client.post(
            "/api/crawler/tasks",
            json={
                "platform": "ks",
                "mode": "search",
                "keywords": "AI",
                "requested_count": 3,
            },
        )

    assert response.status_code == 409
    assert "deferred_upstream_breakage" in response.json()["detail"]


def test_task_response_redacts_sensitive_url_query_values(
    client: TestClient,
) -> None:
    response = client.post(
        "/api/crawler/tasks",
        json={
            "platform": "bili",
            "mode": "detail",
            "target_urls": [
                (
                    "https://www.bilibili.com/video/BV1xx"
                    "?access_token=secret&spm_id_from=pc_feed"
                )
            ],
            "requested_count": 1,
        },
    )

    assert response.status_code == 201
    target_url = response.json()["target_urls"][0]
    assert "secret" not in target_url
    assert "access_token" not in target_url
    assert "spm_id_from=pc_feed" in target_url
