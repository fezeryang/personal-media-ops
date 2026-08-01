from __future__ import annotations

import json
from collections.abc import AsyncIterator
from time import perf_counter

import httpx

from app.models.ai import (
    ModelCapabilities,
    ModelInfo,
    ModelMessage,
    ModelRequest,
    ModelResponse,
    ModelStreamEvent,
    ModelToolCall,
    ModelUsage,
    ProviderHealth,
)
from app.services.ai.providers.base import (
    ModelProvider,
    ProviderError,
    elapsed_ms,
    endpoint,
    iter_sse,
    json_object,
    parse_json_object,
    provider_error_from_response,
    provider_error_from_transport,
    utc_now,
)


class AnthropicCompatibleProvider(ModelProvider):
    def __init__(
        self,
        *,
        provider_id: str,
        provider_name: str,
        base_url: str,
        api_key: str,
        client: httpx.AsyncClient,
        timeout_seconds: float = 60,
    ) -> None:
        self.provider_id = provider_id
        self.provider_name = provider_name
        self.base_url = base_url
        self._api_key = api_key
        self._client = client
        self._timeout_seconds = timeout_seconds

    def _headers(self) -> dict[str, str]:
        return {
            "x-api-key": self._api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

    @staticmethod
    def _message(message: ModelMessage) -> dict[str, object]:
        if message.role == "tool":
            assert message.tool_result is not None
            return {
                "role": "user",
                "content": [
                    {
                        "type": "tool_result",
                        "tool_use_id": message.tool_result.tool_call_id,
                        "content": message.tool_result.content,
                        "is_error": message.tool_result.is_error,
                    }
                ],
            }
        blocks: list[dict[str, object]] = []
        if message.content is not None:
            blocks.append({"type": "text", "text": message.content})
        if message.tool_calls:
            blocks.extend(
                {
                    "type": "tool_use",
                    "id": call.id,
                    "name": call.name,
                    "input": call.arguments,
                }
                for call in message.tool_calls
            )
        return {"role": message.role, "content": blocks}

    @classmethod
    def _body(cls, request: ModelRequest, *, stream: bool) -> dict[str, object]:
        if request.model is None:
            raise ValueError("Model request must resolve a model before provider use")
        body: dict[str, object] = {
            "model": request.model,
            "messages": [cls._message(message) for message in request.messages],
            "max_tokens": request.max_tokens,
            "stream": stream,
        }
        if request.system is not None:
            body["system"] = request.system
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.tools:
            body["tools"] = [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "input_schema": tool.input_schema,
                }
                for tool in request.tools
            ]
        if request.tool_choice is not None and request.tool_choice != "none":
            if request.tool_choice == "auto":
                body["tool_choice"] = {"type": "auto"}
            elif request.tool_choice == "required":
                body["tool_choice"] = {"type": "any"}
            else:
                body["tool_choice"] = {
                    "type": "tool",
                    "name": request.tool_choice,
                }
        if request.tool_choice == "none":
            body.pop("tools", None)
        return body

    @staticmethod
    def _usage(value: object) -> ModelUsage | None:
        if not isinstance(value, dict):
            return None
        return ModelUsage(
            input_tokens=_optional_int(value.get("input_tokens")),
            output_tokens=_optional_int(value.get("output_tokens")),
            cached_tokens=_optional_int(value.get("cache_read_input_tokens")),
            total_tokens=None,
        )

    def _parse_response(self, response: httpx.Response, started: float) -> ModelResponse:
        try:
            payload = json_object(response.json(), context="JSON response")
            blocks = payload.get("content")
            if not isinstance(blocks, list):
                raise TypeError
        except (ValueError, TypeError) as error:
            raise ProviderError(
                code="protocol_error",
                safe_summary="Provider returned an invalid message",
                retryable=False,
            ) from error
        text_parts: list[str] = []
        thinking_parts: list[str] = []
        calls: list[ModelToolCall] = []
        for value in blocks:
            block = json_object(value, context="content block")
            if block.get("type") == "text" and isinstance(block.get("text"), str):
                text_parts.append(str(block["text"]))
            elif block.get("type") == "thinking" and isinstance(
                block.get("thinking"), str
            ):
                thinking_parts.append(str(block["thinking"]))
            elif block.get("type") == "tool_use":
                name = block.get("name")
                if not isinstance(name, str):
                    raise ProviderError(
                        code="protocol_error",
                        safe_summary="Provider returned invalid tool calls",
                        retryable=False,
                    )
                calls.append(
                    ModelToolCall(
                        id=(
                            str(block["id"])
                            if isinstance(block.get("id"), str)
                            else None
                        ),
                        name=name,
                        arguments=json_object(block.get("input"), context="tool input"),
                    )
                )
        return ModelResponse(
            content="".join(text_parts) or None,
            thinking_content="".join(thinking_parts) or None,
            tool_calls=calls or None,
            finish_reason=(
                str(payload["stop_reason"])
                if payload.get("stop_reason") is not None
                else None
            ),
            usage=self._usage(payload.get("usage")),
            provider=self.provider_name,
            model=payload.get("model") if isinstance(payload.get("model"), str) else None,
            request_id=(
                response.headers.get("request-id")
                or response.headers.get("x-request-id")
            ),
            latency_ms=elapsed_ms(started),
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        try:
            response = await self._client.post(
                endpoint(self.base_url, "/v1/messages"),
                headers=self._headers(),
                json=self._body(request, stream=False),
                timeout=request.timeout or self._timeout_seconds,
            )
        except httpx.TransportError as error:
            raise provider_error_from_transport(error) from error
        if response.is_error:
            raise provider_error_from_response(response)
        return self._parse_response(response, started)

    async def stream(self, request: ModelRequest) -> AsyncIterator[ModelStreamEvent]:
        started = perf_counter()
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_buffers: dict[int, dict[str, str | None]] = {}
        model: str | None = None
        finish_reason: str | None = None
        usage_values: dict[str, int] = {}
        request_id: str | None = None
        try:
            async with self._client.stream(
                "POST",
                endpoint(self.base_url, "/v1/messages"),
                headers=self._headers(),
                json=self._body(request, stream=True),
                timeout=request.timeout or self._timeout_seconds,
            ) as response:
                if response.is_error:
                    await response.aread()
                    raise provider_error_from_response(response)
                request_id = response.headers.get("request-id") or response.headers.get(
                    "x-request-id"
                )
                yield ModelStreamEvent(type="start")
                async for event_name, data in iter_sse(response):
                    if event_name == "ping":
                        continue
                    try:
                        event = json_object(json.loads(data), context="stream event")
                    except (json.JSONDecodeError, TypeError) as error:
                        raise ProviderError(
                            code="protocol_error",
                            safe_summary="Provider returned an invalid stream event",
                            retryable=False,
                        ) from error
                    event_type = event.get("type", event_name)
                    if event_type == "error":
                        raise ProviderError(
                            code="provider_error",
                            safe_summary="Provider stream failed",
                            retryable=False,
                        )
                    if event_type == "message_start":
                        message = event.get("message")
                        if isinstance(message, dict):
                            if isinstance(message.get("model"), str):
                                model = str(message["model"])
                            _merge_usage(usage_values, message.get("usage"))
                        continue
                    if event_type == "content_block_start":
                        index = event.get("index")
                        block = event.get("content_block")
                        if (
                            isinstance(index, int)
                            and isinstance(block, dict)
                            and block.get("type") == "tool_use"
                        ):
                            tool_buffers[index] = {
                                "id": (
                                    str(block["id"])
                                    if isinstance(block.get("id"), str)
                                    else None
                                ),
                                "name": (
                                    str(block["name"])
                                    if isinstance(block.get("name"), str)
                                    else ""
                                ),
                                "arguments": "",
                            }
                        continue
                    if event_type == "content_block_delta":
                        index = event.get("index")
                        delta = event.get("delta")
                        if not isinstance(delta, dict):
                            continue
                        if delta.get("type") == "text_delta" and isinstance(
                            delta.get("text"), str
                        ):
                            content_parts.append(str(delta["text"]))
                            yield ModelStreamEvent(
                                type="content_delta",
                                content_delta=str(delta["text"]),
                            )
                        elif delta.get("type") == "thinking_delta" and isinstance(
                            delta.get("thinking"), str
                        ):
                            thinking_parts.append(str(delta["thinking"]))
                            yield ModelStreamEvent(
                                type="thinking_delta",
                                thinking_delta=str(delta["thinking"]),
                            )
                        elif delta.get("type") == "input_json_delta":
                            if not isinstance(index, int) or index not in tool_buffers:
                                raise ProviderError(
                                    code="protocol_error",
                                    safe_summary="Provider returned an invalid tool stream",
                                    retryable=False,
                                )
                            fragment = delta.get("partial_json")
                            if not isinstance(fragment, str):
                                continue
                            buffer = tool_buffers[index]
                            buffer["arguments"] = (buffer["arguments"] or "") + fragment
                            yield ModelStreamEvent(
                                type="tool_call_delta",
                                tool_call_index=index,
                                tool_call_id=buffer["id"],
                                tool_name=buffer["name"],
                                tool_arguments_delta=fragment,
                            )
                        continue
                    if event_type == "message_delta":
                        delta = event.get("delta")
                        if isinstance(delta, dict) and delta.get("stop_reason") is not None:
                            finish_reason = str(delta["stop_reason"])
                        _merge_usage(usage_values, event.get("usage"))
        except httpx.TransportError as error:
            raise provider_error_from_transport(error) from error
        calls: list[ModelToolCall] = []
        for index in sorted(tool_buffers):
            item = tool_buffers[index]
            if not item["name"]:
                raise ProviderError(
                    code="protocol_error",
                    safe_summary="Provider returned an invalid tool stream",
                    retryable=False,
                )
            calls.append(
                ModelToolCall(
                    id=item["id"],
                    name=str(item["name"]),
                    arguments=parse_json_object(
                        item["arguments"] or "{}",
                        context="tool arguments",
                    ),
                )
            )
        yield ModelStreamEvent(
            type="completed",
            response=ModelResponse(
                content="".join(content_parts) or None,
                thinking_content="".join(thinking_parts) or None,
                tool_calls=calls or None,
                finish_reason=finish_reason,
                usage=ModelUsage(
                    input_tokens=usage_values.get("input_tokens"),
                    output_tokens=usage_values.get("output_tokens"),
                    cached_tokens=usage_values.get("cache_read_input_tokens"),
                    total_tokens=None,
                ),
                provider=self.provider_name,
                model=model,
                request_id=request_id,
                latency_ms=elapsed_ms(started),
            ),
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.get(
                endpoint(self.base_url, "/v1/models"),
                headers=self._headers(),
                timeout=self._timeout_seconds,
            )
        except httpx.TransportError as error:
            raise provider_error_from_transport(error) from error
        if response.is_error:
            raise provider_error_from_response(response)
        try:
            payload = json_object(response.json(), context="model list")
            data = payload.get("data")
            if not isinstance(data, list):
                raise TypeError
            return [
                ModelInfo(
                    model_id=str(item["id"]),
                    display_name=(
                        str(item["display_name"])
                        if isinstance(item.get("display_name"), str)
                        else str(item["id"])
                    ),
                )
                for item in data
                if isinstance(item, dict) and isinstance(item.get("id"), str)
            ]
        except (ValueError, TypeError) as error:
            raise ProviderError(
                code="protocol_error",
                safe_summary="Provider returned an invalid model list",
                retryable=False,
            ) from error

    async def health_check(self) -> ProviderHealth:
        started = perf_counter()
        try:
            await self.list_models()
        except ProviderError as error:
            return ProviderHealth(
                status=error.health_status,
                checked_at=utc_now(),
                latency_ms=elapsed_ms(started),
                error_code=error.code,
                error_summary=error.safe_summary,
            )
        return ProviderHealth(
            status="healthy",
            checked_at=utc_now(),
            latency_ms=elapsed_ms(started),
        )

    def capabilities(self, model_id: str) -> ModelCapabilities:
        return ModelCapabilities()


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _merge_usage(target: dict[str, int], value: object) -> None:
    if not isinstance(value, dict):
        return
    for key in ("input_tokens", "output_tokens", "cache_read_input_tokens"):
        parsed = _optional_int(value.get(key))
        if parsed is not None:
            target[key] = parsed
