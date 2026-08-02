from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import UTC, datetime
from typing import Any

from app.models.ai import ModelMessage, ModelRequest
from app.models.research_intent import ResearchIntentContract, ResearchIntentType
from app.services.ai.research_quality import parse_structured_json

KNOWN_PRODUCTS = (
    "Notion",
    "Codex",
    "WorkBuddy",
    "ChatGPT",
    "Claude",
    "Claude Code",
    "Cursor",
    "DeepSeek",
    "OpenClaw",
    "飞书",
    "钉钉",
    "通义",
    "秘塔",
)
PLATFORM_NAMES = {
    "小红书": "xhs",
    "xhs": "xhs",
    "B站": "bili",
    "哔哩哔哩": "bili",
    "bilibili": "bili",
    "知乎": "zhihu",
    "微博": "wb",
    "贴吧": "tieba",
    "快手": "ks",
}


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def _contains(text: str, terms: Iterable[str]) -> bool:
    return any(term.casefold() in text.casefold() for term in terms)


def _unique(values: Iterable[str]) -> list[str]:
    return list(dict.fromkeys(value.strip() for value in values if value and value.strip()))


def _known_entities(request: str) -> list[dict[str, str]]:
    entities: list[dict[str, str]] = []
    for name in KNOWN_PRODUCTS:
        if name.casefold() in request.casefold():
            entities.append({"name": name, "entity_type": "product"})
    for match in re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", request):
        if match.casefold() in {item["name"].casefold() for item in entities}:
            continue
        if match.casefold() in {"AI", "API", "Skills".casefold()}:
            continue
        entities.append({"name": match, "entity_type": "product"})
    return entities[:12]


def _time_scope(request: str) -> tuple[dict[str, object], list[str]]:
    year = re.search(r"(20\d{2})\s*年", request)
    days = re.search(r"近\s*(\d{1,3})\s*天", request)
    if year:
        return {"type": "calendar_year", "year": int(year.group(1))}, []
    if days:
        return {"type": "recent", "default_days": int(days.group(1))}, []
    if _contains(request, ("最近", "近期", "当前", "这段时间")):
        return {"type": "recent", "default_days": 30}, ["我暂时把“最近”理解为过去30天。"]
    if _contains(request, ("长期", "持续", "一直", "监控")):
        return {"type": "ongoing", "default_days": 90}, ["未指定结束时间，先以过去90天作为基线。"]
    return {"type": "recent", "default_days": 30, "inferred": True}, [
        "未指定时间范围，先以过去30天作为默认范围。"
    ]


def _subject(request: str, entities: list[dict[str, str]]) -> dict[str, object]:
    audience = None
    audience_match = re.search(r"([^，。！？\s]{1,20}(?:用户|博主|创作者|团队|开发者|消费者))", request)
    if audience_match:
        audience = audience_match.group(1)
    category_terms = [
        "个人AI工具",
        "个人 AI 工具",
        "个人知识管理",
        "AI工具",
        "AI 工具",
        "市场",
        "产品",
        "内容创作",
        "科技话题",
    ]
    category = next((term for term in category_terms if term.casefold() in request.casefold()), None)
    return {
        "category": category,
        "description": request[:240],
        "known_entity_names": [item["name"] for item in entities],
        "audience": audience,
    }


def _intents(request: str) -> tuple[ResearchIntentType, list[ResearchIntentType]]:
    matches: list[ResearchIntentType] = []
    rules: tuple[tuple[ResearchIntentType, tuple[str, ...]], ...] = (
        ("comparison", ("比较", "对比", "差异", "区别", "vs", " versus ")),
        ("verification", ("验证", "核实", "是否", "到底", "真假")),
        ("pain_point_research", ("抱怨", "吐槽", "不好用", "痛点", "缺点", "问题", "失败")),
        ("competitor_scan", ("竞品", "替代", "竞争", "对手")),
        ("creator_scan", ("博主", "创作者", "up主", "作者", "常用")),
        ("trend_tracking", ("趋势", "什么火", "火了", "增长", "传播", "热门")),
        ("monitoring", ("监控", "持续跟踪", "长期跟踪", "提醒")),
        ("content_opportunity", ("选题", "内容机会", "怎么做内容", "创作机会")),
        ("product_opportunity", ("产品机会", "商业机会", "机会", "值得做")),
        ("market_mapping", ("市场", "行业", "领域", "格局")),
        ("discovery", ("有哪些", "哪些", "什么", "发现", "探索", "值得关注", "推荐", "新产品")),
    )
    for intent, terms in rules:
        if _contains(request, terms):
            matches.append(intent)
    if "discovery" in matches and _contains(request, ("最近", "近期", "值得关注")):
        if "trend_tracking" not in matches:
            matches.append("trend_tracking")
        if "product_opportunity" not in matches and _contains(request, ("值得关注", "推荐")):
            matches.append("product_opportunity")
    if "competitor_scan" in matches and _contains(request, ("为什么选择", "选择原因", "用户为什么")):
        for intent in ("pain_point_research", "comparison", "product_opportunity"):
            if intent not in matches:
                matches.append(intent)
    if not matches:
        return "discovery", []
    primary = matches[0]
    return primary, _unique(matches[1:])  # type: ignore[return-value]


def _unknowns(primary: ResearchIntentType, secondary: list[ResearchIntentType], request: str) -> list[str]:
    intents = {primary, *secondary}
    values: list[str] = []
    if "discovery" in intents:
        values.extend(["product_names", "product_categories", "user_scenarios", "differentiating_features"])
    if "creator_scan" in intents:
        values.extend(["relevant_creators", "tools_used", "real_workflows"])
    if "trend_tracking" in intents:
        values.extend(["emerging_topics", "representative_content", "传播变化", "audience_reaction"])
    if "pain_point_research" in intents:
        values.extend(["user_complaints", "failed_use_cases", "limitations", "alternatives_considered"])
    if "competitor_scan" in intents:
        values.extend(["competitor_names", "selection_reasons", "positioning_differences"])
    if "comparison" in intents:
        values.extend(["dimension_by_dimension_facts", "independent_evidence", "tradeoffs"])
    if "market_mapping" in intents:
        values.extend(["market_segments", "representative_entities", "open_gaps"])
    if "product_opportunity" in intents or "content_opportunity" in intents:
        values.extend(["unserved_needs", "possible_opportunities"])
    if not values:
        values.append("与研究目标直接相关的未知实体、事实和限制")
    if _contains(request, ("工具", "软件")) and "tool_names" not in values:
        values.append("tool_names")
    return _unique(values)


def _evidence(primary: ResearchIntentType, secondary: list[ResearchIntentType]) -> tuple[list[str], list[str]]:
    intents = {primary, *secondary}
    evidence: list[str] = []
    negative: list[str] = []
    if "discovery" in intents or "competitor_scan" in intents:
        evidence.extend(["entity_exists", "recent_activity", "real_usage_case", "independent_user_feedback"])
    if "verification" in intents or "comparison" in intents:
        evidence.extend(["direct_source", "dimension_specific_fact", "independent_confirmation"])
    if "trend_tracking" in intents:
        evidence.extend(["time_bounded_change", "multiple_sources", "audience_response"])
    if "creator_scan" in intents:
        evidence.extend(["creator_identity", "actual_workflow", "tool_mention_in_context"])
    if "pain_point_research" in intents:
        negative.extend(["complaints", "limitations", "failed_use_cases", "alternative_requests"])
    if "comparison" in intents or "product_opportunity" in intents:
        negative.extend(["limitations", "tradeoffs", "counterexamples"])
    return _unique(evidence), _unique(negative)


def _outputs(primary: ResearchIntentType, secondary: list[ResearchIntentType]) -> list[str]:
    intents = {primary, *secondary}
    values: list[str] = []
    if "discovery" in intents:
        values.extend(["product_shortlist", "why_each_matters", "supporting_evidence", "limitations"])
    if "comparison" in intents:
        values.extend(["comparison_matrix", "direct_evidence", "tradeoffs"])
    if "trend_tracking" in intents:
        values.extend(["trend_summary", "representative_entities", "change_signals"])
    if "pain_point_research" in intents:
        values.extend(["pain_point_clusters", "counterevidence", "failed_use_cases"])
    if "competitor_scan" in intents:
        values.extend(["competitor_shortlist", "selection_reasons", "positioning_gaps"])
    if "creator_scan" in intents:
        values.extend(["creator_list", "tool_usage_scenarios", "creator_evidence"])
    if "product_opportunity" in intents or "content_opportunity" in intents:
        values.append("possible_opportunities")
    return _unique(values or ["key_findings", "evidence_gaps", "recommended_next_actions"])


def _confidence(request: str, primary: ResearchIntentType, entities: list[dict[str, str]]) -> tuple[float, list[str], str | None]:
    if _contains(request, ("帮我研究一下市场", "研究一下市场", "研究市场")) and len(request) < 20:
        return 0.32, ["研究对象或行业尚未明确"], "你主要想研究哪个产品或行业？"
    confidence = 0.82 if primary in {"comparison", "competitor_scan", "creator_scan", "pain_point_research", "trend_tracking"} else 0.76
    if entities:
        confidence = min(0.95, confidence + 0.08)
    if len(request.strip()) < 8:
        confidence = 0.4
    return confidence, [], None


def _contract_from_values(
    request: str,
    platforms: list[str],
    values: dict[str, Any],
    *,
    source: str,
) -> ResearchIntentContract:
    now = utc_now()
    fallback = build_default_intent(request, platforms)
    merged: dict[str, Any] = fallback.model_dump()
    for key, value in values.items():
        if key not in merged or value is None:
            continue
        if key in {"original_request", "original_intent"}:
            continue
        merged[key] = value
    merged["original_request"] = request
    merged["original_intent"] = request
    merged["intent_source"] = source
    merged["created_at"] = now
    merged["updated_at"] = now
    merged["version"] = int(values.get("version") or 1)
    try:
        return ResearchIntentContract.model_validate(merged)
    except (TypeError, ValueError):
        return fallback


def build_default_intent(request: str, platforms: list[str] | None = None) -> ResearchIntentContract:
    normalized = " ".join(request.strip().split())
    selected_platforms = _unique(platforms or [])
    primary, secondary = _intents(normalized)
    entities = _known_entities(normalized)
    time_scope, assumptions = _time_scope(normalized)
    evidence, negative = _evidence(primary, secondary)
    unknowns = _unknowns(primary, secondary, normalized)
    confidence, ambiguities, clarification = _confidence(normalized, primary, entities)
    subject = _subject(normalized, entities)
    if not selected_platforms:
        selected_platforms = [PLATFORM_NAMES[name] for name in PLATFORM_NAMES if name in normalized]
    if not selected_platforms:
        selected_platforms = ["bili", "xhs", "zhihu"]
    exclusions = ["纯课程内容", "泛化新闻", "重复转载", "脱离研究范围的营销内容"]
    outputs = _outputs(primary, secondary)
    interpreted = f"围绕{subject.get('category') or normalized[:80]}，{('发现未知实体并验证其真实使用与限制' if primary == 'discovery' else '完成' + primary + '研究')}。"
    criteria = ["覆盖主要未知项", "关键结论绑定直接来源", "明确限制、反证和未解决问题", "输出下一步行动建议"]
    return ResearchIntentContract(
        original_request=normalized,
        original_intent=normalized,
        interpreted_goal=interpreted,
        primary_intent=primary,
        secondary_intents=secondary,
        subject=subject,
        known_entities=entities,
        known_constraints=[],
        unknowns_to_discover=unknowns,
        time_scope=time_scope,
        platform_preferences=selected_platforms,
        target_audience=subject.get("audience") if isinstance(subject.get("audience"), str) else None,
        evidence_requirements=evidence,
        negative_evidence_requirements=negative,
        exclusions=exclusions,
        desired_output=outputs,
        success_criteria=criteria,
        confidence=confidence,
        ambiguities=ambiguities,
        assumptions=assumptions,
        current_research_hypothesis=interpreted,
        intent_revisions=[],
        intent_source="fallback_default",
        clarification_question=clarification,
        created_at=utc_now(),
        updated_at=utc_now(),
    )


def model_request(original_request: str, platforms: list[str]) -> ModelRequest:
    return ModelRequest(
        system=(
            "You are the Intent Interpreter, not a search planner. Understand the user's research goal "
            "and return JSON only. Do not generate platform queries, select a single platform, or decide "
            "whether research is complete. Include primary_intent, secondary_intents, known_entities, "
            "unknowns_to_discover, time_scope, target_audience, evidence_requirements, "
            "negative_evidence_requirements, exclusions, desired_output, success_criteria, confidence, "
            "ambiguities, assumptions, and interpreted_goal. Use only the stable intent enums provided."
        ),
        messages=[
            ModelMessage(
                role="user",
                content=(
                    f"Stable intent enums: discovery, verification, comparison, trend_tracking, "
                    f"pain_point_research, competitor_scan, creator_scan, content_opportunity, "
                    f"market_mapping, product_opportunity, monitoring\n"
                    f"Platforms available for later planning: {platforms}\n"
                    f"User research goal: {original_request}"
                ),
            )
        ],
        temperature=0.1,
        max_tokens=900,
        tools=None,
        tool_choice="none",
        metadata={"runtime_step": "intent_interpretation"},
        timeout=45,
    )


def repair_model_request(original_request: str, raw_response: str, platforms: list[str]) -> ModelRequest:
    return ModelRequest(
        system=(
            "Repair one malformed Intent Contract response. Return strict JSON only, with no markdown. "
            "Do not create platform queries or decide whether research is complete. Preserve the user's "
            "meaning and use only the stable intent enums."
        ),
        messages=[
            ModelMessage(
                role="user",
                content=(
                    f"Original user research goal: {original_request}\n"
                    f"Available platforms for later planning: {platforms}\n"
                    f"Malformed response to repair: {raw_response[:8_000]}\n"
                    "Required JSON keys: interpreted_goal, primary_intent, secondary_intents, subject, "
                    "known_entities, known_constraints, unknowns_to_discover, time_scope, target_audience, "
                    "evidence_requirements, negative_evidence_requirements, exclusions, desired_output, "
                    "success_criteria, confidence, ambiguities, assumptions."
                ),
            )
        ],
        temperature=0.1,
        max_tokens=900,
        tools=None,
        tool_choice="none",
        metadata={"runtime_step": "intent_interpretation_repair"},
        timeout=45,
    )


def interpret_model_text(
    original_request: str,
    text: str,
    platforms: list[str],
) -> ResearchIntentContract:
    parsed = parse_structured_json(text).value
    if not isinstance(parsed, dict):
        return build_default_intent(original_request, platforms)
    return _contract_from_values(original_request, platforms, parsed, source="model")


def execution_query_directions(contract: ResearchIntentContract) -> list[dict[str, str]]:
    """Create bounded plan seeds; these are execution queries, never user goals."""
    subject = str(contract.subject.get("category") or " ".join(
        str(item.get("name")) for item in contract.known_entities if isinstance(item, dict) and item.get("name")
    ) or contract.original_request[:80]).strip()
    entities = [
        str(item.get("name"))
        for item in contract.known_entities
        if isinstance(item, dict) and isinstance(item.get("name"), str)
    ]
    result: list[dict[str, str]] = []
    def add(query: str, role: str) -> None:
        if query.strip() and query.strip() not in {item["query"] for item in result}:
            result.append({"query": query.strip()[:180], "query_role": role})

    intents = {contract.primary_intent, *contract.secondary_intents}
    if "comparison" in intents and entities:
        dimensions = ["长期记忆", "Skills", "自动化任务"]
        for dimension in dimensions:
            add(f"{' '.join(entities)} {dimension} 直接对比", "cross_platform_validation")
    if "competitor_scan" in intents and entities:
        add(f"{entities[0]} 竞品 替代 用户选择原因", "competitor_scan")
    if "creator_scan" in intents:
        add(f"{subject} 创作者 实际使用场景", "creator_scan")
        add(f"{subject} 博主 常用工具 工作流", "seed_discovery")
    if "pain_point_research" in intents:
        add(f"{subject} 用户抱怨 不好用 失败用例", "pain_point_probe")
        add(f"{subject} 缺点 限制 替代方案", "counterevidence")
    if "trend_tracking" in intents:
        add(f"{subject} 近期新趋势 代表话题", "trend_probe")
        add(f"{subject} 近期传播变化 用户反应", "trend_probe")
    if "discovery" in intents or not result:
        add(f"{subject} 近期代表产品 实际使用体验", "seed_discovery")
        add(f"{subject} 用户评价 差异化功能", "seed_discovery")
        add(f"{subject} 新产品 真实反馈 局限", "seed_discovery")
    if "product_opportunity" in intents or "content_opportunity" in intents:
        add(f"{subject} 未满足需求 内容机会 产品机会", "pain_point_probe")
    return result[:10]
