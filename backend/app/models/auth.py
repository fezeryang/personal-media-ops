from datetime import UTC, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

ApiScope = Literal[
    "library:read",
    "intelligence:read",
    "tasks:read",
    "tasks:write",
    "subscriptions:read",
    "subscriptions:write",
    "admin",
]


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=1024)

    @field_validator("username")
    @classmethod
    def normalize_username(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("username must be printable and non-blank")
        return normalized


class OwnerSummary(BaseModel):
    id: str
    username: str


class SessionStatus(BaseModel):
    authenticated: bool
    user: OwnerSummary | None
    csrf_token: str | None


class LoginResponse(BaseModel):
    user: OwnerSummary
    csrf_token: str
    expires_at: str


class SessionSummary(BaseModel):
    id: str
    created_at: str
    expires_at: str
    last_seen_at: str
    revoked_at: str | None
    current: bool


class CreateApiKeyRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    scopes: list[ApiScope] = Field(min_length=1, max_length=7)
    expires_at: datetime | None = None

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("name must be printable and non-blank")
        return normalized

    @field_validator("scopes")
    @classmethod
    def unique_scopes(cls, value: list[ApiScope]) -> list[ApiScope]:
        if len(value) != len(set(value)):
            raise ValueError("scopes must be unique")
        return value

    @field_validator("expires_at")
    @classmethod
    def future_expiry(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        normalized = value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)
        if normalized <= datetime.now(UTC):
            raise ValueError("expires_at must be in the future")
        return normalized


class ApiKeySummary(BaseModel):
    id: str
    name: str
    prefix: str
    scopes: list[ApiScope]
    created_at: str
    last_used_at: str | None
    expires_at: str | None
    revoked_at: str | None


class CreatedApiKey(BaseModel):
    api_key: str
    key: ApiKeySummary
