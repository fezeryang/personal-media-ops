import type {
  CrawlerPlatformCapability,
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

type CapabilityStatus = Pick<
  CrawlerPlatformCapability,
  "availability_status" | "enabled" | "verification_status"
>;

export interface TaskFilters {
  status: "all" | CrawlerTaskStatus;
  platform: string;
  search: string;
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

export function platformDisplayName(
  platform: string,
  capabilities: readonly CrawlerPlatformCapability[] = [],
): string {
  return (
    capabilities.find((capability) => capability.platform === platform)
      ?.display_name ?? platform
  );
}

export function platformIconLabel(
  platform: string,
  capabilities: readonly CrawlerPlatformCapability[] = [],
): string {
  return (
    capabilities.find((capability) => capability.platform === platform)
      ?.icon_label ?? platform.slice(0, 1)
  );
}

export function platformLoginPrompt(
  platform: string,
  capabilities: readonly CrawlerPlatformCapability[] = [],
): string {
  return (
    capabilities.find((capability) => capability.platform === platform)
      ?.login_prompt ?? "按任务状态完成平台登录"
  );
}

export function capabilityStatusLabel(capability: CapabilityStatus): string {
  if (!capability.enabled) {
    const unavailableLabels: Record<
      Exclude<
        CrawlerPlatformCapability["availability_status"],
        "enabled"
      >,
      string
    > = {
      disabled:
        capability.verification_status === "production_verified"
          ? "（已生产验证，未启用）"
          : capability.verification_status === "not_implemented"
            ? "（尚未实现）"
            : "（代码就绪，未启用）",
      deferred_resource_constrained: "（资源限制，暂不可用）",
      deferred_upstream_breakage: "（上游异常，暂不可用）",
      deferred_login_required: "（需要登录验证，暂不可用）",
    };
    if (capability.availability_status !== "enabled") {
      return unavailableLabels[capability.availability_status];
    }
  }
  if (capability.verification_status === "production_verified") {
    return "（已生产验证）";
  }
  if (capability.verification_status === "not_implemented") {
    return "（尚未实现）";
  }
  return "（代码就绪，已启用）";
}

export function filterCrawlerTasks(
  tasks: readonly CrawlerTask[],
  filters: TaskFilters,
): CrawlerTask[] {
  const needle = filters.search.trim().toLocaleLowerCase("zh-CN");
  return tasks.filter((task) => {
    const matchesStatus =
      filters.status === "all" || task.status === filters.status;
    const matchesPlatform =
      filters.platform === "all" || task.platform === filters.platform;
    const matchesSearch =
      !needle ||
      task.keywords.toLocaleLowerCase("zh-CN").includes(needle) ||
      task.id.toLocaleLowerCase("zh-CN").includes(needle);
    return matchesStatus && matchesPlatform && matchesSearch;
  });
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
  capabilities: readonly CrawlerPlatformCapability[] = [],
): EngineState {
  if (!apiConnected) {
    return {
      label: "连接异常",
      detail: "无法连接后端接口",
      tone: "danger",
    };
  }
  const waitingTask = tasks.find(
    (task) => task.status === "waiting_login",
  );
  if (waitingTask) {
    return {
      label: "等待扫码",
      detail: `采集任务正在等待${platformDisplayName(waitingTask.platform, capabilities)}登录`,
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
