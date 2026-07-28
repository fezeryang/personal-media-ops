from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request

from app.models.automation import (
    Subscription,
    SubscriptionDetail,
    SubscriptionRun,
    SubscriptionWrite,
)
from app.security.dependencies import AuthContext, require_scopes
from app.services.automation import (
    AutomationCapabilityError,
    AutomationConflictError,
    AutomationCoordinator,
    AutomationNotFoundError,
)

router = APIRouter(prefix="/subscriptions", tags=["subscriptions"])
SubscriptionRead = Annotated[
    AuthContext,
    Depends(require_scopes("subscriptions:read")),
]
SubscriptionWriteAuth = Annotated[
    AuthContext,
    Depends(require_scopes("subscriptions:write")),
]


def _coordinator(request: Request) -> AutomationCoordinator:
    return request.app.state.automation_coordinator


def _payload(payload: SubscriptionWrite) -> dict[str, object]:
    return {
        "name": payload.name,
        "query": payload.query,
        "platforms": [item.model_dump() for item in payload.platforms],
        "enabled": payload.enabled,
        "schedule_type": payload.schedule_type,
        "schedule_config": payload.schedule_config.model_dump(exclude_none=True),
        "timezone": payload.timezone,
    }


def _domain_error(error: RuntimeError) -> HTTPException:
    if isinstance(error, AutomationNotFoundError):
        return HTTPException(status_code=404, detail=str(error))
    if isinstance(error, (AutomationCapabilityError, AutomationConflictError)):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="Automation request failed")


@router.get("", response_model=list[Subscription])
def list_subscriptions(
    request: Request,
    auth: SubscriptionRead,
) -> list[dict[str, object]]:
    return request.app.state.automation_repository.list_subscriptions(auth.user_id)


@router.post("", response_model=Subscription, status_code=201)
def create_subscription(
    payload: SubscriptionWrite,
    request: Request,
    auth: SubscriptionWriteAuth,
) -> dict[str, object]:
    try:
        return _coordinator(request).create_subscription(
            user_id=auth.user_id,
            payload=_payload(payload),
        )
    except RuntimeError as error:
        raise _domain_error(error) from error


@router.get("/{subscription_id}", response_model=SubscriptionDetail)
def get_subscription(
    subscription_id: str,
    request: Request,
    auth: SubscriptionRead,
) -> dict[str, object]:
    subscription = request.app.state.automation_repository.get_subscription(
        subscription_id=subscription_id,
        user_id=auth.user_id,
    )
    if subscription is None:
        raise HTTPException(status_code=404, detail="subscription not found")
    return subscription


@router.put("/{subscription_id}", response_model=Subscription)
def update_subscription(
    subscription_id: str,
    payload: SubscriptionWrite,
    request: Request,
    auth: SubscriptionWriteAuth,
) -> dict[str, object]:
    try:
        return _coordinator(request).update_subscription(
            subscription_id=subscription_id,
            user_id=auth.user_id,
            payload=_payload(payload),
        )
    except RuntimeError as error:
        raise _domain_error(error) from error


@router.post("/{subscription_id}/pause", response_model=Subscription)
def pause_subscription(
    subscription_id: str,
    request: Request,
    auth: SubscriptionWriteAuth,
) -> dict[str, object]:
    try:
        return _coordinator(request).set_subscription_enabled(
            subscription_id=subscription_id,
            user_id=auth.user_id,
            enabled=False,
        )
    except RuntimeError as error:
        raise _domain_error(error) from error


@router.post("/{subscription_id}/resume", response_model=Subscription)
def resume_subscription(
    subscription_id: str,
    request: Request,
    auth: SubscriptionWriteAuth,
) -> dict[str, object]:
    try:
        return _coordinator(request).set_subscription_enabled(
            subscription_id=subscription_id,
            user_id=auth.user_id,
            enabled=True,
        )
    except RuntimeError as error:
        raise _domain_error(error) from error


@router.post(
    "/{subscription_id}/run",
    response_model=SubscriptionRun,
    status_code=202,
)
def run_subscription(
    subscription_id: str,
    request: Request,
    auth: SubscriptionWriteAuth,
) -> dict[str, object]:
    try:
        return _coordinator(request).manual_subscription_run(
            subscription_id=subscription_id,
            user_id=auth.user_id,
        )
    except RuntimeError as error:
        raise _domain_error(error) from error
