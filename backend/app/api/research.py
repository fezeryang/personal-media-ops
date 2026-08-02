from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse

from app.core.config import Settings
from app.crawler.registry import (
    ModeDisabledError,
    PlatformDisabledError,
    UnsupportedPlatformError,
    platform_registry,
)
from app.models.research import (
    ResearchAction,
    ResearchTaskControl,
    ResearchTaskCreate,
    ResearchTaskDetail,
    ResearchTaskSummary,
)
from app.repositories.research import (
    ResearchTaskConflict,
    ResearchTaskNotFound,
    ResearchTaskRepository,
)
from app.security.dependencies import AuthContext, require_owner_session
from app.services.ai.research_rendering import render_research_markdown

router = APIRouter(prefix="/research", tags=["research-runtime"])
OwnerSession = Annotated[AuthContext, Depends(require_owner_session)]


def _repository(request: Request) -> ResearchTaskRepository:
    return request.app.state.research_repository


def _settings(request: Request) -> Settings:
    return request.app.state.settings


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
    return {
        "crawl_count": task["consumed_crawl_count"],
        "content_count": task["consumed_content_count"],
        "duration_seconds": task["consumed_duration_seconds"],
        "input_tokens": task["input_tokens"],
        "output_tokens": task["output_tokens"],
        "cached_tokens": task["cached_tokens"],
        "estimated_cost": task.get("estimated_cost"),
        "cost_enabled": task["budget_cost_enabled"],
        "cost_currency": task.get("budget_cost_currency"),
    }


def _summary(task: dict[str, object]) -> dict[str, object]:
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
    }


def _detail(task: dict[str, object]) -> dict[str, object]:
    budget = {
        "crawl_limit": task["budget_crawl_limit"],
        "content_limit": task["budget_content_limit"],
        "duration_seconds": task["budget_duration_seconds"],
        "token_limit": task["budget_token_limit"],
        "cost_limit": task.get("budget_cost_limit"),
        "cost_currency": task.get("budget_cost_currency"),
    }
    return {
        **_summary(task),
        "plan": task.get("plan", {}),
        "context": task.get("context", {}),
        "result": _result_with_formats(task.get("result")),
        "route_snapshot": task.get("route_snapshot", {}),
        "budget": budget,
        "trace": task.get("execution_trace", []),
        "findings": task.get("findings", []),
        "queries": task.get("queries", []),
        "events": task.get("events", []),
        "actions": task.get("proposed_actions", []),
    }


def _not_found() -> HTTPException:
    return HTTPException(status_code=404, detail="Research task not found")


def _conflict(error: Exception) -> HTTPException:
    if isinstance(error, ResearchTaskNotFound):
        return _not_found()
    if isinstance(error, ResearchTaskConflict):
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
        )
    except Exception as error:
        raise _conflict(error) from error
    request.app.state.research_runtime.wake()
    return _detail(task)


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
