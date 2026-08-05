import { render, screen } from "@testing-library/react";

import { LocalFixturesPage } from "./local-fixtures-page";

describe("LocalFixturesPage", () => {
  it("renders the major 8D lifecycle and evidence states without an API", () => {
    render(<LocalFixturesPage />);

    expect(screen.getByRole("heading", { name: "8D 研究与发现状态覆盖" })).toBeInTheDocument();
    expect(screen.getByText("预算触发")).toBeInTheDocument();
    expect(screen.getByText("反向证据：")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "证据、Finding 与反例" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "记忆、事件与下一步" })).toBeInTheDocument();
  });
});
