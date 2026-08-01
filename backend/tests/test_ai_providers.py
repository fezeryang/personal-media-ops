import asyncio
import json
from collections.abc import Callable

import httpx
import pytest

from app.models.ai import (
    ModelMessage,
    ModelRequest,
    ModelToolCall,
    ModelToolDefinition,
    ModelToolResult,
)
from app.services.ai.providers import (
    AnthropicCompatibleProvider,
    OpenAICompatibleProvider,
    ProviderError,
)


def _synthetic_key(*parts: str) -> str:
    return "-".join(parts)


SYNTHETIC_API_KEY = _synthetic_key("synthetic", "key")


def _request(*, stream: bool = False) -> ModelRequest:
    return ModelRequest(
        system="Be concise.",
        messages=[
            ModelMessage(role="user", content="Use the status tool."),
            ModelMessage(
                role="assistant",
                tool_calls=[
                    ModelToolCall(
                        id="call-prior",
                        name="status",
                        arguments={"value": "prior"},
                    )
                ],
            ),
            ModelMessage(
                role="tool",
                tool_result=ModelToolResult(
                    tool_call_id="call-prior",
                    content='{"ok":true}',
                ),
            ),
        ],
        model="model-a",
        temperature=0.2,
        max_tokens=64,
        stream=stream,
        tools=[
            ModelToolDefinition(
                name="status",
                description="Return a status value",
                input_schema={
                    "type": "object",
                    "properties": {"value": {"type": "string"}},
                    "required": ["value"],
                },
            )
        ],
        tool_choice="required",
        metadata={"correlation_id": "safe-metadata"},
        timeout=10,
    )


def _client(handler: Callable[[httpx.Request], httpx.Response]) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.MockTransport(handler))


def test_openai_request_and_response_are_normalized() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["authorization"] = request.headers.get("authorization")
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"x-request-id": "req-openai"},
            json={
                "model": "model-a-snapshot",
                "choices": [
                    {
                        "message": {
                            "content": "done",
                            "reasoning_content": "brief thought",
                            "tool_calls": [
                                {
                                    "id": "call-1",
                                    "type": "function",
                                    "function": {
                                        "name": "status",
                                        "arguments": '{"value":"ok"}',
                                    },
                                }
                            ],
                        },
                        "finish_reason": "tool_calls",
                    }
                ],
                "usage": {
                    "prompt_tokens": 12,
                    "completion_tokens": 4,
                    "prompt_tokens_details": {"cached_tokens": 3},
                },
            },
        )

    async def run() -> None:
        async with _client(handler) as client:
            provider = OpenAICompatibleProvider(
                provider_id="provider-openai",
                provider_name="Compatible OpenAI",
                base_url="https://example.test/v1/",
                api_key=SYNTHETIC_API_KEY,
                client=client,
            )
            response = await provider.generate(_request())
        assert response.content == "done"
        assert response.thinking_content == "brief thought"
        assert response.finish_reason == "tool_calls"
        assert response.request_id == "req-openai"
        assert response.model == "model-a-snapshot"
        assert response.usage is not None
        assert response.usage.input_tokens == 12
        assert response.usage.output_tokens == 4
        assert response.usage.cached_tokens == 3
        assert response.tool_calls == [
            ModelToolCall(
                id="call-1",
                name="status",
                arguments={"value": "ok"},
            )
        ]

    asyncio.run(run())
    assert observed["url"] == "https://example.test/v1/chat/completions"
    assert observed["authorization"] == "Bearer synthetic-key"
    body = observed["body"]
    assert isinstance(body, dict)
    assert body["stream"] is False
    assert body["tool_choice"] == "required"
    assert body["tools"][0]["function"]["parameters"]["required"] == ["value"]
    assert body["messages"][0] == {"role": "system", "content": "Be concise."}
    assert body["messages"][-1]["role"] == "tool"
    assert "metadata" not in body


def test_openai_compatible_preserves_provider_version_prefix() -> None:
    observed: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        observed.append(str(request.url))
        return httpx.Response(
            200,
            json={
                "model": "glm-model",
                "choices": [
                    {"message": {"content": "OK"}, "finish_reason": "stop"}
                ],
            },
        )

    async def run() -> None:
        async with _client(handler) as client:
            provider = OpenAICompatibleProvider(
                provider_id="provider-glm",
                provider_name="GLM",
                base_url="https://example.test/api/paas/v4",
                api_key=SYNTHETIC_API_KEY,
                client=client,
            )
            await provider.generate(_request())

    asyncio.run(run())
    assert observed == ["https://example.test/api/paas/v4/chat/completions"]


def test_anthropic_request_and_response_are_normalized() -> None:
    observed: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        observed["url"] = str(request.url)
        observed["api_key"] = request.headers.get("x-api-key")
        observed["version"] = request.headers.get("anthropic-version")
        observed["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            headers={"request-id": "req-anthropic"},
            json={
                "model": "model-a-snapshot",
                "content": [
                    {"type": "thinking", "thinking": "brief thought"},
                    {"type": "text", "text": "done"},
                    {
                        "type": "tool_use",
                        "id": "call-1",
                        "name": "status",
                        "input": {"value": "ok"},
                    },
                ],
                "stop_reason": "tool_use",
                "usage": {
                    "input_tokens": 12,
                    "output_tokens": 4,
                    "cache_read_input_tokens": 3,
                },
            },
        )

    async def run() -> None:
        async with _client(handler) as client:
            provider = AnthropicCompatibleProvider(
                provider_id="provider-anthropic",
                provider_name="Compatible Anthropic",
                base_url="https://example.test",
                api_key=SYNTHETIC_API_KEY,
                client=client,
            )
            response = await provider.generate(_request())
        assert response.content == "done"
        assert response.thinking_content == "brief thought"
        assert response.request_id == "req-anthropic"
        assert response.finish_reason == "tool_use"
        assert response.tool_calls is not None
        assert response.tool_calls[0].arguments == {"value": "ok"}
        assert response.usage is not None
        assert response.usage.cached_tokens == 3

    asyncio.run(run())
    assert observed["url"] == "https://example.test/v1/messages"
    assert observed["api_key"] == "synthetic-key"
    assert observed["version"] == "2023-06-01"
    body = observed["body"]
    assert isinstance(body, dict)
    assert body["system"] == "Be concise."
    assert body["tool_choice"] == {"type": "any"}
    assert body["tools"][0]["input_schema"]["required"] == ["value"]
    assert body["messages"][-1]["content"][0]["type"] == "tool_result"


def test_anthropic_normalizes_string_content_and_base_response_errors() -> None:
    responses = [
        httpx.Response(
            200,
            json={
                "model": "model-a",
                "content": "done",
                "stop_reason": "end_turn",
                "base_resp": {"status_code": 0},
            },
        ),
        httpx.Response(
            200,
            json={
                "base_resp": {"status_code": 1039, "status_msg": "too large"},
            },
        ),
    ]

    def handler(_: httpx.Request) -> httpx.Response:
        return responses.pop(0)

    async def run() -> None:
        async with _client(handler) as client:
            provider = AnthropicCompatibleProvider(
                provider_id="provider-anthropic",
                provider_name="Compatible Anthropic",
                base_url="https://example.test",
                api_key=SYNTHETIC_API_KEY,
                client=client,
            )
            response = await provider.generate(_request())
            assert response.content == "done"
            with pytest.raises(ProviderError) as captured:
                await provider.generate(_request())
        assert captured.value.code == "protocol_error"
        assert captured.value.retryable is False
        assert captured.value.safe_summary == "Provider returned error code 1039"

    asyncio.run(run())


@pytest.mark.parametrize(
    ("provider_type", "content_type", "body", "expected"),
    [
        (
            "openai",
            "text/event-stream",
            """data: {\"id\":\"chunk\",\"model\":\"model-a\",\"choices\":[{\"delta\":{\"content\":\"hi\",\"tool_calls\":[{\"index\":0,\"id\":\"call-1\",\"function\":{\"name\":\"status\",\"arguments\":\"{\\\"value\\\":\"}}]},\"finish_reason\":null}]}\n\ndata: {\"model\":\"model-a\",\"choices\":[{\"delta\":{\"tool_calls\":[{\"index\":0,\"function\":{\"arguments\":\"\\\"ok\\\"}\"}}]},\"finish_reason\":\"tool_calls\"}],\"usage\":{\"prompt_tokens\":2,\"completion_tokens\":1}}\n\ndata: [DONE]\n\n""",
            ("hi", {"value": "ok"}, "tool_calls"),
        ),
        (
            "anthropic",
            "text/event-stream",
            """event: message_start\ndata: {\"type\":\"message_start\",\"message\":{\"model\":\"model-a\",\"usage\":{\"input_tokens\":2,\"output_tokens\":0}}}\n\nevent: content_block_start\ndata: {\"type\":\"content_block_start\",\"index\":0,\"content_block\":{\"type\":\"text\",\"text\":\"\"}}\n\nevent: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"index\":0,\"delta\":{\"type\":\"text_delta\",\"text\":\"hi\"}}\n\nevent: content_block_start\ndata: {\"type\":\"content_block_start\",\"index\":1,\"content_block\":{\"type\":\"tool_use\",\"id\":\"call-1\",\"name\":\"status\",\"input\":{}}}\n\nevent: content_block_delta\ndata: {\"type\":\"content_block_delta\",\"index\":1,\"delta\":{\"type\":\"input_json_delta\",\"partial_json\":\"{\\\"value\\\":\\\"ok\\\"}\"}}\n\nevent: message_delta\ndata: {\"type\":\"message_delta\",\"delta\":{\"stop_reason\":\"tool_use\"},\"usage\":{\"output_tokens\":1}}\n\nevent: message_stop\ndata: {\"type\":\"message_stop\"}\n\n""",
            ("hi", {"value": "ok"}, "tool_use"),
        ),
    ],
)
def test_streams_normalize_text_tools_finish_and_usage(
    provider_type: str,
    content_type: str,
    body: str,
    expected: tuple[str, dict[str, str], str],
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, headers={"content-type": content_type}, text=body)

    async def run() -> None:
        async with _client(handler) as client:
            provider_class = (
                OpenAICompatibleProvider
                if provider_type == "openai"
                else AnthropicCompatibleProvider
            )
            provider = provider_class(
                provider_id=f"provider-{provider_type}",
                provider_name=provider_type,
                base_url="https://example.test/v1"
                if provider_type == "openai"
                else "https://example.test",
                api_key=SYNTHETIC_API_KEY,
                client=client,
            )
            events = [event async for event in provider.stream(_request(stream=True))]
        completed = next(event for event in events if event.type == "completed")
        assert completed.response is not None
        assert completed.response.content == expected[0]
        assert completed.response.tool_calls is not None
        assert completed.response.tool_calls[0].arguments == expected[1]
        assert completed.response.finish_reason == expected[2]
        assert completed.response.usage is not None
        assert completed.response.usage.input_tokens == 2
        assert completed.response.usage.output_tokens == 1

    asyncio.run(run())


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [(401, "authentication_failed", False), (404, "model_not_found", False), (429, "rate_limited", True), (503, "provider_error", True)],
)
def test_provider_http_errors_are_sanitized(
    status: int,
    code: str,
    retryable: bool,
) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            status,
            json={"error": {"message": "secret sk-sensitive upstream detail"}},
        )

    async def run() -> None:
        async with _client(handler) as client:
            provider = OpenAICompatibleProvider(
                provider_id="provider-openai",
                provider_name="OpenAI",
                base_url="https://example.test/v1",
                api_key=SYNTHETIC_API_KEY,
                client=client,
            )
            with pytest.raises(ProviderError) as captured:
                await provider.generate(_request())
        assert captured.value.code == code
        assert captured.value.retryable is retryable
        assert "sensitive" not in captured.value.safe_summary

    asyncio.run(run())
