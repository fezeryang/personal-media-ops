import {
  ACTIVE_TASK_STATUSES,
  buildTaskMetrics,
  capabilityStatusLabel,
  filterCrawlerTasks,
  getEngineState,
  isActiveTask,
  modeCapabilityStatusLabel,
  platformIconLabel,
  platformLoginPrompt,
  platformDisplayName,
  taskPrimaryLabel,
  taskStatusLabel,
} from "./task";
import type {
  CrawlerPlatformCapability,
  CrawlerTask,
} from "../../../api/crawler";

const baseTask: CrawlerTask = {
  id: "task-1",
  platform: "bili",
  mode: "search",
  crawler_type: "search",
  keywords: "AI Agent",
  target_ids: [],
  target_urls: [],
  creator_ids: [],
  creator_urls: [],
  parent_content_id: null,
  parent_comment_id: null,
  login_type: "qrcode",
  status: "pending",
  requested_count: 20,
  actual_count: 0,
  requested_comment_count: 0,
  requested_sub_comment_count: 0,
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
      supports_comments: true,
      supports_sub_comments: true,
      modes: ([
        "search",
        "detail",
        "creator",
        "comments",
        "sub_comments",
      ] as const).map((mode) => ({
        mode,
        label: mode,
        status: "enabled" as const,
        enabled: true,
        reason: null,
        input_fields: [],
        requested_count: { minimum: 1, maximum: 20, default: 1 },
        requested_comment_count: null,
        requested_sub_comment_count: null,
        requires_browser: true,
        login_type: "qrcode" as const,
      })),
    } satisfies CrawlerPlatformCapability;

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
        modes: [],
      }),
    ).toBe("（已生产验证，未启用）");
    expect(
      capabilityStatusLabel({
        verification_status: "code_ready",
        availability_status: "deferred_resource_constrained",
        enabled: false,
        modes: [],
      }),
    ).toBe("（资源限制，暂不可用）");
    expect(
      capabilityStatusLabel({
        verification_status: "not_implemented",
        availability_status: "disabled",
        enabled: false,
        modes: [],
      }),
    ).toBe("（尚未实现）");
    expect(
      capabilityStatusLabel({
        verification_status: "code_ready",
        availability_status: "disabled",
        enabled: false,
        modes: [],
      }),
    ).toBe("（代码就绪，未启用）");
    expect(
      capabilityStatusLabel({
        verification_status: "production_verified",
        availability_status: "enabled",
        enabled: true,
        modes: [],
      }),
    ).toBe("（已生产验证）");
    expect(
      capabilityStatusLabel({
        verification_status: "code_ready",
        availability_status: "deferred_upstream_breakage",
        enabled: false,
        modes: [
          {
            mode: "detail",
            label: "内容详情",
            status: "enabled",
            enabled: true,
            reason: null,
            input_fields: ["target_ids"],
            requested_count: { minimum: 1, maximum: 20, default: 1 },
            requested_comment_count: null,
            requested_sub_comment_count: null,
            requires_browser: true,
            login_type: "qrcode",
          },
        ],
      }),
    ).toBe("（部分模式已启用）");
  });

  it("labels every mode-level capability state accurately", () => {
    expect(
      modeCapabilityStatusLabel({
        status: "production_verified",
        enabled: true,
      }),
    ).toBe("（已生产验证）");
    expect(
      modeCapabilityStatusLabel({ status: "enabled", enabled: true }),
    ).toBe("（代码就绪，已启用）");
    expect(
      modeCapabilityStatusLabel({ status: "enabled", enabled: false }),
    ).toBe("（已启用）");
    expect(
      modeCapabilityStatusLabel({
        status: "deferred_platform_change",
        enabled: false,
      }),
    ).toBe("（平台变化）");
  });

  it("chooses a useful primary label for every task mode", () => {
    expect(taskPrimaryLabel(baseTask)).toBe("AI Agent");
    expect(
      taskPrimaryLabel({
        ...baseTask,
        mode: "detail",
        crawler_type: "detail",
        keywords: null,
        target_urls: ["https://example.test/content"],
      }),
    ).toBe("https://example.test/content");
    expect(
      taskPrimaryLabel({
        ...baseTask,
        mode: "sub_comments",
        crawler_type: "sub_comments",
        keywords: null,
        parent_comment_id: "comment-42",
      }),
    ).toBe("comment-42");
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
