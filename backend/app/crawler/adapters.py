from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from app.models.crawler_platform import (
    CapabilityOption,
    CrawlerPlatformCapability,
    CrawlerResultItem,
    CrawlerResultMetrics,
    RequestedCountCapability,
)

RawResult = Mapping[str, object]


def _text(value: object) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    normalized = str(value).strip()
    return normalized or None


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 and value.is_integer() else None
    if isinstance(value, str):
        normalized = value.strip().replace(",", "")
        if normalized.isdigit():
            return int(normalized)
    return None


def _safe_http_url(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return text


def _first_comma_value(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text.split(",", 1)[0].strip() or None


@dataclass(frozen=True)
class CrawlerPlatformAdapter(ABC):
    platform: str
    display_name: str
    storage_directory: str
    verification_status: Literal["verified", "code_ready"]

    def capability(self, enabled: bool) -> CrawlerPlatformCapability:
        return CrawlerPlatformCapability(
            platform=self.platform,
            display_name=self.display_name,
            enabled=enabled,
            verification_status=self.verification_status,
            crawler_types=[
                CapabilityOption(value="search", label="关键词搜索"),
            ],
            login_types=[
                CapabilityOption(value="qrcode", label="二维码登录"),
            ],
            requested_count=RequestedCountCapability(
                minimum=1,
                maximum=20,
                default=20,
            ),
            supports_comments=False,
            supports_sub_comments=False,
        )

    def build_runner_arguments(
        self,
        *,
        keywords: str,
        requested_count: int,
        output_dir: Path,
        qrcode_path: Path,
    ) -> list[str]:
        return [
            "--platform",
            self.platform,
            "--crawler-type",
            "search",
            f"--keywords={keywords}",
            "--login-type",
            "qrcode",
            "--requested-count",
            str(requested_count),
            "--output-dir",
            str(output_dir),
            "--qrcode-path",
            str(qrcode_path),
            "--max-concurrency-num",
            "1",
            "--enable-comments",
            "false",
            "--enable-sub-comments",
            "false",
        ]

    def content_result_files(self, task_dir: Path) -> list[Path]:
        jsonl_root = task_dir / self.storage_directory / "jsonl"
        if not jsonl_root.is_dir():
            return []
        task_root = task_dir.resolve()
        candidates: list[Path] = []
        for candidate in sorted(jsonl_root.glob("*_contents_*.jsonl")):
            resolved = candidate.resolve()
            if not resolved.is_relative_to(task_root):
                raise ValueError("result path escapes task output directory")
            if resolved.is_file():
                candidates.append(resolved)
        return candidates

    @staticmethod
    def is_login_success(line: str) -> bool:
        return "login successful" in line.casefold()

    @staticmethod
    def _result(
        *,
        platform: str,
        content_id: object,
        content_type: object,
        title: object,
        description: object,
        author_name: object,
        content_url: object,
        cover_url: object,
        published_at: object,
        source_keyword: object,
        play_count: object = None,
        like_count: object = None,
        favorite_count: object = None,
        comment_count: object = None,
        share_count: object = None,
    ) -> CrawlerResultItem:
        return CrawlerResultItem(
            platform=platform,
            content_id=_text(content_id) or "",
            content_type=_text(content_type) or "unknown",
            title=_text(title) or "",
            description=_text(description),
            author_name=_text(author_name),
            content_url=_safe_http_url(content_url),
            cover_url=_safe_http_url(cover_url),
            published_at=_integer(published_at),
            source_keyword=_text(source_keyword),
            metrics=CrawlerResultMetrics(
                play_count=_integer(play_count),
                like_count=_integer(like_count),
                favorite_count=_integer(favorite_count),
                comment_count=_integer(comment_count),
                share_count=_integer(share_count),
            ),
        )

    @abstractmethod
    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        raise NotImplementedError


class BilibiliAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="bili",
            display_name="哔哩哔哩",
            storage_directory="bilibili",
            verification_status="verified",
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("video_id"),
            content_type=raw.get("video_type") or "video",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=raw.get("nickname"),
            content_url=raw.get("video_url"),
            cover_url=raw.get("video_cover_url") or raw.get("cover"),
            published_at=raw.get("create_time") or raw.get("publish_time"),
            source_keyword=raw.get("source_keyword"),
            play_count=raw.get("video_play_count"),
            like_count=raw.get("liked_count"),
            favorite_count=raw.get("video_favorite_count")
            or raw.get("collected_count"),
            comment_count=raw.get("video_comment") or raw.get("comment_count"),
            share_count=raw.get("video_share_count") or raw.get("share_count"),
        )


class XiaohongshuAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="xhs",
            display_name="小红书",
            storage_directory="xhs",
            verification_status="code_ready",
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("note_id"),
            content_type=raw.get("type") or "note",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=raw.get("nickname"),
            content_url=raw.get("note_url"),
            cover_url=_first_comma_value(raw.get("image_list")),
            published_at=raw.get("time"),
            source_keyword=raw.get("source_keyword"),
            like_count=raw.get("liked_count"),
            favorite_count=raw.get("collected_count"),
            comment_count=raw.get("comment_count"),
            share_count=raw.get("share_count"),
        )


class DouyinAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="dy",
            display_name="抖音",
            storage_directory="douyin",
            verification_status="code_ready",
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("aweme_id"),
            content_type=raw.get("aweme_type") or "video",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=raw.get("nickname"),
            content_url=raw.get("aweme_url"),
            cover_url=raw.get("cover_url"),
            published_at=raw.get("create_time"),
            source_keyword=raw.get("source_keyword"),
            like_count=raw.get("liked_count"),
            favorite_count=raw.get("collected_count"),
            comment_count=raw.get("comment_count"),
            share_count=raw.get("share_count"),
        )
