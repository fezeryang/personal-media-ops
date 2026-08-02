from __future__ import annotations

import asyncio
import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import AsyncMock, Mock

import pytest

from app.models.ai import (
    GatewayResponse,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelToolDefinition,
    ModelUsage,
)
from app.repositories.research import ResearchTaskConflict, ResearchTaskRepository
from app.services.ai.model_gateway import ModelGateway
from app.services.ai.providers import ProviderError
from app.services.ai.research_runtime import (
    ResearchRuntime,
    _elapsed_from,
    _json,
    _safe_arguments,
)
from app.services.ai.research_tools import ResearchToolService, extract_entities
from tests.test_research_runtime import create_task, setup_database


def _gateway_response(content: str) -> GatewayResponse:
    response = ModelResponse(
        content=content,
        provider="MiniMax",
        model="MiniMax-M3",
        usage=ModelUsage(input_tokens=8, output_tokens=4, cached_tokens=1),
    )
    return GatewayResponse(
        response=response,
        route_role="tool_calling",
        fallback_used=False,
        request_correlation_id="correlation-8c",
        initial_provider_id="provider-1",
        initial_model_id="model-1",
        final_provider_id="provider-1",
        final_model_id="model-1",
    )


def _route(role: str, model_id: str, *, billing_mode: str, provider_id: str) -> dict[str, object]:
    return {
        "role": role,
        "model_record_id": model_id,
        "provider_id": provider_id,
        "provider_name": provider_id,
        "model_id": model_id,
        "vendor": "MiniMax" if billing_mode == "subscription_fixed" else "DeepSeek",
        "billing_mode": billing_mode,
        "model_enabled": True,
        "provider_enabled": True,
    }


def _model(model_id: str) -> dict[str, object]:
    return {
        "id": model_id,
        "model_id": model_id,
        "supports_tools": True,
        "supports_streaming": True,
        "input_price_per_million": "1",
        "output_price_per_million": "2",
        "cached_input_price_per_million": "0.5",
        "price_currency": "USD",
        "price_effective_at": "2026-08-01T00:00:00Z",
    }


def test_runtime_helpers_budget_gates_and_durable_controls(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task_id = str(task["id"])
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=Mock(),
        gateway=Mock(),
        tools=Mock(),
    )

    assert _json("{\"ok\":true}", {}) == {"ok": True}
    assert _json("invalid", {"fallback": True}) == {"fallback": True}
    safe = _safe_arguments({"long": "x" * 600, "items": ["y" * 300], "map": {"k": 3}})
    assert len(str(safe["long"])) == 500
    assert _elapsed_from("invalid") == 0
    assert _elapsed_from((datetime.now(UTC) - timedelta(seconds=2)).isoformat()) >= 1
    assert runtime._safe_failure(ProviderError(code="rate_limited", safe_summary="limited", retryable=True)) == "limited"
    assert runtime._safe_failure(RuntimeError("hidden")) == "Research runtime failed while executing a bounded step"

    base = repository.get_for_runtime(task_id)
    assert base is not None

    def budget_reason(**updates: object) -> str | None:
        candidate = dict(base)
        candidate["context"] = {}
        candidate.update(updates)
        return runtime._budget_reason(candidate)

    assert budget_reason(consumed_crawl_count=2, context={"crawl_requested": True}) == "crawl task budget reached"
    assert budget_reason(consumed_content_count=100) == "new content budget reached"
    assert budget_reason(started_at="2000-01-01T00:00:00Z") == "research duration budget reached"
    assert budget_reason(input_tokens=25_000, output_tokens=25_000) == "token budget reached"
    assert budget_reason(input_tokens=10, budget_max_input_tokens=10) == "input token budget reached"
    assert budget_reason(output_tokens=10, budget_max_output_tokens=10) == "output token budget reached"
    assert budget_reason(consumed_model_call_count=2, budget_max_model_calls=2) == "model call budget reached"
    assert budget_reason(budget_cost_enabled=True, budget_cost_limit="1", estimated_cost="1") == "configured cost budget reached"
    assert budget_reason() is None

    assert runtime._step_is_allowed(task_id) is True
    repository.control(task_id, "pause")
    assert runtime._step_is_allowed(task_id) is False
    repository.control(task_id, "resume")
    assert runtime._step_is_allowed(task_id) is True
    repository.control(task_id, "cancel", "owner cancelled")
    assert runtime._step_is_allowed(task_id) is False
    assert runtime._step_is_allowed("missing") is False

    stale = dict(base)
    stale["context"] = {"crawl_requested": True}
    stale["consumed_crawl_count"] = stale["budget_crawl_limit"]
    repaired = runtime._clear_stale_completed_crawl_marker(stale)
    assert repaired["context"]["crawl_requested"] is False  # type: ignore[index]

    assert ResearchRuntime._planned_crawl_platform({}, {}) == ("bili", 0)
    assert ResearchRuntime._planned_crawl_platform({"platforms": ["bili", "zhihu"]}, {"next_crawl_platform_index": -1}) == ("bili", 0)
    assert ResearchRuntime._planned_crawl_platform({"platforms": ["bili", "zhihu"]}, {"next_crawl_platform_index": 1}) == ("zhihu", 1)


def test_runtime_route_policy_and_plan_generation(tmp_path: Path) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task_record = create_task(
        database,
        owner_id,
        route_policy="prefer_subscription",
        max_payg_amount="1",
        budget_currency="USD",
    )
    task_id = str(task_record["id"])
    routes = [
        _route("tool_calling", "tool-model", billing_mode="unknown", provider_id="provider-tool"),
        _route("deep", "subscription-model", billing_mode="subscription_fixed", provider_id="provider-sub"),
        _route("final_report", "payg-model", billing_mode="pay_as_you_go", provider_id="provider-payg"),
    ]
    ai_repository = Mock()
    ai_repository.list_routes.return_value = routes
    ai_repository.get_model.side_effect = lambda model_id: _model(str(model_id))
    ai_repository.effective_pricing_model.side_effect = lambda model, _provider_id: model
    ai_repository.get_provider.return_value = {"vendor": "MiniMax", "billing_mode": "subscription_fixed"}
    ai_repository.invocation_billing.return_value = {}
    ai_repository.invocation_cost.return_value = None
    gateway = Mock()
    gateway.generate = AsyncMock(
        return_value=_gateway_response(
            '{"search_terms":["WorkBuddy 使用体验","local agent workflow","personal AI desktop"]}'
        )
    )
    tools = Mock()
    tools.supports_quality_queries = True
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=gateway,
        tools=tools,
    )

    snapshot = runtime._route_snapshot({"route_policy": "prefer_subscription"})
    assert snapshot["primary"]["model_record_id"] == "subscription-model"  # type: ignore[index]
    payg_snapshot = runtime._route_snapshot({"route_policy": "prefer_payg"})
    assert payg_snapshot["primary"]["model_record_id"] == "payg-model"  # type: ignore[index]
    assert runtime._route_item(None) is None
    assert runtime._route_item({"role": "fast"}) is None
    assert runtime._plan_keywords("not json, a useful query, not json", "objective") == ["not json", "a useful query"]
    assert runtime._plan_keywords('{"keywords":["objective","new term"]}', "objective") == ["new term"]
    assert runtime._quality_expansion_term(["AI", "WorkBuddy"]) == "WorkBuddy"
    assert runtime._quality_expansion_term(["AI", "agent"]) is None

    task = repository.get_for_runtime(task_id) or task_record
    asyncio.run(runtime._plan(task))
    repository.set_cost_enabled(task_id, False)
    assert ai_repository.get_model.call_count >= 3
    assert repository.get_for_runtime(task_id)["status"] == "Researching"  # type: ignore[index]
    assert repository.get_for_runtime(task_id)["plan"]["derived_keywords"]  # type: ignore[index]


def test_production_quality_gate_persists_cross_platform_query_chain(
    tmp_path: Path,
    test_settings,
) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(
        database,
        owner_id,
        platforms=["bili"],
        coverage={
            "target_platform_count": 1,
            "target_entity_count": 2,
            "target_negative_evidence_count": 1,
            "max_single_entity_evidence_ratio": 0.6,
            "target_independent_evidence_count": 2,
            "target_new_content_count": 2,
        },
    )
    task_id = str(task["id"])
    repository.save_plan(
        task_id,
        plan={
            "initial_query": "WorkBuddy",
            "derived_keywords": ["WorkBuddy 使用体验", "local agent workflow"],
        },
        route_snapshot={"primary": {"model_record_id": "model-1"}},
        round_number=1,
    )
    repository.transition(task_id, status="Researching", reason="test", step="research_round")

    ai_repository = Mock()
    ai_repository.get_provider.return_value = {"vendor": "MiniMax", "billing_mode": "subscription_fixed"}
    ai_repository.invocation_billing.return_value = {}
    ai_repository.invocation_cost.return_value = None
    gateway = Mock()

    async def score(request: ModelRequest, **_kwargs: object) -> GatewayResponse:
        payload = json.loads(request.messages[0].content)
        count = len(payload["candidates"])
        return _gateway_response(json.dumps({"relevance_scores": [0.9] * count}))

    gateway.generate = score
    tools = ResearchToolService(
        settings=test_settings,
        library_tools=Mock(),
        crawler=Mock(),
        research=repository,
    )
    runtime = ResearchRuntime(
        research=repository,
        ai_repository=ai_repository,
        gateway=gateway,
        tools=tools,
    )
    current = repository.get_for_runtime(task_id, detail=True)
    assert current is not None
    prepared = asyncio.run(
        runtime._prepare_quality_query(
            current,
            round_number=1,
            context={},
            plan=current["plan"],  # type: ignore[arg-type]
            crawl_count=0,
        )
    )
    assert prepared is not None
    detail = repository.get_for_runtime(task_id, detail=True)
    assert detail is not None
    assert any(item["lifecycle_status"] == "executing" for item in detail["queries"])
    assert any(item["lifecycle_status"] == "rejected_generic" for item in detail["queries"])

    candidate = next(item for item in detail["queries"] if item["lifecycle_status"] == "executing")
    async def low_score(_request: ModelRequest, **_kwargs: object) -> GatewayResponse:
        return _gateway_response('{"relevance_scores":[0.1]}')

    gateway.generate = low_score
    rejected = asyncio.run(runtime._score_quality_candidates(current, [candidate]))
    assert rejected == []
    refreshed = repository.get_query(str(candidate["id"]))
    assert refreshed["lifecycle_status"] == "rejected_low_relevance"


def test_runtime_recovers_sqlite_lock_and_tracks_full_content_loading() -> None:
    task = {
        "id": "research-1",
        "status": "Researching",
        "paused": False,
        "current_round": 1,
    }
    research = Mock()
    research.claim_next.return_value = task
    research.waiting_crawls.return_value = []
    runtime = ResearchRuntime(
        research=research,
        ai_repository=Mock(),
        gateway=Mock(),
        tools=Mock(),
    )
    runtime._tick = AsyncMock(side_effect=sqlite3.OperationalError("database is locked"))
    assert asyncio.run(runtime.run_once()) is True
    assert runtime._wake.is_set() is True

    research.get_for_runtime.return_value = {"context": {"compaction_stats": {}}}
    research.append_trace.reset_mock()
    runtime.tools.execute = AsyncMock(return_value={"id": "content-1"})
    result = asyncio.run(runtime._execute_tool(task, "get_content", {"content_id": "content-1"}))
    assert result["id"] == "content-1"
    updated_context = research.update_context.call_args.args[1]
    assert updated_context["full_content_ids"] == ["content-1"]
    assert updated_context["compaction_stats"]["loaded_full_content_count"] == 1


def test_gateway_capability_and_price_edges() -> None:
    repository = Mock()
    cipher = Mock()
    gateway = ModelGateway(repository=repository, secret_cipher=cipher)
    request = ModelRequest(messages=[ModelMessage(role="user", content="x")], max_tokens=10)
    with pytest.raises(RuntimeError, match="output limit"):
        gateway._validate_request({"max_output_tokens": 5, "supports_streaming": True, "supports_tools": True}, request)
    with pytest.raises(RuntimeError, match="streaming"):
        gateway._validate_request({"supports_streaming": False, "supports_tools": True}, request.model_copy(update={"stream": True}))
    with pytest.raises(RuntimeError, match="tool"):
        gateway._validate_request(
            {"supports_streaming": True, "supports_tools": False},
            request.model_copy(
                update={
                    "tools": [
                        ModelToolDefinition(
                            name="status",
                            description="status",
                            input_schema={"type": "object"},
                        )
                    ]
                }
            ),
        )
    assert gateway._fallback_compatible(request, {"supports_tools": True, "supports_streaming": True}) is True
    assert gateway._fallback_compatible(request.model_copy(update={"stream": True}), {"supports_streaming": False}) is False
    assert gateway._cost({}, None) == (None, None, None)
    assert gateway._cost({"input_price_per_million": "1", "output_price_per_million": "2"}, ModelUsage(input_tokens=None, output_tokens=1)) == (None, None, None)
    assert gateway._cost({"input_price_per_million": "1", "output_price_per_million": "2", "price_currency": "USD", "price_effective_at": "now"}, ModelUsage(input_tokens=10, output_tokens=2, cached_tokens=1)) == (None, None, None)
    assert asyncio.run(gateway._default_retry_delay(1)) is None

    repository.get_provider_secret.return_value = None
    with pytest.raises(ProviderError, match="credentials"):
        gateway._provider({"id": "provider-1"})
    repository.get_provider.return_value = None
    with pytest.raises(KeyError, match="Provider not found"):
        gateway.provider_adapter("missing")
    repository.get_provider.return_value = {"id": "provider-1", "enabled": False}
    with pytest.raises(RuntimeError, match="disabled"):
        gateway.provider_adapter("provider-1")


def test_research_tool_argument_and_quality_gate_edges(tmp_path: Path, test_settings) -> None:
    database, owner_id = setup_database(tmp_path)
    repository = ResearchTaskRepository(database)
    task = create_task(database, owner_id)
    task["context"] = {"quality_gate_required": True}
    library = Mock()
    tools = ResearchToolService(
        settings=test_settings,
        library_tools=library,
        crawler=Mock(),
        research=repository,
    )
    with pytest.raises(ResearchTaskConflict, match="quality gate"):
        asyncio.run(tools.execute(task=task, tool_name="search_library", arguments={"query": "WorkBuddy"}))
    with pytest.raises(ResearchTaskConflict, match="duplicates"):
        tools._strings({"ids": ["a", "a"]}, "ids")
    with pytest.raises(ResearchTaskConflict, match="invalid"):
        tools._string({"value": "\n"}, "value")
    assert extract_entities([{"title": "WorkBuddy AI", "description": "agent workflow"}])[:2] == ["agent", "workbuddy"]
