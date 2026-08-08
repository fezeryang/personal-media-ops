from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.crawler.registry import platform_registry
from app.models.opportunity import (
    ActionCreate,
    ActionUpdate,
    OpportunityAction,
    OpportunityAnalysisRequest,
    OpportunityAnalysisResponse,
    OpportunityCreate,
    OpportunityDetail,
    OpportunityFeedback,
    OpportunityFeedbackRequest,
    OpportunitySignal,
    OpportunitySignalCreate,
    OpportunitySummary,
    OutcomeCreate,
    ValidationPlan,
    ValidationPlanCreate,
    ValidationResultCreate,
)
from app.models.research import ResearchBudget
from app.repositories.opportunity import (
    OpportunityConflict,
    OpportunityNotFound,
    OpportunityRepository,
)
from app.security.dependencies import AuthContext, require_owner_session
from app.services.ai.intent_interpreter import build_default_intent
from app.services.ai.opportunity import OpportunityService
from app.services.ai.research_quality import (
    classify_query,
    noise_risk_score,
    normalize_query,
    specificity_score,
)

router = APIRouter(prefix="/opportunities", tags=["opportunity-action"])
actions_router = APIRouter(prefix="/actions", tags=["opportunity-action"])
OwnerSession = Annotated[AuthContext, Depends(require_owner_session)]


def _repository(request: Request) -> OpportunityRepository:
    return request.app.state.opportunity_repository


def _service(request: Request) -> OpportunityService:
    return request.app.state.opportunity_service


def _error(error: Exception) -> HTTPException:
    if isinstance(error, OpportunityNotFound):
        return HTTPException(status_code=404, detail="Opportunity resource not found")
    if isinstance(error, OpportunityConflict):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="Opportunity operation failed")


def _summary(item: dict[str, object]) -> dict[str, object]:
    fields = {
        "id", "opportunity_type", "title", "description", "target_user", "problem",
        "why_attention", "why_now", "next_step", "status", "readiness", "version",
        "scores", "score_explanation", "unknowns", "content_details",
        "related_research_task_id", "related_monitoring_mission_id",
        "related_monitoring_change_id", "related_discovery_candidate_id", "research_space_id",
        "created_at", "updated_at",
    }
    return {key: item.get(key) for key in fields}


def _detail(item: dict[str, object]) -> dict[str, object]:
    return item


def _follow_up_task(
    *,
    request: Request,
    auth: AuthContext,
    opportunity: dict[str, object],
    plan_id: str,
) -> dict[str, object]:
    platforms = [
        str(source.get("source_platform"))
        for source in opportunity.get("sources", [])
        if isinstance(source, dict) and source.get("source_platform")
    ]
    available = platform_registry.enabled_platforms_for_mode("search", request.app.state.settings.enabled_platforms)
    selected = list(dict.fromkeys(platforms + list(available)))[:3]
    if not selected:
        raise OpportunityConflict("no search platform is available for follow-up research")
    budget = ResearchBudget(crawl_limit=3, content_limit=40, max_model_calls=12, token_limit=12_000)
    objective = f"验证机会：{opportunity['title']}。围绕验证计划 {plan_id} 检查关键假设、反向证据和替代方案。"
    research = request.app.state.research_repository
    task = research.create(
        user_id=auth.user_id,
        objective=objective,
        platforms=selected,
        crawl_limit=budget.crawl_limit,
        content_limit=budget.content_limit,
        duration_seconds=budget.duration_seconds,
        token_limit=budget.token_limit,
        cost_limit=budget.cost_limit,
        cost_currency=budget.cost_currency,
        coverage=budget.model_dump(),
        max_input_tokens=budget.max_input_tokens,
        max_output_tokens=budget.max_output_tokens,
        max_model_calls=budget.max_model_calls,
        route_policy=budget.route_policy,
        max_total_tokens=budget.max_total_tokens,
        max_crawl_tasks=budget.max_crawl_tasks,
        max_new_contents=budget.max_new_contents,
        max_runtime_seconds=budget.max_runtime_seconds,
        max_payg_amount=budget.max_payg_amount,
        budget_currency=budget.currency,
    )
    task_id = str(task["id"])
    intent = build_default_intent(objective, selected).model_dump(mode="json")
    intent["primary_intent"] = "opportunity_validation"
    intent["unknowns_to_discover"] = list(opportunity.get("unknowns") or [])
    request.app.state.research_repository.save_intent(task_id, intent, change_reason="opportunity_validation_follow_up")
    normalized = normalize_query(objective)
    saved_intent = request.app.state.research_repository.get_intent(task_id)
    request.app.state.research_repository.create_query(
        task_id=task_id,
        intent_id=str(saved_intent["id"]),
        record_type="user_goal",
        gate_status="not_applicable",
        decision="allow",
        query_role="cross_platform_validation",
        query=objective,
        normalized_query=normalized,
        query_type=classify_query(normalized),
        platform=selected[0],
        source_type="opportunity",
        source_content_id=next((str(source.get("content_id")) for source in opportunity.get("sources", []) if isinstance(source, dict) and source.get("content_id")), None),
        source_finding_id=next((str(source.get("finding_id")) for source in opportunity.get("sources", []) if isinstance(source, dict) and source.get("finding_id")), None),
        parent_query_id=None,
        generation_reason="Owner confirmed Validation Plan; create independent follow-up research",
        specificity_score=specificity_score(normalized),
        novelty_score=1.0,
        noise_risk_score=noise_risk_score(normalized),
        status="candidate",
        expected_evidence_role="direct",
    )
    context = task.get("context") if isinstance(task.get("context"), dict) else {}
    context.update({"opportunity_id": opportunity["id"], "validation_plan_id": plan_id, "opportunity_version": opportunity["version"]})
    request.app.state.research_repository.update_context(task_id, context, step="opportunity_validation_follow_up", round_number=0)
    request.app.state.research_runtime.wake()
    return {"research_task_id": task_id, "status": "created", "opportunity_id": opportunity["id"], "validation_plan_id": plan_id}


@router.get("", response_model=list[OpportunitySummary])
def list_opportunities(
    request: Request,
    auth: OwnerSession,
    limit: int = Query(default=30, ge=1, le=100),
    readiness: str | None = Query(default=None),
    status: str | None = Query(default=None),
) -> list[dict[str, object]]:
    return [_summary(item) for item in _repository(request).list_opportunities(owner_id=auth.user_id, limit=limit, readiness=readiness, status=status)]


@router.post("/signals", response_model=OpportunitySignal, status_code=201)
def create_signal(payload: OpportunitySignalCreate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).create_signal(owner_id=auth.user_id, payload=payload.model_dump(mode="json"))
    except Exception as error:
        raise _error(error) from error


@router.post("/analyze", response_model=OpportunityAnalysisResponse)
def analyze_source(payload: OpportunityAnalysisRequest, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        result = _service(request).analyze_source(owner_id=auth.user_id, source_type=payload.source_type, source_id=payload.source_id, opportunity_type=payload.opportunity_type)
        result["opportunities"] = [_summary(item) for item in result.get("opportunities", []) if isinstance(item, dict)]
        return result
    except Exception as error:
        raise _error(error) from error


@router.post("", response_model=OpportunityDetail, status_code=201)
def create_opportunity(payload: OpportunityCreate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _detail(_service(request).create_explicit(owner_id=auth.user_id, payload=payload.model_dump(mode="json")))
    except Exception as error:
        raise _error(error) from error


@router.get("/{opportunity_id}", response_model=OpportunityDetail)
def get_opportunity(opportunity_id: str, request: Request, auth: OwnerSession) -> dict[str, object]:
    item = _repository(request).get_opportunity(owner_id=auth.user_id, opportunity_id=opportunity_id, detail=True)
    if item is None:
        raise HTTPException(status_code=404, detail="Opportunity not found")
    return _detail(item)


@router.post("/{opportunity_id}/feedback", response_model=OpportunityFeedback, status_code=201)
def feedback(opportunity_id: str, payload: OpportunityFeedbackRequest, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).add_feedback(owner_id=auth.user_id, opportunity_id=opportunity_id, feedback_type=payload.feedback_type, note=payload.note)
    except Exception as error:
        raise _error(error) from error


@router.post("/{opportunity_id}/validation-plan", response_model=ValidationPlan, status_code=201)
def create_validation_plan(opportunity_id: str, payload: ValidationPlanCreate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        opportunity = _repository(request).get_opportunity(owner_id=auth.user_id, opportunity_id=opportunity_id, detail=True)
        if opportunity is None:
            raise OpportunityNotFound(opportunity_id)
        values = _service(request).build_validation_plan(opportunity, payload.model_dump(mode="json", exclude_none=True))
        return _repository(request).create_validation_plan(owner_id=auth.user_id, opportunity_id=opportunity_id, values=values)
    except Exception as error:
        raise _error(error) from error


@router.post("/validation-plans/{plan_id}/approve", response_model=ValidationPlan)
def approve_validation_plan(plan_id: str, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).update_validation_plan_status(owner_id=auth.user_id, plan_id=plan_id, status="ready")
    except Exception as error:
        raise _error(error) from error


@router.post("/validation-plans/{plan_id}/research", response_model=dict[str, object])
def follow_up_research(plan_id: str, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        plan = _repository(request).get_plan(owner_id=auth.user_id, plan_id=plan_id)
        if plan is None:
            raise OpportunityNotFound(plan_id)
        _repository(request).update_validation_plan_status(owner_id=auth.user_id, plan_id=plan_id, status="in_progress")
        opportunity = _repository(request).get_opportunity(owner_id=auth.user_id, opportunity_id=str(plan["opportunity_id"]), detail=True)
        if opportunity is None:
            raise OpportunityNotFound(str(plan["opportunity_id"]))
        return _follow_up_task(request=request, auth=auth, opportunity=opportunity, plan_id=plan_id)
    except Exception as error:
        raise _error(error) from error


@router.post("/validation-plans/{plan_id}/result", response_model=dict[str, object], status_code=201)
def record_validation_result(plan_id: str, payload: ValidationResultCreate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).record_validation_result(owner_id=auth.user_id, plan_id=plan_id, values=payload.model_dump(mode="json"))
    except Exception as error:
        raise _error(error) from error


@router.get("/memory/updates", response_model=list[dict[str, object]])
def list_memory_updates(request: Request, auth: OwnerSession, opportunity_id: str | None = None) -> list[dict[str, object]]:
    return _repository(request).list_memory_updates(owner_id=auth.user_id, opportunity_id=opportunity_id)


@actions_router.get("", response_model=list[OpportunityAction])
def list_actions(request: Request, auth: OwnerSession, limit: int = Query(default=30, ge=1, le=100)) -> list[dict[str, object]]:
    rows = _repository(request).list_opportunities(owner_id=auth.user_id, limit=limit)
    actions: list[dict[str, object]] = []
    for opportunity in rows:
        detail = _repository(request).get_opportunity(owner_id=auth.user_id, opportunity_id=str(opportunity["id"]), detail=True)
        if detail:
            actions.extend(item for item in detail.get("actions", []) if isinstance(item, dict))
    return actions[:limit]


@actions_router.post("", response_model=OpportunityAction, status_code=201)
def create_action(payload: ActionCreate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).create_action(owner_id=auth.user_id, values=payload.model_dump(mode="json"))
    except Exception as error:
        raise _error(error) from error


@actions_router.patch("/{action_id}", response_model=OpportunityAction)
def update_action(action_id: str, payload: ActionUpdate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).update_action(owner_id=auth.user_id, action_id=action_id, status=payload.status, user_notes=payload.user_notes)
    except Exception as error:
        raise _error(error) from error


@actions_router.post("/{action_id}/outcome", response_model=dict[str, object], status_code=201)
def record_outcome(action_id: str, payload: OutcomeCreate, request: Request, auth: OwnerSession) -> dict[str, object]:
    try:
        return _repository(request).record_outcome(owner_id=auth.user_id, action_id=action_id, values=payload.model_dump(mode="json"))
    except Exception as error:
        raise _error(error) from error
