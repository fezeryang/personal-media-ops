from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime
from time import perf_counter

from app.models.ai import ModelMessage, ModelRequest, ModelRouteRole
from app.models.research_intent import ResearchIntentContract
from app.repositories.ai import AIRepository
from app.repositories.research import (
    ResearchTaskConflict,
    ResearchTaskNotFound,
    ResearchTaskRepository,
)
from app.services.ai.context_compactor import compact_research_context
from app.services.ai.information_value import (
    classify_information_utility,
    event_type_for_content,
)
from app.services.ai.intent_interpreter import (
    build_default_intent,
    execution_query_directions,
    interpret_model_text,
)
from app.services.ai.intent_interpreter import model_request as intent_model_request
from app.services.ai.intent_interpreter import (
    repair_model_request as intent_repair_model_request,
)
from app.services.ai.model_gateway import ModelGateway
from app.services.ai.providers import ProviderError
from app.services.ai.research_quality import (
    evaluate_query,
    expected_value_score,
    marginal_stop_decision,
    parse_relevance_batch,
    parse_structured_json,
    platform_query_variants,
    query_priority_score,
)
from app.services.ai.research_rendering import render_research_markdown
from app.services.ai.research_tools import (
    RESEARCH_DEFAULT_REQUESTED_COUNT,
    ResearchToolService,
    extract_entities,
)

MAX_TOOL_ROUNDS = 8
MAX_ARTIFACT_ROUNDS = 3
MAX_ACTION_ARTIFACT_ROUNDS = 2
MAX_TOOL_RESULT_CHARS = 24_000
RECOVERY_INTERVAL_SECONDS = 2.0


def _json(value: object, default: object) -> object:
    if not isinstance(value, str):
        return default
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError:
        return default
    return parsed


def _safe_arguments(arguments: dict[str, object]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in arguments.items():
        if isinstance(value, str):
            result[key] = value[:500]
        elif isinstance(value, list):
            result[key] = [item[:200] if isinstance(item, str) else item for item in value[:20]]
        elif isinstance(value, dict):
            result[key] = {str(k): str(v)[:200] for k, v in list(value.items())[:20]}
        else:
            result[key] = value
    return result


def _elapsed_from(started_at: object) -> int:
    if not isinstance(started_at, str):
        return 0
    try:
        parsed = datetime.fromisoformat(started_at)
    except ValueError:
        return 0
    return max(0, int((datetime.now(UTC) - parsed.astimezone(UTC)).total_seconds()))


class ResearchRuntime:
    """One bounded, restartable Research Agent runtime in the API process."""

    def __init__(
        self,
        *,
        research: ResearchTaskRepository,
        ai_repository: AIRepository,
        gateway: ModelGateway,
        tools: ResearchToolService,
    ) -> None:
        self.research = research
        self.ai_repository = ai_repository
        self.gateway = gateway
        self.tools = tools
        self._wake = asyncio.Event()
        self._stop = asyncio.Event()
        self._task: asyncio.Task[None] | None = None

    async def start(self) -> None:
        if self._task is not None:
            return
        self._stop.clear()
        self._task = asyncio.create_task(self._run_loop(), name="research-runtime")
        self.wake()

    async def stop(self) -> None:
        self._stop.set()
        self._wake.set()
        if self._task is not None:
            await self._task
            self._task = None

    def wake(self) -> None:
        self._wake.set()

    async def run_once(self) -> bool:
        self._recover_waiting_crawls()
        task = self.research.claim_next()
        if task is None:
            return False
        try:
            await self._tick(task)
        except asyncio.CancelledError:
            raise
        except sqlite3.OperationalError as error:
            if "locked" in str(error).casefold() or "busy" in str(error).casefold():
                # SQLite already waits briefly at the connection boundary;
                # keep a transient lock from turning a recoverable task into
                # a terminal runtime failure.
                await asyncio.sleep(0.2)
                self.wake()
                return True
            self._fail_task(str(task["id"]), self._safe_failure(error))
        except Exception as error:  # noqa: BLE001 - persist runtime boundary failure
            self._fail_task(str(task["id"]), self._safe_failure(error))
        return True

    async def _run_loop(self) -> None:
        while not self._stop.is_set():
            did_work = await self.run_once()
            if did_work:
                continue
            self._wake.clear()
            try:
                await asyncio.wait_for(
                    self._wake.wait(),
                    timeout=RECOVERY_INTERVAL_SECONDS,
                )
            except TimeoutError:
                continue

    @staticmethod
    def _safe_failure(error: Exception) -> str:
        if isinstance(error, ProviderError):
            return error.safe_summary
        if isinstance(error, ResearchTaskConflict):
            return str(error)
        return "Research runtime failed while executing a bounded step"

    def _fail_task(self, task_id: str, reason: str) -> None:
        self.research.set_failure(task_id, reason)

    def _step_is_allowed(self, task_id: str) -> bool:
        """Re-read durable controls before every new model/tool step."""
        current = self.research.get_for_runtime(task_id)
        if current is None:
            return False
        return not (str(current.get("status")) == "Cancelled" or bool(current.get("paused")))

    def _recover_waiting_crawls(self) -> None:
        self.research.reconcile_orphan_crawls()
        for item in self.research.waiting_crawls():
            status = str(item["crawler_status"])
            crawler_id = str(item["crawler_id"])
            if status == "succeeded":
                self.research.record_crawl_completion(
                    crawler_id,
                    succeeded=True,
                    new_content_count=int(item.get("research_new_content_count") or 0),
                    existing_content_count=int(
                        item.get("research_existing_content_count") or 0
                    ),
                    updated_content_count=int(
                        item.get("research_updated_content_count") or 0
                    ),
                    result_count=int(item.get("actual_count") or 0),
                )
            elif status in {"failed", "cancelled"}:
                self.research.record_crawl_completion(
                    crawler_id,
                    succeeded=False,
                    error=str(item.get("error_message") or "Crawler task failed"),
                )

    async def _tick(self, task: dict[str, object]) -> None:
        task_id = str(task["id"])
        if bool(task["paused"]):
            return
        self.research.record_duration(task_id)
        task = self.research.get_for_runtime(task_id, detail=True) or task
        task = self._clear_stale_completed_crawl_marker(task)
        budget_reason = self._budget_reason(task)
        if budget_reason is not None and str(task["status"]) not in {
            "BudgetExceeded",
            "Summarizing",
        }:
            self.research.transition(
                task_id,
                status="BudgetExceeded",
                reason=budget_reason,
                step="budget_gate",
                finished=False,
            )
            return

        status = str(task["status"])
        if status == "Draft":
            self.research.transition(
                task_id,
                status="Planning",
                reason="runtime_claimed_draft",
                step="planning",
            )
            return
        if status == "Planning":
            checkpoint = self.research.load_checkpoint(task_id)
            if (
                isinstance(checkpoint, dict)
                and checkpoint.get("checkpoint_key") == "planning_completed"
                and isinstance(task.get("plan"), dict)
                and task.get("plan", {}).get("derived_keywords")
            ):
                self.research.transition(
                    task_id,
                    status="Researching",
                    reason="planning_checkpoint_resumed",
                    step="research_round",
                    round_number=max(1, int(task.get("current_round", 1))),
                )
                return
            await self._plan(task)
            return
        if status in {"Researching", "BudgetExceeded"}:
            if status == "BudgetExceeded":
                self.research.transition(
                    task_id,
                    status="Summarizing",
                    reason="budget_gate_forced_convergence",
                    step="summarizing",
                )
                return
            await self._research_round(task)
            return
        if status == "Summarizing":
            await self._summarize(task)

    def _clear_stale_completed_crawl_marker(
        self,
        task: dict[str, object],
    ) -> dict[str, object]:
        """Repair a pre-fix task that finished its final crawl before the
        completion marker was cleared.

        The marker is only stale when no crawler is currently attached and the
        crawl budget is already exhausted.  Clearing it is idempotent and
        allows an owner-requested rerun to inspect the durable evidence rather
        than immediately re-entering the budget gate.
        """
        if (
            task.get("waiting_crawl_task_id") is not None
            or not task.get("context", {}).get("crawl_requested", False)
            if isinstance(task.get("context"), dict)
            else True
        ):
            return task
        if int(task.get("consumed_crawl_count", 0)) < int(task.get("budget_crawl_limit", 0)):
            return task
        context = dict(task["context"])
        context["crawl_requested"] = False
        self.research.update_context(
            str(task["id"]),
            context,
            step=str(task.get("current_step") or "research_round"),
            round_number=int(task.get("current_round", 0)),
        )
        return self.research.get_for_runtime(str(task["id"])) or task

    def _budget_reason(self, task: dict[str, object]) -> str | None:
        crawl_limit = int(task["budget_crawl_limit"])
        if int(task["consumed_crawl_count"]) >= crawl_limit:
            # A task is allowed to summarize after using its final crawl. The
            # gate only fires when a future crawl is requested; the current
            # round can still save and summarize existing evidence.
            context = task.get("context")
            if crawl_limit == 0 or (
                isinstance(context, dict) and context.get("crawl_requested")
            ):
                return "crawl task budget reached"
        if int(task["consumed_content_count"]) >= int(task["budget_content_limit"]):
            return "new content budget reached"
        if _elapsed_from(task.get("started_at")) >= int(task["budget_duration_seconds"]):
            return "research duration budget reached"
        tokens = int(task["input_tokens"]) + int(task["output_tokens"])
        if tokens >= int(task.get("budget_max_total_tokens", task["budget_token_limit"])):
            return "token budget reached"
        max_input = task.get("budget_max_input_tokens")
        if max_input is not None and int(task["input_tokens"]) >= int(max_input):
            return "input token budget reached"
        max_output = task.get("budget_max_output_tokens")
        if max_output is not None and int(task["output_tokens"]) >= int(max_output):
            return "output token budget reached"
        max_calls = task.get("budget_max_model_calls")
        if max_calls is not None and int(task.get("consumed_model_call_count", 0)) >= int(max_calls):
            return "model call budget reached"
        if bool(task["budget_cost_enabled"]) and task.get("budget_cost_limit") is not None:
            consumed = float(task.get("estimated_cost") or 0)
            max_payg = task.get("budget_max_payg_amount") or task.get("budget_cost_limit")
            if max_payg is not None and consumed >= float(max_payg):
                return "configured cost budget reached"
        return None

    def _route_snapshot(self, task: dict[str, object]) -> dict[str, object]:
        existing = task.get("route_snapshot")
        if isinstance(existing, dict) and existing.get("primary"):
            return existing
        routes = {
            str(item["role"]): item
            for item in self.ai_repository.list_routes()
            if item.get("model_record_id") is not None
        }
        primary = routes.get("tool_calling")
        route_policy = str(task.get("route_policy") or "balanced")
        if route_policy == "prefer_subscription" and primary is not None:
            subscription_candidates = [
                item
                for item in routes.values()
                if item.get("billing_mode") == "subscription_fixed"
                and item.get("model_record_id") is not None
            ]
            for candidate in subscription_candidates:
                candidate_model = self.ai_repository.get_model(str(candidate["model_record_id"]))
                if candidate_model is not None and candidate_model.get("supports_tools") is True:
                    primary = candidate
                    break
        elif route_policy == "prefer_payg" and primary is not None:
            payg_candidates = [
                item
                for item in routes.values()
                if item.get("billing_mode") == "pay_as_you_go"
                and item.get("model_record_id") is not None
            ]
            for candidate in payg_candidates:
                candidate_model = self.ai_repository.get_model(str(candidate["model_record_id"]))
                if candidate_model is not None and candidate_model.get("supports_tools") is True:
                    primary = candidate
                    break
        if primary is None or primary.get("model_enabled") is not True or primary.get("provider_enabled") is not True:
            raise ResearchTaskConflict("tool_calling route is not configured with an enabled model")
        model = self.ai_repository.get_model(str(primary["model_record_id"]))
        if model is None or model.get("supports_tools") is not True:
            raise ResearchTaskConflict("tool_calling model has not passed tool capability tests")
        snapshot: dict[str, object] = {
            "primary": {
                "role": "tool_calling",
                "model_record_id": str(primary["model_record_id"]),
                "provider": primary.get("provider_name"),
                "provider_id": primary.get("provider_id"),
                "model": primary.get("model_id"),
                "streaming": model.get("supports_streaming") is True,
                "supports_tools": model.get("supports_tools") is True,
                "vendor": primary.get("vendor"),
                "billing_mode": primary.get("billing_mode"),
            },
            "fast": self._route_item(routes.get("fast")),
            "deep": self._route_item(routes.get("deep")),
            "final_report": self._route_item(routes.get("final_report"))
            or {
                "role": "tool_calling",
                "model_record_id": str(primary["model_record_id"]),
                "provider": primary.get("provider_name"),
                "model": primary.get("model_id"),
            },
            "fallback": self._route_item(routes.get("fallback")),
        }
        return snapshot

    @staticmethod
    def _route_item(item: dict[str, object] | None) -> dict[str, object] | None:
        if item is None or item.get("model_record_id") is None:
            return None
        return {
            "role": item.get("role"),
            "model_record_id": item.get("model_record_id"),
            "provider": item.get("provider_name"),
            "model": item.get("model_id"),
            "provider_id": item.get("provider_id"),
            "vendor": item.get("vendor"),
            "billing_mode": item.get("billing_mode"),
        }

    async def _plan(self, task: dict[str, object]) -> None:
        task_id = str(task["id"])
        snapshot = self._route_snapshot(task)
        primary = snapshot["primary"]
        if not isinstance(primary, dict):
            raise ResearchTaskConflict("research route snapshot is invalid")
        cost_enabled = False
        payg_limit = task.get("budget_max_payg_amount") or task.get("budget_cost_limit")
        budget_currency = task.get("budget_currency") or task.get("budget_cost_currency")
        if payg_limit is not None and budget_currency:
            for route in snapshot.values():
                if not isinstance(route, dict) or route.get("billing_mode") != "pay_as_you_go":
                    continue
                route_model_id = route.get("model_record_id")
                if not isinstance(route_model_id, str):
                    continue
                candidate = self.ai_repository.get_model(route_model_id)
                if candidate is None:
                    continue
                provider_id = route.get("provider_id")
                if isinstance(provider_id, str):
                    candidate = self.ai_repository.effective_pricing_model(candidate, provider_id)
                if (
                    candidate.get("input_price_per_million") is not None
                    and candidate.get("output_price_per_million") is not None
                    and candidate.get("price_currency")
                    and candidate.get("price_effective_at")
                ):
                    cost_enabled = True
                    break
        self.research.set_cost_enabled(task_id, cost_enabled)
        snapshot["cost_enabled"] = cost_enabled
        existing_contract = task.get("intent_contract")
        modern_intent = (
            isinstance(existing_contract, dict)
            and bool(existing_contract)
            and existing_contract.get("intent_source") != "legacy_migrated"
        )
        intent: ResearchIntentContract | None = None
        intent_directions: list[dict[str, object]] = []
        if modern_intent:
            intent = await self._interpret_intent(
                task,
                primary_model_id=str(primary["model_record_id"]),
                platforms=[
                    str(platform)
                    for platform in task.get("platforms", [])
                    if isinstance(platform, str)
                ],
            )
            intent_directions = execution_query_directions(intent)
            request = ModelRequest(
                system=(
                    "You are the Research Planner, separate from Intent Interpreter. "
                    "Use the supplied Intent Contract to produce a bounded research plan, "
                    "not a new interpretation. Return JSON with search_terms (at least three "
                    "concrete platform execution query directions), query_roles, stages, and "
                    "coverage_gaps. Do not copy the user goal as a platform query and do not claim facts."
                ),
                messages=[
                    ModelMessage(
                        role="user",
                        content=json.dumps(
                            {
                                "intent_contract": intent.model_dump(mode="json"),
                                "deterministic_seed_directions": intent_directions,
                            },
                            ensure_ascii=False,
                        )[:16_000],
                    )
                ],
                temperature=0.1,
                max_tokens=600,
                tools=None,
                tool_choice="none",
                metadata={"runtime_step": "planning"},
                timeout=45,
            )
        else:
            # Tasks created before 8D-0 have no executable intent contract.
            # Keep their planner call and trajectory stable; migration provides
            # a read-only legacy intent for display, but must not re-run it as a
            # modern interpretation or silently change its research behavior.
            request = ModelRequest(
                system=(
                    "You are the planning stage of a bounded research task. "
                    "Return JSON with a search_terms array containing three or more "
                    "concrete search terms not copied verbatim from the objective. "
                    "Do not claim facts."
                ),
                messages=[ModelMessage(role="user", content=str(task["objective"]))],
                max_tokens=400,
                tools=None,
                tool_choice="none",
                metadata={"runtime_step": "planning"},
                timeout=45,
            )
        if not self._step_is_allowed(task_id):
            return
        response = await self._generate(
            task_id=task_id,
            request=request,
            route_role="tool_calling",
            model_record_id=str(primary["model_record_id"]),
        )
        if not self._step_is_allowed(task_id):
            return
        text = response.response.content or ""
        derived_keywords = self._plan_keywords(text, str(task["objective"]))
        if len(derived_keywords) < 3:
            if modern_intent:
                derived_keywords = [item["query"] for item in intent_directions[:8]]
            else:
                raise ResearchTaskConflict("planner returned fewer than three novel search terms")
        if len(derived_keywords) < 3:
            raise ResearchTaskConflict("planner could not produce bounded execution query directions")
        planner_payload = parse_structured_json(text).value
        query_roles: list[str] = []
        if isinstance(planner_payload, dict) and isinstance(planner_payload.get("query_roles"), list):
            query_roles = [str(item) for item in planner_payload["query_roles"] if isinstance(item, str)]
        if not query_roles:
            query_roles = [item["query_role"] for item in intent_directions]
        plan = {
            "objective": str(task["objective"]),
            "model_plan": text[:8_000],
            "steps": (
                [
                    "scan the category and discover concrete entities",
                    "select representative content and validate across planned platforms",
                    "probe counterevidence, limitations, and unresolved unknowns",
                    "classify information utility and save evidence-bound findings",
                    "review intent alignment before summarizing",
                ]
                if modern_intent
                else [
                    "search existing library",
                    "collect missing evidence when necessary",
                    "deduplicate and save evidence-bound findings",
                    "summarize facts, inferences, and proposed actions",
                ]
            ),
            "initial_query": (
                derived_keywords[0][:500]
                if modern_intent
                else str(task["objective"])[:500]
            ),
            "derived_keywords": derived_keywords,
        }
        if modern_intent and intent is not None:
            plan.update(
                {
                    "intent_id": (self.research.get_intent(task_id) or {}).get("id"),
                    "intent_contract": intent.model_dump(mode="json"),
                    "execution_query_directions": intent_directions,
                    "query_roles": query_roles,
                    "unknowns_to_discover": intent.unknowns_to_discover,
                }
            )
        self.research.save_plan(task_id, plan=plan, route_snapshot=snapshot, round_number=1)
        context = task.get("context")
        if not isinstance(context, dict):
            context = {}
        context.update(
            {
                "messages": [],
                "entities": [],
                "crawl_requested": False,
                "quality_gate_required": getattr(
                    self.tools,
                    "supports_quality_queries",
                    False,
                )
                is True,
                "coverage": task.get("coverage", {}),
                "low_marginal_rounds": 0,
                "stop_reason": None,
            }
        )
        if modern_intent and intent is not None:
            context["intent_contract"] = intent.model_dump(mode="json")
        self.research.update_context(task_id, context, step="research_round", round_number=1)
        self.research.record_step_usage(task_id, step="initial_query_generation")
        self.research.save_checkpoint(
            task_id,
            checkpoint_key="planning_completed",
            last_completed_step="planning",
            payload={"derived_keywords": derived_keywords, "coverage": task.get("coverage", {})},
        )
        self.research.transition(
            task_id,
            status="Researching",
            reason="planning_completed",
            step="research_round",
            round_number=1,
        )

    async def _interpret_intent(
        self,
        task: dict[str, object],
        *,
        primary_model_id: str,
        platforms: list[str],
    ):
        """Interpret the user goal once, with a bounded provider fallback."""
        task_id = str(task["id"])
        fallback = build_default_intent(str(task["objective"]), platforms)
        try:
            response = await self._generate(
                task_id=task_id,
                request=intent_model_request(str(task["objective"]), platforms),
                route_role="tool_calling",
                model_record_id=primary_model_id,
            )
            raw = response.response.content or ""
            intent = interpret_model_text(str(task["objective"]), raw, platforms)
            if intent.intent_source == "fallback_default":
                repaired = await self._generate(
                    task_id=task_id,
                    request=intent_repair_model_request(
                        str(task["objective"]),
                        raw,
                        platforms,
                    ),
                    route_role="tool_calling",
                    model_record_id=primary_model_id,
                )
                repaired_intent = interpret_model_text(
                    str(task["objective"]),
                    repaired.response.content or "",
                    platforms,
                )
                if repaired_intent.intent_source == "model":
                    intent = repaired_intent
                else:
                    self.research.append_trace(
                        task_id,
                        event="intent_fallback",
                        status="Planning",
                        reason="structured intent response and one repair attempt were invalid",
                        round_number=0,
                        step="intent_interpretation",
                    )
            if intent.intent_source == "fallback_default":
                self.research.append_trace(
                    task_id,
                    event="intent_fallback",
                    status="Planning",
                    reason="using deterministic default intent",
                    round_number=0,
                    step="intent_interpretation",
                )
                intent = fallback
        except Exception as error:  # noqa: BLE001 - intent is explicitly fail-open
            self.research.append_trace(
                task_id,
                event="intent_fallback",
                status="Planning",
                reason=self._safe_failure(error),
                round_number=0,
                step="intent_interpretation",
            )
            intent = fallback
        saved = self.research.save_intent(
            task_id,
            intent.model_dump(mode="json"),
            change_reason=(
                "model_interpretation"
                if intent.intent_source == "model"
                else "model_interpretation_fallback"
            ),
        )
        # The repository returns the same contract with its durable version.
        try:
            return type(intent).model_validate(saved)
        except (TypeError, ValueError):
            return intent

    @staticmethod
    def _plan_keywords(text: str, objective: str) -> list[str]:
        """Keep only bounded, non-verbatim search terms from the plan text."""
        objective_terms = {
            token.casefold()
            for token in objective.replace("，", " ").replace("。", " ").split()
            if len(token) >= 2
        }
        candidates: list[str] = []
        raw_candidates: list[str] = []
        parsed = parse_structured_json(text).value
        parsed_candidates = False
        if isinstance(parsed, dict):
            for key in ("search_terms", "keywords", "queries", "derived_keywords"):
                value = parsed.get(key)
                if isinstance(value, list):
                    raw_candidates.extend(
                        item for item in value if isinstance(item, str)
                    )
                    parsed_candidates = True
        elif isinstance(parsed, list):
            raw_candidates.extend(item for item in parsed if isinstance(item, str))
            parsed_candidates = True
        if not parsed_candidates:
            # A decoded planner object without a supported query-list field is
            # still malformed for this stage. Do not turn JSON field names
            # into executable queries (for example `time_window_days`).
            if isinstance(parsed, dict):
                return []
            stripped = text.strip()
            if stripped.startswith(("{", "[", "```")):
                return []
            raw_candidates.extend(text.replace("\n", ",").split(","))
        for raw in raw_candidates:
            item = raw.strip(" -*•`\t:：0123456789.[]{}\"'")
            if len(item) < 2 or len(item) > 80 or not item.isprintable():
                continue
            normalized = item.casefold()
            if normalized in objective_terms or normalized == objective.casefold():
                continue
            if item not in candidates:
                candidates.append(item)
        return candidates[:8]

    @staticmethod
    def _quality_expansion_term(
        entities: object,
        objective: str | None = None,
    ) -> str | None:
        if not isinstance(entities, list):
            entities = []
        generic = {
            "ai",
            "agent",
            "api",
            "app",
            "auto",
            "code",
            "coding",
            "产品",
            "工具",
            "软件",
            "工作台",
            "vibe",
            "vibecoding",
            "话题",
            "使用",
            "体验",
            "问题",
        }
        preferred = {
            "chatgpt",
            "claude",
            "codex",
            "cursor",
            "deepseek",
            "hermes",
            "minimax",
            "openclaw",
            "workbuddy",
        }
        candidates = [
            item.strip()
            for item in entities
            if isinstance(item, str) and item.strip()
        ]
        for item in candidates:
            if item.casefold() in preferred:
                return item
        for item in candidates:
            if not isinstance(item, str):
                continue
            if item.casefold() not in generic:
                return item
        if isinstance(objective, str):
            candidate = " ".join(objective.strip().split())
            if candidate and candidate.casefold() not in generic:
                return candidate[:120]
        return None

    async def _score_quality_candidates(
        self,
        task: dict[str, object],
        candidates: list[dict[str, object]],
    ) -> list[dict[str, object]]:
        """Score all accepted deterministic candidates in one model call."""

        if not candidates:
            return []
        snapshot = task.get("route_snapshot")
        primary = snapshot.get("primary") if isinstance(snapshot, dict) else None
        if not isinstance(primary, dict):
            raise ResearchTaskConflict("research route snapshot is missing")
        payload = [
            {
                "query_id": item["id"],
                "query": item["query"],
                "query_type": item["query_type"],
                "specificity_score": item["specificity_score"],
                "novelty_score": item["novelty_score"],
                "noise_risk_score": item["noise_risk_score"],
            }
            for item in candidates
        ]
        if not self._step_is_allowed(str(task["id"])):
            return []
        response = await self._generate(
            task_id=str(task["id"]),
            request=ModelRequest(
                system=(
                    "You are the batch query relevance gate for a bounded research task. "
                    "Score every supplied query against the research objective. "
                    "Return JSON only in the form {\"relevance_scores\":[0..1]}. "
                    "Do not add or rewrite queries."
                ),
                messages=[
                    ModelMessage(
                        role="user",
                        content=json.dumps(
                            {
                                "objective": task["objective"],
                                "candidates": payload,
                            },
                            ensure_ascii=False,
                        )[:12_000],
                    )
                ],
                max_tokens=180,
                tools=None,
                tool_choice="none",
                metadata={"runtime_step": "query_quality_review"},
                timeout=45,
            ),
            route_role="tool_calling",
            model_record_id=str(primary["model_record_id"]),
        )
        if not self._step_is_allowed(str(task["id"])):
            return []
        scores = parse_relevance_batch(response.response.content or "", len(candidates))
        if scores is None:
            for item in candidates:
                self.research.update_query_quality(
                    str(item["id"]),
                    relevance_score=None,
                    expected_value_score=None,
                    status="rejected",
                    rejection_reason="批量相关性评分解析失败，未执行查询",
                )
            return []
        approved: list[dict[str, object]] = []
        for item, relevance in zip(candidates, scores, strict=True):
            value = expected_value_score(
                relevance,
                float(item["specificity_score"]),
                float(item["novelty_score"]),
            )
            if relevance < 0.35 or value is None or value < 0.05:
                self.research.update_query_quality(
                    str(item["id"]),
                    relevance_score=relevance,
                    expected_value_score=value,
                    status="rejected",
                    rejection_reason="相关性或预期价值低于执行阈值",
                )
                continue
            updated = self.research.update_query_quality(
                str(item["id"]),
                relevance_score=relevance,
                expected_value_score=value,
                status="approved",
                lifecycle_status="approved_pending",
            )
            approved.append(updated)
        approved.sort(
            key=lambda item: query_priority_score(
                relevance_score=item.get("relevance_score"),
                specificity_score=float(item.get("specificity_score") or 0),
                novelty_score=float(item.get("novelty_score") or 0),
                noise_risk_score=float(item.get("noise_risk_score") or 0),
                expected_value_score=item.get("expected_value_score"),
                entity_diversity_bonus=float(item.get("entity_diversity_bonus") or 0),
                platform_diversity_bonus=float(item.get("platform_diversity_bonus") or 0),
                negative_evidence_bonus=float(item.get("negative_evidence_bonus") or 0),
                estimated_resource_use=float(item.get("estimated_resource_use") or 0),
            ),
            reverse=True,
        )
        return approved

    async def _prepare_quality_query(
        self,
        task: dict[str, object],
        *,
        round_number: int,
        context: dict[str, object],
        plan: dict[str, object],
        crawl_count: int,
    ) -> tuple[str, str, str] | None:
        """Persist deterministic candidates, reject noise, then batch-score."""

        task_id = str(task["id"])
        platform, platform_index = self._planned_crawl_platform(task, context)
        production_tool_service = isinstance(self.tools, ResearchToolService)
        intent_contract = task.get("intent_contract")
        if not isinstance(intent_contract, dict):
            intent_contract = context.get("intent_contract")
        modern_intent = (
            isinstance(intent_contract, dict)
            and bool(intent_contract)
            and intent_contract.get("intent_source") != "legacy_migrated"
        )
        intent_id = (
            str(intent_contract.get("id"))
            if modern_intent and intent_contract.get("id")
            else None
        )
        if crawl_count == 0:
            query = str(plan.get("initial_query") or task["objective"])[:500]
            source_type = "user_goal" if not modern_intent else "intent_plan"
            source_content_id = None
            parent_query_id = None
            reason = (
                "由用户研究目标生成研究意图，再转换为平台执行查询"
                if modern_intent
                else "由用户研究目标生成首轮查询"
            )
        else:
            term = self._quality_expansion_term(
                context.get("entities"),
                str(task.get("objective") or ""),
            )
            query = f"{term} 使用体验" if term else "个人 AI 工作台 使用体验"
            source_type = "content_entity"
            parent_query_id = context.get("last_query_id")
            parent_query_id = parent_query_id if isinstance(parent_query_id, str) else None
            source_ids = context.get("last_search_content_ids")
            if not isinstance(source_ids, list) or not source_ids:
                source_ids = context.get("last_crawl_content_ids")
            source_content_id = (
                source_ids[0]
                if isinstance(source_ids, list) and source_ids and isinstance(source_ids[0], str)
                else None
            )
            reason = (
                "从上轮查询结果的实体/场景生成扩展查询"
                + (f"，来源内容 {source_content_id}" if source_content_id else "")
            )

        if production_tool_service:
            negative_target = int(
                (task.get("coverage") or {}).get("target_negative_evidence_count", 1)
            )
            negative_found = int(
                self.research.quality_summary(task_id).get("negative_evidence_count", 0)
            )
            variants = platform_query_variants(
                query,
                platform,
                negative=bool(crawl_count > 0 and negative_found < negative_target),
            )
            if variants:
                query = variants[platform_index % len(variants)]
                reason = f"平台 {platform} 差异化证据策略；{reason}"

        historical = self.research.list_normalized_queries(exclude_task_id=task_id)
        detail = self.research.get_for_runtime(task_id, detail=True)
        current_queries = detail.get("queries", []) if isinstance(detail, dict) else []
        historical.extend(
            str(item["normalized_query"])
            for item in current_queries
            if isinstance(item, dict) and item.get("normalized_query")
        )
        raw_candidates: list[tuple[str, str, str]] = [(
            query,
            reason,
            (
                "seed_discovery"
                if modern_intent and crawl_count == 0
                else "entity_expansion"
            ),
        )]

        def transform_initial_candidate(
            candidate: str,
            candidate_role: str,
            offset: int,
        ) -> str:
            if not production_tool_service or crawl_count != 0:
                return candidate
            variants = platform_query_variants(
                candidate,
                platform,
                negative=candidate_role in {"counterevidence", "pain_point_probe"},
            )
            if not variants:
                return candidate
            platform_labels = {
                "bili": "哔哩哔哩",
                "zhihu": "知乎",
                "wb": "微博",
                "tieba": "贴吧",
                "xhs": "小红书",
            }
            label = platform_labels.get(platform, platform)
            return f"{variants[(platform_index + offset) % len(variants)]} {label}"

        if modern_intent and crawl_count > 0:
            held = self.research.claim_held_execution_query(
                task_id,
                platform=platform,
            )
            if held is not None:
                context["last_query_id"] = str(held["id"])
                context["last_query_query"] = str(held["query"])
                return str(held["query"]), str(held["id"]), platform
        if modern_intent and crawl_count == 0:
            directions = plan.get("execution_query_directions")
            if isinstance(directions, list):
                raw_candidates = []
                for item in directions[:10]:
                    if isinstance(item, dict) and isinstance(item.get("query"), str):
                        candidate_role = str(item.get("query_role") or "seed_discovery")
                        raw_candidates.append(
                            (
                                transform_initial_candidate(
                                    str(item["query"])[:500],
                                    candidate_role,
                                    len(raw_candidates),
                                ),
                                f"研究计划基于 Intent Contract 的执行查询转换：{candidate_role}",
                                candidate_role,
                            )
                        )
                if raw_candidates:
                    query = raw_candidates[0][0]
        plan_terms = plan.get("derived_keywords")
        if isinstance(plan_terms, list):
            for item in plan_terms[:8]:
                if not isinstance(item, str):
                    continue
                candidate = item.strip()[:500]
                if candidate:
                    candidate = transform_initial_candidate(
                        candidate,
                        "seed_discovery"
                        if modern_intent and crawl_count == 0
                        else "entity_expansion",
                        len(raw_candidates),
                    )
                    raw_candidates.append(
                        (
                            candidate,
                            f"{reason}；研究计划候选",
                            (
                                "seed_discovery"
                                if modern_intent and crawl_count == 0
                                else "entity_expansion"
                            ),
                        )
                    )
        # Keep the legacy control candidate for pre-8D plans so old quality
        # gate audit tests and historical task trajectories remain readable.
        if not modern_intent:
            raw_candidates.append(("agent", reason, "entity_expansion"))
        persisted: list[dict[str, object]] = []
        covered_entities = detail.get("entity_coverage", []) if isinstance(detail, dict) else []
        covered_entities = covered_entities if isinstance(covered_entities, list) else []
        for candidate, candidate_reason, candidate_role in raw_candidates:
            quality = evaluate_query(
                candidate,
                generation_reason=candidate_reason,
                source_type=source_type,
                historical_queries=historical,
                parent_query_id=parent_query_id,
                source_content_id=source_content_id,
                record_type="execution_query",
                query_role=candidate_role,
                intent_bound=modern_intent,
            )
            candidate_normalized = str(quality.normalized_query).casefold()
            matching_entities = [
                item for item in covered_entities
                if isinstance(item, dict)
                and str(item.get("canonical_name") or "").casefold() in candidate_normalized
            ]
            entity_bonus = 0.8 if not matching_entities else 0.2
            if any(bool(item.get("saturated")) for item in matching_entities):
                entity_bonus = 0.0
            row = self.research.create_query(
                task_id=task_id,
                intent_id=intent_id,
                record_type="execution_query",
                gate_status="reject" if not quality.accepted else "pending",
                decision="reject" if not quality.accepted else "transform" if modern_intent and crawl_count == 0 else "allow",
                query_role=candidate_role,
                query=candidate,
                normalized_query=quality.normalized_query,
                query_type=quality.query_type,
                platform=platform,
                source_type=source_type,
                source_content_id=source_content_id,
                source_finding_id=None,
                parent_query_id=parent_query_id,
                generation_reason=candidate_reason,
                specificity_score=quality.specificity_score,
                novelty_score=quality.novelty_score,
                noise_risk_score=quality.noise_risk_score,
                status="rejected" if not quality.accepted else "candidate",
                rejection_reason=quality.rejection_reason,
                lifecycle_status=(
                    "rejected_generic"
                    if quality.rejection_reason and "泛化" in quality.rejection_reason
                    else "rejected_duplicate"
                    if quality.rejection_reason and "重复" in quality.rejection_reason
                    else "rejected_low_value"
                    if quality.rejection_reason
                    else "generated"
                ),
                platform_diversity_bonus=0.8 if production_tool_service else 0,
                entity_diversity_bonus=entity_bonus if production_tool_service else 0,
                negative_evidence_bonus=0.8 if "负面" in candidate_reason or "反向" in candidate_reason else 0,
                estimated_resource_use=0.2,
                expected_evidence_role=(
                    "contradictory"
                    if candidate_role in {"counterevidence", "pain_point_probe"}
                    or "反向" in candidate_reason or "负面" in candidate_reason
                    else "direct"
                ),
            )
            if quality.accepted:
                persisted.append(row)
            historical.append(quality.normalized_query)
        approved = await self._score_quality_candidates(task, persisted)
        if not approved:
            return None
        selected = approved[0]
        self.research.set_query_lifecycle(
            str(selected["id"]), lifecycle_status="executing"
        )
        for skipped in approved[1:]:
            self.research.set_query_lifecycle(
                str(skipped["id"]),
                lifecycle_status="skipped_low_marginal_value",
                reason="同轮已有更高预期价值查询，保留为未执行候选",
            )
        context["last_query_id"] = str(selected["id"])
        context["last_query_query"] = str(selected["query"])
        return str(selected["query"]), str(selected["id"]), platform

    def _classify_content_value(
        self,
        task: dict[str, object],
        content_items: list[dict[str, object]],
        *,
        query_id: str | None,
        entities: list[str],
    ) -> None:
        contract_data = task.get("intent_contract")
        try:
            contract = ResearchIntentContract.model_validate(contract_data)
        except (TypeError, ValueError):
            contract = build_default_intent(str(task.get("objective") or ""), task.get("platforms") if isinstance(task.get("platforms"), list) else [])
        task_id = str(task["id"])
        known_memory_keys = self.research.list_memory_keys(exclude_task_id=task_id)
        for item in content_items:
            content_id = item.get("id")
            if not isinstance(content_id, str) or not content_id:
                continue
            try:
                decision = self.research.record_content_decision(
                    task_id=task_id,
                    content_id=content_id,
                    query_id=query_id,
                    decision="candidate",
                )
                assessments = classify_information_utility(
                    item,
                    intent=contract,
                    extracted_entities=entities,
                    known_memory_keys=known_memory_keys,
                    is_repost=bool(decision.get("is_repost")),
                    adopted=decision.get("decision") == "adopted",
                )
                for assessment in assessments:
                    self.research.record_information_utility(
                        task_id=task_id,
                        content_id=content_id,
                        utility_type=assessment.utility_type,
                        rationale=assessment.rationale,
                        confidence=assessment.confidence,
                        query_id=query_id,
                    )
                for entity in entities[:8]:
                    if entity.casefold() in {"ai", "agent", "产品", "工具", "软件", "工作台"}:
                        continue
                    known = {
                        str(value.get("name") or "").casefold()
                        for value in contract.known_entities
                        if isinstance(value, dict)
                    }
                    known.update(
                        item.casefold()
                        for item in known_memory_keys
                        if item and item.strip()
                    )
                    self.research.save_entity_candidate(
                        task_id=task_id,
                        entity_type="product",
                        normalized_name=entity,
                        source_content_id=content_id,
                        relevance_to_intent=0.8 if entity.casefold() not in known else 0.6,
                        novelty=1.0 if entity.casefold() not in known else 0.2,
                        confidence=0.72,
                        suggested_next_action="绑定父查询进行实体扩展或跨平台验证",
                    )
                event_type = event_type_for_content(item)
                if event_type:
                    self.research.save_event_candidate(
                        task_id=task_id,
                        event_type=event_type,
                        title=str(item.get("title") or content_id),
                        summary=str(item.get("description") or item.get("title") or "")[:1_000],
                        source_content_id=content_id,
                        confidence=0.72,
                    )
                if entities:
                    self.research.save_memory_item(
                        task_id=task_id,
                        memory_type="observed_entity",
                        memory_key=entities[0],
                        value={"content_id": content_id, "title": item.get("title")},
                        confidence=0.65,
                        content_id=content_id,
                        query_id=query_id,
                    )
            except (ResearchTaskConflict, ResearchTaskNotFound, ValueError):
                # A malformed third-party record must not erase the rest of a
                # bounded batch; the content remains visible in the audit log.
                continue

    def _record_core_evidence_and_memory(self, task_id: str) -> None:
        detail = self.research.get_for_runtime(task_id, detail=True)
        if not isinstance(detail, dict):
            return
        findings = detail.get("findings")
        if not isinstance(findings, list):
            return
        for finding in findings:
            if not isinstance(finding, dict):
                continue
            finding_id = str(finding.get("id") or "")
            for evidence in finding.get("evidence", []):
                if not isinstance(evidence, dict) or not isinstance(evidence.get("content_id"), str):
                    continue
                content_id = str(evidence["content_id"])
                try:
                    self.research.record_information_utility(
                        task_id=task_id,
                        content_id=content_id,
                        utility_type="core_evidence",
                        rationale="内容已绑定到 Finding，直接支持或限制研究结论。",
                        confidence=0.94,
                        finding_id=finding_id or None,
                    )
                    self.research.save_memory_item(
                        task_id=task_id,
                        memory_type="confirmed_fact" if finding.get("kind") == "fact" else "inference",
                        memory_key=str(finding.get("statement") or content_id)[:300],
                        value={"statement": finding.get("statement"), "content_id": content_id},
                        confidence=0.9 if finding.get("kind") == "fact" else 0.65,
                        content_id=content_id,
                        finding_id=finding_id or None,
                    )
                except (ResearchTaskConflict, ResearchTaskNotFound, ValueError):
                    continue

    def _intent_alignment_review(self, task_id: str, *, allow_more_research: bool) -> dict[str, object] | None:
        detail = self.research.get_for_runtime(task_id, detail=True)
        if not isinstance(detail, dict):
            return None
        contract_data = detail.get("intent_contract")
        try:
            contract = ResearchIntentContract.model_validate(contract_data)
        except (TypeError, ValueError):
            return None
        utilities = detail.get("information_utilities")
        utilities = utilities if isinstance(utilities, list) else []
        candidates = detail.get("entity_candidates")
        candidates = candidates if isinstance(candidates, list) else []
        findings = detail.get("findings")
        findings = findings if isinstance(findings, list) else []
        requirements = list(dict.fromkeys(contract.unknowns_to_discover + contract.desired_output[:]))
        covered: list[str] = []
        missing: list[str] = []
        utility_types = {str(item.get("utility_type")) for item in utilities if isinstance(item, dict)}
        if candidates:
            covered.append("unknown_entities_or_topics")
        if "core_evidence" in utility_types or findings:
            covered.append("evidence_bound_findings")
        if "counterevidence" in utility_types:
            covered.append("negative_evidence_requirements")
        if "event_signal" in utility_types:
            covered.append("event_or_change_signals")
        if "memory_update" in utility_types:
            covered.append("long_term_memory_updates")
        for requirement in requirements:
            normalized = requirement.casefold()
            if any(normalized in str(item).casefold() for item in covered):
                continue
            if requirement in {"supporting_evidence", "direct_evidence", "independent_evidence"} and ("core_evidence" in utility_types or findings):
                covered.append(requirement)
                continue
            missing.append(requirement)
        scope_drift: dict[str, object] = {"detected": False, "reason": None}
        if candidates:
            names = [str(item.get("normalized_name")) for item in candidates if isinstance(item, dict)]
            if len(set(names)) == 1 and len(names) >= 1 and "discovery" in {contract.primary_intent, *contract.secondary_intents}:
                scope_drift = {"detected": True, "reason": "当前证据集中于单一实体，尚未覆盖探索类目。", "dominant_entities": names[:1]}
        total = max(1, len(requirements) + 4)
        score = max(0.0, min(1.0, len(set(covered)) / total))
        if scope_drift.get("detected"):
            score = min(score, 0.65)
        budget_remaining = int(detail.get("consumed_crawl_count") or 0) < int(detail.get("budget_max_crawl_tasks") or detail.get("budget_crawl_limit") or 0)
        status = "passed" if score >= 0.75 and not missing and not scope_drift.get("detected") else "needs_more_research" if allow_more_research and budget_remaining else "partial_completion"
        next_step = None
        if status != "passed":
            next_step = "补足：" + "、".join(missing[:3]) if missing else "扩大实体与平台覆盖并寻找反向证据"
        return self.research.save_alignment_review(
            task_id=task_id,
            alignment_score=score,
            covered_requirements=covered,
            missing_requirements=missing,
            scope_drift=scope_drift,
            recommended_next_step=next_step,
            review_status=status,
        )

    async def _research_round(self, task: dict[str, object]) -> None:
        task_id = str(task["id"])
        round_number = max(1, int(task["current_round"]))
        plan = task.get("plan")
        if not isinstance(plan, dict):
            raise ResearchTaskConflict("research plan is missing")
        context = task.get("context")
        if not isinstance(context, dict):
            context = {}
        crawl_count = int(task["consumed_crawl_count"])
        coverage_values = task.get("coverage")
        coverage_values = coverage_values if isinstance(coverage_values, dict) else {}
        coverage_review = self.research.coverage_summary(task_id)
        marginal_stop = marginal_stop_decision(
            rounds_below_threshold=int(context.get("low_marginal_rounds") or 0),
            threshold=float(coverage_values.get("low_marginal_value_threshold", 0.1)),
            round_limit=int(coverage_values.get("low_marginal_round_limit", 2)),
            has_new_entity=int(context.get("last_new_entity_count") or 0) > 0,
            has_negative_evidence=bool(context.get("last_negative_evidence_found")),
        )
        if (
            marginal_stop is not None
            and int(coverage_review.get("actual_platform_count", 0))
            >= int(coverage_values.get("target_platform_count", 0))
        ):
            self.research.skip_pending_queries(
                task_id,
                lifecycle_status=marginal_stop,
                reason="连续低新增率且没有新增实体或反向证据",
            )
            context["stop_reason"] = marginal_stop
            self.research.update_context(task_id, context, step="marginal_review", round_number=round_number)
            self.research.set_stop_reason(task_id, marginal_stop)
            self.research.transition(
                task_id,
                status="Summarizing",
                reason=marginal_stop,
                step="summarizing",
                round_number=round_number,
            )
            return
        quality_enabled = getattr(self.tools, "supports_quality_queries", False) is True
        query_id: str | None = None
        query_platform: str | None = None
        if quality_enabled:
            prepared = await self._prepare_quality_query(
                task,
                round_number=round_number,
                context=context,
                plan=plan,
                crawl_count=crawl_count,
            )
            if prepared is None:
                if isinstance(context.get("last_crawl_failure"), str):
                    stop_reason = "query_candidates_exhausted_after_platform_failure"
                    context["stop_reason"] = stop_reason
                    self.research.update_context(
                        task_id,
                        context,
                        step="query_gate",
                        round_number=round_number,
                    )
                    self.research.set_stop_reason(task_id, stop_reason)
                    self.research.transition(
                        task_id,
                        status="Summarizing",
                        reason=stop_reason,
                        step="summarizing",
                        round_number=round_number,
                    )
                    return
                raise ResearchTaskConflict("all research query candidates were rejected")
            query, query_id, query_platform = prepared
        else:
            query = str(plan.get("initial_query") or task["objective"])
            if round_number > 1:
                derived = plan.get("derived_keywords")
                if isinstance(derived, list) and derived:
                    query = " ".join(str(item) for item in derived[:8])
        search = await self._execute_tool(
            task,
            "search_library",
            {
                "query": query,
                "platform": query_platform,
                "_research_query_id": query_id,
            },
        )
        items = search.get("data") if isinstance(search, dict) else []
        if not isinstance(items, list):
            items = []
        if query_id is not None:
            self.research.record_evidence_occurrences(
                task_id=task_id,
                content_ids=[
                    str(item["id"])
                    for item in items
                    if isinstance(item, dict) and item.get("id")
                ][:20],
                query_id=query_id,
            )
        self.research.record_step_usage(task_id, step="tool_result_evaluation")
        context["last_search_query"] = query
        context["last_search_content_ids"] = [
            str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")
        ][:20]
        context["crawl_requested"] = False
        if query_id is not None:
            context["last_query_id"] = query_id
        content_items = [item for item in items if isinstance(item, dict)]
        for item in content_items:
            content_id = item.get("id")
            if isinstance(content_id, str):
                self.research.record_content_decision(
                    task_id=task_id,
                    content_id=content_id,
                    query_id=query_id,
                    decision="candidate",
                )
        entities = [
            entity
            for entity in extract_entities(content_items)
            if entity.casefold() not in {"ai", "agent", "产品", "工具", "软件", "工作台"}
        ]
        self._classify_content_value(
            task,
            content_items,
            query_id=query_id,
            entities=list(dict.fromkeys(entities)),
        )
        self.research.record_step_usage(task_id, step="entity_extraction")
        existing_detail = self.research.get_for_runtime(task_id, detail=True)
        known_entity_names = {
            str(item.get("canonical_name")).casefold()
            for item in (existing_detail.get("entity_coverage", []) if isinstance(existing_detail, dict) else [])
            if isinstance(item, dict) and item.get("canonical_name")
        }
        context["last_new_entity_count"] = sum(
            1 for entity in dict.fromkeys(entities) if entity.casefold() not in known_entity_names
        )
        for entity in entities[:8]:
            self.research.upsert_entity_coverage(
                task_id,
                entity,
                entity_type="product" if entity.casefold() not in {"需求", "场景"} else "need",
                query_count_delta=1,
                platform=query_platform,
            )
        if query_platform is not None:
            self.research.upsert_platform_coverage(
                task_id,
                query_platform,
                status="executing",
                planned_query_count=1,
            )
        previous_entities = context.get("entities")
        previous_entities = (
            [item for item in previous_entities if isinstance(item, str) and item.strip()]
            if isinstance(previous_entities, list)
            else []
        )
        merged_entities = list(dict.fromkeys(previous_entities + entities))[:24]
        if merged_entities:
            plan["derived_keywords"] = merged_entities
            context["entities"] = merged_entities
            self.research.update_context(task_id, context, step="search_library", round_number=round_number)
            self.research.save_plan(task_id, plan=plan, route_snapshot=task.get("route_snapshot") if isinstance(task.get("route_snapshot"), dict) else {}, round_number=round_number)
        else:
            self.research.update_context(task_id, context, step="search_library", round_number=round_number)

        crawl_limit = int(task["budget_crawl_limit"])
        coverage = task.get("coverage")
        coverage = coverage if isinstance(coverage, dict) else {}
        target_platform_count = int(
            coverage.get("target_platform_count", min(3, len(task.get("platforms", []))))
        )
        target_crawls = min(crawl_limit, max(0, target_platform_count))
        if crawl_count < target_crawls and crawl_limit > 0:
            # Spend one bounded crawl per planned platform before allowing the
            # model to summarize. This is the durable cross-platform gate.
            await self._submit_research_crawl(
                task,
                context=context,
                keywords=query[:200],
                round_number=round_number,
                query_id=query_id,
            )
            return

        if query_id is not None:
            # The library search itself is an executed query even when the
            # crawl budget or platform target prevents a follow-up crawl.
            self.research.complete_query(
                query_id,
                result_count=len(content_items),
                new_content_count=0,
                existing_content_count=len(content_items),
                updated_content_count=0,
                duplicate_evidence_count=0,
            )

        if crawl_count >= crawl_limit:
            context["stop_reason"] = "budget_exhausted"
            self.research.update_context(task_id, context, step="budget_review", round_number=round_number)

        await self._model_tool_loop(task, items, query, round_number)
        self._record_core_evidence_and_memory(task_id)
        refreshed = self.research.get_for_runtime(task_id)
        if refreshed is not None:
            refreshed_context = refreshed.get("context")
            if not isinstance(refreshed_context, dict):
                refreshed_context = {}
            refreshed_context["last_negative_evidence_found"] = (
                self.research.quality_summary(task_id).get("negative_evidence_count", 0) > 0
            )
            self.research.update_context(
                task_id,
                refreshed_context,
                step="coverage_review",
                round_number=round_number,
            )
        latest = self.research.get_for_runtime(task_id)
        if latest is not None and str(latest["status"]) == "Researching" and not bool(latest.get("paused")):
            await self._ensure_research_artifacts(latest, query, round_number)
        latest = self.research.get_for_runtime(task_id)
        if latest is not None and str(latest["status"]) == "Researching" and not bool(latest.get("paused")):
            review = self._intent_alignment_review(task_id, allow_more_research=True)
            if isinstance(review, dict) and review.get("review_status") == "needs_more_research":
                self.research.append_trace(
                    task_id,
                    event="alignment_gap",
                    status="Researching",
                    reason=str(review.get("recommended_next_step") or "missing intent requirements"),
                    round_number=round_number,
                    step="coverage_review",
                )
                return
            self.research.transition(
                task_id,
                status="Summarizing",
                reason="research_round_completed",
                step="summarizing",
                round_number=round_number,
            )

    @staticmethod
    def _planned_crawl_platform(
        task: dict[str, object],
        context: dict[str, object],
    ) -> tuple[str, int]:
        raw_platforms = task.get("platforms")
        platforms = (
            [
                str(platform).casefold()
                for platform in raw_platforms
                if isinstance(platform, str) and platform
            ]
            if isinstance(raw_platforms, list)
            else []
        )
        if not platforms:
            platforms = ["bili"]
        raw_index = context.get("next_crawl_platform_index", 0)
        index = raw_index if isinstance(raw_index, int) and raw_index >= 0 else 0
        return platforms[index % len(platforms)], index

    async def _submit_research_crawl(
        self,
        task: dict[str, object],
        *,
        context: dict[str, object],
        keywords: str,
        round_number: int,
        query_id: str | None = None,
    ) -> None:
        """Submit one bounded crawl and rotate selected platforms fairly."""

        task_id = str(task["id"])
        platform, platform_index = self._planned_crawl_platform(task, context)
        context["crawl_requested"] = True
        self.research.update_context(
            task_id,
            context,
            step="submit_crawl",
            round_number=round_number,
        )
        result = await self._execute_tool(
            task,
            "submit_crawl",
            {
                "platform": platform,
                "keywords": keywords,
                "requested_count": RESEARCH_DEFAULT_REQUESTED_COUNT,
                "reason": (
                    f"平台 {platform} 证据策略；来源查询 {query_id or 'library-search'}"
                ),
                "query_type": "product",
                "parent_query_id": query_id,
                "source_content_id": (
                    context.get("last_search_content_ids", [None])[0]
                    if isinstance(context.get("last_search_content_ids"), list)
                    and context.get("last_search_content_ids")
                    else None
                ),
                "research_task_id": task_id,
                "expected_evidence_role": (
                    "contradictory"
                    if "问题" in keywords
                    or "缺点" in keywords
                    or "不好用" in keywords
                    or "失败" in keywords
                    or "替代" in keywords
                    else "direct"
                ),
                "_research_query_id": query_id,
            },
        )
        if result.get("status") == "waiting_crawl":
            context["next_crawl_platform_index"] = platform_index + 1
            self.research.upsert_platform_coverage(
                task_id,
                platform,
                status="executing",
                planned_query_count=1,
            )
            if query_id is not None:
                self.research.set_query_lifecycle(query_id, lifecycle_status="executing")
            self.research.update_context(
                task_id,
                context,
                step="waiting_crawl",
                round_number=round_number,
            )
            self.research.save_checkpoint(
                task_id,
                checkpoint_key="crawl_submitted",
                last_completed_step="search_library",
                payload={
                    "crawler_task_id": result.get("crawler_task_id"),
                    "platform": platform,
                    "query_id": query_id,
                },
            )

    async def _ensure_research_artifacts(
        self,
        task: dict[str, object],
        query: str,
        round_number: int,
    ) -> None:
        """Give the agent one bounded repair pass for required artifacts.

        The main tool loop can spend its bounded turns reading evidence and
        saving facts, then stop before it records an inference or an owner
        action.  The report would still be technically renderable, but it
        would lose the structured distinction and approval boundary that make
        the runtime auditable.  A short follow-up pass is therefore allowed to
        call only ``save_finding`` and ``propose_action``.  It never crawls or
        mutates anything else, and it is skipped when a provider error already
        forced evidence-preserving convergence.
        """
        task_id = str(task["id"])
        detail = self.research.get_for_runtime(task_id, detail=True)
        if detail is None:
            return
        findings = detail.get("findings")
        if not isinstance(findings, list) or not findings:
            return
        facts = [item for item in findings if isinstance(item, dict) and item.get("kind") == "fact"]
        inferences = [
            item for item in findings if isinstance(item, dict) and item.get("kind") == "inference"
        ]
        actions = detail.get("proposed_actions")
        has_action = isinstance(actions, list) and bool(actions)
        missing: list[str] = []
        if not facts:
            missing.append("fact")
        if not inferences:
            missing.append("inference")
        if not has_action:
            missing.append("action")
        if not missing:
            return

        trace = detail.get("execution_trace")
        if isinstance(trace, list) and any(
            isinstance(entry, dict)
            and entry.get("event") == "model_error"
            and int(entry.get("round_number") or 0) == round_number
            for entry in trace
        ):
            self.research.append_trace(
                task_id,
                event="artifact_gate",
                status="Researching",
                reason="provider_error_convergence",
                round_number=round_number,
                step="research_artifacts",
            )
            return
        budget_reason = self._budget_reason(detail)
        if budget_reason is not None:
            self.research.append_trace(
                task_id,
                event="artifact_gate",
                status="Researching",
                reason=f"{budget_reason}; missing_{'_and_'.join(missing)}",
                round_number=round_number,
                step="research_artifacts",
            )
            return

        self.research.append_trace(
            task_id,
            event="artifact_gate",
            status="Researching",
            reason=f"missing_{'_and_'.join(missing)}",
            round_number=round_number,
            step="research_artifacts",
        )
        snapshot = task.get("route_snapshot")
        primary = snapshot.get("primary") if isinstance(snapshot, dict) else None
        if not isinstance(primary, dict):
            return
        evidence = [
            {
                "id": item.get("id"),
                "kind": item.get("kind"),
                "statement": str(item.get("statement") or "")[:1_000],
                "derivation": str(item.get("derivation") or "")[:1_000],
                "content_ids": [
                    str(evidence_item.get("content_id"))
                    for evidence_item in item.get("evidence", [])
                    if isinstance(evidence_item, dict) and evidence_item.get("content_id")
                ][:8],
            }
            for item in findings
            if isinstance(item, dict)
        ]
        allowed_names = {"save_finding", "propose_action"}
        definitions = [
            definition
            for definition in self.tools.definitions()
            if definition.name in allowed_names
        ]
        messages = [
            ModelMessage(
                role="user",
                content=(
                    f"Research objective: {task['objective']}\n"
                    f"Current query: {query}\n"
                    f"Durable evidence-bound findings: {json.dumps(evidence, ensure_ascii=False)[:12_000]}\n"
                    f"Missing required artifacts: {', '.join(missing)}\n"
                    "Use only the supplied repair tools. Save at least one evidence-bound inference "
                    "with a non-empty derivation, content_ids, and per-evidence support metadata when evidence supports it. "
                    "Include counterevidence_status and counterevidence_explanation. "
                    "Then propose exactly one safe, owner-approval action. Do not crawl."
                ),
            )
        ]
        for _ in range(MAX_ARTIFACT_ROUNDS):
            if not self._step_is_allowed(task_id):
                return
            request = ModelRequest(
                system=(
                    "You are repairing the structured artifacts of a bounded research task. "
                    "Never invent evidence. Only call save_finding and propose_action."
                ),
                messages=messages,
                max_tokens=500,
                tools=definitions,
                tool_choice="auto",
                metadata={"runtime_step": "research_artifacts", "round": str(round_number)},
                timeout=60,
            )
            try:
                response = await self._generate(
                    task_id=task_id,
                    request=request,
                    route_role="tool_calling",
                    model_record_id=str(primary["model_record_id"]),
                )
            except ProviderError as error:
                self.research.append_trace(
                    task_id,
                    event="artifact_gate",
                    status="Researching",
                    reason=f"repair_failed: {error.safe_summary}",
                    round_number=round_number,
                    step="research_artifacts",
                )
                return
            if not self._step_is_allowed(task_id):
                return
            model_response = response.response
            if not model_response.tool_calls:
                break
            messages.append(
                ModelMessage(
                    role="assistant",
                    content=model_response.content,
                    tool_calls=model_response.tool_calls,
                )
            )
            for call in model_response.tool_calls:
                if call.name not in allowed_names:
                    result: dict[str, object] = {
                        "status": "tool_error",
                        "tool_name": call.name,
                        "error": "artifact repair tool is not allowed",
                    }
                else:
                    try:
                        result = await self._execute_tool(task, call.name, call.arguments)
                    except ResearchTaskConflict as error:
                        result = {
                            "status": "tool_error",
                            "tool_name": call.name,
                            "error": str(error)[:500],
                        }
                messages.append(
                    ModelMessage(
                        role="tool",
                        tool_result={
                            "tool_call_id": call.id or f"artifact-{round_number}",
                            "content": json.dumps(result, ensure_ascii=False)[:MAX_TOOL_RESULT_CHARS],
                        },
                    )
                )
        await self._ensure_action_artifact(task, query, round_number, primary)

    async def _ensure_action_artifact(
        self,
        task: dict[str, object],
        query: str,
        round_number: int,
        primary: dict[str, object],
    ) -> None:
        """Run an action-only repair pass after inference repair.

        Models can keep selecting ``save_finding`` when both repair tools are
        exposed.  Once the evidence distinction is present, isolate the
        approval boundary by exposing only ``propose_action`` and by bounding
        the pass separately from the inference repair loop.
        """
        task_id = str(task["id"])
        detail = self.research.get_for_runtime(task_id, detail=True)
        if detail is None:
            return
        actions = detail.get("proposed_actions")
        if isinstance(actions, list) and actions:
            return
        findings = detail.get("findings")
        if not isinstance(findings, list) or not findings:
            return
        budget_reason = self._budget_reason(detail)
        if budget_reason is not None:
            self.research.append_trace(
                task_id,
                event="artifact_gate",
                status="Researching",
                reason=f"{budget_reason}; missing_action",
                round_number=round_number,
                step="research_action",
            )
            return
        self.research.append_trace(
            task_id,
            event="artifact_gate",
            status="Researching",
            reason="missing_action",
            round_number=round_number,
            step="research_action",
        )
        evidence_ids = list(
            dict.fromkeys(
                str(evidence.get("content_id"))
                for item in findings
                if isinstance(item, dict)
                for evidence in item.get("evidence", [])
                if isinstance(evidence, dict) and evidence.get("content_id")
            )
        )[:12]
        definitions = [
            definition
            for definition in self.tools.definitions()
            if definition.name == "propose_action"
        ]
        messages = [
            ModelMessage(
                role="user",
                content=(
                    f"Research objective: {task['objective']}\n"
                    f"Current query: {query}\n"
                    f"Known evidence content_ids: {json.dumps(evidence_ids, ensure_ascii=False)}\n"
                    "The evidence and inference artifacts are already saved. "
                    "Call propose_action exactly once with one safe, bounded action for owner approval. "
                    "Use an existing content_id in payload when useful. Do not call save_finding, crawl, "
                    "or any other tool."
                ),
            )
        ]
        for _ in range(MAX_ACTION_ARTIFACT_ROUNDS):
            if not self._step_is_allowed(task_id):
                return
            request = ModelRequest(
                system=(
                    "You are completing the approval boundary of a bounded research task. "
                    "Only propose_action is available. Never invent evidence or execute the action."
                ),
                messages=messages,
                max_tokens=300,
                tools=definitions,
                tool_choice="auto",
                metadata={"runtime_step": "research_action", "round": str(round_number)},
                timeout=45,
            )
            try:
                response = await self._generate(
                    task_id=task_id,
                    request=request,
                    route_role="tool_calling",
                    model_record_id=str(primary["model_record_id"]),
                )
            except ProviderError as error:
                self.research.append_trace(
                    task_id,
                    event="artifact_gate",
                    status="Researching",
                    reason=f"action_repair_failed: {error.safe_summary}",
                    round_number=round_number,
                    step="research_action",
                )
                return
            if not self._step_is_allowed(task_id):
                return
            model_response = response.response
            if not model_response.tool_calls:
                break
            messages.append(
                ModelMessage(
                    role="assistant",
                    content=model_response.content,
                    tool_calls=model_response.tool_calls,
                )
            )
            for call in model_response.tool_calls:
                if call.name != "propose_action":
                    result: dict[str, object] = {
                        "status": "tool_error",
                        "tool_name": call.name,
                        "error": "action repair only permits propose_action",
                    }
                else:
                    try:
                        result = await self._execute_tool(task, call.name, call.arguments)
                    except ResearchTaskConflict as error:
                        result = {
                            "status": "tool_error",
                            "tool_name": call.name,
                            "error": str(error)[:500],
                        }
                messages.append(
                    ModelMessage(
                        role="tool",
                        tool_result={
                            "tool_call_id": call.id or f"action-{round_number}",
                            "content": json.dumps(result, ensure_ascii=False)[:MAX_TOOL_RESULT_CHARS],
                        },
                    )
                )
            latest = self.research.get_for_runtime(task_id, detail=True)
            latest_actions = latest.get("proposed_actions") if latest else None
            if isinstance(latest_actions, list) and latest_actions:
                return
        self.research.append_trace(
            task_id,
            event="artifact_gate",
            status="Researching",
            reason="action_repair_incomplete",
            round_number=round_number,
            step="research_action",
        )

    async def _model_tool_loop(
        self,
        task: dict[str, object],
        items: list[object],
        query: str,
        round_number: int,
    ) -> None:
        task_id = str(task["id"])
        snapshot = task.get("route_snapshot")
        primary = snapshot.get("primary") if isinstance(snapshot, dict) else None
        if not isinstance(primary, dict):
            raise ResearchTaskConflict("research route snapshot is missing")
        detail = self.research.get_for_runtime(task_id, detail=True) or task
        runtime_context = detail.get("context")
        runtime_context = dict(runtime_context) if isinstance(runtime_context, dict) else {}
        compacted, compaction_stats = compact_research_context(
            objective=str(task["objective"]),
            coverage=(detail.get("coverage") if isinstance(detail.get("coverage"), dict) else {}),
            entities=(detail.get("entity_coverage") if isinstance(detail.get("entity_coverage"), list) else []),
            queries=(detail.get("queries") if isinstance(detail.get("queries"), list) else []),
            findings=(detail.get("findings") if isinstance(detail.get("findings"), list) else []),
            candidate_contents=items,
            loaded_content_ids=(
                runtime_context.get("full_content_ids", [])
                if isinstance(runtime_context, dict)
                else []
            ),
            budget={
                "token_limit": task.get("budget_token_limit"),
                "model_calls": task.get("consumed_model_call_count", 0),
                "crawl_count": task.get("consumed_crawl_count", 0),
            },
        )
        runtime_context["compacted_context"] = compacted
        runtime_context["compaction_stats"] = compaction_stats
        self.research.update_context(task_id, runtime_context, step="context_compaction", round_number=round_number)
        self.research.append_trace(
            task_id,
            event="context_compacted",
            status="Researching",
            reason=json.dumps(compaction_stats, ensure_ascii=False),
            round_number=round_number,
            step="context_compaction",
        )
        self.research.record_step_usage(task_id, step="evidence_selection")
        item_cards = [
            {
                "content_id": item.get("id"),
                "title": str(item.get("title") or "")[:300],
                "description": str(item.get("description") or "")[:800],
                "source_url": item.get("source_url") or (item.get("source") or {}).get("url") if isinstance(item.get("source"), dict) else item.get("source_url"),
                "platform": item.get("platform"),
                "published_at": item.get("published_at"),
                "evidence_role": "candidate",
            }
            for item in items[:20]
            if isinstance(item, dict)
        ]
        messages = [
            ModelMessage(
                role="user",
                content=(
                    f"Research objective: {task['objective']}\n"
                    f"Current query: {query}\n"
                    f"Collected evidence cards (JSON): {json.dumps(item_cards[:12], ensure_ascii=False)[:16_000]}\n"
                    f"Compacted research context (JSON): {json.dumps(compacted, ensure_ascii=False)[:12_000]}\n"
                    "Respect the coverage plan: compare relevant candidates across every completed platform before concluding, "
                    "and do not let one entity or one platform stand in for the market. "
                    "When the plan asks for negative evidence, inspect at least one bounded problem/shortcoming query; "
                    "record not_found only when the inspected evidence genuinely contains no contrary signal. "
                    "Use tools to inspect evidence. Every fact or inference must be saved with content_ids and one evidence_links item per content_id; each item needs support_type, support_strength, and a one-sentence support_explanation. "
                    "Inference findings also need a derivation and counterevidence_explanation; use not_found only when no contrary evidence was found. "
                    "If evidence is insufficient, submit one bounded crawl. Finish by saving findings and proposing one safe action."
                ),
            )
        ]
        for _ in range(MAX_TOOL_ROUNDS):
            if not self._step_is_allowed(task_id):
                return
            request = ModelRequest(
                system=(
                    "You are the only Research Agent. Use only the supplied tools. "
                    "Never state an unsupported fact. Prefer existing library evidence, "
                    "and call save_finding for every conclusion."
                ),
                messages=messages,
                max_tokens=700,
                tools=self.tools.definitions(),
                tool_choice="auto",
                metadata={"runtime_step": "finding_generation", "round": str(round_number)},
                timeout=60,
            )
            try:
                response = await self._generate(
                    task_id=task_id,
                    request=request,
                    route_role="tool_calling",
                    model_record_id=str(primary["model_record_id"]),
                )
            except ProviderError as error:
                detail = self.research.get_for_runtime(task_id, detail=True)
                findings = detail.get("findings", []) if detail is not None else []
                if error.code != "protocol_error" or not isinstance(findings, list) or not findings:
                    raise
                self.research.append_trace(
                    task_id,
                    event="model_error",
                    status="Researching",
                    reason=error.safe_summary,
                    round_number=round_number,
                    step="research_round",
                )
                # Evidence is already durable.  Converge to the report instead
                # of discarding the completed findings because one provider
                # response could not be normalized.
                return
            if not self._step_is_allowed(task_id):
                return
            model_response = response.response
            if not model_response.tool_calls:
                context = self.research.get_for_runtime(task_id)
                context_data = context.get("context") if context else {}
                if not isinstance(context_data, dict):
                    context_data = {}
                context_data["last_model_text"] = (model_response.content or "")[:10_000]
                self.research.update_context(task_id, context_data, step="research_round", round_number=round_number)
                return
            assistant = ModelMessage(
                role="assistant",
                content=model_response.content,
                tool_calls=model_response.tool_calls,
            )
            messages.append(assistant)
            for call in model_response.tool_calls:
                if not self._step_is_allowed(task_id):
                    return
                try:
                    result = await self._execute_tool(task, call.name, call.arguments)
                except ResearchTaskConflict as error:
                    # Scope and capability violations are tool-level failures,
                    # not runtime failures.  Return a safe, bounded error to
                    # the model so it can continue with evidence already in
                    # context (for example, after attempting an out-of-scope
                    # platform crawl).
                    result = {
                        "status": "tool_error",
                        "tool_name": call.name,
                        "error": str(error)[:500],
                    }
                if result.get("status") == "waiting_crawl":
                    context = self.research.get_for_runtime(task_id)
                    if context is not None:
                        context_data = context.get("context")
                        if not isinstance(context_data, dict):
                            context_data = {}
                        context_data["messages"] = [message.model_dump(mode="json") for message in messages]
                        self.research.update_context(task_id, context_data, step="waiting_crawl", round_number=round_number)
                    return
                messages.append(
                    ModelMessage(
                        role="tool",
                        tool_result={
                            "tool_call_id": call.id or f"tool-{round_number}",
                            "content": json.dumps(result, ensure_ascii=False)[:MAX_TOOL_RESULT_CHARS],
                        },
                    )
                )

    async def _execute_tool(
        self,
        task: dict[str, object],
        name: str,
        arguments: dict[str, object],
    ) -> dict[str, object]:
        task_id = str(task["id"])
        self.research.append_trace(
            task_id,
            event="tool_call",
            status=str(task["status"]),
            reason="agent_tool_dispatch",
            round_number=int(task["current_round"]),
            step=name,
            tool_name=name,
            tool_arguments=_safe_arguments(arguments),
        )
        try:
            result = await self.tools.execute(task=task, tool_name=name, arguments=arguments)
        except Exception as error:
            self.research.append_trace(
                task_id,
                event="tool_error",
                status=str(task["status"]),
                reason=self._safe_failure(error),
                round_number=int(task["current_round"]),
                step=name,
                tool_name=name,
                tool_arguments=_safe_arguments(arguments),
            )
            raise
        if name == "get_content":
            content_id = arguments.get("content_id")
            if isinstance(content_id, str) and content_id:
                current = self.research.get_for_runtime(task_id)
                context = current.get("context") if current else {}
                context = dict(context) if isinstance(context, dict) else {}
                loaded = context.get("full_content_ids")
                loaded_ids = [item for item in loaded if isinstance(item, str)] if isinstance(loaded, list) else []
                if content_id not in loaded_ids:
                    loaded_ids.append(content_id)
                context["full_content_ids"] = loaded_ids[-50:]
                stats = context.get("compaction_stats")
                stats = dict(stats) if isinstance(stats, dict) else {}
                stats["loaded_full_content_count"] = len(context["full_content_ids"])
                context["compaction_stats"] = stats
                self.research.update_context(task_id, context, step="get_content")
        self.research.append_trace(
            task_id,
            event="tool_result",
            status=str(task["status"]),
            reason="tool_completed",
            round_number=int(task["current_round"]),
            step=name,
            tool_name=name,
        )
        return result

    async def _summarize(self, task: dict[str, object]) -> None:
        task_id = str(task["id"])
        snapshot = task.get("route_snapshot")
        final = snapshot.get("final_report") if isinstance(snapshot, dict) else None
        primary = snapshot.get("primary") if isinstance(snapshot, dict) else None
        route_role: ModelRouteRole = "final_report" if isinstance(final, dict) else "tool_calling"
        target = final if isinstance(final, dict) else primary
        if not isinstance(target, dict):
            raise ResearchTaskConflict("summary route snapshot is missing")
        detail = self.research.get_for_runtime(task_id, detail=True)
        if detail is None:
            raise ResearchTaskConflict("research task disappeared before summarizing")
        self.research.finalize_content_decisions(task_id)
        self.research.finalize_platform_coverage(task_id)
        self._record_core_evidence_and_memory(task_id)
        detail = self.research.get_for_runtime(task_id, detail=True) or detail
        alignment_review = self._intent_alignment_review(task_id, allow_more_research=False)
        findings = detail.get("findings") or []
        context = detail.get("context") or {}
        context = dict(context) if isinstance(context, dict) else {}
        candidate_contents = [
            {"id": item.get("content_id")}
            for item in (detail.get("content_decisions") or [])
            if isinstance(item, dict) and item.get("content_id")
        ]
        compacted_context, compaction_stats = compact_research_context(
            objective=str(detail["objective"]),
            coverage=(detail.get("coverage") if isinstance(detail.get("coverage"), dict) else {}),
            entities=(detail.get("entity_coverage") if isinstance(detail.get("entity_coverage"), list) else []),
            queries=(detail.get("queries") if isinstance(detail.get("queries"), list) else []),
            findings=(findings if isinstance(findings, list) else []),
            candidate_contents=candidate_contents,
            loaded_content_ids=context.get("full_content_ids", []),
            unresolved_questions=(
                context.get("unresolved_questions", [])
                if isinstance(context.get("unresolved_questions"), list)
                else []
            ),
            budget={
                "max_total_tokens": detail.get("budget_max_total_tokens"),
                "max_model_calls": detail.get("budget_max_model_calls"),
                "max_crawl_tasks": detail.get("budget_max_crawl_tasks"),
                "consumed_model_calls": detail.get("consumed_model_call_count"),
                "consumed_crawl_tasks": detail.get("consumed_crawl_count"),
            },
        )
        context["compacted_context"] = compacted_context
        context["compaction_stats"] = compaction_stats
        self.research.update_context(
            task_id,
            context,
            step="context_compaction",
            round_number=int(detail.get("current_round") or 1),
        )
        self.research.record_step_usage(task_id, step="context_compaction")
        quality = self.research.quality_summary(task_id)
        coverage_review = self.research.coverage_summary(task_id)
        self.research.record_step_usage(task_id, step="coverage_review")
        stop_reason = detail.get("stop_reason")
        if not isinstance(stop_reason, str) or not stop_reason:
            stop_reason = (
                "coverage_target_reached"
                if coverage_review.get("all_targets_reached")
                else "budget_exhausted"
                if self._budget_reason(detail) is not None
                else "platform_capability_limited"
            )
            self.research.set_stop_reason(task_id, stop_reason)
        quality_queries = detail.get("queries") or []
        utility_rows = detail.get("information_utilities")
        utility_rows = utility_rows if isinstance(utility_rows, list) else []
        utility_counts: dict[str, int] = {}
        for row in utility_rows:
            if isinstance(row, dict) and isinstance(row.get("utility_type"), str):
                key = str(row["utility_type"])
                utility_counts[key] = utility_counts.get(key, 0) + 1
        prompt = {
            "objective": detail["objective"],
            "findings": findings,
            "events": detail.get("events") or [],
            "query_quality": quality_queries,
            "quality_counts": quality,
            "coverage_review": coverage_review,
            "intent_contract": detail.get("intent_contract"),
            "alignment_review": alignment_review,
            "information_utility_counts": utility_counts,
            "discovery_candidates": detail.get("entity_candidates", []),
            "step_usage": detail.get("step_usage", []),
            "billing_summary": detail.get("billing_summary", {}),
            "last_model_text": context.get("last_model_text") if isinstance(context, dict) else None,
            "compacted_context": compacted_context,
            "evidence_rule": "separate facts, inferences, unknowns, and proposed actions",
        }
        if not self._step_is_allowed(task_id):
            return
        response = await self._generate(
            task_id=task_id,
            request=ModelRequest(
                system="Write a concise research report. Do not introduce facts without evidence IDs. Clearly label inference and unknown.",
                messages=[ModelMessage(role="user", content=json.dumps(prompt, ensure_ascii=False)[:32_000])],
                max_tokens=1_200,
                tools=None,
                tool_choice="none",
                metadata={"runtime_step": "final_report"},
                timeout=60,
            ),
            route_role=route_role,
            model_record_id=str(target["model_record_id"]),
        )
        if not self._step_is_allowed(task_id):
            return
        summary_markdown = (response.response.content or "").strip()
        result = {
            # Keep the historical key for existing consumers while exposing
            # explicit formats for the Research Center and future exporters.
            "research_question": detail["objective"],
            "intent_contract": detail.get("intent_contract"),
            "research_scope": {
                "platforms": detail.get("platforms", []),
                "time_scope": (
                    detail.get("intent_contract", {}).get("time_scope", {})
                    if isinstance(detail.get("intent_contract"), dict)
                    else {}
                ),
            },
            "discovery_entities": detail.get("entity_candidates", []),
            "event_candidates": detail.get("event_candidates", []),
            "evidence_gaps": (
                alignment_review.get("missing_requirements", [])
                if isinstance(alignment_review, dict)
                else []
            ),
            "recommended_next_actions": detail.get("proposed_actions", []),
            "summary": summary_markdown,
            "summary_markdown": summary_markdown,
            "summary_html": render_research_markdown(summary_markdown),
            "facts": [item for item in findings if isinstance(item, dict) and item.get("kind") == "fact"],
            "inferences": [item for item in findings if isinstance(item, dict) and item.get("kind") == "inference"],
            "evidence_count": quality["independent_evidence_count"],
            "new_content_count": quality["new_content_count"],
            "existing_content_count": quality["existing_content_count"],
            "updated_content_count": quality["updated_content_count"],
            "duplicate_evidence_count": quality["duplicate_evidence_count"],
            "independent_evidence_count": quality["independent_evidence_count"],
            "discovery_count": quality["discovery_count"],
            "repost_count": quality.get("repost_count", 0),
            "negative_evidence_count": quality.get("negative_evidence_count", 0),
            "information_utility_counts": utility_counts,
            "discovery_seed_count": utility_counts.get("discovery_seed", 0),
            "core_evidence_count": utility_counts.get("core_evidence", 0),
            "background_context_count": utility_counts.get("background_context", 0),
            "event_signal_count": utility_counts.get("event_signal", 0),
            "noise_count": utility_counts.get("noise", 0),
            "duplicate_count": utility_counts.get("duplicate", 0),
            "alignment_review": alignment_review,
            "coverage_review": coverage_review,
            "stop_reason": stop_reason,
            "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        }
        self.research.update_result(task_id, result)
        self.research.transition(
            task_id,
            status="AwaitingReview",
            reason="summary_saved_for_owner_review",
            step="awaiting_review",
            finished=False,
        )

    async def _generate(
        self,
        *,
        task_id: str,
        request: ModelRequest,
        route_role: ModelRouteRole,
        model_record_id: str,
    ):
        started = perf_counter()
        response = await self.gateway.generate(
            request,
            route_role=route_role,
            model_record_id=model_record_id,
            research_task_id=task_id,
        )
        model_response = response.response
        usage = model_response.usage
        provider_metadata = self.ai_repository.get_provider(response.final_provider_id)
        provider_metadata = provider_metadata if isinstance(provider_metadata, dict) else {}
        step = str(request.metadata.get("runtime_step") or "unknown")
        billing_snapshot: dict[str, object] = {}
        billing_reader = getattr(self.ai_repository, "invocation_billing", None)
        if callable(billing_reader):
            candidate = billing_reader(
                request_correlation_id=response.request_correlation_id,
                research_task_id=task_id,
            )
            if isinstance(candidate, dict):
                billing_snapshot = candidate
        estimated_cost = billing_snapshot.get("estimated_cost")
        if estimated_cost is None:
            estimated_cost = self.ai_repository.invocation_cost(
                request_correlation_id=response.request_correlation_id,
                research_task_id=task_id,
            )
        self.research.record_usage(
            task_id,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            cached_tokens=usage.cached_tokens if usage else None,
            estimated_cost=estimated_cost,
            provider=model_response.provider,
            model=model_response.model,
            route_role=response.route_role,
            request_correlation_id=response.request_correlation_id,
            elapsed_ms=max(0, round((perf_counter() - started) * 1000)),
            currency=(
                str(billing_snapshot["currency"])
                if billing_snapshot.get("currency")
                else None
            ),
            price_source=(
                str(billing_snapshot["price_source"])
                if billing_snapshot.get("price_source")
                else None
            ),
            provider_instance_id=response.final_provider_id,
            vendor=(str(provider_metadata["vendor"]) if provider_metadata.get("vendor") else None),
            billing_mode=(
                str(provider_metadata["billing_mode"])
                if provider_metadata.get("billing_mode")
                else None
            ),
            fallback_from_provider_instance_id=(
                response.initial_provider_id if response.fallback_used else None
            ),
            fallback_reason="primary_provider_failed" if response.fallback_used else None,
            step=step,
        )
        self.research.save_checkpoint(
            task_id,
            checkpoint_key=f"model_step_{step}",
            last_completed_step=step,
            payload={
                "request_correlation_id": response.request_correlation_id,
                "initial_provider_id": response.initial_provider_id,
                "final_provider_id": response.final_provider_id,
                "fallback_used": response.fallback_used,
            },
        )
        return response
