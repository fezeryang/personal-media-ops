import {
  ArrowLeft,
  CalendarClock,
  CheckCircle2,
  CircleDot,
  Hash,
  Search,
} from "lucide-react";
import { Link, useParams } from "react-router";

import { ErrorState } from "../components/error-state";
import { Button } from "../components/ui/button";
import { Card, CardContent } from "../components/ui/card";
import { CancelTaskDialog } from "../features/crawler/components/cancel-task-dialog";
import { LogViewer } from "../features/crawler/components/log-viewer";
import { QrcodePanel } from "../features/crawler/components/qrcode-panel";
import { ResultBrowser } from "../features/crawler/components/result-browser";
import { TaskStatusBadge } from "../features/crawler/components/task-status-badge";
import {
  useCrawlerCapabilitiesQuery,
  useCrawlerTaskQuery,
} from "../features/crawler/hooks/use-crawler-queries";
import {
  isActiveTask,
  platformDisplayName,
  taskStatusLabel,
} from "../features/crawler/lib/task";
import { formatDateTime, shortTaskId } from "../lib/utils";

interface DetailItemProps {
  label: string;
  value: string;
}

function DetailItem({ label, value }: DetailItemProps) {
  return (
    <div className="rounded-xl border border-line bg-paper/65 px-4 py-3">
      <p className="text-[10px] font-bold uppercase tracking-[0.13em] text-muted">
        {label}
      </p>
      <p className="mt-1.5 break-words text-sm font-semibold text-ink">{value}</p>
    </div>
  );
}

export function TaskDetailPage() {
  const { taskId = "" } = useParams();
  const taskQuery = useCrawlerTaskQuery(taskId);
  const capabilitiesQuery = useCrawlerCapabilitiesQuery();
  const task = taskQuery.data;

  if (taskQuery.isPending) {
    return (
      <div className="space-y-5" aria-label="正在加载任务详情">
        <div className="h-28 animate-pulse rounded-2xl bg-white" />
        <div className="grid gap-5 lg:grid-cols-2">
          <div className="h-72 animate-pulse rounded-2xl bg-white" />
          <div className="h-72 animate-pulse rounded-2xl bg-white" />
        </div>
        <div className="h-80 animate-pulse rounded-2xl bg-white" />
      </div>
    );
  }

  if (taskQuery.isError || !task) {
    return (
      <div className="space-y-5">
        <Button asChild variant="ghost" size="sm">
          <Link to="/crawler/tasks">
            <ArrowLeft className="size-4" />
            返回采集中心
          </Link>
        </Button>
        <ErrorState
          title="无法打开任务"
          error={taskQuery.error}
          onRetry={() => void taskQuery.refetch()}
        />
      </div>
    );
  }

  const active = isActiveTask(task);
  const platformName = platformDisplayName(
    task.platform,
    capabilitiesQuery.data?.platforms,
  );

  return (
    <div className="space-y-7">
      <header className="border-b border-line pb-7">
        <Button asChild variant="ghost" size="sm" className="-ml-3 mb-5">
          <Link to="/crawler/tasks">
            <ArrowLeft className="size-4" />
            返回采集中心
          </Link>
        </Button>
        <div className="flex flex-col gap-5 sm:flex-row sm:items-end sm:justify-between">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-[11px] font-bold uppercase tracking-[0.2em] text-signal-strong">
                Task {shortTaskId(task.id)}
              </p>
              <TaskStatusBadge status={task.status} />
            </div>
            <h1 className="mt-3 break-words font-display text-3xl font-semibold tracking-[-0.035em] text-ink sm:text-4xl">
              {task.keywords}
            </h1>
            <p className="mt-2 text-sm text-muted">
              {platformName} · 关键词搜索 · 二维码登录
            </p>
          </div>
          {active ? <CancelTaskDialog taskId={task.id} /> : null}
        </div>
      </header>

      {task.error_message ? (
        <div className="rounded-2xl border border-danger/20 bg-danger/5 p-5">
          <p className="text-xs font-bold uppercase tracking-[0.14em] text-danger">
            任务错误
          </p>
          <p className="mt-2 whitespace-pre-wrap break-words text-sm leading-6 text-ink">
            {task.error_message}
          </p>
        </div>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1.25fr)_minmax(320px,0.75fr)]">
        <Card>
          <CardContent>
            <div className="flex items-center gap-2">
              <CircleDot className="size-4 text-signal" />
              <h2 className="font-display text-lg font-semibold">任务信息</h2>
            </div>
            <div className="mt-5 grid gap-3 sm:grid-cols-2">
              <DetailItem label="关键词" value={task.keywords} />
              <DetailItem
                label="任务状态"
                value={taskStatusLabel(task.status)}
              />
              <DetailItem
                label="请求数量"
                value={`${task.requested_count} 条`}
              />
              <DetailItem
                label="实际数量"
                value={`${task.actual_count} 条`}
              />
              <DetailItem
                label="创建时间"
                value={formatDateTime(task.created_at)}
              />
              <DetailItem
                label="开始时间"
                value={formatDateTime(task.started_at)}
              />
              <DetailItem
                label="结束时间"
                value={formatDateTime(task.finished_at)}
              />
              <DetailItem
                label="取消请求"
                value={task.cancel_requested ? "已提交" : "未提交"}
              />
            </div>
            <div className="mt-5 flex flex-wrap gap-4 border-t border-line pt-4 text-xs text-muted">
              <span className="flex items-center gap-1.5">
                <Search className="size-3.5" />
                搜索采集
              </span>
              <span className="flex items-center gap-1.5">
                <Hash className="size-3.5" />
                单任务串行
              </span>
              <span className="flex items-center gap-1.5">
                {task.finished_at ? (
                  <CheckCircle2 className="size-3.5" />
                ) : (
                  <CalendarClock className="size-3.5" />
                )}
                {task.finished_at ? "任务已结束" : "状态持续同步"}
              </span>
            </div>
          </CardContent>
        </Card>
        <QrcodePanel task={task} platformName={platformName} />
      </section>

      <LogViewer taskId={task.id} active={active} />
      <ResultBrowser taskId={task.id} active={active} />
    </div>
  );
}
