import {
  ACTIVE_TASK_STATUSES,
  buildTaskMetrics,
  getEngineState,
  isActiveTask,
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
});
