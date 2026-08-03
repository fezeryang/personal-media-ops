import { render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes, useLocation } from "react-router";

import { LegacyTaskDetailRedirect } from "./app";

function LocationProbe() {
  const location = useLocation();
  return <output aria-label="当前路由">{location.pathname}</output>;
}

describe("App compatibility routes", () => {
  it("keeps legacy crawler task links in the crawler tool and preserves the id", async () => {
    render(
      <MemoryRouter initialEntries={["/tasks/task-42"]}>
        <Routes>
          <Route path="/tasks/:taskId" element={<LegacyTaskDetailRedirect />} />
        </Routes>
        <LocationProbe />
      </MemoryRouter>,
    );

    await waitFor(() =>
      expect(screen.getByLabelText("当前路由")).toHaveTextContent("/tools/crawls/task-42"),
    );
  });
});
