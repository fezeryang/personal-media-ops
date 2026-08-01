import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

import * as researchApi from "../api/research";
import { ResearchTasksPage } from "./research-tasks-page";

const task: researchApi.ResearchTaskDetail = {
  id: "research-1",
  task_type: "research",
  objective: "寻找当前值得关注的个人 AI 工作台产品",
  platforms: ["bili"],
  status: "AwaitingReview",
  current_round: 2,
  current_step: "awaiting_review",
  paused: false,
  consumption: {
    crawl_count: 2,
    content_count: 4,
    duration_seconds: 12,
    input_tokens: 120,
    output_tokens: 80,
    cached_tokens: 0,
    estimated_cost: null,
    cost_enabled: false,
    cost_currency: null,
  },
  finding_count: 1,
  event_count: 0,
  action_count: 1,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:12Z",
  finished_at: null,
  failure_reason: null,
  plan: { derived_keywords: ["local-first", "agent memory", "evidence graph"] },
  context: { last_search_query: "local-first agent memory" },
  result: { summary: "模型化研究摘要", evidence_count: 1 },
  route_snapshot: { primary: { provider: "MiniMax", model: "MiniMax-M3" } },
  budget: {
    crawl_limit: 2,
    content_limit: 100,
    duration_seconds: 3600,
    token_limit: 50000,
    cost_limit: null,
    cost_currency: null,
  },
  trace: [
    {
      sequence: 1,
      event: "tool_call",
      status: "Researching",
      reason: "agent_tool_dispatch",
      round_number: 1,
      step: "search_library",
      tool_name: "search_library",
      tool_arguments: { query: "AI workbench" },
      provider: null,
      model: null,
      route_role: null,
      request_correlation_id: null,
      input_tokens: null,
      output_tokens: null,
      elapsed_ms: null,
      created_at: "2026-08-01T00:00:01Z",
    },
  ],
  findings: [
    {
      id: "finding-1",
      research_task_id: "research-1",
      round_number: 2,
      kind: "fact",
      statement: "资料描述了一个本地优先的 AI 工作台。",
      derivation: null,
      status: "active",
      evidence: [
        {
          content_id: "content-1",
          platform: "bili",
          title: "AI 工作台实践",
          source_url: "https://example.test/content-1",
          author_name: "作者",
          published_at: null,
          collected_at: "2026-08-01T00:00:02Z",
          crawl_task_id: "crawl-1",
        },
      ],
      created_at: "2026-08-01T00:00:03Z",
      updated_at: "2026-08-01T00:00:03Z",
    },
  ],
  events: [],
  actions: [
    {
      id: "action-1",
      action: "保存专题集合草案",
      reason: "供所有者审核",
      payload: {},
      status: "pending",
      created_at: "2026-08-01T00:00:04Z",
      decided_at: null,
    },
  ],
};

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <ResearchTasksPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("ResearchTasksPage", () => {
  beforeEach(() => {
    vi.spyOn(researchApi, "listResearchTasks").mockResolvedValue([task]);
    vi.spyOn(researchApi, "getResearchTask").mockResolvedValue(task);
    vi.spyOn(researchApi, "decideResearchAction").mockResolvedValue(task.actions[0]);
  });

  it("shows status, evidence provenance, trace parameters, and owner actions", async () => {
    renderPage();
    expect(await screen.findByText("待审核")).toBeInTheDocument();
    expect(await screen.findByText("资料描述了一个本地优先的 AI 工作台。")).toBeInTheDocument();
    expect(screen.getByText("AI 工作台实践")).toBeInTheDocument();
    expect(screen.getByText("执行轨迹（1 步）")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByText("search_library"));
    expect(screen.getByText(/AI workbench/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "批准" })).toBeInTheDocument();
  });

  it("creates a bounded task from the single task page", async () => {
    const create = vi.spyOn(researchApi, "createResearchTask").mockResolvedValue(task);
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "新建研究任务" }));
    const objective = screen.getByLabelText("研究目标");
    await user.clear(objective);
    await user.type(objective, "研究个人 AI 工作台的产品机会");
    await user.click(screen.getByRole("button", { name: "创建并开始" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ platforms: ["bili"] })));
  });
});
