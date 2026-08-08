import {
  Activity,
  Database,
  FolderKanban,
  LogOut,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Radar,
  SearchCheck,
  Settings,
  Sparkles,
  Wrench,
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { NavLink, Outlet, useLocation } from "react-router";

import { useAuth } from "../features/auth/auth-context";
import { useHealthQuery } from "../features/crawler/hooks/use-crawler-queries";
import { useResearchPreferencesQuery } from "../features/research/hooks/use-discovery-queries";
import { cn } from "../lib/utils";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { SideDrawer } from "./ui/side-drawer";

const SIDEBAR_STORAGE_KEY = "mediaops.sidebar.collapsed";

interface NavigationItem {
  label: string;
  to: string;
  icon: typeof SearchCheck;
  end: boolean;
}

function readSidebarPreference(): boolean {
  try {
    return window.localStorage.getItem(SIDEBAR_STORAGE_KEY) === "true";
  } catch {
    return false;
  }
}

export function AppShell() {
  const health = useHealthQuery();
  const preferences = useResearchPreferencesQuery();
  const auth = useAuth();
  const location = useLocation();
  const [loggingOut, setLoggingOut] = useState(false);
  const [sidebarCollapsed, setSidebarCollapsed] = useState(readSidebarPreference);
  const [mobileOpen, setMobileOpen] = useState(false);
  const connected = health.data?.status === "ok";
  const flags = preferences.data?.feature_flags;
  const navigation = useMemo<NavigationItem[]>(
    () => [
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
    ],
    [flags?.discovery_inbox_enabled, flags?.research_primary_enabled],
  );
  const currentPage = useMemo(
    () => navigation.find((item) => location.pathname === item.to || (!item.end && location.pathname.startsWith(`${item.to}/`)))?.label ?? "AI 研究",
    [location.pathname, navigation],
  );

  useEffect(() => {
    try {
      window.localStorage.setItem(SIDEBAR_STORAGE_KEY, String(sidebarCollapsed));
    } catch {
      // Local storage is a convenience only; it must not affect the layout.
    }
  }, [sidebarCollapsed]);

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
      <aside
        className={cn(
          "fixed inset-y-0 left-0 z-30 hidden flex-col border-r border-[#d8e4e0] bg-[#edf3f0] py-5 transition-[width,padding] duration-200 lg:flex",
          sidebarCollapsed ? "w-[76px] px-3" : "w-[272px] px-4",
        )}
        data-sidebar-collapsed={sidebarCollapsed}
      >
        <div className={cn("flex items-center gap-3", sidebarCollapsed ? "justify-center" : "px-2")}>
          <div className="grid size-11 shrink-0 place-items-center rounded-2xl bg-[#184b4b] text-white shadow-sm">
            <Radar className="size-5" />
          </div>
          {!sidebarCollapsed ? (
            <div className="min-w-0">
              <p className="truncate font-display text-sm font-semibold tracking-wide">Personal Media Ops</p>
              <p className="mt-0.5 text-[10px] tracking-[0.15em] text-[#5d7975]">PERSONAL RESEARCH</p>
            </div>
          ) : null}
        </div>

        <nav className="mt-8 space-y-1" aria-label="主导航">
          {navigation.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.end}
              onClick={() => setMobileOpen(false)}
              title={sidebarCollapsed ? item.label : undefined}
              className={({ isActive }) => cn(
                "group flex items-center gap-3 rounded-xl py-2.5 text-sm font-medium transition-[background,color,box-shadow] duration-150",
                sidebarCollapsed ? "justify-center px-2" : "px-3",
                isActive ? "bg-white text-[#174b4b] shadow-[0_1px_3px_rgba(25,60,56,0.08)]" : "text-[#526a68] hover:bg-white/65 hover:text-ink",
              )}
            >
              <item.icon className="size-4 shrink-0" />
              {!sidebarCollapsed ? <><span className="min-w-0 flex-1 truncate">{item.label}</span><span className="size-1.5 rounded-full bg-current opacity-20" aria-hidden="true" /></> : null}
            </NavLink>
          ))}
        </nav>

        <div className={cn("mt-auto rounded-2xl border border-[#d3e1dc] bg-white/70", sidebarCollapsed ? "p-2" : "p-3")}>
          <div className="flex items-center justify-between gap-2">
            {!sidebarCollapsed ? <span className="text-xs text-muted">系统连接</span> : null}
            <Badge variant={connected ? "success" : "danger"} title={connected ? "系统在线" : "系统异常"}>{connected ? "在线" : "异常"}</Badge>
          </div>
          {!sidebarCollapsed ? <p className="mt-3 truncate text-xs font-semibold">{auth.session?.user?.username}</p> : null}
          <Button className={cn("mt-2 w-full", !sidebarCollapsed && "justify-start")} variant="ghost" size="sm" aria-label="退出登录" title="退出登录" disabled={loggingOut} onClick={() => void logout()}>
            <LogOut className="size-3.5" />
            {!sidebarCollapsed ? (loggingOut ? "正在退出…" : "退出登录") : null}
          </Button>
          <Button className={cn("mt-2 w-full", !sidebarCollapsed && "justify-start")} variant="ghost" size="sm" aria-label={sidebarCollapsed ? "展开侧栏" : "收起侧栏"} aria-expanded={!sidebarCollapsed} title={sidebarCollapsed ? "展开侧栏" : "收起侧栏"} onClick={() => setSidebarCollapsed((value) => !value)}>
            {sidebarCollapsed ? <PanelLeftOpen className="size-4" /> : <PanelLeftClose className="size-4" />}
            {!sidebarCollapsed ? "收起侧栏" : null}
          </Button>
        </div>
      </aside>

      <div className={cn("transition-[padding] duration-200", sidebarCollapsed ? "lg:pl-[76px]" : "lg:pl-[272px]")}>
        <header className="sticky top-0 z-20 border-b border-line bg-canvas/94 px-4 py-3 backdrop-blur-lg lg:hidden">
          <div className="flex items-center justify-between gap-3">
            <div className="flex min-w-0 items-center gap-2">
              <div className="grid size-9 shrink-0 place-items-center rounded-xl bg-[#184b4b] text-white"><Radar className="size-4" /></div>
              <div className="min-w-0"><p className="truncate text-sm font-semibold">{currentPage}</p><p className="text-[10px] text-muted">Personal Research</p></div>
            </div>
            <div className="flex shrink-0 items-center gap-2"><Badge variant={connected ? "success" : "danger"}>{connected ? "在线" : "离线"}</Badge><Button variant="secondary" size="icon" aria-label="打开导航菜单" onClick={() => setMobileOpen(true)}><Menu className="size-4" /></Button></div>
          </div>
        </header>

        <SideDrawer open={mobileOpen} onOpenChange={setMobileOpen} title="导航" description="选择一个工作台区域。">
          <nav className="space-y-1" aria-label="移动端主导航">
            {navigation.map((item) => <NavLink key={item.to} to={item.to} end={item.end} onClick={() => setMobileOpen(false)} className={({ isActive }) => cn("flex items-center gap-3 rounded-xl px-3 py-3 text-sm font-semibold", isActive ? "bg-signal/10 text-signal-strong" : "text-muted hover:bg-paper hover:text-ink")}><item.icon className="size-4" />{item.label}</NavLink>)}
          </nav>
          <div className="mt-6 border-t border-line pt-5"><Button className="w-full justify-start" variant="ghost" disabled={loggingOut} onClick={() => void logout()}><LogOut className="size-4" />{loggingOut ? "正在退出…" : "退出登录"}</Button></div>
        </SideDrawer>

        <main className="mx-auto min-h-screen max-w-[1480px] px-4 py-5 sm:px-6 sm:py-7 xl:px-10">
          <Outlet />
        </main>
      </div>
    </div>
  );
}
