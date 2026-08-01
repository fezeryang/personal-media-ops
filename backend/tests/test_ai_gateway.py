import asyncio
import os
from collections.abc import AsyncIterator
from pathlib import Path

import pytest

from app.models.ai import (
    ModelCapabilities,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelUsage,
    ProviderHealth,
)
from app.repositories.ai import AIRepository
from app.security.provider_secrets import ProviderSecretCipher
from app.services.ai.model_gateway import ModelGateway
from app.services.ai.providers import ModelProvider, ProviderError
from tests.alembic_utils import run_alembic_command


class FakeProvider(ModelProvider):
    def __init__(
        self,
        provider_id: str,
        outcomes: list[ModelResponse | ProviderError],
    ) -> None:
        self.provider_id = provider_id
        self.provider_name = provider_id
        self.outcomes = outcomes
        self.calls = 0

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(status="healthy", checked_at="2026-08-01T00:00:00Z")

    async def list_models(self):
        return []

    async def generate(self, request: ModelRequest) -> ModelResponse:
        outcome = self.outcomes[min(self.calls, len(self.outcomes) - 1)]
        self.calls += 1
        if isinstance(outcome, ProviderError):
            raise outcome
        return outcome.model_copy(update={"model": request.model})

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        response = await self.generate(request)
        yield ModelStreamEvent(type="content_delta", content_delta=response.content)
        yield ModelStreamEvent(type="completed", response=response)

    def capabilities(self, model_id: str) -> ModelCapabilities:
        return ModelCapabilities()


def _response(provider: str, content: str = "ok") -> ModelResponse:
    return ModelResponse(
        content=content,
        provider=provider,
        model="will-be-replaced",
        finish_reason="stop",
        usage=ModelUsage(input_tokens=10, output_tokens=2, cached_tokens=3),
    )


def _setup(tmp_path: Path) -> tuple[AIRepository, ProviderSecretCipher]:
    database = tmp_path / "mediaops.db"
    run_alembic_command(database, "upgrade", "head")
    key_path = tmp_path / "secrets" / "master.key"
    key_path.parent.mkdir(mode=0o700)
    key_path.write_bytes(os.urandom(32))
    key_path.chmod(0o600)
    return AIRepository(database), ProviderSecretCipher(key_path)


def _provider(repository: AIRepository, cipher: ProviderSecretCipher, name: str, retries: int) -> dict[str, object]:
    provider = repository.create_provider(
        name=name,
        provider_type="custom_openai",
        protocol="openai_compatible",
        base_url="https://example.test/v1",
        enabled=True,
        timeout_seconds=10,
        max_retries=retries,
        concurrency_limit=1,
        secret=cipher.encrypt("pending", "placeholder"),
    )
    repository.set_provider_secret(
        str(provider["id"]),
        cipher.encrypt(str(provider["id"]), f"secret-{name}"),
    )
    return provider


def _model(repository: AIRepository, provider_id: str, model_id: str, **prices: str | None) -> dict[str, object]:
    return repository.create_model(
        provider_id=provider_id,
        model_id=model_id,
        display_name=model_id,
        enabled=True,
        context_window=1000,
        max_output_tokens=100,
        supports_streaming=True,
        supports_tools=True,
        supports_thinking=None,
        supports_vision=None,
        supports_files=None,
        supports_structured_output=None,
        capabilities_source="user",
        input_price_per_million=prices.get("input_price_per_million"),
        output_price_per_million=prices.get("output_price_per_million"),
        cached_input_price_per_million=prices.get("cached_input_price_per_million"),
        price_currency="USD" if any(prices.values()) else None,
        price_effective_at="2026-08-01T00:00:00Z" if any(prices.values()) else None,
    )


def test_gateway_retries_then_falls_back_and_records_every_attempt(tmp_path: Path) -> None:
    repository, cipher = _setup(tmp_path)
    primary_provider = _provider(repository, cipher, "primary", retries=1)
    fallback_provider = _provider(repository, cipher, "fallback", retries=0)
    primary_model = _model(repository, str(primary_provider["id"]), "primary-model")
    fallback_model = _model(
        repository,
        str(fallback_provider["id"]),
        "fallback-model",
        input_price_per_million="1.00",
        output_price_per_million="2.00",
        cached_input_price_per_million="0.50",
    )
    repository.replace_routes(
        {"default": str(primary_model["id"]), "fallback": str(fallback_model["id"])}
    )
    unavailable = ProviderError(
        code="unreachable",
        safe_summary="Provider could not be reached",
        retryable=True,
    )
    providers = {
        str(primary_provider["id"]): FakeProvider("primary", [unavailable]),
        str(fallback_provider["id"]): FakeProvider("fallback", [_response("fallback")]),
    }

    async def run() -> None:
        gateway = ModelGateway(
            repository=repository,
            secret_cipher=cipher,
            provider_factory=lambda provider, _: providers[str(provider["id"])],
            retry_delay=lambda _: asyncio.sleep(0),
        )
        result = await gateway.generate(
            ModelRequest(
                messages=[ModelMessage(role="user", content="test")],
                max_tokens=20,
            ),
            route_role="default",
        )
        assert result.fallback_used is True
        assert result.response.provider == "fallback"
        assert result.response.model == "fallback-model"

    asyncio.run(run())
    invocations = repository.list_invocations(limit=10)
    assert [item["status"] for item in invocations[::-1]] == [
        "failed",
        "failed",
        "succeeded",
    ]
    assert len({item["request_correlation_id"] for item in invocations}) == 1
    final = next(item for item in invocations if item["status"] == "succeeded")
    assert final["fallback_from_model_id"] == "primary-model"
    assert final["fallback_reason"] == "Provider could not be reached"
    assert final["estimated_cost"] == "0.0000125"
    assert final["price_currency"] == "USD"


def test_gateway_does_not_fake_cost_and_rejects_disabled_route(tmp_path: Path) -> None:
    repository, cipher = _setup(tmp_path)
    provider = _provider(repository, cipher, "primary", retries=0)
    model = _model(repository, str(provider["id"]), "primary-model")
    repository.replace_routes({"default": str(model["id"])})
    fake = FakeProvider("primary", [_response("primary")])

    async def run_once() -> None:
        gateway = ModelGateway(
            repository=repository,
            secret_cipher=cipher,
            provider_factory=lambda *_: fake,
        )
        await gateway.generate(
            ModelRequest(
                messages=[ModelMessage(role="user", content="test")],
                max_tokens=20,
            ),
            route_role="default",
        )

    asyncio.run(run_once())
    invocation = repository.list_invocations(limit=1)[0]
    assert invocation["estimated_cost"] is None
    repository.update_model(str(model["id"]), enabled=False)
    with pytest.raises(RuntimeError, match="disabled"):
        asyncio.run(run_once())


def test_stream_never_falls_back_after_content_was_emitted(tmp_path: Path) -> None:
    repository, cipher = _setup(tmp_path)
    primary_provider = _provider(repository, cipher, "primary", retries=0)
    fallback_provider = _provider(repository, cipher, "fallback", retries=0)
    primary_model = _model(repository, str(primary_provider["id"]), "primary-model")
    fallback_model = _model(repository, str(fallback_provider["id"]), "fallback-model")
    repository.replace_routes(
        {"default": str(primary_model["id"]), "fallback": str(fallback_model["id"])}
    )

    class BrokenStream(FakeProvider):
        async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
            yield ModelStreamEvent(type="content_delta", content_delta="partial")
            raise ProviderError(
                code="unreachable",
                safe_summary="stream interrupted",
                retryable=True,
            )

    primary = BrokenStream("primary", [_response("primary")])
    fallback = FakeProvider("fallback", [_response("fallback")])

    async def run() -> None:
        gateway = ModelGateway(
            repository=repository,
            secret_cipher=cipher,
            provider_factory=lambda provider, _: (
                primary if provider["id"] == primary_provider["id"] else fallback
            ),
        )
        events: list[ModelStreamEvent] = []
        with pytest.raises(ProviderError, match="stream interrupted"):
            async for event in gateway.stream(
                ModelRequest(
                    messages=[ModelMessage(role="user", content="test")],
                    max_tokens=20,
                    stream=True,
                ),
                route_role="default",
            ):
                events.append(event)
        assert events[0].content_delta == "partial"

    asyncio.run(run())
    assert fallback.calls == 0


def test_gateway_enforces_provider_concurrency_limit(tmp_path: Path) -> None:
    repository, cipher = _setup(tmp_path)
    provider = _provider(repository, cipher, "bounded", retries=0)
    model = _model(repository, str(provider["id"]), "bounded-model")

    class BoundedProvider(FakeProvider):
        active = 0
        maximum_active = 0

        async def generate(self, request: ModelRequest) -> ModelResponse:
            self.active += 1
            self.maximum_active = max(self.maximum_active, self.active)
            try:
                await asyncio.sleep(0.02)
                return _response("bounded").model_copy(
                    update={"model": request.model}
                )
            finally:
                self.active -= 1

    fake = BoundedProvider("bounded", [_response("bounded")])

    async def run() -> None:
        gateway = ModelGateway(
            repository=repository,
            secret_cipher=cipher,
            provider_factory=lambda *_: fake,
        )
        request = ModelRequest(
            messages=[ModelMessage(role="user", content="test")],
            max_tokens=20,
        )
        await asyncio.gather(
            gateway.generate(request, model_record_id=str(model["id"])),
            gateway.generate(request, model_record_id=str(model["id"])),
        )

    asyncio.run(run())
    assert fake.maximum_active == 1
    assert len(repository.list_invocations()) == 2


def test_gateway_cancellation_releases_request_and_records_it(tmp_path: Path) -> None:
    repository, cipher = _setup(tmp_path)
    provider = _provider(repository, cipher, "cancel", retries=0)
    model = _model(repository, str(provider["id"]), "cancel-model")

    class BlockingProvider(FakeProvider):
        def __init__(self) -> None:
            super().__init__("cancel", [_response("cancel")])
            self.started = asyncio.Event()

        async def generate(self, request: ModelRequest) -> ModelResponse:
            self.started.set()
            await asyncio.Event().wait()
            raise AssertionError("cancelled provider request resumed")

    async def run() -> None:
        fake = BlockingProvider()
        gateway = ModelGateway(
            repository=repository,
            secret_cipher=cipher,
            provider_factory=lambda *_: fake,
        )
        task = asyncio.create_task(
            gateway.generate(
                ModelRequest(
                    messages=[ModelMessage(role="user", content="test")],
                    max_tokens=20,
                ),
                model_record_id=str(model["id"]),
            )
        )
        await fake.started.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    asyncio.run(run())
    invocation = repository.list_invocations(limit=1)[0]
    assert invocation["status"] == "cancelled"
    assert invocation["error_code"] == "cancelled"
