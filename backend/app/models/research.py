from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.research_intent import (
    ContentResearchUtility,
    ResearchAlignmentReview,
    ResearchEntityCandidate,
    ResearchEventCandidate,
    ResearchIntentContract,
    ResearchMemoryItem,
    ResearchUnknown,
)

ResearchTaskStatus = Literal[
    "Draft",
    "Planning",
    "Researching",
    "WaitingCrawl",
    "WaitingLogin",
    "Summarizing",
    "AwaitingReview",
    "Done",
    "BudgetExceeded",
    "Failed",
    "Cancelled",
]
FindingKind = Literal["fact", "inference"]
FindingStatus = Literal["active", "superseded"]
ActionStatus = Literal["pending", "approved", "rejected"]
ResearchQueryType = Literal[
    "product",
    "tool",
    "company",
    "creator",
    "person",
    "event",
    "need",
    "scenario",
    "technology",
    "generic_topic",
]
ResearchQueryStatus = Literal[
    "generated",
    "rejected_generic",
    "rejected_duplicate",
    "rejected_low_relevance",
    "rejected_low_value",
    "approved_pending",
    "executing",
    "skipped_budget",
    "skipped_saturation",
    "skipped_low_marginal_value",
    "superseded",
    "cancelled",
    "candidate",
    "approved",
    "rejected",
    "running",
    "completed",
    "failed",
]
ResearchQueryRecordType = Literal["user_goal", "execution_query"]
ResearchQueryGateStatus = Literal[
    "not_applicable",
    "pending",
    "allow",
    "transform",
    "hold",
    "reject",
    "completed",
]
ResearchQueryDecision = Literal["allow", "transform", "hold", "reject"]
ResearchQueryRole = Literal[
    "seed_discovery",
    "entity_expansion",
    "cross_platform_validation",
    "counterevidence",
    "competitor_scan",
    "trend_probe",
    "creator_scan",
    "pain_point_probe",
]
SupportType = Literal["direct", "contextual", "contradictory", "background"]
SupportStrength = Literal["strong", "medium", "weak"]
CounterevidenceStatus = Literal["found", "not_found", "unknown"]
BillingMode = Literal[
    "subscription_fixed",
    "pay_as_you_go",
    "prepaid_balance",
    "quota_bundle",
    "relay",
    "unknown",
]
RoutePolicy = Literal[
    "prefer_subscription",
    "prefer_payg",
    "balanced",
    "quality_first",
    "manual",
]


class ResearchCoveragePlan(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target_platform_count: int = Field(default=3, ge=0, le=7)
    target_entity_count: int = Field(default=3, ge=0, le=100)
    target_negative_evidence_count: int = Field(default=1, ge=0, le=100)
    max_single_entity_evidence_ratio: float = Field(default=0.6, ge=0, le=1)
    target_independent_evidence_count: int = Field(default=5, ge=0, le=10_000)
    target_new_content_count: int = Field(default=5, ge=0, le=10_000)
    low_marginal_value_threshold: float = Field(default=0.1, ge=0, le=1)
    low_marginal_round_limit: int = Field(default=2, ge=1, le=10)
    stop_reason: str | None = None
    completed_at: str | None = None


class ResearchBudget(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crawl_limit: int = Field(default=6, ge=0, le=100)
    content_limit: int = Field(default=100, ge=0, le=10_000)
    duration_seconds: int = Field(default=3_600, ge=1, le=604_800)
    token_limit: int = Field(default=50_000, ge=1, le=10_000_000)
    cost_limit: str | None = Field(default=None, max_length=32)
    cost_currency: str | None = Field(default=None, min_length=3, max_length=12)
    max_input_tokens: int | None = Field(default=None, ge=1, le=10_000_000)
    max_output_tokens: int | None = Field(default=None, ge=1, le=10_000_000)
    max_model_calls: int = Field(default=100, ge=1, le=10_000)
    route_policy: RoutePolicy = "balanced"
    max_total_tokens: int | None = Field(default=None, ge=1, le=10_000_000)
    max_crawl_tasks: int | None = Field(default=None, ge=0, le=100)
    max_new_contents: int | None = Field(default=None, ge=0, le=10_000)
    max_runtime_seconds: int | None = Field(default=None, ge=1, le=604_800)
    max_payg_amount: str | None = Field(default=None, max_length=32)
    currency: str | None = Field(default=None, min_length=3, max_length=12)


class ResearchTaskCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    objective: str = Field(min_length=5, max_length=10_000)
    platforms: list[str] | None = Field(default=None, min_length=1, max_length=7)
    budget: ResearchBudget = Field(default_factory=ResearchBudget)
    coverage: ResearchCoveragePlan = Field(default_factory=ResearchCoveragePlan)

    @field_validator("objective")
    @classmethod
    def normalize_objective(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("objective must be printable and non-blank")
        return normalized

    @field_validator("platforms")
    @classmethod
    def normalize_platforms(cls, values: list[str] | None) -> list[str] | None:
        if values is None:
            return None
        normalized = [value.strip().casefold() for value in values]
        if any(not value or not value.isprintable() for value in normalized):
            raise ValueError("platforms must be printable and non-blank")
        if len(set(normalized)) != len(normalized):
            raise ValueError("platforms must be unique")
        return normalized


class ResearchTaskControl(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str | None = Field(default=None, max_length=500)


class ResearchIntentRevisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    request: str = Field(min_length=5, max_length=10_000)

    @field_validator("request")
    @classmethod
    def normalize_request(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("request must be printable and non-blank")
        return normalized


class ResearchEvidence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_id: str
    platform: str | None = None
    title: str | None = None
    source_url: str | None = None
    author_name: str | None = None
    published_at: str | None = None
    collected_at: str | None = None
    crawl_task_id: str | None = None
    support_type: SupportType
    support_strength: SupportStrength
    support_explanation: str
    source_independence: Literal["independent", "repost", "unknown"] = "unknown"
    content_completeness: Literal["complete", "partial", "missing", "unknown"] = "unknown"
    evidence_quality: Literal["high", "medium", "low", "unknown"] = "unknown"
    is_repost: bool = False
    occurrences: list[ResearchEvidenceOccurrence] = Field(default_factory=list)


class ResearchEvidenceOccurrence(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    finding_id: str | None
    content_id: str
    crawler_task_id: str | None
    research_query_id: str | None
    first_seen_at: str
    last_seen_at: str
    occurrence_count: int
    source_query_ids: list[str] = Field(default_factory=list)
    source_crawler_task_ids: list[str] = Field(default_factory=list)


class ResearchQuery(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    intent_id: str | None = None
    record_type: ResearchQueryRecordType = "execution_query"
    gate_status: ResearchQueryGateStatus = "pending"
    decision: ResearchQueryDecision = "allow"
    query_role: ResearchQueryRole = "seed_discovery"
    query: str
    normalized_query: str
    query_type: ResearchQueryType
    platform: str
    source_type: str
    source_content_id: str | None
    source_finding_id: str | None
    parent_query_id: str | None
    generation_reason: str
    relevance_score: float | None
    specificity_score: float
    novelty_score: float
    noise_risk_score: float
    expected_value_score: float | None
    status: ResearchQueryStatus
    rejection_reason: str | None
    crawler_task_id: str | None
    executed_at: str | None
    result_count: int
    new_content_count: int
    existing_content_count: int
    updated_content_count: int
    duplicate_evidence_count: int
    lifecycle_status: str | None = None
    unexecuted_reason: str | None = None
    entity_diversity_bonus: float = 0
    platform_diversity_bonus: float = 0
    negative_evidence_bonus: float = 0
    estimated_resource_use: float = 0
    expected_evidence_role: SupportType | None = None
    new_content_rate: float | None = None
    new_entity_count: int | None = None
    new_independent_evidence_count: int | None = None
    duplicate_rate: float | None = None
    marginal_value_score: float | None = None
    created_at: str
    updated_at: str


class ResearchFinding(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    round_number: int
    kind: FindingKind
    statement: str
    derivation: str | None
    counterevidence_status: CounterevidenceStatus
    counterevidence_explanation: str
    status: FindingStatus
    evidence: list[ResearchEvidence]
    created_at: str
    updated_at: str


class ResearchEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    research_task_id: str
    round_number: int
    fingerprint: str
    title: str
    summary: str
    content_ids: list[str]
    created_at: str
    updated_at: str


class ResearchAction(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    action: str
    reason: str
    payload: dict[str, object]
    status: ActionStatus
    created_at: str
    decided_at: str | None


class ResearchTraceEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sequence: int
    event: str
    status: ResearchTaskStatus | None
    reason: str | None
    round_number: int | None
    step: str | None
    tool_name: str | None
    tool_arguments: dict[str, object] | None
    provider: str | None
    model: str | None
    route_role: str | None
    request_correlation_id: str | None
    input_tokens: int | None
    output_tokens: int | None
    elapsed_ms: int | None
    created_at: str


class ResearchConsumption(BaseModel):
    model_config = ConfigDict(extra="forbid")

    crawl_count: int
    content_count: int
    duration_seconds: int
    input_tokens: int
    output_tokens: int
    cached_tokens: int
    estimated_cost: str | None
    cost_enabled: bool
    cost_currency: str | None
    model_call_count: int = 0
    subscription_calls: int = 0
    subscription_tokens: int = 0
    payg_calls: int = 0
    payg_tokens: int = 0
    relay_calls: int = 0
    relay_tokens: int = 0
    uncosted_call_count: int = 0


class ResearchPlatformCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = None
    research_task_id: str | None = None
    platform: str
    order_index: int
    status: str
    planned_query_count: int
    actual_query_count: int
    result_count: int
    new_content_count: int
    independent_evidence_count: int
    negative_evidence_count: int
    failure_reason: str | None
    created_at: str | None = None
    updated_at: str | None = None


class ResearchEntityCoverage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    canonical_name: str
    entity_type: str
    entity_query_count: int
    entity_evidence_count: int
    entity_new_content_count: int
    entity_platform_count: int
    entity_coverage_ratio: float
    saturated: bool


class ResearchContentDecision(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content_id: str
    research_query_id: str | None
    decision: str
    not_adopted_reason: str | None
    source_independence: str
    content_completeness: str
    evidence_quality: str
    is_repost: bool
    repost_of_content_id: str | None
    similarity_score: float | None


class ResearchStepUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    step: str
    sequence: int
    provider_instance_id: str | None
    vendor: str | None
    model: str | None
    billing_mode: BillingMode | None
    estimated_cost: str | None = None
    currency: str | None = None
    price_source: str | None = None
    input_tokens: int | None
    output_tokens: int | None
    cached_tokens: int | None
    latency_ms: int | None
    fallback_from_provider_instance_id: str | None
    fallback_reason: str | None
    invocation_id: str | None
    created_at: str


class ResearchTaskSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    task_type: str
    objective: str
    platforms: list[str]
    status: ResearchTaskStatus
    current_round: int
    current_step: str | None
    paused: bool
    consumption: ResearchConsumption
    finding_count: int
    event_count: int
    action_count: int
    created_at: str
    updated_at: str
    finished_at: str | None
    failure_reason: str | None
    stop_reason: str | None = None
    primary_intent: str | None = None
    intent_confidence: float | None = Field(default=None, ge=0, le=1)


class ResearchTaskDetail(ResearchTaskSummary):
    plan: dict[str, object]
    context: dict[str, object]
    result: dict[str, object] | None
    route_snapshot: dict[str, object]
    budget: ResearchBudget
    coverage: ResearchCoveragePlan
    platform_coverage: list[ResearchPlatformCoverage]
    entity_coverage: list[ResearchEntityCoverage]
    content_decisions: list[ResearchContentDecision]
    step_usage: list[ResearchStepUsage]
    budget_events: list[dict[str, object]]
    trace: list[ResearchTraceEntry]
    findings: list[ResearchFinding]
    queries: list[ResearchQuery]
    events: list[ResearchEvent]
    actions: list[ResearchAction]
    intent_contract: ResearchIntentContract | None = None
    intent_versions: list[dict[str, object]] = Field(default_factory=list)
    intent_assumptions: list[dict[str, object]] = Field(default_factory=list)
    unknowns: list[ResearchUnknown] = Field(default_factory=list)
    alignment_review: ResearchAlignmentReview | None = None
    information_utilities: list[ContentResearchUtility] = Field(default_factory=list)
    entity_candidates: list[ResearchEntityCandidate] = Field(default_factory=list)
    event_candidates: list[ResearchEventCandidate] = Field(default_factory=list)
    memory_items: list[ResearchMemoryItem] = Field(default_factory=list)
    research_plan: dict[str, object] = Field(default_factory=dict)
