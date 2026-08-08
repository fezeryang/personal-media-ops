from __future__ import annotations

import asyncio
import json
import sqlite3
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.crawler.registry import (
    ModeDisabledError,
    PlatformDisabledError,
    UnsupportedPlatformError,
    platform_registry,
)
from app.models.discovery import (
    DiscoveryAddToSpaceRequest,
    DiscoveryCandidateDetail,
    DiscoveryContinueRequest,
    DiscoveryFeedbackRequest,
    DiscoveryInboxItem,
    ResearchPreferences,
    ResearchSpaceCreate,
    ResearchSpaceDetail,
    ResearchSpaceItem,
    ResearchSpaceItemCreate,
    ResearchSpaceItemLookup,
    ResearchSpaceSummary,
    ResearchSpaceItemType,
)
from app.models.research import (
    ResearchAction,
    ResearchIntentRevisionRequest,
    ResearchTaskControl,
    ResearchTaskCreate,
    ResearchTaskDetail,
    ResearchTaskSummary,
)
from app.repositories.discovery import (
    DiscoveryConflict,
    DiscoveryNotFound,
    DiscoveryRepository,
)
from app.repositories.research import (
    ResearchTaskConflict,
    ResearchTaskNotFound,
    ResearchTaskRepository,
)
from app.security.dependencies import AuthContext, require_owner_session
from app.services.ai.discovery import DiscoveryEngine
from app.services.ai.intent_interpreter import build_default_intent
from app.services.ai.research_quality import (
    classify_query,
    noise_risk_score,
    normalize_query,
    specificity_score,
)
from app.services.ai.research_rendering import render_research_markdown

router = APIRouter(prefix="/research", tags=["research-runtime"])
OwnerSession = Annotated[AuthContext, Depends(require_owner_session)]


def _repository(request: Request) -> ResearchTaskRepository:
    return request.app.state.research_repository


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _discovery(request: Request) -> DiscoveryRepository:
    return request.app.state.discovery_repository


def _discovery_engine(request: Request) -> DiscoveryEngine:
    return request.app.state.discovery_engine


def _result_with_formats(value: object) -> object:
    if not isinstance(value, dict):
        return value
    markdown = value.get("summary_markdown")
    if not isinstance(markdown, str):
        legacy_summary = value.get("summary")
        if not isinstance(legacy_summary, str):
            return value
        markdown = legacy_summary
    normalized = dict(value)
    normalized["summary"] = markdown
    normalized["summary_markdown"] = markdown
    normalized["summary_html"] = render_research_markdown(markdown)
    return normalized


def _validated_platforms(
    requested: list[str] | None,
    settings: Settings,
) -> list[str]:
    platforms = requested or platform_registry.enabled_platforms_for_mode(
        "search",
        settings.enabled_platforms,
    )
    if not platforms:
        raise ResearchTaskConflict("no enabled crawler platform supports search")
    for platform in platforms:
        try:
            platform_registry.require_mode_enabled(
                platform,
                "search",
                settings.enabled_platforms,
            )
        except (ModeDisabledError, PlatformDisabledError, UnsupportedPlatformError) as error:
            raise ResearchTaskConflict(str(error)) from error
    return platforms


def _consumption(task: dict[str, object]) -> dict[str, object]:
    billing = task.get("billing_summary")
    billing = billing if isinstance(billing, dict) else {}
    subscription = billing.get("subscription_fixed")
    subscription = subscription if isinstance(subscription, dict) else {}
    payg = billing.get("pay_as_you_go")
    payg = payg if isinstance(payg, dict) else {}
    relay = billing.get("relay")
    relay = relay if isinstance(relay, dict) else {}
    return {
        "crawl_count": task["consumed_crawl_count"],
        "content_count": task["consumed_content_count"],
        "duration_seconds": task["consumed_duration_seconds"],
        "input_tokens": task["input_tokens"],
        "output_tokens": task["output_tokens"],
        "cached_tokens": task["cached_tokens"],
        "estimated_cost": task.get("estimated_cost"),
        "cost_enabled": task["budget_cost_enabled"],
        "cost_currency": task.get("budget_cost_currency") or task.get("budget_currency"),
        "model_call_count": task.get("consumed_model_call_count", 0),
        "subscription_calls": subscription.get("calls", 0),
        "subscription_tokens": subscription.get("tokens", 0),
        "payg_calls": payg.get("calls", 0),
        "payg_tokens": payg.get("tokens", 0),
        "relay_calls": relay.get("calls", 0),
        "relay_tokens": relay.get("tokens", 0),
        "uncosted_call_count": sum(
            int(item.get("uncosted_calls", 0))
            for item in billing.values()
            if isinstance(item, dict)
        ),
    }


def _summary(task: dict[str, object]) -> dict[str, object]:
    intent = task.get("intent_contract")
    intent = intent if isinstance(intent, dict) else {}
    return {
        "id": task["id"],
        "task_type": task["task_type"],
        "objective": task["objective"],
        "platforms": task["platforms"],
        "status": task["status"],
        "current_round": task["current_round"],
        "current_step": task.get("current_step"),
        "paused": task["paused"],
        "consumption": _consumption(task),
        "finding_count": task.get("finding_count", 0),
        "event_count": task.get("event_count", 0),
        "action_count": task.get("action_count", 0),
        "created_at": task["created_at"],
        "updated_at": task["updated_at"],
        "finished_at": task.get("finished_at"),
        "failure_reason": task.get("failure_reason"),
        "stop_reason": task.get("stop_reason"),
        "primary_intent": intent.get("primary_intent"),
        "intent_confidence": intent.get("confidence"),
    }


def _detail(task: dict[str, object]) -> dict[str, object]:
    budget = {
        "crawl_limit": task["budget_crawl_limit"],
        "content_limit": task["budget_content_limit"],
        "duration_seconds": task["budget_duration_seconds"],
        "token_limit": task["budget_token_limit"],
        "cost_limit": task.get("budget_cost_limit"),
        "cost_currency": task.get("budget_cost_currency"),
        "max_input_tokens": task.get("budget_max_input_tokens"),
        "max_output_tokens": task.get("budget_max_output_tokens"),
        "max_model_calls": task.get("budget_max_model_calls", 100),
        "route_policy": task.get("route_policy", "balanced"),
        "max_total_tokens": task.get("budget_max_total_tokens", task.get("budget_token_limit")),
        "max_crawl_tasks": task.get("budget_max_crawl_tasks", task.get("budget_crawl_limit")),
        "max_new_contents": task.get("budget_max_new_contents", task.get("budget_content_limit")),
        "max_runtime_seconds": task.get("budget_max_runtime_seconds", task.get("budget_duration_seconds")),
        "max_payg_amount": task.get("budget_max_payg_amount"),
        "currency": task.get("budget_currency", task.get("budget_cost_currency")),
    }
    return {
        **_summary(task),
        "plan": task.get("plan", {}),
        "context": task.get("context", {}),
        "result": _result_with_formats(task.get("result")),
        "route_snapshot": task.get("route_snapshot", {}),
        "budget": budget,
        "coverage": task.get("coverage", {}),
        "platform_coverage": task.get("platform_coverage", []),
        "entity_coverage": task.get("entity_coverage", []),
        "content_decisions": task.get("content_decisions", []),
        "step_usage": task.get("step_usage", []),
        "budget_events": task.get("budget_events", []),
        "trace": task.get("execution_trace", []),
        "findings": task.get("findings", []),
        "queries": task.get("queries", []),
        "events": task.get("events", []),
        "actions": task.get("proposed_actions", []),
        "intent_contract": task.get("intent_contract"),
        "intent_versions": task.get("intent_versions", []),
        "intent_assumptions": task.get("intent_assumptions", []),
        "unknowns": task.get("unknowns", []),
        "alignment_review": task.get("alignment_review"),
        "information_utilities": task.get("information_utilities", []),
        "entity_candidates": task.get("entity_candidates", []),
        "event_candidates": task.get("event_candidates", []),
        "memory_items": task.get("memory_items", []),
        "discovery_candidates": task.get("discovery_candidates", []),
        "discovery_seeds": task.get("discovery_seeds", []),
        "research_plan": task.get("plan", {}),
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Research task not found")


def _conflict(error: Exception) -> HTTPException:
    if isinstance(error, ResearchTaskNotFound):
        return _not_found()
    if isinstance(error, DiscoveryNotFound):
        return HTTPException(status_code=404, detail="Discovery resource not found")
    if isinstance(error, ResearchTaskConflict):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, DiscoveryConflict):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="Research runtime operation failed")


@router.get("/tasks", response_model=list[ResearchTaskSummary])
def list_tasks(request: Request, auth: OwnerSession) -> list[dict[str, object]]:
    return [_summary(item) for item in _repository(request).list(user_id=auth.user_id)]


@router.post("/tasks", response_model=ResearchTaskDetail, status_code=201)
def create_task(
    payload: ResearchTaskCreate,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        platforms = _validated_platforms(payload.platforms, _settings(request))
        task = _repository(request).create(
            user_id=auth.user_id,
            objective=payload.objective,
            platforms=platforms,
            crawl_limit=payload.budget.crawl_limit,
            content_limit=payload.budget.content_limit,
            duration_seconds=payload.budget.duration_seconds,
            token_limit=payload.budget.token_limit,
            cost_limit=payload.budget.cost_limit,
            cost_currency=payload.budget.cost_currency,
            coverage=payload.coverage.model_dump(),
            max_input_tokens=payload.budget.max_input_tokens,
            max_output_tokens=payload.budget.max_output_tokens,
            max_model_calls=payload.budget.max_model_calls,
            route_policy=payload.budget.route_policy,
            max_total_tokens=payload.budget.max_total_tokens,
            max_crawl_tasks=payload.budget.max_crawl_tasks,
            max_new_contents=payload.budget.max_new_contents,
            max_runtime_seconds=payload.budget.max_runtime_seconds,
            max_payg_amount=payload.budget.max_payg_amount,
            budget_currency=payload.budget.currency,
        )
        # The understanding card is available immediately with a bounded
        # deterministic interpretation.  The Runtime may later replace it
        # with the configured model's structured interpretation, but creation
        # never waits on or depends on a provider.
        initial_intent = build_default_intent(payload.objective, platforms)
        _repository(request).save_intent(
            str(task["id"]),
            initial_intent.model_dump(mode="json"),
            change_reason="initial_understanding_card",
        )
        intent = _repository(request).get_intent(str(task["id"]))
        normalized_goal = normalize_query(payload.objective)
        _repository(request).create_query(
            task_id=str(task["id"]),
            intent_id=str(intent["id"]),
            record_type="user_goal",
            gate_status="not_applicable",
            decision="allow",
            query_role="seed_discovery",
            query=payload.objective,
            normalized_query=normalized_goal,
            query_type=classify_query(normalized_goal),
            platform=platforms[0],
            source_type="user_goal",
            source_content_id=None,
            source_finding_id=None,
            parent_query_id=None,
            generation_reason="原始用户目标仅用于 Intent Interpreter，不提交平台搜索",
            specificity_score=specificity_score(normalized_goal),
            novelty_score=1.0,
            noise_risk_score=noise_risk_score(normalized_goal),
            status="candidate",
            expected_evidence_role="background",
        )
        refreshed = _repository(request).get(
            user_id=auth.user_id,
            task_id=str(task["id"]),
            detail=True,
        )
        if refreshed is not None:
            task = refreshed
    except Exception as error:
        raise _conflict(error) from error
    request.app.state.research_runtime.wake()
    return _detail(task)


def _create_follow_up_task(
    *,
    request: Request,
    auth: AuthContext,
    objective: str,
    platforms: list[str],
    candidate: dict[str, object],
) -> dict[str, object]:
    repository = _repository(request)
    settings = _settings(request)
    selected_platforms = _validated_platforms(platforms or None, settings)
    defaults = ResearchTaskCreate(objective=objective, platforms=selected_platforms)
    task = repository.create(
        user_id=auth.user_id,
        objective=defaults.objective,
        platforms=selected_platforms,
        crawl_limit=defaults.budget.crawl_limit,
        content_limit=defaults.budget.content_limit,
        duration_seconds=defaults.budget.duration_seconds,
        token_limit=defaults.budget.token_limit,
        cost_limit=defaults.budget.cost_limit,
        cost_currency=defaults.budget.cost_currency,
        coverage=defaults.coverage.model_dump(),
        max_input_tokens=defaults.budget.max_input_tokens,
        max_output_tokens=defaults.budget.max_output_tokens,
        max_model_calls=defaults.budget.max_model_calls,
        route_policy=defaults.budget.route_policy,
        max_total_tokens=defaults.budget.max_total_tokens,
        max_crawl_tasks=defaults.budget.max_crawl_tasks,
        max_new_contents=defaults.budget.max_new_contents,
        max_runtime_seconds=defaults.budget.max_runtime_seconds,
        max_payg_amount=defaults.budget.max_payg_amount,
        budget_currency=defaults.budget.currency,
    )
    task_id = str(task["id"])
    intent = build_default_intent(objective, selected_platforms)
    repository.save_intent(task_id, intent.model_dump(mode="json"), change_reason="discovery_follow_up")
    normalized_goal = normalize_query(objective)
    saved_intent = repository.get_intent(task_id)
    repository.create_query(
        task_id=task_id,
        intent_id=str(saved_intent["id"]),
        record_type="user_goal",
        gate_status="not_applicable",
        decision="allow",
        query_role="seed_discovery",
        query=objective,
        normalized_query=normalized_goal,
        query_type=classify_query(normalized_goal),
        platform=selected_platforms[0],
        source_type="user_goal",
        source_content_id=str(candidate["source_content_id"]) if candidate.get("source_content_id") else None,
        source_finding_id=None,
        parent_query_id=None,
        generation_reason="基于用户确认的 Discovery Candidate 创建独立后续研究",
        specificity_score=specificity_score(normalized_goal),
        novelty_score=1.0,
        noise_risk_score=noise_risk_score(normalized_goal),
        status="candidate",
        expected_evidence_role="background",
    )
    detail = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
    if detail is None:
        raise ResearchTaskNotFound(task_id)
    context = detail.get("context") if isinstance(detail.get("context"), dict) else {}
    source_ids = [
        str(item.get("content_id"))
        for item in candidate.get("sources", [])
        if isinstance(item, dict) and item.get("content_id")
    ]
    context.update(
        {
            "discovery_parent_candidate_id": str(candidate["id"]),
            "discovery_source_task_id": str(candidate.get("research_task_id") or "") or None,
            "discovery_source_seed_id": str(candidate.get("source_seed_id") or "") or None,
            "discovery_source_candidate_type": str(candidate.get("candidate_type") or ""),
            "discovery_source_normalized_key": str(candidate.get("normalized_key") or ""),
            "discovery_source_content_ids": list(dict.fromkeys(source_ids))[:20],
            "discovery_source_summary": str(candidate.get("summary") or "")[:1_000],
        }
    )
    repository.update_context(task_id, context, step="discovery_follow_up", round_number=0)
    refreshed = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
    if refreshed is None:
        raise ResearchTaskNotFound(task_id)
    return refreshed


@router.get("/tasks/{task_id}", response_model=ResearchTaskDetail)
def get_task(
    task_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    task = _repository(request).get(user_id=auth.user_id, task_id=task_id, detail=True)
    if task is None:
        raise _not_found()
    return _detail(task)


@router.post("/tasks/{task_id}/intent/revise", response_model=ResearchTaskDetail)
def revise_intent(
    task_id: str,
    payload: ResearchIntentRevisionRequest,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    repository = _repository(request)
    task = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
    if task is None:
        raise _not_found()
    if task.get("status") != "Draft":
        raise _conflict(ResearchTaskConflict("研究已开始，不能静默修改原始意图；请创建新的研究分支"))
    try:
        current = repository.get_intent(task_id)
        revised = build_default_intent(
            payload.request,
            [
                str(platform)
                for platform in task.get("platforms", [])
                if isinstance(platform, str)
            ],
        ).model_dump(mode="json")
        revisions = current.get("intent_revisions")
        revisions = list(revisions) if isinstance(revisions, list) else []
        revisions.append(
            {
                "from_version": current.get("version"),
                "request": payload.request,
                "reason": "owner_revised_before_start",
                "created_at": revised.get("created_at"),
            }
        )
        revised.update(
            {
                "original_request": current.get("original_request") or task["objective"],
                "original_intent": current.get("original_intent") or task["objective"],
                "intent_revisions": revisions,
                "intent_source": "owner_revised",
                "created_at": current.get("created_at") or revised.get("created_at"),
            }
        )
        repository.save_intent(task_id, revised, change_reason="owner_revised_before_start")
        refreshed = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
        if refreshed is None:
            raise ResearchTaskNotFound(task_id)
    except Exception as error:
        raise _conflict(error) from error
    request.app.state.research_runtime.wake()
    return _detail(refreshed)


def _control(
    action: str,
    task_id: str,
    request: Request,
    auth: AuthContext,
    reason: str | None,
) -> dict[str, object]:
    repository = _repository(request)
    task = repository.get(user_id=auth.user_id, task_id=task_id, detail=False)
    if task is None:
        raise _not_found()
    try:
        updated = repository.control(task_id, action, reason)
    except Exception as error:
        raise _conflict(error) from error
    if action == "cancel" and updated.get("waiting_crawl_task_id"):
        request.app.state.crawler_repository.request_cancel(
            str(updated["waiting_crawl_task_id"])
        )
    request.app.state.research_runtime.wake()
    detail = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
    if detail is None:
        raise _not_found()
    return _detail(detail)


@router.post("/tasks/{task_id}/pause", response_model=ResearchTaskDetail)
def pause_task(
    task_id: str,
    request: Request,
    auth: OwnerSession,
    payload: ResearchTaskControl | None = None,
) -> dict[str, object]:
    return _control("pause", task_id, request, auth, payload.reason if payload else None)


@router.post("/tasks/{task_id}/resume", response_model=ResearchTaskDetail)
def resume_task(
    task_id: str,
    request: Request,
    auth: OwnerSession,
    payload: ResearchTaskControl | None = None,
) -> dict[str, object]:
    return _control("resume", task_id, request, auth, payload.reason if payload else None)


@router.post("/tasks/{task_id}/cancel", response_model=ResearchTaskDetail)
def cancel_task(
    task_id: str,
    request: Request,
    auth: OwnerSession,
    payload: ResearchTaskControl | None = None,
) -> dict[str, object]:
    return _control("cancel", task_id, request, auth, payload.reason if payload else None)


@router.post("/tasks/{task_id}/rerun", response_model=ResearchTaskDetail)
def rerun_task(
    task_id: str,
    request: Request,
    auth: OwnerSession,
    payload: ResearchTaskControl | None = None,
) -> dict[str, object]:
    return _control("rerun", task_id, request, auth, payload.reason if payload else None)


@router.post("/tasks/{task_id}/complete", response_model=ResearchTaskDetail)
def complete_task(
    task_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    repository = _repository(request)
    task = repository.get(user_id=auth.user_id, task_id=task_id, detail=False)
    if task is None:
        raise _not_found()
    try:
        repository.complete_review(task_id)
    except Exception as error:
        raise _conflict(error) from error
    detail = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
    if detail is None:
        raise _not_found()
    return _detail(detail)


@router.post("/tasks/{task_id}/actions/{action_id}/approve", response_model=ResearchAction)
def approve_action(
    task_id: str,
    action_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    return _decide_action(task_id, action_id, "approved", request, auth)


@router.post("/tasks/{task_id}/actions/{action_id}/reject", response_model=ResearchAction)
def reject_action(
    task_id: str,
    action_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    return _decide_action(task_id, action_id, "rejected", request, auth)


def _decide_action(
    task_id: str,
    action_id: str,
    status: str,
    request: Request,
    auth: AuthContext,
) -> dict[str, object]:
    repository = _repository(request)
    if repository.get(user_id=auth.user_id, task_id=task_id, detail=False) is None:
        raise _not_found()
    try:
        return repository.decide_action(task_id, action_id, status)
    except Exception as error:
        raise _conflict(error) from error


@router.get("/discoveries", response_model=list[DiscoveryInboxItem])
def list_discoveries(
    request: Request,
    auth: OwnerSession,
    state: str | None = Query(default=None),
    research_task_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
) -> list[dict[str, object]]:
    candidates = _discovery(request).list_candidates(
        owner_id=auth.user_id,
        state=state,
        research_task_id=research_task_id,
        limit=limit,
        offset=offset,
    )
    normalized_candidates = [dict(item, source_type="discovery") for item in candidates]
    monitoring = request.app.state.monitoring_repository.list_inbox_changes(
        auth.user_id,
        limit=limit,
    )
    if state is not None:
        monitoring = [item for item in monitoring if item.get("state") == state]
    return normalized_candidates + monitoring


@router.get("/discoveries/{candidate_id}", response_model=DiscoveryCandidateDetail)
def get_discovery(
    candidate_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    candidate = _discovery(request).get_candidate(
        owner_id=auth.user_id,
        candidate_id=candidate_id,
        detail=True,
    )
    if candidate is None:
        raise _conflict(DiscoveryNotFound(candidate_id))
    return candidate


def _feedback_state(feedback_type: str) -> str | None:
    return {
        "valuable": "accepted",
        "irrelevant": "ignored",
        "already_known": "ignored",
        "duplicate": "dismissed_duplicate",
        "follow": "deferred",
        "mute_topic": "ignored",
        "deprioritize_similar": "deferred",
        "needs_more_evidence": "deferred",
        "converted_to_research": "converted_to_research",
        "added_to_space": "added_to_space",
    }.get(feedback_type)


@router.post("/discoveries/{candidate_id}/feedback", response_model=DiscoveryCandidateDetail)
def give_discovery_feedback(
    candidate_id: str,
    payload: DiscoveryFeedbackRequest,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    discovery = _discovery(request)
    try:
        if payload.undo_feedback_id:
            revoked = discovery.undo_feedback(
                owner_id=auth.user_id,
                feedback_id=payload.undo_feedback_id,
            )
            if str(revoked.get("candidate_id") or "") != candidate_id:
                raise DiscoveryConflict("feedback does not belong to candidate")
        else:
            if payload.feedback_type is None:
                raise DiscoveryConflict("feedback_type is required unless undo_feedback_id is supplied")
            if payload.scope == "global" and payload.scope_key:
                raise DiscoveryConflict("global feedback must not include scope_key")
            if payload.scope != "global" and not payload.scope_key:
                raise DiscoveryConflict("scoped feedback requires scope_key")
            discovery.record_feedback(
                owner_id=auth.user_id,
                candidate_id=candidate_id,
                feedback_type=payload.feedback_type,
                scope=payload.scope,
                scope_key=payload.scope_key,
                weight=payload.weight,
                reason=payload.reason,
            )
            next_state = _feedback_state(payload.feedback_type)
            if next_state is not None:
                discovery.set_candidate_state(
                    owner_id=auth.user_id,
                    candidate_id=candidate_id,
                    state=next_state,
                    reason=payload.reason or f"用户反馈：{payload.feedback_type}",
                    feedback_type=payload.feedback_type,
                )
        _discovery_engine(request).rescore_after_feedback(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
        )
    except Exception as error:
        raise _conflict(error) from error
    candidate = discovery.get_candidate(
        owner_id=auth.user_id,
        candidate_id=candidate_id,
        detail=True,
    )
    if candidate is None:
        raise _not_found()
    return candidate


@router.post("/discoveries/{candidate_id}/continue", response_model=ResearchTaskDetail)
def continue_discovery(
    candidate_id: str,
    payload: DiscoveryContinueRequest,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    discovery = _discovery(request)
    candidate = discovery.get_candidate(
        owner_id=auth.user_id,
        candidate_id=candidate_id,
        detail=True,
    )
    if candidate is None:
        raise _not_found()
    settings = _settings(request)
    enabled = platform_registry.enabled_platforms_for_mode("search", settings.enabled_platforms)
    source_platforms = [
        str(item.get("platform"))
        for item in candidate.get("sources", [])
        if isinstance(item, dict) and item.get("platform") in enabled
    ]
    platforms = list(dict.fromkeys(source_platforms)) or enabled
    objective = payload.request or f"继续研究：{candidate['title']}"
    try:
        task = _create_follow_up_task(
            request=request,
            auth=auth,
            objective=objective,
            platforms=platforms,
            candidate=candidate,
        )
        discovery.record_feedback(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
            feedback_type="converted_to_research",
            scope="global",
            scope_key=None,
            weight=1,
            reason="用户选择继续研究，已创建独立 Research Task",
            follow_up_task_id=str(task["id"]),
        )
        discovery.set_candidate_state(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
            state="converted_to_research",
            reason=f"独立后续任务 {task['id']} 已创建",
            feedback_type="converted_to_research",
        )
        _discovery_engine(request).rescore_after_feedback(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
        )
    except Exception as error:
        raise _conflict(error) from error
    request.app.state.research_runtime.wake()
    return _detail(task)


@router.post("/discoveries/{candidate_id}/add-to-space", response_model=ResearchSpaceItem)
def add_discovery_to_space(
    candidate_id: str,
    payload: DiscoveryAddToSpaceRequest,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    discovery = _discovery(request)
    try:
        item = discovery.add_space_item(
            owner_id=auth.user_id,
            space_id=payload.space_id,
            item_type="discovery_candidate",
            item_id=candidate_id,
            position=payload.position,
            note=payload.note,
            source_candidate_id=candidate_id,
        )
        discovery.record_feedback(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
            feedback_type="added_to_space",
            scope="research_space",
            scope_key=payload.space_id,
            weight=1,
            reason="用户将候选加入研究空间",
        )
        discovery.set_candidate_state(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
            state="added_to_space",
            reason=f"已加入研究空间 {payload.space_id}",
            feedback_type="added_to_space",
        )
        _discovery_engine(request).rescore_after_feedback(
            owner_id=auth.user_id,
            candidate_id=candidate_id,
        )
    except Exception as error:
        raise _conflict(error) from error
    return item


@router.get("/spaces", response_model=list[ResearchSpaceSummary])
def list_research_spaces(request: Request, auth: OwnerSession) -> list[dict[str, object]]:
    return _discovery(request).list_spaces(owner_id=auth.user_id)


@router.get("/space-items", response_model=list[ResearchSpaceItemLookup])
def list_research_space_items(
    request: Request,
    auth: OwnerSession,
    item_type: ResearchSpaceItemType | None = Query(default=None),
    query: str | None = Query(default=None, max_length=200),
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, object]]:
    return _discovery(request).list_space_item_lookup(
        owner_id=auth.user_id,
        item_type=item_type,
        query=query,
        limit=limit,
    )


@router.post("/spaces", response_model=ResearchSpaceDetail, status_code=201)
def create_research_space(
    payload: ResearchSpaceCreate,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        return _discovery(request).create_space(
            owner_id=auth.user_id,
            name=payload.name,
            description=payload.description,
        )
    except sqlite3.IntegrityError as error:
        raise HTTPException(status_code=409, detail="research space name already exists") from error
    except Exception as error:
        raise _conflict(error) from error


@router.get("/spaces/{space_id}", response_model=ResearchSpaceDetail)
def get_research_space(
    space_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    space = _discovery(request).get_space(owner_id=auth.user_id, space_id=space_id)
    if space is None:
        raise _not_found()
    return space


@router.post("/spaces/{space_id}/items", response_model=ResearchSpaceItem)
def add_research_space_item(
    space_id: str,
    payload: ResearchSpaceItemCreate,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        return _discovery(request).add_space_item(
            owner_id=auth.user_id,
            space_id=space_id,
            item_type=payload.item_type,
            item_id=payload.item_id,
            position=payload.position,
            note=payload.note,
        )
    except Exception as error:
        raise _conflict(error) from error


@router.get("/preferences", response_model=ResearchPreferences)
def research_preferences(request: Request, auth: OwnerSession) -> dict[str, object]:
    settings = _settings(request)
    return {
        "feature_flags": {
            "research_primary_enabled": bool(getattr(settings, "research_primary_enabled", True)),
            "discovery_inbox_enabled": bool(getattr(settings, "discovery_inbox_enabled", True)),
            "legacy_today_visible": bool(getattr(settings, "legacy_today_visible", False)),
            "legacy_trends_visible": bool(getattr(settings, "legacy_trends_visible", False)),
            "legacy_subscriptions_visible": bool(getattr(settings, "legacy_subscriptions_visible", False)),
            "legacy_creator_watch_visible": bool(getattr(settings, "legacy_creator_watch_visible", False)),
            "manual_crawler_primary": bool(getattr(settings, "manual_crawler_primary", False)),
        },
        "rules": _discovery(request).list_preferences(owner_id=auth.user_id),
    }


@router.get("/tasks/{task_id}/events")
async def task_events(
    task_id: str,
    request: Request,
    auth: OwnerSession,
) -> StreamingResponse:
    repository = _repository(request)
    if repository.get(user_id=auth.user_id, task_id=task_id, detail=False) is None:
        raise _not_found()

    async def events() -> AsyncIterator[str]:
        emitted = 0
        for _ in range(120):
            if await request.is_disconnected():
                break
            task = repository.get(user_id=auth.user_id, task_id=task_id, detail=True)
            if task is None:
                break
            trace = task.get("execution_trace", [])
            if isinstance(trace, list):
                for item in trace[emitted:]:
                    emitted += 1
                    yield f"event: trace\ndata: {json.dumps(item, ensure_ascii=False)}\n\n"
            if task.get("status") in {"Done", "Failed", "Cancelled"}:
                yield f"event: complete\ndata: {json.dumps({'status': task['status']}, ensure_ascii=False)}\n\n"
                break
            yield ": heartbeat\n\n"
            await asyncio.sleep(1)

    return StreamingResponse(events(), media_type="text/event-stream")
