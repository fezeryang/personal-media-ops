from typing import Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)

ScheduleType = Literal[
    "manual",
    "every_6_hours",
    "daily",
    "weekdays",
    "weekly",
]
RunStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "partial",
    "failed",
    "cancelled",
]


class ScheduleConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    time_of_day: str | None = Field(
        default=None,
        pattern=r"^(?:[01]\d|2[0-3]):[0-5]\d$",
    )
    weekday: int | None = Field(default=None, ge=0, le=6)


class SubscriptionPlatformInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    platform: str = Field(min_length=2, max_length=32, pattern=r"^[a-z][a-z0-9_-]+$")
    requested_count: int = Field(ge=1, le=20)


class SubscriptionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    query: str = Field(min_length=1, max_length=200)
    platforms: list[SubscriptionPlatformInput] = Field(min_length=1, max_length=7)
    enabled: bool = True
    schedule_type: ScheduleType
    schedule_config: ScheduleConfig
    timezone: str = Field(min_length=1, max_length=100)

    @field_validator("name", "query")
    @classmethod
    def printable_trimmed(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("value must be printable and non-blank")
        return normalized

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value

    @field_validator("platforms")
    @classmethod
    def unique_platforms(
        cls,
        value: list[SubscriptionPlatformInput],
    ) -> list[SubscriptionPlatformInput]:
        platforms = [item.platform for item in value]
        if len(platforms) != len(set(platforms)):
            raise ValueError("platforms must be unique")
        return value

    @model_validator(mode="after")
    def validate_schedule(self) -> "SubscriptionWrite":
        time_required = self.schedule_type in {"daily", "weekdays", "weekly"}
        if time_required != (self.schedule_config.time_of_day is not None):
            raise ValueError(
                f"{self.schedule_type} schedule has invalid time_of_day"
            )
        weekday_required = self.schedule_type == "weekly"
        if weekday_required != (self.schedule_config.weekday is not None):
            raise ValueError(
                f"{self.schedule_type} schedule has invalid weekday"
            )
        return self


class SubscriptionPlatform(BaseModel):
    platform: str
    requested_count: int


class SubscriptionRunPlatform(BaseModel):
    platform: str
    sequence: int
    task_id: str
    task_status: str
    new_content_count: int
    existing_content_count: int
    changed_content_count: int
    error_summary: str | None


class SubscriptionRun(BaseModel):
    id: str
    subscription_id: str
    scheduled_for: str
    trigger: Literal["manual", "scheduled"]
    status: RunStatus
    started_at: str | None
    finished_at: str | None
    new_content_count: int
    existing_content_count: int
    changed_content_count: int
    error_summary: str | None
    created_at: str
    platform_results: list[SubscriptionRunPlatform]


class Subscription(BaseModel):
    id: str
    name: str
    query: str
    platforms: list[SubscriptionPlatform]
    enabled: bool
    schedule_type: ScheduleType
    schedule_config: ScheduleConfig
    timezone: str
    last_run_at: str | None
    next_run_at: str | None
    last_success_at: str | None
    consecutive_failures: int
    last_error: str | None
    created_at: str
    updated_at: str


class SubscriptionDetail(Subscription):
    runs: list[SubscriptionRun]


class WatchlistWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    creator_id: str = Field(min_length=1, max_length=100)
    enabled: bool = False
    check_frequency: Literal["every_6_hours", "daily", "weekly"]
    requested_count: int = Field(default=3, ge=1, le=5)
    timezone: str = Field(min_length=1, max_length=100)

    @field_validator("timezone")
    @classmethod
    def valid_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as error:
            raise ValueError("timezone must be a valid IANA timezone") from error
        return value


class WatchRun(BaseModel):
    id: str
    watch_id: str
    scheduled_for: str
    trigger: Literal["manual", "scheduled"]
    task_id: str
    status: str
    started_at: str | None
    finished_at: str | None
    new_content_count: int
    existing_content_count: int
    changed_content_count: int
    error_summary: str | None
    created_at: str


class WatchlistItem(BaseModel):
    id: str
    creator_id: str
    platform: str
    creator_name: str | None
    enabled: bool
    check_frequency: str
    requested_count: int
    timezone: str
    last_checked_at: str | None
    next_check_at: str | None
    last_success_at: str | None
    consecutive_failures: int
    last_error: str | None
    created_at: str
    updated_at: str
    runs: list[WatchRun] = Field(default_factory=list)


class AutomationEnabledWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    enabled: bool
