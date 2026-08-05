import {
  Activity,
  Archive,
  Bell,
  Check,
  ExternalLink,
  History,
  Layers3,
  Pause,
  Play,
  Plus,
  Radar,
  RotateCcw,
  ShieldAlert,
  Sparkles,
} from "lucide-react";
import { useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router";

import type {
  MonitoringChange,
  MonitoringMission,
  MonitoringMissionDetail,
  MonitoringNotification,
} from "../api/monitoring";
import { ErrorState } from "../components/error-state";
import { PageHeader } from "../components/page-header";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Card, CardContent, CardHeader } from "../components/ui/card";
import { Input } from "../components/ui/input";
import {
  useArchiveMonitoringMissionMutation,
  useConfirmMonitoringMissionMutation,
  useCreateMonitoringMissionMutation,
  useMonitoringBaselineQuery,
  useMonitoringChangesQuery,
  useMonitoringMissionQuery,
  useMonitoringMissionsQuery,
  useMonitoringNotificationsQuery,
  useMonitoringRunsQuery,
  usePauseMonitoringMissionMutation,
  useResumeMonitoringMissionMutation,
  useRunMonitoringMissionMutation,
  useUpdateMonitoringNotificationMutation,
} from "../features/monitoring/hooks/use-monitoring-queries";
import { errorMessage, formatDateTime } from "../lib/utils";

const statusLabels: Record<string, string> = {
  draft: "待确认",
  active: "运行中",
  paused: "已暂停",
  running: "正在运行",
  waiting_platform: "平台受限",
  waiting_login: "等待登录",
  completed_run: "已完成一轮",
  degraded: "降级运行",
  failed: "本轮失败",
  archived: "已归档",
};
const statusVariants: Record<string, "neutral" | "info" | "success" | "warning" | "danger"> = {
  draft: "neutral",
  active: "success",
  paused: "warning",
  running: "info",
  waiting_platform: "warning",
  waiting_login: "warning",
  completed_run: "success",
  degraded: "warning",
  failed: "danger",
  archived: "neutral",
};
const attentionLabels: Record<string, string> = {
  immediate_attention: "立即关注",
  daily_digest: "今日摘要",
  normal_record: "普通记录",
  silent_memory: "仅写入记忆",
  ignored: "已静默",
};
const changeTypeLabels: Record<string, string> = {
  new_feature: "新功能",
  new_event: "新事件",
  new_negative_evidence: "负向反馈",
  new_positive_evidence: "正向反馈",
  new_user_pain_point: "用户痛点",
  updated_fact: "事实更新",
  contradicted_finding: "反向证据",
  reconfirmed_finding: "重新确认",
  new_entity: "新实体",
  new_claim: "新说法",
};

function statusBadge(status: string) {
  return <Badge variant={statusVariants[status] ?? "neutral"}>{statusLabels[status] ?? status}</Badge>;
}

function unknownText(value: unknown, fallback = "未记录"): string {
  return typeof value === "string" && value.trim() ? value : fallback;
}

function goalPreview(mission: MonitoringMission): string {
  return mission.goal.length > 100 ? `${mission.goal.slice(0, 100)}…` : mission.goal;
}

function scheduleLabel(mission: MonitoringMission): string {
  if (mission.schedule_type === "daily") return "每日运行";
  if (mission.schedule_type === "weekly") return "每周运行";
  if (mission.schedule_type === "custom") return "自定义安全频率";
  return "手动运行";
}

function missionCard(mission: MonitoringMission, onOpen: (id: string) => void) {
  return (
    <button
      key={mission.id}
      type="button"
      onClick={() => onOpen(mission.id)}
      className="w-full rounded-2xl border border-line bg-white p-5 text-left shadow-[0_1px_2px_rgba(15,23,42,0.04)] transition hover:-translate-y-0.5 hover:border-signal/35 hover:shadow-[0_12px_30px_rgba(25,75,75,0.08)]"
    >
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex min-w-0 items-start gap-3">
          <div className="grid size-10 shrink-0 place-items-center rounded-xl bg-[#e7f1ed] text-signal-strong">
            <Radar className="size-5" />
          </div>
          <div className="min-w-0">
            <p className="truncate font-display text-lg font-semibold">{mission.title}</p>
            <p className="mt-1 line-clamp-2 text-sm leading-5 text-muted">{goalPreview(mission)}</p>
          </div>
        </div>
        {statusBadge(mission.status)}
      </div>
      <div className="mt-5 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
        <div className="rounded-xl bg-paper p-3"><p className="text-muted">类型</p><p className="mt-1 font-semibold">{mission.mission_type}</p></div>
        <div className="rounded-xl bg-paper p-3"><p className="text-muted">频率</p><p className="mt-1 font-semibold">{scheduleLabel(mission)}</p></div>
        <div className="rounded-xl bg-paper p-3"><p className="text-muted">最近运行</p><p className="mt-1 font-semibold">{formatDateTime(mission.last_run_at)}</p></div>
        <div className="rounded-xl bg-paper p-3"><p className="text-muted">下次运行</p><p className="mt-1 font-semibold">{formatDateTime(mission.next_run_at)}</p></div>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-2 text-xs text-muted">
        <span>{mission.platforms.length ? `平台：${mission.platforms.join("、")}` : "平台：复用现有证据"}</span>
        <span className="text-line">·</span>
        <span>模型预算 {mission.budget.max_model_calls} 次</span>
        {mission.latest_change ? <Badge variant="info">最近有重要变化</Badge> : <span>暂无重要变化</span>}
      </div>
    </button>
  );
}

function CreateMission({ onCreated }: { onCreated: (mission: MonitoringMissionDetail) => void }) {
  const [goal, setGoal] = useState("");
  const [platforms, setPlatforms] = useState("bili,zhihu");
  const [draft, setDraft] = useState<MonitoringMissionDetail | null>(null);
  const create = useCreateMonitoringMissionMutation();
  const confirm = useConfirmMonitoringMissionMutation();
  const submit = () => {
    if (goal.trim().length < 5) return;
    create.mutate(
      {
        goal: goal.trim(),
        platforms: platforms.split(",").map((item) => item.trim().toLowerCase()).filter(Boolean),
        mission_type: "research_question",
        schedule_type: "manual",
        confirmed: false,
      },
      { onSuccess: setDraft },
    );
  };
  if (draft) {
    const understanding = draft.understanding;
    return (
      <Card className="border-signal/25 bg-[linear-gradient(135deg,#f7fbf9,#eef5f1)]">
        <CardHeader>
          <p className="section-kicker">AI interpretation · step 2</p>
          <h2 className="mt-1 font-display text-2xl font-semibold">先确认我理解的监控目标</h2>
          <p className="mt-2 text-sm leading-6 text-muted">系统会先建立基线；确认后才会创建长期监控，不会暗中开启订阅。</p>
        </CardHeader>
        <CardContent className="space-y-4 pt-5">
          <div className="rounded-xl border border-signal/20 bg-white/75 p-4">
            <p className="text-xs font-semibold text-muted">监控目标</p>
            <p className="mt-1 font-semibold">{unknownText(understanding.interpreted_goal, draft.goal)}</p>
            <p className="mt-3 text-sm leading-6 text-muted">{unknownText(understanding.why_monitor)}</p>
          </div>
          <div className="grid gap-3 md:grid-cols-2">
            <div className="rounded-xl border border-line bg-white/70 p-4"><p className="font-semibold">关注变化</p><ul className="mt-2 space-y-1 text-sm text-muted">{(Array.isArray(understanding.watch_for) ? understanding.watch_for : []).map((item) => <li key={String(item)}>· {String(item)}</li>)}</ul></div>
            <div className="rounded-xl border border-line bg-white/70 p-4"><p className="font-semibold">忽略噪音</p><ul className="mt-2 space-y-1 text-sm text-muted">{(Array.isArray(understanding.ignore) ? understanding.ignore : []).map((item) => <li key={String(item)}>· {String(item)}</li>)}</ul></div>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs text-muted">
            <Badge variant="info">证据要求：独立来源 + 时间 + 反向证据</Badge>
            <Badge variant="neutral">{scheduleLabel(draft)}</Badge>
            <span>平台：{draft.platforms.join("、") || "现有证据库"}</span>
          </div>
          <div className="flex flex-wrap gap-2">
            <Button onClick={() => confirm.mutate(draft.id, { onSuccess: onCreated })} disabled={confirm.isPending}>{confirm.isPending ? "确认中…" : "确认并创建监控"} <Check className="size-4" /></Button>
            <Button variant="ghost" onClick={() => setDraft(null)} disabled={confirm.isPending}>返回修改</Button>
          </div>
          {create.isError || confirm.isError ? <p className="text-sm text-danger">{errorMessage(create.error ?? confirm.error)}</p> : null}
        </CardContent>
      </Card>
    );
  }
  return (
    <Card className="border-signal/20 bg-white">
      <CardHeader>
        <p className="section-kicker">Create a mission · step 1</p>
        <h2 className="mt-1 font-display text-2xl font-semibold">你希望持续了解什么变化？</h2>
        <p className="mt-2 text-sm leading-6 text-muted">用自然语言描述长期关注目标。高级预算和调度会在理解卡中确认。</p>
      </CardHeader>
      <CardContent className="space-y-4 pt-5">
        <textarea
          className="min-h-28 w-full rounded-xl border border-line bg-paper/40 px-4 py-3 text-sm leading-6 outline-none transition focus:border-signal focus:ring-2 focus:ring-signal/15"
          value={goal}
          onChange={(event) => setGoal(event.currentTarget.value)}
          placeholder="例如：持续关注值得关注的个人 AI 工具，只告诉我新产品、重要功能变化和真实用户反馈变化。"
          aria-label="监控目标"
        />
        <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-end">
          <label className="text-sm font-semibold">建议平台（逗号分隔）<Input className="mt-2" value={platforms} onChange={(event) => setPlatforms(event.currentTarget.value)} aria-label="建议平台" /></label>
          <Button onClick={submit} disabled={create.isPending || goal.trim().length < 5}>{create.isPending ? "理解中…" : "生成监控理解卡"} <Sparkles className="size-4" /></Button>
        </div>
        {create.isError ? <p className="text-sm text-danger">{errorMessage(create.error)}</p> : null}
      </CardContent>
    </Card>
  );
}

function ChangeCard({ change }: { change: MonitoringChange }) {
  return (
    <article className="rounded-2xl border border-line bg-white p-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0"><div className="flex flex-wrap items-center gap-2"><Badge variant={change.attention_level === "immediate_attention" ? "danger" : "info"}>{attentionLabels[change.attention_level] ?? change.attention_level}</Badge><Badge variant="neutral">{changeTypeLabels[change.change_type] ?? change.change_type}</Badge></div><h3 className="mt-3 break-words font-display text-xl font-semibold">{change.title}</h3></div>
        <span className="shrink-0 text-xs text-muted">{formatDateTime(change.latest_seen_at)}</span>
      </div>
      <p className="mt-3 text-sm leading-6 text-muted">{change.summary}</p>
      <div className="mt-4 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"><div className="rounded-lg bg-paper p-3"><p className="text-muted">相关性</p><p className="mt-1 font-semibold">{Math.round(change.relevance_score * 100)}%</p></div><div className="rounded-lg bg-paper p-3"><p className="text-muted">新颖性</p><p className="mt-1 font-semibold">{Math.round(change.novelty_score * 100)}%</p></div><div className="rounded-lg bg-paper p-3"><p className="text-muted">独立来源</p><p className="mt-1 font-semibold">{Math.round(change.source_independence_score * 100)}%</p></div><div className="rounded-lg bg-paper p-3"><p className="text-muted">证据数</p><p className="mt-1 font-semibold">{change.sources.length}</p></div></div>
      <div className="mt-4 rounded-xl border border-signal/15 bg-signal/[0.04] p-4 text-sm"><p className="font-semibold">为什么值得关注</p><p className="mt-1 leading-6 text-muted">{unknownText(change.explanation.why_new)}；{unknownText(change.explanation.source_independence)}</p></div>
      {change.memory_update ? <p className="mt-3 text-xs text-muted">已记录记忆更新 · {unknownText(change.memory_update.confirmation_status, "待确认状态未记录")}</p> : null}
      <div className="mt-3 flex flex-wrap gap-2 text-xs text-muted"><span>首次出现 {formatDateTime(change.first_seen_at)}</span><span>·</span><span>{change.sources.filter((source) => source.is_repost === true).length} 条疑似转载已合并</span></div>
    </article>
  );
}

function NotificationPanel({ notifications }: { notifications: MonitoringNotification[] }) {
  const update = useUpdateMonitoringNotificationMutation();
  return (
    <Card>
      <CardHeader><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">Attention queue</p><h2 className="mt-1 font-display text-xl font-semibold">站内通知</h2></div><Bell className="size-5 text-signal" /></div></CardHeader>
      <CardContent className="space-y-3 pt-4">
        {notifications.length === 0 ? <p className="rounded-xl bg-paper p-4 text-sm text-muted">暂无未读通知。没有值得关注的变化时，系统保持安静。</p> : notifications.map((notification) => <div key={notification.id} className="rounded-xl border border-line p-4"><div className="flex items-start justify-between gap-3"><div className="min-w-0"><p className="font-semibold">{notification.title}</p><p className="mt-1 text-sm leading-5 text-muted">{notification.summary}</p></div><Badge variant={notification.status === "unread" ? "warning" : "neutral"}>{notification.status === "unread" ? "未读" : notification.status}</Badge></div><div className="mt-3 flex flex-wrap gap-2"><Button size="sm" variant="secondary" disabled={update.isPending} onClick={() => update.mutate({ notificationId: notification.id, action: "read" })}>标记已读</Button><Button size="sm" variant="ghost" disabled={update.isPending} onClick={() => update.mutate({ notificationId: notification.id, action: "defer" })}>稍后处理</Button><Button size="sm" variant="ghost" disabled={update.isPending} onClick={() => update.mutate({ notificationId: notification.id, action: "ignore" })}>忽略</Button><Link className="inline-flex items-center gap-1 px-2 text-xs font-semibold text-signal hover:underline" to={`/monitoring/${encodeURIComponent(notification.mission_id)}`}>打开监控 <ExternalLink className="size-3" /></Link></div></div>)}
        {update.isError ? <p className="text-sm text-danger">{errorMessage(update.error)}</p> : null}
      </CardContent>
    </Card>
  );
}

function MissionDetail({ missionId }: { missionId: string }) {
  const [tab, setTab] = useState("overview");
  const mission = useMonitoringMissionQuery(missionId);
  const runs = useMonitoringRunsQuery(missionId, tab === "runs" || tab === "overview");
  const changes = useMonitoringChangesQuery(missionId, tab === "changes" || tab === "overview");
  const baseline = useMonitoringBaselineQuery(missionId, tab === "baseline" || tab === "overview");
  const notifications = useMonitoringNotificationsQuery();
  const run = useRunMonitoringMissionMutation();
  const pause = usePauseMonitoringMissionMutation();
  const resume = useResumeMonitoringMissionMutation();
  const archive = useArchiveMonitoringMissionMutation();
  const navigate = useNavigate();
  const tabs = [
    ["overview", "概览"],
    ["changes", "重要变化"],
    ["runs", "运行记录"],
    ["baseline", "已知基线"],
    ["scope", "监控范围"],
    ["budget", "预算"],
    ["technical", "技术详情"],
  ];
  if (mission.isPending) return <div className="grid min-h-64 place-items-center text-sm text-muted">正在加载监控详情…</div>;
  if (mission.isError || !mission.data) return <ErrorState title="监控详情加载失败" error={mission.error} onRetry={() => void mission.refetch()} />;
  const item = mission.data;
  const actionError = run.error ?? pause.error ?? resume.error ?? archive.error;
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Monitoring mission" title={item.title} description={item.goal} action={<Button variant="secondary" onClick={() => void navigate("/monitoring")}>返回监控列表</Button>} />
      <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-line bg-white p-4"><div className="flex flex-wrap items-center gap-2">{statusBadge(item.status)}<span className="text-sm text-muted">{scheduleLabel(item)} · 最近运行 {formatDateTime(item.last_run_at)}</span></div><div className="flex flex-wrap gap-2">{item.status === "paused" ? <Button size="sm" variant="secondary" onClick={() => resume.mutate(item.id)}><Play className="size-4" />恢复</Button> : item.status !== "archived" ? <Button size="sm" variant="secondary" onClick={() => pause.mutate(item.id)}><Pause className="size-4" />暂停</Button> : null}{item.status !== "archived" ? <Button size="sm" onClick={() => run.mutate(item.id)} disabled={run.isPending || item.status === "draft"}><Radar className="size-4" />{run.isPending ? "运行中…" : "立即运行"}</Button> : null}{item.status !== "archived" ? <Button size="sm" variant="ghost" onClick={() => archive.mutate(item.id)}><Archive className="size-4" />归档</Button> : null}</div></div>
      {actionError ? <p className="rounded-xl border border-danger/25 bg-danger/5 p-3 text-sm text-danger">{errorMessage(actionError)}</p> : null}
      <nav className="-mx-1 flex gap-1 overflow-x-auto px-1 pb-1" aria-label="监控详情标签页">{tabs.map(([value, label]) => <button key={value} type="button" onClick={() => setTab(value)} className={`shrink-0 rounded-full px-4 py-2 text-sm font-semibold transition ${tab === value ? "bg-ink text-white" : "bg-paper text-muted hover:text-ink"}`}>{label}</button>)}</nav>

      {tab === "overview" ? <>
        <section className="grid gap-5 lg:grid-cols-[1.15fr_0.85fr]">
          <Card><CardHeader><p className="section-kicker">Mission brief</p><h2 className="mt-1 font-display text-2xl font-semibold">正在监控什么，最近发生了什么？</h2></CardHeader><CardContent className="space-y-4 pt-5"><div className="rounded-xl bg-paper p-4"><p className="text-xs font-semibold text-muted">理解后的目标</p><p className="mt-1 text-sm leading-6">{unknownText(item.understanding.interpreted_goal, item.goal)}</p></div><div className="grid gap-3 sm:grid-cols-2"><div><p className="text-sm font-semibold">关注变化</p><p className="mt-2 text-sm leading-6 text-muted">{Array.isArray(item.understanding.watch_for) ? item.understanding.watch_for.map(String).join("、") : "未记录"}</p></div><div><p className="text-sm font-semibold">忽略内容</p><p className="mt-2 text-sm leading-6 text-muted">{Array.isArray(item.understanding.ignore) ? item.understanding.ignore.map(String).join("、") : "未记录"}</p></div></div><div className="rounded-xl border border-signal/20 bg-signal/[0.04] p-4 text-sm"><p className="font-semibold">下一步建议</p><p className="mt-1 leading-6 text-muted">{changes.data?.[0] ? "先查看这次变化的独立来源，再决定是否继续研究或更新记忆。" : "完成一次运行后，系统会比较新证据与已知基线；无变化时保持静默。"}</p></div></CardContent></Card>
          <Card><CardHeader><p className="section-kicker">Signal summary</p><h2 className="mt-1 font-display text-xl font-semibold">值得关注的变化</h2></CardHeader><CardContent className="space-y-3 pt-4">{changes.isError ? <ErrorState title="变化加载失败" error={changes.error} onRetry={() => void changes.refetch()} /> : changes.data?.slice(0, 3).map((change) => <div key={change.id} className="rounded-xl border border-line p-3"><div className="flex items-center justify-between gap-2"><Badge variant="info">{attentionLabels[change.attention_level] ?? change.attention_level}</Badge><span className="text-xs text-muted">{formatDateTime(change.latest_seen_at)}</span></div><p className="mt-2 font-semibold">{change.title}</p><p className="mt-1 line-clamp-2 text-sm leading-5 text-muted">{change.summary}</p></div>)}{!changes.isPending && !changes.data?.length ? <p className="rounded-xl bg-paper p-4 text-sm text-muted">目前没有重要变化。系统不会把首次基线或重复内容伪装成通知。</p> : null}<Button className="w-full" variant="ghost" onClick={() => setTab("changes")}>查看全部变化 <ExternalLink className="size-3.5" /></Button></CardContent></Card>
        </section>
        <section className="grid gap-5 lg:grid-cols-2"><Card><CardHeader><p className="section-kicker">Platform state</p><h2 className="mt-1 font-display text-xl font-semibold">平台与资源</h2></CardHeader><CardContent className="space-y-3 pt-4"><div className="flex flex-wrap gap-2">{item.platforms.length ? item.platforms.map((platform) => <Badge key={platform} variant="success">{platform} · 已纳入</Badge>) : <Badge variant="neutral">复用现有证据库</Badge>}</div><p className="text-sm leading-6 text-muted">平台状态独立记录。遇到登录或平台限制时，本任务会降级或等待，不会把搜索验证冒充成其他模式已验证。</p></CardContent></Card><Card><CardHeader><p className="section-kicker">Known baseline</p><h2 className="mt-1 font-display text-xl font-semibold">与上次相比</h2></CardHeader><CardContent className="pt-4">{baseline.data ? <div className="grid grid-cols-2 gap-2 text-sm"><div className="rounded-xl bg-paper p-4"><p className="text-muted">基线版本</p><p className="mt-1 font-semibold">v{baseline.data.version}</p></div><div className="rounded-xl bg-paper p-4"><p className="text-muted">已知内容</p><p className="mt-1 font-semibold">{Array.isArray(baseline.data.snapshot.content_ids) ? baseline.data.snapshot.content_ids.length : 0} 条</p></div></div> : <p className="text-sm text-muted">尚未建立基线。立即运行会先记录当前已知状态。</p>}</CardContent></Card></section>
        <NotificationPanel notifications={(notifications.data ?? []).filter((notification) => notification.status === "unread").slice(0, 4)} />
      </> : null}
      {tab === "changes" ? <Card><CardHeader><p className="section-kicker">Change log</p><h2 className="mt-1 font-display text-2xl font-semibold">重要变化</h2><p className="mt-2 text-sm text-muted">只展示相对基线的新信息；转载、同源同步和低置信内容会被合并或静默。</p></CardHeader><CardContent className="space-y-4 pt-5">{changes.isError ? <ErrorState title="重要变化加载失败" error={changes.error} onRetry={() => void changes.refetch()} /> : changes.data?.map((change) => <ChangeCard key={change.id} change={change} />)}{!changes.isPending && !changes.data?.length ? <p className="rounded-xl bg-paper p-6 text-center text-sm text-muted">暂无真实变化。保持静默本身是一次有效监控结果。</p> : null}</CardContent></Card> : null}
      {tab === "runs" ? <Card><CardHeader><p className="section-kicker">Run history</p><h2 className="mt-1 font-display text-2xl font-semibold">运行记录</h2></CardHeader><CardContent className="space-y-3 pt-5">{runs.isError ? <ErrorState title="运行记录加载失败" error={runs.error} onRetry={() => void runs.refetch()} /> : runs.data?.map((runItem) => <article key={runItem.id} className="rounded-xl border border-line p-4"><div className="flex flex-wrap items-center justify-between gap-3"><div className="flex items-center gap-2"><History className="size-4 text-signal" /><p className="font-semibold">{formatDateTime(runItem.created_at)}</p>{statusBadge(runItem.status)}</div><span className="text-xs text-muted">{runItem.trigger === "scheduled" ? "计划触发" : "手动触发"}</span></div><div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4"><div><p className="text-muted">变化</p><p className="mt-1 font-semibold">{runItem.change_count}</p></div><div><p className="text-muted">通知</p><p className="mt-1 font-semibold">{runItem.notification_count}</p></div><div><p className="text-muted">内容</p><p className="mt-1 font-semibold">{unknownText(runItem.resource.collection_count, "未记录")}</p></div><div><p className="text-muted">模型调用</p><p className="mt-1 font-semibold">{unknownText(runItem.resource.model_calls, "未记录")}</p></div></div>{runItem.failure_reason ? <p className="mt-3 rounded-lg bg-danger/5 p-3 text-sm text-danger">{runItem.failure_reason}</p> : null}</article>)}{!runs.isPending && !runs.data?.length ? <p className="rounded-xl bg-paper p-6 text-center text-sm text-muted">还没有运行记录。</p> : null}</CardContent></Card> : null}
      {tab === "baseline" ? <Card><CardHeader><p className="section-kicker">Baseline history</p><h2 className="mt-1 font-display text-2xl font-semibold">已知基线</h2></CardHeader><CardContent className="space-y-4 pt-5">{baseline.data ? <><div className="grid gap-3 sm:grid-cols-3"><div className="rounded-xl bg-paper p-4"><p className="text-xs text-muted">版本</p><p className="mt-1 font-display text-2xl font-semibold">v{baseline.data.version}</p></div><div className="rounded-xl bg-paper p-4"><p className="text-xs text-muted">内容 ID</p><p className="mt-1 font-display text-2xl font-semibold">{Array.isArray(baseline.data.snapshot.content_ids) ? baseline.data.snapshot.content_ids.length : 0}</p></div><div className="rounded-xl bg-paper p-4"><p className="text-xs text-muted">建立时间</p><p className="mt-1 text-sm font-semibold">{formatDateTime(baseline.data.created_at)}</p></div></div><p className="text-sm leading-6 text-muted">基线保留已知实体、事件、Finding、Evidence、时间边界和未解决问题的版本化快照；重要变化不会静默覆盖旧事实。</p></> : <p className="rounded-xl bg-paper p-6 text-center text-sm text-muted">基线尚未建立。</p>}</CardContent></Card> : null}
      {tab === "scope" ? <Card><CardHeader><p className="section-kicker">Scope control</p><h2 className="mt-1 font-display text-2xl font-semibold">监控范围</h2></CardHeader><CardContent className="space-y-4 pt-5"><div className="rounded-xl border border-line p-4"><p className="font-semibold">监控对象</p><div className="mt-3 flex flex-wrap gap-2">{item.targets.length ? item.targets.map((target) => <Badge key={`${target.target_type}-${target.target_value}`} variant="info">{target.target_type} · {target.target_value}</Badge>) : <span className="text-sm text-muted">由自然语言目标驱动，尚未添加独立对象。</span>}</div></div><div className="grid gap-3 sm:grid-cols-2"><div className="rounded-xl bg-paper p-4"><p className="text-sm font-semibold">重要性规则</p><p className="mt-2 text-sm leading-6 text-muted">{item.importance_rule ?? "高相关、新颖且有独立证据的变化进入发现收件箱。"}</p></div><div className="rounded-xl bg-paper p-4"><p className="text-sm font-semibold">忽略规则</p><p className="mt-2 text-sm leading-6 text-muted">{item.ignored_content_rule ?? "忽略基础介绍、营销转载、重复内容和无变化背景。"}</p></div></div></CardContent></Card> : null}
      {tab === "budget" ? <Card><CardHeader><p className="section-kicker">Bounded resources</p><h2 className="mt-1 font-display text-2xl font-semibold">预算</h2></CardHeader><CardContent className="grid gap-3 pt-5 sm:grid-cols-2 lg:grid-cols-4">{[["每次模型调用", `${item.budget.max_model_calls} 次`], ["每次 Token", item.budget.max_total_tokens.toLocaleString()], ["每次采集", `${item.budget.max_collection_count} 次`], ["每次平台", `${item.budget.max_platforms} 个`], ["最长运行", `${item.budget.max_runtime_seconds} 秒`], ["每日 Token", item.budget.daily_token_budget.toLocaleString()], ["每周运行", `${item.budget.weekly_run_budget} 次`]].map(([label, value]) => <div key={label} className="rounded-xl bg-paper p-4"><p className="text-xs text-muted">{label}</p><p className="mt-1 font-display text-xl font-semibold">{value}</p></div>)}</CardContent></Card> : null}
      {tab === "technical" ? <Card><CardHeader><p className="section-kicker">Technical details</p><h2 className="mt-1 font-display text-2xl font-semibold">可审计运行细节</h2></CardHeader><CardContent className="space-y-3 pt-5"><div className="flex items-start gap-3 rounded-xl border border-line p-4"><Layers3 className="mt-0.5 size-5 shrink-0 text-signal" /><p className="text-sm leading-6 text-muted">原始查询、工具轨迹、平台状态和失败退避保留在运行记录中；本页面只展示对用户有用的摘要。单浏览器 Worker、任务锁和暂停状态由服务端统一协调。</p></div><div className="flex items-start gap-3 rounded-xl border border-warning/25 bg-warning/5 p-4"><ShieldAlert className="mt-0.5 size-5 shrink-0 text-warning-strong" /><p className="text-sm leading-6 text-muted">遇到平台登录、验证码或上游不可用时，系统会明确标记 waiting_login / waiting_platform，不会生成合成变化。</p></div>{runs.data?.[0]?.queries.map((query) => <div key={String(query.id)} className="rounded-xl bg-paper p-4 text-sm"><div className="flex flex-wrap items-center justify-between gap-2"><span className="font-semibold">{unknownText(query.query)}</span><Badge variant="neutral">{unknownText(query.status)}</Badge></div><p className="mt-2 text-xs text-muted">平台 {unknownText(query.platform)} · {unknownText(query.reason)}</p></div>)}</CardContent></Card> : null}
    </div>
  );
}

export function MonitoringMissionsPage() {
  const { missionId } = useParams<{ missionId: string }>();
  const navigate = useNavigate();
  const missions = useMonitoringMissionsQuery();
  const notifications = useMonitoringNotificationsQuery();
  const [creating, setCreating] = useState(false);
  const activeNotifications = useMemo(() => (notifications.data ?? []).filter((item) => item.status === "unread"), [notifications.data]);
  if (missionId) return <MissionDetail missionId={missionId} />;
  return (
    <div className="space-y-7">
      <PageHeader eyebrow="Proactive intelligence · 8E" title="监控任务" description="把长期关注目标交给受控的研究任务：比较上次已知状态与新证据，只把真正值得关注的变化送进发现收件箱。" action={<Button onClick={() => setCreating((value) => !value)}>{creating ? "关闭创建" : "新建监控"} <Plus className="size-4" /></Button>} />
      {activeNotifications.length ? <div className="flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-warning/25 bg-warning/7 p-4"><div className="flex items-center gap-3"><Bell className="size-5 text-warning-strong" /><p className="text-sm font-semibold">有 {activeNotifications.length} 条待处理变化</p></div><Link className="text-sm font-semibold text-signal hover:underline" to={`/monitoring/${encodeURIComponent(activeNotifications[0].mission_id)}`}>查看最新变化 →</Link></div> : null}
      {creating ? <CreateMission onCreated={(mission) => { setCreating(false); void navigate(`/monitoring/${encodeURIComponent(mission.id)}`); }} /> : null}
      {missions.isError ? <ErrorState title="监控任务加载失败" error={missions.error} onRetry={() => void missions.refetch()} /> : <section className="space-y-4"><div className="flex items-center justify-between gap-3"><div><p className="section-kicker">Mission registry</p><h2 className="mt-1 font-display text-2xl font-semibold">你的主动监控</h2></div><span className="text-sm text-muted">{missions.data?.length ?? 0} 个任务</span></div>{missions.isPending ? <div className="grid gap-4 lg:grid-cols-2">{Array.from({ length: 4 }, (_, index) => <div key={index} className="h-52 animate-pulse rounded-2xl bg-paper" />)}</div> : null}{!missions.isPending && !missions.data?.length ? <Card><CardContent className="grid min-h-64 place-items-center p-8 text-center"><div><Activity className="mx-auto size-8 text-signal" /><h3 className="mt-3 font-display text-xl font-semibold">还没有监控任务</h3><p className="mt-2 max-w-md text-sm leading-6 text-muted">从“我希望持续知道什么变化”开始。系统会先生成理解卡，确认后才建立长期监控。</p><Button className="mt-5" onClick={() => setCreating(true)}><Plus className="size-4" />创建第一个监控</Button></div></CardContent></Card> : null}<div className="grid gap-4 lg:grid-cols-2">{missions.data?.map((mission) => missionCard(mission, (id) => void navigate(`/monitoring/${encodeURIComponent(id)}`)))}</div></section>}
      <Card className="border-dashed bg-paper/45"><CardContent className="flex flex-wrap items-start gap-3 p-5"><RotateCcw className="mt-0.5 size-5 shrink-0 text-signal" /><div><p className="font-semibold">监控是变化管理，不是抓取数量</p><p className="mt-1 text-sm leading-6 text-muted">每次运行都会记录基线、来源独立性、转载合并、反向证据和资源使用。没有真实变化时，结果会明确显示 no_meaningful_change。</p></div></CardContent></Card>
    </div>
  );
}
