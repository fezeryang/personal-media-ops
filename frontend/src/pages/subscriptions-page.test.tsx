import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as subscriptionApi from "../api/subscriptions";
import { SubscriptionsPage } from "./subscriptions-page";

vi.mock("../features/crawler/hooks/use-crawler-queries", () => ({
  useCrawlerCapabilitiesQuery: () => ({
    data: {
      max_concurrent_tasks: 1,
      platforms: [
        {
          platform: "bili",
          display_name: "B站",
          enabled: true,
          modes: [
            {
              mode: "search",
              enabled: true,
              status: "production_verified",
            },
          ],
        },
      ],
    },
  }),
}));

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
      <SubscriptionsPage />
    </QueryClientProvider>,
  );
}

describe("SubscriptionsPage", () => {
  it("edits, manually runs, and resumes a subscription", async () => {
    vi.spyOn(subscriptionApi, "listSubscriptions").mockResolvedValue([
      subscription,
    ]);
    const save = vi
      .spyOn(subscriptionApi, "saveSubscription")
      .mockResolvedValue(subscription);
    const run = vi
      .spyOn(subscriptionApi, "runSubscription")
      .mockResolvedValue({
        id: "run-1",
        subscription_id: subscription.id,
        scheduled_for: "2026-07-28T01:00:00Z",
        trigger: "manual",
        status: "queued",
        started_at: null,
        finished_at: null,
        new_content_count: 0,
        existing_content_count: 0,
        changed_content_count: 0,
        error_summary: null,
        created_at: "2026-07-28T01:00:00Z",
        platform_results: [],
      });
    const toggle = vi
      .spyOn(subscriptionApi, "setSubscriptionEnabled")
      .mockResolvedValue({ ...subscription, enabled: true });
    const user = userEvent.setup();
    renderPage();

    expect(
      await screen.findByText("AI Agent 每日观察"),
    ).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /编辑/ }));
    const name = screen.getByLabelText("名称");
    await user.clear(name);
    await user.type(name, "AI Agent 追踪");
    await user.click(screen.getByRole("button", { name: "保存订阅" }));
    await waitFor(() =>
      expect(save).toHaveBeenCalledWith(
        expect.objectContaining({ name: "AI Agent 追踪" }),
        "subscription-1",
      ),
    );

    await user.click(screen.getByRole("button", { name: /手动执行/ }));
    await waitFor(() => expect(run).toHaveBeenCalled());
    expect(run.mock.calls[0]?.[0]).toBe("subscription-1");
    await user.click(screen.getByRole("button", { name: /恢复/ }));
    await waitFor(() =>
      expect(toggle).toHaveBeenCalledWith("subscription-1", true),
    );
  });
});
