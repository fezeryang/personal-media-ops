import type { CrawlerTaskStatus } from "../../../api/crawler";
import { Badge } from "../../../components/ui/badge";
import { cn } from "../../../lib/utils";
import { taskStatusLabel } from "../lib/task";

type BadgeTone = "neutral" | "info" | "success" | "warning" | "danger";

const statusTone: Record<CrawlerTaskStatus, BadgeTone> = {
  pending: "neutral",
  running: "info",
  waiting_login: "warning",
  succeeded: "success",
  failed: "danger",
  cancelled: "neutral",
};

export function TaskStatusBadge({
  status,
}: {
  status: CrawlerTaskStatus;
}) {
  return (
    <Badge variant={statusTone[status]}>
      <span
        className={cn(
          "size-1.5 rounded-full bg-current",
          status === "running" && "animate-pulse",
        )}
      />
      {taskStatusLabel(status)}
    </Badge>
  );
}
