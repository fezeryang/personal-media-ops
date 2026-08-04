import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import * as subscriptionApi from "../api/subscriptions";
import { SubscriptionsPage } from "./subscriptions-page";

const subscription: subscriptionApi.Subscription = {
  id: "subscription-1",
  name: "AI Agent 每日观察",
  query: "AI Agent",
  platforms: [{ platform: "bili", requested_count: 2 }],
  enabled: false,
  schedule_type: "daily",
  schedule_config: { time_of_day: "09:00" },
  timezone: "Asia/Shanghai",
  last_run_at: null,
  next_run_at: null,
  last_success_at: null,
  consecutive_failures: 0,
  last_error: null,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
};

function renderPage() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <SubscriptionsPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("SubscriptionsPage", () => {
  it("shows historical subscriptions without exposing write actions", async () => {
    vi.spyOn(subscriptionApi, "listSubscriptions").mockResolvedValue([
      subscription,
    ]);
    renderPage();

    expect(
      await screen.findByText("AI Agent 每日观察"),
    ).toBeInTheDocument();
    expect(screen.getByRole("note")).toHaveTextContent(
      "已停止作为核心产品继续开发",
    );
    expect(
      screen.queryByRole("button", { name: /编辑|手动执行|恢复|暂停/ }),
    ).not.toBeInTheDocument();
    expect(screen.queryByRole("textbox")).not.toBeInTheDocument();
  });
});
