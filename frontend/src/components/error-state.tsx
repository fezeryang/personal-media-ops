import { AlertTriangle, RefreshCw } from "lucide-react";

import { errorMessage } from "../lib/utils";
import { Button } from "./ui/button";

interface ErrorStateProps {
  error: unknown;
  onRetry?: () => void;
  title?: string;
}

export function ErrorState({
  error,
  onRetry,
  title = "数据加载失败",
}: ErrorStateProps) {
  return (
    <div
      className="rounded-2xl border border-danger/20 bg-danger/5 p-5"
      role="alert"
    >
      <div className="flex items-start gap-3">
        <AlertTriangle className="mt-0.5 size-5 shrink-0 text-danger" />
        <div className="min-w-0 flex-1">
          <p className="font-semibold text-ink">{title}</p>
          <p className="mt-1 text-sm text-muted">{errorMessage(error)}</p>
        </div>
        {onRetry ? (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <RefreshCw className="size-3.5" />
            重试
          </Button>
        ) : null}
      </div>
    </div>
  );
}
