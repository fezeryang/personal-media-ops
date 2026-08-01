from __future__ import annotations

import asyncio
import json
from datetime import UTC, datetime
from time import perf_counter

from app.models.ai import ModelMessage, ModelRequest, ModelRouteRole
from app.repositories.ai import AIRepository
from app.repositories.research import (
    ResearchTaskConflict,
    ResearchTaskRepository,
)
from app.services.ai.model_gateway import ModelGateway
from app.services.ai.providers import ProviderError
from app.services.ai.research_tools import ResearchToolService, extract_entities

MAX_TOOL_ROUNDS = 8
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

    def _recover_waiting_crawls(self) -> None:
        self.research.reconcile_orphan_crawls()
        for item in self.research.waiting_crawls():
            status = str(item["crawler_status"])
            crawler_id = str(item["crawler_id"])
            if status == "succeeded":
                self.research.record_crawl_completion(
                    crawler_id,
                    succeeded=True,
                    new_content_count=0,
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
        task = self.research.get_for_runtime(task_id) or task
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
        if tokens >= int(task["budget_token_limit"]):
            return "token budget reached"
        if bool(task["budget_cost_enabled"]) and task.get("budget_cost_limit") is not None:
            consumed = float(task.get("estimated_cost") or 0)
            if consumed >= float(task["budget_cost_limit"]):
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
                "model": primary.get("model_id"),
                "streaming": model.get("supports_streaming") is True,
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
        }

    async def _plan(self, task: dict[str, object]) -> None:
        task_id = str(task["id"])
        snapshot = self._route_snapshot(task)
        primary = snapshot["primary"]
        if not isinstance(primary, dict):
            raise ResearchTaskConflict("research route snapshot is invalid")
        primary_model = self.ai_repository.get_model(str(primary["model_record_id"]))
        cost_enabled = bool(
            task.get("budget_cost_limit") is not None
            and task.get("budget_cost_currency")
            and primary_model is not None
            and primary_model.get("input_price_per_million") is not None
            and primary_model.get("output_price_per_million") is not None
            and primary_model.get("price_currency")
            and primary_model.get("price_effective_at")
        )
        self.research.set_cost_enabled(task_id, cost_enabled)
        snapshot["cost_enabled"] = cost_enabled
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
        response = await self._generate(
            task_id=task_id,
            request=request,
            route_role="tool_calling",
            model_record_id=str(primary["model_record_id"]),
        )
        text = response.response.content or ""
        derived_keywords = self._plan_keywords(text, str(task["objective"]))
        if len(derived_keywords) < 3:
            raise ResearchTaskConflict(
                "planner returned fewer than three novel search terms"
            )
        plan = {
            "objective": str(task["objective"]),
            "model_plan": text[:8_000],
            "steps": [
                "search existing library",
                "collect missing evidence when necessary",
                "deduplicate and save evidence-bound findings",
                "summarize facts, inferences, and proposed actions",
            ],
            "initial_query": str(task["objective"])[:500],
            "derived_keywords": derived_keywords,
        }
        self.research.save_plan(task_id, plan=plan, route_snapshot=snapshot, round_number=1)
        context = task.get("context")
        if not isinstance(context, dict):
            context = {}
        context.update({"messages": [], "entities": [], "crawl_requested": False})
        self.research.update_context(task_id, context, step="research_round", round_number=1)
        self.research.transition(
            task_id,
            status="Researching",
            reason="planning_completed",
            step="research_round",
            round_number=1,
        )

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
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError:
            # Compatible models sometimes wrap an otherwise valid JSON plan
            # in a Markdown code fence.  Strip only that presentation layer;
            # the persisted raw model plan remains untouched for auditability.
            fenced = text.strip()
            if fenced.startswith("```") and fenced.endswith("```"):
                lines = fenced.splitlines()
                fenced = "\n".join(lines[1:-1]).strip()
                if fenced.casefold().startswith("json\n"):
                    fenced = fenced[5:]
            try:
                parsed = json.loads(fenced)
            except json.JSONDecodeError:
                parsed = None
        parsed_candidates = False
        if isinstance(parsed, dict):
            for key in ("search_terms", "keywords", "queries", "derived_keywords"):
                value = parsed.get(key)
                if isinstance(value, list):
                    raw_candidates.extend(str(item) for item in value)
                    parsed_candidates = True
        elif isinstance(parsed, list):
            raw_candidates.extend(str(item) for item in parsed)
            parsed_candidates = True
        if not parsed_candidates:
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

    async def _research_round(self, task: dict[str, object]) -> None:
        task_id = str(task["id"])
        round_number = max(1, int(task["current_round"]))
        plan = task.get("plan")
        if not isinstance(plan, dict):
            raise ResearchTaskConflict("research plan is missing")
        query = str(plan.get("initial_query") or task["objective"])
        if round_number > 1:
            derived = plan.get("derived_keywords")
            if isinstance(derived, list) and derived:
                query = " ".join(str(item) for item in derived[:8])
        search = await self._execute_tool(
            task,
            "search_library",
            {"query": query, "platform": None},
        )
        items = search.get("data") if isinstance(search, dict) else []
        if not isinstance(items, list):
            items = []
        context = task.get("context")
        if not isinstance(context, dict):
            context = {}
        context["last_search_query"] = query
        context["last_search_content_ids"] = [
            str(item.get("id")) for item in items if isinstance(item, dict) and item.get("id")
        ][:20]
        context["crawl_requested"] = False
        entities = extract_entities([item for item in items if isinstance(item, dict)])
        if entities:
            plan["derived_keywords"] = entities
            context["entities"] = entities
            self.research.update_context(task_id, context, step="search_library", round_number=round_number)
            self.research.save_plan(task_id, plan=plan, route_snapshot=task.get("route_snapshot") if isinstance(task.get("route_snapshot"), dict) else {}, round_number=round_number)
        else:
            self.research.update_context(task_id, context, step="search_library", round_number=round_number)

        crawl_count = int(task["consumed_crawl_count"])
        crawl_limit = int(task["budget_crawl_limit"])
        if crawl_count == 0 and crawl_limit > 0:
            # Always spend the first bounded crawl after checking the library;
            # this makes the first round a real retrieval pass even when the
            # library already contains adjacent material.
            context["crawl_requested"] = True
            self.research.update_context(task_id, context, step="submit_crawl", round_number=round_number)
            await self._execute_tool(
                task,
                "submit_crawl",
                {
                    "platform": str((task.get("platforms") or ["bili"])[0]),
                    "keywords": query[:200],
                    "requested_count": 5,
                },
            )
            return
        if crawl_count < min(2, crawl_limit) and items and round_number >= 1 and entities:
            # The second-round query is made only from entities extracted from
            # actual first-round library results; it never repeats the goal.
            context["crawl_requested"] = True
            self.research.update_context(task_id, context, step="submit_crawl", round_number=round_number + 1)
            await self._execute_tool(
                task,
                "submit_crawl",
                {
                    "platform": str((task.get("platforms") or ["bili"])[0]),
                    "keywords": " ".join(entities[:6]),
                    "requested_count": 5,
                },
            )
            return
        if not items and crawl_count == 0 and crawl_count < crawl_limit:
            context["crawl_requested"] = True
            self.research.update_context(task_id, context, step="submit_crawl", round_number=round_number)
            await self._execute_tool(
                task,
                "submit_crawl",
                {
                    "platform": str((task.get("platforms") or ["bili"])[0]),
                    "keywords": query[:200],
                    "requested_count": 5,
                },
            )
            return

        await self._model_tool_loop(task, items, query, round_number)
        latest = self.research.get_for_runtime(task_id)
        if latest is not None and str(latest["status"]) == "Researching":
            self.research.transition(
                task_id,
                status="Summarizing",
                reason="research_round_completed",
                step="summarizing",
                round_number=round_number,
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
        messages = [
            ModelMessage(
                role="user",
                content=(
                    f"Research objective: {task['objective']}\n"
                    f"Current query: {query}\n"
                    f"Collected library results (JSON): {json.dumps(items[:12], ensure_ascii=False)[:16_000]}\n"
                    "Use tools to inspect evidence. Every fact or inference must be saved with content_ids. "
                    "If evidence is insufficient, submit one bounded crawl. Finish by saving findings and proposing one safe action."
                ),
            )
        ]
        for _ in range(MAX_TOOL_ROUNDS):
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
                metadata={"runtime_step": "research_round", "round": str(round_number)},
                timeout=60,
            )
            response = await self._generate(
                task_id=task_id,
                request=request,
                route_role="tool_calling",
                model_record_id=str(primary["model_record_id"]),
            )
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
                result = await self._execute_tool(task, call.name, call.arguments)
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
        findings = detail.get("findings") or []
        context = detail.get("context") or {}
        prompt = {
            "objective": detail["objective"],
            "findings": findings,
            "events": detail.get("events") or [],
            "last_model_text": context.get("last_model_text") if isinstance(context, dict) else None,
            "evidence_rule": "separate facts, inferences, unknowns, and proposed actions",
        }
        response = await self._generate(
            task_id=task_id,
            request=ModelRequest(
                system="Write a concise research report. Do not introduce facts without evidence IDs. Clearly label inference and unknown.",
                messages=[ModelMessage(role="user", content=json.dumps(prompt, ensure_ascii=False)[:32_000])],
                max_tokens=1_200,
                tools=None,
                tool_choice="none",
                metadata={"runtime_step": "summarizing"},
                timeout=60,
            ),
            route_role=route_role,
            model_record_id=str(target["model_record_id"]),
        )
        result = {
            "summary": (response.response.content or "").strip(),
            "facts": [item for item in findings if isinstance(item, dict) and item.get("kind") == "fact"],
            "inferences": [item for item in findings if isinstance(item, dict) and item.get("kind") == "inference"],
            "evidence_count": sum(len(item.get("evidence", [])) for item in findings if isinstance(item, dict)),
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
        self.research.record_usage(
            task_id,
            input_tokens=usage.input_tokens if usage else None,
            output_tokens=usage.output_tokens if usage else None,
            cached_tokens=usage.cached_tokens if usage else None,
            estimated_cost=self.ai_repository.invocation_cost(
                request_correlation_id=response.request_correlation_id,
                research_task_id=task_id,
            ),
            provider=model_response.provider,
            model=model_response.model,
            route_role=response.route_role,
            request_correlation_id=response.request_correlation_id,
            elapsed_ms=max(0, round((perf_counter() - started) * 1000)),
        )
        return response
