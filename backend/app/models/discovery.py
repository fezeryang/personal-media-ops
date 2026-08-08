from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DiscoveryCandidateType = Literal[
    "entity",
    "creator",
    "topic",
    "event",
    "query",
    "pain_point",
    "need",
    "product_opportunity_signal",
    "content_opportunity_signal",
]
DiscoveryCandidateState = Literal[
    "generated",
    "scored",
    "queued",
    "accepted",
    "ignored",
    "deferred",
    "converted_to_research",
    "added_to_space",
    "dismissed_duplicate",
    "expired",
]
DiscoveryFeedbackType = Literal[
    "valuable",
    "irrelevant",
    "already_known",
    "duplicate",
    "follow",
    "mute_topic",
    "deprioritize_similar",
    "needs_more_evidence",
    "converted_to_research",
    "added_to_space",
]
DiscoveryFeedbackScope = Literal[
    "global",
    "platform",
    "research_intent",
    "research_space",
    "topic",
]
ResearchSpaceItemType = Literal[
    "research_task",
    "discovery_candidate",
    "evidence",
    "entity",
    "event",
    "finding",
    "unresolved_question",
    "memory",
    "opportunity",
    "validation_plan",
    "action",
    "outcome",
]


class DiscoveryCandidateSource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    seed_id: str | None = None
    research_task_id: str
    content_id: str | None = None
    platform: str | None = None
    source_kind: str
    source_title: str | None = None
    source_author: str | None = None
    source_url: str | None = None
    is_repost: bool = False
    repost_of_content_id: str | None = None
    similarity_score: float | None = Field(default=None, ge=0, le=1)
    independent_group: str | None = None
    created_at: str


class DiscoveryCandidateScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    candidate_id: str
    scoring_version: str
    final_score: float = Field(ge=0, le=1)
    components: dict[str, object]
    explanation: dict[str, object]
    created_at: str


class DiscoveryFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    candidate_id: str | None = None
    target_type: str
    target_key: str
    feedback_type: DiscoveryFeedbackType
    scope: DiscoveryFeedbackScope
    scope_key: str | None = None
    weight: float = Field(ge=-1, le=1)
    reason: str | None = None
    follow_up_task_id: str | None = None
    undone_at: str | None = None
    created_at: str


class DiscoveryCandidateSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    candidate_type: DiscoveryCandidateType
    title: str
    summary: str
    normalized_key: str
    parent_candidate_id: str | None = None
    source_seed_id: str | None = None
    source_content_id: str | None = None
    source_platform: str | None = None
    relevance_score: float = Field(ge=0, le=1)
    novelty_score: float = Field(ge=0, le=1)
    evidence_strength_score: float = Field(ge=0, le=1)
    source_independence_score: float = Field(ge=0, le=1)
    cross_platform_score: float = Field(ge=0, le=1)
    counterevidence_score: float = Field(ge=0, le=1)
    actionability_score: float = Field(ge=0, le=1)
    feedback_score: float = Field(ge=0, le=1)
    noise_risk_score: float = Field(ge=0, le=1)
    marketing_risk_score: float = Field(ge=0, le=1)
    saturation_score: float = Field(ge=0, le=1)
    resource_cost_score: float = Field(ge=0, le=1)
    final_score: float = Field(ge=0, le=1)
    score_explanation: dict[str, object] = Field(default_factory=dict)
    content_count: int = Field(ge=0)
    independent_source_count: int = Field(ge=0)
    platform_count: int = Field(ge=0)
    suspected_repost_count: int = Field(ge=0)
    depth: int = Field(ge=0, le=1)
    state: DiscoveryCandidateState
    suggested_next_action: str | None = None
    experimental_status: str | None = None
    created_at: str
    updated_at: str


class DiscoveryInboxItem(DiscoveryCandidateSummary):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["discovery", "monitoring"]
    research_task_id: str | None
    mission_id: str | None = None
    attention_level: str | None = None
    change_type: str | None = None
    source_mission_title: str | None = None


class DiscoveryCandidateDetail(DiscoveryCandidateSummary):
    sources: list[DiscoveryCandidateSource] = Field(default_factory=list)
    scores: list[DiscoveryCandidateScore] = Field(default_factory=list)
    feedback: list[DiscoveryFeedback] = Field(default_factory=list)
    lifecycle: list[dict[str, object]] = Field(default_factory=list)


class DiscoveryFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_type: DiscoveryFeedbackType | None = None
    scope: DiscoveryFeedbackScope = "global"
    scope_key: str | None = Field(default=None, max_length=300)
    reason: str | None = Field(default=None, max_length=1_000)
    weight: float = Field(default=1, ge=-1, le=1)
    undo_feedback_id: str | None = None

    @field_validator("reason", "scope_key", "undo_feedback_id")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class DiscoveryContinueRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str | None = Field(default=None, min_length=5, max_length=10_000)

    @field_validator("request")
    @classmethod
    def normalize_request(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("request must be printable and non-blank")
        return normalized


class DiscoveryAddToSpaceRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    space_id: str = Field(min_length=1, max_length=200)
    position: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=2_000)

    @field_validator("space_id", "note")
    @classmethod
    def normalize_space_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("space text must be printable and non-blank")
        return normalized


class ResearchSpaceCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2_000)

    @field_validator("name", "description")
    @classmethod
    def normalize_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("space text must be printable and non-blank")
        return normalized


class ResearchSpaceItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: ResearchSpaceItemType
    item_id: str = Field(min_length=1, max_length=200)
    position: int = Field(default=0, ge=0)
    note: str | None = Field(default=None, max_length=2_000)

    @field_validator("item_id", "note")
    @classmethod
    def normalize_item_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("space item text must be printable and non-blank")
        return normalized


class ResearchSpaceItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    space_id: str
    item_type: ResearchSpaceItemType
    item_id: str
    position: int = Field(ge=0)
    note: str | None = None
    source_candidate_id: str | None = None
    item: dict[str, object] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class ResearchSpaceItemLookup(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item_type: ResearchSpaceItemType
    item_id: str
    title: str
    summary: str | None = None
    source_type: str | None = None
    updated_at: str


class ResearchSpaceSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    description: str | None
    status: Literal["active", "archived"]
    item_count: int = Field(ge=0)
    created_at: str
    updated_at: str


class ResearchSpaceDetail(ResearchSpaceSummary):
    items: list[ResearchSpaceItem] = Field(default_factory=list)


class ResearchPreferences(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feature_flags: dict[str, bool]
    rules: list[dict[str, object]] = Field(default_factory=list)
