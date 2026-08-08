from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

OpportunityType = Literal[
    "product_opportunity",
    "business_opportunity",
    "content_opportunity",
    "research_opportunity",
]
OpportunityStatus = Literal[
    "weak_signal",
    "evidence_building",
    "candidate",
    "review_ready",
    "validation_ready",
    "accepted",
    "rejected",
    "deferred",
    "validating",
    "validated",
    "invalidated",
    "converted_to_action",
    "archived",
]
OpportunityReadiness = Literal[
    "insufficient_evidence",
    "needs_more_evidence",
    "review_ready",
    "validation_ready",
    "validated",
]
OpportunitySignalType = Literal[
    "pain_point", "unmet_need", "workflow_friction", "repeated_complaint",
    "behavior_shift", "new_tool_category", "product_gap", "feature_request",
    "switching_signal", "pricing_friction", "complexity_friction", "trust_issue",
    "content_gap", "knowledge_gap", "emerging_interest",
]
OpportunityFeedbackType = Literal[
    "valuable", "irrelevant", "evidence_insufficient", "already_known", "defer",
    "reject", "continue_research", "create_validation_plan", "add_to_space",
    "lower_priority",
]
ValidationPlanStatus = Literal["draft", "ready", "in_progress", "completed", "abandoned"]
ValidationOutcome = Literal["supported", "partially_supported", "not_supported", "inconclusive"]
ActionType = Literal[
    "research", "validate", "prototype", "interview", "compare", "write",
    "review", "monitor", "manual_other",
]
ActionStatus = Literal["proposed", "approved", "in_progress", "completed", "abandoned"]
SourceRole = Literal["core", "supporting", "counterevidence", "background"]
EvidenceKind = Literal["direct", "inference", "estimate", "unknown"]


def _text(value: str | None) -> str | None:
    if value is None:
        return None
    normalized = value.strip()
    if not normalized or not normalized.isprintable():
        raise ValueError("text must be printable and non-blank")
    return normalized


class OpportunitySignalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    signal_type: OpportunitySignalType
    title: str = Field(min_length=2, max_length=300)
    summary: str = Field(min_length=5, max_length=4_000)
    evidence_id: str | None = Field(default=None, max_length=300)
    content_id: str | None = Field(default=None, max_length=200)
    finding_id: str | None = Field(default=None, max_length=200)
    discovery_candidate_id: str | None = Field(default=None, max_length=200)
    monitoring_change_id: str | None = Field(default=None, max_length=200)
    source_type: str = Field(min_length=2, max_length=80)
    source_id: str = Field(min_length=1, max_length=300)
    source_platform: str | None = Field(default=None, max_length=40)
    source_url: str | None = Field(default=None, max_length=2_000)
    entity_key: str | None = Field(default=None, max_length=300)
    event_key: str | None = Field(default=None, max_length=300)
    observed_at: str | None = Field(default=None, max_length=80)
    aggregation_key: str | None = Field(default=None, max_length=300)
    metadata: dict[str, object] = Field(default_factory=dict)

    _normalize = field_validator(
        "title", "summary", "evidence_id", "content_id", "finding_id",
        "discovery_candidate_id", "monitoring_change_id", "source_type", "source_id",
        "source_platform", "source_url", "entity_key", "event_key", "observed_at",
        "aggregation_key",
    )(_text)


class OpportunityCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_type: OpportunityType
    title: str = Field(min_length=2, max_length=300)
    description: str = Field(min_length=5, max_length=8_000)
    target_user: str = Field(min_length=2, max_length=1_000)
    problem: str = Field(min_length=2, max_length=4_000)
    why_attention: str = Field(min_length=2, max_length=4_000)
    why_now: str = Field(min_length=2, max_length=4_000)
    next_step: str = Field(min_length=2, max_length=2_000)
    unknowns: list[str] = Field(default_factory=list, max_length=20)
    content_details: dict[str, object] = Field(default_factory=dict)
    related_research_task_id: str | None = None
    related_monitoring_mission_id: str | None = None
    related_monitoring_change_id: str | None = None
    related_discovery_candidate_id: str | None = None
    research_space_id: str | None = None
    sources: list[OpportunitySourceInput] = Field(min_length=1, max_length=50)

    _normalize = field_validator(
        "title", "description", "target_user", "problem", "why_attention", "why_now", "next_step",
    )(_text)


class OpportunitySourceInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: str = Field(min_length=2, max_length=80)
    source_id: str = Field(min_length=1, max_length=300)
    source_role: SourceRole = "supporting"
    evidence_kind: EvidenceKind = "unknown"
    support_explanation: str = Field(min_length=2, max_length=1_000)
    signal_id: str | None = None
    evidence_id: str | None = None
    content_id: str | None = None
    finding_id: str | None = None
    source_platform: str | None = None
    source_url: str | None = None
    source_title: str | None = None
    independent_group: str | None = None
    is_repost: bool = False

    _normalize = field_validator(
        "source_type", "source_id", "support_explanation", "signal_id", "evidence_id",
        "content_id", "finding_id", "source_platform", "source_url", "source_title",
        "independent_group",
    )(_text)


class OpportunityFeedbackRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    feedback_type: OpportunityFeedbackType
    note: str | None = Field(default=None, max_length=2_000)

    _normalize = field_validator("note")(_text)


class ValidationPlanCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_hypothesis: str | None = Field(default=None, max_length=2_000)
    target_user: str | None = Field(default=None, max_length=1_000)
    problem_hypothesis: str | None = Field(default=None, max_length=2_000)
    value_hypothesis: str | None = Field(default=None, max_length=2_000)
    critical_assumptions: list[str] | None = Field(default=None, max_length=12)
    unknowns: list[str] | None = Field(default=None, max_length=20)
    validation_questions: list[str] | None = Field(default=None, max_length=20)
    evidence_needed: list[str] | None = Field(default=None, max_length=20)
    cheapest_next_test: str | None = Field(default=None, max_length=2_000)
    success_criteria: list[str] | None = Field(default=None, max_length=12)
    failure_criteria: list[str] | None = Field(default=None, max_length=12)
    estimated_effort: str | None = Field(default=None, max_length=300)
    risk: str | None = Field(default=None, max_length=1_000)
    next_decision: str | None = Field(default=None, max_length=1_000)

    _normalize = field_validator(
        "opportunity_hypothesis", "target_user", "problem_hypothesis", "value_hypothesis",
        "cheapest_next_test", "estimated_effort", "risk", "next_decision",
    )(_text)


class ValidationResultCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    outcome: ValidationOutcome
    what_happened: str = Field(min_length=2, max_length=4_000)
    result: str = Field(min_length=2, max_length=4_000)
    evidence: list[dict[str, object]] = Field(default_factory=list, max_length=30)
    user_notes: str | None = Field(default=None, max_length=2_000)
    next_step: str = Field(min_length=2, max_length=2_000)

    _normalize = field_validator("what_happened", "result", "user_notes", "next_step")(_text)


class ActionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    opportunity_id: str | None = None
    validation_plan_id: str | None = None
    source_type: str = Field(min_length=2, max_length=80)
    source_id: str = Field(min_length=1, max_length=300)
    action_type: ActionType
    title: str = Field(min_length=2, max_length=300)
    why: str = Field(min_length=2, max_length=2_000)
    expected_result: str = Field(min_length=2, max_length=2_000)
    success_criteria: str = Field(min_length=2, max_length=2_000)
    user_notes: str | None = Field(default=None, max_length=2_000)

    _normalize = field_validator(
        "opportunity_id", "validation_plan_id", "source_type", "source_id", "title", "why",
        "expected_result", "success_criteria", "user_notes",
    )(_text)


class ActionUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["approved", "in_progress", "completed", "abandoned"]
    user_notes: str | None = Field(default=None, max_length=2_000)

    _normalize = field_validator("user_notes")(_text)


class OutcomeCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    what_happened: str = Field(min_length=2, max_length=4_000)
    result: str = Field(min_length=2, max_length=4_000)
    evidence: list[dict[str, object]] = Field(default_factory=list, max_length=30)
    metrics: dict[str, object] = Field(default_factory=dict)
    lesson: str = Field(min_length=2, max_length=2_000)
    next_step: str = Field(min_length=2, max_length=2_000)
    published_url: str | None = Field(default=None, max_length=2_000)
    manual_views: int | None = Field(default=None, ge=0, le=2_147_483_647)
    manual_engagement: int | None = Field(default=None, ge=0, le=2_147_483_647)
    user_observation: str | None = Field(default=None, max_length=2_000)

    _normalize = field_validator(
        "what_happened", "result", "lesson", "next_step", "published_url", "user_observation",
    )(_text)


class OpportunitySignal(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    signal_type: OpportunitySignalType
    title: str
    summary: str
    evidence_id: str | None
    content_id: str | None
    finding_id: str | None
    discovery_candidate_id: str | None
    monitoring_change_id: str | None
    source_type: str
    source_id: str
    source_platform: str | None
    source_url: str | None
    entity_key: str | None
    event_key: str | None
    observed_at: str | None
    aggregation_key: str
    status: Literal["active", "archived"]
    metadata: dict[str, object]
    created_at: str
    updated_at: str


class OpportunitySource(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    signal_id: str | None
    source_type: str
    source_id: str
    evidence_id: str | None
    content_id: str | None
    finding_id: str | None
    source_role: SourceRole
    evidence_kind: EvidenceKind
    support_explanation: str
    source_platform: str | None
    source_url: str | None
    source_title: str | None
    independent_group: str | None
    is_repost: bool
    created_at: str


class OpportunityVersion(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int
    snapshot: dict[str, object]
    readiness_before: OpportunityReadiness | None
    readiness_after: OpportunityReadiness
    change_reason: str
    created_at: str


class OpportunityScore(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    version: int
    scores: dict[str, float]
    explanation: dict[str, object]
    readiness: OpportunityReadiness
    created_at: str


class OpportunityFeedback(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    opportunity_id: str
    feedback_type: OpportunityFeedbackType
    note: str | None
    undone_at: str | None
    created_at: str


class OpportunitySummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    opportunity_type: OpportunityType
    title: str
    description: str
    target_user: str
    problem: str
    why_attention: str
    why_now: str
    next_step: str
    status: OpportunityStatus
    readiness: OpportunityReadiness
    version: int
    scores: dict[str, float]
    score_explanation: dict[str, object]
    unknowns: list[str]
    content_details: dict[str, object]
    related_research_task_id: str | None
    related_monitoring_mission_id: str | None
    related_monitoring_change_id: str | None
    related_discovery_candidate_id: str | None
    research_space_id: str | None
    created_at: str
    updated_at: str


class ValidationPlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    opportunity_id: str
    source_version: int
    status: ValidationPlanStatus
    opportunity_hypothesis: str
    target_user: str
    problem_hypothesis: str
    value_hypothesis: str
    critical_assumptions: list[str]
    unknowns: list[str]
    validation_questions: list[str]
    evidence_needed: list[str]
    cheapest_next_test: str
    success_criteria: list[str]
    failure_criteria: list[str]
    estimated_effort: str
    risk: str
    next_decision: str
    approved_at: str | None
    created_at: str
    updated_at: str
    results: list[dict[str, object]] = Field(default_factory=list)


class OpportunityAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    opportunity_id: str | None
    validation_plan_id: str | None
    source_type: str
    source_id: str
    action_type: ActionType
    title: str
    why: str
    expected_result: str
    success_criteria: str
    status: ActionStatus
    user_notes: str | None
    started_at: str | None
    completed_at: str | None
    created_at: str
    updated_at: str
    outcomes: list[dict[str, object]] = Field(default_factory=list)


class OpportunityDetail(OpportunitySummary):
    sources: list[OpportunitySource] = Field(default_factory=list)
    versions: list[OpportunityVersion] = Field(default_factory=list)
    score_history: list[OpportunityScore] = Field(default_factory=list)
    feedback: list[OpportunityFeedback] = Field(default_factory=list)
    validation_plans: list[ValidationPlan] = Field(default_factory=list)
    actions: list[OpportunityAction] = Field(default_factory=list)


class OpportunityAnalysisRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_type: Literal["research_task", "discovery_candidate", "monitoring_change", "research_space", "manual"]
    source_id: str = Field(min_length=1, max_length=300)
    opportunity_type: OpportunityType = "product_opportunity"


class OpportunityAnalysisResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: Literal["opportunity_identified", "no_opportunity_identified", "needs_more_evidence"]
    explanation: str
    signal_count: int = Field(ge=0)
    independent_source_count: int = Field(ge=0)
    opportunities: list[OpportunitySummary] = Field(default_factory=list)


OpportunityCreate.model_rebuild()
