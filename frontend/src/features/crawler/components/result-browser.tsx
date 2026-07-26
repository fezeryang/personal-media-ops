import {
  ChevronLeft,
  ChevronRight,
  Clock3,
  ExternalLink,
  Heart,
  ImageOff,
  MessageCircle,
  Play,
  Star,
  Tag,
  UserRound,
} from "lucide-react";
import { useState } from "react";

import { ErrorState } from "../../../components/error-state";
import { Button } from "../../../components/ui/button";
import { Card, CardContent, CardHeader } from "../../../components/ui/card";
import { formatDateTime } from "../../../lib/utils";
import { useCrawlerResultsQuery } from "../hooks/use-crawler-queries";
import {
  normalizeCrawlerResult,
  type NormalizedCrawlerResult,
} from "../lib/result-fields";

const PAGE_SIZE = 12;

function displayPublishTime(value: string | null): string {
  if (!value) return "未提供";
  if (/^\d{10,13}$/.test(value)) {
    const timestamp = Number(value) * (value.length === 10 ? 1_000 : 1);
    return formatDateTime(new Date(timestamp).toISOString());
  }
  return formatDateTime(value);
}

function ResultCard({
  item,
  index,
}: {
  item: NormalizedCrawlerResult;
  index: number;
}) {
  const [imageFailed, setImageFailed] = useState(false);

  return (
    <article className="grid gap-4 rounded-xl border border-line bg-white p-4 sm:grid-cols-[148px_minmax(0,1fr)]">
      <div className="aspect-video overflow-hidden rounded-lg bg-paper sm:aspect-[4/3]">
        {item.coverUrl && !imageFailed ? (
          <img
            src={item.coverUrl}
            alt=""
            loading="lazy"
            referrerPolicy="no-referrer"
            className="size-full object-cover"
            onError={() => setImageFailed(true)}
          />
        ) : (
          <div className="grid size-full place-items-center text-muted/60">
            <ImageOff className="size-6" />
          </div>
        )}
      </div>
      <div className="min-w-0">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.14em] text-muted/75">
              Result {String(index + 1).padStart(2, "0")}
            </p>
            <h3 className="mt-1 line-clamp-2 text-sm font-semibold leading-6 text-ink">
              {item.title}
            </h3>
          </div>
          {item.videoUrl ? (
            <Button asChild variant="ghost" size="icon">
              <a
                href={item.videoUrl}
                target="_blank"
                rel="noopener noreferrer"
                aria-label={`在新标签页打开：${item.title}`}
              >
                <ExternalLink className="size-4" />
              </a>
            </Button>
          ) : null}
        </div>

        <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-xs text-muted">
          <span className="flex items-center gap-1.5">
            <UserRound className="size-3.5" />
            {item.author}
          </span>
          <span className="flex items-center gap-1.5">
            <Clock3 className="size-3.5" />
            {displayPublishTime(item.publishedAt)}
          </span>
          {item.sourceKeyword ? (
            <span className="flex items-center gap-1.5">
              <Tag className="size-3.5" />
              {item.sourceKeyword}
            </span>
          ) : null}
        </div>

        <div className="mt-4 flex flex-wrap gap-2">
          {[
            { label: "播放", value: item.playCount, icon: Play },
            { label: "点赞", value: item.likeCount, icon: Heart },
            { label: "收藏", value: item.favoriteCount, icon: Star },
            { label: "评论", value: item.commentCount, icon: MessageCircle },
          ].map((metric) => (
            <span
              key={metric.label}
              className="inline-flex items-center gap-1.5 rounded-md bg-paper px-2 py-1 text-[11px] text-muted"
              title={metric.label}
            >
              <metric.icon className="size-3" />
              <span className="font-medium tabular-nums">{metric.value}</span>
            </span>
          ))}
        </div>
      </div>
    </article>
  );
}

interface ResultBrowserProps {
  taskId: string;
  active: boolean;
}

export function ResultBrowser({ taskId, active }: ResultBrowserProps) {
  const [offset, setOffset] = useState(0);
  const resultsQuery = useCrawlerResultsQuery(
    taskId,
    offset,
    PAGE_SIZE,
    active,
  );
  const results = resultsQuery.data;

  return (
    <Card className="overflow-hidden">
      <CardHeader className="flex flex-row items-center justify-between border-b border-line pb-4">
        <div>
          <h2 className="font-display text-lg font-semibold">采集结果</h2>
          <p className="mt-1 text-xs text-muted">
            后端分页读取 JSONL，每页最多 {PAGE_SIZE} 条
          </p>
        </div>
        {results ? (
          <span className="text-xs font-semibold text-muted tabular-nums">
            {results.items.length
              ? `${results.offset + 1}–${results.offset + results.items.length}`
              : "0"}{" "}
            条
          </span>
        ) : null}
      </CardHeader>
      <CardContent>
        {resultsQuery.isError ? (
          <ErrorState
            title="采集结果加载失败"
            error={resultsQuery.error}
            onRetry={() => void resultsQuery.refetch()}
          />
        ) : resultsQuery.isPending ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {Array.from({ length: 4 }, (_, index) => (
              <div
                key={index}
                className="h-44 animate-pulse rounded-xl bg-paper"
              />
            ))}
          </div>
        ) : results && results.items.length > 0 ? (
          <div className="grid gap-3 xl:grid-cols-2">
            {results.items.map((record, index) => (
              <ResultCard
                key={`${results.offset}-${index}`}
                item={normalizeCrawlerResult(record)}
                index={results.offset + index}
              />
            ))}
          </div>
        ) : (
          <div className="grid min-h-44 place-items-center text-center">
            <div>
              <p className="text-sm font-semibold text-ink">暂无采集结果</p>
              <p className="mt-1 text-xs text-muted">
                任务产生 JSONL 数据后，结果会按页显示在这里。
              </p>
            </div>
          </div>
        )}

        <div className="mt-5 flex items-center justify-between border-t border-line pt-4">
          <Button
            variant="secondary"
            size="sm"
            disabled={offset === 0 || resultsQuery.isFetching}
            onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}
          >
            <ChevronLeft className="size-4" />
            上一页
          </Button>
          <span className="text-xs text-muted tabular-nums">
            第 {Math.floor(offset / PAGE_SIZE) + 1} 页
          </span>
          <Button
            variant="secondary"
            size="sm"
            disabled={!results?.has_more || resultsQuery.isFetching}
            onClick={() => {
              if (results) setOffset(results.next_offset);
            }}
          >
            下一页
            <ChevronRight className="size-4" />
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
