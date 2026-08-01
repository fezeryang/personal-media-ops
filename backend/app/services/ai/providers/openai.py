from __future__ import annotations

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


class OpenAICompatibleProvider(ModelProvider):
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
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }

    @staticmethod
    def _message(message: ModelMessage) -> dict[str, object]:
        if message.role == "tool":
            assert message.tool_result is not None
            return {
                "role": "tool",
                "tool_call_id": message.tool_result.tool_call_id,
                "content": message.tool_result.content,
            }
        result: dict[str, object] = {
            "role": message.role,
            "content": message.content,
        }
        if message.tool_calls:
            result["tool_calls"] = [
                {
                    "id": call.id,
                    "type": "function",
                    "function": {
                        "name": call.name,
                        "arguments": _compact_json(call.arguments),
                    },
                }
                for call in message.tool_calls
            ]
        return result

    @classmethod
    def _body(cls, request: ModelRequest, *, stream: bool) -> dict[str, object]:
        if request.model is None:
            raise ValueError("Model request must resolve a model before provider use")
        messages: list[dict[str, object]] = []
        if request.system is not None:
            messages.append({"role": "system", "content": request.system})
        messages.extend(cls._message(message) for message in request.messages)
        body: dict[str, object] = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "stream": stream,
        }
        if request.temperature is not None:
            body["temperature"] = request.temperature
        if request.tools:
            body["tools"] = [
                {
                    "type": "function",
                    "function": {
                        "name": tool.name,
                        "description": tool.description,
                        "parameters": tool.input_schema,
                    },
                }
                for tool in request.tools
            ]
        if request.tool_choice is not None:
            if request.tool_choice in {"auto", "none", "required"}:
                body["tool_choice"] = request.tool_choice
            else:
                body["tool_choice"] = {
                    "type": "function",
                    "function": {"name": request.tool_choice},
                }
        return body

    @staticmethod
    def _usage(value: object) -> ModelUsage | None:
        if not isinstance(value, dict):
            return None
        details = value.get("prompt_tokens_details")
        cached = details.get("cached_tokens") if isinstance(details, dict) else None
        return ModelUsage(
            input_tokens=_optional_int(value.get("prompt_tokens")),
            output_tokens=_optional_int(value.get("completion_tokens")),
            cached_tokens=_optional_int(cached),
            total_tokens=_optional_int(value.get("total_tokens")),
        )

    def _parse_response(self, response: httpx.Response, started: float) -> ModelResponse:
        try:
            payload = json_object(response.json(), context="JSON response")
            choices = payload.get("choices")
            if not isinstance(choices, list) or not choices:
                raise ValueError
            choice = json_object(choices[0], context="choice")
            message = json_object(choice.get("message"), context="message")
        except (ValueError, TypeError) as error:
            raise ProviderError(
                code="protocol_error",
                safe_summary="Provider returned an invalid chat completion",
                retryable=False,
            ) from error
        calls = _parse_tool_calls(message.get("tool_calls"))
        content = message.get("content")
        thinking = message.get("reasoning_content", message.get("reasoning"))
        return ModelResponse(
            content=content if isinstance(content, str) else None,
            thinking_content=thinking if isinstance(thinking, str) else None,
            tool_calls=calls or None,
            finish_reason=(
                str(choice["finish_reason"])
                if choice.get("finish_reason") is not None
                else None
            ),
            usage=self._usage(payload.get("usage")),
            provider=self.provider_name,
            model=payload.get("model") if isinstance(payload.get("model"), str) else None,
            request_id=response.headers.get("x-request-id"),
            latency_ms=elapsed_ms(started),
        )

    async def generate(self, request: ModelRequest) -> ModelResponse:
        started = perf_counter()
        try:
            response = await self._client.post(
                endpoint(self.base_url, "/chat/completions"),
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
        body = self._body(request, stream=True)
        content_parts: list[str] = []
        thinking_parts: list[str] = []
        tool_buffers: dict[int, dict[str, str | None]] = {}
        finish_reason: str | None = None
        usage: ModelUsage | None = None
        response_model: str | None = None
        request_id: str | None = None
        try:
            async with self._client.stream(
                "POST",
                endpoint(self.base_url, "/chat/completions"),
                headers=self._headers(),
                json=body,
                timeout=request.timeout or self._timeout_seconds,
            ) as response:
                if response.is_error:
                    await response.aread()
                    raise provider_error_from_response(response)
                request_id = response.headers.get("x-request-id")
                yield ModelStreamEvent(type="start")
                async for _, data in iter_sse(response):
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json_object(
                            __import__("json").loads(data),
                            context="stream event",
                        )
                    except (ValueError, TypeError) as error:
                        raise ProviderError(
                            code="protocol_error",
                            safe_summary="Provider returned an invalid stream event",
                            retryable=False,
                        ) from error
                    if isinstance(chunk.get("model"), str):
                        response_model = str(chunk["model"])
                    usage = self._usage(chunk.get("usage")) or usage
                    choices = chunk.get("choices")
                    if not isinstance(choices, list) or not choices:
                        continue
                    choice = json_object(choices[0], context="stream choice")
                    if choice.get("finish_reason") is not None:
                        finish_reason = str(choice["finish_reason"])
                    delta = choice.get("delta")
                    if not isinstance(delta, dict):
                        continue
                    content = delta.get("content")
                    if isinstance(content, str) and content:
                        content_parts.append(content)
                        yield ModelStreamEvent(
                            type="content_delta",
                            content_delta=content,
                        )
                    thinking = delta.get("reasoning_content", delta.get("reasoning"))
                    if isinstance(thinking, str) and thinking:
                        thinking_parts.append(thinking)
                        yield ModelStreamEvent(
                            type="thinking_delta",
                            thinking_delta=thinking,
                        )
                    delta_calls = delta.get("tool_calls")
                    if isinstance(delta_calls, list):
                        for raw_call in delta_calls:
                            if not isinstance(raw_call, dict):
                                continue
                            index = raw_call.get("index")
                            if not isinstance(index, int) or index < 0:
                                raise ProviderError(
                                    code="protocol_error",
                                    safe_summary="Provider returned an invalid tool stream",
                                    retryable=False,
                                )
                            buffer = tool_buffers.setdefault(
                                index,
                                {"id": None, "name": "", "arguments": ""},
                            )
                            if isinstance(raw_call.get("id"), str):
                                buffer["id"] = raw_call["id"]
                            function = raw_call.get("function")
                            name_delta: str | None = None
                            argument_delta: str | None = None
                            if isinstance(function, dict):
                                if isinstance(function.get("name"), str):
                                    name_delta = function["name"]
                                    buffer["name"] = (buffer["name"] or "") + name_delta
                                if isinstance(function.get("arguments"), str):
                                    argument_delta = function["arguments"]
                                    buffer["arguments"] = (
                                        buffer["arguments"] or ""
                                    ) + argument_delta
                            yield ModelStreamEvent(
                                type="tool_call_delta",
                                tool_call_index=index,
                                tool_call_id=(
                                    str(buffer["id"]) if buffer["id"] else None
                                ),
                                tool_name=name_delta,
                                tool_arguments_delta=argument_delta,
                            )
        except httpx.TransportError as error:
            raise provider_error_from_transport(error) from error
        calls = _tool_buffers(tool_buffers)
        yield ModelStreamEvent(
            type="completed",
            response=ModelResponse(
                content="".join(content_parts) or None,
                thinking_content="".join(thinking_parts) or None,
                tool_calls=calls or None,
                finish_reason=finish_reason,
                usage=usage,
                provider=self.provider_name,
                model=response_model,
                request_id=request_id,
                latency_ms=elapsed_ms(started),
            ),
        )

    async def list_models(self) -> list[ModelInfo]:
        try:
            response = await self._client.get(
                endpoint(self.base_url, "/models"),
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
                ModelInfo(model_id=str(item["id"]), display_name=str(item["id"]))
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


def _compact_json(value: dict[str, object]) -> str:
    return __import__("json").dumps(value, separators=(",", ":"), ensure_ascii=False)


def _optional_int(value: object) -> int | None:
    return value if isinstance(value, int) and value >= 0 else None


def _parse_tool_calls(value: object) -> list[ModelToolCall]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ProviderError(
            code="protocol_error",
            safe_summary="Provider returned invalid tool calls",
            retryable=False,
        )
    result: list[ModelToolCall] = []
    for item in value:
        call = json_object(item, context="tool call")
        function = json_object(call.get("function"), context="tool function")
        name = function.get("name")
        arguments = function.get("arguments")
        if not isinstance(name, str) or not isinstance(arguments, str):
            raise ProviderError(
                code="protocol_error",
                safe_summary="Provider returned invalid tool calls",
                retryable=False,
            )
        result.append(
            ModelToolCall(
                id=call.get("id") if isinstance(call.get("id"), str) else None,
                name=name,
                arguments=parse_json_object(arguments, context="tool arguments"),
            )
        )
    return result


def _tool_buffers(buffers: dict[int, dict[str, str | None]]) -> list[ModelToolCall]:
    result: list[ModelToolCall] = []
    for index in sorted(buffers):
        item = buffers[index]
        name = item.get("name")
        if not name:
            raise ProviderError(
                code="protocol_error",
                safe_summary="Provider returned an invalid tool stream",
                retryable=False,
            )
        result.append(
            ModelToolCall(
                id=item.get("id"),
                name=name,
                arguments=parse_json_object(
                    item.get("arguments") or "{}",
                    context="tool arguments",
                ),
            )
        )
    return result
