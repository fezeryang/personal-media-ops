import hashlib
import secrets
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from hmac import compare_digest
from typing import Any

from app.core.config import Settings
from app.repositories.auth import AuthRepository
from app.security.passwords import verify_dummy_password, verify_password


class InvalidCredentialsError(RuntimeError):
    pass


class LoginRateLimitedError(RuntimeError):
    def __init__(self, retry_after_seconds: int) -> None:
        super().__init__("Too many login attempts")
        self.retry_after_seconds = max(retry_after_seconds, 1)


class OwnerLimitError(RuntimeError):
    pass


@dataclass(frozen=True)
class CreatedSession:
    token: str
    csrf_token: str
    expires_at: str
    record: dict[str, Any]


@dataclass(frozen=True)
class AuthenticatedApiKey:
    record: dict[str, Any]


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _parse(value: str) -> datetime:
    return datetime.fromisoformat(value).astimezone(UTC)


class AuthService:
    def __init__(self, repository: AuthRepository, settings: Settings) -> None:
        self.repository = repository
        self.settings = settings

    def authenticate_password(
        self,
        *,
        username: str,
        password: str,
    ) -> CreatedSession:
        user = self.repository.get_user_by_username(username)
        if user is None:
            verify_dummy_password(password)
            raise InvalidCredentialsError
        locked_until = user["locked_until"]
        if locked_until is not None:
            remaining = int((_parse(str(locked_until)) - datetime.now(UTC)).total_seconds())
            if remaining > 0:
                raise LoginRateLimitedError(remaining)
        if not bool(user["is_active"]) or not verify_password(
            password,
            str(user["password_hash"]),
        ):
            failures, locked = self.repository.record_login_failure(
                user_id=str(user["id"]),
                failure_limit=self.settings.login_failure_limit,
                lockout_seconds=self.settings.login_lockout_seconds,
            )
            if locked is not None or failures >= self.settings.login_failure_limit:
                raise LoginRateLimitedError(self.settings.login_lockout_seconds)
            raise InvalidCredentialsError
        self.repository.record_login_success(str(user["id"]))
        token = secrets.token_urlsafe(32)
        csrf_token = secrets.token_urlsafe(32)
        expires_at = _utc(
            datetime.now(UTC)
            + timedelta(seconds=self.settings.session_lifetime_seconds)
        )
        session = self.repository.create_session(
            user_id=str(user["id"]),
            token_hash=hash_secret(token),
            csrf_token_hash=hash_secret(csrf_token),
            expires_at=expires_at,
        )
        return CreatedSession(
            token=token,
            csrf_token=csrf_token,
            expires_at=expires_at,
            record=session,
        )

    def authenticate_session(self, token: str | None) -> dict[str, Any] | None:
        if not token:
            return None
        session = self.repository.get_session_by_hash(hash_secret(token))
        if session is None:
            return None
        if not bool(session["is_active"]) or not self.repository.is_timestamp_active(
            expires_at=str(session["expires_at"]),
            revoked_at=session["revoked_at"],
        ):
            return None
        self.repository.touch_session(str(session["id"]))
        return session

    def rotate_csrf(self, session_id: str) -> str:
        token = secrets.token_urlsafe(32)
        self.repository.rotate_csrf(session_id, hash_secret(token))
        return token

    @staticmethod
    def validate_csrf(session: dict[str, Any], token: str | None) -> bool:
        return bool(
            token
            and compare_digest(
                hash_secret(token),
                str(session["csrf_token_hash"]),
            )
        )

    def create_api_key(
        self,
        *,
        user_id: str,
        name: str,
        scopes: Sequence[str],
        expires_at: str | None,
    ) -> tuple[str, dict[str, Any]]:
        prefix = secrets.token_hex(4)
        secret = secrets.token_urlsafe(32)
        full_key = f"pmo_{prefix}_{secret}"
        record = self.repository.create_api_key(
            user_id=user_id,
            name=name,
            prefix=prefix,
            key_hash=hash_secret(full_key),
            scopes=scopes,
            expires_at=expires_at,
        )
        return full_key, record

    def authenticate_api_key(self, full_key: str | None) -> dict[str, Any] | None:
        if not full_key or not full_key.startswith("pmo_"):
            return None
        record = self.repository.get_api_key_by_hash(hash_secret(full_key))
        if record is None or not bool(record["is_active"]):
            return None
        if not self.repository.is_timestamp_active(
            expires_at=record["expires_at"],
            revoked_at=record["revoked_at"],
        ):
            return None
        self.repository.touch_api_key(str(record["id"]))
        return record
