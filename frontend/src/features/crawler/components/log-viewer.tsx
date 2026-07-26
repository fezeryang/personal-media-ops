import {
  ArrowDownToLine,
  CirclePause,
  CirclePlay,
  RefreshCw,
  Terminal,
} from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { ErrorState } from "../../../components/error-state";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../../components/ui/card";
import { useCrawlerTaskLogsQuery } from "../hooks/use-crawler-queries";

interface LogViewerProps {
  taskId: string;
  active: boolean;
}

export function LogViewer({ taskId, active }: LogViewerProps) {
  const [autoRefresh, setAutoRefresh] = useState(true);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const logsQuery = useCrawlerTaskLogsQuery(taskId, active, autoRefresh);
  const logs = logsQuery.data ?? "";
  const lineCount = logs ? logs.split("\n").length : 0;

  useEffect(() => {
    if (!autoScroll || !scrollRef.current) return;
    scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
  }, [autoScroll, logs]);

  const scrollToLatest = () => {
    const container = scrollRef.current;
    if (container) container.scrollTop = container.scrollHeight;
  };

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-col gap-3 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <Terminal className="size-4 text-signal" />
            <h2 className="font-display text-lg font-semibold">运行日志</h2>
          </div>
          <p className="mt-1 text-xs text-muted">
            仅加载最新 300 行 · 当前 {lineCount} 行
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setAutoRefresh((current) => !current)}
            disabled={!active}
          >
            {autoRefresh ? (
              <CirclePause className="size-3.5" />
            ) : (
              <CirclePlay className="size-3.5" />
            )}
            {active
              ? autoRefresh
                ? "暂停刷新"
                : "继续刷新"
              : "任务已结束"}
          </Button>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => setAutoScroll((current) => !current)}
          >
            <ArrowDownToLine className="size-3.5" />
            {autoScroll ? "暂停自动滚动" : "恢复自动滚动"}
          </Button>
          <Button
            variant="secondary"
            size="icon"
            aria-label="手动刷新日志"
            onClick={() => void logsQuery.refetch()}
            disabled={logsQuery.isFetching}
          >
            <RefreshCw
              className={`size-3.5 ${logsQuery.isFetching ? "animate-spin" : ""}`}
            />
          </Button>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        {logsQuery.isError ? (
          <div className="p-5">
            <ErrorState
              error={logsQuery.error}
              onRetry={() => void logsQuery.refetch()}
            />
          </div>
        ) : (
          <div className="relative">
            <div
              ref={scrollRef}
              className="h-[360px] overflow-auto bg-[#101722] p-4 sm:p-5"
              onScroll={(event) => {
                const target = event.currentTarget;
                const distance =
                  target.scrollHeight - target.scrollTop - target.clientHeight;
                if (distance > 80 && autoScroll) setAutoScroll(false);
              }}
            >
              <pre className="whitespace-pre-wrap break-words font-mono text-[12px] leading-6 text-slate-300">
                {logs ||
                  (logsQuery.isPending
                    ? "正在连接任务日志…"
                    : "日志尚未生成。Worker 领取任务后会在这里显示运行输出。")}
              </pre>
            </div>
            {!autoScroll && logs ? (
              <Button
                size="sm"
                className="absolute bottom-4 right-4 shadow-lg"
                onClick={() => {
                  setAutoScroll(true);
                  scrollToLatest();
                }}
              >
                <ArrowDownToLine className="size-3.5" />
                回到最新
              </Button>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
