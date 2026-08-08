import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    event_aggregation: {
      first_seen: "2026-08-01T00:00:00Z",
      latest_seen: "2026-08-03T00:00:00Z",
      related_entities: ["AI 工作台"],
      platforms: ["bili", "zhihu"],
      positive_evidence_count: 1,
      negative_evidence_count: 1,
      unknown_evidence_count: 0,
    },
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
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByRole("heading", { name: "AI 工作台登录摩擦" }, { timeout: 10_000 })).toBeInTheDocument();
    expect(screen.queryByText("为什么相关")).not.toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "为什么推荐" }));
    expect(screen.getByText("为什么相关")).toBeInTheDocument();
    expect(screen.getByText("继续寻找独立用户证据。")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "后续动作" }));
    await user.click(screen.getByRole("button", { name: /加入研究空间/ }));
    expect(screen.getByText("还没有研究空间，先创建一个再收藏这条发现。")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /^证据/ }));
    expect(screen.getByText("真实登录体验")).toBeInTheDocument();
    expect(screen.getAllByText("独立来源").length).toBeGreaterThan(0);
  }, 10_000);

  it("renders event aggregation and unavailable experimental status", async () => {
    const eventCandidate: DiscoveryCandidateDetail = {
      ...candidate,
      candidate_type: "event",
      title: "AI 工作台版本变化",
      experimental_status: "experimental_not_available",
    };
    vi.mocked(researchApi.getDiscovery).mockResolvedValue(eventCandidate);
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByRole("heading", { name: "AI 工作台版本变化" }, { timeout: 10_000 })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "相关对象" }));
    expect(screen.getByText("时间范围")).toBeInTheDocument();
    expect(screen.getByText("2026-08-01T00:00:00Z → 2026-08-03T00:00:00Z")).toBeInTheDocument();
    expect(screen.getByText("平台：bili、zhihu")).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "技术详情" }));
    await user.click(screen.getByRole("button", { name: /技术详情/ }));
    expect(screen.getByText("扩展关系暂不可用：experimental_not_available")).toBeInTheDocument();
  });

  it("exposes explicit topic and ranking feedback actions", async () => {
    const giveFeedback = vi.spyOn(researchApi, "giveDiscoveryFeedback").mockResolvedValue(candidate);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "AI 工作台登录摩擦" }, { timeout: 10_000 });
    await user.click(screen.getByRole("button", { name: "判断" }));
    expect(screen.getByRole("menuitem", { name: "稍后" })).toBeInTheDocument();
    expect(screen.getByRole("menuitem", { name: "降低同类优先级" })).toBeInTheDocument();
    await user.click(screen.getByRole("menuitem", { name: "静默主题" }));
    await waitFor(() => expect(giveFeedback).toHaveBeenCalledWith("candidate-1", {
      feedback_type: "mute_topic",
      scope: "topic",
      scope_key: "pain:login",
    }));
  });

  it("undoes the newest feedback action", async () => {
    const latestCandidate: DiscoveryCandidateDetail = {
      ...candidate,
      feedback: [
        {
          id: "feedback-new",
          candidate_id: "candidate-1",
          target_type: "candidate",
          target_key: "pain:login",
          feedback_type: "irrelevant",
          scope: "global",
          scope_key: null,
          weight: 1,
          reason: "newest",
          follow_up_task_id: null,
          undone_at: null,
          created_at: "2026-08-03T00:00:02Z",
        },
        {
          id: "feedback-old",
          candidate_id: "candidate-1",
          target_type: "candidate",
          target_key: "pain:login",
          feedback_type: "valuable",
          scope: "global",
          scope_key: null,
          weight: 1,
          reason: "oldest",
          follow_up_task_id: null,
          undone_at: null,
          created_at: "2026-08-03T00:00:01Z",
        },
      ],
    };
    const giveFeedback = vi.spyOn(researchApi, "giveDiscoveryFeedback").mockResolvedValue(latestCandidate);
    vi.mocked(researchApi.getDiscovery).mockResolvedValue(latestCandidate);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "AI 工作台登录摩擦" }, { timeout: 10_000 });
    await user.click(screen.getByRole("button", { name: "判断" }));
    await user.click(screen.getByRole("menuitem", { name: /撤销最近反馈/ }));
    await waitFor(() => expect(giveFeedback).toHaveBeenCalledWith("candidate-1", {
      undo_feedback_id: "feedback-new",
    }));
  });
});
