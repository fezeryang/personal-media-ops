from __future__ import annotations

import json
from pathlib import Path

from app.crawler.results import TaskEntityBatch
from app.db import connect_database
from app.models.library import NormalizedContent
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.library import LibraryRepository
from app.repositories.research import ResearchTaskRepository
from app.services.ai.context_compactor import compact_research_context
from tests.test_research_runtime import create_task, setup_database


def _ingest_content(
    database: Path,
    tmp_path: Path,
    *,
    platform: str,
    source_content_id: str,
    title: str,
    description: str,
) -> str:
    crawler = CrawlerTaskRepository(database)
    crawler_task = crawler.create(
        platform=platform,
        crawler_type="search",
        keywords="phase 8c",
        login_type="qrcode",
        requested_count=1,
        output_dir=str(tmp_path / "output" / source_content_id),
        log_path=str(tmp_path / "logs" / f"{source_content_id}.log"),
        qrcode_path=str(tmp_path / "qrcodes" / f"{source_content_id}.png"),
    )
    assert crawler.claim_next() is not None
    LibraryRepository(database).ingest_task(
        task_id=str(crawler_task["id"]),
        batch=TaskEntityBatch(
            contents=[
                NormalizedContent(
                    platform=platform,
                    source_content_id=source_content_id,
                    content_type="post",
                    title=title,
                    description=description,
                    source_url=f"https://example.test/{source_content_id}",
                    cover_url=None,
                    author_source_id=f"author-{source_content_id}",
                    author_name="Author",
                    published_at=None,
                    source_keyword="phase 8c",
                    view_count=1,
                    like_count=1,
                    favorite_count=0,
                    comment_count=0,
                    share_count=0,
                    raw_payload={},
                )
            ],
            creators=[],
            comments=[],
            actual_count=1,
        ),
    )
    with connect_database(database) as connection:
        row = connection.execute(
            "SELECT id FROM library_contents WHERE platform = ? AND source_content_id = ?",
            (platform, source_content_id),
        ).fetchone()
    assert row is not None
    return str(row[0])


def test_context_compactor_preserves_provenance_and_reports_loading_counts() -> None:
    compacted, stats = compact_research_context(
        objective="Compare personal AI workbench products",
        coverage={"target_platform_count": 3},
        entities=[{"canonical_name": "WorkBuddy"}],
        queries=[
            {
                "id": "query-1",
                "query": "WorkBuddy 深度分析",
                "platform": "zhihu",
                "lifecycle_status": "completed",
                "source_content_id": "content-1",
            }
        ],
        findings=[
            {
                "id": "finding-1",
                "kind": "fact",
                "statement": "A bounded fact",
                "evidence": [
                    {
                        "content_id": "content-1",
                        "source_url": "https://example.test/content-1",
                        "platform": "zhihu",
                        "published_at": "2026-08-01T00:00:00Z",
                        "support_type": "direct",
                    }
                ],
            }
        ],
        candidate_contents=[{"id": "content-1"}, {"id": "content-2"}],
        loaded_content_ids=["content-1"],
        unresolved_questions=["真实付费意愿"],
        budget={"max_total_tokens": 5000},
    )

    assert stats == {
        "candidate_query_count": 1,
        "candidate_content_count": 2,
        "loaded_full_content_count": 1,
        "final_evidence_count": 1,
        "preserved_content_count": 1,
        "compressed_branch_count": 0,
    }
    assert compacted["objective"] == "Compare personal AI workbench products"
    assert compacted["preserved_content_ids"] == ["content-1"]
    evidence = compacted["high_value_evidence"][0]["evidence"]  # type: ignore[index]
    assert evidence[0]["source_url"] == "https://example.test/content-1"  # type: ignore[index]
    assert evidence[0]["platform"] == "zhihu"  # type: ignore[index]
    assert evidence[0]["published_at"] == "2026-08-01T00:00:00Z"  # type: ignore[index]
    assert evidence[0]["evidence_role"] == "direct"  # type: ignore[index]


def test_entity_platform_coverage_counts_distinct_platforms(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id, platforms=["bili", "zhihu"])
    task_id = str(task["id"])

    first = repository.upsert_entity_coverage(
        task_id,
        "WorkBuddy",
        platform="bili",
        query_count_delta=1,
        evidence_count_delta=1,
    )
    second = repository.upsert_entity_coverage(
        task_id,
        "WorkBuddy",
        platform="bili",
        query_count_delta=1,
        evidence_count_delta=1,
    )
    third = repository.upsert_entity_coverage(
        task_id,
        "WorkBuddy",
        platform="zhihu",
        query_count_delta=1,
        evidence_count_delta=1,
    )

    assert first["entity_platform_count"] == 1
    assert second["entity_platform_count"] == 1
    assert third["entity_platform_count"] == 2
    detail = repository.get_for_runtime(task_id, detail=True)
    assert detail is not None
    assert detail["entity_coverage"][0]["entity_platform_count"] == 2  # type: ignore[index]


def test_occurrences_aggregate_repeated_discovery_and_preserve_sources(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    content_id = _ingest_content(
        database,
        tmp_path,
        platform="bili",
        source_content_id="occurrence-1",
        title="A durable evidence item",
        description="A complete description",
    )
    query_one = repository.create_query(
        task_id=str(task["id"]),
        query="durable evidence one",
        normalized_query="durable evidence one",
        query_type="product",
        platform="bili",
        source_type="user_goal",
        source_content_id=None,
        source_finding_id=None,
        parent_query_id=None,
        generation_reason="test source one",
        specificity_score=0.8,
        novelty_score=1.0,
        noise_risk_score=0.1,
    )
    query_two = repository.create_query(
        task_id=str(task["id"]),
        query="durable evidence two",
        normalized_query="durable evidence two",
        query_type="product",
        platform="bili",
        source_type="user_goal",
        source_content_id=None,
        source_finding_id=None,
        parent_query_id=None,
        generation_reason="test source two",
        specificity_score=0.8,
        novelty_score=1.0,
        noise_risk_score=0.1,
    )
    with connect_database(database) as connection:
        crawler_id = str(
            connection.execute(
                "SELECT id FROM crawler_tasks ORDER BY created_at DESC, id DESC LIMIT 1"
            ).fetchone()[0]
        )

    repository.record_evidence_occurrences(
        task_id=str(task["id"]),
        content_ids=[content_id],
        query_id=str(query_one["id"]),
        crawler_task_id=crawler_id,
    )
    repository.record_evidence_occurrences(
        task_id=str(task["id"]),
        content_ids=[content_id],
        query_id=str(query_two["id"]),
        crawler_task_id=crawler_id,
    )
    with connect_database(database) as connection:
        row = connection.execute(
            "SELECT occurrence_count, source_query_ids, source_crawler_task_ids "
            "FROM evidence_occurrences WHERE research_task_id = ? AND content_id = ?",
            (str(task["id"]), content_id),
        ).fetchone()
    assert row is not None
    assert row[0] == 2
    assert json.loads(row[1]) == [str(query_one["id"]), str(query_two["id"])]
    assert json.loads(row[2]) == [crawler_id]


def test_repost_decision_is_not_counted_as_independent_evidence(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id, platforms=["bili", "zhihu"])
    first = _ingest_content(
        database,
        tmp_path,
        platform="bili",
        source_content_id="repost-1",
        title="WorkBuddy product experience",
        description="The same detailed user experience appears on both platforms.",
    )
    second = _ingest_content(
        database,
        tmp_path,
        platform="zhihu",
        source_content_id="repost-2",
        title="WorkBuddy product experience",
        description="The same detailed user experience appears on both platforms.",
    )
    repository.record_content_decision(
        task_id=str(task["id"]), content_id=first, decision="candidate"
    )
    decision = repository.record_content_decision(
        task_id=str(task["id"]), content_id=second, decision="candidate"
    )
    assert decision["is_repost"] is True
    assert decision["source_independence"] == "repost"

    repository.mark_content_adopted(str(task["id"]), [first, second])
    assert repository.quality_summary(str(task["id"]))["repost_count"] == 1
