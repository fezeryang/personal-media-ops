import {
  Activity,
  Database,
  FolderKanban,
  ChevronRight,
  LogOut,
  Radar,
  SearchCheck,
  Sparkles,
  Settings,
  Wrench,
} from "lucide-react";
import { useState } from "react";
import { NavLink, Outlet } from "react-router";

import { useAuth } from "../features/auth/auth-context";
import { useHealthQuery } from "../features/crawler/hooks/use-crawler-queries";
import { useResearchPreferencesQuery } from "../features/research/hooks/use-discovery-queries";
import { cn } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";

export function AppShell() {
  const health = useHealthQuery();
  const preferences = useResearchPreferencesQuery();
  const auth = useAuth();
  const [loggingOut, setLoggingOut] = useState(false);
  const connected = health.data?.status === "ok";
  const flags = preferences.data?.feature_flags;
  const navigation = [
    ...(flags?.research_primary_enabled !== false
      ? [{ label: "AI 研究", to: "/research", icon: SearchCheck, end: true }]
      : []),
    ...(flags?.discovery_inbox_enabled !== false
      ? [{ label: "发现收件箱", to: "/discoveries", icon: Sparkles, end: false }]
      : []),
    { label: "研究空间", to: "/spaces", icon: FolderKanban, end: false },
    { label: "记忆与证据", to: "/memory", icon: Database, end: false },
    { label: "监控任务", to: "/monitoring", icon: Activity, end: false },
    { label: "工具中心", to: "/tools", icon: Wrench, end: false },
    { label: "设置", to: "/settings", icon: Settings, end: false },
  ];

  async function logout() {
    setLoggingOut(true);
    try {
      await auth.logout();
    } finally {
      setLoggingOut(false);
    }
  }

  return (
    <div className="min-h-screen bg-canvas text-ink">
      <aside className="fixed inset-y-0 left-0 z-30 hidden w-[272px] flex-col border-r border-[#d8e4e0] bg-[#edf3f0] px-4 py-5 lg:flex">
        <div className="flex items-center gap-3 px-2">
          <div className="grid size-11 place-items-center rounded-2xl bg-[#184b4b] text-white shadow-sm">
            <Radar className="size-5" />
          </div>
          <div>
            <p className="font-display text-sm font-semibold tracking-wide">
              Personal Media Ops
            </p>
            <p className="mt-0.5 text-[10px] tracking-[0.15em] text-[#5d7975]">
              INTELLIGENCE LAB
            </p>
          </div>
        </div>

        <nav className="mt-8 space-y-1" aria-label="主导航">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              className={({ isActive }) =>
                cn(
                  "group flex items-center gap-3 rounded-xl px-3 py-2.5 text-sm font-medium transition-[background,color,box-shadow] duration-150",
                  isActive
                    ? "bg-white text-[#174b4b] shadow-[0_1px_3px_rgba(25,60,56,0.08)]"
                    : "text-[#526a68] hover:bg-white/65 hover:text-ink",
                )
              }
            >
              <item.icon className="size-4" />
              {item.label}
              <ChevronRight className="ml-auto size-3.5 opacity-30" />
            </NavLink>
          ))}
        </nav>

        <div className="mt-auto rounded-2xl border border-[#d3e1dc] bg-white/70 p-3">
          <div className="flex items-center justify-between">
            <span className="text-xs text-muted">系统连接</span>
            <Badge variant={connected ? "success" : "danger"}>
              {connected ? "在线" : "异常"}
            </Badge>
          </div>
          <p className="mt-3 truncate text-xs font-semibold">
            {auth.session?.user?.username}
          </p>
          <Button
            className="mt-2 w-full justify-start"
            variant="ghost"
            size="sm"
            disabled={loggingOut}
            onClick={() => void logout()}
          >
            <LogOut className="size-3.5" />
            {loggingOut ? "正在退出…" : "退出登录"}
          </Button>
        </div>
      </aside>

      <div className="lg:pl-[272px]">
        <header className="sticky top-0 z-20 border-b border-line bg-canvas/94 px-4 py-3 backdrop-blur-lg lg:hidden">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <div className="grid size-9 place-items-center rounded-xl bg-[#184b4b] text-white">
                <Radar className="size-4" />
              </div>
              <div>
                <p className="text-sm font-semibold">Personal Media Ops</p>
                <p className="text-[10px] text-muted">个人互联网情报工作台</p>
              </div>
            </div>
            <Badge variant={connected ? "success" : "danger"}>
              {connected ? "在线" : "离线"}
            </Badge>
          </div>
          <nav
            className="-mx-4 mt-3 flex gap-2 overflow-x-auto px-4 pb-1"
            aria-label="移动端主导航"
          >
            {navigation.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={({ isActive }) =>
                  cn(
                    "shrink-0 rounded-full border px-3 py-1.5 text-xs font-semibold",
                    isActive
                      ? "border-[#184b4b] bg-[#184b4b] text-white"
                      : "border-line bg-white text-muted",
                  )
                }
              >
                {item.label}
              </NavLink>
            ))}
          </nav>
        </header>

        <main className="mx-auto min-h-screen max-w-[1480px] px-4 py-7 sm:px-6 sm:py-9 xl:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
