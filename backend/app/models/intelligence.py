from datetime import UTC, datetime, timedelta
from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class TrendGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_end: datetime
    window_hours: int = Field(default=24, ge=6, le=168)

    @field_validator("window_end")
    @classmethod
    def utc_window_end(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


class TrendSignal(BaseModel):
    id: str
    topic: str
    window_start: str
    window_end: str
    score: float
    volume_score: float
    velocity_score: float
    cross_platform_score: float
    engagement_score: float
    platforms: list[str]
    content_ids: list[str]
    explanation: str
    evidence: dict[str, object]
    status: Literal["detected", "insufficient_data"]
    formula_version: str
    created_at: str


class BriefGenerateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    window_start: datetime
    window_end: datetime
    timezone: str = Field(min_length=1, max_length=100)
    regenerate: bool = False

    @field_validator("window_start", "window_end")
    @classmethod
    def utc_timestamp(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value

    @model_validator(mode="after")
    def ordered_window(self) -> "BriefGenerateRequest":
        if self.window_end <= self.window_start:
            raise ValueError("window_end must be after window_start")
        if self.window_end - self.window_start > timedelta(days=31):
            raise ValueError("brief window must not exceed 31 days")
        return self


class BriefItem(BaseModel):
    id: str
    section: str
    conclusion_type: Literal[
        "fact",
        "calculation",
        "rule",
        "insufficient_data",
        "unknown",
    ]
    title: str
    body: str
    position: int
    evidence: dict[str, object]
    content_ids: list[str]
    trend_ids: list[str]


class Brief(BaseModel):
    id: str
    window_start: str
    window_end: str
    timezone: str
    version: int
    generator: Literal["deterministic", "ai_enhanced"]
    ai_provider: str
    status: str
    created_at: str
    evidence_count: int
    items: list[BriefItem]


class BriefScheduleWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
    timezone: str = Field(min_length=1, max_length=100)
    time_of_day: str = Field(pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$")

    @field_validator("timezone")
    @classmethod
    def schedule_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value


class BriefSchedule(BriefScheduleWrite):
    id: str
    last_run_at: str | None
    next_run_at: str | None
    consecutive_failures: int
    last_error: str | None
    created_at: str
    updated_at: str
