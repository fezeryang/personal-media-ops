import { FolderKanban, Plus, Search, Sparkles } from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import type {
  ResearchSpaceDetail,
  ResearchSpaceItemLookup,
  ResearchSpaceItemType,
} from "../api/research";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../components/ui/dialog";
import { EmptyState } from "../components/ui/empty-state";
import { FilterBar } from "../components/ui/filter-bar";
import { MasterDetailLayout } from "../components/ui/master-detail-layout";
import { SegmentedTabs } from "../components/ui/segmented-tabs";
import { Input } from "../components/ui/input";
import {
  useAddResearchSpaceItemMutation,
  useCreateResearchSpaceMutation,
  useResearchSpaceItemsQuery,
  useResearchSpaceQuery,
  useResearchSpacesQuery,
} from "../features/research/hooks/use-discovery-queries";
import { errorMessage } from "../lib/utils";

const itemTypeLabels: Record<ResearchSpaceItemType, string> = {
  research_task: "研究任务",
  discovery_candidate: "发现",
  evidence: "证据",
  entity: "实体",
  event: "事件",
  finding: "结论",
  unresolved_question: "未解问题",
  memory: "记忆",
  opportunity: "机会",
  validation_plan: "验证计划",
  action: "行动",
  outcome: "行动结果",
};

const itemTypes = Object.keys(itemTypeLabels) as ResearchSpaceItemType[];
const tabItems = [
  { value: "overview", label: "概览" },
  { value: "research", label: "研究" },
  { value: "discoveries", label: "发现" },
  { value: "opportunities", label: "机会" },
  { value: "evidence", label: "证据" },
  { value: "actions", label: "行动" },
] as const;
type SpaceTab = (typeof tabItems)[number]["value"];

function itemTitle(item: { item: Record<string, unknown>; item_id: string }): string {
  for (const key of ["title", "name", "statement", "objective", "summary", "result"]) {
    const value = item.item[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  return "未命名材料";
}

function itemGroup(itemType: ResearchSpaceItemType): Exclude<SpaceTab, "overview"> {
  if (["research_task", "entity", "event", "finding", "unresolved_question"].includes(itemType)) return "research";
  if (itemType === "discovery_candidate") return "discoveries";
  if (["opportunity", "validation_plan"].includes(itemType)) return "opportunities";
  if (["evidence", "memory"].includes(itemType)) return "evidence";
  return "actions";
}

function formatLookupDate(value: string) {
  return new Date(value).toLocaleDateString("zh-CN");
}

export function ResearchSpacesPage() {
  const navigate = useNavigate();
  const { spaceId } = useParams<{ spaceId: string }>();
  const [selectedId, setSelectedId] = useState("");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState<"all" | "active" | "archived">("all");
  const [sort, setSort] = useState<"updated" | "created" | "name">("updated");
  const [createOpen, setCreateOpen] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const spaces = useResearchSpacesQuery();
  const create = useCreateResearchSpaceMutation();
  const effectiveId = spaceId ?? selectedId ?? spaces.data?.[0]?.id ?? "";
  const detail = useResearchSpaceQuery(effectiveId);
  const filteredSpaces = useMemo(() => {
    const needle = search.trim().toLowerCase();
    return [...(spaces.data ?? [])]
      .filter((space) => status === "all" || space.status === status)
      .filter((space) => !needle || `${space.name} ${space.description ?? ""}`.toLowerCase().includes(needle))
      .sort((left, right) => {
        if (sort === "name") return left.name.localeCompare(right.name, "zh-CN");
        const field = sort === "created" ? "created_at" : "updated_at";
        return right[field].localeCompare(left[field]);
      });
  }, [search, sort, spaces.data, status]);

  function submitCreate() {
    const trimmedName = name.trim();
    if (!trimmedName) return;
    create.mutate(
      { name: trimmedName, description: description.trim() || undefined },
      {
        onSuccess: (space) => {
          setName("");
          setDescription("");
          setCreateOpen(false);
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
    <div className="space-y-5">
      <PageHeader
        title="研究空间"
        description="把需要持续理解的研究、发现和证据放在同一个上下文里。"
        action={<Button onClick={() => setCreateOpen(true)}><Plus className="size-4" />新建空间</Button>}
      />

      <Dialog open={createOpen} onOpenChange={setCreateOpen}>
        <DialogContent>
          <DialogTitle>新建研究空间</DialogTitle>
          <DialogDescription>为一个需要持续追踪的问题建立可积累的上下文。</DialogDescription>
          <div className="mt-5 space-y-4">
            <label className="block text-sm font-semibold">空间名称<Input className="mt-2" value={name} onChange={(event) => setName(event.currentTarget.value)} placeholder="例如：个人 AI 工具机会" maxLength={200} /></label>
            <label className="block text-sm font-semibold">描述（可选）<textarea className="mt-2 min-h-24 w-full rounded-xl border border-line px-3 py-2 text-sm outline-none focus:border-signal focus:ring-2 focus:ring-signal/15" value={description} onChange={(event) => setDescription(event.currentTarget.value)} maxLength={2_000} placeholder="这个空间持续追踪什么问题？" /></label>
            {create.error ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button><Button disabled={create.isPending || name.trim().length === 0} onClick={submitCreate}>{create.isPending ? "创建中…" : "创建空间"}</Button></div>
          </div>
        </DialogContent>
      </Dialog>

      <FilterBar
        search={search}
        onSearchChange={setSearch}
        searchPlaceholder="搜索研究空间"
        resultCount={filteredSpaces.length}
        filters={<>
          <label className="flex min-w-0 items-center gap-2 text-sm"><span className="shrink-0 text-xs text-muted">状态</span><select className="h-10 min-w-0 rounded-lg border border-line bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.currentTarget.value as typeof status)} aria-label="空间状态"><option value="all">全部</option><option value="active">活跃</option><option value="archived">已归档</option></select></label>
        </>}
        sort={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">排序</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={sort} onChange={(event) => setSort(event.currentTarget.value as typeof sort)} aria-label="空间排序"><option value="updated">最近更新</option><option value="created">最近创建</option><option value="name">名称</option></select></label>}
        chips={[
          ...(status !== "all" ? [{ label: `状态：${status === "active" ? "活跃" : "已归档"}`, onRemove: () => setStatus("all") }] : []),
          ...(sort !== "updated" ? [{ label: `排序：${sort === "created" ? "最近创建" : "名称"}`, onRemove: () => setSort("updated") }] : []),
        ]}
        onClear={() => { setSearch(""); setStatus("all"); setSort("updated"); }}
      />

      {spaces.isError ? <ErrorState title="研究空间加载失败" error={spaces.error} onRetry={() => void spaces.refetch()} /> : (
        <MasterDetailLayout
          listLabel="空间列表"
          storageKey="mediaops.master-detail.spaces.collapsed"
          list={<SpaceList spaces={filteredSpaces} pending={spaces.isPending} selectedId={effectiveId} onSelect={selectSpace} />}
          detail={detail.isError ? <ErrorState title="研究空间详情加载失败" error={detail.error} onRetry={() => void detail.refetch()} /> : detail.data ? <SpaceDetail space={detail.data} /> : <EmptyState icon={<FolderKanban className="size-7" />} title="选择一个空间" description="从左侧选择研究空间，查看它正在积累的材料。" />}
        />
      )}
    </div>
  );
}

function SpaceList({
  spaces,
  pending,
  selectedId,
  onSelect,
}: {
  spaces: Array<{ id: string; name: string; description: string | null; status: "active" | "archived"; item_count: number; updated_at: string }>;
  pending: boolean;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-line pb-4"><p className="section-kicker">持续上下文</p><h2 className="mt-1 font-display text-xl font-semibold">空间列表</h2></CardHeader>
      <CardContent className="space-y-2 p-3">
        {pending ? Array.from({ length: 4 }, (_, index) => <div key={index} className="h-20 animate-pulse rounded-xl bg-paper" />) : null}
        {!pending && spaces.length === 0 ? <EmptyState title="没有符合条件的空间" description="调整筛选条件，或新建一个研究空间。" /> : null}
        {spaces.map((space) => <button key={space.id} type="button" onClick={() => onSelect(space.id)} className={`w-full rounded-xl border p-3 text-left transition ${selectedId === space.id ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}><div className="flex items-start justify-between gap-2"><span className="line-clamp-2 text-sm font-semibold">{space.name}</span><Badge variant={space.status === "active" ? "success" : "neutral"}>{space.status === "active" ? "活跃" : "已归档"}</Badge></div><p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">{space.description ?? "没有描述"}</p><p className="mt-2 text-xs text-muted">{space.item_count} 项 · {formatLookupDate(space.updated_at)} 更新</p></button>)}
      </CardContent>
    </Card>
  );
}

function SpaceDetail({ space }: { space: ResearchSpaceDetail }) {
  const [tab, setTab] = useState<SpaceTab>("overview");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [itemSearch, setItemSearch] = useState("");
  const [pickerSearch, setPickerSearch] = useState("");
  const [itemSort, setItemSort] = useState<"updated" | "type">("updated");
  const [itemType, setItemType] = useState<ResearchSpaceItemType>("discovery_candidate");
  const [selectedLookup, setSelectedLookup] = useState<ResearchSpaceItemLookup | null>(null);
  const [note, setNote] = useState("");
  const [success, setSuccess] = useState("");
  const addItem = useAddResearchSpaceItemMutation();
  const lookup = useResearchSpaceItemsQuery({ itemType, query: pickerSearch });
  const items = useMemo(() => {
    const needle = itemSearch.trim().toLowerCase();
    return space.items
      .filter((item) => tab === "overview" || itemGroup(item.item_type) === tab)
      .filter((item) => !needle || `${itemTitle(item)} ${itemTypeLabels[item.item_type]} ${item.note ?? ""}`.toLowerCase().includes(needle))
      .sort((left, right) => itemSort === "type" ? itemTypeLabels[left.item_type].localeCompare(itemTypeLabels[right.item_type], "zh-CN") : right.updated_at.localeCompare(left.updated_at));
  }, [itemSearch, itemSort, space.items, tab]);

  function addSelected() {
    if (!selectedLookup) return;
    addItem.mutate(
      { spaceId: space.id, itemType: selectedLookup.item_type, itemId: selectedLookup.item_id, note: note.trim() || undefined },
      {
        onSuccess: () => {
          setSelectedLookup(null);
          setNote("");
          setPickerOpen(false);
          setSuccess("材料已加入空间");
        },
      },
    );
  }

  return (
    <div className="space-y-5">
      <Card>
        <CardHeader className="border-b border-line pb-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="section-kicker">研究空间</p><h2 className="mt-1 break-words font-display text-2xl font-semibold">{space.name}</h2><p className="mt-2 max-w-2xl text-sm leading-6 text-muted">{space.description ?? "这个空间还没有描述。"}</p></div><Badge variant={space.status === "active" ? "success" : "neutral"}>{space.status === "active" ? "活跃" : "已归档"}</Badge></div></CardHeader>
        <CardContent className="grid grid-cols-2 gap-3 p-4 sm:grid-cols-4"><Metric label="材料总数" value={String(space.items.length)} /><Metric label="研究与结论" value={String(space.items.filter((item) => itemGroup(item.item_type) === "research").length)} /><Metric label="发现与机会" value={String(space.items.filter((item) => ["discoveries", "opportunities"].includes(itemGroup(item.item_type))).length)} /><Metric label="证据与记忆" value={String(space.items.filter((item) => itemGroup(item.item_type) === "evidence").length)} /></CardContent>
      </Card>

      {success ? <p className="rounded-lg border border-signal/20 bg-signal/8 px-3 py-2 text-sm text-signal-strong" role="status">{success}</p> : null}
      {addItem.error ? <p className="rounded-lg border border-danger/20 bg-danger/8 px-3 py-2 text-sm text-danger" role="alert">{errorMessage(addItem.error)}</p> : null}

      <div className="flex flex-wrap items-center justify-between gap-3">
        <SegmentedTabs value={tab} onChange={setTab} label="研究空间内容" items={tabItems.map((item) => ({ ...item, count: item.value === "overview" ? space.items.length : space.items.filter((spaceItem) => itemGroup(spaceItem.item_type) === item.value).length }))} className="min-w-0 flex-1" />
        <Button onClick={() => { setSuccess(""); setPickerSearch(""); setPickerOpen(true); }}><Plus className="size-4" />添加材料</Button>
      </div>

      {tab !== "overview" ? <FilterBar search={itemSearch} onSearchChange={setItemSearch} searchPlaceholder="搜索空间材料" resultCount={items.length} sort={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">排序</span><select className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={itemSort} onChange={(event) => setItemSort(event.currentTarget.value as typeof itemSort)} aria-label="材料排序"><option value="updated">最近更新</option><option value="type">按类型</option></select></label>} onClear={() => { setItemSearch(""); setItemSort("updated"); }} chips={itemSort === "type" ? [{ label: "排序：按类型", onRemove: () => setItemSort("updated") }] : []} /> : null}

      {tab === "overview" ? <Overview space={space} onOpenPicker={() => setPickerOpen(true)} /> : <SpaceItems items={items} />}

      <Dialog open={pickerOpen} onOpenChange={setPickerOpen}>
        <DialogContent className="max-w-2xl">
          <DialogTitle>添加材料</DialogTitle>
          <DialogDescription>从已有材料中按标题和来源查找，不需要记住内部标识。</DialogDescription>
          <div className="mt-5 space-y-4">
            <div className="grid gap-3 sm:grid-cols-[180px_minmax(0,1fr)]"><label className="text-sm font-semibold">材料类型<select className="mt-2 h-10 w-full rounded-lg border border-line bg-white px-3 text-sm" value={itemType} onChange={(event) => { setItemType(event.currentTarget.value as ResearchSpaceItemType); setSelectedLookup(null); }} aria-label="材料类型">{itemTypes.map((type) => <option key={type} value={type}>{itemTypeLabels[type]}</option>)}</select></label><label className="text-sm font-semibold">搜索已有材料<div className="relative mt-2"><Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" /><Input className="pl-9" value={pickerSearch} onChange={(event) => setPickerSearch(event.currentTarget.value)} placeholder="输入标题或摘要" aria-label="搜索已有材料" /></div></label></div>
            <div className="max-h-72 space-y-2 overflow-y-auto rounded-xl border border-line p-2" role="listbox" aria-label="可选材料">
              {lookup.isPending ? <p className="p-4 text-sm text-muted">正在查找材料…</p> : null}
              {!lookup.isPending && (lookup.data ?? []).length === 0 ? <p className="p-4 text-sm text-muted">没有找到可选材料。可以换一个类型或关键词。</p> : null}
              {(lookup.data ?? []).map((choice) => <button key={`${choice.item_type}-${choice.item_id}`} type="button" role="option" aria-selected={selectedLookup?.item_id === choice.item_id} onClick={() => setSelectedLookup(choice)} className={`w-full rounded-lg border p-3 text-left ${selectedLookup?.item_id === choice.item_id ? "border-signal bg-signal/8" : "border-transparent hover:bg-paper"}`}><div className="flex items-start justify-between gap-3"><span className="line-clamp-2 text-sm font-semibold">{choice.title}</span><Badge variant="neutral">{itemTypeLabels[choice.item_type]}</Badge></div><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{choice.summary ?? "没有摘要"}</p><p className="mt-1 text-[11px] text-muted">{choice.source_type ?? "研究材料"} · {formatLookupDate(choice.updated_at)} 更新</p></button>)}
            </div>
            {selectedLookup ? <div className="rounded-xl bg-paper p-3"><p className="text-sm font-semibold">已选择：{selectedLookup.title}</p><Input className="mt-3" value={note} onChange={(event) => setNote(event.currentTarget.value)} placeholder="备注（可选）" aria-label="材料备注" /></div> : null}
            <div className="flex justify-end gap-2"><Button variant="ghost" onClick={() => setPickerOpen(false)}>取消</Button><Button disabled={!selectedLookup || addItem.isPending} onClick={addSelected}>{addItem.isPending ? "加入中…" : "加入空间"}</Button></div>
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function Overview({ space, onOpenPicker }: { space: ResearchSpaceDetail; onOpenPicker: () => void }) {
  return <div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><p className="section-kicker">当前上下文</p><h3 className="mt-1 font-display text-xl font-semibold">这个空间正在积累什么</h3></CardHeader><CardContent className="space-y-3"><p className="text-sm leading-6 text-muted">按材料类型整理后，研究过程、发现、机会和证据可以分别查看，不必在一条长页面里滚动。</p><div className="grid grid-cols-2 gap-2">{tabItems.slice(1).map((item) => <div key={item.value} className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{item.label}</p><p className="mt-1 text-lg font-semibold">{space.items.filter((spaceItem) => itemGroup(spaceItem.item_type) === item.value).length}</p></div>)}</div></CardContent></Card><Card><CardHeader><p className="section-kicker">下一步</p><h3 className="mt-1 font-display text-xl font-semibold">把新材料放进来</h3></CardHeader><CardContent className="space-y-3"><p className="text-sm leading-6 text-muted">从已有研究对象中搜索并选择，空间会保留来源和更新时间。</p><Button onClick={onOpenPicker}><Plus className="size-4" />添加材料</Button><Link className="block text-sm font-semibold text-signal hover:underline" to="/discoveries">去发现收件箱找新线索 →</Link></CardContent></Card></div>;
}

function SpaceItems({ items }: { items: ResearchSpaceDetail["items"] }) {
  if (items.length === 0) return <EmptyState icon={<Sparkles className="size-7" />} title="这里还没有材料" description="添加已有研究、发现或证据后，它们会按更新时间出现在这里。" />;
  return <div className="space-y-2">{items.map((item) => <article key={item.id} className="rounded-xl border border-line bg-white p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><Badge variant="info">{itemTypeLabels[item.item_type]}</Badge><p className="break-words text-sm font-semibold">{itemTitle(item)}</p></div>{item.note ? <p className="mt-2 rounded-lg bg-paper px-3 py-2 text-sm leading-5 text-muted">{item.note}</p> : null}<p className="mt-2 text-xs text-muted">更新于 {formatLookupDate(item.updated_at)}</p></div><details className="shrink-0"><summary className="cursor-pointer list-none text-xs font-semibold text-muted hover:text-ink">技术详情</summary><p className="mt-2 max-w-[16rem] break-all text-[11px] text-muted">对象标识：{item.item_id}</p></details></div></article>)}</div>;
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}
