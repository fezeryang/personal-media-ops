import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";

import { LocalUxFixturesPage } from "./local-ux-fixtures-page";

describe("LocalUxFixturesPage", () => {
  it("provides a dense, searchable, collapsible research surface fixture", async () => {
    const user = userEvent.setup();
    render(<MemoryRouter initialEntries={["/__local/ux/research"]}><LocalUxFixturesPage /></MemoryRouter>);

    expect(screen.getByRole("heading", { name: "核心页面响应式验收" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "AI 研究" })).toBeInTheDocument();
    expect(screen.getAllByRole("button").filter((button) => button.textContent?.includes("研究任务")).length).toBeGreaterThan(20);
    expect(screen.getByRole("searchbox", { name: "搜索" })).toBeInTheDocument();
    expect(screen.getByText(/loading \/ empty \/ error/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "收起研究任务列表" }));
    expect(screen.queryByRole("button", { name: /研究任务 01 · 个人 AI 工作流/ })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: "显示研究任务列表" })).toBeInTheDocument();
  });
});
