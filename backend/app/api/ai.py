from __future__ import annotations

import json
import sqlite3
import uuid
from collections.abc import AsyncIterator
from decimal import Decimal
from time import perf_counter
from typing import Annotated, Literal
from urllib.parse import urlsplit, urlunsplit

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import StreamingResponse
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SecretStr,
    field_validator,
    model_validator,
)

from app.models.ai import (
    EvalCaseView,
    GatewayResponse,
    ModelInfo,
    ModelMessage,
    ModelRequest,
    ModelRouteRole,
    ModelToolDefinition,
    PromptDefinitionView,
    PromptVersionAction,
    ProviderHealth,
    ProviderProtocol,
)
from app.repositories.ai import AIRepository
from app.security.dependencies import AuthContext, require_owner_session
from app.security.provider_secrets import ProviderSecretCipher
from app.services.ai.model_gateway import ModelGateway
from app.services.ai.providers import ProviderError
from app.services.ai.providers.base import utc_now

router = APIRouter(prefix="/ai", tags=["ai-model-center"])
OwnerSession = Annotated[AuthContext, Depends(require_owner_session)]
ProviderType = Literal[
    "minimax",
    "deepseek",
    "glm",
    "anthropic",
    "openai",
    "custom_anthropic",
    "custom_openai",
]
BillingMode = Literal[
    "subscription_fixed",
    "pay_as_you_go",
    "prepaid_balance",
    "quota_bundle",
    "relay",
    "unknown",
]
CheckKind = Literal["text", "streaming", "tools", "thinking"]

PROVIDER_TEMPLATES = (
    {
        "id": "minimax",
        "display_name": "MiniMax",
        "protocol": "openai_compatible",
        "base_url": "https://api.minimax.io/v1",
    },
    {
        "id": "deepseek",
        "display_name": "DeepSeek",
        "protocol": "openai_compatible",
        "base_url": "https://api.deepseek.com",
    },
    {
        "id": "glm",
        "display_name": "GLM / 智谱",
        "protocol": "openai_compatible",
        "base_url": "https://open.bigmodel.cn/api/paas/v4",
    },
    {
        "id": "anthropic",
        "display_name": "Anthropic",
        "protocol": "anthropic_compatible",
        "base_url": "https://api.anthropic.com",
    },
    {
        "id": "openai",
        "display_name": "OpenAI",
        "protocol": "openai_compatible",
        "base_url": "https://api.openai.com/v1",
    },
    {
        "id": "custom_anthropic",
        "display_name": "自定义 Anthropic Compatible",
        "protocol": "anthropic_compatible",
        "base_url": None,
    },
    {
        "id": "custom_openai",
        "display_name": "自定义 OpenAI Compatible",
        "protocol": "openai_compatible",
        "base_url": None,
    },
)


def _normalize_base_url(value: str) -> str:
    normalized = value.strip().rstrip("/")
    parts = urlsplit(normalized)
    if parts.scheme not in {"http", "https"} or not parts.hostname:
        raise ValueError("base_url must be an absolute HTTP(S) URL")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("base_url must not contain credentials, query, or fragment")
    if parts.scheme == "http" and parts.hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        raise ValueError("HTTP base_url is allowed only for loopback development")
    return urlunsplit((parts.scheme, parts.netloc, parts.path.rstrip("/"), "", ""))


class ProviderTemplateView(BaseModel):
    id: ProviderType
    display_name: str
    protocol: ProviderProtocol
    base_url: str | None


class ProviderWriteBase(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    provider_type: ProviderType
    protocol: ProviderProtocol
    base_url: str = Field(min_length=1, max_length=2_000)
    enabled: bool = False
    timeout_seconds: float = Field(default=60, ge=1, le=600)
    max_retries: int = Field(default=1, ge=0, le=5)
    concurrency_limit: int = Field(default=1, ge=1, le=20)
    vendor: str | None = Field(default=None, max_length=100)
    instance_label: str | None = Field(default=None, max_length=200)
    billing_mode: BillingMode | None = None
    billing_profile_id: str | None = Field(default=None, max_length=100)
    relay_metadata: str = Field(default="{}", max_length=10_000)

    @field_validator("name")
    @classmethod
    def normalized_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized or not normalized.isprintable():
            raise ValueError("name must be printable and non-blank")
        return normalized

    @field_validator("base_url")
    @classmethod
    def valid_base_url(cls, value: str) -> str:
        return _normalize_base_url(value)


class ProviderCreate(ProviderWriteBase):
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=10_000)


class ProviderUpdate(ProviderWriteBase):
    api_key: SecretStr | None = Field(default=None, min_length=1, max_length=10_000)
    clear_api_key: bool = False

    @model_validator(mode="after")
    def secret_action_is_unambiguous(self) -> ProviderUpdate:
        if self.api_key is not None and self.clear_api_key:
            raise ValueError("api_key and clear_api_key cannot be used together")
        return self


class ProviderView(ProviderWriteBase):
    id: str
    credentials_configured: bool
    model_count: int
    last_health_status: str | None
    last_health_latency_ms: int | None
    last_health_checked_at: str | None
    created_at: str
    updated_at: str
    tool_capability_status: str = "unknown"
    tool_capability_tested_at: str | None = None


class ModelWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    display_name: str = Field(min_length=1, max_length=200)
    enabled: bool = False
    context_window: int | None = Field(default=None, gt=0)
    max_output_tokens: int | None = Field(default=None, gt=0)
    supports_streaming: bool | None = None
    supports_tools: bool | None = None
    supports_thinking: bool | None = None
    supports_vision: bool | None = None
    supports_files: bool | None = None
    supports_structured_output: bool | None = None
    capabilities_source: Literal["unknown", "provider", "user", "tested"] = "unknown"
    input_price_per_million: Decimal | None = Field(default=None, ge=0)
    output_price_per_million: Decimal | None = Field(default=None, ge=0)
    cached_input_price_per_million: Decimal | None = Field(default=None, ge=0)
    cache_write_price_per_million: Decimal | None = Field(default=None, ge=0)
    price_source: str | None = Field(default=None, max_length=500)
    price_currency: str | None = Field(default=None, min_length=3, max_length=12)
    price_effective_at: str | None = Field(default=None, max_length=40)

    @model_validator(mode="after")
    def validate_price_metadata(self) -> ModelWrite:
        configured = any(
            value is not None
            for value in (
                self.input_price_per_million,
                self.output_price_per_million,
                self.cached_input_price_per_million,
                self.cache_write_price_per_million,
            )
        )
        if configured != (
            self.price_currency is not None and self.price_effective_at is not None
        ):
            raise ValueError(
                "price currency and effective time are required with configured prices"
            )
        if self.price_currency is not None:
            self.price_currency = self.price_currency.strip().upper()
        return self


class ModelUpdate(ModelWrite):
    provider_id: str | None = Field(default=None, exclude=True)
    model_id: str | None = Field(default=None, exclude=True)


class RouteWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routes: dict[ModelRouteRole, str | None]


class ProviderTestWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_record_id: str = Field(min_length=1, max_length=100)
    check_kind: CheckKind = "text"


class DebugWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    message: str = Field(min_length=1, max_length=2_000)
    route_role: ModelRouteRole | None = "default"
    model_record_id: str | None = Field(default=None, max_length=100)
    stream: bool = False

    @field_validator("message")
    @classmethod
    def trimmed_message(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("message must not be blank")
        return normalized


class BillingProfileWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=200)
    vendor: str = Field(min_length=1, max_length=100)
    billing_mode: BillingMode
    package_name: str | None = Field(default=None, max_length=200)
    purchase_amount: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=12)
    starts_at: str | None = Field(default=None, max_length=40)
    ends_at: str | None = Field(default=None, max_length=40)
    quota_description: str | None = Field(default=None, max_length=2_000)
    token_quota: int | None = Field(default=None, ge=0)
    call_limit: int | None = Field(default=None, ge=0)
    concurrency_limit: int | None = Field(default=None, ge=1, le=20)


class ProviderPriceVersionWrite(BaseModel):
    model_config = ConfigDict(extra="forbid")

    provider_id: str = Field(min_length=1, max_length=100)
    model_record_id: str | None = Field(default=None, max_length=100)
    model_id: str = Field(min_length=1, max_length=200)
    input_price_per_million: Decimal | None = Field(default=None, ge=0)
    output_price_per_million: Decimal | None = Field(default=None, ge=0)
    cached_input_price_per_million: Decimal | None = Field(default=None, ge=0)
    cache_write_price_per_million: Decimal | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, min_length=3, max_length=12)
    effective_at: str = Field(min_length=1, max_length=40)
    source: str = Field(min_length=1, max_length=500)


def _repository(request: Request) -> AIRepository:
    return request.app.state.ai_repository


def _cipher(request: Request) -> ProviderSecretCipher:
    return request.app.state.provider_secret_cipher


def _gateway(request: Request) -> ModelGateway:
    return request.app.state.model_gateway


def _http_error(error: Exception) -> HTTPException:
    if isinstance(error, KeyError):
        return HTTPException(status_code=404, detail=str(error.args[0]))
    if isinstance(error, sqlite3.IntegrityError):
        return HTTPException(status_code=409, detail="AI configuration conflicts with existing data")
    if isinstance(error, ProviderError):
        status = 429 if error.code == "rate_limited" else 502
        return HTTPException(status_code=status, detail=error.safe_summary)
    if isinstance(error, (RuntimeError, ValueError)):
        return HTTPException(status_code=409, detail=str(error))
    return HTTPException(status_code=500, detail="AI model center operation failed")


@router.get("/provider-templates", response_model=list[ProviderTemplateView])
def list_provider_templates(_: OwnerSession) -> tuple[dict[str, object], ...]:
    return PROVIDER_TEMPLATES


@router.get("/billing-profiles")
def list_billing_profiles(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_billing_profiles()


@router.post("/billing-profiles", status_code=201)
def create_billing_profile(
    payload: BillingProfileWrite,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    try:
        values = payload.model_dump(mode="json")
        if values.get("currency") is not None:
            values["currency"] = str(values["currency"]).upper()
        return _repository(request).create_billing_profile(**values)
    except Exception as error:
        raise _http_error(error) from error


@router.get("/provider-prices")
def list_provider_prices(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_provider_price_versions()


@router.post("/provider-prices", status_code=201)
def create_provider_price(
    payload: ProviderPriceVersionWrite,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    try:
        values = payload.model_dump(mode="json")
        if values.get("currency") is not None:
            values["currency"] = str(values["currency"]).upper()
        return _repository(request).create_provider_price_version(**values)
    except Exception as error:
        raise _http_error(error) from error


@router.get("/providers", response_model=list[ProviderView])
def list_providers(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_providers()


@router.post("/providers", response_model=ProviderView, status_code=201)
def create_provider(
    payload: ProviderCreate,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    provider_id = str(uuid.uuid4())
    secret = (
        _cipher(request).encrypt(provider_id, payload.api_key.get_secret_value())
        if payload.api_key is not None
        else None
    )
    values = payload.model_dump(exclude={"api_key"})
    try:
        return _repository(request).create_provider(
            provider_id=provider_id,
            secret=secret,
            **values,
        )
    except Exception as error:
        raise _http_error(error) from error


@router.get("/providers/{provider_id}", response_model=ProviderView)
def get_provider(
    provider_id: str,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    provider = _repository(request).get_provider(provider_id)
    if provider is None:
        raise HTTPException(status_code=404, detail="Provider not found")
    return provider


@router.put("/providers/{provider_id}", response_model=ProviderView)
def update_provider(
    provider_id: str,
    payload: ProviderUpdate,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    repository = _repository(request)
    try:
        secret = (
            _cipher(request).encrypt(provider_id, payload.api_key.get_secret_value())
            if payload.api_key is not None
            else None
        )
        values = payload.model_dump(exclude={"api_key", "clear_api_key"})
        for optional_field in ("vendor", "instance_label", "billing_mode", "billing_profile_id"):
            if values.get(optional_field) is None:
                values.pop(optional_field, None)
        repository.update_provider(provider_id, **values)
        if secret is not None:
            repository.set_provider_secret(provider_id, secret)
        elif payload.clear_api_key:
            repository.clear_provider_secret(provider_id)
        provider = repository.get_provider(provider_id)
        assert provider is not None
        return provider
    except Exception as error:
        raise _http_error(error) from error


@router.delete("/providers/{provider_id}", status_code=204)
def delete_provider(
    provider_id: str,
    request: Request,
    _: OwnerSession,
) -> Response:
    try:
        _repository(request).delete_provider(provider_id)
    except Exception as error:
        raise _http_error(error) from error
    return Response(status_code=204)


@router.post("/providers/{provider_id}/refresh-models", response_model=list[ModelInfo])
async def refresh_models(
    provider_id: str,
    request: Request,
    _: OwnerSession,
) -> list[ModelInfo]:
    try:
        _, adapter = _gateway(request).provider_adapter(provider_id)
        return await adapter.list_models()
    except Exception as error:
        raise _http_error(error) from error


async def _run_provider_test(
    gateway: ModelGateway,
    repository: AIRepository,
    provider_id: str,
    model_record_id: str,
    check_kind: CheckKind,
) -> ProviderHealth:
    model = repository.get_model(model_record_id)
    if model is None:
        raise KeyError("Model not found")
    if model["provider_id"] != provider_id:
        raise RuntimeError("Model does not belong to the selected provider")
    _, adapter = gateway.provider_adapter(provider_id)
    tools = None
    tool_choice = None
    if check_kind == "tools":
        tools = [
            ModelToolDefinition(
                name="report_status",
                description="Return a minimal status object",
                input_schema={
                    "type": "object",
                    "properties": {"status": {"type": "string"}},
                    "required": ["status"],
                },
            )
        ]
        tool_choice = "required"
    model_request = ModelRequest(
        system="This is a connection test. Keep the response minimal.",
        messages=[ModelMessage(role="user", content="Return only OK.")],
        model=str(model["model_id"]),
        max_tokens=32,
        stream=check_kind == "streaming",
        tools=tools,
        tool_choice=tool_choice,
        metadata={"check_kind": check_kind},
        timeout=30,
    )
    started = perf_counter()
    observed = False
    if check_kind == "streaming":
        completed = None
        async for event in adapter.stream(model_request):
            if event.content_delta:
                observed = True
            if event.response is not None:
                completed = event.response
        observed = observed and completed is not None
    else:
        response = await adapter.generate(model_request)
        if check_kind == "tools":
            observed = bool(response.tool_calls)
        elif check_kind == "thinking":
            observed = bool(response.thinking_content)
        else:
            observed = bool(response.content)
    latency = max(0, round((perf_counter() - started) * 1000))
    return ProviderHealth(
        status="healthy" if observed else "degraded",
        checked_at=utc_now(),
        latency_ms=latency,
        error_code=None if observed else "capability_not_observed",
        error_summary=None if observed else f"{check_kind} capability was not observed",
        check_kind=check_kind,
        model_id=str(model["model_id"]),
    )


@router.post("/providers/{provider_id}/test", response_model=ProviderHealth)
async def test_provider(
    provider_id: str,
    payload: ProviderTestWrite,
    request: Request,
    _: OwnerSession,
) -> ProviderHealth:
    repository = _repository(request)
    try:
        health = await _run_provider_test(
            _gateway(request),
            repository,
            provider_id,
            payload.model_record_id,
            payload.check_kind,
        )
    except ProviderError as error:
        health = ProviderHealth(
            status=error.health_status,
            checked_at=utc_now(),
            error_code=error.code,
            error_summary=error.safe_summary,
            check_kind=payload.check_kind,
        )
    except Exception as error:
        raise _http_error(error) from error
    repository.record_health(
        provider_id=provider_id,
        model_id=health.model_id,
        check_kind=health.check_kind,
        status=health.status,
        checked_at=health.checked_at,
        latency_ms=health.latency_ms,
        error_code=health.error_code,
        error_summary=health.error_summary,
    )
    capability_field = {
        "streaming": "supports_streaming",
        "tools": "supports_tools",
        "thinking": "supports_thinking",
    }.get(payload.check_kind)
    changes: dict[str, object] = {
        "last_health_status": health.status,
        "last_health_checked_at": health.checked_at,
    }
    if capability_field is not None and health.error_code in {
        None,
        "capability_not_observed",
    }:
        changes[capability_field] = health.status == "healthy"
        changes["capabilities_source"] = "tested"
    repository.update_model(payload.model_record_id, **changes)
    return health


@router.get("/models")
def list_models(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_models()


@router.post("/models", status_code=201)
def create_model(
    payload: ModelWrite,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    try:
        return _repository(request).create_model(**payload.model_dump(mode="json"))
    except Exception as error:
        raise _http_error(error) from error


@router.put("/models/{model_record_id}")
def update_model(
    model_record_id: str,
    payload: ModelUpdate,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    values = payload.model_dump(
        mode="json",
        exclude={"provider_id", "model_id"},
    )
    try:
        return _repository(request).update_model(model_record_id, **values)
    except Exception as error:
        raise _http_error(error) from error


@router.delete("/models/{model_record_id}", status_code=204)
def delete_model(
    model_record_id: str,
    request: Request,
    _: OwnerSession,
) -> Response:
    try:
        _repository(request).delete_model(model_record_id)
    except Exception as error:
        raise _http_error(error) from error
    return Response(status_code=204)


@router.get("/routes")
def list_routes(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_routes()


@router.put("/routes")
def update_routes(
    payload: RouteWrite,
    request: Request,
    _: OwnerSession,
) -> list[dict[str, object]]:
    try:
        return _repository(request).replace_routes(payload.routes)
    except Exception as error:
        raise _http_error(error) from error


@router.get("/usage")
def get_usage(request: Request, _: OwnerSession) -> dict[str, object]:
    return _repository(request).usage_summary()


@router.get("/health")
def get_health(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_health()


@router.get("/prompts", response_model=list[PromptDefinitionView])
def list_prompts(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_prompt_definitions()


@router.get("/evals", response_model=list[EvalCaseView])
def list_evals(request: Request, _: OwnerSession) -> list[dict[str, object]]:
    return _repository(request).list_eval_cases()


@router.post("/prompts/{prompt_key}/activate", response_model=PromptDefinitionView)
def activate_prompt(
    prompt_key: str,
    payload: PromptVersionAction,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    try:
        return _repository(request).activate_prompt(
            prompt_key=prompt_key,
            version=payload.version,
        )
    except Exception as error:
        raise _http_error(error) from error


@router.post("/prompts/{prompt_key}/rollback", response_model=PromptDefinitionView)
def rollback_prompt(
    prompt_key: str,
    request: Request,
    _: OwnerSession,
) -> dict[str, object]:
    try:
        return _repository(request).rollback_prompt(prompt_key=prompt_key)
    except Exception as error:
        raise _http_error(error) from error


def _debug_request(payload: DebugWrite) -> ModelRequest:
    return ModelRequest(
        system="This is a bounded Model Gateway diagnostic request.",
        messages=[ModelMessage(role="user", content=payload.message)],
        max_tokens=256,
        stream=payload.stream,
        metadata={
            "source": "model-center-debug",
            "prompt_key": "model_center_debug",
            "prompt_version": "v1",
            "context_version": "ctx-v1",
            "tool_contract_version": "v1",
        },
        timeout=60,
    )


@router.post("/debug", response_model=GatewayResponse)
async def debug_generate(
    payload: DebugWrite,
    request: Request,
    _: OwnerSession,
) -> GatewayResponse | StreamingResponse:
    gateway = _gateway(request)
    model_request = _debug_request(payload)
    if not payload.stream:
        try:
            return await gateway.generate(
                model_request,
                route_role=payload.route_role,
                model_record_id=payload.model_record_id,
            )
        except Exception as error:
            raise _http_error(error) from error

    async def events() -> AsyncIterator[str]:
        try:
            async for event in gateway.stream(
                model_request,
                route_role=payload.route_role,
                model_record_id=payload.model_record_id,
            ):
                encoded = json.dumps(
                    event.model_dump(mode="json"),
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                yield f"data: {encoded}\n\n"
        except ProviderError as error:
            encoded = json.dumps(
                {
                    "type": "error",
                    "error_code": error.code,
                    "error_summary": error.safe_summary,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            yield f"data: {encoded}\n\n"

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
