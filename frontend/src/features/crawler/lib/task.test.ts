import {
  ACTIVE_TASK_STATUSES,
  buildTaskMetrics,
  capabilityStatusLabel,
  filterCrawlerTasks,
  getEngineState,
  isActiveTask,
  platformIconLabel,
  platformLoginPrompt,
  platformDisplayName,
  taskStatusLabel,
} from "./task";
import type { CrawlerTask } from "../../../api/crawler";

const baseTask: CrawlerTask = {
  id: "task-1",
  platform: "bili",
  crawler_type: "search",
  keywords: "AI Agent",
  login_type: "qrcode",
  status: "pending",
  requested_count: 20,
  actual_count: 0,
  output_dir: "/private/output",
  log_path: "/private/log",
  qrcode_path: "/private/qr",
  pid: null,
  error_message: null,
  created_at: "2026-07-26T12:00:00Z",
  started_at: null,
  finished_at: null,
  cancel_requested: false,
};

describe("crawler task helpers", () => {
  it("maps every status to Chinese", () => {
    expect(ACTIVE_TASK_STATUSES).toEqual([
      "pending",
      "running",
      "waiting_login",
    ]);
    expect(taskStatusLabel("waiting_login")).toBe("等待登录");
    expect(taskStatusLabel("succeeded")).toBe("已完成");
  });

  it("recognizes active and terminal tasks", () => {
    expect(isActiveTask(baseTask)).toBe(true);
    expect(
      isActiveTask({ ...baseTask, status: "cancelled" }),
    ).toBe(false);
  });

  it("derives dashboard metrics from real tasks", () => {
    const tasks = [
      baseTask,
      { ...baseTask, id: "2", status: "running" as const },
      { ...baseTask, id: "3", status: "waiting_login" as const },
      { ...baseTask, id: "4", status: "succeeded" as const },
      { ...baseTask, id: "5", status: "failed" as const },
    ];

    expect(buildTaskMetrics(tasks)).toEqual({
      total: 5,
      running: 1,
      waitingLogin: 1,
      succeeded: 1,
      failed: 1,
    });
  });

  it("reports only task-derived engine states", () => {
    expect(getEngineState([], false).label).toBe("连接异常");
    expect(getEngineState([], true).label).toBe("接口可用");
    expect(
      getEngineState([{ ...baseTask, status: "waiting_login" }], true).label,
    ).toBe("等待扫码");
    expect(
      getEngineState([{ ...baseTask, status: "running" }], true).label,
    ).toBe("执行中");
    expect(getEngineState([baseTask], true).label).toBe("队列待处理");
  });

  it("uses capability metadata for platform display names", () => {
    const capability = {
      platform: "xhs",
      display_name: "小红书",
      icon_label: "红",
      enabled: true,
      verification_status: "code_ready" as const,
      availability_status: "enabled" as const,
      login_prompt: "使用小红书客户端扫码登录",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 20 },
      supports_comments: false,
      supports_sub_comments: false,
    };

    expect(platformDisplayName("xhs", [capability])).toBe("小红书");
    expect(platformIconLabel("xhs", [capability])).toBe("红");
    expect(platformLoginPrompt("xhs", [capability])).toBe(
      "使用小红书客户端扫码登录",
    );
    expect(platformDisplayName("unknown", [capability])).toBe("unknown");
    expect(
      getEngineState(
        [{ ...baseTask, platform: "xhs", status: "waiting_login" }],
        true,
        [capability],
      ).detail,
    ).toContain("小红书");
  });

  it("keeps verification and availability labels independent", () => {
    expect(
      capabilityStatusLabel({
        verification_status: "production_verified",
        availability_status: "disabled",
        enabled: false,
      }),
    ).toBe("（已生产验证，未启用）");
    expect(
      capabilityStatusLabel({
        verification_status: "code_ready",
        availability_status: "deferred_resource_constrained",
        enabled: false,
      }),
    ).toBe("（资源限制，暂不可用）");
  });

  it("filters tasks by platform, status, and search text", () => {
    const tasks = [
      baseTask,
      {
        ...baseTask,
        id: "task-2",
        platform: "xhs",
        keywords: "人工智能",
        status: "succeeded" as const,
      },
    ];

    expect(
      filterCrawlerTasks(tasks, {
        platform: "xhs",
        status: "succeeded",
        search: "人工",
      }),
    ).toEqual([tasks[1]]);
    expect(
      filterCrawlerTasks(tasks, {
        platform: "bili",
        status: "all",
        search: "",
      }),
    ).toEqual([tasks[0]]);
  });
});
