import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

import * as researchApi from "../api/research";
import { ResearchTasksPage } from "./research-tasks-page";

vi.mock("../features/crawler/hooks/use-crawler-queries", () => ({
  useCrawlerCapabilitiesQuery: () => ({
    data: {
      max_concurrent_tasks: 1,
      platforms: [
        {
          platform: "bili",
          display_name: "Bilibili",
          icon_label: "B",
          enabled: true,
          verification_status: "production_verified",
          availability_status: "enabled",
          login_prompt: "Bilibili login",
          crawler_types: [{ value: "search", label: "关键词搜索" }],
          login_types: [{ value: "qrcode", label: "二维码登录" }],
          requested_count: { minimum: 1, maximum: 20, default: 5 },
          supports_comments: false,
          supports_sub_comments: false,
          modes: [
            {
              mode: "search",
              label: "关键词搜索",
              status: "production_verified",
              enabled: true,
              reason: null,
              input_fields: ["keywords"],
              requested_count: { minimum: 1, maximum: 20, default: 5 },
              requested_comment_count: null,
              requested_sub_comment_count: null,
              requires_browser: true,
              login_type: "qrcode",
            },
          ],
        },
        {
          platform: "xhs",
          display_name: "小红书",
          icon_label: "红",
          enabled: true,
          verification_status: "production_verified",
          availability_status: "enabled",
          login_prompt: "Xiaohongshu login",
          crawler_types: [{ value: "search", label: "关键词搜索" }],
          login_types: [{ value: "qrcode", label: "二维码登录" }],
          requested_count: { minimum: 1, maximum: 20, default: 5 },
          supports_comments: false,
          supports_sub_comments: false,
          modes: [
            {
              mode: "search",
              label: "关键词搜索",
              status: "production_verified",
              enabled: true,
              reason: null,
              input_fields: ["keywords"],
              requested_count: { minimum: 1, maximum: 20, default: 5 },
              requested_comment_count: null,
              requested_sub_comment_count: null,
              requires_browser: true,
              login_type: "qrcode",
            },
          ],
        },
        {
          platform: "ks",
          display_name: "快手",
          icon_label: "快",
          enabled: false,
          verification_status: "code_ready",
          availability_status: "deferred_upstream_breakage",
          login_prompt: "Kuaishou login",
          crawler_types: [{ value: "search", label: "关键词搜索" }],
          login_types: [{ value: "qrcode", label: "二维码登录" }],
          requested_count: { minimum: 1, maximum: 20, default: 5 },
          supports_comments: false,
          supports_sub_comments: false,
          modes: [
            {
              mode: "search",
              label: "关键词搜索",
              status: "deferred_upstream_breakage",
              enabled: false,
              reason: "上游搜索协议异常",
              input_fields: ["keywords"],
              requested_count: { minimum: 1, maximum: 20, default: 5 },
              requested_comment_count: null,
              requested_sub_comment_count: null,
              requires_browser: true,
              login_type: "qrcode",
            },
          ],
        },
      ],
    },
    isPending: false,
    error: null,
  }),
}));

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
  result: {
    summary: "模型化研究摘要",
    summary_markdown: "## 模型化研究摘要",
    summary_html: "<h2>模型化研究摘要</h2><script>alert(1)</script>",
    evidence_count: 1,
    new_content_count: 2,
    existing_content_count: 3,
    updated_content_count: 1,
    duplicate_evidence_count: 1,
    independent_evidence_count: 1,
    discovery_count: 5,
    repost_count: 1,
    negative_evidence_count: 1,
  },
  route_snapshot: { primary: { provider: "MiniMax", model: "MiniMax-M3" } },
  budget: {
    crawl_limit: 2,
    content_limit: 100,
    duration_seconds: 3600,
    token_limit: 50000,
    cost_limit: null,
    cost_currency: null,
    max_input_tokens: 20000,
    max_output_tokens: 10000,
    max_model_calls: 12,
    route_policy: "prefer_subscription",
    max_total_tokens: 50000,
    max_crawl_tasks: 6,
    max_new_contents: 100,
    max_runtime_seconds: 3600,
    max_payg_amount: null,
    currency: "CNY",
  },
  coverage: {
    target_platform_count: 3,
    target_entity_count: 3,
    target_negative_evidence_count: 1,
    max_single_entity_evidence_ratio: 0.6,
    target_independent_evidence_count: 5,
    target_new_content_count: 5,
    low_marginal_value_threshold: 0.25,
    low_marginal_round_limit: 2,
    stop_reason: "skipped_low_marginal_value",
    completed_at: "2026-08-01T00:00:12Z",
  },
  platform_coverage: [
    {
      id: "coverage-bili",
      research_task_id: "research-1",
      platform: "bili",
      order_index: 0,
      status: "completed",
      planned_query_count: 2,
      actual_query_count: 2,
      result_count: 5,
      new_content_count: 2,
      independent_evidence_count: 1,
      negative_evidence_count: 0,
      failure_reason: null,
    },
    {
      id: "coverage-zhihu",
      research_task_id: "research-1",
      platform: "zhihu",
      order_index: 1,
      status: "failed",
      planned_query_count: 1,
      actual_query_count: 1,
      result_count: 0,
      new_content_count: 0,
      independent_evidence_count: 0,
      negative_evidence_count: 1,
      failure_reason: "平台登录状态失效",
    },
  ],
  entity_coverage: [
    {
      canonical_name: "WorkBuddy",
      entity_type: "product",
      entity_query_count: 2,
      entity_evidence_count: 1,
      entity_new_content_count: 1,
      entity_platform_count: 1,
      entity_coverage_ratio: 1,
      saturated: true,
    },
    {
      canonical_name: "Local Agent",
      entity_type: "product",
      entity_query_count: 1,
      entity_evidence_count: 0,
      entity_new_content_count: 0,
      entity_platform_count: 1,
      entity_coverage_ratio: 0,
      saturated: false,
    },
  ],
  content_decisions: [
    {
      content_id: "content-1",
      research_query_id: "query-1",
      decision: "adopted",
      not_adopted_reason: null,
      source_independence: "independent",
      content_completeness: "complete",
      evidence_quality: "high",
      is_repost: false,
      repost_of_content_id: null,
      similarity_score: null,
    },
    {
      content_id: "content-2",
      research_query_id: "query-1",
      decision: "not_adopted",
      not_adopted_reason: "重复转载",
      source_independence: "repost",
      content_completeness: "partial",
      evidence_quality: "low",
      is_repost: true,
      repost_of_content_id: "content-1",
      similarity_score: 0.98,
    },
  ],
  step_usage: [
    {
      step: "final_report",
      sequence: 1,
      provider_instance_id: "provider-minimax",
      vendor: "MiniMax",
      model: "MiniMax-M3",
      billing_mode: "subscription_fixed",
      estimated_cost: null,
      currency: "CNY",
      price_source: null,
      input_tokens: 120,
      output_tokens: 80,
      cached_tokens: 0,
      latency_ms: 120,
      fallback_from_provider_instance_id: null,
      fallback_reason: null,
      invocation_id: "invocation-1",
      created_at: "2026-08-01T00:00:03Z",
    },
  ],
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
          support_type: "direct",
          support_strength: "strong",
          support_explanation: "标题与正文直接描述该产品。",
          occurrences: [],
        },
      ],
      created_at: "2026-08-01T00:00:03Z",
      updated_at: "2026-08-01T00:00:03Z",
    },
  ],
  queries: [
    {
      id: "query-1",
      research_task_id: "research-1",
      query: "Claude Code 个人工作流",
      normalized_query: "claude code 个人工作流",
      query_type: "scenario",
      platform: "bili",
      source_type: "user_goal",
      source_content_id: null,
      source_finding_id: null,
      parent_query_id: null,
      generation_reason: "由用户研究目标生成首轮查询",
      relevance_score: 0.9,
      specificity_score: 0.8,
      novelty_score: 1,
      noise_risk_score: 0.1,
      expected_value_score: 0.72,
      status: "completed",
      rejection_reason: null,
      crawler_task_id: "crawl-1",
      executed_at: "2026-08-01T00:00:02Z",
      result_count: 5,
      new_content_count: 2,
      existing_content_count: 3,
      updated_content_count: 1,
      duplicate_evidence_count: 1,
      created_at: "2026-08-01T00:00:01Z",
      updated_at: "2026-08-01T00:00:02Z",
    },
    {
      id: "query-rejected",
      research_task_id: "research-1",
      query: "agent",
      normalized_query: "agent",
      query_type: "generic_topic",
      platform: "bili",
      source_type: "user_goal",
      source_content_id: null,
      source_finding_id: null,
      parent_query_id: null,
      generation_reason: "规划模型候选",
      relevance_score: null,
      specificity_score: 0,
      novelty_score: 1,
      noise_risk_score: 1,
      expected_value_score: null,
      status: "rejected",
      rejection_reason: "仅包含泛化词，必须与具体实体或限定场景组合",
      crawler_task_id: null,
      executed_at: null,
      result_count: 0,
      new_content_count: 0,
      existing_content_count: 0,
      updated_content_count: 0,
      duplicate_evidence_count: 0,
      created_at: "2026-08-01T00:00:01Z",
      updated_at: "2026-08-01T00:00:01Z",
    },
    {
      id: "query-skipped",
      research_task_id: "research-1",
      query: "WorkBuddy 不好用",
      normalized_query: "workbuddy 不好用",
      query_type: "product",
      platform: "zhihu",
      source_type: "finding",
      source_content_id: "content-1",
      source_finding_id: "finding-1",
      parent_query_id: "query-1",
      generation_reason: "寻找反向证据",
      relevance_score: 0.8,
      specificity_score: 0.9,
      novelty_score: 0.8,
      noise_risk_score: 0.2,
      expected_value_score: 0.6,
      status: "skipped_low_marginal_value",
      lifecycle_status: "skipped_low_marginal_value",
      unexecuted_reason: "连续两轮新增率低于阈值且未发现新实体",
      rejection_reason: null,
      crawler_task_id: null,
      executed_at: null,
      result_count: 0,
      new_content_count: 0,
      existing_content_count: 0,
      updated_content_count: 0,
      duplicate_evidence_count: 0,
      new_content_rate: 0,
      new_entity_count: 0,
      new_independent_evidence_count: 0,
      duplicate_rate: 1,
      marginal_value_score: 0.1,
      created_at: "2026-08-01T00:00:01Z",
      updated_at: "2026-08-01T00:00:01Z",
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
    vi.spyOn(researchApi, "pauseResearchTask").mockResolvedValue(task);
    vi.spyOn(researchApi, "resumeResearchTask").mockResolvedValue(task);
    vi.spyOn(researchApi, "cancelResearchTask").mockResolvedValue(task);
  });

  it("shows status, evidence provenance, trace parameters, and owner actions", async () => {
    renderPage();
    expect(await screen.findByText("待审核")).toBeInTheDocument();
    expect(await screen.findByText("资料描述了一个本地优先的 AI 工作台。")).toBeInTheDocument();
    expect(screen.getByText("模型化研究摘要")).toBeInTheDocument();
    expect(document.querySelector("script")).not.toBeInTheDocument();
    expect(screen.getByText("AI 工作台实践")).toBeInTheDocument();
    expect(screen.getByText("查询轨迹与质量闸门")).toBeInTheDocument();
    expect(screen.getByText("平台计划与实体覆盖")).toBeInTheDocument();
    expect(screen.getByText("证据池与未采用内容")).toBeInTheDocument();
    expect(screen.getByText("预算分类与模型轨迹")).toBeInTheDocument();
    expect(screen.getByText(/仅包含泛化词/)).toBeInTheDocument();
    expect(screen.getByText(/连续两轮新增率低于阈值/)).toBeInTheDocument();
    expect(screen.getByText("独立证据")).toBeInTheDocument();
    expect(screen.getByText("执行轨迹（1 步）")).toBeInTheDocument();
    await userEvent.setup().click(screen.getByText("search_library"));
    expect(screen.getByText(/AI workbench/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "批准" })).toBeInTheDocument();
  });

  it("keeps quality counts, rejected queries, and evidence reachable at 390px", async () => {
    const previousWidth = window.innerWidth;
    Object.defineProperty(window, "innerWidth", { configurable: true, value: 390 });
    try {
      renderPage();
      expect(await screen.findByText("查询轨迹与质量闸门")).toBeInTheDocument();
      expect(screen.getByText("已存在")).toBeInTheDocument();
      expect(screen.getByText(/拒绝原因：仅包含泛化词/)).toBeInTheDocument();
      expect(screen.getByText("直接支持 · 强")).toBeInTheDocument();
      expect(screen.getByText(/停止原因：/)).toBeInTheDocument();
    } finally {
      Object.defineProperty(window, "innerWidth", { configurable: true, value: previousWidth });
    }
  });

  it("shows pause, resume, and cancel controls for durable runtime states", async () => {
    renderPage();
    expect(await screen.findByRole("button", { name: "暂停" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消任务" })).toBeInTheDocument();

    cleanup();
    vi.mocked(researchApi.getResearchTask).mockResolvedValue({ ...task, status: "Researching", paused: true });
    renderPage();
    expect(await screen.findByRole("button", { name: "继续" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "取消任务" })).toBeInTheDocument();
  });

  it("creates a bounded task from the single task page", async () => {
    const create = vi.spyOn(researchApi, "createResearchTask").mockResolvedValue(task);
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "新建研究任务" }));
    expect(screen.getByText("快手")).toBeInTheDocument();
    expect(screen.getByText(/上游搜索协议异常/)).toBeInTheDocument();
    const objective = screen.getByLabelText("研究目标");
    await user.clear(objective);
    await user.type(objective, "研究个人 AI 工作台的产品机会");
    await user.click(screen.getByRole("button", { name: "创建并开始" }));
    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ platforms: ["bili", "xhs"] })));
  });
});
