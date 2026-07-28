from typing import Literal
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    ValidationInfo,
    field_serializer,
    field_validator,
    model_validator,
)

from app.models.crawler_platform import CrawlerResultItem, TaskMode

TaskStatus = Literal[
    "pending",
    "running",
    "waiting_login",
    "succeeded",
    "failed",
    "cancelled",
]


class CreateCrawlerTaskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$")
    mode: TaskMode | None = None
    crawler_type: TaskMode | None = None
    keywords: str | None = Field(default=None, max_length=200)
    target_ids: list[str] = Field(default_factory=list, max_length=20)
    target_urls: list[str] = Field(default_factory=list, max_length=20)
    creator_ids: list[str] = Field(default_factory=list, max_length=20)
    creator_urls: list[str] = Field(default_factory=list, max_length=20)
    parent_content_id: str | None = Field(default=None, max_length=500)
    parent_comment_id: str | None = Field(default=None, max_length=500)
    requested_count: int = Field(default=5, ge=1, le=20)
    requested_comment_count: int = Field(default=0, ge=0, le=10)
    requested_sub_comment_count: int = Field(default=0, ge=0, le=5)
    login_type: Literal["qrcode"] = "qrcode"

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped:
            raise ValueError("keywords must not be blank")
        if not stripped.isprintable():
            raise ValueError("keywords must not contain control characters")
        return stripped

    @field_validator(
        "target_ids",
        "target_urls",
        "creator_ids",
        "creator_urls",
    )
    @classmethod
    def validate_target_lists(
        cls,
        values: list[str],
        info: ValidationInfo,
    ) -> list[str]:
        normalized: list[str] = []
        for value in values:
            stripped = value.strip()
            if not stripped or not stripped.isprintable():
                raise ValueError("task target values must be printable and non-blank")
            if len(stripped) > 2000:
                raise ValueError("task target values must not exceed 2000 characters")
            if (
                info.field_name in {"target_ids", "creator_ids"}
                and stripped.casefold().startswith(("http://", "https://"))
            ):
                raise ValueError("HTTP targets must use the corresponding URL field")
            normalized.append(stripped)
        if len(normalized) != len(set(normalized)):
            raise ValueError("task target values must be unique")
        return normalized

    @field_validator("parent_content_id", "parent_comment_id")
    @classmethod
    def validate_parent_ids(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        if not stripped or not stripped.isprintable():
            raise ValueError("parent identifiers must be printable and non-blank")
        if stripped.casefold().startswith(("http://", "https://")):
            raise ValueError("HTTP targets must use target_urls")
        return stripped

    @model_validator(mode="after")
    def validate_mode_fields(self) -> "CreateCrawlerTaskRequest":
        if (
            self.mode is not None
            and self.crawler_type is not None
            and self.mode != self.crawler_type
        ):
            raise ValueError("mode and crawler_type must match when both are set")
        resolved_mode = self.mode or self.crawler_type
        if resolved_mode is None:
            raise ValueError("mode is required")
        self.mode = resolved_mode
        self.crawler_type = resolved_mode

        has_content_target = bool(self.target_ids or self.target_urls)
        has_creator_target = bool(self.creator_ids or self.creator_urls)
        forbidden_common = (
            has_content_target
            or has_creator_target
            or self.parent_content_id is not None
            or self.parent_comment_id is not None
        )

        if resolved_mode == "search":
            if self.keywords is None:
                raise ValueError("search mode requires keywords")
            if forbidden_common:
                raise ValueError("search mode accepts only keywords")
            if self.requested_comment_count or self.requested_sub_comment_count:
                raise ValueError("search mode does not accept comment counts")
        elif resolved_mode == "detail":
            if self.keywords is not None or not has_content_target:
                raise ValueError("detail mode requires target_ids or target_urls")
            if has_creator_target or self.parent_content_id or self.parent_comment_id:
                raise ValueError("detail mode received incompatible target fields")
            if len(self.target_ids) + len(self.target_urls) > self.requested_count:
                raise ValueError(
                    "detail mode target count must not exceed requested_count"
                )
            if self.requested_comment_count or self.requested_sub_comment_count:
                raise ValueError("detail mode does not accept comment counts")
        elif resolved_mode == "creator":
            if self.keywords is not None or not has_creator_target:
                raise ValueError("creator mode requires creator_ids or creator_urls")
            if has_content_target or self.parent_content_id or self.parent_comment_id:
                raise ValueError("creator mode received incompatible target fields")
            if len(self.creator_ids) + len(self.creator_urls) > self.requested_count:
                raise ValueError(
                    "creator mode target count must not exceed requested_count"
                )
            if self.requested_comment_count or self.requested_sub_comment_count:
                raise ValueError("creator mode does not accept comment counts")
        elif resolved_mode == "comments":
            if self.keywords is not None or has_creator_target:
                raise ValueError("comments mode received incompatible target fields")
            if self.parent_comment_id is not None:
                raise ValueError("comments mode does not accept parent_comment_id")
            target_count = len(self.target_urls) + int(self.parent_content_id is not None)
            target_count += len(self.target_ids)
            if target_count != 1:
                raise ValueError("comments mode requires exactly one content target")
            if not 1 <= self.requested_comment_count <= 10:
                raise ValueError(
                    "comments mode requires requested_comment_count from 1 to 10"
                )
            if self.requested_sub_comment_count:
                raise ValueError("comments mode does not accept sub-comment count")
            self.requested_count = 1
        elif resolved_mode == "sub_comments":
            if self.keywords is not None or has_creator_target:
                raise ValueError("sub_comments mode received incompatible target fields")
            target_count = len(self.target_urls) + int(self.parent_content_id is not None)
            target_count += len(self.target_ids)
            if target_count != 1 or self.parent_comment_id is None:
                raise ValueError(
                    "sub_comments mode requires one content target and "
                    "parent_comment_id"
                )
            if not 1 <= self.requested_sub_comment_count <= 5:
                raise ValueError(
                    "sub_comments mode requires requested_sub_comment_count "
                    "from 1 to 5"
                )
            if self.requested_comment_count:
                raise ValueError("sub_comments mode does not accept comment count")
            self.requested_count = 1
        return self


class CrawlerTaskResponse(BaseModel):
    id: str
    platform: str
    mode: TaskMode
    crawler_type: TaskMode
    keywords: str | None
    target_ids: list[str]
    target_urls: list[str]
    creator_ids: list[str]
    creator_urls: list[str]
    parent_content_id: str | None
    parent_comment_id: str | None
    login_type: str
    status: TaskStatus
    requested_count: int
    actual_count: int
    requested_comment_count: int
    requested_sub_comment_count: int
    output_dir: str
    log_path: str
    qrcode_path: str
    pid: int | None
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    cancel_requested: bool

    @field_serializer("target_urls", "creator_urls")
    def redact_sensitive_query_values(self, values: list[str]) -> list[str]:
        redacted: list[str] = []
        for value in values:
            parts = urlsplit(value)
            safe_query = [
                (key, query_value)
                for key, query_value in parse_qsl(
                    parts.query,
                    keep_blank_values=True,
                )
                if "token" not in key.casefold()
                and "cookie" not in key.casefold()
                and "signature" not in key.casefold()
            ]
            redacted.append(
                urlunsplit(
                    (
                        parts.scheme,
                        parts.netloc,
                        parts.path,
                        urlencode(safe_query),
                        "",
                    )
                )
            )
        return redacted


class CrawlerResultsResponse(BaseModel):
    items: list[CrawlerResultItem]
    offset: int
    limit: int
    next_offset: int
    has_more: bool
