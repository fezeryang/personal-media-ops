"""Explicit contracts for tools exposed to the AI Runtime."""

from __future__ import annotations

TOOL_CONTRACT_VERSION = "v1"

_CONTRACTS: tuple[dict[str, object], ...] = (
    {
        "name": "search_library",
        "purpose": "Find bounded existing evidence relevant to a user goal.",
        "not_for": "Creating a fact, expanding scope, or bypassing query gates.",
        "input_schema": {"type": "object", "required": ["query", "limit"]},
        "output_schema": {"type": "object", "required": ["items", "content_ids"]},
        "preconditions": ["authenticated owner task", "bounded limit"],
        "budget_impact": "library read; no browser task",
        "async": False,
        "failure_types": ["invalid_query", "database_unavailable"],
        "retry": "one bounded retry for transient SQLite lock",
        "state_change": "none",
    },
    {
        "name": "submit_crawl",
        "purpose": "Queue one production-verified platform search for a research gap.",
        "not_for": "Direct browser execution, unsupported modes, or automatic monitoring.",
        "input_schema": {"type": "object", "required": ["platform", "query", "research_task_id"]},
        "output_schema": {"type": "object", "required": ["crawler_task_id", "status"]},
        "preconditions": ["quality-gated execution query", "platform capability", "worker queue"],
        "budget_impact": "one crawler task and its content budget",
        "async": True,
        "failure_types": ["platform_deferred", "login_required", "queue_busy", "budget_exceeded"],
        "retry": "durable retry candidate only; never duplicate a claimed task",
        "state_change": "creates WaitingCrawl research checkpoint",
    },
    {
        "name": "save_finding",
        "purpose": "Persist an evidence-bound fact or inference.",
        "not_for": "Guessing, unsupported summaries, or replacing an existing fact silently.",
        "input_schema": {"type": "object", "required": ["statement", "content_ids"]},
        "output_schema": {"type": "object", "required": ["finding_id", "status"]},
        "preconditions": ["content IDs exist", "support type and derivation are present for inference"],
        "budget_impact": "one bounded artifact write",
        "async": False,
        "failure_types": ["missing_evidence", "scope_conflict", "database_unavailable"],
        "retry": "no automatic duplicate write",
        "state_change": "adds or supersedes a Finding",
    },
    {
        "name": "identify_opportunity",
        "purpose": "Group source-bound Signals into a bounded Opportunity Candidate.",
        "not_for": "Promoting every Discovery, inventing demand, market size, revenue, or a claim without Evidence IDs.",
        "input_schema": {"type": "object", "required": ["source_type", "source_id", "opportunity_type"]},
        "output_schema": {"type": "object", "required": ["status", "signal_count", "independent_source_count", "opportunities"]},
        "preconditions": ["owner-scoped source", "Evidence or source rows", "repost-aware grouping"],
        "budget_impact": "bounded local analysis; no browser task",
        "async": False,
        "failure_types": ["source_not_found", "insufficient_evidence", "database_unavailable"],
        "retry": "safe read/recompute; do not duplicate a user-approved write without idempotency review",
        "state_change": "may append Signals and a versioned Opportunity Candidate",
    },
    {
        "name": "create_validation_plan",
        "purpose": "Turn an accepted evidence-bound Opportunity into the cheapest bounded validation step.",
        "not_for": "Declaring a business as proven or starting real-world action without owner approval.",
        "input_schema": {"type": "object", "required": ["opportunity_id"]},
        "output_schema": {"type": "object", "required": ["validation_plan_id", "status", "success_criteria", "failure_criteria"]},
        "preconditions": ["review-ready or validation-ready Opportunity", "owner confirmation"],
        "budget_impact": "one bounded plan write; follow-up research gets its own budget",
        "async": False,
        "failure_types": ["insufficient_evidence", "owner_not_confirmed", "database_unavailable"],
        "retry": "no duplicate plan for the same source version without explicit owner action",
        "state_change": "creates draft Validation Plan",
    },
    {
        "name": "propose_action",
        "purpose": "Propose a small next action and capture its expected result for owner approval.",
        "not_for": "Publishing, contacting strangers, purchasing, payment, external form submission, or automatic execution.",
        "input_schema": {"type": "object", "required": ["source_type", "source_id", "action_type", "title"]},
        "output_schema": {"type": "object", "required": ["action_id", "status", "success_criteria"]},
        "preconditions": ["source Opportunity, Validation Plan, Research, or Discovery exists", "owner-scoped source"],
        "budget_impact": "one local action record; execution budget is explicit per action",
        "async": False,
        "failure_types": ["source_not_found", "owner_not_confirmed", "database_unavailable"],
        "retry": "safe only before approval; never auto-approve a real-world action",
        "state_change": "creates proposed Action",
    },
)


def get_tool_contracts() -> list[dict[str, object]]:
    return [dict(item) for item in _CONTRACTS]
