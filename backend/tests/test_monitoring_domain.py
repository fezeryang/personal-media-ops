from __future__ import annotations

from app.services.monitoring.attention import attention_for_change
from app.services.monitoring.change_detection import (
    compare_baseline,
    memory_update_for_change,
)


def _content(
    content_id: str,
    title: str,
    *,
    url: str = "https://example.test/default",
    platform: str = "bili",
    author: str = "author-a",
) -> dict[str, object]:
    return {
        "id": content_id,
        "title": title,
        "description": "真实用户反馈与产品变化",
        "source_url": url,
        "platform": platform,
        "author_name": author,
        "published_at": "2026-08-04T00:00:00Z",
    }


def test_first_run_establishes_baseline_without_calling_everything_new() -> None:
    result = compare_baseline(
        goal="持续关注个人 AI 工具的功能变化",
        baseline=None,
        current_contents=[_content("c1", "Tool A release")],
    )
    assert result["outcome"] == "baseline_created"
    assert result["changes"] == []
    assert result["baseline"]["content_ids"] == ["c1"]


def test_change_detection_filters_known_content_and_groups_reposts() -> None:
    result = compare_baseline(
        goal="持续关注个人 AI 工具的功能变化",
        baseline={"content_ids": ["known"], "last_run_at": "2026-08-01T00:00:00Z"},
        current_contents=[
            _content("known", "Known item", url="https://example.test/known"),
            _content("new-a", "Tool A has a major update", url="https://example.test/update"),
            _content("new-b", "Tool A has a major update", url="https://example.test/update", platform="zhihu", author="author-b"),
        ],
    )
    assert result["outcome"] == "meaningful_change"
    change = result["changes"][0]
    assert change["change_type"] in {"new_feature", "updated_fact", "new_claim"}
    assert change["independent_source_count"] == 2
    assert change["suspected_repost_count"] == 1
    assert change["evidence"][0]["content_id"] == "new-a"


def test_no_meaningful_change_is_silent_and_memory_update_is_reversible() -> None:
    result = compare_baseline(
        goal="持续关注个人 AI 工具的功能变化",
        baseline={"content_ids": ["known"], "last_run_at": "2026-08-01T00:00:00Z"},
        current_contents=[_content("known", "Known item", url="https://example.test/known")],
    )
    assert result["outcome"] == "no_meaningful_change"
    assert result["changes"] == []
    assert attention_for_change({"relevance_score": 0.2, "novelty_score": 0.2})["level"] == "silent_memory"
    update = memory_update_for_change(
        {"fingerprint": "fp-1", "title": "Tool A update", "evidence": [{"content_id": "new-a"}]},
        old_value={"status": "old"},
        new_value={"status": "new"},
    )
    assert update["old_value"] == {"status": "old"}
    assert update["new_value"] == {"status": "new"}
    assert update["evidence_ids"] == ["new-a"]
