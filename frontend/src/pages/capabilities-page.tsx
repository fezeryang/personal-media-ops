import { CheckCircle2, CircleSlash2 } from "lucide-react";

import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Card } from "../components/ui/card";
import { useCrawlerCapabilitiesQuery } from "../features/crawler/hooks/use-crawler-queries";
import {
  modeCapabilityStatusLabel,
  TASK_MODE_LABELS,
} from "../features/crawler/lib/task";

export function CapabilitiesPage() {
  const query = useCrawlerCapabilitiesQuery();

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Platform × content mode"
        title="能力矩阵"
        description="每个平台的搜索、详情、创作者、一级评论和二级评论独立记录真实状态。代码就绪不等于生产验证。"
      />
      {query.isError ? (
        <ErrorState
          title="能力矩阵加载失败"
          error={query.error}
          onRetry={() => void query.refetch()}
        />
      ) : (
        <Card className="overflow-x-auto">
          <table className="min-w-[920px] w-full border-collapse text-left">
            <thead>
              <tr className="border-b border-line bg-paper text-xs text-muted">
                <th className="px-5 py-4">平台</th>
                {Object.entries(TASK_MODE_LABELS).map(([mode, label]) => (
                  <th key={mode} className="px-4 py-4">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="divide-y divide-line">
              {(query.data?.platforms ?? []).map((platform) => (
                <tr key={platform.platform} className="align-top">
                  <th className="px-5 py-4 text-sm font-semibold">
                    {platform.display_name}
                  </th>
                  {platform.modes.map((mode) => (
                    <td key={mode.mode} className="px-4 py-4">
                      <span className="flex items-start gap-2 text-xs font-medium">
                        {mode.enabled ? (
                          <CheckCircle2 className="mt-0.5 size-3.5 shrink-0 text-success" />
                        ) : (
                          <CircleSlash2 className="mt-0.5 size-3.5 shrink-0 text-muted" />
                        )}
                        <span>
                          {modeCapabilityStatusLabel(mode)}
                          {mode.reason ? (
                            <span className="mt-1 block max-w-40 font-normal leading-5 text-muted">
                              {mode.reason}
                            </span>
                          ) : null}
                        </span>
                      </span>
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </Card>
      )}
    </div>
  );
}
