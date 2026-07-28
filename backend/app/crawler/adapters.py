import re
from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from app.models.crawler_platform import (
    AvailabilityStatus,
    CapabilityOption,
    CrawlerPlatformCapability,
    CrawlerResultItem,
    CrawlerResultMetrics,
    RequestedCountCapability,
    VerificationStatus,
)

RawResult = Mapping[str, object]
LoginStateSignal = Literal[
    "success",
    "captcha_required",
    "login_expired",
    "login_timeout",
]


def _text(value: object) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    normalized = str(value).strip()
    return normalized or None


_COUNT_UNIT_MULTIPLIERS = {
    "万": 10_000,
    "w": 10_000,
    "W": 10_000,
    "亿": 100_000_000,
}
_ABBREVIATED_COUNT_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_MAX_COUNT_TEXT_LENGTH = 64
# Crawled text is not trusted input: ``Decimal("1E+9999999")`` parses fine but
# overflows the decimal context on multiplication, and a merely large exponent
# would materialise a multi-hundred-megabyte int. Reject implausible magnitudes
# before any arithmetic; real engagement counts stay far below this bound.
_MAX_ABBREVIATED_AMOUNT = Decimal(10) ** 12


def _integer_from_string(value: str) -> int | None:
    normalized = value.strip().replace(",", "")
    if normalized.endswith("+"):
        normalized = normalized[:-1].strip()
    multiplier = _COUNT_UNIT_MULTIPLIERS.get(normalized[-1:], 1)
    if multiplier != 1:
        normalized = normalized[:-1].strip()
    if not normalized or len(normalized) > _MAX_COUNT_TEXT_LENGTH:
        return None
    if multiplier == 1:
        # isdecimal() (not isdigit()) matches exactly what int() accepts:
        # superscripts like "²" are isdigit() yet crash int().
        return int(normalized) if normalized.isdecimal() else None
    if _ABBREVIATED_COUNT_PATTERN.fullmatch(normalized) is None:
        return None
    try:
        amount = Decimal(normalized)
    except InvalidOperation:
        return None
    if not amount.is_finite() or amount < 0 or amount > _MAX_ABBREVIATED_AMOUNT:
        return None
    return int(amount * multiplier)


def _integer(value: object) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value if value >= 0 else None
    if isinstance(value, float):
        return int(value) if value >= 0 and value.is_integer() else None
    if isinstance(value, str):
        return _integer_from_string(value)
    return None


def _timestamp(value: object) -> int | None:
    numeric = _integer(value)
    if numeric is not None:
        return numeric
    text = _text(value)
    if text is None or len(text) > 64:
        return None
    normalized = text[:-1] + "+00:00" if text.endswith(("Z", "z")) else text
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=UTC)
    timestamp = int(parsed.timestamp())
    return timestamp if timestamp >= 0 else None


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
    icon_label: str
    storage_directories: tuple[str, ...]
    verification_status: VerificationStatus
    unavailable_status: AvailabilityStatus
    login_prompt: str
    headless_browser: bool
    qrcode_startup_timeout_seconds: float | None
    default_requested_count: int

    def capability(self, enabled: bool) -> CrawlerPlatformCapability:
        return CrawlerPlatformCapability(
            platform=self.platform,
            display_name=self.display_name,
            icon_label=self.icon_label,
            enabled=enabled,
            verification_status=self.verification_status,
            availability_status="enabled" if enabled else self.unavailable_status,
            login_prompt=self.login_prompt,
            crawler_types=[
                CapabilityOption(value="search", label="关键词搜索"),
            ],
            login_types=[
                CapabilityOption(value="qrcode", label="二维码登录"),
            ],
            requested_count=RequestedCountCapability(
                minimum=1,
                maximum=20,
                default=self.default_requested_count,
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
            "--headless",
            "true" if self.headless_browser else "false",
        ]

    def content_result_files(self, task_dir: Path) -> list[Path]:
        task_root = task_dir.resolve()
        collected: set[Path] = set()
        for storage_directory in self.storage_directories:
            jsonl_root = task_dir / storage_directory / "jsonl"
            if not jsonl_root.is_dir():
                continue
            for candidate in jsonl_root.glob("*_contents_*.jsonl"):
                resolved = candidate.resolve()
                if not resolved.is_relative_to(task_root):
                    raise ValueError("result path escapes task output directory")
                if resolved.is_file():
                    collected.add(resolved)
        return sorted(collected)

    @staticmethod
    def is_login_success(line: str) -> bool:
        return "login successful" in line.casefold()

    def classify_login_line(self, line: str) -> LoginStateSignal | None:
        normalized = line.casefold()
        if (
            self.is_login_success(line)
            or "[mediaops] existing login state ready:" in normalized
        ):
            return "success"
        if (
            "需要验证码" in line
            or "captcha required" in normalized
            or "requires captcha" in normalized
        ):
            return "captcha_required"
        if (
            ("login" in normalized and "expired" in normalized)
            or "登录状态失效" in line
            or "登录已失效" in line
        ):
            return "login_expired"
        if (
            ("login" in normalized and "timeout" in normalized)
            or ("qr" in normalized and "timeout" in normalized)
            or "have not found qrcode" in normalized
            or (
                "login" in normalized
                and "failed by qrcode" in normalized
            )
            or "登录超时" in line
        ):
            return "login_timeout"
        return None

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
        raw_payload: RawResult,
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
            published_at=_timestamp(published_at),
            source_keyword=_text(source_keyword),
            raw_payload=dict(raw_payload),
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
            icon_label="哔",
            storage_directories=("bili", "bilibili"),
            verification_status="production_verified",
            unavailable_status="disabled",
            login_prompt="使用哔哩哔哩客户端扫码登录",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=20,
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
            raw_payload=raw,
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
            icon_label="红",
            storage_directories=("xhs",),
            verification_status="production_verified",
            unavailable_status="disabled",
            login_prompt="使用小红书客户端扫码登录",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=20,
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
            raw_payload=raw,
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
            icon_label="抖",
            storage_directories=("dy", "douyin"),
            verification_status="code_ready",
            unavailable_status="deferred_resource_constrained",
            login_prompt="资源条件允许后使用抖音客户端扫码登录",
            # douyin.com serves a captcha interstitial to headless browsers,
            # so the reviewed Runner must drive a headful browser on a
            # virtual display for this platform.
            headless_browser=False,
            # Preserve the dedicated production override and its 180-second
            # default while letting the Worker stay platform-agnostic.
            qrcode_startup_timeout_seconds=None,
            default_requested_count=3,
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
            raw_payload=raw,
            like_count=raw.get("liked_count"),
            favorite_count=raw.get("collected_count"),
            comment_count=raw.get("comment_count"),
            share_count=raw.get("share_count"),
        )


class ZhihuAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="zhihu",
            display_name="知乎",
            icon_label="知",
            storage_directories=("zhihu",),
            verification_status="production_verified",
            unavailable_status="disabled",
            login_prompt="使用知乎客户端扫码登录；若出现验证码请按任务提示完成",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=5,
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("content_id"),
            content_type=raw.get("content_type") or "answer",
            title=raw.get("title"),
            description=raw.get("desc") or raw.get("content_text"),
            author_name=raw.get("user_nickname") or raw.get("nickname"),
            content_url=raw.get("content_url"),
            cover_url=None,
            published_at=raw.get("created_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            like_count=raw.get("voteup_count"),
            comment_count=raw.get("comment_count"),
        )


class WeiboAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="wb",
            display_name="微博",
            icon_label="微",
            storage_directories=("weibo",),
            verification_status="production_verified",
            unavailable_status="disabled",
            login_prompt="使用微博客户端扫码登录；正文始终按纯文本展示",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=5,
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("note_id"),
            content_type="post",
            title=raw.get("content"),
            description=None,
            author_name=raw.get("nickname") or raw.get("user_nickname"),
            content_url=raw.get("note_url"),
            cover_url=raw.get("image_url") or raw.get("cover_url"),
            published_at=raw.get("create_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            like_count=raw.get("liked_count"),
            comment_count=raw.get("comments_count") or raw.get("comment_count"),
            share_count=raw.get("shared_count") or raw.get("share_count"),
        )


class TiebaAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="tieba",
            display_name="百度贴吧",
            icon_label="贴",
            storage_directories=("tieba",),
            verification_status="code_ready",
            unavailable_status="disabled",
            login_prompt="使用百度客户端或网页二维码登录贴吧",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=5,
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("note_id"),
            content_type="post",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=raw.get("user_nickname") or raw.get("nickname"),
            content_url=raw.get("note_url"),
            cover_url=None,
            published_at=raw.get("publish_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            comment_count=raw.get("total_replay_num"),
        )


class KuaishouAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="ks",
            display_name="快手",
            icon_label="快",
            storage_directories=("kuaishou",),
            verification_status="code_ready",
            unavailable_status="disabled",
            login_prompt="使用快手客户端扫码登录；任务启动前会检查浏览器资源",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=3,
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("video_id"),
            content_type=raw.get("video_type") or "video",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=raw.get("user_nickname") or raw.get("nickname"),
            content_url=raw.get("video_url"),
            cover_url=raw.get("video_cover_url"),
            published_at=raw.get("create_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            play_count=raw.get("viewd_count") or raw.get("view_count"),
            like_count=raw.get("liked_count"),
        )
