from __future__ import annotations

import hashlib
import re
from collections.abc import Iterable

from pydantic import JsonValue

from app.core.config import Settings
from app.crawler.registry import (
    ModeDisabledError,
    PlatformDisabledError,
    UnsupportedPlatformError,
    platform_registry,
)
from app.models.ai import ModelToolDefinition
from app.models.research_intent import ResearchIntentContract
from app.repositories.crawler_tasks import CrawlerTaskRepository
from app.repositories.research import (
    ResearchTaskConflict,
    ResearchTaskNotFound,
    ResearchTaskRepository,
)
from app.services.agent_tools import AgentToolService
from app.services.ai.research_quality import (
    evaluate_query,
    expected_value_score,
    normalize_query,
)

TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{2,}|[\u4e00-\u9fff]{2,8}")
STOPWORDS = {
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
ENTITY_BLOCKLIST = {
    "ai",
    "agent",
    "api",
    "app",
    "code",
    "coding",
    "com",
    "dna",
    "http",
    "https",
    "maldi-tof",
    "ngs",
    "pcr",
    "quot",
    "sop",
    "tool",
    "tools",
    "url",
    "vibe",
    "vibecoding",
    "www",
    "产品",
    "工具",
    "软件",
    "应用",
    "话题",
    "分析",
    "文科生",
}
PRODUCT_HINTS = {
    "chatgpt",
    "claude",
    "claude code",
    "codex",
    "codebuddy",
    "copilot",
    "cursor",
    "deepseek",
    "豆包",
    "飞书",
    "gemini",
    "hermes",
    "即梦",
    "kiro",
    "notion",
    "obsidian",
    "omniwork",
    "openclaw",
    "qoder",
    "trae",
    "within",
    "windsurf",
    "workbuddy",
}
PRODUCT_CONTEXT_TERMS = (
    "个人",
    "用户",
    "普通人",
    "创作者",
    "工作流",
    "效率",
    "内容创作",
    "编程",
    "写作",
    "知识管理",
    "工作台",
    "助手",
    "工具",
    "软件",
    "应用",
    "产品",
    "使用",
    "体验",
    "评测",
    "测评",
    "推荐",
    "对比",
    "自动化",
)
PRODUCT_CONTEXT_RE = re.compile(
    r"([\u4e00-\u9fff]{2,8})(?:AI|ai|工具|助手|工作台|软件|应用|产品)"
)
RESEARCH_DEFAULT_REQUESTED_COUNT = 12


class ResearchToolService:
    """The bounded, in-process Research Agent tool allow-list."""

    # ResearchRuntime uses this marker to keep lightweight unit-test doubles
    # on the historical path while ensuring the production implementation
    # always records and evaluates query candidates before crawling.
    supports_quality_queries = True

    TOOL_NAMES = (
        "search_library",
        "get_content",
        "get_provenance",
        "get_creator_history",
        "submit_crawl",
        "dedupe_check",
        "save_finding",
        "propose_action",
    )

    def __init__(
        self,
        *,
        settings: Settings,
        library_tools: AgentToolService,
        crawler: CrawlerTaskRepository,
        research: ResearchTaskRepository,
    ) -> None:
        self.settings = settings
        self.library_tools = library_tools
        self.crawler = crawler
        self.research = research

    @classmethod
    def definitions(cls) -> list[ModelToolDefinition]:
        schemas: dict[str, tuple[str, dict[str, JsonValue]]] = {
            "search_library": (
                "Search already collected content before requesting a crawl.",
                {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string"},
                        "platform": {"type": "string"},
                    },
                    "required": ["query"],
                },
            ),
            "get_content": (
                "Read one normalized content record without raw payload.",
                {
                    "type": "object",
                    "properties": {"content_id": {"type": "string"}},
                    "required": ["content_id"],
                },
            ),
            "get_provenance": (
                "Return platform, author, publication and crawl provenance.",
                {
                    "type": "object",
                    "properties": {"content_id": {"type": "string"}},
                    "required": ["content_id"],
                },
            ),
            "get_creator_history": (
                "Return bounded normalized history for one creator.",
                {
                    "type": "object",
                    "properties": {"creator_id": {"type": "string"}},
                    "required": ["creator_id"],
                },
            ),
            "submit_crawl": (
                "Submit one bounded asynchronous search crawl. It never waits.",
                {
                    "type": "object",
                    "properties": {
                        "platform": {"type": "string"},
                        "keywords": {"type": "string"},
                        "requested_count": {"type": "integer"},
                        "reason": {"type": "string"},
                        "query_type": {"type": "string"},
                        "parent_query_id": {"type": "string"},
                        "source_content_id": {"type": "string"},
                        "source_finding_id": {"type": "string"},
                        "research_task_id": {"type": "string"},
                        "expected_evidence_role": {
                            "type": "string",
                            "enum": ["direct", "contextual", "contradictory", "background"],
                        },
                    },
                    "required": ["platform", "keywords"],
                },
            ),
            "dedupe_check": (
                "Fingerprint content and attach it to a research event.",
                {
                    "type": "object",
                    "properties": {
                        "content_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "title": {"type": "string"},
                        "summary": {"type": "string"},
                    },
                    "required": ["content_ids"],
                },
            ),
            "save_finding": (
                "Save a fact or inference only when it has content evidence.",
                {
                    "type": "object",
                    "properties": {
                        "kind": {"type": "string", "enum": ["fact", "inference"]},
                        "statement": {"type": "string"},
                        "derivation": {"type": "string"},
                        "content_ids": {
                            "type": "array",
                            "items": {"type": "string"},
                        },
                        "evidence_links": {
                            "type": "array",
                            "items": {
                                "type": "object",
                                "properties": {
                                    "content_id": {"type": "string"},
                                    "support_type": {
                                        "type": "string",
                                        "enum": ["direct", "contextual", "contradictory", "background"],
                                    },
                                    "support_strength": {
                                        "type": "string",
                                        "enum": ["strong", "medium", "weak"],
                                    },
                                    "support_explanation": {"type": "string"},
                                },
                                "required": ["content_id", "support_type", "support_strength", "support_explanation"],
                            },
                        },
                        "counterevidence_status": {
                            "type": "string",
                            "enum": ["found", "not_found", "unknown"],
                        },
                        "counterevidence_explanation": {"type": "string"},
                    },
                    "required": ["kind", "statement", "content_ids", "evidence_links"],
                },
            ),
            "propose_action": (
                "Place a safe action proposal into the owner approval queue.",
                {
                    "type": "object",
                    "properties": {
                        "action": {"type": "string"},
                        "reason": {"type": "string"},
                        "payload": {"type": "object"},
                    },
                    "required": ["action", "reason"],
                },
            ),
        }
        return [
            ModelToolDefinition(name=name, description=schemas[name][0], input_schema=schemas[name][1])
            for name in cls.TOOL_NAMES
        ]

    @staticmethod
    def _string(arguments: dict[str, object], name: str, *, max_length: int = 2_000) -> str:
        value = arguments.get(name)
        if not isinstance(value, str):
            raise ResearchTaskConflict(f"tool argument {name} must be a string")
        value = value.strip()
        if not value or len(value) > max_length or not value.isprintable():
            raise ResearchTaskConflict(f"tool argument {name} is invalid")
        return value

    @staticmethod
    def _strings(arguments: dict[str, object], name: str, *, limit: int = 20) -> list[str]:
        value = arguments.get(name)
        if not isinstance(value, list) or not value or len(value) > limit:
            raise ResearchTaskConflict(f"tool argument {name} must be a bounded list")
        result: list[str] = []
        for item in value:
            if not isinstance(item, str) or not item.strip():
                raise ResearchTaskConflict(f"tool argument {name} contains an invalid id")
            result.append(item.strip())
        if len(set(result)) != len(result):
            raise ResearchTaskConflict(f"tool argument {name} contains duplicates")
        return result

    async def execute(
        self,
        *,
        task: dict[str, object],
        tool_name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        if tool_name not in self.TOOL_NAMES:
            raise ResearchTaskConflict(f"tool '{tool_name}' is not in the allow-list")
        if tool_name == "search_library":
            query = self._string(arguments, "query")
            task_context = task.get("context")
            if isinstance(task_context, dict) and task_context.get("quality_gate_required") is True:
                query_id = arguments.get("_research_query_id")
                if not isinstance(query_id, str) or not query_id:
                    raise ResearchTaskConflict(
                        "search query must pass the research quality gate"
                    )
                quality_query = self.research.get_query(query_id)
                if (
                    str(quality_query.get("research_task_id")) != str(task["id"])
                    or normalize_query(str(quality_query.get("query") or ""))
                    != normalize_query(query)
                    or quality_query.get("status") not in {"approved", "running", "completed"}
                ):
                    raise ResearchTaskConflict(
                        "search query is not an approved quality-gated candidate"
                    )
            platform = arguments.get("platform")
            if platform is not None and not isinstance(platform, str):
                raise ResearchTaskConflict("platform must be a string")
            result = self.library_tools.search_contents(
                query=query,
                platform=platform.strip() if isinstance(platform, str) else None,
                tag_id=None,
                is_favorite=None,
                offset=0,
                limit=20,
            )
            # Library search is intentionally conservative for the public API
            # and treats a query as one phrase.  Research rounds often receive
            # a natural-language objective, however, and a newly collected
            # result may contain only one of its meaningful terms.  When the
            # phrase has no hit, retry a small bounded set of extracted terms
            # and merge by content id.  This keeps the mandatory library-first
            # lookup while allowing entity extraction from real first-round
            # results.
            data = result.get("data") if isinstance(result, dict) else None
            if isinstance(data, list) and data:
                return result
            terms: list[str] = []
            for term in TOKEN_RE.findall(query):
                if term.casefold() in STOPWORDS:
                    continue
                terms.append(term)
                if all("\u4e00" <= char <= "\u9fff" for char in term):
                    # Add bounded two-character n-grams so a phrase such as
                    # "工作台产品" can still match a title containing only
                    # "产品" after the first crawl.
                    terms.extend(term[index : index + 2] for index in range(len(term) - 1))
            terms = list(dict.fromkeys(terms))[:6]
            merged: dict[str, dict[str, object]] = {}
            for term in terms:
                fallback = self.library_tools.search_contents(
                    query=term,
                    platform=platform.strip() if isinstance(platform, str) else None,
                    tag_id=None,
                    is_favorite=None,
                    offset=0,
                    limit=20,
                )
                fallback_data = fallback.get("data") if isinstance(fallback, dict) else None
                if not isinstance(fallback_data, list):
                    continue
                for item in fallback_data:
                    if isinstance(item, dict) and item.get("id"):
                        merged[str(item["id"])] = item
                if len(merged) >= 20:
                    break
            if not merged:
                return result
            return {
                "data": list(merged.values())[:20],
                "meta": {
                    "offset": 0,
                    "limit": 20,
                    "next_offset": 0,
                    "has_more": False,
                },
            }
        if tool_name == "get_content":
            content_id = self._string(arguments, "content_id", max_length=200)
            result = self.library_tools.get_content(content_id)
            if result is None:
                raise ResearchTaskConflict("content was not found")
            return result
        if tool_name == "get_provenance":
            content_id = self._string(arguments, "content_id", max_length=200)
            result = self.library_tools.get_content(content_id)
            if result is None:
                raise ResearchTaskConflict("content was not found")
            source = result.get("source")
            source_data = source if isinstance(source, dict) else {}
            return {
                "content_id": content_id,
                "platform": source_data.get("platform"),
                "source_url": source_data.get("url"),
                "author_name": result.get("author_name"),
                "published_at": result.get("published_at"),
                "crawl_tasks": result.get("provenance", []),
            }
        if tool_name == "get_creator_history":
            creator_id = self._string(arguments, "creator_id", max_length=200)
            result = self.library_tools.get_creator(creator_id)
            if result is None:
                raise ResearchTaskConflict("creator was not found")
            return result
        if tool_name == "submit_crawl":
            current = self.research.get_for_runtime(str(task["id"]))
            current_context = current.get("context") if current else None
            if not isinstance(current_context, dict) or not current_context.get(
                "last_search_query"
            ):
                raise ResearchTaskConflict(
                    "search_library must run before submit_crawl"
                )
            return self._submit_crawl(task, arguments)
        if tool_name == "dedupe_check":
            return self._dedupe(task, arguments)
        if tool_name == "save_finding":
            kind = self._string(arguments, "kind", max_length=32)
            if kind not in {"fact", "inference"}:
                raise ResearchTaskConflict("finding kind must be fact or inference")
            statement = self._string(arguments, "statement", max_length=10_000)
            content_ids = self._strings(arguments, "content_ids")
            self._validate_finding_scope(task, content_ids)
            derivation_value = arguments.get("derivation")
            derivation = (
                derivation_value.strip()
                if isinstance(derivation_value, str) and derivation_value.strip()
                else None
            )
            if kind == "inference" and derivation is None:
                raise ResearchTaskConflict(
                    "inference findings require a derivation"
                )
            raw_links = arguments.get("evidence_links")
            task_context = task.get("context")
            quality_metadata_required = (
                isinstance(task_context, dict)
                and task_context.get("quality_gate_required") is True
            )
            if quality_metadata_required and raw_links is None:
                raise ResearchTaskConflict(
                    "quality-gated findings require per-evidence support metadata"
                )
            evidence_links: list[dict[str, str]] | None = None
            if raw_links is not None:
                if not isinstance(raw_links, list) or not raw_links:
                    raise ResearchTaskConflict("evidence_links must be a non-empty list")
                evidence_links = []
                for raw_link in raw_links:
                    if not isinstance(raw_link, dict):
                        raise ResearchTaskConflict("evidence_links contains an invalid item")
                    link_content_id = raw_link.get("content_id")
                    support_type = raw_link.get("support_type")
                    support_strength = raw_link.get("support_strength")
                    support_explanation = raw_link.get("support_explanation")
                    if not all(
                        isinstance(value, str) and value.strip()
                        for value in (
                            link_content_id,
                            support_type,
                            support_strength,
                            support_explanation,
                        )
                    ):
                        raise ResearchTaskConflict("evidence_links metadata is incomplete")
                    evidence_links.append(
                        {
                            "content_id": link_content_id.strip(),
                            "support_type": support_type.strip(),
                            "support_strength": support_strength.strip(),
                            "support_explanation": support_explanation.strip(),
                        }
                    )
            counterevidence_status = arguments.get("counterevidence_status", "not_found")
            if not isinstance(counterevidence_status, str) or counterevidence_status not in {
                "found",
                "not_found",
                "unknown",
            }:
                raise ResearchTaskConflict("counterevidence_status is invalid")
            counterevidence_explanation = arguments.get(
                "counterevidence_explanation",
                "未找到反证。",
            )
            if not isinstance(counterevidence_explanation, str) or not counterevidence_explanation.strip():
                raise ResearchTaskConflict("counterevidence_explanation is required")
            return self.research.save_finding(
                task_id=str(task["id"]),
                round_number=int(task["current_round"]),
                kind=kind,
                statement=statement,
                derivation=derivation,
                content_ids=content_ids,
                evidence_links=evidence_links,
                counterevidence_status=counterevidence_status,
                counterevidence_explanation=counterevidence_explanation.strip(),
            )
        if tool_name == "propose_action":
            action = self._string(arguments, "action", max_length=500)
            reason = self._string(arguments, "reason", max_length=2_000)
            payload = arguments.get("payload")
            if not isinstance(payload, dict):
                payload = {}
            return self.research.add_action(
                task_id=str(task["id"]),
                action=action,
                reason=reason,
                payload={str(key): value for key, value in payload.items()},
            )
        raise ResearchTaskConflict(f"tool '{tool_name}' is not implemented")

    def _validate_finding_scope(
        self,
        task: dict[str, object],
        content_ids: list[str],
    ) -> None:
        """Reject modern findings whose entire evidence set is out of scope.

        The model may still use a contextual card to explain an evidence gap,
        but it must not turn an unrelated library result into a Finding.  The
        check is deliberately conservative and only applies when an audited
        8D Intent Contract exists; legacy tasks retain their historical tool
        behaviour.
        """
        contract_data = task.get("intent_contract")
        if not isinstance(contract_data, dict):
            try:
                contract_data = self.research.get_intent(str(task["id"]))
            except ResearchTaskNotFound:
                return
        if not isinstance(contract_data, dict):
            return
        if contract_data.get("intent_source") == "legacy_migrated":
            return
        try:
            contract = ResearchIntentContract.model_validate(contract_data)
        except (TypeError, ValueError):
            return
        scores: list[float] = []
        for content_id in content_ids:
            content = self.library_tools.get_content(content_id)
            if not isinstance(content, dict):
                raise ResearchTaskConflict(
                    "finding evidence could not be validated against the Intent Contract"
                )
            scores.append(intent_relevance_score(content, intent=contract))
        if scores and max(scores) < 0.3:
            raise ResearchTaskConflict(
                "finding evidence is outside the Intent Contract scope"
            )

    def _submit_crawl(
        self,
        task: dict[str, object],
        arguments: dict[str, object],
    ) -> dict[str, object]:
        platform = self._string(arguments, "platform", max_length=32).casefold()
        keywords = self._string(arguments, "keywords", max_length=200)
        platforms = task.get("platforms")
        if not isinstance(platforms, list) or platform not in platforms:
            raise ResearchTaskConflict("crawl platform is outside this research task scope")
        try:
            adapter = platform_registry.require_mode_enabled(
                platform,
                "search",
                self.settings.enabled_platforms,
            )
        except (UnsupportedPlatformError, PlatformDisabledError, ModeDisabledError) as error:
            raise ResearchTaskConflict(str(error)) from error
        if int(task["consumed_crawl_count"]) >= int(task["budget_crawl_limit"]):
            raise ResearchTaskConflict("crawl budget is exhausted")
        query_id = arguments.get("_research_query_id")
        supplied_task_id = arguments.get("research_task_id")
        if supplied_task_id is not None and supplied_task_id != str(task["id"]):
            raise ResearchTaskConflict("research_task_id does not match the active task")
        expected_role = arguments.get("expected_evidence_role")
        if expected_role is not None and expected_role not in {
            "direct",
            "contextual",
            "contradictory",
            "background",
        }:
            raise ResearchTaskConflict("expected_evidence_role is invalid")
        identifier = self.crawler.new_id()
        requested = arguments.get(
            "requested_count",
            RESEARCH_DEFAULT_REQUESTED_COUNT,
        )
        requested_count = (
            int(requested)
            if isinstance(requested, int)
            else RESEARCH_DEFAULT_REQUESTED_COUNT
        )
        if not 10 <= requested_count <= 15:
            raise ResearchTaskConflict(
                "research requested_count must be between 10 and 15"
            )
        task_id = str(task["id"])
        current = self.research.get_for_runtime(task_id)
        if current is None:
            raise ResearchTaskConflict("research task no longer exists")
        if str(current["status"]) != "Researching":
            raise ResearchTaskConflict(
                f"cannot submit crawl while task is {current['status']}"
            )
        task = current
        if not isinstance(query_id, str) or not query_id:
            current_context = task.get("context")
            current_context = current_context if isinstance(current_context, dict) else {}
            if current_context.get("quality_gate_required") is True:
                raise ResearchTaskConflict(
                    "crawl query must pass the research quality gate"
                )
            source_content_id = None
            source_ids = current_context.get("last_search_content_ids")
            if isinstance(source_ids, list) and source_ids and isinstance(source_ids[0], str):
                source_content_id = source_ids[0]
            parent_query_id = current_context.get("last_query_id")
            parent_query_id = parent_query_id if isinstance(parent_query_id, str) else None
            source_type = "user_goal" if parent_query_id is None else "agent_search"
            quality = evaluate_query(
                keywords,
                generation_reason="从已有 search_library 结果触发补充采集",
                source_type=source_type,
                historical_queries=self.research.list_normalized_queries(
                    exclude_task_id=task_id,
                ),
                parent_query_id=parent_query_id,
                source_content_id=source_content_id,
            )
            query = self.research.create_query(
                task_id=task_id,
                query=keywords,
                normalized_query=quality.normalized_query,
                query_type=quality.query_type,
                platform=platform,
                source_type=source_type,
                source_content_id=source_content_id,
                source_finding_id=None,
                parent_query_id=parent_query_id,
                generation_reason=(
                    self._string(arguments, "reason", max_length=500)
                    if isinstance(arguments.get("reason"), str)
                    else "从已有 search_library 结果触发补充采集"
                ),
                specificity_score=quality.specificity_score,
                novelty_score=quality.novelty_score,
                noise_risk_score=quality.noise_risk_score,
                relevance_score=1.0 if quality.accepted else None,
                expected_value_score=(
                    expected_value_score(
                        1.0,
                        quality.specificity_score,
                        quality.novelty_score,
                    )
                    if quality.accepted
                    else None
                ),
                status="candidate" if quality.accepted else "rejected",
                rejection_reason=quality.rejection_reason,
                expected_evidence_role=(
                    str(expected_role) if isinstance(expected_role, str) else "direct"
                ),
            )
            if not quality.accepted:
                raise ResearchTaskConflict(quality.rejection_reason or "query rejected")
            query_id = str(query["id"])
        self.crawler.create(
            task_id=identifier,
            platform=platform,
            crawler_type="search",
            keywords=keywords,
            login_type="qrcode",
            requested_count=requested_count,
            research_task_id=task_id,
            output_dir=str(self.settings.output_root / "tasks" / identifier),
            log_path=str(self.settings.log_root / "crawler" / f"{identifier}.log"),
            qrcode_path=str(self.settings.qrcode_root / f"{identifier}.png"),
        )
        try:
            # Link the quality-gated query before making the crawler visible
            # to the single Worker; otherwise a fast Worker could complete a
            # task before its query provenance is attached.
            self.research.attach_query_crawler(query_id, identifier)
            self.research.add_crawl_submission(task_id, identifier)
        except Exception:
            # Do not leave a pending crawler orphaned if the research row
            # changed between validation and submission.
            self.crawler.request_cancel(identifier)
            self.research.complete_query(
                query_id,
                result_count=0,
                new_content_count=0,
                existing_content_count=0,
                updated_content_count=0,
                duplicate_evidence_count=0,
                failed=True,
            )
            raise
        return {
            "status": "waiting_crawl",
            "crawler_task_id": identifier,
            "platform": adapter.display_name,
            "keywords": keywords,
        }

    def _dedupe(
        self,
        task: dict[str, object],
        arguments: dict[str, object],
    ) -> dict[str, object]:
        content_ids = self._strings(arguments, "content_ids")
        records = []
        for content_id in content_ids:
            content = self.library_tools.get_content(content_id)
            if content is None:
                raise ResearchTaskConflict("dedupe content was not found")
            records.append(content)
        title = arguments.get("title")
        summary = arguments.get("summary")
        normalized_title = (
            title.strip() if isinstance(title, str) and title.strip() else str(records[0].get("title") or "Untitled event")
        )
        normalized_summary = (
            summary.strip() if isinstance(summary, str) and summary.strip() else str(records[0].get("description") or normalized_title)
        )
        fingerprint_source = "|".join(
            sorted(
                " ".join(
                    TOKEN_RE.findall(
                        f"{record.get('title') or ''} {record.get('description') or ''}"
                    )
                ).casefold()
                for record in records
            )
        )
        fingerprint = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()
        return self.research.dedupe_event(
            task_id=str(task["id"]),
            round_number=int(task["current_round"]),
            fingerprint=fingerprint,
            title=normalized_title[:500],
            summary=normalized_summary[:4_000],
            content_ids=content_ids,
        )


def extract_entities(items: list[dict[str, object]], *, limit: int = 8) -> list[str]:
    """Extract bounded next-round search terms from actual library results."""

    counts: dict[str, int] = {}
    for item in items:
        source = f"{item.get('title') or ''} {item.get('description') or ''}"
        for token in TOKEN_RE.findall(source):
            normalized = token.casefold()
            if normalized in STOPWORDS or len(normalized) < 2:
                continue
            counts[normalized] = counts.get(normalized, 0) + 1
    return [token for token, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]]


def _content_text(content: dict[str, object]) -> str:
    return " ".join(
        str(content.get(key) or "")
        for key in ("title", "description", "content", "summary")
    ).strip()


def _intent_context_terms(intent: ResearchIntentContract) -> set[str]:
    subject = intent.subject if isinstance(intent.subject, dict) else {}
    subject_text = " ".join(
        str(subject.get(key) or "") for key in ("category", "description")
    )
    terms = {
        token.casefold()
        for token in TOKEN_RE.findall(subject_text)
        if token.casefold() not in ENTITY_BLOCKLIST and token.casefold() not in STOPWORDS
    }
    terms.update(term.casefold() for term in PRODUCT_CONTEXT_TERMS)
    return terms


def _looks_like_product_name(value: str, *, source: str, context_terms: set[str]) -> bool:
    normalized = value.strip().casefold()
    if not normalized or normalized in ENTITY_BLOCKLIST or len(normalized) < 2:
        return False
    if normalized in PRODUCT_HINTS:
        return True
    if normalized.isascii() and normalized.isupper():
        return False
    if not any(term in source for term in context_terms):
        return False
    # A capitalized Latin token in a product/usage context is a bounded
    # discovery candidate.  Generic words are filtered above and by the
    # explicit blocklist, so technical prose cannot turn every token into a
    # product candidate.
    return bool(re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]{2,}", value))


def extract_intent_entities(
    items: Iterable[dict[str, object]],
    *,
    intent: ResearchIntentContract,
    limit: int = 8,
) -> list[str]:
    """Extract product-like candidates relevant to one Intent Contract.

    ``extract_entities`` is retained for the historical 8C planner path.  The
    8D path needs a stricter extractor: generic tokens such as ``https`` or
    ``coding`` are not discovery entities, and candidates are only accepted
    when they appear in a product/usage context.
    """

    counts: dict[str, int] = {}
    context_terms = _intent_context_terms(intent)
    for item in items:
        source = _content_text(item)
        folded = source.casefold()
        candidates: list[str] = []
        for hint in PRODUCT_HINTS:
            if hint in folded:
                candidates.append(hint)
        candidates.extend(PRODUCT_CONTEXT_RE.findall(source))
        candidates.extend(re.findall(r"\b[A-Z][A-Za-z0-9_-]{2,}\b", source))
        for token in candidates:
            normalized = token.strip().casefold()
            if _looks_like_product_name(
                token,
                source=folded,
                context_terms=context_terms,
            ) or normalized in PRODUCT_HINTS:
                counts[normalized] = counts.get(normalized, 0) + 1
    return [
        token
        for token, _ in sorted(counts.items(), key=lambda pair: (-pair[1], pair[0]))[:limit]
    ]


def intent_relevance_score(
    content: dict[str, object],
    *,
    intent: ResearchIntentContract,
    extracted_entities: Iterable[str] = (),
) -> float:
    """Return a conservative [0, 1] scope score for one captured item."""

    source = _content_text(content).casefold()
    if not source:
        return 0.0
    entities = extract_intent_entities([content], intent=intent)
    explicit_entities = [
        value.strip()
        for value in extracted_entities
        if isinstance(value, str) and value.strip()
    ]
    entities = list(dict.fromkeys(entities + explicit_entities))
    context_hits = sum(term in source for term in PRODUCT_CONTEXT_TERMS)
    subject = intent.subject if isinstance(intent.subject, dict) else {}
    subject_terms = {
        token.casefold()
        for token in TOKEN_RE.findall(
            " ".join(str(subject.get(key) or "") for key in ("category", "description"))
        )
        if token.casefold() not in ENTITY_BLOCKLIST and token.casefold() not in STOPWORDS
    }
    subject_hits = sum(term in source for term in subject_terms)
    score = 0.0
    if entities:
        score += 0.55
    score += min(0.3, context_hits * 0.06)
    score += min(0.2, subject_hits * 0.1)
    if any(
        term in source
        for term in ("痛点", "需求", "缺口", "替代", "不好用", "限制", "问题")
    ) and {
        "pain_point_research",
        "product_opportunity",
        "content_opportunity",
        "competitor_scan",
    }.intersection({intent.primary_intent, *intent.secondary_intents}):
        score += 0.25
    if any(term in source for term in ("购买", "优惠", "扫码", "推广", "课程")):
        score -= 0.12
    return round(max(0.0, min(1.0, score)), 4)
