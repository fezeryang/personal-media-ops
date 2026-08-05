from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request

from app.models.monitoring import (
    MonitoringBaseline,
    MonitoringChange,
    MonitoringMissionCreate,
    MonitoringMissionDetail,
    MonitoringMissionPatch,
    MonitoringMissionSummary,
    MonitoringNotification,
    MonitoringRun,
    MonitoringRunResult,
    NotificationAction,
)
from app.repositories.monitoring import MonitoringConflict, MonitoringRepository
from app.security.dependencies import AuthContext, require_owner_session
from app.services.monitoring.service import MonitoringService

router = APIRouter(prefix="/monitoring", tags=["monitoring"])
notifications_router = APIRouter(prefix="/notifications", tags=["notifications"])
OwnerSession = Annotated[AuthContext, Depends(require_owner_session)]


def _repository(request: Request) -> MonitoringRepository:
    return request.app.state.monitoring_repository


def _service(request: Request) -> MonitoringService:
    return request.app.state.monitoring_service


def _error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail="监控任务不存在")
    if isinstance(error, MonitoringConflict):
        return HTTPException(status_code=409, detail=str(error))
    if isinstance(error, ValueError):
        return HTTPException(status_code=422, detail=str(error))
    return HTTPException(status_code=500, detail="监控任务操作失败")


def _mission_or_404(request: Request, owner_id: str, mission_id: str) -> dict[str, object]:
    mission = _repository(request).get_mission(owner_id, mission_id, detail=True)
    if mission is None:
        raise HTTPException(status_code=404, detail="监控任务不存在")
    return mission


@router.get("/missions", response_model=list[MonitoringMissionSummary])
def list_missions(request: Request, auth: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_missions(auth.user_id)


@router.post("/missions", response_model=MonitoringMissionDetail, status_code=201)
def create_mission(
    payload: MonitoringMissionCreate,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        return _service(request).create_mission(
            owner_id=auth.user_id,
            payload=payload.model_dump(mode="json"),
        )
    except Exception as error:
        raise _error(error) from error


@router.get("/missions/{mission_id}", response_model=MonitoringMissionDetail)
def get_mission(
    mission_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    return _mission_or_404(request, auth.user_id, mission_id)


@router.patch("/missions/{mission_id}", response_model=MonitoringMissionDetail)
def update_mission(
    mission_id: str,
    payload: MonitoringMissionPatch,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        _mission_or_404(request, auth.user_id, mission_id)
        values = payload.model_dump(mode="json", exclude_none=True)
        return _repository(request).update_mission(
            owner_id=auth.user_id,
            mission_id=mission_id,
            changes=values,
        ) or _mission_or_404(request, auth.user_id, mission_id)
    except Exception as error:
        raise _error(error) from error


@router.post("/missions/{mission_id}/confirm", response_model=MonitoringMissionDetail)
def confirm_mission(
    mission_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        _mission_or_404(request, auth.user_id, mission_id)
        return _repository(request).set_status(
            owner_id=auth.user_id,
            mission_id=mission_id,
            status="active",
        ) or _mission_or_404(request, auth.user_id, mission_id)
    except Exception as error:
        raise _error(error) from error


@router.post("/missions/{mission_id}/run", response_model=MonitoringRunResult)
def run_mission(
    mission_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object]:
    try:
        result = _service(request).run_once(
            owner_id=auth.user_id,
            mission_id=mission_id,
        )
        if result.get("outcome") == "research_task_queued":
            request.app.state.research_runtime.wake()
        return result
    except Exception as error:
        raise _error(error) from error


def _set_mission_status(
    mission_id: str,
    status: str,
    request: Request,
    auth: AuthContext,
) -> dict[str, object]:
    try:
        _mission_or_404(request, auth.user_id, mission_id)
        return _repository(request).set_status(
            owner_id=auth.user_id,
            mission_id=mission_id,
            status=status,
        ) or _mission_or_404(request, auth.user_id, mission_id)
    except Exception as error:
        raise _error(error) from error


@router.post("/missions/{mission_id}/pause", response_model=MonitoringMissionDetail)
def pause_mission(mission_id: str, request: Request, auth: OwnerSession) -> dict[str, object]:
    return _set_mission_status(mission_id, "paused", request, auth)


@router.post("/missions/{mission_id}/resume", response_model=MonitoringMissionDetail)
def resume_mission(mission_id: str, request: Request, auth: OwnerSession) -> dict[str, object]:
    return _set_mission_status(mission_id, "active", request, auth)


@router.post("/missions/{mission_id}/archive", response_model=MonitoringMissionDetail)
def archive_mission(mission_id: str, request: Request, auth: OwnerSession) -> dict[str, object]:
    return _set_mission_status(mission_id, "archived", request, auth)


@router.get("/missions/{mission_id}/runs", response_model=list[MonitoringRun])
def list_runs(
    mission_id: str,
    request: Request,
    auth: OwnerSession,
    limit: int = Query(default=50, ge=1, le=100),
) -> list[dict[str, object]]:
    _mission_or_404(request, auth.user_id, mission_id)
    return _repository(request).list_runs(auth.user_id, mission_id, limit=limit)


@router.get("/missions/{mission_id}/changes", response_model=list[MonitoringChange])
def list_changes(
    mission_id: str,
    request: Request,
    auth: OwnerSession,
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, object]]:
    _mission_or_404(request, auth.user_id, mission_id)
    return _repository(request).list_changes(auth.user_id, mission_id, limit=limit)


@router.get("/missions/{mission_id}/baseline", response_model=MonitoringBaseline | None)
def get_baseline(
    mission_id: str,
    request: Request,
    auth: OwnerSession,
) -> dict[str, object] | None:
    _mission_or_404(request, auth.user_id, mission_id)
    return _repository(request).latest_baseline(auth.user_id, mission_id)


@notifications_router.get("", response_model=list[MonitoringNotification])
def list_notifications(
    request: Request,
    auth: OwnerSession,
    status: str | None = Query(default=None),
    limit: int = Query(default=100, ge=1, le=200),
) -> list[dict[str, object]]:
    return _repository(request).list_notifications(auth.user_id, status=status, limit=limit)


def _notification_action(
    notification_id: str,
    action: str,
    request: Request,
    auth: AuthContext,
    payload: NotificationAction | None,
) -> dict[str, object]:
    result = _repository(request).update_notification(
        owner_id=auth.user_id,
        notification_id=notification_id,
        action=action,
        until=payload.until if payload is not None else None,
    )
    if result is None:
        raise HTTPException(status_code=404, detail="站内通知不存在")
    return result


@notifications_router.post("/{notification_id}/read", response_model=MonitoringNotification)
def read_notification(
    notification_id: str,
    request: Request,
    auth: OwnerSession,
    payload: NotificationAction | None = None,
) -> dict[str, object]:
    return _notification_action(notification_id, "read", request, auth, payload)


@notifications_router.post("/{notification_id}/defer", response_model=MonitoringNotification)
def defer_notification(
    notification_id: str,
    request: Request,
    auth: OwnerSession,
    payload: NotificationAction | None = None,
) -> dict[str, object]:
    return _notification_action(notification_id, "defer", request, auth, payload)


@notifications_router.post("/{notification_id}/ignore", response_model=MonitoringNotification)
def ignore_notification(
    notification_id: str,
    request: Request,
    auth: OwnerSession,
    payload: NotificationAction | None = None,
) -> dict[str, object]:
    return _notification_action(notification_id, "ignore", request, auth, payload)
