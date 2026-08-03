from __future__ import annotations

import hashlib
from collections import defaultdict
from collections.abc import Iterable

from app.repositories.discovery import DiscoveryRepository
from app.repositories.research import ResearchTaskRepository

_NEGATIVE_TERMS = (
    "不好用",
    "难用",
    "失败",
    "缺点",
    "问题",
    "吐槽",
    "踩坑",
    "不稳定",
    "无法",
    "bug",
    "缺陷",
)
_NEED_TERMS = (
    "需要",
    "希望",
    "想要",
    "寻找",
    "痛点",
    "场景",
    "workflow",
    "工作流",
    "需求",
)
_PRODUCT_TERMS = (
    "工具",
    "产品",
    "工作台",
    "软件",
    "app",
    "agent",
    "ai",
    "平台",
)
_MARKETING_TERMS = (
    "官网",
    "限时",
    "优惠",
    "立即购买",
    "扫码",
    "注册链接",
    "独家",
    "领先",
)
_GENERIC_KEYS = {"ai", "agent", "app", "api", "工具", "软件", "产品", "工作台"}
_SCORE_FIELDS = (
    "relevance_score",
    "novelty_score",
    "evidence_strength_score",
    "source_independence_score",
    "cross_platform_score",
    "counterevidence_score",
    "actionability_score",
    "feedback_score",
    "noise_risk_score",
    "marketing_risk_score",
    "saturation_score",
    "resource_cost_score",
    "final_score",
)


def _clamp(value: float) -> float:
    return max(0.0, min(1.0, value))


def _norm(value: object) -> str:
    return " ".join(str(value or "").casefold().strip().split())


def _short(value: object, limit: int) -> str:
    return str(value or "").strip()[:limit]


def _content_text(content: dict[str, object]) -> str:
    return _norm(f"{content.get('title', '')} {content.get('description', '')}")


def _content_signature(content: dict[str, object]) -> str:
    text = _content_text(content)
    return hashlib.sha256(text.encode("utf-8")).hexdigest() if text else ""


def _independent_group(content: dict[str, object]) -> str:
    url = _norm(content.get("source_url"))
    if url:
        return f"url:{url}"
    platform = _norm(content.get("platform")) or "unknown"
    author = _norm(content.get("author_source_id")) or _norm(content.get("author_name"))
    if author:
        return f"author:{platform}:{author}"
    return f"content:{content.get('id', '')}"


def _actionability(candidate_type: str) -> float:
    return {
        "entity": 0.62,
        "creator": 0.58,
        "topic": 0.55,
        "event": 0.7,
        "query": 0.52,
        "pain_point": 0.82,
        "need": 0.8,
        "product_opportunity_signal": 0.88,
        "content_opportunity_signal": 0.78,
    }.get(candidate_type, 0.5)


def _score(values: dict[str, float]) -> float:
    weights = {
        "relevance_score": 0.19,
        "novelty_score": 0.14,
        "evidence_strength_score": 0.14,
        "source_independence_score": 0.1,
        "cross_platform_score": 0.09,
        "counterevidence_score": 0.07,
        "actionability_score": 0.1,
        "feedback_score": 0.08,
        "noise_risk_score": -0.04,
        "marketing_risk_score": -0.025,
        "saturation_score": -0.015,
        "resource_cost_score": -0.005,
    }
    return _clamp(sum(values.get(key, 0.0) * weight for key, weight in weights.items()))


def _state_for_score(value: float) -> str:
    return "queued" if value >= 0.55 else "scored"


class DiscoveryEngine:
    """Bounded, auditable discovery generation for one research task."""

    def __init__(
        self,
        *,
        discovery: DiscoveryRepository,
        research: ResearchTaskRepository,
        production_verified_platforms: Iterable[str] | None = None,
    ) -> None:
        self.discovery = discovery
        self.research = research
        self.production_verified_platforms = (
            tuple(dict.fromkeys(str(platform).casefold() for platform in production_verified_platforms))
            if production_verified_platforms is not None
            else None
        )

    def _allowed_platforms(self, task: dict[str, object]) -> tuple[str, ...] | None:
        task_platforms = tuple(
            dict.fromkeys(
                str(platform).casefold()
                for platform in task.get("platforms", [])
                if isinstance(platform, str) and platform.strip()
            )
        )
        if self.production_verified_platforms is None:
            return task_platforms or None
        verified = set(self.production_verified_platforms)
        if task_platforms:
            verified.intersection_update(task_platforms)
        return tuple(platform for platform in self.production_verified_platforms if platform in verified)

    def _is_allowed_content(self, content: dict[str, object] | None, task: dict[str, object]) -> bool:
        if content is None:
            return False
        allowed = self._allowed_platforms(task)
        return allowed is None or str(content.get("platform") or "").casefold() in allowed

    def generate_for_task(
        self,
        task_id: str,
        *,
        max_depth: int = 1,
        max_seeds: int = 24,
        max_candidates: int = 30,
    ) -> dict[str, object]:
        existing_run = self.discovery.latest_completed_run(task_id)
        if existing_run is not None:
            return {
                "run": existing_run,
                "seeds": self.discovery.list_seeds(task_id),
                "candidates": self.discovery.list_task_candidates(task_id),
            }
        task = self.research.get_for_runtime(task_id, detail=True)
        if task is None:
            raise KeyError(task_id)
        owner_id = str(task["user_id"])
        run = self.discovery.create_run(task_id=task_id, depth=max_depth)
        try:
            seeds = self._collect_seeds(task, str(run["id"]), max_seeds)
            candidate_inputs = self._candidate_inputs(task, seeds, max_candidates)
            saved: list[dict[str, object]] = []
            platform_names: set[str] = set()
            for input_item in candidate_inputs:
                sources = self._sources_for_input(input_item, task, limit=12)
                if not sources:
                    continue
                platform_names.update(
                    str(source.get("platform"))
                    for source in sources
                    if source.get("platform")
                )
                score_data = self._score_input(
                    input_item,
                    sources,
                    task,
                    owner_id=owner_id,
                )
                candidate = self.discovery.upsert_candidate(
                    owner_id=owner_id,
                    task_id=task_id,
                    run_id=str(run["id"]),
                    candidate_type=str(input_item["candidate_type"]),
                    title=str(input_item["title"]),
                    summary=str(input_item["summary"]),
                    normalized_key=str(input_item["normalized_key"]),
                    parent_candidate_id=(
                        str(input_item["parent_candidate_id"])
                        if input_item.get("parent_candidate_id")
                        else None
                    ),
                    source_seed_id=(
                        str(input_item["source_seed_id"])
                        if input_item.get("source_seed_id")
                        else None
                    ),
                    source_content_id=(
                        str(input_item["source_content_id"])
                        if input_item.get("source_content_id")
                        else None
                    ),
                    source_platform=(
                        str(input_item["source_platform"])
                        if input_item.get("source_platform")
                        else None
                    ),
                    scores=score_data["scores"],
                    score_explanation=score_data["explanation"],
                    counts=score_data["counts"],
                    depth=max_depth,
                    state=_state_for_score(score_data["scores"]["final_score"]),
                    suggested_next_action=str(input_item.get("suggested_next_action") or "继续验证独立来源与反向证据"),
                    experimental_status=input_item.get("experimental_status"),
                )
                for source in sources:
                    self.discovery.add_candidate_source(
                        candidate_id=str(candidate["id"]),
                        seed_id=(str(input_item["source_seed_id"]) if input_item.get("source_seed_id") else None),
                        task_id=task_id,
                        content=source["content"] if isinstance(source.get("content"), dict) else None,
                        source_kind=str(source.get("source_kind") or "evidence"),
                        is_repost=bool(source.get("is_repost")),
                        repost_of_content_id=(
                            str(source["repost_of_content_id"])
                            if source.get("repost_of_content_id")
                            else None
                        ),
                        similarity_score=(
                            float(source["similarity_score"])
                            if source.get("similarity_score") is not None
                            else None
                        ),
                        independent_group=(
                            str(source["independent_group"])
                            if source.get("independent_group")
                            else None
                        ),
                    )
                saved.append(candidate)
            status = "completed" if saved else "partial"
            stop_reason = None if saved else "no eligible source-bound discovery candidates"
            final_run = self.discovery.finish_run(
                str(run["id"]),
                status=status,
                seed_count=len(seeds),
                candidate_count=len(saved),
                platform_count=len(platform_names),
                stop_reason=stop_reason,
            )
            return {"run": final_run, "seeds": seeds, "candidates": saved}
        except Exception as error:
            self.discovery.finish_run(
                str(run["id"]),
                status="failed",
                seed_count=0,
                candidate_count=0,
                platform_count=0,
                stop_reason=str(error)[:500],
            )
            raise

    def _collect_seeds(
        self,
        task: dict[str, object],
        run_id: str,
        max_seeds: int,
    ) -> list[dict[str, object]]:
        task_id = str(task["id"])
        owner_id = str(task["user_id"])
        utilities = task.get("information_utilities")
        utilities = utilities if isinstance(utilities, list) else []
        allowed_utilities = {
            "core_evidence",
            "discovery_seed",
            "counterevidence",
            "event_signal",
            "memory_update",
        }
        seeds: list[dict[str, object]] = []
        seen: set[tuple[str, str, str, str, str]] = set()

        def append_seed(
            *,
            seed_type: str,
            source_content_id: str | None,
            relation_to_intent: str,
            novelty: float,
            confidence: float,
            information_utility: str,
            source_finding_id: str | None = None,
            source_entity_candidate_id: str | None = None,
            source_event_candidate_id: str | None = None,
            source_candidate_id: str | None = None,
        ) -> bool:
            if len(seeds) >= max_seeds:
                return False
            if source_content_id:
                source_content = self.discovery.get_content(source_content_id)
                if not self._is_allowed_content(source_content, task):
                    return False
            key = (
                seed_type,
                source_content_id or "",
                source_entity_candidate_id or "",
                source_event_candidate_id or "",
                source_candidate_id or "",
            )
            if key in seen:
                return True
            seen.add(key)
            seeds.append(
                self.discovery.create_seed(
                    task_id=task_id,
                    run_id=run_id,
                    seed_type=seed_type,
                    source_content_id=source_content_id,
                    source_finding_id=source_finding_id,
                    source_entity_candidate_id=source_entity_candidate_id,
                    source_event_candidate_id=source_event_candidate_id,
                    source_candidate_id=source_candidate_id,
                    relation_to_intent=relation_to_intent,
                    novelty=novelty,
                    confidence=confidence,
                    information_utility=information_utility,
                )
            )
            return True

        for item in utilities:
            if not isinstance(item, dict) or str(item.get("utility_type")) not in allowed_utilities:
                continue
            content_id = str(item.get("content_id") or "")
            if not content_id:
                continue
            append_seed(
                seed_type=str(item["utility_type"]),
                source_content_id=content_id,
                source_finding_id=(str(item["source_finding_id"]) if item.get("source_finding_id") else None),
                relation_to_intent=str(item.get("rationale") or "来源内容与当前研究意图存在信息用途关系"),
                novelty=0.7 if item["utility_type"] in {"discovery_seed", "event_signal"} else 0.5,
                confidence=float(item.get("confidence") or 0.5),
                information_utility=str(item["utility_type"]),
            )
            if len(seeds) >= max_seeds:
                return seeds

        for content in self.discovery.list_favorite_contents(limit=max_seeds):
            content_id = str(content.get("id") or "") or None
            if append_seed(
                seed_type="favorite",
                source_content_id=content_id,
                relation_to_intent="用户明确收藏的内容是长期研究偏好的来源种子",
                novelty=0.65,
                confidence=0.8,
                information_utility="discovery_seed",
            ) and len(seeds) >= max_seeds:
                return seeds

        for candidate in self.discovery.list_accepted_candidates(
            owner_id=owner_id,
            exclude_task_id=task_id,
            limit=max_seeds,
        ):
            source_content_id = str(candidate.get("source_content_id") or "") or None
            append_seed(
                seed_type="accepted_candidate",
                source_content_id=source_content_id,
                source_candidate_id=str(candidate.get("id") or "") or None,
                relation_to_intent="用户已采纳的历史 Discovery 候选可作为后续研究的明确方向",
                novelty=float(candidate.get("novelty_score") or 0.6),
                confidence=float(candidate.get("evidence_strength_score") or 0.6),
                information_utility="discovery_seed",
            )
            if len(seeds) >= max_seeds:
                return seeds

        for entity in self.discovery.list_space_entity_candidates(
            owner_id=owner_id,
            limit=max_seeds,
        ):
            source_content_id = str(entity.get("source_content_id") or "") or None
            append_seed(
                seed_type="space_entity",
                source_content_id=source_content_id,
                source_entity_candidate_id=str(entity.get("id") or "") or None,
                relation_to_intent=(
                    f"研究空间 {entity.get('focus_space_id')} 中的焦点实体应优先验证"
                ),
                novelty=float(entity.get("novelty") or 0.6),
                confidence=float(entity.get("confidence") or 0.6),
                information_utility="discovery_seed",
            )
            if len(seeds) >= max_seeds:
                return seeds

        for event in self.discovery.list_confirmed_events(
            owner_id=owner_id,
            limit=max_seeds,
        ):
            source_content_id = str(event.get("source_content_id") or "") or None
            append_seed(
                seed_type="confirmed_event",
                source_content_id=source_content_id,
                source_event_candidate_id=str(event.get("id") or "") or None,
                relation_to_intent="用户确认的事件是变化验证和跨平台回搜的高优先级种子",
                novelty=0.75,
                confidence=float(event.get("confidence") or 0.6),
                information_utility="event_signal",
            )
            if len(seeds) >= max_seeds:
                return seeds

        entities = task.get("entity_candidates")
        entities = entities if isinstance(entities, list) else []
        for item in entities:
            if not isinstance(item, dict) or str(item.get("status")) == "dismissed":
                continue
            name = _norm(item.get("normalized_name"))
            if not name or name in _GENERIC_KEYS:
                continue
            content_id = str(item.get("source_content_id") or "") or None
            append_seed(
                seed_type="discovery_seed",
                source_content_id=content_id,
                source_entity_candidate_id=(str(item["id"]) if item.get("id") else None),
                relation_to_intent="8D-0 实体候选是有限 Discovery 的来源种子",
                novelty=float(item.get("novelty") or 0.5),
                confidence=float(item.get("confidence") or 0.5),
                information_utility="discovery_seed",
            )
            if len(seeds) >= max_seeds:
                return seeds
        events = task.get("event_candidates")
        events = events if isinstance(events, list) else []
        for item in events:
            if not isinstance(item, dict) or str(item.get("status")) == "dismissed":
                continue
            content_id = str(item.get("source_content_id") or "") or None
            append_seed(
                seed_type="confirmed_event" if str(item.get("status")) == "accepted" else "discovery_seed",
                source_content_id=content_id,
                source_event_candidate_id=(str(item["id"]) if item.get("id") else None),
                relation_to_intent="事件候选提供了变化、发布或争议的有限扩展入口",
                novelty=0.75,
                confidence=float(item.get("confidence") or 0.5),
                information_utility="event_signal",
            )
            if len(seeds) >= max_seeds:
                return seeds
        return seeds

    def _candidate_inputs(
        self,
        task: dict[str, object],
        seeds: list[dict[str, object]],
        max_candidates: int,
    ) -> list[dict[str, object]]:
        entity_by_id = {
            str(item.get("id")): item
            for item in (task.get("entity_candidates") or [])
            if isinstance(item, dict) and item.get("id")
        }
        event_by_id = {
            str(item.get("id")): item
            for item in (task.get("event_candidates") or [])
            if isinstance(item, dict) and item.get("id")
        }
        utilities_by_content: dict[str, set[str]] = defaultdict(set)
        for item in task.get("information_utilities") or []:
            if isinstance(item, dict) and item.get("content_id"):
                utilities_by_content[str(item["content_id"])].add(str(item.get("utility_type")))
        intent_contract = task.get("intent_contract")
        primary_intent = (
            str(intent_contract.get("primary_intent"))
            if isinstance(intent_contract, dict)
            else ""
        )
        pain_point_research = primary_intent == "pain_point_research"
        results: list[dict[str, object]] = []
        seen: set[tuple[str, str]] = set()
        for seed in seeds:
            content_id = str(seed.get("source_content_id") or "") or None
            entity_id = str(seed.get("source_entity_candidate_id") or "")
            event_id = str(seed.get("source_event_candidate_id") or "")
            entity = entity_by_id.get(entity_id)
            event = event_by_id.get(event_id)
            if entity is not None:
                name = _short(entity.get("normalized_name"), 300)
                key = ("entity", _norm(name))
                if name and key not in seen and _norm(name) not in _GENERIC_KEYS:
                    seen.add(key)
                    candidate_type = "creator" if str(entity.get("entity_type")) == "creator" else "entity"
                    results.append(
                        {
                            "candidate_type": candidate_type,
                            "title": name,
                            "summary": "来自研究证据中的新实体候选；需要继续验证真实使用场景、反馈和限制。",
                            "normalized_key": _norm(name),
                            "source_seed_id": seed.get("id"),
                            "source_content_id": content_id,
                            "source_platform": None,
                            "base_relevance": float(entity.get("relevance_to_intent") or 0.5),
                            "base_novelty": float(entity.get("novelty") or seed.get("novelty") or 0.5),
                            "base_confidence": float(entity.get("confidence") or seed.get("confidence") or 0.5),
                        }
                    )
            if event is not None:
                title = _short(event.get("title"), 300)
                key = ("event", _norm(title))
                if title and key not in seen:
                    seen.add(key)
                    results.append(
                        {
                            "candidate_type": "event",
                            "title": title,
                            "summary": _short(event.get("summary") or "来源事件候选，仍需确认发生时间、变化和反向证据。", 2_000),
                            "normalized_key": _norm(title),
                            "source_seed_id": seed.get("id"),
                            "source_content_id": content_id,
                            "source_platform": None,
                            "base_relevance": 0.75,
                            "base_novelty": 0.75,
                            "base_confidence": float(event.get("confidence") or 0.5),
                        }
                    )
            if content_id and (
                utilities_by_content.get(content_id, set())
                & {"core_evidence", "discovery_seed", "counterevidence", "event_signal"}
                or pain_point_research
            ):
                content = self.discovery.get_content(content_id)
                text = _content_text(content or {})
                if any(term in text for term in _NEGATIVE_TERMS):
                    title = _short((content or {}).get("title") or content_id, 300)
                    key = ("pain_point", content_id)
                    if key not in seen:
                        seen.add(key)
                        results.append(
                            {
                                "candidate_type": "pain_point",
                                "title": title,
                                "summary": _short((content or {}).get("description") or "来源记录了与工具使用相关的负向体验或限制，需寻找独立用户证据。", 2_000),
                                "normalized_key": f"pain:{content_id}",
                                "source_seed_id": seed.get("id"),
                                "source_content_id": content_id,
                                "source_platform": (content or {}).get("platform"),
                                "base_relevance": 0.82,
                                "base_novelty": 0.7,
                                "base_confidence": float(seed.get("confidence") or 0.5),
                            }
                        )
            if len(results) >= max_candidates:
                break

        def add_derived_candidate(
            *,
            candidate_type: str,
            title: str,
            summary: str,
            normalized_key: str,
            seed: dict[str, object],
            content: dict[str, object] | None,
            base_relevance: float,
            base_novelty: float,
            base_confidence: float,
            suggested_next_action: str,
            experimental_status: str | None = None,
        ) -> None:
            if len(results) >= max_candidates:
                return
            normalized = _norm(normalized_key)
            key = (candidate_type, normalized)
            if not normalized or key in seen:
                return
            seen.add(key)
            results.append(
                {
                    "candidate_type": candidate_type,
                    "title": _short(title, 300),
                    "summary": _short(summary, 2_000),
                    "normalized_key": normalized,
                    "source_seed_id": seed.get("id"),
                    "source_content_id": (str(content.get("id")) if content and content.get("id") else None),
                    "source_platform": (str(content.get("platform")) if content and content.get("platform") else None),
                    "base_relevance": _clamp(base_relevance),
                    "base_novelty": _clamp(base_novelty),
                    "base_confidence": _clamp(base_confidence),
                    "suggested_next_action": suggested_next_action,
                    "experimental_status": experimental_status,
                }
            )

        for seed in seeds:
            content_id = str(seed.get("source_content_id") or "") or None
            content = self.discovery.get_content(content_id) if content_id else None
            accepted_candidate = None
            source_candidate_id = str(seed.get("source_candidate_id") or "")
            if source_candidate_id:
                accepted_candidate = self.discovery.get_candidate(
                    owner_id=str(task["user_id"]),
                    candidate_id=source_candidate_id,
                    detail=False,
                )
            if content is None and accepted_candidate is None:
                continue
            if content is not None and not self._is_allowed_content(content, task):
                continue
            title = _short(
                (content or {}).get("source_keyword")
                or (content or {}).get("title")
                or (accepted_candidate or {}).get("title")
                or content_id,
                180,
            )
            text = _content_text(content or accepted_candidate or {})
            if not title or _norm(title) in _GENERIC_KEYS:
                continue
            source_seed_confidence = float(seed.get("confidence") or 0.5)
            source_seed_novelty = float(seed.get("novelty") or 0.5)
            source_platform = str((content or {}).get("platform") or "")
            if str(seed.get("seed_type")) == "confirmed_event" or str(seed.get("information_utility")) == "event_signal":
                add_derived_candidate(
                    candidate_type="event",
                    title=f"事件信号：{title}",
                    summary="来源内容提供了可聚合的变化或发布信号；需要确认时间、相关实体、正负证据和未知项。",
                    normalized_key=f"event:{title}",
                    seed=seed,
                    content=content,
                    base_relevance=0.78,
                    base_novelty=max(0.7, source_seed_novelty),
                    base_confidence=source_seed_confidence,
                    suggested_next_action="补齐相近时间的独立来源并核对事件变化",
                )
            topic_title = f"{title} 相关主题"
            add_derived_candidate(
                candidate_type="topic",
                title=topic_title,
                summary="来源内容形成了可继续观察的主题边界；需要跨平台验证其稳定性和新变化。",
                normalized_key=f"topic:{title}",
                seed=seed,
                content=content,
                base_relevance=0.68,
                base_novelty=source_seed_novelty,
                base_confidence=source_seed_confidence,
                suggested_next_action="在已通过生产门禁的平台上验证主题变化",
            )
            add_derived_candidate(
                candidate_type="query",
                title=f"验证：{title}",
                summary=f"围绕“{title}”的下一条有限执行查询方向，保留来源和平台边界。",
                normalized_key=f"query:{title}",
                seed=seed,
                content=content,
                base_relevance=0.72,
                base_novelty=0.62,
                base_confidence=source_seed_confidence,
                suggested_next_action="继续研究该查询方向，并检查反向证据",
            )
            has_need = any(term in text for term in _NEED_TERMS)
            has_negative = any(term in text for term in _NEGATIVE_TERMS)
            if has_need or pain_point_research:
                add_derived_candidate(
                    candidate_type="need",
                    title=f"用户需求：{title}",
                    summary="来源内容显式表达了需求、期望或使用场景；仍需独立用户证据确认普遍性。",
                    normalized_key=f"need:{title}",
                    seed=seed,
                    content=content,
                    base_relevance=0.84,
                    base_novelty=0.72,
                    base_confidence=source_seed_confidence,
                    suggested_next_action="寻找来自不同作者和平台的相同需求表达",
                )
            if has_negative or pain_point_research:
                add_derived_candidate(
                    candidate_type="pain_point",
                    title=f"痛点：{title}",
                    summary="来源内容包含负向体验或限制信号；需区分单个用户抱怨、转载和可复现问题。",
                    normalized_key=f"pain:{content_id or title}",
                    seed=seed,
                    content=content,
                    base_relevance=0.86,
                    base_novelty=0.74,
                    base_confidence=source_seed_confidence,
                    suggested_next_action="搜索直接负向证据并合并疑似转载",
                )
            if (
                any(term in text for term in _PRODUCT_TERMS)
                and (has_need or has_negative or primary_intent in {"product_opportunity", "discovery"})
            ):
                add_derived_candidate(
                    candidate_type="product_opportunity_signal",
                    title=f"产品机会：{title}",
                    summary="从来源中的需求或限制提炼出的产品机会信号，不等同于已验证的市场结论。",
                    normalized_key=f"product-opportunity:{title}",
                    seed=seed,
                    content=content,
                    base_relevance=0.8,
                    base_novelty=0.76,
                    base_confidence=source_seed_confidence,
                    suggested_next_action="验证是否存在跨平台、跨作者的重复需求，再形成产品假设",
                )
                add_derived_candidate(
                    candidate_type="content_opportunity_signal",
                    title=f"内容机会：{title}",
                    summary="从可验证的需求、限制或变化中提炼出的内容选题信号，不自动发布。",
                    normalized_key=f"content-opportunity:{title}",
                    seed=seed,
                    content=content,
                    base_relevance=0.76,
                    base_novelty=0.7,
                    base_confidence=source_seed_confidence,
                    suggested_next_action="用独立来源补齐事实、反例和受众边界",
                )
            if source_platform and str(seed.get("source_entity_candidate_id") or ""):
                entity = entity_by_id.get(str(seed.get("source_entity_candidate_id")))
                if entity and str(entity.get("entity_type")) == "creator":
                    # Relationship/recommendation data is not inferred from a
                    # single content record; show the candidate as experimental.
                    add_derived_candidate(
                        candidate_type="creator",
                        title=title,
                        summary="创作者候选来自显式来源记录；关系图和推荐暂不可用，需独立验证。",
                        normalized_key=f"creator:{title}",
                        seed=seed,
                        content=content,
                        base_relevance=0.62,
                        base_novelty=source_seed_novelty,
                        base_confidence=source_seed_confidence,
                        suggested_next_action="仅验证显式创作者资料，不推断未记录的关系",
                        experimental_status="experimental_not_available",
                    )
        return results[:max_candidates]

    def _sources_for_input(
        self,
        input_item: dict[str, object],
        task: dict[str, object],
        *,
        limit: int,
    ) -> list[dict[str, object]]:
        source_id = str(input_item.get("source_content_id") or "")
        source_content = self.discovery.get_content(source_id) if source_id else None
        if source_content is not None and not self._is_allowed_content(source_content, task):
            source_content = None
        candidate_type = str(input_item.get("candidate_type"))
        search_term = str(input_item.get("title") or "")
        if candidate_type == "pain_point" and source_content is not None:
            search_term = _short(source_content.get("title") or source_content.get("description"), 100)
        contents: list[dict[str, object]] = []
        if source_content is not None:
            contents.append(source_content)
        allowed_platforms = self._allowed_platforms(task)
        if search_term and candidate_type != "event":
            contents.extend(
                self.discovery.find_related_contents(
                    search_term,
                    limit=limit,
                    platforms=allowed_platforms,
                )
            )
        elif candidate_type == "event" and source_content is not None:
            contents.extend(
                self.discovery.find_related_contents(
                    str(source_content.get("title") or ""),
                    limit=limit,
                    platforms=allowed_platforms,
                )
            )
        cards = task.get("context")
        cards = cards.get("content_cards") if isinstance(cards, dict) else []
        utility_types: dict[str, set[str]] = defaultdict(set)
        for utility in task.get("information_utilities") or []:
            if isinstance(utility, dict) and utility.get("content_id"):
                utility_types[str(utility["content_id"])].add(str(utility.get("utility_type")))
        if isinstance(cards, list):
            known_ids = {str(item.get("id")) for item in contents if item.get("id")}
            for card in cards:
                if not isinstance(card, dict) or not card.get("id"):
                    continue
                content_id = str(card["id"])
                if content_id in known_ids:
                    continue
                fetched = self.discovery.get_content(content_id)
                if fetched is not None and self._is_allowed_content(fetched, task) and (
                    _norm(input_item.get("title")) in _content_text(fetched)
                    or candidate_type == "pain_point"
                    and any(term in _content_text(fetched) for term in _NEGATIVE_TERMS)
                ):
                    contents.append(fetched)
                    known_ids.add(content_id)
        unique: list[dict[str, object]] = []
        seen_ids: set[str] = set()
        signatures: dict[str, str] = {}
        for content in contents:
            content_id = str(content.get("id") or "")
            if not content_id or content_id in seen_ids:
                continue
            if not self._is_allowed_content(content, task):
                continue
            if not str(content.get("description") or "").strip():
                continue
            content_text = _content_text(content)
            if not content_text:
                continue
            content_utilities = utility_types.get(content_id, set())
            if content_utilities.intersection({"noise", "duplicate"}):
                continue
            marketing_hits = sum(term in content_text for term in _MARKETING_TERMS)
            if marketing_hits >= 2:
                continue
            seen_ids.add(content_id)
            signature = _content_signature(content)
            repost_of = signatures.get(signature) if signature else None
            if signature:
                signatures.setdefault(signature, content_id)
            unique.append(
                {
                    "content": content,
                    "source_kind": (
                        "cross_platform_validation"
                        if source_content is not None
                        and content_id != source_id
                        and str(content.get("platform") or "")
                        != str(source_content.get("platform") or "")
                        else "seed_evidence"
                    ),
                    "is_repost": repost_of is not None,
                    "repost_of_content_id": repost_of,
                    "similarity_score": 1.0 if repost_of is not None else None,
                    "independent_group": _independent_group(content),
                }
            )
            if len(unique) >= limit:
                break
        return unique

    def _score_input(
        self,
        input_item: dict[str, object],
        sources: list[dict[str, object]],
        task: dict[str, object],
        *,
        owner_id: str,
    ) -> dict[str, object]:
        content_items = [
            item["content"] for item in sources if isinstance(item.get("content"), dict)
        ]
        independent_groups = {
            str(item.get("independent_group")) for item in sources if item.get("independent_group")
        }
        platforms = {
            str(content.get("platform")) for content in content_items if content.get("platform")
        }
        repost_count = sum(1 for item in sources if item.get("is_repost"))
        content_count = len(content_items)
        independent_count = len(independent_groups)
        utilities_by_content: dict[str, set[str]] = defaultdict(set)
        for item in task.get("information_utilities") or []:
            if isinstance(item, dict) and item.get("content_id"):
                utilities_by_content[str(item["content_id"])].add(str(item.get("utility_type")))
        counterevidence = sum(
            1
            for content in content_items
            if "counterevidence" in utilities_by_content.get(str(content.get("id")), set())
        )
        noise_count = sum(
            1
            for content in content_items
            if "noise" in utilities_by_content.get(str(content.get("id")), set())
        )
        marketing_count = sum(
            1
            for content in content_items
            if any(term in _content_text(content) for term in _MARKETING_TERMS)
        )
        candidate_type = str(input_item["candidate_type"])
        intent = task.get("intent_contract")
        intent_names = {
            str(intent.get("primary_intent"))
            for intent in [intent]
            if isinstance(intent, dict)
        }
        if isinstance(intent, dict):
            intent_names.update(str(value) for value in intent.get("secondary_intents", []) if isinstance(value, str))
        topic_key = _norm(input_item.get("title"))
        intent_id = str(intent.get("id")) if isinstance(intent, dict) and intent.get("id") else None
        feedback_adjustment, feedback_rules = self.discovery.active_feedback_adjustment(
            owner_id=owner_id,
            candidate_type=candidate_type,
            platform=(str(input_item.get("source_platform")) if input_item.get("source_platform") else None),
            topic_key=topic_key,
            intent_id=intent_id,
        )
        feedback_score = _clamp(0.5 + feedback_adjustment)
        relevance = _clamp(float(input_item.get("base_relevance") or 0.5))
        novelty = _clamp(float(input_item.get("base_novelty") or 0.5))
        evidence_strength = _clamp(min(1.0, independent_count / 3))
        independence = _clamp(independent_count / max(1, content_count))
        cross_platform = _clamp(len(platforms) / 2)
        counter = _clamp(counterevidence / max(1, content_count))
        noise_risk = _clamp(noise_count / max(1, content_count))
        marketing_risk = _clamp(marketing_count / max(1, content_count))
        saturation = _clamp(max(0, content_count - 5) / 5)
        resource_cost = _clamp(0.2 + 0.1 * max(0, len(platforms) - 1))
        if candidate_type == "pain_point" or "pain_point_research" in intent_names:
            counter = max(counter, 0.65 if content_count else 0.4)
        actionability = _actionability(candidate_type)
        scores = {
            "relevance_score": relevance,
            "novelty_score": novelty,
            "evidence_strength_score": evidence_strength,
            "source_independence_score": independence,
            "cross_platform_score": cross_platform,
            "counterevidence_score": counter,
            "actionability_score": actionability,
            "feedback_score": feedback_score,
            "noise_risk_score": noise_risk,
            "marketing_risk_score": marketing_risk,
            "saturation_score": saturation,
            "resource_cost_score": resource_cost,
        }
        scores["final_score"] = _score(scores)
        explanation = {
            "why_relevant": f"与当前 {intent.get('primary_intent') if isinstance(intent, dict) else '研究'!s} 意图相关性为 {relevance:.2f}。",
            "why_new": f"候选的历史新颖性为 {novelty:.2f}；当前记忆与候选键按精确匹配降权。",
            "evidence": f"共有 {content_count} 条内容、{independent_count} 个独立来源，其中 {repost_count} 条疑似转载。",
            "source_independence": f"覆盖 {len(platforms)} 个平台，独立来源程度为 {independence:.2f}。",
            "counterevidence": f"记录到 {counterevidence} 条反向/负向证据用途。",
            "actionability": f"候选类型 {candidate_type} 的行动性先验为 {actionability:.2f}。",
            "feedback": (
                f"用户偏好影响 {feedback_adjustment:+.2f}。"
                if feedback_rules
                else "尚无同类用户反馈，使用中性排序。"
            ),
            "risks": f"噪音风险 {noise_risk:.2f}，营销风险 {marketing_risk:.2f}，饱和度 {saturation:.2f}，资源成本 {resource_cost:.2f}。",
            "recommendation": "继续寻找独立来源和反向证据，再决定是否转为研究任务或加入研究空间。",
            "score_breakdown": {key: round(value, 3) for key, value in scores.items()},
        }
        if candidate_type == "event":
            dated_sources = sorted(
                str(content.get("published_at"))
                for content in content_items
                if content.get("published_at") is not None
            )
            positive_terms = ("提升", "增长", "成功", "改善", "更好", "好用", "发布")
            positive_count = sum(
                any(term in _content_text(content) for term in positive_terms)
                for content in content_items
            )
            negative_count = sum(
                any(term in _content_text(content) for term in _NEGATIVE_TERMS)
                for content in content_items
            )
            related_entities = sorted(
                {
                    str(item.get("normalized_name"))
                    for item in task.get("entity_candidates") or []
                    if isinstance(item, dict) and item.get("normalized_name")
                }
            )
            explanation["event_aggregation"] = {
                "first_seen": dated_sources[0] if dated_sources else None,
                "latest_seen": dated_sources[-1] if dated_sources else None,
                "related_entities": related_entities[:12],
                "platforms": sorted(platforms),
                "positive_evidence_count": positive_count,
                "negative_evidence_count": negative_count,
                "unknown_evidence_count": max(0, content_count - positive_count - negative_count),
            }
        return {
            "scores": scores,
            "explanation": explanation,
            "counts": {
                "content_count": content_count,
                "independent_source_count": independent_count,
                "platform_count": len(platforms),
                "suspected_repost_count": repost_count,
            },
        }

    def rescore_after_feedback(self, *, owner_id: str, candidate_id: str) -> dict[str, object]:
        candidate = self.discovery.get_candidate(owner_id=owner_id, candidate_id=candidate_id, detail=True)
        if candidate is None:
            raise KeyError(candidate_id)
        task = self.research.get_for_runtime(
            str(candidate.get("research_task_id")), detail=True
        )
        intent_contract = task.get("intent_contract") if task else None
        intent_id = (
            str(intent_contract.get("id"))
            if isinstance(intent_contract, dict) and intent_contract.get("id")
            else None
        )
        adjustment, rules = self.discovery.active_feedback_adjustment(
            owner_id=owner_id,
            candidate_type=str(candidate.get("candidate_type")),
            platform=(str(candidate.get("source_platform")) if candidate.get("source_platform") else None),
            topic_key=_norm(candidate.get("title")),
            intent_id=intent_id,
            candidate_id=candidate_id,
        )
        scores = {
            key: _clamp(float(candidate.get(key) or 0))
            for key in _SCORE_FIELDS
            if key != "final_score"
        }
        scores["feedback_score"] = _clamp(0.5 + adjustment)
        scores["final_score"] = _score(scores)
        explanation = candidate.get("score_explanation")
        explanation = dict(explanation) if isinstance(explanation, dict) else {}
        explanation["feedback"] = (
            f"用户反馈规则影响 {adjustment:+.2f}，当前生效规则 {len(rules)} 条。"
            if rules
            else "尚无生效用户反馈规则。"
        )
        explanation["score_breakdown"] = {
            key: round(value, 3) for key, value in scores.items()
        }
        state = str(candidate.get("state"))
        active_feedback = [
            item
            for item in candidate.get("feedback", [])
            if isinstance(item, dict) and not item.get("undone_at")
        ]
        explicit_states = {
            "accepted",
            "ignored",
            "deferred",
            "converted_to_research",
            "added_to_space",
            "dismissed_duplicate",
            "expired",
        }
        if not active_feedback and state in explicit_states:
            lifecycle = candidate.get("lifecycle")
            lifecycle = lifecycle if isinstance(lifecycle, list) else []
            restore_state = next(
                (
                    str(item.get("previous_state"))
                    for item in reversed(lifecycle)
                    if isinstance(item, dict)
                    and item.get("next_state") == state
                    and item.get("previous_state")
                ),
                None,
            )
            next_state = restore_state if restore_state in {"generated", "scored", "queued"} else _state_for_score(scores["final_score"])
        elif state in explicit_states:
            next_state: str | None = state
        else:
            next_state = _state_for_score(scores["final_score"])
        return self.discovery.rescore_candidate(
            owner_id=owner_id,
            candidate_id=candidate_id,
            scores=scores,
            explanation=explanation,
            state=next_state,
        )
