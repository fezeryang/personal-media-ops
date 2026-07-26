import {
  Activity,
  AlertTriangle,
  CheckCircle2,
  Clock3,
  ListTodo,
  QrCode,
  RadioTower,
} from "lucide-react";
import { Link } from "react-router";

import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { TaskTable } from "../features/crawler/components/task-table";
import {
  useCrawlerTasksQuery,
  useHealthQuery,
} from "../features/crawler/hooks/use-crawler-queries";
import {
  buildTaskMetrics,
  getEngineState,
} from "../features/crawler/lib/task";

const metricDefinitions = [
  { key: "total", label: "任务总数", icon: ListTodo, accent: "text-ink" },
  { key: "running", label: "正在运行", icon: Activity, accent: "text-signal" },
  {
    key: "waitingLogin",
    label: "等待登录",
    icon: QrCode,
    accent: "text-warning",
  },
  {
    key: "succeeded",
    label: "成功任务",
    icon: CheckCircle2,
    accent: "text-success",
  },
  {
    key: "failed",
    label: "失败任务",
    icon: AlertTriangle,
    accent: "text-danger",
  },
] as const;

const engineTone = {
  neutral: "neutral",
  info: "info",
  warning: "warning",
  danger: "danger",
} as const;

export function OverviewPage() {
  const tasksQuery = useCrawlerTasksQuery();
  const healthQuery = useHealthQuery();
  const tasks = tasksQuery.data ?? [];
  const metrics = buildTaskMetrics(tasks);
  const engine = getEngineState(tasks, healthQuery.data?.status === "ok");

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Operations overview"
        title="总览"
        description="基于真实采集任务状态汇总当前工作负载，不填充预测或模拟数据。"
        action={
          <Button asChild variant="secondary">
            <Link to="/crawler/tasks">
              <RadioTower className="size-4" />
              进入采集中心
            </Link>
          </Button>
        }
      />

      {tasksQuery.isError ? (
        <ErrorState
          error={tasksQuery.error}
          onRetry={() => void tasksQuery.refetch()}
        />
      ) : null}

      <section
        className="grid grid-cols-2 gap-3 md:grid-cols-3 xl:grid-cols-5"
        aria-label="任务统计"
      >
        {metricDefinitions.map((metric) => (
          <Card key={metric.key} className="relative overflow-hidden">
            <CardContent className="p-4 sm:p-5">
              <div className="flex items-center justify-between">
                <p className="text-xs font-semibold text-muted">
                  {metric.label}
                </p>
                <metric.icon className={`size-4 ${metric.accent}`} />
              </div>
              <p className="mt-5 font-display text-3xl font-semibold tracking-tight tabular-nums">
                {tasksQuery.isPending ? "—" : metrics[metric.key]}
              </p>
            </CardContent>
          </Card>
        ))}
      </section>

      <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_320px]">
        <Card className="min-w-0 overflow-hidden">
          <CardHeader className="flex flex-row items-center justify-between pb-4">
            <div>
              <h2 className="font-display text-lg font-semibold">最近任务</h2>
              <p className="mt-1 text-xs text-muted">按创建时间倒序</p>
            </div>
            <Button asChild variant="ghost" size="sm">
              <Link to="/crawler/tasks">查看全部</Link>
            </Button>
          </CardHeader>
          <TaskTable tasks={tasks.slice(0, 5)} compact />
        </Card>

        <Card className="overflow-hidden">
          <CardHeader>
            <p className="text-[11px] font-bold uppercase tracking-[0.18em] text-muted">
              Crawler engine
            </p>
            <div className="mt-4 flex items-start justify-between gap-3">
              <div className="grid size-11 place-items-center rounded-xl bg-sidebar text-white">
                <RadioTower className="size-5" />
              </div>
              <Badge variant={engineTone[engine.tone]}>{engine.label}</Badge>
            </div>
          </CardHeader>
          <CardContent className="pt-4">
            <h2 className="font-display text-xl font-semibold">B 站搜索引擎</h2>
            <p className="mt-2 text-sm leading-6 text-muted">{engine.detail}</p>
            <div className="mt-6 space-y-3 border-t border-line pt-5">
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">并发策略</span>
                <span className="font-semibold text-ink">单任务串行</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="text-muted">已验证范围</span>
                <span className="font-semibold text-ink">B 站关键词搜索</span>
              </div>
              <div className="flex items-center justify-between text-xs">
                <span className="flex items-center gap-1.5 text-muted">
                  <Clock3 className="size-3.5" />
                  状态来源
                </span>
                <span className="font-semibold text-ink">实时任务 API</span>
              </div>
            </div>
          </CardContent>
        </Card>
      </section>
    </div>
  );
}
