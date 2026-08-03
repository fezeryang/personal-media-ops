import { Database, Filter, Search } from "lucide-react";
import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import { useCrawlerCapabilitiesQuery } from "../features/crawler/hooks/use-crawler-queries";
import { ContentCard } from "../features/library/components/content-card";
import {
  useLibraryContentsQuery,
  useLibraryStatsQuery,
} from "../features/library/hooks/use-library-queries";
import { createTag, listTags, setFavorite } from "../api/organization";
import { Button } from "../components/ui/button";

export function LibraryPage() {
  const [platform, setPlatform] = useState("");
  const [keyword, setKeyword] = useState("");
  const [hasComments, setHasComments] = useState("");
  const [tagId, setTagId] = useState("");
  const [favoriteOnly, setFavoriteOnly] = useState(false);
  const [newTag, setNewTag] = useState("");
  const queryClient = useQueryClient();
  const capabilities = useCrawlerCapabilitiesQuery();
  const stats = useLibraryStatsQuery();
  const contents = useLibraryContentsQuery({
    platform: platform || undefined,
    keyword: keyword.trim() || undefined,
    has_comments:
      hasComments === "" ? undefined : hasComments === "with_comments",
    tag_id: tagId || undefined,
    is_favorite: favoriteOnly || undefined,
    limit: 50,
  });
  const tags = useQuery({
    queryKey: ["library", "tags"],
    queryFn: ({ signal }) => listTags(signal),
  });
  const favorite = useMutation({
    mutationFn: ({
      contentId,
      value,
    }: {
      contentId: string;
      value: boolean;
    }) => setFavorite(contentId, value),
    onSuccess: async () => {
      await queryClient.invalidateQueries({
        queryKey: ["library", "contents"],
      });
    },
  });
  const addNewTag = useMutation({
    mutationFn: () => createTag(newTag.trim()),
    onSuccess: async () => {
      setNewTag("");
      await queryClient.invalidateQueries({
        queryKey: ["library", "tags"],
      });
    },
  });

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Memory · Evidence"
        title="记忆与证据"
        description="跨任务沉淀标准化内容、创作者、评论和来源关系。页面只展示安全文本，不直接渲染原始载荷；研究空间和候选发现会从这里引用真实证据。"
      />

      <section className="grid gap-4 sm:grid-cols-3">
        {[
          ["内容", stats.data?.contents],
          ["创作者", stats.data?.creators],
          ["评论", stats.data?.comments],
        ].map(([label, value]) => (
          <Card key={String(label)} className="p-5">
            <p className="text-xs font-semibold text-muted">{label}</p>
            <p className="mt-2 font-display text-3xl font-semibold tabular-nums">
              {typeof value === "number" ? value.toLocaleString("zh-CN") : "—"}
            </p>
          </Card>
        ))}
      </section>

      <Card className="p-4">
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-[minmax(0,1fr)_160px_160px_160px]">
          <div className="relative">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <Input
              className="pl-9"
              value={keyword}
              onChange={(event) => setKeyword(event.currentTarget.value)}
              placeholder="搜索标题、摘要或来源关键词"
              aria-label="搜索资料库"
            />
          </div>
          <div className="relative">
            <Filter className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" />
            <select
              className="h-10 w-full rounded-lg border border-line bg-white pl-9 pr-3 text-sm"
              value={platform}
              onChange={(event) => setPlatform(event.currentTarget.value)}
              aria-label="按平台筛选资料库"
            >
              <option value="">全部平台</option>
              {(capabilities.data?.platforms ?? []).map((item) => (
                <option key={item.platform} value={item.platform}>
                  {item.display_name}
                </option>
              ))}
            </select>
          </div>
          <select
            className="h-10 w-full rounded-lg border border-line bg-white px-3 text-sm"
            value={hasComments}
            onChange={(event) => setHasComments(event.currentTarget.value)}
            aria-label="按评论状态筛选"
          >
            <option value="">全部评论状态</option>
            <option value="with_comments">已有评论</option>
            <option value="without_comments">暂无评论</option>
          </select>
          <select
            className="form-select"
            value={tagId}
            onChange={(event) => setTagId(event.currentTarget.value)}
            aria-label="按标签筛选"
          >
            <option value="">全部标签</option>
            {(tags.data ?? []).map((tag) => (
              <option key={tag.id} value={tag.id}>
                #{tag.name} ({tag.content_count})
              </option>
            ))}
          </select>
          <label className="flex h-10 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm">
            <input
              type="checkbox"
              checked={favoriteOnly}
              onChange={(event) =>
                setFavoriteOnly(event.currentTarget.checked)
              }
            />
            只看收藏
          </label>
        </div>
        <div className="mt-3 flex gap-2 border-t border-line pt-3">
          <Input
            className="max-w-xs"
            value={newTag}
            onChange={(event) => setNewTag(event.currentTarget.value)}
            placeholder="创建资料标签"
            aria-label="新标签名称"
          />
          <Button
            variant="secondary"
            disabled={!newTag.trim() || addNewTag.isPending}
            onClick={() => addNewTag.mutate()}
          >
            创建标签
          </Button>
        </div>
      </Card>

      {contents.isError ? (
        <ErrorState
          title="资料库加载失败"
          error={contents.error}
          onRetry={() => void contents.refetch()}
        />
      ) : contents.isPending ? (
        <div className="space-y-4" aria-label="正在加载资料库">
          {Array.from({ length: 3 }, (_, index) => (
            <div
              key={index}
              className="h-44 animate-pulse rounded-2xl bg-white"
            />
          ))}
        </div>
      ) : contents.data.items.length === 0 ? (
        <Card className="grid min-h-60 place-items-center p-8 text-center">
          <div>
            <Database className="mx-auto size-7 text-muted" />
            <p className="mt-3 font-semibold">没有符合条件的资料</p>
            <p className="mt-1 text-sm text-muted">
              采集任务完成入库后会自动出现在这里。
            </p>
          </div>
        </Card>
      ) : (
        <div className="space-y-4">
          {contents.data.items.map((content) => (
            <ContentCard
              key={content.id}
              content={content}
              onFavoriteChange={(contentId, value) =>
                favorite.mutate({ contentId, value })
              }
            />
          ))}
          <p className="text-right text-xs text-muted">
            当前显示 {contents.data.items.length} 条
          </p>
        </div>
      )}
    </div>
  );
}
