import {
  getSubscription,
  listSubscriptions,
  runSubscription,
  saveSubscription,
  setSubscriptionEnabled,
  type SubscriptionInput,
} from "./subscriptions";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const subscription = {
  id: "subscription/1",
  name: "AI Agent 每日观察",
  query: "AI Agent",
  platforms: [{ platform: "bili", requested_count: 3 }],
  enabled: false,
  schedule_type: "manual",
  schedule_config: {},
  timezone: "Asia/Shanghai",
  last_run_at: null,
  next_run_at: null,
  last_success_at: null,
  consecutive_failures: 0,
  last_error: null,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
};

const run = {
  id: "run-1",
  subscription_id: "subscription/1",
  scheduled_for: "2026-07-28T00:00:00Z",
  trigger: "manual",
  status: "queued",
  started_at: null,
  finished_at: null,
  new_content_count: 0,
  existing_content_count: 0,
  changed_content_count: 0,
  error_summary: null,
  created_at: "2026-07-28T00:00:00Z",
  platform_results: [],
};

const input: SubscriptionInput = {
  name: subscription.name,
  query: subscription.query,
  platforms: subscription.platforms,
  enabled: false,
  schedule_type: "manual",
  schedule_config: {},
  timezone: "Asia/Shanghai",
};

describe("subscriptions API", () => {
  it("covers list, detail, create, edit, pause, resume, and manual run", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([subscription]))
      .mockResolvedValueOnce(
        jsonResponse({ ...subscription, runs: [run] }),
      )
      .mockResolvedValueOnce(jsonResponse(subscription))
      .mockResolvedValueOnce(jsonResponse(subscription))
      .mockResolvedValueOnce(jsonResponse(subscription))
      .mockResolvedValueOnce(jsonResponse({ ...subscription, enabled: true }))
      .mockResolvedValueOnce(jsonResponse(run));

    await expect(listSubscriptions()).resolves.toEqual([subscription]);
    await expect(getSubscription("subscription/1")).resolves.toMatchObject({
      runs: [run],
    });
    await expect(saveSubscription(input)).resolves.toEqual(subscription);
    await expect(
      saveSubscription(input, "subscription/1"),
    ).resolves.toEqual(subscription);
    await expect(
      setSubscriptionEnabled("subscription/1", false),
    ).resolves.toEqual(subscription);
    await expect(
      setSubscriptionEnabled("subscription/1", true),
    ).resolves.toMatchObject({ enabled: true });
    await expect(runSubscription("subscription/1")).resolves.toEqual(run);

    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/subscriptions/subscription%2F1",
    );
    expect(fetchMock.mock.calls[2]?.[1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[3]?.[1]?.method).toBe("PUT");
    expect(fetchMock.mock.calls[4]?.[0]).toContain("/pause");
    expect(fetchMock.mock.calls[5]?.[0]).toContain("/resume");
  });
});
