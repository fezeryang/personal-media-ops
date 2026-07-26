from typing import Literal

from pydantic import BaseModel


class CapabilityOption(BaseModel):
    value: str
    label: str


class RequestedCountCapability(BaseModel):
    minimum: int
    maximum: int
    default: int


class CrawlerPlatformCapability(BaseModel):
    platform: str
    display_name: str
    enabled: bool
    verification_status: Literal["verified", "code_ready"]
    crawler_types: list[CapabilityOption]
    login_types: list[CapabilityOption]
    requested_count: RequestedCountCapability
    supports_comments: bool
    supports_sub_comments: bool


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
    metrics: CrawlerResultMetrics
