import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

const mocks = vi.hoisted(() => ({
  logout: vi.fn().mockResolvedValue(undefined),
}));

vi.mock("../features/auth/auth-context", () => ({
  useAuth: () => ({
    session: {
      authenticated: true,
      user: { id: "owner-1", username: "owner" },
      csrf_token: "csrf",
    },
    pending: false,
    login: vi.fn(),
    logout: mocks.logout,
  }),
}));

vi.mock("../features/crawler/hooks/use-crawler-queries", () => ({
  useHealthQuery: () => ({
    data: { status: "ok", version: "0.1.0" },
  }),
}));

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  it("keeps all intelligence navigation reachable at 390px and logs out", async () => {
    Object.defineProperty(window, "innerWidth", {
      configurable: true,
      value: 390,
    });
    const user = userEvent.setup();
    const { container } = render(
      <MemoryRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<p>content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const mobile = screen.getByRole("navigation", {
      name: "移动端主导航",
    });
    expect(mobile).toHaveClass("overflow-x-auto");
    expect(mobile.querySelectorAll("a")).toHaveLength(12);
    expect(container).toHaveTextContent("今日情报");
    expect(container).toHaveTextContent("AI 模型中心");
    expect(container).toHaveTextContent("AI 研究任务");
    await user.click(screen.getByRole("button", { name: "退出登录" }));
    expect(mocks.logout).toHaveBeenCalledOnce();
  });
});
