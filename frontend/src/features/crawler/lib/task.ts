import type {
  CrawlerTask,
  CrawlerTaskStatus,
} from "../../../api/crawler";

export const ACTIVE_TASK_STATUSES = [
  "pending",
  "running",
  "waiting_login",
] as const satisfies readonly CrawlerTaskStatus[];

export const TASK_STATUS_LABELS: Record<CrawlerTaskStatus, string> = {
  pending: "等待执行",
  running: "采集中",
  waiting_login: "等待登录",
  succeeded: "已完成",
  failed: "失败",
  cancelled: "已取消",
};

export interface TaskMetrics {
  total: number;
  running: number;
  waitingLogin: number;
  succeeded: number;
  failed: number;
}

export interface EngineState {
  label: string;
  detail: string;
  tone: "neutral" | "info" | "warning" | "danger";
}

export function taskStatusLabel(status: CrawlerTaskStatus): string {
  return TASK_STATUS_LABELS[status];
}

export function isActiveStatus(status: CrawlerTaskStatus): boolean {
  return ACTIVE_TASK_STATUSES.some((active) => active === status);
}

export function isActiveTask(task: CrawlerTask): boolean {
  return isActiveStatus(task.status);
}

export function buildTaskMetrics(tasks: CrawlerTask[]): TaskMetrics {
  return tasks.reduce<TaskMetrics>(
    (metrics, task) => {
      metrics.total += 1;
      if (task.status === "running") metrics.running += 1;
      if (task.status === "waiting_login") metrics.waitingLogin += 1;
      if (task.status === "succeeded") metrics.succeeded += 1;
      if (task.status === "failed") metrics.failed += 1;
      return metrics;
    },
    { total: 0, running: 0, waitingLogin: 0, succeeded: 0, failed: 0 },
  );
}

export function getEngineState(
  tasks: CrawlerTask[],
  apiConnected: boolean,
): EngineState {
  if (!apiConnected) {
    return {
      label: "连接异常",
      detail: "无法连接后端接口",
      tone: "danger",
    };
  }
  if (tasks.some((task) => task.status === "waiting_login")) {
    return {
      label: "等待扫码",
      detail: "采集任务正在等待哔哩哔哩登录",
      tone: "warning",
    };
  }
  if (tasks.some((task) => task.status === "running")) {
    return {
      label: "执行中",
      detail: "单任务采集引擎正在工作",
      tone: "info",
    };
  }
  if (tasks.some((task) => task.status === "pending")) {
    return {
      label: "队列待处理",
      detail: "已有任务等待 Worker 领取",
      tone: "warning",
    };
  }
  return {
    label: "接口可用",
    detail: "当前没有活动采集任务",
    tone: "neutral",
  };
}
