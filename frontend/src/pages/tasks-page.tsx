import { Filter, Search } from "lucide-react";
import { useMemo, useState } from "react";

import type { CrawlerTaskStatus } from "../api/crawler";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { CreateTaskDialog } from "../features/crawler/components/create-task-dialog";
import { TaskTable } from "../features/crawler/components/task-table";
import {
  useCrawlerCapabilitiesQuery,
  useCrawlerTasksQuery,
} from "../features/crawler/hooks/use-crawler-queries";
import {
  filterCrawlerTasks,
  TASK_STATUS_LABELS,
} from "../features/crawler/lib/task";

type StatusFilter = "all" | CrawlerTaskStatus;
type PlatformFilter = string;

export function TasksPage() {
  const tasksQuery = useCrawlerTasksQuery();
  const capabilitiesQuery = useCrawlerCapabilitiesQuery();
  const [status, setStatus] = useState<StatusFilter>("all");
  const [platform, setPlatform] = useState<PlatformFilter>("all");
  const [search, setSearch] = useState("");

  const filteredTasks = useMemo(() => {
    return filterCrawlerTasks(tasksQuery.data ?? [], {
      platform,
      search,
      status,
    });
  }, [platform, search, status, tasksQuery.data]);
  const enabledPlatformNames = (
    capabilitiesQuery.data?.platforms.filter((platform) =>
      platform.modes.some((mode) => mode.enabled),
    ) ??
    []
  ).map((platform) => platform.display_name);

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Crawler operations"
        title="采集中心"
        description={`创建并管理${enabledPlatformNames.length ? enabledPlatformNames.join("、") : "已启用平台"}的搜索、详情、创作者与评论任务。服务器采用单任务串行执行。`}
        action={<CreateTaskDialog />}
      />

      <Card className="overflow-hidden">
        <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="relative w-full sm:max-w-sm">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              value={search}
              onChange={(event) => setSearch(event.currentTarget.value)}
              placeholder="搜索关键词或任务 ID"
              aria-label="搜索任务"
            />
          </div>
          <div className="flex w-full flex-col gap-3 sm:w-auto sm:flex-row">
            <div className="relative w-full sm:w-44">
              <Filter className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
              <select
                className="h-10 w-full appearance-none rounded-lg border border-line bg-white pl-9 pr-3 text-sm font-medium text-ink outline-none focus:border-signal focus:ring-2 focus:ring-signal/12"
                value={platform}
                onChange={(event) => setPlatform(event.currentTarget.value)}
                aria-label="按平台筛选"
              >
                <option value="all">全部平台</option>
                {(capabilitiesQuery.data?.platforms ?? []).map((capability) => (
                  <option key={capability.platform} value={capability.platform}>
                    {capability.display_name}
                  </option>
                ))}
              </select>
            </div>
            <div className="relative w-full sm:w-44">
            <Filter className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <select
              className="h-10 w-full appearance-none rounded-lg border border-line bg-white pl-9 pr-3 text-sm font-medium text-ink outline-none focus:border-signal focus:ring-2 focus:ring-signal/12"
              value={status}
              onChange={(event) =>
                setStatus(event.currentTarget.value as StatusFilter)
              }
              aria-label="按状态筛选"
            >
              <option value="all">全部状态</option>
              {Object.entries(TASK_STATUS_LABELS).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
            </div>
          </div>
        </div>

        {tasksQuery.isError ? (
          <div className="p-5">
            <ErrorState
              error={tasksQuery.error}
              onRetry={() => void tasksQuery.refetch()}
            />
          </div>
        ) : tasksQuery.isPending ? (
          <div className="space-y-3 p-5" aria-label="正在加载任务">
            {Array.from({ length: 4 }, (_, index) => (
              <div
                key={index}
                className="h-16 animate-pulse rounded-xl bg-paper"
              />
            ))}
          </div>
        ) : (
          <>
            <TaskTable tasks={filteredTasks} />
            <div className="flex items-center justify-between border-t border-line bg-paper/60 px-5 py-3 text-xs text-muted">
              <span>
                显示 {filteredTasks.length} / {tasksQuery.data.length} 个任务
              </span>
              <span>列表每 3–15 秒按活动状态刷新</span>
            </div>
          </>
        )}
      </Card>
    </div>
  );
}
