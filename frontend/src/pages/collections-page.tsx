import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { FolderKanban, Plus, Trash2 } from "lucide-react";
import { type FormEvent, useState } from "react";
import { Link } from "react-router";

import { listLibraryContents } from "../api/library";
import {
  addCollectionItem,
  createCollection,
  getCollection,
  listCollections,
  removeCollectionItem,
} from "../api/organization";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";

export function CollectionsPage() {
  const queryClient = useQueryClient();
  const [selectedId, setSelectedId] = useState("");
  const [creating, setCreating] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [contentId, setContentId] = useState("");
  const collections = useQuery({
    queryKey: ["collections"],
    queryFn: ({ signal }) => listCollections(signal),
  });
  const effectiveSelectedId = selectedId || collections.data?.[0]?.id || "";
  const detail = useQuery({
    queryKey: ["collections", effectiveSelectedId],
    queryFn: ({ signal }) => getCollection(effectiveSelectedId, signal),
    enabled: Boolean(effectiveSelectedId),
  });
  const contents = useQuery({
    queryKey: ["library", "collection-options"],
    queryFn: ({ signal }) => listLibraryContents({ limit: 100 }, signal),
  });
  const invalidate = async () => {
    await queryClient.invalidateQueries({ queryKey: ["collections"] });
  };
  const create = useMutation({
    mutationFn: () =>
      createCollection({
        name: name.trim(),
        description: description.trim() || null,
      }),
    onSuccess: async (created) => {
      setSelectedId(created.id);
      setName("");
      setDescription("");
      setCreating(false);
      await invalidate();
    },
  });
  const add = useMutation({
    mutationFn: () =>
      addCollectionItem(
        effectiveSelectedId,
        contentId,
        detail.data?.items.length ?? 0,
      ),
    onSuccess: async () => {
      setContentId("");
      await invalidate();
    },
  });
  const remove = useMutation({
    mutationFn: (itemContentId: string) =>
      removeCollectionItem(effectiveSelectedId, itemContentId),
    onSuccess: invalidate,
  });
  const present = new Set(
    (detail.data?.items ?? []).map((item) => item.content.id),
  );

  function submitCreate(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    create.mutate();
  }

  return (
    <div className="space-y-8">
      <PageHeader
        eyebrow="Curated research"
        title="专题集合"
        description="把真实内容组织成有顺序的研究专题。收藏使用资料库唯一字段，不与专题集合混为一套状态。"
        action={
          <Button onClick={() => setCreating((value) => !value)}>
            <Plus className="size-4" /> 新建专题
          </Button>
        }
      />

      {creating ? (
        <Card>
          <CardContent>
            <form
              onSubmit={submitCreate}
              className="grid gap-4 sm:grid-cols-2"
            >
              <label className="text-sm font-semibold">
                名称
                <Input
                  className="mt-2"
                  value={name}
                  onChange={(event) => setName(event.currentTarget.value)}
                  required
                />
              </label>
              <label className="text-sm font-semibold">
                描述
                <Input
                  className="mt-2"
                  value={description}
                  onChange={(event) =>
                    setDescription(event.currentTarget.value)
                  }
                />
              </label>
              <div className="flex justify-end gap-2 sm:col-span-2">
                <Button
                  type="button"
                  variant="ghost"
                  onClick={() => setCreating(false)}
                >
                  取消
                </Button>
                <Button disabled={create.isPending || !name.trim()}>
                  创建
                </Button>
              </div>
            </form>
          </CardContent>
        </Card>
      ) : null}

      <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
        <Card className="h-fit">
          <CardHeader>
            <p className="section-kicker">Collections</p>
            <h2 className="mt-1 font-display text-xl font-semibold">
              我的专题
            </h2>
          </CardHeader>
          <CardContent className="space-y-2 pt-4">
            {(collections.data ?? []).map((collection) => (
              <button
                key={collection.id}
                type="button"
                onClick={() => setSelectedId(collection.id)}
                className={`w-full rounded-xl border px-4 py-3 text-left transition ${
                  effectiveSelectedId === collection.id
                    ? "border-signal/30 bg-signal/7"
                    : "border-transparent hover:bg-paper"
                }`}
              >
                <span className="block text-sm font-semibold">
                  {collection.name}
                </span>
                <span className="mt-1 block text-xs text-muted">
                  {collection.content_count} 条内容
                </span>
              </button>
            ))}
          </CardContent>
        </Card>

        {detail.data ? (
          <Card>
            <CardHeader className="border-b border-line pb-5">
              <div className="flex items-start justify-between">
                <div>
                  <p className="section-kicker">Research dossier</p>
                  <h2 className="mt-1 font-display text-2xl font-semibold">
                    {detail.data.name}
                  </h2>
                  <p className="mt-2 text-sm text-muted">
                    {detail.data.description ?? "未填写专题描述"}
                  </p>
                </div>
                <span className="font-mono text-sm text-muted">
                  {detail.data.items.length}
                </span>
              </div>
              <div className="mt-5 flex flex-col gap-2 sm:flex-row">
                <select
                  className="form-select flex-1"
                  aria-label="选择要加入专题的内容"
                  value={contentId}
                  onChange={(event) => setContentId(event.currentTarget.value)}
                >
                  <option value="">选择资料库内容</option>
                  {(contents.data?.items ?? [])
                    .filter((content) => !present.has(content.id))
                    .map((content) => (
                      <option key={content.id} value={content.id}>
                        {content.title ?? content.source_content_id}
                      </option>
                    ))}
                </select>
                <Button
                  variant="secondary"
                  disabled={!contentId || add.isPending}
                  onClick={() => add.mutate()}
                >
                  加入专题
                </Button>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              {detail.data.items.map((item, index) => (
                <article
                  key={item.content.id}
                  className="flex gap-4 rounded-xl border border-line bg-paper/50 p-4"
                >
                  <span className="font-mono text-xs text-muted">
                    {String(index + 1).padStart(2, "0")}
                  </span>
                  <div className="min-w-0 flex-1">
                    <Link
                      to={`/library/contents/${encodeURIComponent(item.content.id)}`}
                      className="line-clamp-2 font-semibold hover:text-signal-strong"
                    >
                      {item.content.title ?? "无标题内容"}
                    </Link>
                    <p className="mt-1 text-xs text-muted">
                      {item.content.platform} ·{" "}
                      {item.content.author_name ?? "未知作者"}
                    </p>
                  </div>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="从专题移除"
                    onClick={() => remove.mutate(item.content.id)}
                  >
                    <Trash2 className="size-4 text-danger" />
                  </Button>
                </article>
              ))}
              {!detail.data.items.length ? (
                <p className="py-10 text-center text-sm text-muted">
                  这个专题还没有内容。
                </p>
              ) : null}
            </CardContent>
          </Card>
        ) : (
          <Card className="grid min-h-72 place-items-center p-8 text-center">
            <div>
              <FolderKanban className="mx-auto size-8 text-muted" />
              <p className="mt-3 font-semibold">选择或创建一个专题</p>
            </div>
          </Card>
        )}
      </section>
      {collections.isError ? <ErrorState error={collections.error} /> : null}
    </div>
  );
}
