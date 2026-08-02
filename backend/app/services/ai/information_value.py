from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from app.models.research_intent import ResearchIntentContract

NEGATIVE_TERMS = ("不好用", "缺点", "问题", "失败", "吐槽", "崩溃", "限制", "替代", "不推荐")
EVENT_TERMS = ("上线", "发布", "更新", "新版本", "定价", "涨价", "合作", "融资", "故障", "下线")
MARKETING_TERMS = ("购买", "优惠", "扫码", "推广", "私信领取", "限时")
OPPORTUNITY_TERMS = ("需求", "痛点", "机会", "缺口", "希望有", "替代")


@dataclass(frozen=True)
class InformationUtilityAssessment:
    utility_type: str
    rationale: str
    confidence: float


def _text(content: dict[str, object]) -> str:
    return " ".join(
        str(content.get(key) or "")
        for key in ("title", "description", "content", "summary")
    ).strip()


def _known_names(intent: ResearchIntentContract) -> set[str]:
    values: set[str] = set()
    for item in intent.known_entities:
        if isinstance(item, dict) and isinstance(item.get("name"), str):
            values.add(item["name"].casefold())
        elif isinstance(item, str):
            values.add(item.casefold())
    return values


def classify_information_utility(
    content: dict[str, object],
    *,
    intent: ResearchIntentContract,
    extracted_entities: Iterable[str] = (),
    known_memory_keys: Iterable[str] = (),
    is_repost: bool = False,
    adopted: bool = False,
) -> list[InformationUtilityAssessment]:
    """Return explainable, multi-label value assessments for one content item.

    This deterministic baseline is deliberately fail-open for useful material:
    a model may refine it later, but a provider outage must not erase discovery
    seeds, counterevidence, or memory updates.
    """
    body = _text(content).casefold()
    if is_repost:
        return [InformationUtilityAssessment("duplicate", "与已知内容高度重复或为跨平台转载。", 0.96)]
    if not body:
        return [InformationUtilityAssessment("noise", "内容没有可判断的事实文本。", 0.95)]
    assessments: list[InformationUtilityAssessment] = []
    negative = [term for term in NEGATIVE_TERMS if term.casefold() in body]
    event = [term for term in EVENT_TERMS if term.casefold() in body]
    marketing = [term for term in MARKETING_TERMS if term.casefold() in body]
    opportunity = [term for term in OPPORTUNITY_TERMS if term.casefold() in body]
    known = _known_names(intent)
    known.update(item.casefold() for item in known_memory_keys if item and item.strip())
    entities = [item.strip() for item in extracted_entities if item and item.strip()]
    new_entities = [item for item in entities if item.casefold() not in known]
    target_text = " ".join(
        [intent.interpreted_goal, str(intent.subject), *intent.unknowns_to_discover]
    ).casefold()
    relevant = any(token and token in body for token in target_text.split() if len(token) >= 2)
    if new_entities:
        assessments.append(
            InformationUtilityAssessment(
                "discovery_seed",
                f"包含待确认的新实体：{'、'.join(new_entities[:5])}。",
                0.86,
            )
        )
    if negative and intent.negative_evidence_requirements:
        assessments.append(
            InformationUtilityAssessment(
                "counterevidence",
                f"出现反向证据线索：{'、'.join(negative[:4])}。",
                0.84,
            )
        )
    if event:
        assessments.append(
            InformationUtilityAssessment(
                "event_signal",
                f"包含可能的事件变化：{'、'.join(event[:4])}。",
                0.8,
            )
        )
    if opportunity and ("product_opportunity" in {intent.primary_intent, *intent.secondary_intents} or "content_opportunity" in {intent.primary_intent, *intent.secondary_intents}):
        assessments.append(
            InformationUtilityAssessment(
                "action_trigger",
                "内容包含待研究的需求、缺口或机会信号。",
                0.72,
            )
        )
    if marketing and not new_entities and not negative:
        assessments.append(InformationUtilityAssessment("noise", "主要是推广或转化文案，缺少独立事实增量。", 0.82))
    elif relevant or new_entities or negative or event:
        if adopted:
            assessments.append(InformationUtilityAssessment("core_evidence", "内容已被 Finding 采用并直接支撑研究结论。", 0.92))
        else:
            assessments.append(InformationUtilityAssessment("background_context", "与当前意图相关，可帮助理解领域但尚未形成结论。", 0.62))
        if entities or event:
            assessments.append(InformationUtilityAssessment("memory_update", "包含可用于后续研究的实体属性、事实或时间变化。", 0.7))
    else:
        assessments.append(InformationUtilityAssessment("noise", "与当前研究意图的事实相关性不足。", 0.72))
    if not assessments:
        assessments.append(InformationUtilityAssessment("background_context", "内容可作为研究背景保留。", 0.5))
    return list(dict.fromkeys(assessments))


def event_type_for_content(content: dict[str, object]) -> str | None:
    body = _text(content).casefold()
    mappings = (
        ("new_version", ("新版本", "更新", "升级")),
        ("new_pricing", ("定价", "涨价", "价格")),
        ("failure", ("故障", "崩溃", "不可用", "失败")),
        ("partnership", ("合作", "联名")),
        ("launch", ("上线", "发布")),
    )
    for event_type, terms in mappings:
        if any(term in body for term in terms):
            return event_type
    return None
