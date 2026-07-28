from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.automation import (
    AutomationEnabledWrite,
    WatchlistItem,
    WatchlistWrite,
    WatchRun,
)
from app.security.dependencies import AuthContext, require_scopes
from app.services.automation import (
    AutomationCapabilityError,
    AutomationConflictError,
    AutomationNotFoundError,
)

router = APIRouter(prefix="/watchlist", tags=["creator-watch"])
WatchRead = Annotated[
    AuthContext,
    Depends(require_scopes("library:read")),
]
WatchWrite = Annotated[
    AuthContext,
    Depends(require_scopes("subscriptions:write")),
]


def _error(error: RuntimeError) -> HTTPException:
    if isinstance(error, AutomationNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (AutomationCapabilityError, AutomationConflictError)):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="Watch request failed")


@router.get("", response_model=list[WatchlistItem])
def list_watchlist(
    request: Request,
    auth: WatchRead,
) -> list[dict[str, object]]:
    return request.app.state.automation_repository.list_watches(auth.user_id)


@router.post("", response_model=WatchlistItem, status_code=201)
def create_watch(
    payload: WatchlistWrite,
    request: Request,
    auth: WatchWrite,
) -> dict[str, object]:
    try:
        return request.app.state.automation_coordinator.create_watch(
            user_id=auth.user_id,
            **payload.model_dump(),
        )
    except RuntimeError as error:
        raise _error(error) from error


@router.post("/{watch_id}/run", response_model=WatchRun, status_code=202)
def run_watch(
    watch_id: str,
    request: Request,
    auth: WatchWrite,
) -> dict[str, object]:
    try:
        return request.app.state.automation_coordinator.manual_watch_run(
            watch_id=watch_id,
            user_id=auth.user_id,
        )
    except RuntimeError as error:
        raise _error(error) from error


@router.patch("/{watch_id}", response_model=WatchlistItem)
def set_watch_enabled(
    watch_id: str,
    payload: AutomationEnabledWrite,
    request: Request,
    auth: WatchWrite,
) -> dict[str, object]:
    try:
        return request.app.state.automation_coordinator.set_watch_enabled(
            watch_id=watch_id,
            user_id=auth.user_id,
            enabled=payload.enabled,
        )
    except RuntimeError as error:
        raise _error(error) from error
