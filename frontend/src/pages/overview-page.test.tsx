import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import * as aiApi from "../api/ai";
import { OverviewPage } from "./overview-page";

vi.mock("../features/crawler/hooks/use-crawler-queries", () => ({
  useHealthQuery: () => ({
    data: { status: "ok", service: "personal-media-ops-api", version: "test" },
    isPending: false,
    isError: false,
  }),
  useCrawlerTasksQuery: () => ({
    data: [
      {
        id: "crawl-1",
        platform: "bili",
        mode: "search",
        keywords: "AI",
        status: "running",
        created_at: "2026-08-03T00:00:00Z",
      },
    ],
    isPending: false,
    isError: false,
  }),
  useCrawlerCapabilitiesQuery: () => ({
    data: {
      platforms: [
        {
          platform: "bili",
          display_name: "B站",
          verification_status: "production_verified",
          availability_status: "enabled",
        },
      ],
    },
    isPending: false,
    isError: false,
  }),
}));

vi.mock("../features/research/hooks/use-research-queries", () => ({
  useResearchTasksQuery: () => ({
    data: [
      {
        id: "research-1",
        objective: "验证一个真实研究目标",
        status: "Researching",
        current_step: "跨平台验证",
        updated_at: "2026-08-03T00:00:00Z",
      },
    ],
    isPending: false,
    isError: false,
  }),
}));

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <OverviewPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("OverviewPage", () => {
  beforeEach(() => {
    vi.spyOn(aiApi, "getAiHealth").mockResolvedValue([
      {
        id: "health-1",
        provider_id: "provider-1",
        provider_name: "Test Provider",
        status: "healthy",
        checked_at: "2026-08-03T00:00:00Z",
        check_kind: "text",
        model_id: "test-model",
      },
    ]);
    vi.spyOn(aiApi, "getUsage").mockResolvedValue({
      totals: {
        invocation_count: 3,
        success_count: 3,
        failure_count: 0,
        success_rate: 1,
        average_latency_ms: 100,
        input_tokens: 10,
        output_tokens: 20,
        cached_tokens: 0,
        uncosted_invocation_count: 0,
        costed_invocation_count: 3,
        estimated_cost: "0.01",
        price_currency: "USD",
      },
      by_provider: [],
      by_model: [],
      by_role: [],
      cost_by_currency: [],
      recent_invocations: [],
    });
  });

  it("shows runtime health and does not reuse legacy command-center metrics", async () => {
    renderPage();
    expect(
      await screen.findByRole("heading", { name: "运行概览" }),
    ).toBeInTheDocument();
    expect(screen.getByText("平台能力状态")).toBeInTheDocument();
    expect(screen.getByText("模型健康")).toBeInTheDocument();
    expect(screen.getByText("资源用量")).toBeInTheDocument();
    expect(screen.getByText("验证一个真实研究目标")).toBeInTheDocument();
    expect(screen.queryByText("今日新增")).not.toBeInTheDocument();
    expect(screen.queryByText("活跃订阅")).not.toBeInTheDocument();
    expect(screen.queryByText("热度变化主题")).not.toBeInTheDocument();
  });
});
