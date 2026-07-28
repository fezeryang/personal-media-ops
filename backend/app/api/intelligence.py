from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.intelligence import (
    Brief,
    BriefGenerateRequest,
    BriefSchedule,
    BriefScheduleWrite,
    TrendGenerateRequest,
    TrendSignal,
)
from app.repositories.intelligence import BriefConflictError
from app.security.dependencies import (
    AuthContext,
    require_scopes,
)

router = APIRouter(prefix="/intelligence", tags=["intelligence"])
IntelligenceRead = Annotated[
    AuthContext,
    Depends(require_scopes("intelligence:read")),
]
OwnerWrite = Annotated[
    AuthContext,
    Depends(require_scopes("admin")),
]


@router.get("/trends", response_model=list[TrendSignal])
def list_trends(
    request: Request,
    auth: IntelligenceRead,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 50,
) -> list[dict[str, object]]:
    return request.app.state.intelligence_repository.list_trends(
        offset=offset,
        limit=limit,
    )["items"]


@router.post("/trends/generate", response_model=list[TrendSignal])
def generate_trends(
    payload: TrendGenerateRequest,
    request: Request,
    auth: OwnerWrite,
) -> list[dict[str, object]]:
    return request.app.state.trend_service.generate(
        window_end=payload.window_end,
        window_hours=payload.window_hours,
    )


@router.get("/briefs/latest", response_model=Brief)
def latest_brief(
    request: Request,
    auth: IntelligenceRead,
) -> dict[str, object]:
    brief = request.app.state.intelligence_repository.get_latest_brief(
        user_id=auth.user_id,
    )
    if brief is None:
        raise HTTPException(status_code=404, detail="brief not found")
    return brief


@router.post("/briefs", response_model=Brief, status_code=201)
def generate_brief(
    payload: BriefGenerateRequest,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    try:
        return request.app.state.brief_generator.generate(
            user_id=auth.user_id,
            window_start=payload.window_start.isoformat().replace("+00:00", "Z"),
            window_end=payload.window_end.isoformat().replace("+00:00", "Z"),
            timezone=payload.timezone,
            regenerate=payload.regenerate,
        )
    except BriefConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error


@router.get("/briefs/schedule", response_model=BriefSchedule)
def get_brief_schedule(
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    schedule = request.app.state.intelligence_repository.get_brief_schedule(
        user_id=auth.user_id,
    )
    if schedule is None:
        raise HTTPException(status_code=404, detail="brief schedule not configured")
    return schedule


@router.put("/briefs/schedule", response_model=BriefSchedule)
def set_brief_schedule(
    payload: BriefScheduleWrite,
    request: Request,
    auth: OwnerWrite,
) -> dict[str, object]:
    return request.app.state.intelligence_repository.set_brief_schedule(
        user_id=auth.user_id,
        **payload.model_dump(),
    )
