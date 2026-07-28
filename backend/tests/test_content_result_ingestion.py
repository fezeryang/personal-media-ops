import json
from pathlib import Path

import pytest

from app.crawler.registry import platform_registry
from app.crawler.results import CrawlerResultDataError, parse_task_entities


def write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


def test_parse_content_creator_and_comment_outputs(tmp_path: Path) -> None:
    adapter = platform_registry.get("bili")
    root = tmp_path / "bilibili" / "jsonl"
    write_jsonl(
        root / "detail_contents_test.jsonl",
        [
            {
                "video_id": "BV1",
                "title": "Title",
                "mid": "42",
                "nickname": "Creator",
                "video_comment": "1",
            }
        ],
    )
    write_jsonl(
        root / "creator_creators_test.jsonl",
        [
            {
                "_mediaops_source_creator_id": "42",
                "nickname": "Creator",
                "fans": "2万",
            }
        ],
    )
    write_jsonl(
        root / "detail_comments_test.jsonl",
        [
            {
                "comment_id": "100",
                "video_id": "BV1",
                "content": "root",
            },
            {
                "comment_id": "101",
                "video_id": "BV1",
                "content": "reply",
                "parent_comment_id": "100",
            },
        ],
    )

    batch = parse_task_entities(
        adapter=adapter,
        task_dir=tmp_path,
        mode="comments",
        requested_count=1,
        requested_comment_count=1,
        requested_sub_comment_count=0,
    )

    assert batch.actual_count == 1
    assert batch.contents[0].author_source_id == "42"
    assert batch.creators[0].follower_count == 20_000
    assert batch.comments[0].source_comment_id == "100"


def test_comments_can_succeed_empty_only_with_verified_zero_count(
    tmp_path: Path,
) -> None:
    adapter = platform_registry.get("bili")
    write_jsonl(
        tmp_path / "bilibili" / "jsonl" / "detail_contents_test.jsonl",
        [{"video_id": "BV1", "video_comment": 0}],
    )

    batch = parse_task_entities(
        adapter=adapter,
        task_dir=tmp_path,
        mode="comments",
        requested_count=1,
        requested_comment_count=10,
        requested_sub_comment_count=0,
    )

    assert batch.actual_count == 0
    assert batch.legal_empty is True


@pytest.mark.parametrize("mode", ["search", "detail", "creator", "comments", "sub_comments"])
def test_unexplained_empty_outputs_fail_closed(
    tmp_path: Path,
    mode: str,
) -> None:
    with pytest.raises(CrawlerResultDataError):
        parse_task_entities(
            adapter=platform_registry.get("bili"),
            task_dir=tmp_path,
            mode=mode,
            requested_count=1,
            requested_comment_count=1,
            requested_sub_comment_count=1,
        )


def test_invalid_jsonl_fails_closed(tmp_path: Path) -> None:
    path = tmp_path / "bilibili" / "jsonl" / "search_contents_test.jsonl"
    path.parent.mkdir(parents=True)
    path.write_text("{not json}\n", encoding="utf-8")

    with pytest.raises(CrawlerResultDataError, match="invalid JSONL"):
        parse_task_entities(
            adapter=platform_registry.get("bili"),
            task_dir=tmp_path,
            mode="search",
            requested_count=1,
            requested_comment_count=0,
            requested_sub_comment_count=0,
        )
