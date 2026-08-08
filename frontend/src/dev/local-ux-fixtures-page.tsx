import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router";

import { PageHeader } from "../components/page-header";
import { ActionMenu } from "../components/ui/action-menu";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { CollapsibleSection } from "../components/ui/collapsible-section";
import { Dialog, DialogContent, DialogDescription, DialogTitle } from "../components/ui/dialog";
import { EmptyState } from "../components/ui/empty-state";
import { FilterBar } from "../components/ui/filter-bar";
import { MasterDetailLayout } from "../components/ui/master-detail-layout";
import { SegmentedTabs } from "../components/ui/segmented-tabs";
import { SideDrawer } from "../components/ui/side-drawer";
import { Input } from "../components/ui/input";

type Surface = "research" | "discovery" | "monitoring" | "spaces" | "memory" | "opportunities";
type Tab = "overview" | "evidence" | "history" | "actions";

interface FixtureRow {
  id: string;
  title: string;
  summary: string;
  type: string;
  status: string;
  platform: string;
  updated: string;
}

const surfaceConfig: Record<Surface, { title: string; description: string; listLabel: string; rowType: string }> = {
  research: { title: "AI 研究", description: "从一个问题开始，先确认理解，再在边界内推进。", listLabel: "研究任务列表", rowType: "研究任务" },
  discovery: { title: "发现收件箱", description: "集中处理值得判断的新线索，并保留来源与推荐原因。", listLabel: "发现列表", rowType: "发现" },
  monitoring: { title: "监控任务", description: "持续比较已知基线与新证据，只把重要变化送进收件箱。", listLabel: "监控任务列表", rowType: "监控" },
  spaces: { title: "研究空间", description: "把需要持续理解的研究、发现和证据放在同一个上下文里。", listLabel: "空间列表", rowType: "研究空间" },
  memory: { title: "记忆与证据", description: "按研究记录查看沉淀的结论、证据、未解决问题和长期记忆。", listLabel: "研究记录列表", rowType: "研究记录" },
  opportunities: { title: "机会", description: "只展示有证据路径的机会判断，并把验证动作留给用户确认。", listLabel: "机会列表", rowType: "机会" },
};

const surfaceLinks: Array<[Surface, string]> = [
  ["research", "AI 研究"],
  ["discovery", "发现"],
  ["monitoring", "监控"],
  ["spaces", "空间"],
  ["memory", "记忆"],
  ["opportunities", "机会"],
];

function fixtureRows(surface: Surface): FixtureRow[] {
  const config = surfaceConfig[surface];
  return Array.from({ length: 24 }, (_, index) => ({
    id: `${surface}-${index + 1}`,
    title: index === 7
      ? `${config.rowType}：一个很长的中文标题，用来验证窄屏下的换行、截断和下一步动作仍然可见`
      : `${config.rowType} ${String(index + 1).padStart(2, "0")} · ${surface === "spaces" ? "个人 AI 研究上下文" : "个人 AI 工作流"}`,
    summary: index === 5
      ? "这是一段较长的中文说明，用于检查列表密度、长文本断行和详情区域的可扫描性。"
      : `${index % 3 === 0 ? "正在推进" : index % 3 === 1 ? "等待判断" : "已完成"} · 保留来源、更新时间和下一步。`,
    type: index % 2 === 0 ? config.rowType : "跨平台线索",
    status: index % 4 === 0 ? "运行中" : index % 4 === 1 ? "待处理" : index % 4 === 2 ? "已完成" : "平台受限",
    platform: index % 3 === 0 ? "Bilibili · 知乎" : index % 3 === 1 ? "多平台" : "待选择平台",
    updated: `2026-08-${String(8 - (index % 7)).padStart(2, "0")}`,
  }));
}

function statusVariant(status: string): "success" | "warning" | "info" | "neutral" {
  if (status === "运行中") return "info";
  if (status === "待处理" || status === "平台受限") return "warning";
  if (status === "已完成") return "success";
  return "neutral";
}

function SurfaceStateCoverage() {
  return (
    <CollapsibleSection title="状态覆盖 · loading / empty / error / platform blocked" description="仅供本地 UX 验收，不代表生产数据。" count={5}>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <div className="rounded-xl bg-paper p-3 text-sm"><p className="font-semibold">加载中</p><div className="mt-3 h-2 animate-pulse rounded bg-line" /><p className="mt-2 text-xs text-muted">正在加载列表…</p></div>
        <div className="rounded-xl bg-paper p-3 text-sm"><p className="font-semibold">空状态</p><p className="mt-2 text-xs leading-5 text-muted">没有符合条件的材料。</p></div>
        <div className="rounded-xl border border-danger/20 bg-danger/5 p-3 text-sm"><p className="font-semibold text-danger">错误</p><p className="mt-2 text-xs leading-5 text-muted">数据加载失败，可重试。</p></div>
        <div className="rounded-xl border border-warning/20 bg-warning/5 p-3 text-sm"><p className="font-semibold">平台受限</p><p className="mt-2 text-xs leading-5 text-muted">需要登录或平台暂不可用。</p></div>
        <div className="rounded-xl bg-paper p-3 text-sm"><p className="font-semibold">长文本</p><p className="mt-2 line-clamp-2 text-xs leading-5 text-muted">长标题和长证据说明会在列表中收敛，在详情中完整展开。</p></div>
      </div>
    </CollapsibleSection>
  );
}

function FixtureList({ rows, selectedId, onSelect, listLabel }: { rows: FixtureRow[]; selectedId: string; onSelect: (id: string) => void; listLabel: string }) {
  return (
    <Card className="overflow-hidden">
      <CardHeader className="border-b border-line pb-4"><p className="section-kicker">本地密度样本 · 24 条</p><h2 className="mt-1 font-display text-xl font-semibold">{listLabel}</h2></CardHeader>
      <CardContent className="space-y-1.5 p-2">
        {rows.map((row) => <button key={row.id} type="button" onClick={() => onSelect(row.id)} className={`w-full rounded-xl border p-3 text-left transition ${row.id === selectedId ? "border-signal/35 bg-signal/7" : "border-transparent hover:bg-paper"}`}><div className="flex min-w-0 items-start justify-between gap-2"><span className="line-clamp-2 min-w-0 text-sm font-semibold">{row.title}</span><Badge variant={statusVariant(row.status)}>{row.status}</Badge></div><p className="mt-1 line-clamp-2 text-xs leading-5 text-muted">{row.summary}</p><p className="mt-2 text-[11px] text-muted">{row.type} · {row.platform} · {row.updated}</p></button>)}
      </CardContent>
    </Card>
  );
}

function FixtureDetail({ surface, row, onFeedback }: { surface: Surface; row: FixtureRow; onFeedback: (message: string) => void }) {
  const [tab, setTab] = useState<Tab>("overview");
  const [composer, setComposer] = useState("");
  const [pickerOpen, setPickerOpen] = useState(false);
  const [selectedMaterial, setSelectedMaterial] = useState("");
  const [notificationsOpen, setNotificationsOpen] = useState(false);
  const tabs: Array<{ value: Tab; label: string; count?: number }> = [
    { value: "overview", label: "概览" },
    { value: "evidence", label: "证据", count: 6 },
    { value: "history", label: surface === "monitoring" ? "运行记录" : "历史", count: 4 },
    { value: "actions", label: "后续动作", count: 2 },
  ];
  return (
    <div className="space-y-4">
      <Card><CardHeader className="border-b border-line pb-4"><div className="flex flex-wrap items-start justify-between gap-3"><div className="min-w-0"><p className="section-kicker">{surfaceConfig[surface].rowType}</p><h2 className="mt-1 break-words font-display text-2xl font-semibold">{row.title}</h2><p className="mt-2 text-sm leading-6 text-muted">{row.summary}</p></div><Badge variant={statusVariant(row.status)}>{row.status}</Badge></div><div className="mt-4 flex flex-wrap gap-2"><Button onClick={() => onFeedback("主要动作已触发")}>{surface === "opportunities" ? "创建验证计划" : surface === "monitoring" ? "立即运行" : "继续推进"}</Button><ActionMenu label="判断" items={[{ label: "有价值", onSelect: () => onFeedback("已标记为有价值") }, { label: "稍后", onSelect: () => onFeedback("已安排稍后处理") }, { label: "不相关", onSelect: () => onFeedback("已标记为不相关"), tone: "danger" }]} />{surface === "monitoring" ? <Button variant="secondary" onClick={() => setNotificationsOpen(true)}>通知 3</Button> : null}</div></CardHeader><CardContent className="grid grid-cols-2 gap-2 p-4 sm:grid-cols-4"><Metric label="来源" value="6" /><Metric label="独立来源" value="3" /><Metric label="平台" value="2" /><Metric label="最近更新" value={row.updated} /></CardContent></Card>
      <SegmentedTabs value={tab} onChange={setTab} label="详情标签页" items={tabs} />
      {tab === "overview" ? <div className="grid gap-4 md:grid-cols-2"><Card><CardHeader><p className="section-kicker">现在看什么</p><h3 className="mt-1 font-display text-xl font-semibold">这条记录说明了什么</h3></CardHeader><CardContent><p className="text-sm leading-6 text-muted">默认先看状态、推荐原因和下一步。完整来源、历史和内部资源按需展开。</p></CardContent></Card><Card><CardHeader><p className="section-kicker">焦点</p><h3 className="mt-1 font-display text-xl font-semibold">下一步建议</h3></CardHeader><CardContent><p className="text-sm leading-6 text-muted">确认是否值得继续投入，再打开证据或运行详情。</p></CardContent></Card></div> : null}
      {tab === "evidence" ? <Card><CardHeader><p className="section-kicker">Evidence</p><h3 className="mt-1 font-display text-xl font-semibold">来源与证据强度</h3></CardHeader><CardContent className="space-y-2">{Array.from({ length: 6 }, (_, index) => <article key={index} className="rounded-xl border border-line p-3"><div className="flex flex-wrap items-start justify-between gap-2"><p className="font-semibold">独立来源 {index + 1} · 一段可核对的真实材料</p><Badge variant={index === 4 ? "warning" : "success"}>{index === 4 ? "反向证据" : "直接证据"}</Badge></div><p className="mt-1 text-xs leading-5 text-muted">平台来源 · 更新时间 · 支持关系与说明</p></article>)}</CardContent></Card> : null}
      {tab === "history" ? <Card><CardHeader><p className="section-kicker">历史与运行</p><h3 className="mt-1 font-display text-xl font-semibold">摘要优先，详情按次展开</h3></CardHeader><CardContent className="space-y-2">{Array.from({ length: 4 }, (_, index) => <details key={index} className="rounded-xl border border-line p-3"><summary className="cursor-pointer list-none text-sm font-semibold">第 {index + 1} 次运行 · {index === 0 ? "有重要变化" : "无显著变化"}</summary><div className="mt-3 grid gap-2 text-xs text-muted sm:grid-cols-2"><span>查询：研究方向 {index + 1}</span><span>平台：Bilibili、知乎</span><span>新增数据：{index + 2} 条</span><span>资源：{index + 1} 次调用</span></div></details>)}</CardContent></Card> : null}
      {tab === "actions" ? <div className="space-y-3"><CollapsibleSection title={surface === "opportunities" ? "记录验证结果" : "高级设置与后续动作"} description="准备好时再填写，默认不占用页面空间" count={2}><div className="space-y-3"><Input aria-label="动作说明" value={composer} onChange={(event) => setComposer(event.currentTarget.value)} placeholder="输入下一步说明" /><Button variant="secondary" onClick={() => onFeedback(composer.trim() ? "动作已保存" : "请先填写动作说明")}>保存动作</Button></div></CollapsibleSection><p className="rounded-xl bg-paper p-4 text-sm text-muted">动作必须由用户明确确认，fixture 不会执行外部操作。</p></div> : null}
      {surface === "research" ? <CollapsibleSection title="高级设置" description="平台、预算和覆盖范围" count={3}><p className="text-sm text-muted">Bilibili · 知乎 · 低资源模式</p></CollapsibleSection> : null}
      {surface === "spaces" ? <><Button variant="secondary" onClick={() => setPickerOpen(true)}>添加材料</Button><Dialog open={pickerOpen} onOpenChange={setPickerOpen}><DialogContent><DialogTitle>添加材料</DialogTitle><DialogDescription>从已有对象选择，不需要知道内部 ID。</DialogDescription><div className="mt-4 space-y-2">{["研究任务：验证工作流", "发现：登录摩擦", "证据：真实反馈"].map((item) => <button key={item} type="button" className={`w-full rounded-lg border p-3 text-left text-sm ${selectedMaterial === item ? "border-signal bg-signal/8" : "border-line"}`} onClick={() => setSelectedMaterial(item)}>{item}</button>)}<Button disabled={!selectedMaterial} onClick={() => { setPickerOpen(false); onFeedback("材料已加入空间"); }}>加入空间</Button></div></DialogContent></Dialog></> : null}
      <SideDrawer open={notificationsOpen} onOpenChange={setNotificationsOpen} title="通知" description="只显示需要判断的变化。"><div className="space-y-2"><p className="rounded-xl bg-paper p-3 text-sm">新增变化值得继续研究。</p><p className="rounded-xl bg-paper p-3 text-sm">平台受限任务等待处理。</p></div></SideDrawer>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return <div className="rounded-xl bg-paper p-3"><p className="text-xs text-muted">{label}</p><p className="mt-1 text-sm font-semibold">{value}</p></div>;
}

function LocalUxSurface({ surface, defaultCollapsed }: { surface: Surface; defaultCollapsed: boolean }) {
  const config = surfaceConfig[surface];
  const rows = useMemo(() => fixtureRows(surface), [surface]);
  const [selectedId, setSelectedId] = useState(rows[0]?.id ?? "");
  const [search, setSearch] = useState("");
  const [status, setStatus] = useState("all");
  const [sort, setSort] = useState("updated");
  const [feedback, setFeedback] = useState("");
  const visibleRows = useMemo(() => rows.filter((row) => !search.trim() || `${row.title} ${row.summary} ${row.platform}`.toLowerCase().includes(search.trim().toLowerCase())).filter((row) => status === "all" || (status === "blocked" ? row.status === "平台受限" : row.status === status)).sort((left, right) => sort === "name" ? left.title.localeCompare(right.title, "zh-CN") : right.updated.localeCompare(left.updated)), [rows, search, sort, status]);
  const selected = rows.find((row) => row.id === selectedId) ?? rows[0];
  return <div data-ux-surface={surface} className="space-y-5"><PageHeader title={config.title} description={config.description} action={<Button onClick={() => setFeedback("主要动作已触发")}>新建</Button>} /><p className="rounded-xl border border-signal/20 bg-signal/5 px-3 py-2 text-sm text-signal-strong" role="status">{feedback || "这是脱敏本地 UX fixture：24 条列表、长文本和多种状态。"}</p><FilterBar search={search} onSearchChange={setSearch} searchPlaceholder={`搜索${config.rowType}`} resultCount={visibleRows.length} filters={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">状态</span><select aria-label={`${config.rowType}状态`} className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.currentTarget.value)}><option value="all">全部</option><option value="运行中">运行中</option><option value="待处理">待处理</option><option value="blocked">平台受限</option></select></label>} sort={<label className="flex items-center gap-2 text-sm"><span className="text-xs text-muted">排序</span><select aria-label={`${config.rowType}排序`} className="h-10 rounded-lg border border-line bg-white px-3 text-sm" value={sort} onChange={(event) => setSort(event.currentTarget.value)}><option value="updated">最近更新</option><option value="name">名称</option></select></label>} chips={[...(status !== "all" ? [{ label: `状态：${status === "blocked" ? "平台受限" : status}`, onRemove: () => setStatus("all") }] : []), ...(sort !== "updated" ? [{ label: "排序：名称", onRemove: () => setSort("updated") }] : [])]} onClear={() => { setSearch(""); setStatus("all"); setSort("updated"); }} /><MasterDetailLayout listLabel={config.listLabel} defaultCollapsed={defaultCollapsed} list={<FixtureList rows={visibleRows} selectedId={selected?.id ?? ""} onSelect={setSelectedId} listLabel={config.listLabel} />} detail={selected ? <FixtureDetail surface={surface} row={selected} onFeedback={setFeedback} /> : <EmptyState title={`没有符合条件的${config.rowType}`} description="清除筛选后重新查看。" />} /><SurfaceStateCoverage /></div>;
}

export function LocalUxFixturesPage() {
  const [params] = useSearchParams();
  const rawSurface = window.location.pathname.split("/").filter(Boolean).at(-1) ?? "research";
  const surface: Surface = (rawSurface in surfaceConfig ? rawSurface : "research") as Surface;
  const defaultCollapsed = params.get("list") === "collapsed";
  useEffect(() => {
    const root = document.documentElement;
    document.body.dataset.documentOverflow = root.scrollWidth <= root.clientWidth ? "passed" : `${root.scrollWidth}>${root.clientWidth}`;
  });
  return <main className="min-h-screen bg-canvas px-4 py-5 text-ink sm:px-6 sm:py-7 xl:px-10"><div className="mx-auto max-w-[1480px]"><header className="mb-5 rounded-2xl border border-line bg-white p-4"><p className="section-kicker">Local UX fixture · 24 条密度样本</p><h1 className="mt-1 font-display text-xl font-semibold sm:text-2xl">核心页面响应式验收</h1><p className="mt-2 max-w-3xl text-sm leading-6 text-muted">用于检查信息层级、筛选、折叠、主次动作和长文本。所有内容均为脱敏本地样例，不调用生产 API。</p><nav className="mt-4 flex flex-wrap gap-2" aria-label="本地 UX 页面"><a className="rounded-lg border border-line px-3 py-2 text-sm font-semibold hover:bg-paper" href="/__local/fixtures">状态总览</a>{surfaceLinks.map(([value, label]) => <a key={value} className={`rounded-lg px-3 py-2 text-sm font-semibold ${value === surface ? "bg-ink text-white" : "border border-line hover:bg-paper"}`} href={`/__local/ux/${value}`}>{label}</a>)}</nav></header><LocalUxSurface surface={surface} defaultCollapsed={defaultCollapsed} /></div></main>;
}
