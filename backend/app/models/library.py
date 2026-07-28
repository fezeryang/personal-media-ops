from typing import Literal

from pydantic import BaseModel, ConfigDict

LibraryEntityType = Literal["content", "creator", "comment"]


class NormalizedContent(BaseModel):
    platform: str
    source_content_id: str
    content_type: str
    title: str | None
    description: str | None
    source_url: str | None
    cover_url: str | None
    author_source_id: str | None
    author_name: str | None
    published_at: int | None
    source_keyword: str | None
    view_count: int | None
    like_count: int | None
    favorite_count: int | None
    comment_count: int | None
    share_count: int | None
    raw_payload: dict[str, object]


class NormalizedCreator(BaseModel):
    platform: str
    source_creator_id: str
    display_name: str | None
    profile_url: str | None
    avatar_url: str | None
    description: str | None
    follower_count: int | None
    following_count: int | None
    content_count: int | None
    raw_payload: dict[str, object]


class NormalizedComment(BaseModel):
    platform: str
    source_comment_id: str
    source_content_id: str
    parent_comment_id: str | None
    author_source_id: str | None
    author_name: str | None
    body: str
    like_count: int | None
    reply_count: int | None
    published_at: int | None
    raw_payload: dict[str, object]


class LibraryContentSummary(BaseModel):
    id: str
    platform: str
    source_content_id: str
    content_type: str
    title: str | None
    description: str | None
    source_url: str | None
    cover_url: str | None
    author_source_id: str | None
    author_name: str | None
    published_at: str | None
    first_collected_at: str
    last_collected_at: str
    source_keyword: str | None
    view_count: int | None
    like_count: int | None
    favorite_count: int | None
    comment_count: int | None
    share_count: int | None
    has_comments: bool
    created_at: str | None = None
    updated_at: str | None = None


class TaskProvenance(BaseModel):
    task_id: str
    collected_at: str


class LibraryCreatorSummary(BaseModel):
    id: str
    platform: str
    source_creator_id: str
    display_name: str | None
    profile_url: str | None
    avatar_url: str | None
    description: str | None
    follower_count: int | None
    following_count: int | None
    content_count: int | None
    first_collected_at: str
    last_collected_at: str
    created_at: str | None = None
    updated_at: str | None = None


class LibraryCommentSummary(BaseModel):
    id: str
    platform: str
    source_comment_id: str
    source_content_id: str
    parent_comment_id: str | None
    author_source_id: str | None
    author_name: str | None
    body: str
    like_count: int | None
    reply_count: int | None
    published_at: str | None
    collected_at: str


class LibraryContentDetail(LibraryContentSummary):
    model_config = ConfigDict(extra="forbid")

    raw_payload: dict[str, object] | None = None
    creator: LibraryCreatorSummary | None
    comments: list[LibraryCommentSummary]
    tasks: list[TaskProvenance]


class LibraryCreatorDetail(LibraryCreatorSummary):
    model_config = ConfigDict(extra="forbid")

    raw_payload: dict[str, object] | None = None
    contents: list[LibraryContentSummary]
    tasks: list[TaskProvenance]


class LibraryContentPage(BaseModel):
    items: list[LibraryContentSummary]
    offset: int
    limit: int
    next_offset: int
    has_more: bool


class LibraryCreatorPage(BaseModel):
    items: list[LibraryCreatorSummary]
    offset: int
    limit: int
    next_offset: int
    has_more: bool


class LibraryCommentPage(BaseModel):
    items: list[LibraryCommentSummary]
    offset: int
    limit: int
    next_offset: int
    has_more: bool


class LibraryStats(BaseModel):
    contents: int
    creators: int
    comments: int
