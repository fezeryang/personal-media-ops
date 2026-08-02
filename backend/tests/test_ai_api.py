from __future__ import annotations

import sqlite3
from collections.abc import AsyncIterator

from fastapi.testclient import TestClient

from app.models.ai import (
    ModelCapabilities,
    ModelInfo,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelToolCall,
    ModelUsage,
    ProviderHealth,
)
from app.services.ai.providers import ModelProvider

PROVIDER_PAYLOAD = {
    "name": "Custom OpenAI",
    "provider_type": "custom_openai",
    "protocol": "openai_compatible",
    "base_url": "https://models.example.test/v1",
    "enabled": True,
    "timeout_seconds": 30,
    "max_retries": 1,
    "concurrency_limit": 2,
}


class AdminFakeProvider(ModelProvider):
    provider_id = "fake-provider"
    provider_name = "Fake provider"

    async def health_check(self) -> ProviderHealth:
        return ProviderHealth(
            status="healthy",
            checked_at="2026-08-01T00:00:00Z",
            latency_ms=4,
        )

    async def list_models(self) -> list[ModelInfo]:
        return [
            ModelInfo(model_id="candidate-a", display_name="Candidate A"),
            ModelInfo(model_id="candidate-b", display_name="Candidate B"),
        ]

    async def generate(self, request: ModelRequest) -> ModelResponse:
        calls = None
        thinking = None
        finish_reason = "stop"
        if request.tools:
            calls = [
                ModelToolCall(
                    id="call-1",
                    name=request.tools[0].name,
                    arguments={"status": "ok"},
                )
            ]
            finish_reason = "tool_calls"
        if request.metadata.get("check_kind") == "thinking":
            thinking = "brief thought"
        return ModelResponse(
            content="OK",
            thinking_content=thinking,
            tool_calls=calls,
            finish_reason=finish_reason,
            usage=ModelUsage(input_tokens=4, output_tokens=1, cached_tokens=None),
            provider=self.provider_name,
            model=request.model,
            request_id="request-fake",
            latency_ms=5,
        )

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        yield ModelStreamEvent(type="content_delta", content_delta="O")
        yield ModelStreamEvent(type="content_delta", content_delta="K")
        yield ModelStreamEvent(type="completed", response=await self.generate(request))

    def capabilities(self, model_id: str) -> ModelCapabilities:
        return ModelCapabilities()


def _create_provider(
    client: TestClient,
    *,
    with_secret: bool = True,
    name: str = "Custom OpenAI",
) -> dict[str, object]:
    payload = dict(PROVIDER_PAYLOAD)
    payload["name"] = name
    if with_secret:
        payload["api_key"] = "synthetic-provider-secret"
    response = client.post("/api/ai/providers", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def _create_model(client: TestClient, provider_id: str) -> dict[str, object]:
    response = client.post(
        "/api/ai/models",
        json={
            "provider_id": provider_id,
            "model_id": "model-a",
            "display_name": "Model A",
            "enabled": True,
            "context_window": 128_000,
            "max_output_tokens": 4_096,
            "supports_streaming": True,
            "supports_tools": True,
            "supports_thinking": None,
            "supports_vision": False,
            "supports_files": False,
            "supports_structured_output": True,
            "capabilities_source": "user",
            "input_price_per_million": None,
            "output_price_per_million": None,
            "cached_input_price_per_million": None,
            "price_currency": None,
            "price_effective_at": None,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_provider_crud_encrypts_secret_and_never_returns_secret(client: TestClient) -> None:
    provider = _create_provider(client)

    assert provider["credentials_configured"] is True
    assert "api_key" not in provider
    assert "encrypted_api_key" not in provider
    assert "nonce" not in provider
    assert "master" not in str(provider).lower()
    listed = client.get("/api/ai/providers")
    detail = client.get(f"/api/ai/providers/{provider['id']}")
    assert listed.status_code == detail.status_code == 200
    combined = listed.text + detail.text
    assert "synthetic-provider-secret" not in combined
    assert "encrypted_api_key" not in combined
    assert "nonce" not in combined

    with sqlite3.connect(client.app.state.settings.database_path) as connection:
        stored = connection.execute(
            """
            SELECT encrypted_api_key, nonce, key_version
            FROM ai_provider_secrets WHERE provider_id = ?
            """,
            (provider["id"],),
        ).fetchone()
    assert stored is not None
    assert b"synthetic-provider-secret" not in bytes(stored[0])
    assert len(bytes(stored[1])) == 12
    assert stored[2] == 1

    update = dict(PROVIDER_PAYLOAD)
    update["name"] = "Renamed provider"
    update["api_key"] = None
    update["clear_api_key"] = False
    updated = client.put(f"/api/ai/providers/{provider['id']}", json=update)
    assert updated.status_code == 200
    assert updated.json()["name"] == "Renamed provider"
    assert updated.json()["credentials_configured"] is True

    unconfigured = _create_provider(
        client,
        with_secret=False,
        name="Unconfigured provider",
    )
    assert unconfigured["credentials_configured"] is False
    deleted = client.delete(f"/api/ai/providers/{unconfigured['id']}")
    assert deleted.status_code == 204


def test_provider_templates_have_no_models_prices_or_keys(client: TestClient) -> None:
    response = client.get("/api/ai/provider-templates")

    assert response.status_code == 200
    templates = response.json()
    assert {item["id"] for item in templates} == {
        "minimax",
        "deepseek",
        "glm",
        "anthropic",
        "openai",
        "custom_anthropic",
        "custom_openai",
    }
    encoded = response.text.lower()
    assert "api_key" not in encoded
    assert "price" not in encoded
    assert "models" not in encoded


def test_billing_profiles_and_versioned_prices_are_owner_visible(client: TestClient) -> None:
    profile = client.post(
        "/api/ai/billing-profiles",
        json={
            "name": "MiniMax 年度套餐测试",
            "vendor": "MiniMax",
            "billing_mode": "subscription_fixed",
            "package_name": "年度专业版",
            "purchase_amount": "999",
            "currency": "cny",
            "starts_at": "2026-01-01T00:00:00Z",
            "ends_at": "2026-12-31T23:59:59Z",
            "quota_description": "年度订阅额度",
            "token_quota": 1000000,
            "call_limit": 1000,
            "concurrency_limit": 1,
        },
    )
    assert profile.status_code == 201, profile.text
    assert profile.json()["currency"] == "CNY"
    assert any(item["vendor"] == "MiniMax" for item in client.get("/api/ai/billing-profiles").json())

    provider = _create_provider(client, name="DeepSeek 官方")
    model = _create_model(client, str(provider["id"]))
    price = client.post(
        "/api/ai/provider-prices",
        json={
            "provider_id": provider["id"],
            "model_record_id": model["id"],
            "model_id": "model-a",
            "input_price_per_million": "0.27",
            "output_price_per_million": "1.10",
            "cached_input_price_per_million": "0.07",
            "cache_write_price_per_million": "0.50",
            "currency": "usd",
            "effective_at": "2026-08-01T00:00:00Z",
            "source": "official-price-config",
        },
    )
    assert price.status_code == 201, price.text
    assert price.json()["currency"] == "USD"
    assert client.get("/api/ai/provider-prices").json()[0]["source"] == "official-price-config"

    invalid_price_model = dict(
        PROVIDER_PAYLOAD,
        api_key=None,
    )
    invalid_price_model["name"] = "Invalid price provider"
    created = client.post("/api/ai/providers", json=invalid_price_model)
    assert created.status_code == 201
    invalid_model = {
        "provider_id": created.json()["id"],
        "model_id": "invalid-price-model",
        "display_name": "Invalid price model",
        "enabled": False,
        "context_window": 1000,
        "max_output_tokens": 100,
        "supports_streaming": True,
        "supports_tools": False,
        "supports_thinking": None,
        "supports_vision": None,
        "supports_files": None,
        "supports_structured_output": None,
        "capabilities_source": "user",
        "input_price_per_million": "1",
        "output_price_per_million": None,
        "cached_input_price_per_million": None,
        "cache_write_price_per_million": None,
        "price_currency": None,
        "price_effective_at": None,
    }
    assert client.post("/api/ai/models", json=invalid_model).status_code == 422


def test_model_and_routes_require_enabled_records_and_guard_deletion(
    client: TestClient,
) -> None:
    provider = _create_provider(client)
    model = _create_model(client, str(provider["id"]))

    routes = client.put(
        "/api/ai/routes",
        json={
            "routes": {
                "default": model["id"],
                "fast": model["id"],
                "deep": None,
                "tool_calling": model["id"],
                "final_report": None,
                "fallback": model["id"],
            }
        },
    )
    assert routes.status_code == 200
    assert next(item for item in routes.json() if item["role"] == "default")[
        "model_id"
    ] == "model-a"
    assert client.delete(f"/api/ai/models/{model['id']}").status_code == 409
    assert client.delete(f"/api/ai/providers/{provider['id']}").status_code == 409

    disabled_payload = dict(PROVIDER_PAYLOAD)
    disabled_payload.update(
        {"enabled": False, "api_key": None, "clear_api_key": False}
    )
    assert (
        client.put(f"/api/ai/providers/{provider['id']}", json=disabled_payload).status_code
        == 409
    )
    assert client.put(
        "/api/ai/routes",
        json={
            "routes": {
                "default": None,
                "fast": None,
                "deep": None,
                "tool_calling": None,
                "final_report": None,
                "fallback": None,
            }
        },
    ).status_code == 200
    assert (
        client.put(f"/api/ai/providers/{provider['id']}", json=disabled_payload).status_code
        == 200
    )
    invalid_route = client.put(
        "/api/ai/routes",
        json={"routes": {"default": model["id"]}},
    )
    assert invalid_route.status_code == 409


def test_refresh_candidates_does_not_create_or_enable_models(client: TestClient) -> None:
    provider = _create_provider(client)
    client.app.state.model_gateway._provider_factory = lambda *_: AdminFakeProvider()

    refreshed = client.post(f"/api/ai/providers/{provider['id']}/refresh-models")

    assert refreshed.status_code == 200
    assert [item["model_id"] for item in refreshed.json()] == [
        "candidate-a",
        "candidate-b",
    ]
    assert client.get("/api/ai/models").json() == []


def test_connection_capabilities_are_tested_independently(client: TestClient) -> None:
    provider = _create_provider(client)
    model = _create_model(client, str(provider["id"]))
    client.app.state.model_gateway._provider_factory = lambda *_: AdminFakeProvider()

    text = client.post(
        f"/api/ai/providers/{provider['id']}/test",
        json={"model_record_id": model["id"], "check_kind": "text"},
    )
    stream = client.post(
        f"/api/ai/providers/{provider['id']}/test",
        json={"model_record_id": model["id"], "check_kind": "streaming"},
    )
    tools = client.post(
        f"/api/ai/providers/{provider['id']}/test",
        json={"model_record_id": model["id"], "check_kind": "tools"},
    )
    thinking = client.post(
        f"/api/ai/providers/{provider['id']}/test",
        json={"model_record_id": model["id"], "check_kind": "thinking"},
    )

    assert text.json()["status"] == "healthy"
    assert stream.json()["status"] == "healthy"
    assert tools.json()["status"] == "healthy"
    assert thinking.json()["status"] == "healthy"
    history = client.get("/api/ai/health")
    assert history.status_code == 200
    assert {item["check_kind"] for item in history.json()} >= {
        "text",
        "streaming",
        "tools",
        "thinking",
    }


def test_usage_empty_then_debug_records_real_tokens_and_unknown_cost(
    client: TestClient,
) -> None:
    empty = client.get("/api/ai/usage")
    assert empty.status_code == 200
    assert empty.json()["totals"]["invocation_count"] == 0
    assert empty.json()["totals"]["estimated_cost"] is None

    provider = _create_provider(client)
    model = _create_model(client, str(provider["id"]))
    client.app.state.model_gateway._provider_factory = lambda *_: AdminFakeProvider()
    routes = client.put(
        "/api/ai/routes",
        json={"routes": {"default": model["id"], "fallback": model["id"]}},
    )
    assert routes.status_code == 200
    debug = client.post(
        "/api/ai/debug",
        json={
            "message": "Reply briefly",
            "route_role": "default",
            "model_record_id": None,
            "stream": False,
        },
    )
    assert debug.status_code == 200, debug.text
    payload = debug.json()
    assert payload["response"]["content"] == "OK"
    assert payload["response"]["usage"] == {
        "input_tokens": 4,
        "output_tokens": 1,
        "cached_tokens": None,
        "total_tokens": None,
    }
    assert payload["fallback_used"] is False

    usage = client.get("/api/ai/usage").json()
    assert usage["totals"]["invocation_count"] == 1
    assert usage["totals"]["input_tokens"] == 4
    assert usage["totals"]["output_tokens"] == 1
    assert usage["totals"]["estimated_cost"] is None
    assert usage["totals"]["uncosted_invocation_count"] == 1
    assert len(usage["recent_invocations"]) == 1


def test_ai_api_requires_owner_session_and_csrf(test_settings) -> None:
    from pathlib import Path

    from app.main import create_app
    from app.repositories.auth import AuthRepository
    from app.security.passwords import hash_password
    from tests.alembic_utils import run_alembic_command

    run_alembic_command(test_settings.database_path, "upgrade", "head")
    key_path = Path(test_settings.model_gateway_master_key_path)
    key_path.parent.mkdir(mode=0o700)
    key_path.write_bytes(b"k" * 32)
    key_path.chmod(0o600)
    with TestClient(create_app(test_settings)) as anonymous:
        assert anonymous.get("/api/ai/providers").status_code == 401
        assert anonymous.get("/api/ai/usage").status_code == 401
        assert anonymous.post("/api/ai/providers", json=PROVIDER_PAYLOAD).status_code == 401

        AuthRepository(test_settings.database_path).create_owner(
            username="ai-owner",
            password_hash=hash_password("ai-owner-password"),
        )
        login = anonymous.post(
            "/api/auth/login",
            json={"username": "ai-owner", "password": "ai-owner-password"},
            headers={"Origin": "http://testserver"},
        )
        assert login.status_code == 200
        missing_csrf = anonymous.post(
            "/api/ai/providers",
            json=PROVIDER_PAYLOAD,
            headers={"Origin": "http://testserver"},
        )
        assert missing_csrf.status_code == 403
        assert missing_csrf.json()["detail"] == "CSRF validation failed"


def test_debug_stream_returns_sse_and_releases_response(client: TestClient) -> None:
    provider = _create_provider(client)
    model = _create_model(client, str(provider["id"]))
    client.app.state.model_gateway._provider_factory = lambda *_: AdminFakeProvider()
    assert client.put(
        "/api/ai/routes",
        json={"routes": {"default": model["id"]}},
    ).status_code == 200

    with client.stream(
        "POST",
        "/api/ai/debug",
        json={
            "message": "Reply briefly",
            "route_role": "default",
            "model_record_id": None,
            "stream": True,
        },
    ) as response:
        body = "".join(response.iter_text())

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type":"content_delta"' in body
    assert '"type":"completed"' in body
