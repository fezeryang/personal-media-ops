import {
  createWatch,
  listWatches,
  runWatch,
  setWatchEnabled,
} from "./watchlist";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const watch = {
  id: "watch/1",
  creator_id: "creator-1",
  platform: "bili",
  creator_name: "Creator",
  enabled: false,
  check_frequency: "daily",
  requested_count: 3,
  timezone: "Asia/Shanghai",
  last_checked_at: null,
  next_check_at: null,
  last_success_at: null,
  consecutive_failures: 0,
  last_error: null,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
  runs: [],
};

const run = {
  id: "watch-run-1",
  watch_id: "watch/1",
  scheduled_for: "2026-07-28T00:00:00Z",
  trigger: "manual",
  task_id: "task-1",
  status: "queued",
  started_at: null,
  finished_at: null,
  new_content_count: 0,
  existing_content_count: 0,
  changed_content_count: 0,
  error_summary: null,
  created_at: "2026-07-28T00:00:00Z",
};

describe("watchlist API", () => {
  it("covers create, pause, resume, list, and manual execution", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([watch]))
      .mockResolvedValueOnce(jsonResponse(watch))
      .mockResolvedValueOnce(jsonResponse(watch))
      .mockResolvedValueOnce(jsonResponse({ ...watch, enabled: true }))
      .mockResolvedValueOnce(jsonResponse(run));

    await expect(listWatches()).resolves.toEqual([watch]);
    await expect(
      createWatch({
        creator_id: "creator-1",
        enabled: false,
        check_frequency: "daily",
        requested_count: 3,
        timezone: "Asia/Shanghai",
      }),
    ).resolves.toEqual(watch);
    await expect(setWatchEnabled("watch/1", false)).resolves.toEqual(watch);
    await expect(setWatchEnabled("watch/1", true)).resolves.toMatchObject({
      enabled: true,
    });
    await expect(runWatch("watch/1")).resolves.toEqual(run);

    expect(fetchMock.mock.calls[2]?.[0]).toBe("/api/watchlist/watch%2F1");
    expect(fetchMock.mock.calls[2]?.[1]?.method).toBe("PATCH");
    expect(fetchMock.mock.calls[4]?.[0]).toBe(
      "/api/watchlist/watch%2F1/run",
    );
  });
});
