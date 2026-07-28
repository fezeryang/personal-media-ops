import sqlite3

from fastapi.testclient import TestClient

from tests.test_library_organization import seed_content


def _api_key(client: TestClient, scopes: list[str]) -> tuple[str, str]:
    created = client.post(
        "/api/auth/api-keys",
        json={"name": "Agent test", "scopes": scopes},
    )
    assert created.status_code == 201
    return created.json()["api_key"], created.json()["key"]["id"]


def test_agent_tool_service_and_v1_library_contract(client: TestClient) -> None:
    content_id = seed_content(client)
    key, _ = _api_key(client, ["library:read", "intelligence:read"])
    headers = {"X-API-Key": key}

    search = client.get(
        "/api/v1/library/search",
        params={"q": "Agent", "limit": 10},
        headers=headers,
    )
    assert search.status_code == 200
    assert search.json()["data"][0]["id"] == content_id
    assert search.json()["meta"]["limit"] == 10
    assert "raw_payload" not in search.text
    assert "output_dir" not in search.text

    detail = client.get(
        f"/api/v1/library/contents/{content_id}",
        headers=headers,
    )
    assert detail.status_code == 200
    assert detail.json()["data"]["source"]["platform"] == "bili"
    assert detail.json()["data"]["source"]["source_id"] == "source-content-1"

    missing = client.get(
        "/api/v1/library/contents/missing",
        headers=headers,
    )
    assert missing.status_code == 404
    assert missing.json() == {
        "error": {
            "code": "not_found",
            "message": "Content not found",
        }
    }


def test_agent_api_scope_and_revocation(client: TestClient) -> None:
    key, key_id = _api_key(client, ["library:read"])
    headers = {"X-API-Key": key}

    forbidden = client.get("/api/v1/intelligence/trends", headers=headers)
    assert forbidden.status_code == 403
    assert forbidden.json()["error"]["code"] == "insufficient_scope"
    assert client.get("/api/v1/subscriptions", headers=headers).status_code == 403

    assert client.delete(f"/api/auth/api-keys/{key_id}").status_code == 204
    revoked = client.get("/api/v1/library/search", headers=headers)
    assert revoked.status_code == 401
    assert revoked.json()["error"]["code"] == "authentication_required"


def test_admin_key_can_use_owner_write_apis_but_not_manage_keys(
    client: TestClient,
) -> None:
    key, _ = _api_key(client, ["admin"])
    headers = {"X-API-Key": key}

    tag = client.post(
        "/api/library/tags",
        json={"name": "Admin key test"},
        headers=headers,
    )
    trends = client.post(
        "/api/intelligence/trends/generate",
        json={
            "window_end": "2026-07-29T00:00:00Z",
            "window_hours": 24,
        },
        headers=headers,
    )

    assert tag.status_code == 201
    assert trends.status_code == 200
    assert client.get("/api/auth/api-keys", headers=headers).status_code == 403


def test_agent_subscription_status_uses_stable_schema(client: TestClient) -> None:
    subscription = client.post(
        "/api/subscriptions",
        json={
            "name": "Agent API",
            "query": "Agent",
            "platforms": [{"platform": "bili", "requested_count": 1}],
            "enabled": False,
            "schedule_type": "manual",
            "schedule_config": {},
            "timezone": "Asia/Shanghai",
        },
    ).json()
    key, _ = _api_key(client, ["subscriptions:read"])
    headers = {"X-API-Key": key}

    listing = client.get("/api/v1/subscriptions", headers=headers)
    detail = client.get(
        f"/api/v1/subscriptions/{subscription['id']}",
        headers=headers,
    )
    assert listing.status_code == 200
    assert listing.json()["data"][0]["id"] == subscription["id"]
    assert detail.status_code == 200
    assert detail.json()["data"]["query"] == "Agent"
    assert "schedule_config" in detail.json()["data"]


def test_agent_api_validation_uses_v1_error_envelope(
    client: TestClient,
) -> None:
    key, _ = _api_key(client, ["library:read"])
    response = client.get(
        "/api/v1/library/search",
        params={"limit": 1000},
        headers={"X-API-Key": key},
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": {
            "code": "invalid_request",
            "message": "Request validation failed",
        }
    }


def test_creator_activity_paginates_at_the_repository_boundary(
    client: TestClient,
) -> None:
    first_id = seed_content(client, content_id="creator-content-1")
    second_id = seed_content(client, content_id="creator-content-2")
    database_path = client.app.state.settings.database_path
    now = "2026-07-28T00:00:00Z"
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
                'agent-creator', 'bili', 'agent-source-creator',
                'Agent creator', 'https://space.bilibili.com/42',
                NULL, NULL, 10, NULL, 2, ?, ?, '{}', ?, ?
            )
            """,
            (now, now, now, now),
        )
        connection.executemany(
            """
            INSERT INTO content_creator_links (
                content_id, creator_id, first_collected_at, last_collected_at
            )
            VALUES (?, 'agent-creator', ?, ?)
            """,
            [(first_id, now, now), (second_id, now, now)],
        )
    key, _ = _api_key(client, ["library:read"])
    headers = {"X-API-Key": key}

    first = client.get(
        "/api/v1/library/creators/agent-creator/activity",
        params={"offset": 0, "limit": 1},
        headers=headers,
    )
    second = client.get(
        "/api/v1/library/creators/agent-creator/activity",
        params={"offset": 1, "limit": 1},
        headers=headers,
    )

    assert first.status_code == 200
    assert first.json()["meta"] == {
        "offset": 0,
        "limit": 1,
        "next_offset": 1,
        "has_more": True,
    }
    assert second.status_code == 200
    assert second.json()["meta"]["has_more"] is False
    assert {
        first.json()["data"][0]["id"],
        second.json()["data"][0]["id"],
    } == {first_id, second_id}
