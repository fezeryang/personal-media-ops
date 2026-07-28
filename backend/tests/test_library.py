import sqlite3

from fastapi.testclient import TestClient

from app.crawler.results import TaskEntityBatch
from app.models.library import (
    NormalizedComment,
    NormalizedContent,
    NormalizedCreator,
)
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.library import LibraryRepository


def seed_active_task(
    repository: CrawlerTaskRepository,
    *,
    task_id: str,
) -> None:
    repository.create(
        task_id=task_id,
        platform="bili",
        crawler_type="search",
        keywords="AI Agent",
        login_type="qrcode",
        requested_count=1,
        output_dir=f"/output/{task_id}",
        log_path=f"/log/{task_id}",
        qrcode_path=f"/qrcode/{task_id}",
    )
    claimed = repository.claim_next()
    assert claimed is not None
    assert claimed["id"] == task_id


def entity_batch(
    *,
    title: str = "First title",
    like_count: int | None = 9,
) -> TaskEntityBatch:
    return TaskEntityBatch(
        contents=[
            NormalizedContent(
                platform="bili",
                source_content_id="BV1xx",
                content_type="video",
                title=title,
                description="<script>alert(1)</script> useful text",
                source_url="https://www.bilibili.com/video/BV1xx",
                cover_url=None,
                author_source_id="42",
                author_name="Creator",
                published_at=1_700_000_000,
                source_keyword="AI Agent",
                view_count=None,
                like_count=like_count,
                favorite_count=None,
                comment_count=1,
                share_count=None,
                raw_payload={"secret_debug_value": "<b>raw</b>"},
            )
        ],
        creators=[
            NormalizedCreator(
                platform="bili",
                source_creator_id="42",
                display_name="Creator",
                profile_url="https://space.bilibili.com/42",
                avatar_url=None,
                description=None,
                follower_count=None,
                following_count=None,
                content_count=None,
                raw_payload={"creator_debug": True},
            )
        ],
        comments=[
            NormalizedComment(
                platform="bili",
                source_comment_id="comment-1",
                source_content_id="BV1xx",
                parent_comment_id=None,
                author_source_id="84",
                author_name="Commenter",
                body="<img src=x onerror=alert(1)>plain",
                like_count=None,
                reply_count=0,
                published_at=1_700_000_001,
                raw_payload={"comment_debug": True},
            )
        ],
        actual_count=1,
    )


def test_library_ingestion_is_idempotent_and_preserves_provenance(
    repository: CrawlerTaskRepository,
) -> None:
    library = LibraryRepository(repository.database_path)
    seed_active_task(repository, task_id="task-one")
    first = library.ingest_task(task_id="task-one", batch=entity_batch())
    initial = library.list_contents()
    initial_content = initial["items"][0]
    initial_first_collected = initial_content["first_collected_at"]

    seed_active_task(repository, task_id="task-two")
    second = library.ingest_task(
        task_id="task-two",
        batch=entity_batch(title="Updated title", like_count=None),
    )

    assert first == {"contents": 1, "creators": 1, "comments": 1}
    assert second == first
    assert library.counts() == {"contents": 1, "creators": 1, "comments": 1}
    content = library.list_contents()["items"][0]
    assert content["title"] == "Updated title"
    assert content["like_count"] == 9
    assert content["first_collected_at"] == initial_first_collected
    detail = library.get_content(str(content["id"]))
    assert detail is not None
    assert {item["task_id"] for item in detail["tasks"]} == {
        "task-one",
        "task-two",
    }
    assert detail["creator"]["source_creator_id"] == "42"
    assert len(detail["comments"]) == 1


def test_library_ingestion_rolls_back_all_entities_and_task_state(
    repository: CrawlerTaskRepository,
) -> None:
    library = LibraryRepository(repository.database_path)
    seed_active_task(repository, task_id="atomic-task")
    batch = entity_batch()
    batch.contents.append(
        NormalizedContent(
            platform="bili",
            source_content_id="BV-bad-payload",
            content_type="video",
            title="Must roll back",
            description=None,
            source_url=None,
            cover_url=None,
            author_source_id=None,
            author_name=None,
            published_at=None,
            source_keyword=None,
            view_count=None,
            like_count=None,
            favorite_count=None,
            comment_count=None,
            share_count=None,
            raw_payload={"not_json_serializable": object()},
        )
    )

    try:
        library.ingest_task(task_id="atomic-task", batch=batch)
    except TypeError:
        pass
    else:
        raise AssertionError("non-serializable payload unexpectedly ingested")

    assert library.counts() == {"contents": 0, "creators": 0, "comments": 0}
    task = repository.get("atomic-task")
    assert task is not None
    assert task["status"] == "running"
    assert task["actual_count"] == 0


def test_library_unique_constraints_are_platform_scoped(
    repository: CrawlerTaskRepository,
) -> None:
    with sqlite3.connect(repository.database_path) as connection:
        columns = (
            "id, platform, source_content_id, content_type, "
            "first_collected_at, last_collected_at, raw_payload, "
            "created_at, updated_at"
        )
        values = "?, ?, ?, 'video', ?, ?, '{}', ?, ?"
        timestamps = ("2026-07-28T00:00:00Z",) * 4
        connection.execute(
            f"INSERT INTO library_contents ({columns}) VALUES ({values})",
            ("one", "bili", "same-id", *timestamps),
        )
        connection.execute(
            f"INSERT INTO library_contents ({columns}) VALUES ({values})",
            ("two", "xhs", "same-id", *timestamps),
        )

        try:
            connection.execute(
                f"INSERT INTO library_contents ({columns}) VALUES ({values})",
                ("three", "bili", "same-id", *timestamps),
            )
        except sqlite3.IntegrityError:
            pass
        else:
            raise AssertionError("same-platform duplicate source ID was accepted")


def test_library_api_filters_paginates_and_omits_raw_by_default(
    client: TestClient,
) -> None:
    repository = client.app.state.crawler_repository
    library = client.app.state.library_repository
    seed_active_task(repository, task_id="api-task")
    library.ingest_task(task_id="api-task", batch=entity_batch())

    stats = client.get("/api/library/stats")
    listing = client.get(
        "/api/library/contents",
        params={"platform": "bili", "keyword": "Agent", "limit": 1},
    )

    assert stats.status_code == 200
    assert stats.json() == {"contents": 1, "creators": 1, "comments": 1}
    assert listing.status_code == 200
    page = listing.json()
    assert page["limit"] == 1
    assert page["has_more"] is False
    assert "raw_payload" not in page["items"][0]

    content_id = page["items"][0]["id"]
    safe_detail = client.get(f"/api/library/contents/{content_id}")
    raw_detail = client.get(
        f"/api/library/contents/{content_id}",
        params={"include_raw": True},
    )
    assert safe_detail.status_code == 200
    assert safe_detail.json()["raw_payload"] is None
    assert raw_detail.status_code == 200
    assert raw_detail.json()["raw_payload"] == {
        "secret_debug_value": "<b>raw</b>"
    }
    assert "<script>" in safe_detail.json()["description"]

    creator_id = safe_detail.json()["creator"]["id"]
    creator = client.get(f"/api/library/creators/{creator_id}")
    comments = client.get(
        "/api/library/comments",
        params={"platform": "bili", "source_content_id": "BV1xx"},
    )
    assert creator.status_code == 200
    assert creator.json()["raw_payload"] is None
    assert comments.status_code == 200
    assert comments.json()["items"][0]["body"].startswith("<img")


def test_library_api_validates_pagination_and_not_found(
    client: TestClient,
) -> None:
    assert client.get("/api/library/contents", params={"limit": 101}).status_code == 422
    assert (
        client.get(
            "/api/library/contents",
            params={"date_from": "not-a-date"},
        ).status_code
        == 422
    )
    assert client.get("/api/library/contents/missing").status_code == 404
    assert client.get("/api/library/creators/missing").status_code == 404


def test_library_api_normalizes_date_filters_to_utc(
    client: TestClient,
) -> None:
    repository = client.app.state.crawler_repository
    library = client.app.state.library_repository
    seed_active_task(repository, task_id="date-filter-task")
    library.ingest_task(task_id="date-filter-task", batch=entity_batch())

    included = client.get(
        "/api/library/contents",
        params={
            "date_from": "2023-11-14T23:00:00+01:00",
            "date_to": "2023-11-15T00:00:00+01:00",
        },
    )
    excluded = client.get(
        "/api/library/contents",
        params={"date_from": "2023-11-15T00:00:01Z"},
    )

    assert included.status_code == 200
    assert len(included.json()["items"]) == 1
    assert excluded.status_code == 200
    assert excluded.json()["items"] == []
