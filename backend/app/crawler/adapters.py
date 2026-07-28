import re
from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from app.models.crawler_platform import (
    AvailabilityStatus,
    CapabilityOption,
    CrawlerModeCapability,
    CrawlerPlatformCapability,
    CrawlerResultItem,
    CrawlerResultMetrics,
    ModeStatus,
    RequestedCountCapability,
    TaskMode,
    VerificationStatus,
)
from app.models.library import (
    NormalizedComment,
    NormalizedContent,
    NormalizedCreator,
)

RawResult = Mapping[str, object]
TaskInput = Mapping[str, object]
LoginStateSignal = Literal[
    "success",
    "captcha_required",
    "login_expired",
    "login_timeout",
]

MODE_LABELS: dict[TaskMode, str] = {
    "search": "关键词搜索",
    "detail": "内容详情",
    "creator": "创作者主页",
    "comments": "一级评论",
    "sub_comments": "二级评论",
}
MODE_INPUT_FIELDS: dict[TaskMode, list[str]] = {
    "search": ["keywords"],
    "detail": ["target_ids", "target_urls"],
    "creator": ["creator_ids", "creator_urls"],
    "comments": ["parent_content_id", "target_ids", "target_urls"],
    "sub_comments": [
        "parent_content_id",
        "target_ids",
        "target_urls",
        "parent_comment_id",
    ],
}
SUBMITTABLE_BASE_STATUSES = frozenset({"code_ready", "production_verified"})


def _text(value: object) -> str | None:
    if not isinstance(value, (str, int, float)) or isinstance(value, bool):
        return None
    normalized = str(value).strip()
    return normalized or None


def _first_text(raw: RawResult, *keys: str) -> str | None:
    for key in keys:
        value = _text(raw.get(key))
        if value is not None:
            return value
    return None


def _first_present(raw: RawResult, *keys: str) -> object:
    for key in keys:
        value = raw.get(key)
        if value is not None:
            return value
    return None


_COUNT_UNIT_MULTIPLIERS = {
    "万": 10_000,
    "w": 10_000,
    "W": 10_000,
    "亿": 100_000_000,
}
_ABBREVIATED_COUNT_PATTERN = re.compile(r"^[0-9]+(?:\.[0-9]+)?$")
_MAX_COUNT_TEXT_LENGTH = 64
# Crawled text is untrusted: reject implausible magnitudes before Decimal
# arithmetic can materialize a huge integer or overflow the decimal context.
_MAX_ABBREVIATED_AMOUNT = Decimal(10) ** 12
_MAX_UNIX_SECONDS = 253_402_300_799
_MAX_UNIX_NANOSECONDS = 253_402_300_799_999_999_999


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
        # ``isdecimal`` matches what ``int`` accepts; superscripts pass
        # ``isdigit`` but would still raise ValueError.
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
        if numeric > _MAX_UNIX_NANOSECONDS:
            return None
        # MediaCrawler platform payloads are inconsistent about epoch units.
        # Reduce milliseconds, microseconds, or nanoseconds to seconds before
        # values reach datetime.fromtimestamp in the persistence layer.
        while numeric > _MAX_UNIX_SECONDS:
            numeric //= 1000
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
    if (
        parsed.scheme not in {"http", "https"}
        or not parsed.netloc
        or parsed.username is not None
        or parsed.password is not None
    ):
        return None
    return text


def _host_is_allowed(value: str, allowed_hosts: frozenset[str]) -> bool:
    hostname = urlparse(value).hostname
    if hostname is None:
        return False
    normalized = hostname.casefold().rstrip(".")
    return any(
        normalized == allowed or normalized.endswith(f".{allowed}")
        for allowed in allowed_hosts
    )


def _first_comma_value(value: object) -> str | None:
    text = _text(value)
    if text is None:
        return None
    return text.split(",", 1)[0].strip() or None


def _task_strings(task: TaskInput, key: str) -> tuple[str, ...]:
    value = task.get(key)
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


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
    mode_statuses: Mapping[TaskMode, ModeStatus]
    mode_reasons: Mapping[TaskMode, str]
    allowed_target_hosts: frozenset[str]
    requires_content_url_modes: frozenset[TaskMode] = frozenset()
    requires_creator_url: bool = False

    def mode_status(self, mode: TaskMode, configured: bool) -> tuple[ModeStatus, bool]:
        base_status = self.mode_statuses.get(mode, "not_implemented")
        enabled = configured and base_status in SUBMITTABLE_BASE_STATUSES
        if enabled and base_status == "code_ready":
            return "enabled", True
        return base_status, enabled

    def capability(self, configured: bool) -> CrawlerPlatformCapability:
        modes: list[CrawlerModeCapability] = []
        for mode, mode_label in MODE_LABELS.items():
            status, enabled = self.mode_status(mode, configured)
            modes.append(
                CrawlerModeCapability(
                    mode=mode,
                    label=mode_label,
                    status=status,
                    enabled=enabled,
                    reason=self.mode_reasons.get(mode),
                    input_fields=MODE_INPUT_FIELDS[mode],
                    requested_count=RequestedCountCapability(
                        minimum=1,
                        maximum=20,
                        default=(
                            1
                            if mode in {"comments", "sub_comments"}
                            else self.default_requested_count
                        ),
                    ),
                    requested_comment_count=(
                        RequestedCountCapability(minimum=1, maximum=10, default=10)
                        if mode == "comments"
                        else None
                    ),
                    requested_sub_comment_count=(
                        RequestedCountCapability(minimum=1, maximum=5, default=5)
                        if mode == "sub_comments"
                        else None
                    ),
                    requires_browser=True,
                    login_type="qrcode",
                )
            )

        search_status, search_enabled = self.mode_status("search", configured)
        verification_status: VerificationStatus
        if search_status == "production_verified":
            verification_status = "production_verified"
        elif search_status == "not_implemented":
            verification_status = "not_implemented"
        else:
            verification_status = "code_ready"
        if search_enabled:
            availability_status: AvailabilityStatus = "enabled"
        elif search_status in {
            "deferred_resource_constrained",
            "deferred_upstream_breakage",
            "deferred_login_required",
            "deferred_platform_change",
        }:
            availability_status = search_status
        else:
            availability_status = self.unavailable_status

        return CrawlerPlatformCapability(
            platform=self.platform,
            display_name=self.display_name,
            icon_label=self.icon_label,
            enabled=search_enabled,
            verification_status=verification_status,
            availability_status=availability_status,
            login_prompt=self.login_prompt,
            crawler_types=[
                CapabilityOption(value=mode.mode, label=mode.label)
                for mode in modes
                if mode.status != "not_implemented"
            ],
            login_types=[CapabilityOption(value="qrcode", label="二维码登录")],
            requested_count=RequestedCountCapability(
                minimum=1,
                maximum=20,
                default=self.default_requested_count,
            ),
            supports_comments=any(
                mode.mode == "comments" and mode.status != "not_implemented"
                for mode in modes
            ),
            supports_sub_comments=any(
                mode.mode == "sub_comments" and mode.status != "not_implemented"
                for mode in modes
            ),
            modes=modes,
        )

    def validate_task_request(self, task: TaskInput) -> TaskMode:
        mode_value = task.get("crawler_type")
        if mode_value not in MODE_LABELS:
            raise ValueError("unsupported crawler mode")
        mode: TaskMode = mode_value
        if self.mode_statuses.get(mode, "not_implemented") not in (
            SUBMITTABLE_BASE_STATUSES
        ):
            raise ValueError(f"{self.display_name} {MODE_LABELS[mode]} is unavailable")

        target_ids = _task_strings(task, "target_ids")
        target_urls = _task_strings(task, "target_urls")
        creator_ids = _task_strings(task, "creator_ids")
        creator_urls = _task_strings(task, "creator_urls")
        identifiers = (
            *target_ids,
            *creator_ids,
            *(
                [str(task["parent_content_id"])]
                if task.get("parent_content_id") is not None
                else []
            ),
        )
        if any(
            identifier.casefold().startswith(("http://", "https://"))
            for identifier in identifiers
        ):
            raise ValueError("HTTP targets must use the corresponding URL field")
        for url in (*target_urls, *creator_urls):
            if _safe_http_url(url) is None:
                raise ValueError("task target URLs must use HTTP or HTTPS")
            if not _host_is_allowed(url, self.allowed_target_hosts):
                raise ValueError(
                    f"{self.display_name} target URL must use an approved "
                    "platform hostname"
                )
        if mode in self.requires_content_url_modes and not target_urls:
            raise ValueError(
                f"{self.display_name} {MODE_LABELS[mode]} requires a full target URL"
            )
        if mode == "creator" and self.requires_creator_url and not creator_urls:
            raise ValueError(
                f"{self.display_name} creator mode requires a full creator URL"
            )
        if mode == "detail" and not (target_ids or target_urls):
            raise ValueError("detail mode requires a content target")
        if mode == "detail" and len(target_ids) + len(target_urls) > int(
            task["requested_count"]
        ):
            raise ValueError(
                "detail mode target count must not exceed requested_count"
            )
        if mode == "creator" and not (creator_ids or creator_urls):
            raise ValueError("creator mode requires a creator target")
        if mode == "creator" and len(creator_ids) + len(creator_urls) > int(
            task["requested_count"]
        ):
            raise ValueError(
                "creator mode target count must not exceed requested_count"
            )
        if mode in {"comments", "sub_comments"} and not (
            target_ids or target_urls or _text(task.get("parent_content_id"))
        ):
            raise ValueError(f"{mode} mode requires a content target")
        if mode == "sub_comments" and not _text(task.get("parent_comment_id")):
            raise ValueError("sub_comments mode requires parent_comment_id")
        return mode

    def build_runner_arguments(
        self,
        *,
        task: TaskInput,
        output_dir: Path,
        qrcode_path: Path,
    ) -> list[str]:
        mode = self.validate_task_request(task)
        arguments = [
            "--platform",
            self.platform,
            "--crawler-type",
            mode,
            "--login-type",
            "qrcode",
            "--requested-count",
            str(task["requested_count"]),
            "--requested-comment-count",
            str(task.get("requested_comment_count", 0)),
            "--requested-sub-comment-count",
            str(task.get("requested_sub_comment_count", 0)),
            "--output-dir",
            str(output_dir),
            "--qrcode-path",
            str(qrcode_path),
            "--max-concurrency-num",
            "1",
            "--enable-comments",
            "true" if mode == "comments" else "false",
            "--enable-sub-comments",
            "false",
            "--headless",
            "true" if self.headless_browser else "false",
        ]
        keywords = _text(task.get("keywords"))
        if keywords is not None:
            arguments.append(f"--keywords={keywords}")
        for field, flag in (
            ("target_ids", "--target-id"),
            ("target_urls", "--target-url"),
            ("creator_ids", "--creator-id"),
            ("creator_urls", "--creator-url"),
        ):
            for value in _task_strings(task, field):
                arguments.append(f"{flag}={value}")
        for field, flag in (
            ("parent_content_id", "--parent-content-id"),
            ("parent_comment_id", "--parent-comment-id"),
        ):
            value = _text(task.get(field))
            if value is not None:
                arguments.append(f"{flag}={value}")
        return arguments

    def _result_files(self, task_dir: Path, item_type: str) -> list[Path]:
        task_root = task_dir.resolve()
        collected: set[Path] = set()
        for storage_directory in self.storage_directories:
            jsonl_root = task_dir / storage_directory / "jsonl"
            if not jsonl_root.is_dir():
                continue
            for candidate in jsonl_root.glob(f"*_{item_type}_*.jsonl"):
                resolved = candidate.resolve()
                if not resolved.is_relative_to(task_root):
                    raise ValueError("result path escapes task output directory")
                if resolved.is_file():
                    collected.add(resolved)
        return sorted(collected)

    def discover_content_files(self, task_dir: Path) -> list[Path]:
        return self._result_files(task_dir, "contents")

    def discover_creator_files(self, task_dir: Path) -> list[Path]:
        return self._result_files(task_dir, "creators")

    def discover_comment_files(self, task_dir: Path) -> list[Path]:
        return self._result_files(task_dir, "comments")

    def content_result_files(self, task_dir: Path) -> list[Path]:
        """Compatibility alias used by the legacy task-result endpoint."""
        return self.discover_content_files(task_dir)

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
            or ("login" in normalized and "failed by qrcode" in normalized)
            or "登录超时" in line
        ):
            return "login_timeout"
        return None

    def classify_failure(self, message: str) -> str:
        normalized = message.casefold()
        if "captcha" in normalized or "验证码" in message:
            return "Platform requires manual verification"
        if "no usable results" in normalized or "contract unavailable" in normalized:
            return "Platform upstream returned no usable data"
        return message

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

    def normalize_content(self, raw: RawResult) -> NormalizedContent:
        result = self.normalize_result(raw)
        if not result.content_id:
            raise ValueError("content result is missing a source content ID")
        return NormalizedContent(
            platform=self.platform,
            source_content_id=result.content_id,
            content_type=result.content_type,
            title=result.title or None,
            description=result.description,
            source_url=result.content_url,
            cover_url=result.cover_url,
            author_source_id=_first_text(
                raw,
                "creator_hash",
                "author_source_id",
                "user_id",
                "mid",
                "author_id",
            ),
            author_name=result.author_name,
            published_at=result.published_at,
            source_keyword=result.source_keyword,
            view_count=result.metrics.play_count,
            like_count=result.metrics.like_count,
            favorite_count=result.metrics.favorite_count,
            comment_count=result.metrics.comment_count,
            share_count=result.metrics.share_count,
            raw_payload=dict(raw),
        )

    def normalize_creator(self, raw: RawResult) -> NormalizedCreator:
        source_creator_id = _first_text(
            raw,
            "_mediaops_source_creator_id",
            "creator_hash",
            "creator_id",
            "user_id",
            "uid",
            "mid",
            "id",
            "url_token",
        )
        if source_creator_id is None:
            raise ValueError("creator result is missing a source creator ID")
        return NormalizedCreator(
            platform=self.platform,
            source_creator_id=source_creator_id,
            display_name=_first_text(
                raw,
                "display_name",
                "nickname",
                "user_nickname",
                "name",
                "screen_name",
            ),
            profile_url=_safe_http_url(
                _first_present(raw, "_mediaops_profile_url", "profile_url")
            ),
            avatar_url=_safe_http_url(
                _first_present(raw, "avatar_url", "avatar", "avatar_hd", "face")
            ),
            description=_first_text(raw, "description", "desc", "signature", "bio"),
            follower_count=_integer(
                _first_present(
                    raw,
                    "follower_count",
                    "fans",
                    "followers_count",
                )
            ),
            following_count=_integer(
                _first_present(
                    raw,
                    "following_count",
                    "follows",
                    "follow_count",
                )
            ),
            content_count=_integer(
                _first_present(
                    raw,
                    "content_count",
                    "notes",
                    "statuses_count",
                    "video_count",
                    "anwser_count",
                )
            ),
            raw_payload=dict(raw),
        )

    def normalize_comment(self, raw: RawResult) -> NormalizedComment:
        comment_id = _first_text(raw, "comment_id", "id", "rpid")
        content_id = _first_text(
            raw,
            "source_content_id",
            "content_id",
            "note_id",
            "video_id",
            "aweme_id",
        )
        body = _first_text(raw, "content", "body", "text", "message")
        if comment_id is None or content_id is None or body is None:
            raise ValueError("comment result is missing ID, content ID, or body")
        parent_comment_id = _first_text(
            raw,
            "parent_comment_id",
            "root_comment_id",
            "rootid",
            "parent",
        )
        if parent_comment_id in {"0", comment_id}:
            parent_comment_id = None
        return NormalizedComment(
            platform=self.platform,
            source_comment_id=comment_id,
            source_content_id=content_id,
            parent_comment_id=parent_comment_id,
            author_source_id=_first_text(
                raw,
                "creator_hash",
                "author_source_id",
                "user_id",
                "author_id",
            ),
            author_name=_first_text(
                raw,
                "nickname",
                "user_nickname",
                "author_name",
            ),
            body=body,
            like_count=_integer(
                _first_present(
                    raw,
                    "like_count",
                    "comment_like_count",
                    "like",
                )
            ),
            reply_count=_integer(
                _first_present(raw, "reply_count", "sub_comment_count")
            ),
            published_at=_timestamp(
                _first_present(
                    raw,
                    "published_at",
                    "publish_time",
                    "create_time",
                    "timestamp",
                )
            ),
            raw_payload=dict(raw),
        )


def _mode_map(
    *,
    search: ModeStatus,
    detail: ModeStatus = "code_ready",
    creator: ModeStatus = "code_ready",
    comments: ModeStatus = "code_ready",
    sub_comments: ModeStatus = "code_ready",
) -> Mapping[TaskMode, ModeStatus]:
    return {
        "search": search,
        "detail": detail,
        "creator": creator,
        "comments": comments,
        "sub_comments": sub_comments,
    }


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
            mode_statuses=_mode_map(
                search="production_verified",
                detail="production_verified",
                creator="production_verified",
                comments="production_verified",
                sub_comments="production_verified",
            ),
            mode_reasons={},
            allowed_target_hosts=frozenset({"bilibili.com", "b23.tv"}),
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
            cover_url=_first_present(raw, "video_cover_url", "cover"),
            published_at=_first_present(raw, "create_time", "publish_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            play_count=raw.get("video_play_count"),
            like_count=raw.get("liked_count"),
            favorite_count=_first_present(
                raw,
                "video_favorite_count",
                "collected_count",
            ),
            comment_count=_first_present(raw, "video_comment", "comment_count"),
            share_count=_first_present(raw, "video_share_count", "share_count"),
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
            mode_statuses=_mode_map(
                search="production_verified",
                detail="deferred_login_required",
                creator="deferred_login_required",
                comments="deferred_login_required",
                sub_comments="deferred_login_required",
            ),
            mode_reasons={
                "detail": "内容 URL 需要包含有效的 xsec 参数",
                "creator": "创作者 URL 需要包含有效的 xsec 参数",
                "comments": "内容 URL 需要包含有效的 xsec 参数",
                "sub_comments": "内容 URL 需要包含有效的 xsec 参数",
            },
            allowed_target_hosts=frozenset(
                {"xiaohongshu.com", "xhslink.com"}
            ),
            requires_content_url_modes=frozenset(
                {"detail", "comments", "sub_comments"}
            ),
            requires_creator_url=True,
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
        deferred = _mode_map(
            search="deferred_resource_constrained",
            detail="deferred_resource_constrained",
            creator="deferred_resource_constrained",
            comments="deferred_resource_constrained",
            sub_comments="deferred_resource_constrained",
        )
        super().__init__(
            platform="dy",
            display_name="抖音",
            icon_label="抖",
            storage_directories=("dy", "douyin"),
            verification_status="code_ready",
            unavailable_status="deferred_resource_constrained",
            login_prompt="资源条件允许后使用抖音客户端扫码登录",
            headless_browser=False,
            qrcode_startup_timeout_seconds=None,
            default_requested_count=3,
            mode_statuses=deferred,
            mode_reasons={
                mode: "当前生产主机浏览器资源不足，保留独立容量延期任务"
                for mode in MODE_LABELS
            },
            allowed_target_hosts=frozenset({"douyin.com"}),
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
            mode_statuses=_mode_map(
                search="production_verified",
                detail="production_verified",
                creator="production_verified",
                comments="production_verified",
                sub_comments="production_verified",
            ),
            mode_reasons={},
            allowed_target_hosts=frozenset({"zhihu.com"}),
            requires_content_url_modes=frozenset(
                {"detail", "comments", "sub_comments"}
            ),
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("content_id"),
            content_type=raw.get("content_type") or "answer",
            title=raw.get("title"),
            description=_first_present(raw, "desc", "content_text"),
            author_name=_first_present(raw, "user_nickname", "nickname"),
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
            mode_statuses=_mode_map(
                search="production_verified",
                detail="production_verified",
                creator="production_verified",
                comments="production_verified",
                sub_comments="deferred_platform_change",
            ),
            mode_reasons={
                "sub_comments": "固定上游只返回根评论内嵌回复，无法按父评论独立限量采集"
            },
            allowed_target_hosts=frozenset({"weibo.com", "weibo.cn"}),
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("note_id"),
            content_type="post",
            title=raw.get("content"),
            description=None,
            author_name=_first_present(raw, "nickname", "user_nickname"),
            content_url=raw.get("note_url"),
            cover_url=_first_present(raw, "image_url", "cover_url"),
            published_at=raw.get("create_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            like_count=raw.get("liked_count"),
            comment_count=_first_present(raw, "comments_count", "comment_count"),
            share_count=_first_present(raw, "shared_count", "share_count"),
        )


class TiebaAdapter(CrawlerPlatformAdapter):
    def __init__(self) -> None:
        super().__init__(
            platform="tieba",
            display_name="百度贴吧",
            icon_label="贴",
            storage_directories=("tieba",),
            verification_status="production_verified",
            unavailable_status="disabled",
            login_prompt="使用百度客户端或网页二维码登录贴吧",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=5,
            mode_statuses=_mode_map(
                search="production_verified",
                detail="production_verified",
                creator="production_verified",
                comments="production_verified",
                sub_comments="deferred_platform_change",
            ),
            mode_reasons={
                "sub_comments": "固定上游按楼层页面递归采集，当前无法按父回复安全限量"
            },
            allowed_target_hosts=frozenset({"tieba.baidu.com"}),
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("note_id"),
            content_type="post",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=_first_present(raw, "user_nickname", "nickname"),
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
            unavailable_status="deferred_upstream_breakage",
            login_prompt="搜索上游失效；详情、创作者和评论需独立生产验证",
            headless_browser=True,
            qrcode_startup_timeout_seconds=180,
            default_requested_count=3,
            mode_statuses=_mode_map(
                search="deferred_upstream_breakage",
                detail="production_verified",
                creator="deferred_upstream_breakage",
                comments="production_verified",
            ),
            mode_reasons={
                "search": "固定上游 GraphQL 搜索已被平台 REST 接口替代",
                "creator": "固定上游创作者资料接口对多个公开目标均返回空资料",
            },
            allowed_target_hosts=frozenset({"kuaishou.com"}),
        )

    def normalize_result(self, raw: RawResult) -> CrawlerResultItem:
        return self._result(
            platform=self.platform,
            content_id=raw.get("video_id"),
            content_type=raw.get("video_type") or "video",
            title=raw.get("title"),
            description=raw.get("desc"),
            author_name=_first_present(raw, "user_nickname", "nickname"),
            content_url=raw.get("video_url"),
            cover_url=raw.get("video_cover_url"),
            published_at=raw.get("create_time"),
            source_keyword=raw.get("source_keyword"),
            raw_payload=raw,
            play_count=_first_present(raw, "viewd_count", "view_count"),
            like_count=raw.get("liked_count"),
        )
