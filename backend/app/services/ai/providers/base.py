from __future__ import annotations

import json
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from datetime import UTC, datetime
from time import perf_counter
from urllib.parse import urlsplit, urlunsplit

import httpx

from app.models.ai import (
    ModelCapabilities,
    ModelInfo,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ProviderHealth,
    ProviderHealthStatus,
)


class ProviderError(RuntimeError):
    def __init__(
        self,
        *,
        code: str,
        safe_summary: str,
        retryable: bool,
        status_code: int | None = None,
    ) -> None:
        super().__init__(safe_summary)
        self.code = code
        self.safe_summary = safe_summary
        self.retryable = retryable
        self.status_code = status_code

    @property
    def health_status(self) -> ProviderHealthStatus:
        if self.code in {
            "unreachable",
            "authentication_failed",
            "model_not_found",
            "rate_limited",
            "protocol_error",
        }:
            return self.code  # type: ignore[return-value]
        return "degraded"


def utc_now() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")


def elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))


def endpoint(base_url: str, path: str) -> str:
    parts = urlsplit(base_url.rstrip("/"))
    base_path = parts.path.rstrip("/")
    target = path if path.startswith("/") else f"/{path}"
    if base_path.endswith("/v1") and target.startswith("/v1/"):
        target = target[3:]
    return urlunsplit(
        (parts.scheme, parts.netloc, f"{base_path}{target}", "", "")
    )


def provider_error_from_response(response: httpx.Response) -> ProviderError:
    status = response.status_code
    if status in {401, 403}:
        return ProviderError(
            code="authentication_failed",
            safe_summary="Provider authentication failed",
            retryable=False,
            status_code=status,
        )
    if status == 404:
        return ProviderError(
            code="model_not_found",
            safe_summary="Provider endpoint or model was not found",
            retryable=False,
            status_code=status,
        )
    if status == 429:
        return ProviderError(
            code="rate_limited",
            safe_summary="Provider rate limit was reached",
            retryable=True,
            status_code=status,
        )
    return ProviderError(
        code="provider_error",
        safe_summary=f"Provider returned HTTP {status}",
        retryable=status >= 500,
        status_code=status,
    )


def provider_error_from_transport(error: Exception) -> ProviderError:
    if isinstance(error, httpx.TimeoutException):
        summary = "Provider request timed out"
    else:
        summary = "Provider could not be reached"
    return ProviderError(code="unreachable", safe_summary=summary, retryable=True)


def json_object(value: object, *, context: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise ProviderError(
            code="protocol_error",
            safe_summary=f"Provider returned invalid {context}",
            retryable=False,
        )
    return value


def parse_json_object(value: str, *, context: str) -> dict[str, object]:
    try:
        parsed = json.loads(value or "{}")
    except (json.JSONDecodeError, TypeError) as error:
        raise ProviderError(
            code="protocol_error",
            safe_summary=f"Provider returned invalid {context}",
            retryable=False,
        ) from error
    return json_object(parsed, context=context)


async def iter_sse(response: httpx.Response) -> AsyncIterator[tuple[str | None, str]]:
    event_name: str | None = None
    data_lines: list[str] = []
    async for line in response.aiter_lines():
        if not line:
            if data_lines:
                yield event_name, "\n".join(data_lines)
            event_name = None
            data_lines = []
            continue
        if line.startswith(":"):
            continue
        field, separator, value = line.partition(":")
        if separator and value.startswith(" "):
            value = value[1:]
        if field == "event":
            event_name = value
        elif field == "data":
            data_lines.append(value)
    if data_lines:
        yield event_name, "\n".join(data_lines)


class ModelProvider(ABC):
    provider_id: str
    provider_name: str

    @abstractmethod
    async def health_check(self) -> ProviderHealth:
        raise NotImplementedError

    @abstractmethod
    async def list_models(self) -> list[ModelInfo]:
        raise NotImplementedError

    @abstractmethod
    async def generate(self, request: ModelRequest) -> ModelResponse:
        raise NotImplementedError

    @abstractmethod
    def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self, model_id: str) -> ModelCapabilities:
        raise NotImplementedError
