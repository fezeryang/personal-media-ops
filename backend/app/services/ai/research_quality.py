from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from difflib import SequenceMatcher

QUERY_TYPE_VALUES = (
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
)

GENERIC_TERMS = {
    "app",
    "工具",
    "话题",
    "agent",
    "api",
    "人工智能",
    "ai",
    "软件",
    "产品",
}
STOPWORDS = {
    "的",
    "和",
    "与",
    "或",
    "及",
    "当前",
    "值得",
    "寻找",
    "分析",
    "真实",
    "用户",
    "体验",
    "反馈",
    "研究",
    "这个",
    "我们",
    "他们",
    "可以",
    "一个",
    "以及",
    "相关",
    "内容",
    "没有",
    "进行",
}
ENTITY_TERMS = {
    "codex",
    "workbuddy",
    "claude",
    "hermes",
    "openclaw",
    "openai",
    "腾讯",
    "腾讯云",
    "飞书",
    "钉钉",
    "企业微信",
    "小红书",
    "b站",
    "bilibili",
}
PLATFORM_EVIDENCE_STRATEGIES: dict[str, tuple[str, ...]] = {
    "bili": ("教程", "演示", "使用体验", "工作流案例"),
    "zhihu": ("深度分析", "需求讨论", "产品评价", "反向观点"),
    "wb": ("即时发布", "传播变化", "产品动态", "争议"),
    "tieba": ("真实问题", "负面体验", "长期用户反馈", "故障 使用障碍"),
    "xhs": ("实际使用体验", "消费决策", "场景反馈", "易用性", "普通用户评价"),
}
QUERY_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}|[\u4e00-\u9fff]{2,8}")


@dataclass(frozen=True)
class QueryQuality:
    normalized_query: str
    query_type: str
    specificity_score: float
    novelty_score: float
    noise_risk_score: float
    rejection_reason: str | None

    @property
    def accepted(self) -> bool:
        return self.rejection_reason is None


@dataclass(frozen=True)
class StructuredOutputResult:
    value: object | None
    strategy: str
    error: str | None = None


def parse_structured_json(
    value: str,
    *,
    repair_value: str | None = None,
) -> StructuredOutputResult:
    """Decode JSON with one bounded repair attempt and no retry loop."""
    candidates = [(value, "strict_json")]
    stripped = value.strip()
    if stripped.startswith("```") and stripped.endswith("```"):
        lines = stripped.splitlines()
        candidates.append(("\n".join(lines[1:-1]).strip(), "tool_schema"))
    if repair_value is not None:
        candidates.append((repair_value, "json_repair_once"))
    for candidate, strategy in candidates:
        try:
            parsed = json.loads(candidate)
        except (TypeError, ValueError):
            continue
        if isinstance(parsed, (dict, list)):
            return StructuredOutputResult(parsed, strategy)
    return StructuredOutputResult(None, "failed", "structured JSON could not be decoded")


def normalize_query(query: str) -> str:
    """Create a stable, punctuation-insensitive query representation."""

    normalized = unicodedata.normalize("NFKC", query).casefold().strip()
    normalized = re.sub(r"[^\w\u4e00-\u9fff]+", " ", normalized)
    normalized = re.sub(r"_+", " ", normalized)
    return " ".join(normalized.split())


def query_tokens(query: str) -> list[str]:
    return list(dict.fromkeys(token.casefold() for token in QUERY_TOKEN_RE.findall(query)))


def classify_query(query: str) -> str:
    normalized = normalize_query(query)
    tokens = set(query_tokens(normalized))
    if not tokens or tokens.issubset(GENERIC_TERMS):
        return "generic_topic"
    if tokens & {"需求", "痛点", "问题", "外包", "效率"}:
        return "need"
    if tokens & {"场景", "工作流", "自动化", "运营", "写作", "协作"}:
        return "scenario"
    if tokens & {"skill", "mcp", "api", "模型", "记忆", "插件", "多agent"}:
        return "technology"
    if tokens & {"公司", "腾讯", "腾讯云", "openai", "anthropic"}:
        return "company"
    if tokens & ENTITY_TERMS or tokens & {"工作台", "桌面", "助手"}:
        return "product"
    if tokens & {"作者", "创作者", "博主", "up主"}:
        return "creator"
    if tokens & {"人物", "专家", "创始人"}:
        return "person"
    if tokens & {"发布", "上线", "融资", "更新", "事件"}:
        return "event"
    if tokens & {"工具", "软件", "插件", "应用"}:
        return "tool"
    return "generic_topic"


def specificity_score(query: str) -> float:
    tokens = query_tokens(query)
    meaningful = [token for token in tokens if token not in STOPWORDS]
    concrete = [token for token in meaningful if token not in GENERIC_TERMS]
    if not meaningful or not concrete:
        return 0.0
    token_score = min(1.0, len(concrete) / 4)
    length_score = min(1.0, len(normalize_query(query)) / 24)
    entity_bonus = 0.2 if set(concrete) & ENTITY_TERMS else 0.0
    return round(min(1.0, token_score * 0.55 + length_score * 0.25 + entity_bonus), 4)


def noise_risk_score(query: str) -> float:
    tokens = query_tokens(query)
    if not tokens:
        return 1.0
    generic_count = sum(token in GENERIC_TERMS for token in tokens)
    meaningful = [token for token in tokens if token not in STOPWORDS]
    if not meaningful or generic_count == len(tokens):
        return 1.0
    ratio = generic_count / len(tokens)
    return round(min(1.0, 0.85 if ratio >= 0.66 else 0.45 if ratio >= 0.5 else 0.12), 4)


def novelty_score(normalized_query: str, historical_queries: list[str]) -> float:
    if not normalized_query:
        return 0.0
    normalized_history = [normalize_query(item) for item in historical_queries if item]
    if normalized_query in normalized_history:
        return 0.0
    query_set = set(normalized_query.split())
    for previous in normalized_history:
        if SequenceMatcher(None, normalized_query, previous).ratio() >= 0.9:
            return 0.0
        previous_set = set(previous.split())
        if query_set and previous_set:
            overlap = len(query_set & previous_set) / len(query_set | previous_set)
            if overlap >= 0.8:
                return 0.0
    return 1.0


def expected_value_score(
    relevance_score: float | None,
    specificity: float,
    novelty: float,
) -> float | None:
    if relevance_score is None:
        return None
    return round(max(0.0, min(1.0, relevance_score)) * specificity * novelty, 4)


def platform_query_variants(
    entity_or_objective: str,
    platform: str,
    *,
    negative: bool = False,
    limit: int = 5,
) -> list[str]:
    """Build deterministic, platform-native query variants for one branch."""
    subject = " ".join(entity_or_objective.strip().split())
    if not subject:
        return []
    normalized_platform = platform.casefold()
    terms = PLATFORM_EVIDENCE_STRATEGIES.get(
        normalized_platform,
        ("使用体验", "产品评价", "问题"),
    )
    if negative:
        terms = tuple(
            term for term in ("问题", "缺点", "不好用", "失败", "替代", "负面体验")
        )
    return list(dict.fromkeys(f"{subject} {term}" for term in terms))[:limit]


def query_priority_score(
    *,
    relevance_score: float | None,
    specificity_score: float,
    novelty_score: float,
    noise_risk_score: float,
    expected_value_score: float | None,
    entity_diversity_bonus: float = 0,
    platform_diversity_bonus: float = 0,
    negative_evidence_bonus: float = 0,
    estimated_resource_use: float = 0,
) -> float:
    """Return one explainable [0,1] scheduler score."""
    base = expected_value_score
    if base is None:
        base = (relevance_score or 0) * specificity_score * novelty_score
    score = (
        base * 0.45
        + specificity_score * 0.12
        + novelty_score * 0.12
        + max(0.0, 1.0 - noise_risk_score) * 0.08
        + max(0.0, min(1.0, entity_diversity_bonus)) * 0.10
        + max(0.0, min(1.0, platform_diversity_bonus)) * 0.08
        + max(0.0, min(1.0, negative_evidence_bonus)) * 0.08
        - max(0.0, estimated_resource_use) * 0.05
    )
    return round(max(0.0, min(1.0, score)), 4)


def marginal_stop_decision(
    *,
    rounds_below_threshold: int,
    threshold: float,
    round_limit: int,
    has_new_entity: bool,
    has_negative_evidence: bool,
) -> str | None:
    if (
        rounds_below_threshold >= round_limit
        and threshold >= 0
        and not has_new_entity
        and not has_negative_evidence
    ):
        return "skipped_saturation" if threshold <= 0.1 else "skipped_low_marginal_value"
    return None


def evaluate_query(
    query: str,
    *,
    generation_reason: str | None,
    source_type: str,
    historical_queries: list[str],
    parent_query_id: str | None = None,
    source_content_id: str | None = None,
    source_finding_id: str | None = None,
    record_type: str = "execution_query",
    query_role: str = "entity_expansion",
    intent_bound: bool = False,
) -> QueryQuality:
    normalized = normalize_query(query)
    tokens = query_tokens(normalized)
    query_type = classify_query(normalized)
    specificity = specificity_score(normalized)
    novelty = novelty_score(normalized, historical_queries)
    noise = noise_risk_score(normalized)
    reason: str | None = None
    if not normalized or len(normalized) < 2:
        reason = "query 过短或为空"
    elif not generation_reason or not generation_reason.strip():
        reason = "缺少 generation_reason"
    elif record_type == "execution_query" and query_role not in {
        "seed_discovery",
        "cross_platform_validation",
        "counterevidence",
        "competitor_scan",
        "trend_probe",
        "creator_scan",
        "pain_point_probe",
    } and source_type != "user_goal" and (
        parent_query_id is None
        or (source_content_id is None and source_finding_id is None)
    ):
        reason = "后续查询必须绑定 parent_query_id 与来源内容或 Finding"
    elif record_type == "execution_query" and query_role == "seed_discovery" and not intent_bound:
        reason = "seed_discovery 查询必须绑定 Intent Contract"
    elif record_type == "execution_query" and query_role in {
        "cross_platform_validation",
        "counterevidence",
        "competitor_scan",
        "trend_probe",
        "creator_scan",
        "pain_point_probe",
    } and not intent_bound and source_type != "user_goal":
        reason = "语义角色查询必须绑定 Intent Contract"
    elif record_type == "execution_query" and tokens and set(tokens).issubset(GENERIC_TERMS):
        reason = "仅包含泛化词，必须与具体实体或限定场景组合"
    elif record_type == "execution_query" and novelty == 0.0:
        reason = "与本任务或历史任务查询重复"
    elif record_type == "execution_query" and noise >= 0.85:
        reason = "通用词占比过高，噪声风险过高"
    return QueryQuality(
        normalized_query=normalized,
        query_type=query_type,
        specificity_score=specificity,
        novelty_score=novelty,
        noise_risk_score=noise,
        rejection_reason=reason,
    )


def parse_relevance_batch(value: str, count: int) -> list[float] | None:
    """Parse one model batch response without allowing malformed scores through."""

    parsed_result = parse_structured_json(value)
    parsed = parsed_result.value
    if parsed is None:
        return None
    values = parsed.get("relevance_scores") if isinstance(parsed, dict) else parsed
    if not isinstance(values, list) or len(values) != count:
        return None
    scores: list[float] = []
    for item in values:
        if isinstance(item, bool) or not isinstance(item, (int, float)):
            return None
        scores.append(round(max(0.0, min(1.0, float(item))), 4))
    return scores
