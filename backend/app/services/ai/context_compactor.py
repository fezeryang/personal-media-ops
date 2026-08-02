"""Bounded, traceable context compaction for Research Runtime."""

from __future__ import annotations

from collections.abc import Iterable


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def compact_research_context(
    *,
    objective: str,
    coverage: dict[str, object],
    entities: Iterable[object],
    queries: Iterable[object],
    findings: Iterable[object],
    candidate_contents: Iterable[object] = (),
    loaded_content_ids: Iterable[object] = (),
    unresolved_questions: Iterable[object] = (),
    budget: dict[str, object] | None = None,
    max_items: int = 24,
) -> tuple[dict[str, object], dict[str, int]]:
    """Keep the durable IDs and provenance needed to reconstruct decisions.

    Full bodies and repeated tool payloads remain in the library and execution
    trace; the model context only receives concise evidence cards.
    """
    entity_items = [
        _text(item.get("canonical_name"), 160)
        for item in entities
        if isinstance(item, dict) and item.get("canonical_name")
    ][:max_items]
    query_items = []
    for item in queries:
        if not isinstance(item, dict):
            continue
        query_items.append(
            {
                "query_id": _text(item.get("id"), 80),
                "query": _text(item.get("query"), 240),
                "platform": _text(item.get("platform"), 32),
                "status": _text(item.get("lifecycle_status") or item.get("status"), 40),
                "source_content_id": item.get("source_content_id"),
                "source_finding_id": item.get("source_finding_id"),
            }
        )
    candidate_content_ids = {
        _text(item.get("id"), 100)
        for item in candidate_contents
        if isinstance(item, dict) and _text(item.get("id"), 100)
    }
    loaded_ids = {
        _text(item, 100)
        for item in loaded_content_ids
        if _text(item, 100)
    }
    finding_items = []
    preserved_content_ids: set[str] = set()
    for item in findings:
        if not isinstance(item, dict):
            continue
        evidence_cards = []
        for evidence in item.get("evidence", []):
            if not isinstance(evidence, dict):
                continue
            content_id = _text(evidence.get("content_id"), 100)
            if not content_id:
                continue
            preserved_content_ids.add(content_id)
            evidence_cards.append(
                {
                    "content_id": content_id,
                    "source_url": evidence.get("source_url"),
                    "platform": evidence.get("platform"),
                    "published_at": evidence.get("published_at"),
                    "evidence_role": evidence.get("support_type") or "background",
                }
            )
        finding_items.append(
            {
                "finding_id": _text(item.get("id"), 100),
                "kind": item.get("kind"),
                "statement": _text(item.get("statement"), 700),
                "counterevidence_status": item.get("counterevidence_status"),
                "evidence": evidence_cards[:8],
            }
        )
    unresolved = [_text(item, 240) for item in unresolved_questions if _text(item, 240)][:12]
    compacted = {
        "objective": _text(objective, 2_000),
        "coverage": dict(coverage),
        "confirmed_entities": entity_items,
        "query_source_chain": query_items[-max_items:],
        "high_value_evidence": finding_items[-max_items:],
        "unresolved_questions": unresolved,
        "budget": dict(budget or {}),
        "preserved_content_ids": sorted(preserved_content_ids),
    }
    stats = {
        "candidate_query_count": len(query_items),
        "candidate_content_count": len(candidate_content_ids),
        "loaded_full_content_count": len(loaded_ids),
        "final_evidence_count": sum(len(item["evidence"]) for item in finding_items),
        "preserved_content_count": len(preserved_content_ids),
        "compressed_branch_count": max(0, len(query_items) - max_items),
    }
    return compacted, stats
