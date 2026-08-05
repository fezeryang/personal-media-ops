import {
  discoveryCandidateDetailSchema,
  researchSpaceDetailSchema,
  researchTaskDetailSchema,
  type DiscoveryCandidateDetail,
  type ResearchSpaceDetail,
  type ResearchTaskDetail,
} from "../api/research";

const timestamp = "2026-08-05T00:00:00Z";

export const researchStatusFixtures = [
  { status: "Draft", label: "草稿", description: "用户目标已保存，等待解释" },
  { status: "Planning", label: "规划中", description: "AI 正在拆解意图与研究计划" },
  { status: "Researching", label: "研究中", description: "Runtime 正在执行研究步骤" },
  { status: "WaitingCrawl", label: "等待采集", description: "等待单并发 Worker 执行" },
  { status: "Partial", label: "部分完成", description: "已有结论，但仍有未解决问题" },
  { status: "Done", label: "已完成", description: "研究、证据与发现已收束" },
  { status: "Failed", label: "失败", description: "失败原因必须可见且可恢复" },
  { status: "BudgetExceeded", label: "预算触发", description: "资源边界阻止继续执行" },
] as const;

const taskResponse = {
  id: "fixture-task-8d",
  task_type: "discovery",
  objective: "验证 AI 研究工作台的机会发现闭环",
  platforms: ["bili", "zhihu"],
  status: "Done",
  current_round: 1,
  current_step: "final_report",
  paused: false,
  consumption: {
    crawl_count: 2,
    content_count: 8,
    duration_seconds: 42,
    input_tokens: 1800,
    output_tokens: 620,
    cached_tokens: 0,
    estimated_cost: null,
    cost_enabled: false,
    cost_currency: null,
    model_call_count: 2,
  },
  finding_count: 1,
  event_count: 1,
  action_count: 1,
  created_at: timestamp,
  updated_at: timestamp,
  finished_at: timestamp,
  failure_reason: null,
  stop_reason: "coverage_satisfied",
  primary_intent: "product_opportunity",
  intent_confidence: 0.88,
  plan: { steps: ["interpret_intent", "collect_evidence", "score_discoveries"] },
  context: { fixture: true, source: "local_recorded_response" },
  result: {
    summary: "独立来源显示，研究型工作台的可追溯发现是高价值方向。",
    evidence_count: 2,
    discovery_count: 2,
    independent_evidence_count: 2,
    negative_evidence_count: 1,
  },
  route_snapshot: { route_role: "research", provider: "fixture" },
  budget: {
    crawl_limit: 4,
    content_limit: 20,
    duration_seconds: 300,
    token_limit: 8000,
    cost_limit: null,
    cost_currency: null,
    max_model_calls: 4,
  },
  trace: [],
  findings: [],
  events: [],
  actions: [],
} satisfies Record<string, unknown>;

export const researchFixtureTask: ResearchTaskDetail =
  researchTaskDetailSchema.parse(taskResponse);

const candidateResponse = {
  id: "fixture-candidate-1",
  research_task_id: researchFixtureTask.id,
  candidate_type: "product_opportunity_signal",
  title: "可追溯的研究型工作台",
  summary: "用户愿意为带反向证据和后续行动的研究流程持续投入时间。",
  normalized_key: "traceable-research-workbench",
  parent_candidate_id: null,
  source_seed_id: "fixture-seed-1",
  source_content_id: "fixture-content-1",
  source_platform: "bili",
  relevance_score: 0.92,
  novelty_score: 0.81,
  evidence_strength_score: 0.86,
  source_independence_score: 0.9,
  cross_platform_score: 0.75,
  counterevidence_score: 0.42,
  actionability_score: 0.88,
  feedback_score: 0.5,
  noise_risk_score: 0.12,
  marketing_risk_score: 0.08,
  saturation_score: 0.2,
  resource_cost_score: 0.3,
  final_score: 0.84,
  score_explanation: {
    positive: ["独立来源", "可转为后续研究"],
    counterevidence: "样本仍集中在早期用户，需要更多反例",
  },
  content_count: 3,
  independent_source_count: 2,
  platform_count: 2,
  suspected_repost_count: 0,
  depth: 0,
  state: "scored",
  suggested_next_action: "继续验证目标用户的具体工作流",
  experimental_status: null,
  created_at: timestamp,
  updated_at: timestamp,
  sources: [],
  scores: [],
  feedback: [
    {
      id: "fixture-feedback-1",
      candidate_id: "fixture-candidate-1",
      target_type: "candidate",
      target_key: "traceable-research-workbench",
      feedback_type: "needs_more_evidence",
      scope: "research_intent",
      scope_key: researchFixtureTask.id,
      weight: 0.2,
      reason: "保留候选，但要求反向证据",
      follow_up_task_id: null,
      undone_at: timestamp,
      created_at: timestamp,
    },
  ],
  lifecycle: [{ event: "feedback_undone", at: timestamp }],
} satisfies Record<string, unknown>;

export const researchFixtureCandidate: DiscoveryCandidateDetail =
  discoveryCandidateDetailSchema.parse(candidateResponse);

const spaceResponse = {
  id: "fixture-space-1",
  name: "研究型工作台机会",
  description: "用于验证候选、证据、Finding 与下一轮研究的关联。",
  status: "active",
  item_count: 1,
  created_at: timestamp,
  updated_at: timestamp,
  items: [
    {
      id: "fixture-space-item-1",
      space_id: "fixture-space-1",
      item_type: "discovery_candidate",
      item_id: researchFixtureCandidate.id,
      position: 0,
      note: "等待下一轮研究补充反向证据",
      source_candidate_id: researchFixtureCandidate.id,
      item: { title: researchFixtureCandidate.title, state: "scored" },
      created_at: timestamp,
      updated_at: timestamp,
    },
  ],
} satisfies Record<string, unknown>;

export const researchFixtureSpace: ResearchSpaceDetail =
  researchSpaceDetailSchema.parse(spaceResponse);

export const researchFixtureEvidence = [
  { type: "direct", label: "直接证据", detail: "两个平台的独立来源" },
  { type: "contradictory", label: "反向证据", detail: "早期用户样本可能偏重" },
  { type: "background", label: "背景资料", detail: "研究工具的长期使用场景" },
] as const;

export const researchFixtureMemory = [
  { type: "Finding", detail: "可追溯性是候选转行动的关键" },
  { type: "Event Candidate", detail: "研究工作流出现跨平台迁移需求" },
  { type: "Memory Update", detail: "后续研究需优先收集反向证据" },
] as const;
