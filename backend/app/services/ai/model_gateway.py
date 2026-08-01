from __future__ import annotations

import asyncio
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from decimal import Decimal
from time import perf_counter

import httpx

from app.models.ai import (
    GatewayResponse,
    ModelRequest,
    ModelResponse,
    ModelRouteRole,
    ModelStreamEvent,
    ModelUsage,
)
from app.repositories.ai import AIRepository
from app.security.provider_secrets import ProviderSecretCipher
from app.services.ai.providers import (
    AnthropicCompatibleProvider,
    ModelProvider,
    OpenAICompatibleProvider,
    ProviderError,
)

ProviderFactory = Callable[[dict[str, object], str], ModelProvider]
RetryDelay = Callable[[int], Awaitable[None]]


class ModelGateway:
    def __init__(
        self,
        *,
        repository: AIRepository,
        secret_cipher: ProviderSecretCipher,
        client: httpx.AsyncClient | None = None,
        provider_factory: ProviderFactory | None = None,
        retry_delay: RetryDelay | None = None,
    ) -> None:
        self.repository = repository
        self.secret_cipher = secret_cipher
        self._client = client
        self._provider_factory = provider_factory or self._default_provider_factory
        self._retry_delay = retry_delay or self._default_retry_delay
        self._semaphores: dict[str, tuple[int, asyncio.Semaphore]] = {}

    @staticmethod
    async def _default_retry_delay(attempt: int) -> None:
        await asyncio.sleep(min(0.25 * (2 ** max(0, attempt - 1)), 2.0))

    def _default_provider_factory(
        self,
        provider: dict[str, object],
        api_key: str,
    ) -> ModelProvider:
        if self._client is None:
            raise RuntimeError("Model gateway HTTP client is not configured")
        arguments = {
            "provider_id": str(provider["id"]),
            "provider_name": str(provider["name"]),
            "base_url": str(provider["base_url"]),
            "api_key": api_key,
            "client": self._client,
            "timeout_seconds": float(provider["timeout_seconds"]),
        }
        if provider["protocol"] == "anthropic_compatible":
            return AnthropicCompatibleProvider(**arguments)
        if provider["protocol"] == "openai_compatible":
            return OpenAICompatibleProvider(**arguments)
        raise RuntimeError("Unsupported provider protocol")

    def _semaphore(self, provider: dict[str, object]) -> asyncio.Semaphore:
        provider_id = str(provider["id"])
        limit = int(provider["concurrency_limit"])
        current = self._semaphores.get(provider_id)
        if current is None or current[0] != limit:
            current = (limit, asyncio.Semaphore(limit))
            self._semaphores[provider_id] = current
        return current[1]

    def _provider(self, provider: dict[str, object]) -> ModelProvider:
        provider_id = str(provider["id"])
        encrypted = self.repository.get_provider_secret(provider_id)
        if encrypted is None:
            raise ProviderError(
                code="authentication_failed",
                safe_summary="Provider credentials are not configured",
                retryable=False,
            )
        api_key = self.secret_cipher.decrypt(
            provider_id=provider_id,
            ciphertext=bytes(encrypted["encrypted_api_key"]),
            nonce=bytes(encrypted["nonce"]),
            key_version=int(encrypted["key_version"]),
        )
        return self._provider_factory(provider, api_key)

    def provider_adapter(
        self,
        provider_id: str,
    ) -> tuple[dict[str, object], ModelProvider]:
        provider = self.repository.get_provider(provider_id)
        if provider is None:
            raise KeyError("Provider not found")
        if not bool(provider["enabled"]):
            raise RuntimeError("Provider is disabled")
        return provider, self._provider(provider)

    @staticmethod
    def _validate_request(model: dict[str, object], request: ModelRequest) -> None:
        configured_max = model.get("max_output_tokens")
        if configured_max is not None and request.max_tokens > int(configured_max):
            raise RuntimeError("Requested output exceeds the model output limit")
        if request.stream and model.get("supports_streaming") is not True:
            raise RuntimeError("Model streaming capability is not enabled")
        if request.tools and model.get("supports_tools") is not True:
            raise RuntimeError("Model tool capability is not enabled")

    @staticmethod
    def _cost(
        model: dict[str, object],
        usage: ModelUsage | None,
    ) -> tuple[Decimal | None, str | None, str | None]:
        if usage is None:
            return None, None, None
        input_tokens = usage.input_tokens
        output_tokens = usage.output_tokens
        cached_tokens = usage.cached_tokens or 0
        if input_tokens is None or output_tokens is None:
            return None, None, None
        input_price = model.get("input_price_per_million")
        output_price = model.get("output_price_per_million")
        cache_price = model.get("cached_input_price_per_million")
        if input_price is None or output_price is None:
            return None, None, None
        if cached_tokens > 0 and cache_price is None:
            return None, None, None
        currency = model.get("price_currency")
        effective_at = model.get("price_effective_at")
        if currency is None or effective_at is None:
            return None, None, None
        uncached_tokens = max(0, input_tokens - cached_tokens)
        divisor = Decimal(1_000_000)
        cost = Decimal(uncached_tokens) * Decimal(str(input_price)) / divisor
        cost += Decimal(output_tokens) * Decimal(str(output_price)) / divisor
        if cached_tokens:
            cost += Decimal(cached_tokens) * Decimal(str(cache_price)) / divisor
        return cost, str(currency), str(effective_at)

    def _target(
        self,
        *,
        route_role: ModelRouteRole | None,
        model_record_id: str | None,
    ) -> tuple[dict[str, object], dict[str, object]]:
        if model_record_id is not None:
            return self.repository.get_model_target(model_record_id)
        return self.repository.get_route_target(route_role or "default")

    async def _generate_target(
        self,
        *,
        provider: dict[str, object],
        model: dict[str, object],
        request: ModelRequest,
        route_role: ModelRouteRole | None,
        correlation_id: str,
        attempt_offset: int,
        is_fallback: bool,
        fallback_from_provider_id: str | None = None,
        fallback_from_model_id: str | None = None,
        fallback_reason: str | None = None,
    ) -> tuple[ModelResponse | None, ProviderError | None, int]:
        resolved = request.model_copy(update={"model": str(model["model_id"])})
        self._validate_request(model, resolved)
        adapter = self._provider(provider)
        maximum_attempts = int(provider["max_retries"]) + 1
        for local_attempt in range(1, maximum_attempts + 1):
            attempt_number = attempt_offset + local_attempt
            invocation_id = self.repository.start_invocation(
                provider_id=str(provider["id"]),
                model_record_id=str(model["id"]),
                model_id=str(model["model_id"]),
                route_role=route_role,
                request_correlation_id=correlation_id,
                attempt_number=attempt_number,
                is_fallback=is_fallback,
                fallback_from_provider_id=fallback_from_provider_id,
                fallback_from_model_id=fallback_from_model_id,
                fallback_reason=fallback_reason,
            )
            started = perf_counter()
            try:
                async with self._semaphore(provider):
                    response = await adapter.generate(resolved)
            except asyncio.CancelledError:
                self.repository.finish_invocation(
                    invocation_id,
                    status="cancelled",
                    latency_ms=_elapsed_ms(started),
                    error_code="cancelled",
                    error_summary="Model request was cancelled",
                )
                raise
            except ProviderError as error:
                self.repository.finish_invocation(
                    invocation_id,
                    status="failed",
                    latency_ms=_elapsed_ms(started),
                    error_code=error.code,
                    error_summary=error.safe_summary,
                )
                if error.retryable and local_attempt < maximum_attempts:
                    await self._retry_delay(local_attempt)
                    continue
                return None, error, attempt_number
            cost, currency, effective_at = self._cost(model, response.usage)
            usage = response.usage
            self.repository.finish_invocation(
                invocation_id,
                status="succeeded",
                latency_ms=_elapsed_ms(started),
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                cached_tokens=usage.cached_tokens if usage else None,
                estimated_cost=cost,
                price_currency=currency,
                pricing_effective_at=effective_at,
            )
            return response, None, attempt_number
        raise AssertionError("bounded provider attempt loop did not return")

    async def generate(
        self,
        request: ModelRequest,
        *,
        route_role: ModelRouteRole | None = "default",
        model_record_id: str | None = None,
    ) -> GatewayResponse:
        provider, model = self._target(
            route_role=route_role,
            model_record_id=model_record_id,
        )
        correlation_id = str(uuid.uuid4())
        response, error, attempts = await self._generate_target(
            provider=provider,
            model=model,
            request=request,
            route_role=route_role,
            correlation_id=correlation_id,
            attempt_offset=0,
            is_fallback=False,
        )
        if response is not None:
            return GatewayResponse(
                response=response,
                route_role=route_role,
                fallback_used=False,
                request_correlation_id=correlation_id,
                initial_provider_id=str(provider["id"]),
                initial_model_id=str(model["model_id"]),
                final_provider_id=str(provider["id"]),
                final_model_id=str(model["model_id"]),
            )
        assert error is not None
        if not error.retryable or route_role in {None, "fallback"}:
            raise error
        try:
            fallback_provider, fallback_model = self.repository.get_route_target(
                "fallback"
            )
        except (KeyError, RuntimeError, ValueError):
            raise error
        if fallback_model["id"] == model["id"]:
            raise error
        fallback_response, fallback_error, _ = await self._generate_target(
            provider=fallback_provider,
            model=fallback_model,
            request=request,
            route_role=route_role,
            correlation_id=correlation_id,
            attempt_offset=attempts,
            is_fallback=True,
            fallback_from_provider_id=str(provider["id"]),
            fallback_from_model_id=str(model["model_id"]),
            fallback_reason=error.safe_summary,
        )
        if fallback_response is None:
            assert fallback_error is not None
            raise fallback_error
        return GatewayResponse(
            response=fallback_response,
            route_role=route_role,
            fallback_used=True,
            request_correlation_id=correlation_id,
            initial_provider_id=str(provider["id"]),
            initial_model_id=str(model["model_id"]),
            final_provider_id=str(fallback_provider["id"]),
            final_model_id=str(fallback_model["model_id"]),
        )

    async def stream(
        self,
        request: ModelRequest,
        *,
        route_role: ModelRouteRole | None = "default",
        model_record_id: str | None = None,
    ) -> AsyncIterator[ModelStreamEvent]:
        provider, model = self._target(
            route_role=route_role,
            model_record_id=model_record_id,
        )
        correlation_id = str(uuid.uuid4())
        attempt_number = 0
        primary_error: ProviderError | None = None
        current_provider = provider
        current_model = model
        is_fallback = False
        while True:
            adapter = self._provider(current_provider)
            resolved = request.model_copy(
                update={"model": str(current_model["model_id"]), "stream": True}
            )
            self._validate_request(current_model, resolved)
            maximum_attempts = int(current_provider["max_retries"]) + 1
            for local_attempt in range(1, maximum_attempts + 1):
                attempt_number += 1
                invocation_id = self.repository.start_invocation(
                    provider_id=str(current_provider["id"]),
                    model_record_id=str(current_model["id"]),
                    model_id=str(current_model["model_id"]),
                    route_role=route_role,
                    request_correlation_id=correlation_id,
                    attempt_number=attempt_number,
                    is_fallback=is_fallback,
                    fallback_from_provider_id=(
                        str(provider["id"]) if is_fallback else None
                    ),
                    fallback_from_model_id=(
                        str(model["model_id"]) if is_fallback else None
                    ),
                    fallback_reason=(
                        primary_error.safe_summary
                        if is_fallback and primary_error is not None
                        else None
                    ),
                )
                started = perf_counter()
                emitted = False
                completed: ModelResponse | None = None
                try:
                    async with self._semaphore(current_provider):
                        async for event in adapter.stream(resolved):
                            if event.type not in {"start", "completed"}:
                                emitted = True
                            if event.type == "completed":
                                completed = event.response
                            if event.type == "completed":
                                event = event.model_copy(
                                    update={
                                        "fallback_used": is_fallback,
                                        "request_correlation_id": correlation_id,
                                        "initial_provider_id": str(provider["id"]),
                                        "initial_model_id": str(model["model_id"]),
                                        "final_provider_id": str(current_provider["id"]),
                                        "final_model_id": str(current_model["model_id"]),
                                    }
                                )
                            yield event
                    if completed is None:
                        raise ProviderError(
                            code="protocol_error",
                            safe_summary="Provider stream ended without completion",
                            retryable=False,
                        )
                except asyncio.CancelledError:
                    self.repository.finish_invocation(
                        invocation_id,
                        status="cancelled",
                        latency_ms=_elapsed_ms(started),
                        error_code="cancelled",
                        error_summary="Model request was cancelled",
                    )
                    raise
                except ProviderError as error:
                    self.repository.finish_invocation(
                        invocation_id,
                        status="failed",
                        latency_ms=_elapsed_ms(started),
                        error_code=error.code,
                        error_summary=error.safe_summary,
                    )
                    if emitted:
                        raise
                    if error.retryable and local_attempt < maximum_attempts:
                        await self._retry_delay(local_attempt)
                        continue
                    primary_error = error
                    break
                cost, currency, effective_at = self._cost(
                    current_model,
                    completed.usage,
                )
                usage = completed.usage
                self.repository.finish_invocation(
                    invocation_id,
                    status="succeeded",
                    latency_ms=_elapsed_ms(started),
                    input_tokens=usage.input_tokens if usage else None,
                    output_tokens=usage.output_tokens if usage else None,
                    cached_tokens=usage.cached_tokens if usage else None,
                    estimated_cost=cost,
                    price_currency=currency,
                    pricing_effective_at=effective_at,
                )
                return
            assert primary_error is not None
            if (
                is_fallback
                or not primary_error.retryable
                or route_role in {None, "fallback"}
            ):
                raise primary_error
            try:
                fallback_provider, fallback_model = self.repository.get_route_target(
                    "fallback"
                )
            except (KeyError, RuntimeError, ValueError):
                raise primary_error
            if fallback_model["id"] == model["id"]:
                raise primary_error
            current_provider = fallback_provider
            current_model = fallback_model
            is_fallback = True


def _elapsed_ms(started: float) -> int:
    return max(0, round((perf_counter() - started) * 1000))
