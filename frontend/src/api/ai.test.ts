import {
  createAiProvider,
  createModel,
  debugModel,
  listAiProviders,
  refreshProviderModels,
  streamDebugModel,
  updateAiProvider,
  updateRoutes,
  type AiProvider,
} from "./ai";

const SYNTHETIC_API_KEY = ["secret", "value"].join("-");

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

function requestBody(call: [RequestInfo | URL, RequestInit?] | undefined) {
  const body = call?.[1]?.body;
  if (typeof body !== "string") throw new Error("expected a JSON request body");
  return JSON.parse(body) as unknown;
}

const provider: AiProvider = {
  id: "provider/1",
  name: "DeepSeek",
  provider_type: "deepseek",
  protocol: "openai_compatible",
  base_url: "https://api.deepseek.com",
  enabled: true,
  timeout_seconds: 60,
  max_retries: 1,
  concurrency_limit: 1,
  credentials_configured: true,
  model_count: 1,
  last_health_status: "healthy",
  last_health_latency_ms: 123,
  last_health_checked_at: "2026-08-01T00:00:00Z",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const model = {
  id: "model/1",
  provider_id: provider.id,
  model_id: "deepseek-chat",
  display_name: "DeepSeek Chat",
  enabled: true,
  context_window: 128000,
  max_output_tokens: 8192,
  supports_streaming: true,
  supports_tools: true,
  supports_thinking: false,
  supports_vision: null,
  supports_files: null,
  supports_structured_output: null,
  capabilities_source: "user",
  last_health_status: "healthy",
  last_health_checked_at: "2026-08-01T00:00:00Z",
  input_price_per_million: null,
  output_price_per_million: null,
  cached_input_price_per_million: null,
  price_currency: null,
  price_effective_at: null,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
  provider_name: provider.name,
  protocol: provider.protocol,
  provider_enabled: true,
};

describe("AI model center API", () => {
  it("keeps provider secrets write-only across list, create, and edit", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([provider]))
      .mockResolvedValueOnce(jsonResponse(provider, 201))
      .mockResolvedValueOnce(jsonResponse(provider));

    const listed = await listAiProviders();
    expect(listed).toEqual([provider]);
    await createAiProvider({
      name: "DeepSeek",
      provider_type: "deepseek",
      protocol: "openai_compatible",
      base_url: "https://api.deepseek.com",
      enabled: true,
      timeout_seconds: 60,
      max_retries: 1,
      concurrency_limit: 1,
      api_key: SYNTHETIC_API_KEY,
    });
    await updateAiProvider(provider.id, {
      name: provider.name,
      provider_type: provider.provider_type,
      protocol: provider.protocol,
      base_url: provider.base_url,
      enabled: provider.enabled,
      timeout_seconds: provider.timeout_seconds,
      max_retries: provider.max_retries,
      concurrency_limit: provider.concurrency_limit,
    });

    expect(requestBody(fetchMock.mock.calls[1])).toMatchObject({
      api_key: SYNTHETIC_API_KEY,
    });
    expect(requestBody(fetchMock.mock.calls[2])).not.toHaveProperty(
      "api_key",
    );
    expect(JSON.stringify(listed)).not.toContain(SYNTHETIC_API_KEY);
  });

  it("keeps refreshed models as disabled candidates until explicitly created", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        jsonResponse([
          {
            model_id: "deepseek-reasoner",
            display_name: "DeepSeek Reasoner",
            capabilities: {
              supports_streaming: null,
              supports_tools: null,
              supports_thinking: null,
              supports_vision: null,
              supports_files: null,
              supports_structured_output: null,
            },
          },
        ]),
      )
      .mockResolvedValueOnce(jsonResponse(model, 201));

    const candidates = await refreshProviderModels(provider.id);
    expect(candidates[0]?.model_id).toBe("deepseek-reasoner");
    expect(fetchMock).toHaveBeenCalledTimes(1);
    await createModel({
      provider_id: provider.id,
      model_id: "deepseek-reasoner",
      display_name: "DeepSeek Reasoner",
      enabled: false,
      context_window: null,
      max_output_tokens: null,
      supports_streaming: null,
      supports_tools: null,
      supports_thinking: null,
      supports_vision: null,
      supports_files: null,
      supports_structured_output: null,
      capabilities_source: "provider",
      input_price_per_million: null,
      output_price_per_million: null,
      cached_input_price_per_million: null,
      price_currency: null,
      price_effective_at: null,
    });
    expect(requestBody(fetchMock.mock.calls[1])).toMatchObject({
      enabled: false,
    });
  });

  it("updates role routes and parses non-streaming gateway metadata", async () => {
    const route = {
      role: "default",
      model_record_id: model.id,
      updated_at: "2026-08-01T00:00:00Z",
      model_id: model.model_id,
      display_name: model.display_name,
      model_enabled: true,
      provider_id: provider.id,
      provider_name: provider.name,
      provider_enabled: true,
    };
    const gateway = {
      response: {
        content: "OK",
        thinking_content: null,
        tool_calls: null,
        finish_reason: "stop",
        usage: {
          input_tokens: 3,
          output_tokens: 1,
          cached_tokens: null,
          total_tokens: 4,
        },
        provider: provider.name,
        model: model.model_id,
        request_id: "request-1",
        latency_ms: 91,
      },
      route_role: "default",
      fallback_used: false,
      request_correlation_id: "correlation-1",
      initial_provider_id: provider.id,
      initial_model_id: model.model_id,
      final_provider_id: provider.id,
      final_model_id: model.model_id,
    };
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([route]))
      .mockResolvedValueOnce(jsonResponse(gateway));

    await expect(
      updateRoutes({ default: model.id, fallback: null }),
    ).resolves.toEqual([route]);
    await expect(
      debugModel({ message: "ping", route_role: "default", stream: false }),
    ).resolves.toMatchObject({ response: { content: "OK" }, fallback_used: false });
    expect(fetchMock.mock.calls[0]?.[1]?.method).toBe("PUT");
  });

  it("parses fragmented SSE events and releases the response body", async () => {
    const encoder = new TextEncoder();
    const chunks = [
      'data: {"type":"content_delta","content_delta":"O"}\n',
      '\ndata: {"type":"content_delta","content_delta":"K"}\n\n',
      'data: {"type":"completed","response":{"content":"OK","thinking_content":null,"tool_calls":null,"finish_reason":"stop","usage":null,"provider":"DeepSeek","model":"deepseek-chat","request_id":null,"latency_ms":12},"fallback_used":false,"request_correlation_id":"c1","initial_provider_id":"p1","initial_model_id":"deepseek-chat","final_provider_id":"p1","final_model_id":"deepseek-chat"}\n\n',
    ];
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        new ReadableStream({
          start(controller) {
            for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
            controller.close();
          },
        }),
        { headers: { "content-type": "text/event-stream" } },
      ),
    );

    const seen = [];
    for await (const event of streamDebugModel({
      message: "ping",
      route_role: "default",
      stream: true,
    })) {
      seen.push(event);
    }
    expect(seen.map((event) => event.type)).toEqual([
      "content_delta",
      "content_delta",
      "completed",
    ]);
    expect(seen[2]).toMatchObject({ final_model_id: "deepseek-chat" });
  });
});
