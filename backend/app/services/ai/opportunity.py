from __future__ import annotations

from collections.abc import Mapping
from typing import Literal

from app.repositories.opportunity import OpportunityRepository

AnalysisStatus = Literal[
    "opportunity_identified",
    "no_opportunity_identified",
    "needs_more_evidence",
]


PAIN_WORDS = ("复杂", "难", "不稳定", "不稳", "太贵", "贵", "价格", "配置", "安装", "缺少", "不好用", "痛点", "抱怨", "麻烦")
CONTENT_GAP_WORDS = ("不知道", "没有教程", "没人讲", "争议", "误解", "困惑", "怎么用", "缺少案例", "内容")


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _text(row: Mapping[str, object]) -> str:
    return " ".join(
        str(row.get(key) or "")
        for key in ("title", "summary", "description", "statement", "note")
    ).strip()


def _independent_group(row: Mapping[str, object]) -> str:
    explicit = str(row.get("independent_group") or "").strip()
    if explicit:
        return explicit
    platform = str(row.get("platform") or row.get("source_platform") or "unknown")
    author = str(row.get("author_name") or row.get("source_author") or "").strip()
    return f"{platform}:{author or row.get('content_id') or 'unknown'}"


class OpportunityService:
    """Evidence-bound, bounded opportunity materialization.

    The first 8F implementation deliberately keeps the aggregation rule
    deterministic. Prompt roles govern future model-assisted explanations,
    while a local/production request can never create a claim without source
    rows and independent-evidence checks.
    """

    def __init__(self, repository: OpportunityRepository) -> None:
        self.repository = repository

    @staticmethod
    def _signal_type(text: str, opportunity_type: str) -> str:
        if opportunity_type == "content_opportunity" or any(word in text for word in CONTENT_GAP_WORDS):
            return "content_gap"
        if any(word in text for word in ("价格", "贵", "收费")):
            return "pricing_friction"
        if any(word in text for word in ("复杂", "配置", "安装", "难用", "麻烦")):
            return "workflow_friction"
        if any(word in text for word in ("缺少", "没有", "需要")):
            return "unmet_need"
        if any(word in text for word in ("不稳", "崩溃", "失败", "登录")):
            return "trust_issue"
        if any(word in text for word in ("抱怨", "不好用", "痛点")):
            return "repeated_complaint"
        return "emerging_interest"

    @staticmethod
    def _readiness(*, source_count: int, independent_count: int, has_counterevidence: bool, evidence_strength: float) -> str:
        if source_count < 1:
            return "insufficient_evidence"
        if independent_count < 2 or evidence_strength < 0.45:
            return "needs_more_evidence"
        if independent_count >= 3 and has_counterevidence and evidence_strength >= 0.65:
            return "validation_ready"
        return "review_ready"

    @staticmethod
    def _scores(rows: list[Mapping[str, object]], independent_groups: set[str], has_counterevidence: bool) -> tuple[dict[str, float], dict[str, object]]:
        texts = [_text(row) for row in rows]
        pain_hits = sum(any(word in text for word in PAIN_WORDS) for text in texts)
        platforms = {str(row.get("platform") or row.get("source_platform") or "unknown") for row in rows}
        repost_count = sum(bool(row.get("is_repost")) for row in rows)
        evidence_strength = sum(
            {"strong": 1.0, "medium": 0.65, "weak": 0.35}.get(str(row.get("support_strength") or "medium"), 0.5)
            for row in rows
        ) / max(1, len(rows))
        scores = {
            "problem_severity": _clamp(0.45 + min(0.4, pain_hits * 0.12)),
            "evidence_strength": _clamp(evidence_strength),
            "source_independence": _clamp(len(independent_groups) / 4),
            "signal_frequency": _clamp(len(rows) / 5),
            "cross_platform_support": _clamp(len(platforms) / 3),
            "novelty": _clamp(0.45 + (0.1 if len(platforms) > 1 else 0)),
            "urgency": _clamp(0.35 + (0.2 if pain_hits else 0)),
            "actionability": _clamp(0.5 + (0.15 if len(independent_groups) >= 2 else 0)),
            "validation_cost": _clamp(0.75 - min(0.35, len(rows) * 0.05)),
            "competition_or_saturation": _clamp(0.35 + repost_count / max(1, len(rows)) * 0.4),
            "counterevidence": 0.65 if has_counterevidence else 0.2,
            "user_relevance": 0.5,
        }
        scores["confidence"] = _clamp(
            scores["evidence_strength"] * 0.35
            + scores["source_independence"] * 0.25
            + scores["signal_frequency"] * 0.15
            + scores["counterevidence"] * 0.15
            + scores["user_relevance"] * 0.1
        )
        explanation = {
            "positive": [
                f"{len(rows)} 条可追踪证据",
                f"{len(independent_groups)} 个独立来源组",
                f"{len(platforms)} 个平台",
            ],
            "caveats": [
                "抓取数量不等于机会价值",
                "候选不等于已验证机会",
            ],
            "repost_count": repost_count,
            "counterevidence_present": has_counterevidence,
            "content_count": len(rows),
            "independent_source_count": len(independent_groups),
            "platform_count": len(platforms),
        }
        return scores, explanation

    def analyze_source(
        self,
        *,
        owner_id: str,
        source_type: str,
        source_id: str,
        opportunity_type: str,
    ) -> dict[str, object]:
        rows = self.repository.analysis_source(owner_id=owner_id, source_type=source_type, source_id=source_id)
        if not rows:
            return {
                "status": "no_opportunity_identified",
                "explanation": "当前来源没有足够的可追踪 Evidence 形成机会候选。继续研究或补充证据后再判断。",
                "signal_count": 0,
                "independent_source_count": 0,
                "opportunities": [],
            }
        existing = self.repository.get_opportunity_for_origin(
            owner_id=owner_id,
            source_type=source_type,
            source_id=source_id,
            opportunity_type=opportunity_type,
        )
        if existing is not None:
            return {
                "status": "opportunity_identified",
                "explanation": "该来源已经有机会候选；系统复用原候选及其版本历史，避免重复创建。",
                "signal_count": 0,
                "independent_source_count": len({
                    str(source.get("independent_group"))
                    for source in existing.get("sources", [])
                    if isinstance(source, Mapping)
                }),
                "opportunities": [existing],
            }
        unique_rows: list[dict[str, object]] = []
        seen_content: set[str] = set()
        for row in rows:
            content_id = str(row.get("content_id") or "")
            if not content_id or content_id in seen_content:
                continue
            seen_content.add(content_id)
            unique_rows.append(dict(row))
        rows = unique_rows[:50]
        independent_groups = {_independent_group(row) for row in rows if not bool(row.get("is_repost"))}
        has_counterevidence = any(
            str(row.get("support_type") or "") == "contradictory"
            or str(row.get("counterevidence_status") or "") == "found"
            for row in rows
        )
        scores, explanation = self._scores(rows, independent_groups, has_counterevidence)
        readiness = self._readiness(
            source_count=len(rows),
            independent_count=len(independent_groups),
            has_counterevidence=has_counterevidence,
            evidence_strength=scores["evidence_strength"],
        )
        signal_ids: list[str] = []
        signal_type = self._signal_type(" ".join(_text(row) for row in rows), opportunity_type)
        for row in rows[:10]:
            signal = self.repository.create_signal(
                owner_id=owner_id,
                payload={
                    "signal_type": signal_type,
                    "title": str(row.get("title") or row.get("source_title") or "Evidence signal"),
                    "summary": str(row.get("summary") or row.get("description") or row.get("statement") or "可追踪证据中的重复信号"),
                    "evidence_id": f"content:{row.get('content_id')}",
                    "content_id": row.get("content_id"),
                    "finding_id": row.get("finding_id"),
                    "discovery_candidate_id": source_id if source_type == "discovery_candidate" else None,
                    "monitoring_change_id": source_id if source_type == "monitoring_change" else None,
                    "source_type": source_type,
                    "source_id": source_id,
                    "source_platform": row.get("platform") or row.get("source_platform"),
                    "source_url": row.get("source_url"),
                    "entity_key": row.get("candidate_type"),
                    "observed_at": row.get("published_at"),
                    "aggregation_key": f"{signal_type}:{str(row.get('title') or row.get('source_title') or '')[:120]}".casefold(),
                    "metadata": {"source_content_id": row.get("content_id"), "is_repost": bool(row.get("is_repost"))},
                },
            )
            signal_ids.append(str(signal["id"]))
        if len(independent_groups) < 2:
            return {
                "status": "needs_more_evidence",
                "explanation": f"已发现 {len(rows)} 条相关证据，但只有 {len(independent_groups)} 个独立来源组；不能把单一来源直接升级为机会。",
                "signal_count": len(signal_ids),
                "independent_source_count": len(independent_groups),
                "opportunities": [],
            }
        title_prefix = "内容机会" if opportunity_type == "content_opportunity" else "重复出现的需求信号"
        summary_text = str(rows[0].get("summary") or rows[0].get("description") or rows[0].get("statement") or "")
        sources: list[dict[str, object]] = []
        used_roles: set[tuple[str, str]] = set()
        for index, row in enumerate(rows):
            role = "counterevidence" if str(row.get("support_type") or "") == "contradictory" or str(row.get("counterevidence_status") or "") == "found" else "core" if index == 0 else "supporting"
            source_type_for_row = source_type
            source_id_for_row = source_id
            key = (source_id_for_row, role)
            if key in used_roles:
                source_type_for_row = "content"
                source_id_for_row = str(row.get("content_id"))
                key = (source_id_for_row, role)
            if key in used_roles:
                continue
            used_roles.add(key)
            sources.append({
                "source_type": source_type_for_row,
                "source_id": source_id_for_row,
                "signal_id": signal_ids[min(index, len(signal_ids) - 1)] if signal_ids else None,
                "evidence_id": f"content:{row.get('content_id')}",
                "content_id": row.get("content_id"),
                "finding_id": row.get("finding_id"),
                "source_role": role,
                "evidence_kind": "inference" if str(row.get("kind")) == "inference" else "direct",
                "support_explanation": str(row.get("support_explanation") or "来自已有研究/发现/监控证据；原始来源保留在 Evidence Pack。"),
                "source_platform": row.get("platform") or row.get("source_platform"),
                "source_url": row.get("source_url"),
                "source_title": row.get("title") or row.get("source_title"),
                "independent_group": _independent_group(row),
                "is_repost": bool(row.get("is_repost")),
            })
        details: dict[str, object] = {}
        if opportunity_type == "content_opportunity":
            details = {
                "audience": "当前证据中明确出现该问题的用户",
                "content_gap": "现有材料重复描述问题，但没有充分回答具体解决路径或反向条件",
                "angles": ["教程型：从真实问题出发", "反常识型：解释为什么常见方案不适用", "案例型：对比不同用户场景"],
                "saturation_statement": "仅能说明当前研究样本中的同质化程度，不能推断全网热度。",
            }
        payload = {
            "opportunity_type": opportunity_type,
            "title": f"{title_prefix}：{str(rows[0].get('title') or rows[0].get('source_title') or '需要进一步验证的需求')[:100]}",
            "description": summary_text[:1_000] or "多个独立来源共同指向一个仍需验证的价值空间。",
            "target_user": "在当前证据中反复出现该问题的用户或工作流场景",
            "problem": "多个来源显示用户在同一工作流、产品能力或信息理解上遇到阻力。",
            "why_attention": "来源独立性和重复信号达到最低门槛，但仍需把问题严重度与可行动性分开验证。",
            "why_now": "当前研究/发现/监控资料中出现了跨来源重复，适合进行低成本下一步验证。",
            "next_step": "先确认关键假设，再选择最低成本的研究或用户问题验证动作。",
            "unknowns": ["问题发生频率是否足够高", "当前替代方案的真实成本", "用户是否愿意尝试更简单的方案"],
            "content_details": details,
            "related_research_task_id": source_id if source_type == "research_task" else None,
            "related_monitoring_change_id": source_id if source_type == "monitoring_change" else None,
            "related_discovery_candidate_id": source_id if source_type == "discovery_candidate" else None,
            "research_space_id": source_id if source_type == "research_space" else None,
            "sources": sources,
        }
        opportunity = self.repository.create_opportunity(
            owner_id=owner_id,
            payload=payload,
            scores=scores,
            score_explanation=explanation,
            readiness=readiness,
            status="review_ready" if readiness in {"review_ready", "validation_ready"} else "evidence_building",
        )
        return {
            "status": "opportunity_identified",
            "explanation": "机会候选已由独立来源、Evidence Pack和反向证据字段组成；它仍不是已验证结论。",
            "signal_count": len(signal_ids),
            "independent_source_count": len(independent_groups),
            "opportunities": [opportunity],
        }

    def create_explicit(self, *, owner_id: str, payload: Mapping[str, object]) -> dict[str, object]:
        sources = [item for item in payload.get("sources", []) if isinstance(item, Mapping)]
        independent_groups = {
            str(item.get("independent_group") or item.get("source_id"))
            for item in sources
            if not bool(item.get("is_repost"))
        }
        has_counterevidence = any(item.get("source_role") == "counterevidence" for item in sources)
        scores, explanation = self._scores(
            [{"is_repost": item.get("is_repost"), "platform": item.get("source_platform"), "support_strength": "medium", "support_type": item.get("source_role")} for item in sources],
            independent_groups,
            has_counterevidence,
        )
        readiness = self._readiness(
            source_count=len(sources),
            independent_count=len(independent_groups),
            has_counterevidence=has_counterevidence,
            evidence_strength=scores["evidence_strength"],
        )
        return self.repository.create_opportunity(
            owner_id=owner_id,
            payload=payload,
            scores=scores,
            score_explanation=explanation,
            readiness=readiness,
            status="review_ready" if readiness in {"review_ready", "validation_ready"} else "evidence_building",
        )

    @staticmethod
    def build_validation_plan(opportunity: Mapping[str, object], overrides: Mapping[str, object]) -> dict[str, object]:
        unknowns = list(overrides.get("unknowns") or opportunity.get("unknowns") or [])
        target_user = str(overrides.get("target_user") or opportunity.get("target_user") or "当前证据中的目标用户")
        problem = str(overrides.get("problem_hypothesis") or opportunity.get("problem") or "当前问题需要验证")
        return {
            "opportunity_hypothesis": str(overrides.get("opportunity_hypothesis") or opportunity.get("description") or "该问题存在可验证的价值空间"),
            "target_user": target_user,
            "problem_hypothesis": problem,
            "value_hypothesis": str(overrides.get("value_hypothesis") or "如果问题持续发生，用户可能愿意尝试更低成本的替代方案"),
            "critical_assumptions": list(overrides.get("critical_assumptions") or ["问题发生频率足够高", "现有替代方案存在明显成本", "目标用户愿意尝试新方案"]),
            "unknowns": unknowns,
            "validation_questions": list(overrides.get("validation_questions") or ["问题最近发生的频率是多少？", "用户当前如何解决？", "什么结果会让用户认为新方案值得尝试？"]),
            "evidence_needed": list(overrides.get("evidence_needed") or ["至少两个独立用户/平台来源", "反向证据", "替代方案对比"]),
            "cheapest_next_test": str(overrides.get("cheapest_next_test") or "继续收集独立反馈并比较替代方案，不自动执行外部行动"),
            "success_criteria": list(overrides.get("success_criteria") or ["出现至少两个独立来源支持同一问题", "用户能清楚描述当前解决成本"]),
            "failure_criteria": list(overrides.get("failure_criteria") or ["只有营销或转载来源", "问题无法复现或用户已有低成本替代方案"]),
            "estimated_effort": str(overrides.get("estimated_effort") or "低：一次有边界的后续研究"),
            "risk": str(overrides.get("risk") or "样本偏差、来源同源、把兴趣误判为付费意愿"),
            "next_decision": str(overrides.get("next_decision") or "决定继续验证、降低优先级或停止"),
        }
