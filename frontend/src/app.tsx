import { Navigate, Route, Routes, useLocation } from "react-router";

import { AppShell } from "./components/app-shell";
import { CapabilitiesPage } from "./pages/capabilities-page";
import { LibraryContentPage } from "./pages/library-content-page";
import { LibraryCreatorPage } from "./pages/library-creator-page";
import { LibraryPage } from "./pages/library-page";
import { OverviewPage } from "./pages/overview-page";
import { TaskDetailPage } from "./pages/task-detail-page";
import { TasksPage } from "./pages/tasks-page";
import { LoginPage } from "./pages/login-page";
import { TodayPage } from "./pages/today-page";
import { SubscriptionsPage } from "./pages/subscriptions-page";
import { TrendsPage } from "./pages/trends-page";
import { CreatorWatchPage } from "./pages/creator-watch-page";
import { CollectionsPage } from "./pages/collections-page";
import { IntegrationsPage } from "./pages/integrations-page";
import { AiModelCenterPage } from "./pages/ai-model-center-page";
import { ResearchTasksPage } from "./pages/research-tasks-page";
import { useAuth } from "./features/auth/auth-context";

function ProtectedShell() {
  const auth = useAuth();
  const location = useLocation();
  if (auth.pending) {
    return (
      <div className="grid min-h-screen place-items-center bg-canvas text-sm text-muted">
        正在恢复安全会话…
      </div>
    );
  }
  if (!auth.session?.authenticated) {
    return (
      <Navigate
        to="/login"
        state={{ from: `${location.pathname}${location.search}` }}
        replace
      />
    );
  }
  return <AppShell />;
}

export function App() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route element={<ProtectedShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="today" element={<TodayPage />} />
        <Route path="subscriptions" element={<SubscriptionsPage />} />
        <Route path="trends" element={<TrendsPage />} />
        <Route path="creators" element={<CreatorWatchPage />} />
        <Route path="collections" element={<CollectionsPage />} />
        <Route path="integrations" element={<IntegrationsPage />} />
        <Route path="ai/models" element={<AiModelCenterPage />} />
        <Route path="research/tasks" element={<ResearchTasksPage />} />
        <Route path="system" element={<CapabilitiesPage />} />
        <Route path="crawler/tasks" element={<TasksPage />} />
        <Route path="crawler/tasks/:taskId" element={<TaskDetailPage />} />
        <Route
          path="crawler/capabilities"
          element={<Navigate to="/system" replace />}
        />
        <Route path="library" element={<LibraryPage />} />
        <Route
          path="library/contents/:contentId"
          element={<LibraryContentPage />}
        />
        <Route
          path="library/creators/:creatorId"
          element={<LibraryCreatorPage />}
        />
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
