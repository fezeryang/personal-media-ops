import { FolderKanban, Plus, Sparkles } from "lucide-react";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import type { ResearchSpaceDetail, ResearchSpaceItemType } from "../api/research";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";
import {
  useAddResearchSpaceItemMutation,
  useCreateResearchSpaceMutation,
  useResearchSpaceQuery,
  useResearchSpacesQuery,
} from "../features/research/hooks/use-discovery-queries";
import { errorMessage } from "../lib/utils";

const itemTypeLabels: Record<ResearchSpaceItemType, string> = {
  research_task: "研究任务",
  discovery_candidate: "发现候选",
  evidence: "证据",
  entity: "实体",
  event: "事件",
  finding: "结论",
  unresolved_question: "未解问题",
  memory: "长期记忆",
  opportunity: "机会",
  validation_plan: "验证计划",
  action: "行动",
  outcome: "行动结果",
};

const itemTypes = Object.keys(itemTypeLabels) as ResearchSpaceItemType[];

function itemTitle(item: { item: Record<string, unknown>; item_id: string }): string {
  for (const key of ["title", "name", "statement", "objective", "summary"]) {
    const value = item.item[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return item.item_id;
}

export function ResearchSpacesPage() {
  const navigate = useNavigate();
  const { spaceId } = useParams<{ spaceId: string }>();
  const [selectedId, setSelectedId] = useState("");
  const spaces = useResearchSpacesQuery();
  const effectiveId = spaceId ?? selectedId ?? spaces.data?.[0]?.id ?? "";
  const detail = useResearchSpaceQuery(effectiveId);
  const create = useCreateResearchSpaceMutation();
  const addItem = useAddResearchSpaceItemMutation();
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [itemType, setItemType] = useState<ResearchSpaceItemType>("discovery_candidate");
  const [itemId, setItemId] = useState("");
  const [itemNote, setItemNote] = useState("");

  function submitCreate() {
    const trimmedName = name.trim();
    if (!trimmedName) return;
    create.mutate(
      { name: trimmedName, description: description.trim() || undefined },
      {
        onSuccess: (space) => {
          setName("");
          setDescription("");
          setShowCreate(false);
          setSelectedId(space.id);
          void navigate(`/spaces/${encodeURIComponent(space.id)}`);
        },
      },
    );
  }

  function selectSpace(id: string) {
    setSelectedId(id);
    void navigate(`/spaces/${encodeURIComponent(id)}`);
  }

  return (
    <div className="space-y-7">
      <PageHeader
        eyebrow="Long-term research spaces · 8D-3"
        title="研究空间"
        description="把研究任务、发现候选、证据、结论和长期记忆放在同一个可持续推进的上下文里。空间是可积累的研究对象，不是旧版专题集合的别名。"
        action={<Button onClick={() => setShowCreate((value) => !value)}><Plus className="size-4" />新建研究空间</Button>}
      />

      {showCreate ? (
        <Card>
          <CardHeader><p className="section-kicker">Create space</p><h2 className="mt-1 font-display text-xl font-semibold">建立一个长期问题上下文</h2></CardHeader>
          <CardContent className="space-y-4">
            <label className="block text-sm font-semibold">空间名称<Input className="mt-2" value={name} onChange={(event) => setName(event.currentTarget.value)} placeholder="例如：个人 AI 工作台机会" maxLength={200} /></label>
            <label className="block text-sm font-semibold">描述（可选）<textarea className="mt-2 min-h-20 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15" value={description} onChange={(event) => setDescription(event.currentTarget.value)} maxLength={2_000} placeholder="这个空间持续追踪什么问题？" /></label>
            {create.error ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setShowCreate(false)}>取消</Button><Button disabled={create.isPending || name.trim().length === 0} onClick={submitCreate}>{create.isPending ? "创建中…" : "创建空间"}</Button></div>
          </CardContent>
        </Card>
      ) : null}

      {spaces.isError ? <ErrorState title="研究空间加载失败" error={spaces.error} onRetry={() => void spaces.refetch()} /> : (
        <section className="grid gap-5 xl:grid-cols-[300px_minmax(0,1fr)]">
          <Card className="h-fit overflow-hidden">
            <CardHeader className="border-b border-line pb-4"><p className="section-kicker">Persistent context</p><h2 className="mt-1 font-display text-xl font-semibold">空间列表</h2></CardHeader>
            <CardContent className="space-y-2 p-3">
              {spaces.isPending ? Array.from({ length: 3 }, (_, index) => <div key={index} className="h-20 animate-pulse rounded-xl bg-paper" />) : null}
              {!spaces.isPending && spaces.data?.length === 0 ? <p className="rounded-xl bg-paper p-5 text-sm text-muted">还没有研究空间。先建立一个，再把发现和证据放进去。</p> : null}
              {spaces.data?.map((space) => <button key={space.id} type="button" onClick={() => selectSpace(space.id)} className={`w-full rounded-xl border p-3 text-left transition ${effectiveId === space.id ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}><div className="flex items-start justify-between gap-2"><span className="line-clamp-2 text-sm font-semibold">{space.name}</span><Badge variant={space.status === "active" ? "success" : "neutral"}>{space.status === "active" ? "活跃" : "已归档"}</Badge></div><p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">{space.description ?? "没有描述"}</p><p className="mt-2 text-xs text-muted">{space.item_count} 项 · 更新于 {new Date(space.updated_at).toLocaleString("zh-CN")}</p></button>)}
            </CardContent>
          </Card>

          {detail.isError ? <ErrorState title="研究空间详情加载失败" error={detail.error} onRetry={() => void detail.refetch()} /> : detail.data ? (
            <SpaceDetail
              space={detail.data}
              itemType={itemType}
              itemId={itemId}
              itemNote={itemNote}
              pending={addItem.isPending}
              error={addItem.error}
              onItemTypeChange={setItemType}
              onItemIdChange={setItemId}
              onItemNoteChange={setItemNote}
              onAdd={() => {
                if (!itemId.trim()) return;
                addItem.mutate({ spaceId: detail.data.id, itemType, itemId: itemId.trim(), note: itemNote.trim() || undefined }, { onSuccess: () => { setItemId(""); setItemNote(""); } });
              }}
            />
          ) : (
            <Card className="grid min-h-80 place-items-center"><div className="text-center"><FolderKanban className="mx-auto size-8 text-muted" /><p className="mt-3 text-sm text-muted">选择一个空间查看它积累的研究材料。</p></div></Card>
          )}
        </section>
      )}
    </div>
  );
}

function SpaceDetail({
  space,
  itemType,
  itemId,
  itemNote,
  pending,
  error,
  onItemTypeChange,
  onItemIdChange,
  onItemNoteChange,
  onAdd,
}: {
  space: ResearchSpaceDetail;
  itemType: ResearchSpaceItemType;
  itemId: string;
  itemNote: string;
  pending: boolean;
  error: unknown;
  onItemTypeChange: (value: ResearchSpaceItemType) => void;
  onItemIdChange: (value: string) => void;
  onItemNoteChange: (value: string) => void;
  onAdd: () => void;
}) {
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="border-b border-line pb-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><p className="section-kicker">Research space</p><h2 className="mt-1 font-display text-2xl font-semibold">{space.name}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{space.description ?? "这个空间还没有描述。"}</p></div><Badge variant={space.status === "active" ? "success" : "neutral"}>{space.status === "active" ? "活跃空间" : "已归档"}</Badge></div></CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 p-5 sm:grid-cols-4"><Metric label="材料总数" value={String(space.items.length)} /><Metric label="研究任务" value={String(space.items.filter((item) => item.item_type === "research_task").length)} /><Metric label="发现候选" value={String(space.items.filter((item) => item.item_type === "discovery_candidate").length)} /><Metric label="证据 / 记忆" value={String(space.items.filter((item) => ["evidence", "memory", "finding"].includes(item.item_type)).length)} /></CardContent>
      </Card>

      <Card>
        <CardHeader><p className="section-kicker">Add typed item</p><h3 className="mt-1 font-display text-xl font-semibold">加入已有研究材料</h3><p className="mt-2 text-sm text-muted">输入真实对象 ID，类型会决定后端如何校验和展示它。</p></CardHeader>
        <CardContent className="space-y-3">
          <div className="grid gap-3 md:grid-cols-[180px_minmax(0,1fr)]"><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={itemType} onChange={(event) => onItemTypeChange(event.currentTarget.value as ResearchSpaceItemType)} aria-label="材料类型">{itemTypes.map((type) => <option key={type} value={type}>{itemTypeLabels[type]}</option>)}</select><Input value={itemId} onChange={(event) => onItemIdChange(event.currentTarget.value)} placeholder="对象 ID" aria-label="对象 ID" /></div>
          <Input value={itemNote} onChange={(event) => onItemNoteChange(event.currentTarget.value)} placeholder="备注（可选）" aria-label="材料备注" />
          {error ? <p className="text-sm text-danger">{errorMessage(error)}</p> : null}
          <Button disabled={pending || !itemId.trim()} onClick={onAdd}>{pending ? "加入中…" : "加入空间"}</Button>
        </CardContent>
      </Card>

      <Card>
        <CardHeader><p className="section-kicker">Accumulated evidence</p><h3 className="mt-1 font-display text-xl font-semibold">空间材料</h3></CardHeader>
        <CardContent className="space-y-3">
          {space.items.length === 0 ? <div className="grid min-h-44 place-items-center rounded-xl bg-paper text-center"><div><Sparkles className="mx-auto size-6 text-muted" /><p className="mt-2 text-sm text-muted">空间还没有材料。可以从发现收件箱一键加入。</p><Link className="mt-3 inline-block text-sm font-semibold text-signal hover:underline" to="/discoveries">打开发现收件箱 →</Link></div></div> : space.items.map((item) => <article key={item.id} className="rounded-xl border border-line p-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><Badge variant="info">{itemTypeLabels[item.item_type]}</Badge><span className="font-semibold">{itemTitle(item)}</span></div><p className="mt-2 text-xs leading-5 text-muted">对象 ID：{item.item_id}</p>{item.note ? <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-sm leading-5 text-muted">{item.note}</p> : null}</div><span className="text-xs text-muted">#{item.position}</span></div></article>)}
        </CardContent>
      </Card>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}
