from pathlib import Path

import pytest

from app.crawler.adapters import _integer
from app.crawler.registry import (
    PlatformDisabledError,
    UnsupportedPlatformError,
    platform_registry,
)


def test_registry_reports_truthful_platform_capabilities() -> None:
    capabilities = platform_registry.list_capabilities(("bili",))

    assert [item.platform for item in capabilities] == ["bili", "xhs", "dy"]
    assert capabilities[0].enabled is True
    assert capabilities[0].verification_status == "verified"
    assert capabilities[1].enabled is False
    assert capabilities[1].verification_status == "verified"
    assert capabilities[2].enabled is False
    assert capabilities[2].verification_status == "code_ready"
    assert all(item.crawler_types[0].value == "search" for item in capabilities)
    assert all(item.login_types[0].value == "qrcode" for item in capabilities)
    assert all(item.requested_count.maximum == 20 for item in capabilities)
    assert all(item.supports_comments is False for item in capabilities)


def test_registry_rejects_unknown_or_disabled_platform() -> None:
    with pytest.raises(UnsupportedPlatformError):
        platform_registry.require_enabled("youtube", ("bili",))
    with pytest.raises(PlatformDisabledError):
        platform_registry.require_enabled("xhs", ("bili",))


@pytest.mark.parametrize("platform", ["bili", "xhs", "dy"])
def test_adapter_builds_fixed_safe_runner_arguments(platform: str) -> None:
    adapter = platform_registry.get(platform)

    arguments = adapter.build_runner_arguments(
        keywords="--not-an-option",
        requested_count=5,
        output_dir=Path("/fixed/output"),
        qrcode_path=Path("/fixed/qrcode.png"),
    )

    assert arguments[:2] == ["--platform", platform]
    assert "--keywords=--not-an-option" in arguments
    assert arguments[arguments.index("--max-concurrency-num") + 1] == "1"
    assert arguments[arguments.index("--enable-comments") + 1] == "false"
    assert arguments[arguments.index("--enable-sub-comments") + 1] == "false"
    assert "--enable-proxy" not in arguments


@pytest.mark.parametrize(
    ("platform", "expected"),
    [("bili", "true"), ("xhs", "true"), ("dy", "false")],
)
def test_adapter_requests_headful_browser_only_for_douyin(
    platform: str,
    expected: str,
) -> None:
    adapter = platform_registry.get(platform)

    arguments = adapter.build_runner_arguments(
        keywords="AI",
        requested_count=5,
        output_dir=Path("/fixed/output"),
        qrcode_path=Path("/fixed/qrcode.png"),
    )

    assert adapter.headless_browser is (expected == "true")
    assert arguments[arguments.index("--headless") + 1] == expected


@pytest.mark.parametrize(
    ("platform", "raw", "expected"),
    [
        (
            "bili",
            {
                "video_id": "123",
                "video_type": "video",
                "title": "Bilibili title",
                "desc": "Bilibili description",
                "nickname": "UP",
                "video_url": "https://www.bilibili.com/video/av123",
                "video_cover_url": "https://example.test/bili.jpg",
                "video_play_count": "10",
                "liked_count": "9",
                "video_favorite_count": "8",
                "video_comment": "7",
                "video_share_count": "6",
                "create_time": 1700000000,
                "source_keyword": "AI",
            },
            {
                "content_id": "123",
                "content_url": "https://www.bilibili.com/video/av123",
                "cover_url": "https://example.test/bili.jpg",
                "play_count": 10,
            },
        ),
        (
            "xhs",
            {
                "note_id": "note-1",
                "type": "normal",
                "title": "XHS title",
                "desc": "XHS description",
                "nickname": "Author",
                "note_url": "https://www.xiaohongshu.com/explore/note-1",
                "image_list": "https://example.test/xhs.jpg,https://example.test/2.jpg",
                "liked_count": "9",
                "collected_count": "8",
                "comment_count": "7",
                "share_count": "6",
                "time": 1700000000000,
                "source_keyword": "AI",
            },
            {
                "content_id": "note-1",
                "content_url": "https://www.xiaohongshu.com/explore/note-1",
                "cover_url": "https://example.test/xhs.jpg",
                "play_count": None,
            },
        ),
        (
            "dy",
            {
                "aweme_id": "aweme-1",
                "aweme_type": "0",
                "title": "Douyin title",
                "desc": "Douyin description",
                "nickname": "Creator",
                "aweme_url": "https://www.douyin.com/video/aweme-1",
                "cover_url": "https://example.test/dy.jpg",
                "liked_count": "9",
                "collected_count": "8",
                "comment_count": "7",
                "share_count": "6",
                "create_time": 1700000000,
                "source_keyword": "AI",
            },
            {
                "content_id": "aweme-1",
                "content_url": "https://www.douyin.com/video/aweme-1",
                "cover_url": "https://example.test/dy.jpg",
                "play_count": None,
            },
        ),
    ],
)
def test_adapters_normalize_platform_results(
    platform: str,
    raw: dict[str, object],
    expected: dict[str, object],
) -> None:
    result = platform_registry.get(platform).normalize_result(raw)

    assert result.platform == platform
    assert result.title
    assert result.metrics.like_count == 9
    assert result.metrics.favorite_count == 8
    assert result.metrics.comment_count == 7
    assert result.metrics.share_count == 6
    for field, value in expected.items():
        if field == "play_count":
            assert result.metrics.play_count == value
        else:
            assert getattr(result, field) == value


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("399", 399),
        ("0", 0),
        (" 399 ", 399),
        ("１２３", 123),
        ("1544", 1544),
        ("1,544", 1544),
        ("5.7万", 57000),
        ("2.1万", 21000),
        ("3亿", 300000000),
        ("1.2w", 12000),
        ("1.2W", 12000),
        ("1000+", 1000),
        ("1.5万+", 15000),
        # Sub-integer remainders of abbreviated counts truncate toward zero.
        ("1.0000001万", 10000),
        ("0.0万", 0),
        (7, 7),
        (0, 0),
        (7.0, 7),
        (0.0, 0),
        (7.5, None),
        (True, None),
        (False, None),
        (-3, None),
        (-1.0, None),
        ("-5", None),
        ("-5.7万", None),
        ("5.7", None),
        ("赞", None),
        ("", None),
        ("   ", None),
        ("-", None),
        ("万", None),
        ("+", None),
        ("²", None),
        ("NaN", None),
        ("Infinity", None),
        ("NaN万", None),
        ("Infinity万", None),
        # Implausible magnitudes are rejected before any Decimal arithmetic:
        # multiplying them would overflow the decimal context or materialise a
        # multi-hundred-megabyte int from untrusted crawled text.
        ("1E+9999999万", None),
        ("10000000000000万", None),
        ("999999999999万", 9999999999990000),
        ("1..5万", None),
        ("1_2万", None),
        ("1e3万", None),
        (".5万", None),
        ("1.万", None),
        ("赞万", None),
        (float("nan"), None),
        (float("inf"), None),
        (None, None),
    ],
)
def test_integer_parses_plain_and_abbreviated_counts(
    value: object,
    expected: int | None,
) -> None:
    assert _integer(value) == expected


def test_integer_rejects_oversized_plain_numeric_text() -> None:
    assert _integer("9" * 5000) is None


def test_xhs_adapter_normalizes_abbreviated_metric_counts() -> None:
    raw = {
        "note_id": "note-prod-1",
        "type": "normal",
        "title": "Production note",
        "desc": "Production description",
        "nickname": "Author",
        "note_url": "https://www.xiaohongshu.com/explore/note-prod-1",
        "image_list": "https://example.test/a.jpg,https://example.test/b.jpg",
        "time": 1753500000000,
        "source_keyword": "AI",
        "liked_count": "5.7万",
        "collected_count": "2.1万",
        "comment_count": "399",
        "share_count": "1544",
    }

    result = platform_registry.get("xhs").normalize_result(raw)

    assert result.platform == "xhs"
    assert result.content_id == "note-prod-1"
    assert result.published_at == 1753500000000
    assert result.metrics.like_count == 57000
    assert result.metrics.favorite_count == 21000
    assert result.metrics.comment_count == 399
    assert result.metrics.share_count == 1544


def test_adapter_rejects_unsafe_result_urls() -> None:
    result = platform_registry.get("bili").normalize_result(
        {
            "video_id": "123",
            "video_url": "javascript:alert(1)",
            "video_cover_url": "data:text/html,bad",
        }
    )

    assert result.content_url is None
    assert result.cover_url is None


def _write_result_file(task_dir: Path, storage_directory: str, name: str) -> Path:
    jsonl_dir = task_dir / storage_directory / "jsonl"
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    result_file = jsonl_dir / name
    result_file.write_text('{"video_id": "1"}\n', encoding="utf-8")
    return result_file


@pytest.mark.parametrize(
    ("platform", "storage_directory"),
    [
        ("bili", "bili"),
        ("bili", "bilibili"),
        ("dy", "dy"),
        ("dy", "douyin"),
        ("xhs", "xhs"),
    ],
)
def test_content_result_files_supports_each_storage_layout(
    tmp_path: Path,
    platform: str,
    storage_directory: str,
) -> None:
    result_file = _write_result_file(
        tmp_path, storage_directory, "search_contents_2026-07-26.jsonl"
    )

    found = platform_registry.get(platform).content_result_files(tmp_path)

    assert found == [result_file.resolve()]


def test_content_result_files_merges_candidates_sorted_without_duplicates(
    tmp_path: Path,
) -> None:
    short_file = _write_result_file(
        tmp_path, "bili", "search_contents_b.jsonl"
    )
    long_file = _write_result_file(
        tmp_path, "bilibili", "search_contents_a.jsonl"
    )

    found = platform_registry.get("bili").content_result_files(tmp_path)

    assert found == sorted([short_file.resolve(), long_file.resolve()])


def test_content_result_files_deduplicates_linked_storage_directories(
    tmp_path: Path,
) -> None:
    result_file = _write_result_file(
        tmp_path, "bili", "search_contents_test.jsonl"
    )
    (tmp_path / "bilibili").symlink_to(tmp_path / "bili")

    found = platform_registry.get("bili").content_result_files(tmp_path)

    assert found == [result_file.resolve()]


def test_content_result_files_rejects_paths_escaping_task_directory(
    tmp_path: Path,
) -> None:
    task_dir = tmp_path / "task"
    outside = tmp_path / "outside"
    _write_result_file(outside, "bili", "search_contents_test.jsonl")
    (task_dir / "bili").mkdir(parents=True)
    (task_dir / "bili" / "jsonl").symlink_to(outside / "bili" / "jsonl")

    with pytest.raises(ValueError):
        platform_registry.get("bili").content_result_files(task_dir)


@pytest.mark.parametrize("platform", ["bili", "xhs", "dy"])
def test_login_success_detection_ignores_qr_save_line(platform: str) -> None:
    adapter = platform_registry.get(platform)

    assert (
        adapter.is_login_success("[MediaOps] QR code saved: /fixed/code.png") is False
    )
    assert adapter.is_login_success("Login successful then wait for 5 seconds") is True
