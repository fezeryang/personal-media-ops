import {
  giveDiscoveryFeedback,
  listDiscoveries,
  listResearchSpaces,
} from "./research";

const candidate = {
  id: "candidate-1",
  research_task_id: "task-1",
  candidate_type: "pain_point",
  title: "本地 AI 工作台的登录摩擦",
  summary: "来源记录了真实使用限制，需要独立证据。",
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
    why_relevant: "与当前研究意图相关。",
    recommendation: "继续寻找独立来源。",
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
  sources: [],
  scores: [],
  feedback: [],
  lifecycle: [],
};

describe("research discovery API", () => {
  it("encodes bounded discovery filters and validates candidate details", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([candidate]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(
      listDiscoveries({ state: "queued", researchTaskId: "task/1", limit: 20 }, undefined),
    ).resolves.toEqual([expect.objectContaining({
      id: candidate.id,
      title: candidate.title,
      final_score: candidate.final_score,
      state: candidate.state,
    })]);
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/research/discoveries?state=queued&research_task_id=task%2F1&limit=20",
      expect.objectContaining({ credentials: "include" }),
    );
  });

  it("sends owner feedback through the explicit API contract", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify(candidate), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await giveDiscoveryFeedback("candidate/1", {
      feedback_type: "valuable",
      scope: "global",
      reason: "与当前问题直接相关",
    });

    expect(fetchMock).toHaveBeenCalledWith(
      "/api/research/discoveries/candidate%2F1/feedback",
      expect.objectContaining({
        method: "POST",
        body: JSON.stringify({
          feedback_type: "valuable",
          scope: "global",
          reason: "与当前问题直接相关",
        }),
      }),
    );
  });

  it("validates research spaces as a separate resource", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify([
        {
          id: "space-1",
          name: "个人 AI 机会",
          description: "持续追踪",
          status: "active",
          item_count: 1,
          created_at: "2026-08-03T00:00:00Z",
          updated_at: "2026-08-03T00:00:00Z",
        },
      ]), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    await expect(listResearchSpaces()).resolves.toHaveLength(1);
  });
});
