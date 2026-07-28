import { ArrowUpRight, Clock3, Inbox } from "lucide-react";
import { Link } from "react-router";

import type { CrawlerTask } from "../../../api/crawler";
import { Button } from "../../../components/ui/button";
import { cn, formatDateTime, shortTaskId } from "../../../lib/utils";
import { useCrawlerCapabilitiesQuery } from "../hooks/use-crawler-queries";
import {
  platformDisplayName,
  platformIconLabel,
  taskPrimaryLabel,
  TASK_MODE_LABELS,
} from "../lib/task";
import { TaskStatusBadge } from "./task-status-badge";

interface TaskTableProps {
  tasks: CrawlerTask[];
  compact?: boolean;
}

export function TaskTable({ tasks, compact = false }: TaskTableProps) {
  const capabilitiesQuery = useCrawlerCapabilitiesQuery();
  const capabilities = capabilitiesQuery.data?.platforms;

  if (tasks.length === 0) {
    return (
      <div className="grid min-h-52 place-items-center px-5 py-10 text-center">
        <div>
          <div className="mx-auto grid size-11 place-items-center rounded-xl bg-paper text-muted">
            <Inbox className="size-5" />
          </div>
          <p className="mt-3 text-sm font-semibold text-ink">暂无采集任务</p>
          <p className="mt-1 text-xs text-muted">
            创建首个采集任务后会显示在这里。
          </p>
        </div>
      </div>
    );
  }

  return (
    <>
      <div className="divide-y divide-line sm:hidden">
        {tasks.map((task) => (
          <Link
            key={task.id}
            to={`/crawler/tasks/${encodeURIComponent(task.id)}`}
            className="block bg-white p-4 transition-colors hover:bg-paper"
          >
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">
                  {taskPrimaryLabel(task)}
                </p>
                <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted/75">
                  ID {shortTaskId(task.id)}
                </p>
              </div>
              <TaskStatusBadge status={task.status} />
            </div>
            <div className="mt-4 grid grid-cols-3 gap-2 text-xs">
              <div>
                <p className="text-[10px] text-muted">平台</p>
                <p className="mt-1 font-medium text-ink">
                  {platformDisplayName(task.platform, capabilities)}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted">模式</p>
                <p className="mt-1 font-medium text-ink">
                  {TASK_MODE_LABELS[task.mode]}
                </p>
              </div>
              <div>
                <p className="text-[10px] text-muted">数量</p>
                <p className="mt-1 font-semibold text-ink tabular-nums">
                  {task.actual_count} / {task.requested_count}
                </p>
              </div>
            </div>
          </Link>
        ))}
      </div>
      <div className="hidden overflow-x-auto sm:block">
        <table
          className={cn(
            "w-full border-collapse text-left",
            compact ? "min-w-[700px]" : "min-w-[880px]",
          )}
        >
          <thead>
            <tr className="border-b border-line bg-paper/75 text-[11px] font-bold uppercase tracking-[0.12em] text-muted">
              <th className="px-5 py-3">任务 / 目标</th>
              <th className={cn("px-4 py-3", compact && "hidden")}>平台</th>
              <th className="px-4 py-3">模式</th>
              <th className="px-4 py-3">状态</th>
              <th className="px-4 py-3">数量</th>
              <th className="px-4 py-3">创建时间</th>
              <th className="px-5 py-3 text-right">操作</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-line">
            {tasks.map((task) => (
              <tr
                key={task.id}
                className="group bg-white transition-colors hover:bg-paper/65"
              >
                <td className="px-5 py-4">
                  <Link
                    to={`/crawler/tasks/${encodeURIComponent(task.id)}`}
                    className="block max-w-[300px]"
                  >
                    <p className="truncate text-sm font-semibold text-ink group-hover:text-signal-strong">
                      {taskPrimaryLabel(task)}
                    </p>
                    <p className="mt-1 font-mono text-[10px] uppercase tracking-wider text-muted/75">
                      ID {shortTaskId(task.id)}
                    </p>
                  </Link>
                </td>
                <td className={cn("px-4 py-4", compact && "hidden")}>
                  <span className="inline-flex items-center gap-2 text-sm text-ink">
                    <span className="grid size-6 place-items-center rounded-md bg-signal/10 text-[10px] font-bold uppercase text-signal-strong">
                      {platformIconLabel(task.platform, capabilities)}
                    </span>
                    {platformDisplayName(task.platform, capabilities)}
                  </span>
                </td>
                <td className="px-4 py-4 text-xs font-medium text-ink">
                  {TASK_MODE_LABELS[task.mode]}
                </td>
                <td className="px-4 py-4">
                  <TaskStatusBadge status={task.status} />
                </td>
                <td className="px-4 py-4 text-sm tabular-nums">
                  <span className="font-semibold text-ink">
                    {task.actual_count}
                  </span>
                  <span className="text-muted"> / {task.requested_count}</span>
                </td>
                <td className="px-4 py-4">
                  <span className="flex items-center gap-2 text-xs text-muted">
                    <Clock3 className="size-3.5" />
                    {formatDateTime(task.created_at)}
                  </span>
                </td>
                <td className="px-5 py-4 text-right">
                  <Button asChild variant="ghost" size="sm">
                    <Link
                      to={`/crawler/tasks/${encodeURIComponent(task.id)}`}
                      aria-label={`查看任务 ${taskPrimaryLabel(task)}`}
                    >
                      {compact ? "打开" : "查看详情"}
                      <ArrowUpRight className="size-3.5" />
                    </Link>
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </>
  );
}
