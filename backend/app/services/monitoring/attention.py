"""Deterministic attention decisions for change notifications."""

from __future__ import annotations


def attention_for_change(change: dict[str, object]) -> dict[str, object]:
    relevance = max(0.0, min(1.0, float(change.get("relevance_score") or 0)))
    novelty = max(0.0, min(1.0, float(change.get("novelty_score") or 0)))
    evidence = max(0.0, min(1.0, float(change.get("evidence_strength_score") or 0)))
    independence = max(0.0, min(1.0, float(change.get("source_independence_score") or 0)))
    noise = max(0.0, min(1.0, float(change.get("noise_risk_score") or 0)))
    score = (
        relevance * 0.30
        + novelty * 0.20
        + evidence * 0.20
        + independence * 0.15
        + float(change.get("actionability_score") or 0) * 0.10
        + float(change.get("persistence_score") or 0) * 0.05
        - noise * 0.20
    )
    if score >= 0.78 and evidence >= 0.55:
        level = "immediate_attention"
    elif score >= 0.52 and evidence >= 0.35:
        level = "daily_digest"
    elif score >= 0.28:
        level = "normal_record"
    elif evidence > 0 or relevance > 0 or novelty > 0:
        level = "silent_memory"
    else:
        level = "ignored"
    return {
        "level": level,
        "score": round(max(0.0, min(1.0, score)), 4),
        "reason": (
            f"相关性 {relevance:.2f}，新颖性 {novelty:.2f}，"
            f"证据强度 {evidence:.2f}，独立来源 {independence:.2f}，噪音风险 {noise:.2f}"
        ),
    }
