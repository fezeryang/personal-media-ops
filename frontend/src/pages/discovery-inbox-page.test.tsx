import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import * as researchApi from "../api/research";
import type { DiscoveryCandidateDetail, DiscoveryCandidateSummary } from "../api/research";
import { DiscoveryInboxPage } from "./discovery-inbox-page";

const candidate: DiscoveryCandidateDetail = {
  id: "candidate-1",
  research_task_id: "task-1",
  candidate_type: "pain_point",
  title: "AI 工作台登录摩擦",
  summary: "真实内容记录了登录限制。",
  normalized_key: "pain:login",
  parent_candidate_id: null,
  source_seed_id: "seed-1",
  source_content_id: "content-1",
  source_platform: "bili",
  relevance_score: 0.9,
  novelty_score: 0.8,
  evidence_strength_score: 0.7,
  source_independence_score: 0.6,
  cross_platform_score: 0.5,
  counterevidence_score: 0.7,
  actionability_score: 0.82,
  feedback_score: 0.5,
  noise_risk_score: 0.1,
  marketing_risk_score: 0.05,
  saturation_score: 0.1,
  resource_cost_score: 0.2,
  final_score: 0.74,
  score_explanation: {
    why_relevant: "与当前研究目标相关。",
    why_new: "历史记忆中尚无同键记录。",
    evidence: "2 条内容，2 个独立来源。",
    source_independence: "覆盖 2 个平台。",
    counterevidence: "记录到 1 条反向证据。",
    risks: "营销风险较低。",
    recommendation: "继续寻找独立用户证据。",
  },
  content_count: 2,
  independent_source_count: 2,
  platform_count: 2,
  suspected_repost_count: 0,
  depth: 1,
  state: "queued",
  suggested_next_action: "继续验证",
  experimental_status: null,
  created_at: "2026-08-03T00:00:00Z",
  updated_at: "2026-08-03T00:00:00Z",
  sources: [{
    id: "source-1",
    seed_id: "seed-1",
    research_task_id: "task-1",
    content_id: "content-1",
    platform: "bili",
    source_kind: "evidence",
    source_title: "真实登录体验",
    source_author: "作者",
    source_url: "https://example.test/content-1",
    is_repost: false,
    repost_of_content_id: null,
    similarity_score: null,
    independent_group: "author:bili:author",
    created_at: "2026-08-03T00:00:00Z",
  }],
  scores: [],
  feedback: [],
  lifecycle: [],
};

const summary: DiscoveryCandidateSummary = { ...candidate };

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/discoveries/candidate-1"]}><Routes><Route path="/discoveries/:candidateId" element={<DiscoveryInboxPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("DiscoveryInboxPage", () => {
  beforeEach(() => {
    vi.spyOn(researchApi, "listDiscoveries").mockResolvedValue([summary]);
    vi.spyOn(researchApi, "getDiscovery").mockResolvedValue(candidate);
    vi.spyOn(researchApi, "listResearchSpaces").mockResolvedValue([]);
  });

  it("renders source-bound explanations and honest follow-up controls", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "AI 工作台登录摩擦" })).toBeInTheDocument();
    expect(screen.getByText("为什么相关")).toBeInTheDocument();
    expect(screen.getByText("继续寻找独立用户证据。")).toBeInTheDocument();
    expect(screen.getByText("还没有研究空间，先创建一个再收藏这条发现。")).toBeInTheDocument();
    expect(screen.getByText("真实登录体验")).toBeInTheDocument();
  });
});
