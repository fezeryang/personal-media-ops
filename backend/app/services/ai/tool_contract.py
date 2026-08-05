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
)


def get_tool_contracts() -> list[dict[str, object]]:
    return [dict(item) for item in _CONTRACTS]
