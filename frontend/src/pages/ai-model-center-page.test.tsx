import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as aiApi from "../api/ai";
import { AiModelCenterPage } from "./ai-model-center-page";

const SYNTHETIC_API_KEY = ["temporary", "secret"].join("-");

const provider: aiApi.AiProvider = {
  id: "provider-1",
  name: "DeepSeek 生产",
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
  last_health_latency_ms: 88,
  last_health_checked_at: "2026-08-01T00:00:00Z",
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:00Z",
};

const model: aiApi.AiModel = {
  id: "model-1",
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

const routes: aiApi.ModelRoute[] = aiApi.routeRoles.map((role) => ({
  role,
  model_record_id: role === "default" ? model.id : null,
  updated_at: "2026-08-01T00:00:00Z",
  model_id: role === "default" ? model.model_id : null,
  display_name: role === "default" ? model.display_name : null,
  model_enabled: role === "default" ? true : null,
  provider_id: role === "default" ? provider.id : null,
  provider_name: role === "default" ? provider.name : null,
  provider_enabled: role === "default" ? true : null,
}));

const emptyUsage: aiApi.UsageSummary = {
  totals: {
    invocation_count: 0,
    success_count: 0,
    failure_count: 0,
    success_rate: null,
    average_latency_ms: null,
    input_tokens: 0,
    output_tokens: 0,
    cached_tokens: 0,
    uncosted_invocation_count: 0,
    costed_invocation_count: 0,
    estimated_cost: null,
    price_currency: null,
  },
  by_provider: [],
  by_model: [],
  by_role: [],
  cost_by_currency: [],
  recent_invocations: [],
};

function mockQueries() {
  vi.spyOn(aiApi, "listProviderTemplates").mockResolvedValue([
    {
      id: "deepseek",
      display_name: "DeepSeek",
      protocol: "openai_compatible",
      base_url: "https://api.deepseek.com",
    },
    {
      id: "custom_openai",
      display_name: "自定义 OpenAI Compatible",
      protocol: "openai_compatible",
      base_url: null,
    },
  ]);
  vi.spyOn(aiApi, "listAiProviders").mockResolvedValue([provider]);
  vi.spyOn(aiApi, "listAiModels").mockResolvedValue([model]);
  vi.spyOn(aiApi, "listRoutes").mockResolvedValue(routes);
  vi.spyOn(aiApi, "getUsage").mockResolvedValue(emptyUsage);
  vi.spyOn(aiApi, "getAiHealth").mockResolvedValue([]);
}

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <AiModelCenterPage />
    </QueryClientProvider>,
  );
}

describe("AiModelCenterPage", () => {
  beforeEach(() => mockQueries());

  it("adds and edits providers without refilling the API key", async () => {
    const create = vi
      .spyOn(aiApi, "createAiProvider")
      .mockResolvedValue(provider);
    vi.spyOn(aiApi, "updateAiProvider").mockResolvedValue(provider);
    const user = userEvent.setup();
    renderPage();

    expect(await screen.findByText("DeepSeek 生产")).toBeInTheDocument();
    expect(screen.getByText("凭证已配置")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "添加服务商" }));
    const key = screen.getByLabelText("API Key");
    expect(key).toHaveAttribute("type", "password");
    await user.type(screen.getByLabelText("服务商名称"), "自定义服务");
    await user.type(screen.getByLabelText("Base URL"), "https://models.example.com/v1");
    await user.type(key, SYNTHETIC_API_KEY);
    await user.click(screen.getByRole("button", { name: "保存服务商" }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(
        expect.objectContaining({ api_key: SYNTHETIC_API_KEY }),
      ),
    );

    await user.click(screen.getByRole("button", { name: /编辑 DeepSeek 生产/ }));
    expect(screen.getByLabelText("API Key")).toHaveValue("");
    expect(screen.getByText("留空以保留现有凭证")).toBeInTheDocument();
  }, 10_000);

  it("tests a provider and imports refreshed models only after confirmation", async () => {
    const test = vi.spyOn(aiApi, "testAiProvider").mockResolvedValue({
      status: "healthy",
      checked_at: "2026-08-01T00:00:00Z",
      latency_ms: 76,
      error_code: null,
      error_summary: null,
      check_kind: "text",
      model_id: model.model_id,
    });
    vi.spyOn(aiApi, "refreshProviderModels").mockResolvedValue([
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
    ]);
    const create = vi.spyOn(aiApi, "createModel").mockResolvedValue(model);
    const user = userEvent.setup();
    renderPage();

    await screen.findByText("DeepSeek 生产");
    await user.selectOptions(
      screen.getByLabelText("测试能力 DeepSeek 生产"),
      "tools",
    );
    await user.click(screen.getByRole("button", { name: /测试 DeepSeek 生产/ }));
    await waitFor(() =>
      expect(test).toHaveBeenCalledWith(provider.id, {
        model_record_id: model.id,
        check_kind: "tools",
      }),
    );
    expect(await screen.findByText(/工具调用检查通过/)).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "模型" }));
    await user.click(screen.getByRole("button", { name: "拉取候选模型" }));
    expect(await screen.findByText("deepseek-reasoner")).toBeInTheDocument();
    expect(create).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: /加入候选模型/ }));
    expect(screen.getByLabelText("启用模型")).not.toBeChecked();
    expect(screen.getByRole("dialog").querySelector("form")?.checkValidity()).toBe(
      true,
    );
    await user.click(screen.getByRole("button", { name: "保存模型" }));
    await waitFor(() =>
      expect(create).toHaveBeenCalledWith(expect.objectContaining({ enabled: false })),
    );
  });

  it("saves routes, shows a truthful usage empty state, and runs diagnostics", async () => {
    const saveRoutes = vi.spyOn(aiApi, "updateRoutes").mockResolvedValue(routes);
    vi.spyOn(aiApi, "debugModel").mockResolvedValue({
      response: {
        content: "OK",
        thinking_content: null,
        tool_calls: null,
        finish_reason: "stop",
        usage: { input_tokens: 3, output_tokens: 1, cached_tokens: null, total_tokens: 4 },
        provider: provider.name,
        model: model.model_id,
        request_id: "request-1",
        latency_ms: 80,
      },
      route_role: "default",
      fallback_used: false,
      request_correlation_id: "correlation-1",
      initial_provider_id: provider.id,
      initial_model_id: model.model_id,
      final_provider_id: provider.id,
      final_model_id: model.model_id,
    });
    const user = userEvent.setup();
    Object.defineProperty(window, "innerWidth", { value: 390, configurable: true });
    renderPage();
    await screen.findByText("DeepSeek 生产");

    await user.click(screen.getByRole("tab", { name: "路由" }));
    await user.selectOptions(screen.getByLabelText("备用模型"), model.id);
    await user.click(screen.getByRole("button", { name: "保存路由" }));
    await waitFor(() =>
      expect(saveRoutes).toHaveBeenCalledWith(expect.objectContaining({ fallback: model.id })),
    );

    await user.click(screen.getByRole("tab", { name: "用量" }));
    expect(await screen.findByText("还没有模型调用记录")).toBeInTheDocument();

    await user.click(screen.getByRole("tab", { name: "调试测试" }));
    await user.type(screen.getByLabelText("短消息"), "只回复 OK");
    await user.click(screen.getByRole("button", { name: "执行测试" }));
    expect(await screen.findByText("OK")).toBeInTheDocument();
    expect(screen.getByText("未发生 fallback")).toBeInTheDocument();
  });
});
