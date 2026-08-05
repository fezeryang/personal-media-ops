from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MonitoringMissionType = Literal[
    "topic",
    "entity",
    "creator",
    "event",
    "research_question",
    "query",
]
MonitoringMissionStatus = Literal[
    "draft",
    "active",
    "paused",
    "running",
    "waiting_platform",
    "waiting_login",
    "completed_run",
    "degraded",
    "failed",
    "archived",
]
MonitoringScheduleType = Literal["manual", "daily", "weekly", "custom"]
MonitoringRunStatus = Literal[
    "queued",
    "running",
    "waiting_platform",
    "waiting_login",
    "completed",
    "no_meaningful_change",
    "degraded",
    "failed",
    "cancelled",
]
AttentionLevel = Literal[
    "immediate_attention",
    "daily_digest",
    "normal_record",
    "silent_memory",
    "ignored",
]
NotificationStatus = Literal["unread", "read", "deferred", "ignored"]


class MonitoringTargetInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_type: MonitoringMissionType
    target_value: str = Field(min_length=1, max_length=300)

    @field_validator("target_value")
    @classmethod
    def normalize_target(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("target_value must be printable and non-blank")
        return normalized


class MonitoringBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    max_model_calls: int = Field(default=4, ge=0, le=20)
    max_total_tokens: int = Field(default=8_000, ge=0, le=100_000)
    max_collection_count: int = Field(default=3, ge=0, le=20)
    max_platforms: int = Field(default=3, ge=0, le=7)
    max_runtime_seconds: int = Field(default=300, ge=1, le=3_600)
    daily_token_budget: int = Field(default=20_000, ge=0, le=1_000_000)
    weekly_run_budget: int = Field(default=7, ge=1, le=31)


class MonitoringMissionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    goal: str = Field(min_length=5, max_length=10_000)
    title: str | None = Field(default=None, max_length=200)
    mission_type: MonitoringMissionType = "research_question"
    targets: list[MonitoringTargetInput] = Field(default_factory=list, max_length=8)
    platforms: list[str] = Field(default_factory=list, max_length=7)
    schedule_type: MonitoringScheduleType = "manual"
    schedule_config: dict[str, object] = Field(default_factory=dict)
    importance_rule: str | None = Field(default=None, max_length=1_000)
    ignored_content_rule: str | None = Field(default=None, max_length=1_000)
    budget: MonitoringBudget = Field(default_factory=MonitoringBudget)
    confirmed: bool = False

    @field_validator("goal")
    @classmethod
    def normalize_goal(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("goal must be printable and non-blank")
        return normalized

    @field_validator("platforms")
    @classmethod
    def normalize_platforms(cls, values: list[str]) -> list[str]:
        normalized = [value.strip().casefold() for value in values]
        if any(not value or not value.isprintable() for value in normalized):
            raise ValueError("platforms must be printable and non-blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("platforms must be unique")
        return normalized


class MonitoringMissionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    title: str | None = Field(default=None, max_length=200)
    schedule_type: MonitoringScheduleType | None = None
    schedule_config: dict[str, object] | None = None
    platforms: list[str] | None = Field(default=None, max_length=7)
    importance_rule: str | None = Field(default=None, max_length=1_000)
    ignored_content_rule: str | None = Field(default=None, max_length=1_000)
    budget: MonitoringBudget | None = None


class MonitoringMissionSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    title: str
    goal: str
    mission_type: MonitoringMissionType
    status: MonitoringMissionStatus
    schedule_type: MonitoringScheduleType
    schedule_config: dict[str, object]
    platforms: list[str]
    understanding: dict[str, object]
    budget: MonitoringBudget
    next_run_at: str | None
    last_run_at: str | None
    last_run_status: str | None
    latest_change: dict[str, object] | None
    created_at: str
    updated_at: str


class MonitoringMissionDetail(MonitoringMissionSummary):
    targets: list[dict[str, object]]
    importance_rule: str | None
    ignored_content_rule: str | None
    consecutive_failures: int
    last_error: str | None


class MonitoringRun(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mission_id: str
    research_task_id: str | None
    status: MonitoringRunStatus
    trigger: str
    started_at: str | None
    completed_at: str | None
    baseline_created: bool
    change_count: int
    notification_count: int
    resource: dict[str, object]
    failure_reason: str | None
    backoff_until: str | None
    claimed_at: str | None
    created_at: str
    queries: list[dict[str, object]]


class MonitoringChange(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    source_type: Literal["monitoring"] = "monitoring"
    mission_id: str
    run_id: str
    change_type: str
    fingerprint: str
    title: str
    summary: str
    first_seen_at: str | None
    latest_seen_at: str | None
    relevance_score: float
    novelty_score: float
    evidence_strength_score: float
    source_independence_score: float
    cross_platform_score: float
    actionability_score: float
    persistence_score: float
    noise_risk_score: float
    attention_level: AttentionLevel
    state: Literal["new", "read", "deferred", "ignored", "merged"]
    explanation: dict[str, object]
    sources: list[dict[str, object]]
    memory_update: dict[str, object] | None
    created_at: str
    updated_at: str


class MonitoringNotification(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mission_id: str
    change_id: str
    level: AttentionLevel
    status: NotificationStatus
    title: str
    summary: str
    created_at: str
    read_at: str | None
    deferred_until: str | None
    ignored_at: str | None


class MonitoringBaseline(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    mission_id: str
    version: int
    snapshot: dict[str, object]
    source_run_id: str | None
    created_at: str


class MonitoringRunResult(MonitoringRun):
    baseline: MonitoringBaseline | None = None
    changes: list[dict[str, object]] = Field(default_factory=list)
    outcome: str


class NotificationAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    until: str | None = Field(default=None, max_length=80)
