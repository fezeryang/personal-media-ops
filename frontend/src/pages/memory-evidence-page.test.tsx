import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import * as researchApi from "../api/research";
import type { ResearchTaskDetail, ResearchTaskSummary } from "../api/research";
import { MemoryEvidencePage } from "./memory-evidence-page";

const summary = {
  id: "task-memory-1",
  task_type: "research",
  objective: "验证个人 AI 工具的真实使用体验",
  platforms: ["bili"],
  status: "Done",
  current_round: 2,
  current_step: "complete",
  paused: false,
  consumption: {
    crawl_count: 1,
    content_count: 3,
    duration_seconds: 12,
    input_tokens: 100,
    output_tokens: 80,
    cached_tokens: 0,
    estimated_cost: null,
    cost_enabled: false,
    cost_currency: null,
  },
  finding_count: 1,
  event_count: 0,
  action_count: 0,
  created_at: "2026-08-01T00:00:00Z",
  updated_at: "2026-08-01T00:00:12Z",
  finished_at: "2026-08-01T00:00:12Z",
  failure_reason: null,
  stop_reason: null,
  primary_intent: "discovery",
  intent_confidence: 0.9,
} satisfies ResearchTaskSummary;

const detail = {
  ...summary,
  plan: {},
  context: {},
  result: null,
  route_snapshot: {},
  budget: {
    crawl_limit: 1,
    content_limit: 3,
    duration_seconds: 60,
    token_limit: 1000,
    cost_limit: null,
    cost_currency: null,
  },
  coverage: {
    target_platform_count: 1,
    target_entity_count: 0,
    target_negative_evidence_count: 1,
    max_single_entity_evidence_ratio: 1,
    target_independent_evidence_count: 1,
    target_new_content_count: 1,
    low_marginal_value_threshold: 0.1,
    low_marginal_round_limit: 1,
  },
  platform_coverage: [],
  entity_coverage: [],
  content_decisions: [],
  step_usage: [],
  budget_events: [],
  trace: [],
  findings: [
    {
      id: "finding-1",
      research_task_id: summary.id,
      round_number: 2,
      kind: "fact",
      statement: "工具在本地工作流中减少了重复整理成本。",
      derivation: null,
      counterevidence_status: "found",
      counterevidence_explanation: "存在登录限制的反向记录。",
      status: "active",
      evidence: [
        {
          content_id: "content-direct",
          platform: "bili",
          title: "真实工作流记录",
          source_url: "https://example.test/direct",
          author_name: "作者 A",
          published_at: null,
          collected_at: "2026-08-01T00:00:01Z",
          crawl_task_id: "crawl-1",
          support_type: "direct",
          support_strength: "strong",
          support_explanation: "正文直接描述使用结果。",
          source_independence: "independent",
          content_completeness: "complete",
          evidence_quality: "high",
          is_repost: false,
          occurrences: [],
        },
        {
          content_id: "content-contrary",
          platform: "bili",
          title: "登录限制复盘",
          source_url: "https://example.test/contrary",
          author_name: "作者 B",
          published_at: null,
          collected_at: "2026-08-01T00:00:02Z",
          crawl_task_id: "crawl-1",
          support_type: "contradictory",
          support_strength: "medium",
          support_explanation: "记录了无法完成登录的情况。",
          source_independence: "independent",
          content_completeness: "complete",
          evidence_quality: "medium",
          is_repost: false,
          occurrences: [],
        },
      ],
      created_at: "2026-08-01T00:00:03Z",
      updated_at: "2026-08-01T00:00:03Z",
    },
  ],
  queries: [],
  events: [],
  actions: [],
  intent_contract: null,
  intent_versions: [],
  intent_assumptions: [],
  unknowns: [
    {
      id: "unknown-1",
      research_task_id: summary.id,
      unknown: "是否存在跨平台的同类体验",
      priority: 1,
      status: "unresolved",
      evidence_count: 0,
      resolution: null,
      created_at: "2026-08-01T00:00:03Z",
      updated_at: "2026-08-01T00:00:03Z",
    },
  ],
  alignment_review: null,
  information_utilities: [],
  entity_candidates: [],
  event_candidates: [],
  memory_items: [
    {
      id: "memory-1",
      research_task_id: summary.id,
      memory_type: "fact",
      memory_key: "local_workflow_value",
      value: "减少重复整理成本",
      source_content_id: "content-direct",
      source_query_id: null,
      source_finding_id: "finding-1",
      confidence: 0.88,
      is_current: true,
      created_at: "2026-08-01T00:00:03Z",
      updated_at: "2026-08-01T00:00:03Z",
    },
  ],
  discovery_candidates: [],
  discovery_seeds: [],
  research_plan: {},
} as ResearchTaskDetail;

describe("MemoryEvidencePage", () => {
  beforeEach(() => {
    vi.spyOn(researchApi, "listResearchTasks").mockResolvedValue([summary]);
    vi.spyOn(researchApi, "getResearchTask").mockResolvedValue(detail);
  });

  it("centers long-term memory, findings, evidence roles, and unresolved gaps", async () => {
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <MemoryEvidencePage />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(await screen.findByRole("heading", { name: "记忆与证据" })).toBeInTheDocument();
    expect(await screen.findByText(summary.objective)).toBeInTheDocument();
    expect(await screen.findByText("工具在本地工作流中减少了重复整理成本。")).toBeInTheDocument();
    expect(screen.getByText("直接证据")).toBeInTheDocument();
    expect(screen.getByText("反向证据")).toBeInTheDocument();
    expect(screen.getByText("是否存在跨平台的同类体验")).toBeInTheDocument();
    expect(screen.getByText("减少重复整理成本")).toBeInTheDocument();
    expect(screen.getAllByText("浏览来源资料")).toHaveLength(2);
    expect(screen.queryByText("资料库")).not.toBeInTheDocument();
  });
});
