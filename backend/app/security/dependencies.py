from collections.abc import Callable
from dataclasses import dataclass
from typing import Annotated, Literal
from urllib.parse import urlsplit

from fastapi import Depends, HTTPException, Request
from fastapi.security import APIKeyHeader

from app.services.auth import AuthService

SESSION_COOKIE_NAME = "mediaops_session"
CSRF_HEADER_NAME = "X-CSRF-Token"
UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
api_key_header = APIKeyHeader(
    name="X-API-Key",
    scheme_name="MediaOpsApiKey",
    description="Scoped Personal Media Ops API key. The full key is shown once.",
    auto_error=False,
)


@dataclass(frozen=True)
class AuthContext:
    user_id: str
    username: str
    auth_type: Literal["session", "api_key"]
    scopes: frozenset[str]
    session_id: str | None = None
    session_record: dict[str, object] | None = None
    api_key_id: str | None = None


def get_auth_service(request: Request) -> AuthService:
    return request.app.state.auth_service


def _request_origin(request: Request) -> str:
    return f"{request.url.scheme}://{request.url.netloc}"


def validate_request_origin(request: Request) -> None:
    origin = request.headers.get("origin")
    if origin is None:
        referer = request.headers.get("referer")
        if referer:
            parts = urlsplit(referer)
            origin = f"{parts.scheme}://{parts.netloc}"
    allowed = {_request_origin(request), *request.app.state.settings.frontend_origins}
    if origin not in allowed:
        raise HTTPException(status_code=403, detail="Request origin is not allowed")


def authenticate_request(
    request: Request,
    service: Annotated[AuthService, Depends(get_auth_service)],
    external_key: Annotated[str | None, Depends(api_key_header)] = None,
) -> AuthContext:
    if external_key:
        key = service.authenticate_api_key(external_key)
        if key is None:
            raise HTTPException(status_code=401, detail="Authentication required")
        return AuthContext(
            user_id=str(key["user_id"]),
            username=str(key["username"]),
            auth_type="api_key",
            scopes=frozenset(str(scope) for scope in key["scopes"]),
            api_key_id=str(key["id"]),
        )

    session = service.authenticate_session(request.cookies.get(SESSION_COOKIE_NAME))
    if session is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    context = AuthContext(
        user_id=str(session["user_id"]),
        username=str(session["username"]),
        auth_type="session",
        scopes=frozenset({"admin"}),
        session_id=str(session["id"]),
        session_record=session,
    )
    if request.method in UNSAFE_METHODS:
        validate_request_origin(request)
        if not service.validate_csrf(
            session,
            request.headers.get(CSRF_HEADER_NAME),
        ):
            raise HTTPException(status_code=403, detail="CSRF validation failed")
    return context


def require_scopes(*required_scopes: str) -> Callable[..., AuthContext]:
    def dependency(
        context: Annotated[AuthContext, Depends(authenticate_request)],
    ) -> AuthContext:
        if (
            context.auth_type == "api_key"
            and "admin" not in context.scopes
            and not set(required_scopes).issubset(context.scopes)
        ):
            raise HTTPException(status_code=403, detail="Insufficient API key scope")
        return context

    return dependency


def require_owner_session(
    context: Annotated[AuthContext, Depends(authenticate_request)],
) -> AuthContext:
    if context.auth_type != "session":
        raise HTTPException(status_code=403, detail="Owner session required")
    return context
