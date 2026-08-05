"""Tiered context construction for all Research Runtime roles."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping

from app.services.ai.context_compactor import compact_research_context

CONTEXT_VERSION = "ctx-v1"


def _text(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _unique(items: Iterable[object], key: str = "id") -> list[dict[str, object]]:
    seen: set[str] = set()
    result: list[dict[str, object]] = []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        identifier = _text(item.get(key), 160) or hashlib.sha1(
            repr(sorted(item.items())).encode("utf-8"), usedforsecurity=False
        ).hexdigest()
        if identifier in seen:
            continue
        seen.add(identifier)
        result.append(dict(item))
    return result


class ContextBuilder:
    """Build high-value context tiers before the compactor trims raw material."""

    version = CONTEXT_VERSION

    def build(
        self,
        *,
        objective: str,
        intent: Mapping[str, object] | None = None,
        findings: Iterable[object] = (),
        unknowns: Iterable[object] = (),
        reverse_evidence: Iterable[object] = (),
        entities: Iterable[object] = (),
        events: Iterable[object] = (),
        memories: Iterable[object] = (),
        queries: Iterable[object] = (),
        raw_contents: Iterable[object] = (),
        success_criteria: Iterable[object] = (),
        max_items: int = 24,
    ) -> tuple[dict[str, object], dict[str, int]]:
        intent_data = dict(intent or {})
        raw_content_items = list(raw_contents)
        unknown_items = list(unknowns)
        reverse_items = list(reverse_evidence)
        entity_items = list(entities)
        event_items = list(events)
        memory_items = list(memories)
        query_source_items = list(queries)
        finding_items = _unique(findings)[:max_items]
        evidence_cards: list[dict[str, object]] = []
        for finding in finding_items:
            for evidence in finding.get("evidence", []):
                if isinstance(evidence, Mapping) and evidence.get("content_id"):
                    evidence_cards.append(
                        {
                            "content_id": _text(evidence.get("content_id"), 120),
                            "evidence_id": _text(evidence.get("id") or evidence.get("evidence_id"), 120) or None,
                            "source": evidence.get("source") or evidence.get("platform"),
                            "published_at": evidence.get("published_at"),
                            "evidence_role": evidence.get("support_type") or "background",
                            "kind": finding.get("kind") or "fact",
                        }
                    )
        query_items = _unique(query_source_items)[: max_items * 2]
        query_cards = [
            {
                "query_id": _text(item.get("id"), 120),
                "query": _text(item.get("query"), 300),
                "parent_goal": _text(item.get("parent_goal") or objective, 500),
                "parent_unknown": item.get("parent_unknown"),
                "query_role": item.get("query_role"),
                "generation_reason": item.get("generation_reason"),
                "scope_distance": item.get("scope_distance"),
                "platform": item.get("platform"),
                "status": item.get("status") or item.get("lifecycle_status"),
            }
            for item in query_items
        ]
        content_items = _unique(raw_content_items)[:max_items]
        content_cards = [
            {
                "id": _text(item.get("id"), 120),
                "title": _text(item.get("title"), 300),
                "description": _text(item.get("description"), 700),
                "source": item.get("source") or item.get("platform"),
                "source_url": item.get("source_url"),
                "published_at": item.get("published_at"),
            }
            for item in content_items
        ]
        context = {
            "context_version": self.version,
            "tiers": {
                "tier_1": {
                    "objective": _text(objective, 2_000),
                    "intent": intent_data,
                    "success_criteria": [_text(item, 300) for item in success_criteria][:12],
                },
                "tier_2": {"findings": finding_items, "evidence": evidence_cards[: max_items * 2]},
                "tier_3": {
                    "unknowns": [_text(item, 300) for item in unknown_items][:16],
                    "reverse_evidence": _unique(reverse_items)[:max_items],
                },
                "tier_4": {
                    "entities": _unique(entity_items)[:max_items],
                    "events": _unique(event_items)[:max_items],
                    "memories": _unique(memory_items)[:max_items],
                },
                "tier_5": {"queries": query_cards[-max_items:]},
                "tier_6": {"contents": content_cards},
            },
        }
        compacted, compact_stats = compact_research_context(
            objective=objective,
            coverage={"intent": intent_data},
            entities=entity_items,
            queries=query_items,
            findings=finding_items,
            candidate_contents=content_items,
            unresolved_questions=unknown_items,
            max_items=max_items,
        )
        context["compacted"] = compacted
        stats = {
            **compact_stats,
            "raw_content_count": len(raw_content_items),
            "deduplicated_content_count": len(content_cards),
            "finding_count": len(finding_items),
            "query_count": len(query_cards),
            "preserved_evidence_count": len(evidence_cards),
        }
        return context, stats
