import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

const monitoringMocks = vi.hoisted(() => {
  const budget = {
    max_model_calls: 4,
    max_total_tokens: 4000,
    max_collection_count: 20,
    max_platforms: 2,
    max_runtime_seconds: 120,
    daily_token_budget: 10000,
    weekly_run_budget: 7,
  };
  const baseMission = {
    id: "mission-1",
    title: "持续关注 AI 产品变化",
    goal: "持续了解个人 AI 工作台的新功能、用户反馈和重要变化。",
    mission_type: "topic",
    status: "active",
    schedule_type: "daily",
    schedule_config: {},
    platforms: ["bili", "zhihu"],
    understanding: { interpreted_goal: "关注 AI 产品变化" },
    budget,
    next_run_at: "2026-08-09T00:00:00Z",
    last_run_at: "2026-08-08T00:00:00Z",
    last_run_status: "completed",
    latest_change: { title: "出现新的配置反馈" },
    created_at: "2026-08-01T00:00:00Z",
    updated_at: "2026-08-08T00:00:00Z",
  };
  const pausedMission = {
    ...baseMission,
    id: "mission-2",
    title: "暂停的竞品监控",
    status: "paused",
    latest_change: null,
  };
  const detail = {
    ...baseMission,
    targets: [{ id: "target-1", target_type: "topic", target_value: "个人 AI 工作台" }],
    importance_rule: "新颖、相关且有独立来源的变化进入收件箱。",
    ignored_content_rule: "忽略重复转载和基础介绍。",
    consecutive_failures: 0,
    last_error: null,
  };
  const run = {
    id: "run-1",
    mission_id: "mission-1",
    research_task_id: null,
    status: "completed",
    trigger: "scheduled",
    started_at: "2026-08-08T00:00:00Z",
    completed_at: "2026-08-08T00:01:00Z",
    baseline_created: false,
    change_count: 1,
    notification_count: 1,
    resource: { collection_count: 3, model_calls: 1 },
    failure_reason: null,
    backoff_until: null,
    claimed_at: null,
    created_at: "2026-08-08T00:00:00Z",
    queries: [{ id: "query-1", query: "AI 工作台", platform: "bili", new_content_count: 2 }],
  };
  const baseline = {
    id: "baseline-1",
    mission_id: "mission-1",
    version: 2,
    snapshot: { content_ids: ["content-1"] },
    source_run_id: "run-1",
    created_at: "2026-08-08T00:00:00Z",
  };
  const change = {
    id: "change-1",
    source_type: "monitoring",
    mission_id: "mission-1",
    run_id: "run-1",
    change_type: "new_feature",
    fingerprint: "change-1",
    title: "出现新的配置反馈",
    summary: "多个来源开始讨论配置体验。",
    first_seen_at: "2026-08-08T00:00:00Z",
    latest_seen_at: "2026-08-08T00:00:00Z",
    relevance_score: 0.8,
    novelty_score: 0.7,
    evidence_strength_score: 0.7,
    source_independence_score: 0.6,
    cross_platform_score: 0.5,
    actionability_score: 0.6,
    persistence_score: 0.5,
    noise_risk_score: 0.1,
    attention_level: "immediate_attention",
    state: "new",
    explanation: {},
    sources: [],
    memory_update: null,
    created_at: "2026-08-08T00:00:00Z",
    updated_at: "2026-08-08T00:00:00Z",
  };
  const notification = {
    id: "notification-1",
    mission_id: "mission-1",
    change_id: "change-1",
    level: "immediate_attention",
    status: "unread",
    title: "出现新的配置反馈",
    summary: "多个来源开始讨论配置体验。",
    created_at: "2026-08-08T00:00:00Z",
    read_at: null,
    deferred_until: null,
    ignored_at: null,
  };
  const query = <T,>(data: T) => ({ data, isPending: false, isError: false, error: null, refetch: vi.fn() });
  return {
    baseMission,
    pausedMission,
    detail,
    run,
    baseline,
    change,
    notification,
    archive: vi.fn(),
    missionsQuery: query([baseMission, pausedMission]),
    detailQuery: query(detail),
    runsQuery: query([run]),
    changesQuery: query([change]),
    baselineQuery: query(baseline),
    notificationsQuery: query([notification]),
    mutation: () => ({ mutate: vi.fn(), isPending: false, isError: false, error: null }),
  };
});

vi.mock("../features/monitoring/hooks/use-monitoring-queries", () => ({
  useMonitoringMissionsQuery: () => monitoringMocks.missionsQuery,
  useMonitoringMissionQuery: () => monitoringMocks.detailQuery,
  useMonitoringRunsQuery: () => monitoringMocks.runsQuery,
  useMonitoringChangesQuery: () => monitoringMocks.changesQuery,
  useMonitoringBaselineQuery: () => monitoringMocks.baselineQuery,
  useMonitoringNotificationsQuery: () => monitoringMocks.notificationsQuery,
  useArchiveMonitoringMissionMutation: () => ({ ...monitoringMocks.mutation(), mutate: monitoringMocks.archive }),
  useConfirmMonitoringMissionMutation: () => monitoringMocks.mutation(),
  useCreateMonitoringMissionMutation: () => monitoringMocks.mutation(),
  usePauseMonitoringMissionMutation: () => monitoringMocks.mutation(),
  useResumeMonitoringMissionMutation: () => monitoringMocks.mutation(),
  useRunMonitoringMissionMutation: () => monitoringMocks.mutation(),
  useUpdateMonitoringNotificationMutation: () => monitoringMocks.mutation(),
}));

import { MonitoringMissionsPage } from "./monitoring-missions-page";

function renderPage(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/monitoring" element={<MonitoringMissionsPage />} />
          <Route path="/monitoring/:missionId" element={<MonitoringMissionsPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("MonitoringMissionsPage", () => {
  it("filters missions and exposes structured detail actions", async () => {
    const user = userEvent.setup();
    renderPage("/monitoring");

    expect(await screen.findByText("持续关注 AI 产品变化")).toBeInTheDocument();
    expect(screen.getByText("暂停的竞品监控")).toBeInTheDocument();

    await user.selectOptions(screen.getAllByLabelText("监控状态")[0], "running");
    expect(screen.getByText("持续关注 AI 产品变化")).toBeInTheDocument();
    expect(screen.queryByText("暂停的竞品监控")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /持续关注 AI 产品变化/ }));

    expect(await screen.findByRole("heading", { name: "正在监控什么，最近发生了什么？" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "运行记录" })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: "运行记录" }));
    await user.click(screen.getByText(/运行详情 · 1 条查询/));
    expect(screen.getByText("AI 工作台")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "更多" }));
    await user.click(screen.getByRole("menuitem", { name: "归档" }));
    expect(screen.getByRole("alertdialog", { name: "归档这个监控？" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "确认归档" }));
    await waitFor(() => expect(monitoringMocks.archive).toHaveBeenCalledWith("mission-1"));
  });
});
