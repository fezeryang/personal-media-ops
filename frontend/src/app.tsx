import { lazy, Suspense } from "react";
import { Navigate, Route, Routes, useLocation } from "react-router";

import { AppShell } from "./components/app-shell";
import { LoginPage } from "./pages/login-page";
import { useAuth } from "./features/auth/auth-context";

const AiModelCenterPage = lazy(() => import("./pages/ai-model-center-page").then((module) => ({ default: module.AiModelCenterPage })));
const CapabilitiesPage = lazy(() => import("./pages/capabilities-page").then((module) => ({ default: module.CapabilitiesPage })));
const CreatorWatchPage = lazy(() => import("./pages/creator-watch-page").then((module) => ({ default: module.CreatorWatchPage })));
const DiscoveryInboxPage = lazy(() => import("./pages/discovery-inbox-page").then((module) => ({ default: module.DiscoveryInboxPage })));
const IntegrationsPage = lazy(() => import("./pages/integrations-page").then((module) => ({ default: module.IntegrationsPage })));
const LibraryContentPage = lazy(() => import("./pages/library-content-page").then((module) => ({ default: module.LibraryContentPage })));
const LibraryCreatorPage = lazy(() => import("./pages/library-creator-page").then((module) => ({ default: module.LibraryCreatorPage })));
const MemoryEvidencePage = lazy(() => import("./pages/memory-evidence-page").then((module) => ({ default: module.MemoryEvidencePage })));
const OverviewPage = lazy(() => import("./pages/overview-page").then((module) => ({ default: module.OverviewPage })));
const ResearchSpacesPage = lazy(() => import("./pages/research-spaces-page").then((module) => ({ default: module.ResearchSpacesPage })));
const ResearchTasksPage = lazy(() => import("./pages/research-tasks-page").then((module) => ({ default: module.ResearchTasksPage })));
const SubscriptionsPage = lazy(() => import("./pages/subscriptions-page").then((module) => ({ default: module.SubscriptionsPage })));
const TaskDetailPage = lazy(() => import("./pages/task-detail-page").then((module) => ({ default: module.TaskDetailPage })));
const TasksPage = lazy(() => import("./pages/tasks-page").then((module) => ({ default: module.TasksPage })));
const ToolsPage = lazy(() => import("./pages/tools-page").then((module) => ({ default: module.ToolsPage })));
const TrendsPage = lazy(() => import("./pages/trends-page").then((module) => ({ default: module.TrendsPage })));
const SettingsPage = lazy(() => import("./pages/settings-page").then((module) => ({ default: module.SettingsPage })));

function RouteLoading() {
  return <div className="grid min-h-80 place-items-center text-sm text-muted">正在打开工作台…</div>;
}

function ProtectedShell() {
  const auth = useAuth();
  const location = useLocation();
  if (auth.pending) {
    return <div className="grid min-h-screen place-items-center bg-canvas text-sm text-muted">正在恢复安全会话…</div>;
  }
  if (!auth.session?.authenticated) {
    return <Navigate to="/login" state={{ from: `${location.pathname}${location.search}` }} replace />;
  }
  return <Suspense fallback={<RouteLoading />}><AppShell /></Suspense>;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<Navigate to="/research" replace />} />

        <Route path="research" element={<ResearchTasksPage />} />
        <Route path="research/tasks" element={<Navigate to="/research" replace />} />
        <Route path="research/tasks/:taskId" element={<Navigate to="/research" replace />} />
        <Route path="discoveries" element={<DiscoveryInboxPage />} />
        <Route path="discoveries/:candidateId" element={<DiscoveryInboxPage />} />
        <Route path="spaces" element={<ResearchSpacesPage />} />
        <Route path="spaces/:spaceId" element={<ResearchSpacesPage />} />
        <Route path="memory" element={<MemoryEvidencePage />} />
        <Route path="memory/contents/:contentId" element={<LibraryContentPage />} />
        <Route path="memory/creators/:creatorId" element={<LibraryCreatorPage />} />
        <Route path="tools" element={<ToolsPage />} />
        <Route path="tools/overview" element={<OverviewPage />} />
        <Route path="tools/crawls" element={<TasksPage />} />
        <Route path="tools/crawls/:taskId" element={<TaskDetailPage />} />
        <Route path="tools/capabilities" element={<CapabilitiesPage />} />
        <Route path="tools/legacy-trends" element={<TrendsPage />} />
        <Route path="tools/legacy-automation/subscriptions" element={<SubscriptionsPage />} />
        <Route path="tools/legacy-automation/creators" element={<CreatorWatchPage />} />
        <Route path="settings" element={<SettingsPage />} />
        <Route path="settings/models" element={<AiModelCenterPage />} />
        <Route path="settings/integrations" element={<IntegrationsPage />} />
        <Route path="settings/security" element={<SettingsPage />} />

        {/* Compatibility redirects keep old bookmarks from opening legacy modules as primary surfaces. */}
        <Route path="today" element={<Navigate to="/discoveries" replace />} />
        <Route path="subscriptions" element={<Navigate to="/tools/legacy-automation/subscriptions" replace />} />
        <Route path="trends" element={<Navigate to="/tools/legacy-trends" replace />} />
        <Route path="creators" element={<Navigate to="/tools/legacy-automation/creators" replace />} />
        <Route path="collections" element={<Navigate to="/spaces" replace />} />
        <Route path="integrations" element={<Navigate to="/settings/integrations" replace />} />
        <Route path="ai/models" element={<Navigate to="/settings/models" replace />} />
        <Route path="system" element={<Navigate to="/tools/capabilities" replace />} />
        <Route path="crawler/tasks" element={<Navigate to="/tools/crawls" replace />} />
        <Route path="crawler/tasks/:taskId" element={<Navigate to="/tools/crawls" replace />} />
        <Route path="crawler/capabilities" element={<Navigate to="/tools/capabilities" replace />} />
        <Route path="library" element={<Navigate to="/memory" replace />} />
        <Route path="library/contents/:contentId" element={<LibraryContentPage />} />
        <Route path="library/creators/:creatorId" element={<LibraryCreatorPage />} />
        <Route path="*" element={<Navigate to="/research" replace />} />
      </Route>
    </Routes>
  );
}
