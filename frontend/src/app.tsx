import { Navigate, Route, Routes } from "react-router";

import { AppShell } from "./components/app-shell";
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
        <Route path="*" element={<Navigate to="/" replace />} />
      </Route>
    </Routes>
  );
}
