from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ResearchIntentType = Literal[
    "discovery",
    "verification",
    "comparison",
    "trend_tracking",
    "pain_point_research",
    "competitor_scan",
    "creator_scan",
    "content_opportunity",
    "market_mapping",
    "product_opportunity",
    "monitoring",
]

IntentSource = Literal["model", "fallback_default", "legacy_migrated", "owner_revised"]
UnknownStatus = Literal["open", "discovered", "verified", "unresolved"]
UtilityType = Literal[
    "core_evidence",
    "discovery_seed",
    "background_context",
    "event_signal",
    "counterevidence",
    "memory_update",
    "action_trigger",
    "noise",
    "duplicate",
]


class ResearchIntentContract(BaseModel):
    model_config = ConfigDict(extra="forbid")

    original_request: str
    original_intent: str
    interpreted_goal: str
    primary_intent: ResearchIntentType
    secondary_intents: list[ResearchIntentType] = Field(default_factory=list)
    subject: dict[str, object] = Field(default_factory=dict)
    known_entities: list[object] = Field(default_factory=list)
    known_constraints: list[object] = Field(default_factory=list)
    unknowns_to_discover: list[str] = Field(default_factory=list)
    time_scope: dict[str, object] = Field(default_factory=dict)
    platform_preferences: list[str] = Field(default_factory=list)
    target_audience: str | None = None
    evidence_requirements: list[str] = Field(default_factory=list)
    negative_evidence_requirements: list[str] = Field(default_factory=list)
    exclusions: list[str] = Field(default_factory=list)
    desired_output: list[str] = Field(default_factory=list)
    success_criteria: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    ambiguities: list[str] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    current_research_hypothesis: str
    intent_revisions: list[dict[str, object]] = Field(default_factory=list)
    intent_source: IntentSource = "fallback_default"
    clarification_question: str | None = None
    id: str | None = None
    research_task_id: str | None = None
    version: int = Field(default=1, ge=1)
    created_at: str
    updated_at: str


class ResearchUnknown(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    unknown: str
    priority: int = Field(ge=0)
    status: UnknownStatus
    evidence_count: int = Field(ge=0)
    resolution: str | None
    created_at: str
    updated_at: str


class ResearchAlignmentReview(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    alignment_score: float = Field(ge=0, le=1)
    covered_requirements: list[str]
    missing_requirements: list[str]
    scope_drift: dict[str, object]
    recommended_next_step: str | None
    review_status: Literal["passed", "needs_more_research", "partial_completion"]
    created_at: str


class ContentResearchUtility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    content_id: str
    utility_type: UtilityType
    rationale: str
    confidence: float = Field(ge=0, le=1)
    research_query_id: str | None
    source_finding_id: str | None
    created_at: str


class ResearchEntityCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    entity_type: str
    normalized_name: str
    source_content_id: str | None
    relevance_to_intent: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    suggested_next_action: str | None
    status: Literal["candidate_discovery", "accepted", "dismissed"]
    created_at: str
    updated_at: str


class ResearchEventCandidate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    event_type: str
    title: str
    summary: str
    source_content_id: str | None
    confidence: float = Field(ge=0, le=1)
    status: Literal["candidate", "accepted", "dismissed"]
    created_at: str
    updated_at: str


class ResearchMemoryItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str | None
    memory_type: str
    memory_key: str
    value: object
    source_content_id: str | None
    source_query_id: str | None
    source_finding_id: str | None
    source_opportunity_id: str | None = None
    source_action_id: str | None = None
    source_outcome_id: str | None = None
    confidence: float = Field(ge=0, le=1)
    is_current: bool
    created_at: str
    updated_at: str
