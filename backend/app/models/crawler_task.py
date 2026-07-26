from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

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

    platform: Literal["bili"]
    crawler_type: Literal["search"]
    keywords: str = Field(min_length=1, max_length=200)
    requested_count: int = Field(ge=1, le=20)

    @field_validator("keywords")
    @classmethod
    def validate_keywords(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("keywords must not be blank")
        if not stripped.isprintable():
            raise ValueError("keywords must not contain control characters")
        return stripped


class CrawlerTaskResponse(BaseModel):
    id: str
    platform: str
    crawler_type: str
    keywords: str
    login_type: str
    status: TaskStatus
    requested_count: int
    actual_count: int
    output_dir: str
    log_path: str
    qrcode_path: str
    pid: int | None
    error_message: str | None
    created_at: str
    started_at: str | None
    finished_at: str | None
    cancel_requested: bool


class CrawlerResultsResponse(BaseModel):
    items: list[object]
    offset: int
    limit: int
    next_offset: int
    has_more: bool
