import sqlite3

from fastapi.testclient import TestClient


def seed_content(client: TestClient, *, content_id: str = "content-1") -> str:
    now = "2026-07-28T00:00:00Z"
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
                ?, 'bili', ?, 'video', 'Agent workflow', 'safe text',
                'https://www.bilibili.com/video/BV1', NULL, NULL, NULL,
                '2026-07-28T00:00:00Z', ?, ?, 'AI Agent', 100, 10, NULL,
                1, NULL, '{}', ?, ?, 0
            )
            """,
            (content_id, f"source-{content_id}", now, now, now, now),
        )
    return content_id


def test_tags_favorite_and_ordered_collection(client: TestClient) -> None:
    content_id = seed_content(client)
    tag = client.post("/api/library/tags", json={"name": "研究"}).json()
    assert client.post(
        f"/api/library/contents/{content_id}/tags/{tag['id']}"
    ).status_code == 204

    renamed = client.patch(
        f"/api/library/tags/{tag['id']}",
        json={"name": "深度研究"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name"] == "深度研究"

    favorite = client.patch(
        f"/api/library/contents/{content_id}/favorite",
        json={"is_favorite": True},
    )
    assert favorite.status_code == 200
    assert favorite.json()["is_favorite"] is True

    filtered = client.get(
        "/api/library/contents",
        params={"tag_id": tag["id"], "is_favorite": True},
    )
    assert [item["id"] for item in filtered.json()["items"]] == [content_id]

    collection = client.post(
        "/api/library/collections",
        json={"name": "AI Agent", "description": "真实研究资料"},
    ).json()
    added = client.post(
        f"/api/library/collections/{collection['id']}/items",
        json={"content_id": content_id, "position": 0},
    )
    assert added.status_code == 201
    detail = client.get(f"/api/library/collections/{collection['id']}")
    assert detail.json()["content_count"] == 1
    assert detail.json()["items"][0]["content"]["id"] == content_id
    assert detail.json()["items"][0]["position"] == 0

    in_use = client.delete(f"/api/library/tags/{tag['id']}")
    assert in_use.status_code == 409
    assert client.delete(
        f"/api/library/contents/{content_id}/tags/{tag['id']}"
    ).status_code == 204
    assert client.delete(f"/api/library/tags/{tag['id']}").status_code == 204


def test_tag_and_collection_names_are_owner_unique(client: TestClient) -> None:
    assert client.post("/api/library/tags", json={"name": "竞品"}).status_code == 201
    assert client.post("/api/library/tags", json={"name": "竞品"}).status_code == 409
    payload = {"name": "竞品观察", "description": None}
    assert client.post("/api/library/collections", json=payload).status_code == 201
    assert client.post("/api/library/collections", json=payload).status_code == 409
