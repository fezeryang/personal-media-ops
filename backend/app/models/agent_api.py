from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field


class AgentSource(BaseModel):
    platform: str
    source_id: str
    url: str | None


class AgentMetricSet(BaseModel):
    view_count: int | None = None
    like_count: int | None = None
    favorite_count: int | None = None
    comment_count: int | None = None
    share_count: int | None = None
    follower_count: int | None = None
    following_count: int | None = None
    content_count: int | None = None


class AgentTag(BaseModel):
    id: str
    name: str


class AgentContent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    content_type: str
    title: str | None
    description: str | None
    author_id: str | None
    author_name: str | None
    published_at: str | None
    first_collected_at: str
    last_collected_at: str
    source_keyword: str | None
    is_favorite: bool
    tags: list[AgentTag] = Field(default_factory=list)
    source: AgentSource
    metrics: AgentMetricSet


class AgentProvenance(BaseModel):
    task_id: str
    collected_at: str


class AgentComment(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_id: str
    source_content_id: str
    parent_comment_id: str | None
    author_id: str | None
    author_name: str | None
    body: str
    like_count: int | None
    reply_count: int | None
    published_at: str | None
    collected_at: str
    platform: str


class AgentCreator(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str | None
    description: str | None
    first_collected_at: str
    last_collected_at: str
    source: AgentSource
    metrics: AgentMetricSet


class AgentContentDetail(AgentContent):
    creator: AgentCreator | None
    comments: list[AgentComment]
    provenance: list[AgentProvenance]


class AgentCreatorDetail(AgentCreator):
    recent_contents: list[AgentContent]
    provenance: list[AgentProvenance]


class PageMeta(BaseModel):
    offset: int
    limit: int
    next_offset: int
    has_more: bool


DataT = TypeVar("DataT")


class ApiData(BaseModel, Generic[DataT]):
    data: DataT


class ApiPage(BaseModel, Generic[DataT]):
    data: list[DataT]
    meta: PageMeta


class ApiErrorDetail(BaseModel):
    code: str
    message: str


class ApiError(BaseModel):
    error: ApiErrorDetail
