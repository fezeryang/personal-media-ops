import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "./components/app-shell";
import { CapabilitiesPage } from "./pages/capabilities-page";
import { LibraryContentPage } from "./pages/library-content-page";
import { LibraryCreatorPage } from "./pages/library-creator-page";
import { LibraryPage } from "./pages/library-page";
import { OverviewPage } from "./pages/overview-page";
import { TaskDetailPage } from "./pages/task-detail-page";
import { TasksPage } from "./pages/tasks-page";

export function App() {
  return (
    <Routes>
      <Route element={<AppShell />}>
        <Route index element={<OverviewPage />} />
        <Route path="crawler/tasks" element={<TasksPage />} />
        <Route path="crawler/tasks/:taskId" element={<TaskDetailPage />} />
        <Route path="crawler/capabilities" element={<CapabilitiesPage />} />
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
