import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import * as opportunityApi from "../api/opportunity";
import * as researchApi from "../api/research";
import { OpportunitiesPage } from "./opportunities-page";

const timestamp = "2026-08-08T00:00:00Z";

const detail: opportunityApi.OpportunityDetail = {
  id: "opportunity-1",
  opportunity_type: "content_opportunity",
  title: "首次配置复杂形成内容缺口",
  description: "两个独立来源都描述了首次配置困难，但现有内容没有解释最小解决路径。",
  target_user: "正在尝试个人 AI 工具的新用户",
  problem: "用户不知道如何完成首次配置。",
  why_attention: "证据来自两个独立来源，且仍有反向证据未知。",
  why_now: "当前研究样本中出现了重复困惑。",
  next_step: "先验证问题频率和替代方案成本。",
  status: "review_ready",
  readiness: "review_ready",
  version: 1,
  scores: { evidence_strength: 0.7, source_independence: 0.5, actionability: 0.65, counterevidence: 0.2 },
  score_explanation: { summary: "两个独立来源组，仍需验证" },
  unknowns: ["问题频率是否足够高"],
  content_details: { audience: "新用户", content_gap: "没有清晰的首次配置路径", angles: ["教程型", "案例型"], saturation_statement: "仅代表当前研究样本" },
  related_research_task_id: "task-1",
  related_monitoring_mission_id: null,
  related_monitoring_change_id: null,
  related_discovery_candidate_id: null,
  research_space_id: null,
  created_at: timestamp,
  updated_at: timestamp,
  sources: [{ id: "source-1", signal_id: "signal-1", source_type: "research_task", source_id: "task-1", evidence_id: "content:c1", content_id: "c1", finding_id: "finding-1", source_role: "core", evidence_kind: "direct", support_explanation: "直接反馈", source_platform: "bili", source_url: null, source_title: "用户反馈", independent_group: "bili:用户甲", is_repost: false, created_at: timestamp }],
  versions: [{ id: "version-1", version: 1, snapshot: {}, readiness_before: null, readiness_after: "review_ready", change_reason: "initial", created_at: timestamp }],
  score_history: [{ id: "score-1", version: 1, scores: { evidence_strength: 0.7 }, explanation: {}, readiness: "review_ready", created_at: timestamp }],
  feedback: [],
  validation_plans: [],
  actions: [],
};

function renderPage(path: string, initialOpportunities?: opportunityApi.OpportunitySummary[]) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  if (initialOpportunities) queryClient.setQueryData(["opportunities"], initialOpportunities);
  render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={[path]}><Routes><Route path="/opportunities" element={<OpportunitiesPage />} /><Route path="/opportunities/:opportunityId" element={<OpportunitiesPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("OpportunitiesPage", () => {
  beforeEach(() => {
    vi.spyOn(opportunityApi, "listOpportunities").mockResolvedValue([]);
    vi.spyOn(opportunityApi, "getOpportunity").mockResolvedValue(detail);
    vi.spyOn(researchApi, "listResearchSpaces").mockResolvedValue([]);
  });

  it("explains the evidence-bound empty state", async () => {
    renderPage("/opportunities", []);
    expect(await screen.findByRole("heading", { name: "目前还没有足够证据形成值得行动的机会" })).toBeInTheDocument();
    expect(screen.getByText(/AI会逐步形成机会候选/)).toBeInTheDocument();
  });

  it("shows an opportunity card and evidence tab", async () => {
    vi.spyOn(opportunityApi, "listOpportunities").mockResolvedValue([detail]);
    renderPage("/opportunities/opportunity-1");
    expect(await screen.findByRole("heading", { name: detail.title })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "证据" }));
    expect(screen.getByText("Evidence Pack · 1")).toBeInTheDocument();
    expect(screen.getByText("直接反馈")).toBeInTheDocument();
  });
});
