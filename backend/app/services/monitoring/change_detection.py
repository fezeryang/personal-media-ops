"""Baseline comparison, repost grouping, event fingerprints, and memory updates."""

from __future__ import annotations

import hashlib
from collections.abc import Iterable, Mapping
from difflib import SequenceMatcher

CHANGE_TYPES = (
    "new_entity",
    "new_event",
    "new_feature",
    "new_claim",
    "new_user_pain_point",
    "new_negative_evidence",
    "new_positive_evidence",
    "updated_fact",
    "contradicted_finding",
    "reconfirmed_finding",
    "source_disappeared",
    "no_meaningful_change",
)


def _text(value: object, limit: int = 500) -> str:
    return str(value or "").strip()[:limit]


def _similarity(left: object, right: object) -> float:
    return SequenceMatcher(None, _text(left, 500).casefold(), _text(right, 500).casefold()).ratio()


def _fingerprint(item: Mapping[str, object]) -> str:
    value = "|".join(
        [
            _text(item.get("title"), 240).casefold(),
            _text(item.get("description"), 360).casefold(),
            _text(item.get("platform"), 50).casefold(),
        ]
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:24]


def _independent_key(item: Mapping[str, object]) -> str:
    explicit = _text(item.get("independent_group"), 200)
    if explicit:
        return explicit
    author = _text(item.get("author_name"), 200)
    platform = _text(item.get("platform"), 80)
    if author:
        return f"author:{platform}:{author}".casefold()
    url = _text(item.get("source_url"), 1_000)
    if url:
        return f"url:{url}".casefold()
    return f"content:{_text(item.get('id'), 160)}"


def _is_negative(item: Mapping[str, object]) -> bool:
    text = f"{item.get('title', '')} {item.get('description', '')}".casefold()
    return any(token in text for token in ("不好用", "不稳定", "复杂", "太贵", "价格高", "失败", "bug", "吐槽", "问题"))


def _change_type(item: Mapping[str, object]) -> str:
    text = f"{item.get('title', '')} {item.get('description', '')}".casefold()
    if _is_negative(item):
        return "new_negative_evidence"
    if any(token in text for token in ("发布", "上线", "事件", "收购", "融资", "公告")):
        return "new_event"
    if any(token in text for token in ("更新", "版本", "功能", "release", "feature", "推出")):
        return "new_feature"
    if any(token in text for token in ("好用", "推荐", "提升", "满意")):
        return "new_positive_evidence"
    return "new_claim"


def _group_sources(items: Iterable[Mapping[str, object]]) -> list[dict[str, object]]:
    groups: list[dict[str, object]] = []
    for item in items:
        url = _text(item.get("source_url"), 1_000)
        matched: dict[str, object] | None = None
        reason = ""
        similarity = 0.0
        for group in groups:
            first = group["first"]
            if not isinstance(first, Mapping):
                continue
            first_url = _text(first.get("source_url"), 1_000)
            title_similarity = _similarity(item.get("title"), first.get("title"))
            body_similarity = _similarity(item.get("description"), first.get("description"))
            same_author = _text(item.get("author_name"), 200) and _text(item.get("author_name"), 200) == _text(first.get("author_name"), 200)
            if url and first_url and url == first_url:
                matched, reason, similarity = group, "same_source_url", 1.0
                break
            if title_similarity >= 0.88 or body_similarity >= 0.88:
                matched, reason, similarity = group, "near_duplicate_text", max(title_similarity, body_similarity)
                break
            if same_author and title_similarity >= 0.75:
                matched, reason, similarity = group, "same_author_synchronized", title_similarity
                break
        if matched is None:
            group = {"first": dict(item), "items": [dict(item)], "group": f"source-{len(groups) + 1}"}
            groups.append(group)
        else:
            members = matched.get("items")
            if isinstance(members, list):
                members.append(dict(item))
            matched.setdefault("matches", []).append({"content_id": item.get("id"), "reason": reason, "similarity": round(similarity, 4)})
    return groups


def compare_baseline(
    *,
    goal: str,
    baseline: Mapping[str, object] | None,
    current_contents: Iterable[Mapping[str, object]],
) -> dict[str, object]:
    unique: dict[str, dict[str, object]] = {}
    for item in current_contents:
        content_id = _text(item.get("id"), 160)
        if content_id:
            unique[content_id] = dict(item)
    current = list(unique.values())
    def snapshot(
        current_items: list[dict[str, object]],
        prior: Mapping[str, object] | None = None,
    ) -> dict[str, object]:
        return {
            **(dict(prior) if prior is not None else {}),
            "content_ids": sorted(
                str(item["id"]) for item in current_items if item.get("id")
            ),
            "content_fingerprints": {
                str(item["id"]): _fingerprint(item)
                for item in current_items
                if item.get("id")
            },
            "content_records": [
                {
                    key: item.get(key)
                    for key in (
                        "id",
                        "platform",
                        "title",
                        "description",
                        "source_url",
                        "author_name",
                        "published_at",
                    )
                    if item.get(key) is not None
                }
                for item in current_items[:200]
                if item.get("id")
            ],
        }

    if baseline is None:
        return {
            "outcome": "baseline_created",
            "changes": [],
            "baseline": snapshot(current),
        }
    known_ids = {str(value) for value in baseline.get("content_ids", []) if value}
    new_items = [item for item in current if str(item["id"]) not in known_ids]
    known_fingerprints = baseline.get("content_fingerprints")
    known_fingerprints = known_fingerprints if isinstance(known_fingerprints, Mapping) else {}
    updated_items = [
        item
        for item in current
        if str(item.get("id")) in known_ids
        and known_fingerprints.get(str(item.get("id")))
        and known_fingerprints.get(str(item.get("id"))) != _fingerprint(item)
    ]
    if not new_items and not updated_items:
        return {
            "outcome": "no_meaningful_change",
            "changes": [],
            "baseline": snapshot(current, baseline),
        }
    for item in updated_items:
        item["_change_type"] = "updated_fact"
    groups = _group_sources([*new_items, *updated_items])
    changes: list[dict[str, object]] = []
    goal_terms = {term.casefold() for term in goal.split() if len(term) >= 2}
    for group in groups:
        items = group.get("items")
        items = items if isinstance(items, list) else []
        first = items[0] if items and isinstance(items[0], Mapping) else {}
        first = dict(first)
        text = f"{first.get('title', '')} {first.get('description', '')}".casefold()
        relevance = min(1.0, 0.45 + 0.1 * sum(1 for term in goal_terms if term in text))
        matches = group.get("matches")
        matches = matches if isinstance(matches, list) else []
        independent_keys = {
            _independent_key(item) for item in items if isinstance(item, Mapping)
        }
        change_type = str(first.get("_change_type") or _change_type(first))
        platforms = {str(item.get("platform")) for item in items if item.get("platform")}
        change = {
            "change_type": change_type,
            "fingerprint": _fingerprint(first),
            "title": _text(first.get("title"), 300) or "未命名变化",
            "summary": _text(first.get("description"), 800) or "出现了新的监控证据。",
            "first_seen_at": first.get("published_at"),
            "latest_seen_at": max((_text(item.get("published_at"), 80) for item in items), default=None),
            "relevance_score": round(relevance, 4),
            "novelty_score": 1.0,
            "evidence_strength_score": 0.75 if items else 0.0,
            "source_independence_score": round(len(independent_keys) / max(1, len(items)), 4),
            "cross_platform_score": round(min(1.0, len(platforms) / 2), 4),
            "actionability_score": 0.65 if change_type != "new_claim" else 0.35,
            "persistence_score": 0.0,
            "noise_risk_score": 0.15 if len(items) <= 2 else 0.35,
            "independent_source_count": len(independent_keys),
            "platform_count": len(platforms),
            "suspected_repost_count": len(matches),
            "evidence": [
                {
                    "content_id": item.get("id"),
                    "platform": item.get("platform"),
                    "source_url": item.get("source_url"),
                    "source_title": item.get("title"),
                    "source_author": item.get("author_name"),
                    "published_at": item.get("published_at"),
                    "is_repost": index > 0 and _independent_key(item) == _independent_key(first),
                    "independent_group": _independent_key(item),
                }
                for index, item in enumerate(items)
                if isinstance(item, Mapping)
            ],
            "explanation": {
                "compared_with_baseline": True,
                "why_new": "内容 ID 不在上次监控基线中或内容指纹发生变化",
                "source_independence": "相同 URL/高度相似内容合并，不重复增加置信度",
                "repost_detection": {"suspected_repost_count": len(matches), "matches": matches},
                "unknowns": ["是否持续出现", "是否需要用户进一步确认"],
            },
        }
        changes.append(change)
    current_ids = sorted(set(known_ids) | {str(item["id"]) for item in current})
    return {
        "outcome": "meaningful_change" if changes else "no_meaningful_change",
        "changes": changes,
        "baseline": snapshot(current, {**dict(baseline), "content_ids": current_ids}),
    }


def memory_update_for_change(
    change: Mapping[str, object],
    *,
    old_value: object,
    new_value: object,
) -> dict[str, object]:
    evidence = change.get("evidence")
    evidence_ids = [
        str(item.get("content_id"))
        for item in evidence
        if isinstance(item, Mapping) and item.get("content_id")
    ] if isinstance(evidence, list) else []
    return {
        "memory_key": _text(change.get("fingerprint"), 120),
        "old_value": old_value,
        "new_value": new_value,
        "evidence_ids": list(dict.fromkeys(evidence_ids)),
        "changed_at": change.get("latest_seen_at"),
        "confidence": float(change.get("evidence_strength_score") or 0),
        "confirmation_status": "needs_user_confirmation" if float(change.get("relevance_score") or 0) >= 0.7 else "recorded",
    }
