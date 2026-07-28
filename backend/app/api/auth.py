from datetime import UTC
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from app.models.auth import (
    ApiKeySummary,
    CreateApiKeyRequest,
    CreatedApiKey,
    LoginRequest,
    LoginResponse,
    SessionStatus,
    SessionSummary,
)
from app.repositories.auth import AuthRepository
from app.security.dependencies import (
    SESSION_COOKIE_NAME,
    AuthContext,
    require_owner_session,
    validate_request_origin,
)
from app.services.auth import (
    AuthService,
    InvalidCredentialsError,
    LoginRateLimitedError,
)

router = APIRouter(prefix="/auth", tags=["authentication"])
OwnerSession = Annotated[AuthContext, Depends(require_owner_session)]


def _summary(record: dict[str, object]) -> dict[str, object]:
    return {
        "id": str(record["id"]),
        "name": str(record["name"]),
        "prefix": str(record["key_prefix"]),
        "scopes": record["scopes"],
        "created_at": str(record["created_at"]),
        "last_used_at": record["last_used_at"],
        "expires_at": record["expires_at"],
        "revoked_at": record["revoked_at"],
    }


@router.post("/login", response_model=LoginResponse)
def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
) -> dict[str, object]:
    validate_request_origin(request)
    service: AuthService = request.app.state.auth_service
    try:
        created = service.authenticate_password(
            username=payload.username,
            password=payload.password,
        )
    except InvalidCredentialsError as error:
        raise HTTPException(
            status_code=401,
            detail="Invalid username or password",
        ) from error
    except LoginRateLimitedError as error:
        raise HTTPException(
            status_code=429,
            detail="Too many login attempts",
            headers={"Retry-After": str(error.retry_after_seconds)},
        ) from error
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=created.token,
        max_age=request.app.state.settings.session_lifetime_seconds,
        expires=created.expires_at,
        path="/",
        secure=request.app.state.settings.secure_session_cookie,
        httponly=True,
        samesite="strict",
    )
    return {
        "user": {
            "id": str(created.record["user_id"]),
            "username": str(created.record["username"]),
        },
        "csrf_token": created.csrf_token,
        "expires_at": created.expires_at,
    }


@router.get("/session", response_model=SessionStatus)
def session_status(request: Request) -> dict[str, object]:
    service: AuthService = request.app.state.auth_service
    session = service.authenticate_session(request.cookies.get(SESSION_COOKIE_NAME))
    if session is None:
        return {"authenticated": False, "user": None, "csrf_token": None}
    csrf_token = service.rotate_csrf(str(session["id"]))
    return {
        "authenticated": True,
        "user": {
            "id": str(session["user_id"]),
            "username": str(session["username"]),
        },
        "csrf_token": csrf_token,
    }


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    response: Response,
    owner: OwnerSession,
) -> None:
    request.app.state.auth_repository.revoke_session(str(owner.session_id))
    response.delete_cookie(
        SESSION_COOKIE_NAME,
        path="/",
        secure=request.app.state.settings.secure_session_cookie,
        httponly=True,
        samesite="strict",
    )


@router.get("/sessions", response_model=list[SessionSummary])
def list_sessions(
    request: Request,
    owner: OwnerSession,
) -> list[dict[str, object]]:
    return [
        {
            **record,
            "current": str(record["id"]) == owner.session_id,
        }
        for record in request.app.state.auth_repository.list_sessions(
            owner.user_id
        )
    ]


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: str,
    request: Request,
    owner: OwnerSession,
) -> None:
    revoked = request.app.state.auth_repository.revoke_user_session(
        session_id=session_id,
        user_id=owner.user_id,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="Session not found")


@router.get("/api-keys", response_model=list[ApiKeySummary])
def list_api_keys(
    request: Request,
    owner: OwnerSession,
) -> list[dict[str, object]]:
    repository: AuthRepository = request.app.state.auth_repository
    return [_summary(item) for item in repository.list_api_keys(owner.user_id)]


@router.post("/api-keys", response_model=CreatedApiKey, status_code=201)
def create_api_key(
    payload: CreateApiKeyRequest,
    request: Request,
    owner: OwnerSession,
) -> dict[str, object]:
    expires_at = (
        payload.expires_at.astimezone(UTC).isoformat().replace("+00:00", "Z")
        if payload.expires_at is not None
        else None
    )
    full_key, record = request.app.state.auth_service.create_api_key(
        user_id=owner.user_id,
        name=payload.name,
        scopes=payload.scopes,
        expires_at=expires_at,
    )
    return {"api_key": full_key, "key": _summary(record)}


@router.delete("/api-keys/{key_id}", status_code=204)
def revoke_api_key(
    key_id: str,
    request: Request,
    owner: OwnerSession,
) -> None:
    revoked = request.app.state.auth_repository.revoke_api_key(
        key_id=key_id,
        user_id=owner.user_id,
    )
    if not revoked:
        raise HTTPException(status_code=404, detail="API key not found")
