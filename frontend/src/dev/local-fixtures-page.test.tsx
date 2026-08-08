import { render, screen } from "@testing-library/react";

import { LocalFixturesPage } from "./local-fixtures-page";

describe("LocalFixturesPage", () => {
  it("renders the major 8D and 8E lifecycle and evidence states without an API", () => {
    render(<LocalFixturesPage />);

    expect(screen.getByRole("heading", { name: "8E AI 行为与主动监控状态覆盖" })).toBeInTheDocument();
    expect(screen.getByText("预算触发")).toBeInTheDocument();
    expect(screen.getByText("反向证据：")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "证据、Finding 与反例" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "记忆、事件与下一步" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "监控任务列表、理解卡与注意力状态" })).toBeInTheDocument();
    expect(screen.getByText(/no_meaningful_change/)).toBeInTheDocument();
    expect(screen.getByText("等待 Owner 确认")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: /证据 → 信号 → 机会/ })).toBeInTheDocument();
    expect(screen.getByText("Content Opportunity", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("Action & Outcome", { exact: true })).toBeInTheDocument();
    expect(screen.getByText("No Opportunity", { exact: true })).toBeInTheDocument();
  });
});
