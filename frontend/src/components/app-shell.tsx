import {
  Activity,
  BookOpen,
  Bot,
  ChevronRight,
  Compass,
  Database,
  Eye,
  LayoutDashboard,
  Radar,
} from "lucide-react";
import { NavLink, Outlet } from "react-router";

import { useHealthQuery } from "../features/crawler/hooks/use-crawler-queries";
import { cn } from "../lib/utils";
import { Badge } from "./ui/badge";

const enabledNavigation = [
  { label: "总览", to: "/", icon: LayoutDashboard, end: true },
  { label: "采集中心", to: "/crawler/tasks", icon: Radar, end: false },
  { label: "内容资料库", to: "/library", icon: Database, end: false },
  {
    label: "能力矩阵",
    to: "/crawler/capabilities",
    icon: Activity,
    end: false,
  },
];

const upcomingNavigation = [
  { label: "今日情报", icon: Compass },
  { label: "选题与创作", icon: BookOpen },
  { label: "账号观察", icon: Eye },
  { label: "Agent 状态", icon: Bot },
];

export function AppShell() {
  const health = useHealthQuery();
  const connected = health.data?.status === "ok";

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 flex-col border-r border-white/8 bg-sidebar px-4 py-5 text-white lg:flex">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-10 place-items-center rounded-xl border border-white/15 bg-white/8 font-display text-sm font-bold tracking-wider">
            PM
          </div>
          <div>
            <p className="font-display text-sm font-semibold tracking-wide">
              Personal Media Ops
            </p>
            <p className="mt-0.5 text-[10px] tracking-[0.14em] text-slate-400">
              INTELLIGENCE DESK
            </p>
          </div>
        </div>

        <nav className="mt-9 space-y-1" aria-label="主导航">
          {enabledNavigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-colors",
                  isActive
                    ? "bg-white text-sidebar shadow-sm"
                    : "text-slate-400 hover:bg-white/6 hover:text-white",
                )
              }
            >
              <item.icon className="size-4" />
              {item.label}
              <ChevronRight className="ml-auto size-3.5 opacity-40" />
            </NavLink>
          ))}
        </nav>

        <div className="mt-8 border-t border-white/8 pt-6">
          <p className="px-3 text-[10px] font-bold uppercase tracking-[0.18em] text-slate-500">
            即将开放
          </p>
          <div className="mt-2 space-y-1">
            {upcomingNavigation.map((item) => (
              <div
                key={item.label}
                className="flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm text-slate-600"
                aria-disabled="true"
              >
                <item.icon className="size-4" />
                {item.label}
              </div>
            ))}
          </div>
        </div>

        <div className="mt-auto rounded-xl border border-white/8 bg-white/[0.04] p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-slate-400">API 连接</span>
            <span
              className={cn(
                "size-2 rounded-full",
                connected
                  ? "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,0.5)]"
                  : "bg-rose-400",
              )}
            />
          </div>
          <p className="mt-2 text-xs font-medium text-slate-200">
            {connected ? "服务在线" : health.isPending ? "正在检查" : "连接异常"}
          </p>
          {health.data ? (
            <p className="mt-1 text-[10px] text-slate-500">
              API v{health.data.version}
            </p>
          ) : null}
        </div>
      </aside>

      <div className="lg:pl-64">
        <header className="sticky top-0 z-20 border-b border-line bg-canvas/92 px-4 py-3 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="grid size-8 place-items-center rounded-lg bg-sidebar text-[11px] font-bold text-white">
                PM
              </div>
              <div>
                <p className="text-sm font-semibold">Personal Media Ops</p>
                <p className="text-[10px] text-muted">个人互联网情报工作台</p>
              </div>
            </div>
            <Badge variant={connected ? "success" : "danger"}>
              <Activity className="size-3" />
              {connected ? "在线" : "离线"}
            </Badge>
          </div>
          <nav className="mt-3 flex gap-2" aria-label="移动端主导航">
            {enabledNavigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "rounded-lg px-3 py-1.5 text-xs font-semibold",
                    isActive
                      ? "bg-ink text-white"
                      : "border border-line bg-white text-muted",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto min-h-screen max-w-[1440px] px-4 py-7 sm:px-6 sm:py-9 xl:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
