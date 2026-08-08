import { render, screen, waitFor, within } from "@testing-library/react";
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

vi.mock("../features/research/hooks/use-discovery-queries", () => ({
  useResearchPreferencesQuery: () => ({
    data: {
      feature_flags: {
        research_primary_enabled: true,
        discovery_inbox_enabled: true,
      },
    },
  }),
}));

import { AppShell } from "./app-shell";

describe("AppShell", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  it("uses an accessible mobile navigation drawer instead of a horizontal rail", async () => {
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

    expect(screen.getByRole("button", { name: "打开导航菜单" })).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(container).toHaveTextContent("发现收件箱");
    expect(container).toHaveTextContent("记忆与证据");
    expect(container).toHaveTextContent("监控任务");
    expect(container).toHaveTextContent("AI 研究");
    expect(container).not.toHaveTextContent("今日情报");
    expect(container).not.toHaveTextContent("AI 模型中心");
    await user.click(screen.getByRole("button", { name: "打开导航菜单" }));
    const drawer = screen.getByRole("dialog");
    expect(within(drawer).getByRole("navigation", { name: "移动端主导航" })).toBeInTheDocument();
    expect(within(drawer).getAllByRole("link")).toHaveLength(7);
    await user.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "退出登录" }));
    expect(mocks.logout).toHaveBeenCalledOnce();
  });

  it("persists the desktop sidebar collapse state", async () => {
    const user = userEvent.setup();
    render(
      <MemoryRouter>
        <Routes>
          <Route element={<AppShell />}>
            <Route index element={<p>content</p>} />
          </Route>
        </Routes>
      </MemoryRouter>,
    );

    const collapse = screen.getByRole("button", { name: "收起侧栏" });
    expect(collapse).toHaveAttribute("aria-expanded", "true");
    await user.click(collapse);
    expect(screen.getByRole("button", { name: "展开侧栏" })).toHaveAttribute("aria-expanded", "false");
    expect(window.localStorage.getItem("mediaops.sidebar.collapsed")).toBe("true");
  });
});
