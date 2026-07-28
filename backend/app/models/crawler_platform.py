from typing import Literal

from pydantic import BaseModel

TaskMode = Literal[
    "search",
    "detail",
    "creator",
    "comments",
    "sub_comments",
]
ModeStatus = Literal[
    "not_implemented",
    "code_ready",
    "enabled",
    "production_verified",
    "deferred_resource_constrained",
    "deferred_upstream_breakage",
    "deferred_login_required",
    "deferred_platform_change",
    "disabled",
]
VerificationStatus = Literal[
    "not_implemented",
    "code_ready",
    "production_verified",
]
AvailabilityStatus = Literal[
    "enabled",
    "disabled",
    "deferred_resource_constrained",
    "deferred_upstream_breakage",
    "deferred_login_required",
    "deferred_platform_change",
]


class CapabilityOption(BaseModel):
    value: str
    label: str


class RequestedCountCapability(BaseModel):
    minimum: int
    maximum: int
    default: int


class CrawlerModeCapability(BaseModel):
    mode: TaskMode
    label: str
    status: ModeStatus
    enabled: bool
    reason: str | None
    input_fields: list[str]
    requested_count: RequestedCountCapability
    requested_comment_count: RequestedCountCapability | None
    requested_sub_comment_count: RequestedCountCapability | None
    requires_browser: bool
    login_type: Literal["qrcode"]


class CrawlerPlatformCapability(BaseModel):
    platform: str
    display_name: str
    icon_label: str
    enabled: bool
    verification_status: VerificationStatus
    availability_status: AvailabilityStatus
    login_prompt: str
    crawler_types: list[CapabilityOption]
    login_types: list[CapabilityOption]
    requested_count: RequestedCountCapability
    supports_comments: bool
    supports_sub_comments: bool
    modes: list[CrawlerModeCapability]


class CrawlerCapabilitiesResponse(BaseModel):
    max_concurrent_tasks: int
    platforms: list[CrawlerPlatformCapability]


class CrawlerResultMetrics(BaseModel):
    play_count: int | None
    like_count: int | None
    favorite_count: int | None
    comment_count: int | None
    share_count: int | None


class CrawlerResultItem(BaseModel):
    platform: str
    content_id: str
    content_type: str
    title: str
    description: str | None
    author_name: str | None
    content_url: str | None
    cover_url: str | None
    published_at: int | None
    source_keyword: str | None
    raw_payload: dict[str, object]
    metrics: CrawlerResultMetrics
