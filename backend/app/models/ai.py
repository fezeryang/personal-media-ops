from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, JsonValue, model_validator

ProviderProtocol = Literal["anthropic_compatible", "openai_compatible"]
ProviderHealthStatus = Literal[
    "healthy",
    "degraded",
    "unreachable",
    "authentication_failed",
    "model_not_found",
    "rate_limited",
    "protocol_error",
    "disabled",
]
ModelRouteRole = Literal[
    "default",
    "fast",
    "deep",
    "tool_calling",
    "final_report",
    "fallback",
]
ModelMessageRole = Literal["user", "assistant", "tool"]
ModelStreamEventType = Literal[
    "start",
    "content_delta",
    "thinking_delta",
    "tool_call_delta",
    "completed",
]


class ModelToolDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9_-]+$")
    description: str | None = Field(default=None, max_length=2_000)
    input_schema: dict[str, JsonValue]


class ModelToolCall(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str | None = Field(default=None, max_length=256)
    name: str = Field(min_length=1, max_length=128)
    arguments: dict[str, JsonValue]


class ModelToolResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    tool_call_id: str = Field(min_length=1, max_length=256)
    content: str = Field(max_length=100_000)
    is_error: bool = False


class ModelMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: ModelMessageRole
    content: str | None = Field(default=None, max_length=200_000)
    tool_calls: list[ModelToolCall] | None = None
    tool_result: ModelToolResult | None = None

    @model_validator(mode="after")
    def validate_role_payload(self) -> ModelMessage:
        if self.role == "tool" and self.tool_result is None:
            raise ValueError("tool messages require tool_result")
        if self.role != "tool" and self.tool_result is not None:
            raise ValueError("tool_result is only valid for tool messages")
        if self.role != "assistant" and self.tool_calls:
            raise ValueError("tool_calls are only valid for assistant messages")
        if self.content is None and not self.tool_calls and self.tool_result is None:
            raise ValueError("message content must not be empty")
        return self


class ModelUsage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    input_tokens: int | None = Field(default=None, ge=0)
    output_tokens: int | None = Field(default=None, ge=0)
    cached_tokens: int | None = Field(default=None, ge=0)
    total_tokens: int | None = Field(default=None, ge=0)


class ModelCapabilities(BaseModel):
    model_config = ConfigDict(extra="forbid")

    supports_streaming: bool | None = None
    supports_tools: bool | None = None
    supports_thinking: bool | None = None
    supports_vision: bool | None = None
    supports_files: bool | None = None
    supports_structured_output: bool | None = None


class ModelInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_id: str = Field(min_length=1, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)
    capabilities: ModelCapabilities = Field(default_factory=ModelCapabilities)


class ProviderHealth(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: ProviderHealthStatus
    checked_at: str
    latency_ms: int | None = Field(default=None, ge=0)
    error_code: str | None = Field(default=None, max_length=100)
    error_summary: str | None = Field(default=None, max_length=500)
    check_kind: str = Field(default="connectivity", max_length=32)
    model_id: str | None = Field(default=None, max_length=200)


class ModelRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    system: str | None = Field(default=None, max_length=100_000)
    messages: list[ModelMessage] = Field(min_length=1, max_length=200)
    model: str | None = Field(default=None, min_length=1, max_length=200)
    temperature: float | None = Field(default=None, ge=0, le=2)
    max_tokens: int = Field(default=512, ge=1, le=100_000)
    stream: bool = False
    tools: list[ModelToolDefinition] | None = Field(default=None, max_length=64)
    tool_choice: str | None = Field(default=None, max_length=128)
    metadata: dict[str, str] = Field(default_factory=dict)
    timeout: float | None = Field(default=None, gt=0, le=600)


class ModelResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str | None = None
    thinking_content: str | None = None
    tool_calls: list[ModelToolCall] | None = None
    finish_reason: str | None = None
    usage: ModelUsage | None = None
    provider: str
    model: str | None = None
    request_id: str | None = None
    latency_ms: int | None = Field(default=None, ge=0)


class ModelStreamEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: ModelStreamEventType
    content_delta: str | None = None
    thinking_delta: str | None = None
    tool_call_index: int | None = Field(default=None, ge=0)
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_arguments_delta: str | None = None
    response: ModelResponse | None = None
    fallback_used: bool | None = None
    request_correlation_id: str | None = None
    initial_provider_id: str | None = None
    initial_model_id: str | None = None
    final_provider_id: str | None = None
    final_model_id: str | None = None


class GatewayResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    response: ModelResponse
    route_role: ModelRouteRole | None = None
    fallback_used: bool
    request_correlation_id: str
    initial_provider_id: str
    initial_model_id: str
    final_provider_id: str
    final_model_id: str
