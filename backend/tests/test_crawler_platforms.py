from pathlib import Path

import pytest

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
    assert capabilities[1].verification_status == "code_ready"
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


@pytest.mark.parametrize("platform", ["bili", "xhs", "dy"])
def test_login_success_detection_ignores_qr_save_line(platform: str) -> None:
    adapter = platform_registry.get(platform)

    assert (
        adapter.is_login_success("[MediaOps] QR code saved: /fixed/code.png") is False
    )
    assert adapter.is_login_success("Login successful then wait for 5 seconds") is True
