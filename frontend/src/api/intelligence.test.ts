import {
  generateBrief,
  generateTrends,
  getBriefSchedule,
  getLatestBrief,
  listTrends,
  setBriefSchedule,
} from "./intelligence";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

const trend = {
  id: "trend-1",
  topic: "AI Agent",
  window_start: "2026-07-27T00:00:00Z",
  window_end: "2026-07-28T00:00:00Z",
  score: 61,
  volume_score: 70,
  velocity_score: 60,
  cross_platform_score: 50,
  engagement_score: 40,
  platforms: ["bili", "xhs"],
  content_ids: ["content-1"],
  explanation: "rules-v1 deterministic score",
  evidence: { current_volume: 5 },
  status: "detected",
  formula_version: "rules-v1",
  created_at: "2026-07-28T00:00:00Z",
};

const brief = {
  id: "brief-1",
  window_start: "2026-07-27T00:00:00Z",
  window_end: "2026-07-28T00:00:00Z",
  timezone: "Asia/Shanghai",
  version: 1,
  generator: "deterministic",
  ai_provider: "disabled",
  status: "ready",
  created_at: "2026-07-28T00:01:00Z",
  evidence_count: 1,
  items: [
    {
      id: "item-1",
      section: "new_content",
      conclusion_type: "fact",
      title: "新增内容",
      body: "来自资料库",
      position: 0,
      evidence: { new_content_count: 1 },
      content_ids: ["content-1"],
      trend_ids: [],
    },
  ],
};

const schedule = {
  id: "schedule-1",
  enabled: true,
  timezone: "Asia/Shanghai",
  time_of_day: "09:00",
  last_run_at: null,
  next_run_at: "2026-07-29T01:00:00Z",
  consecutive_failures: 0,
  last_error: null,
  created_at: "2026-07-28T00:00:00Z",
  updated_at: "2026-07-28T00:00:00Z",
};

describe("intelligence API", () => {
  it("covers reads, deterministic generation, and daily schedule updates", async () => {
    const signal = new AbortController().signal;
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([trend]))
      .mockResolvedValueOnce(jsonResponse(brief))
      .mockResolvedValueOnce(jsonResponse([trend]))
      .mockResolvedValueOnce(jsonResponse(brief))
      .mockResolvedValueOnce(jsonResponse(schedule))
      .mockResolvedValueOnce(jsonResponse(schedule));

    await expect(listTrends(signal)).resolves.toEqual([trend]);
    await expect(getLatestBrief(signal)).resolves.toEqual(brief);
    await expect(generateTrends()).resolves.toEqual([trend]);
    await expect(generateBrief(true)).resolves.toEqual(brief);
    await expect(getBriefSchedule(signal)).resolves.toEqual(schedule);
    await expect(
      setBriefSchedule({
        enabled: true,
        timezone: "Asia/Shanghai",
        time_of_day: "09:00",
      }),
    ).resolves.toEqual(schedule);

    expect(fetchMock.mock.calls.map((call) => call[0])).toEqual([
      "/api/intelligence/trends",
      "/api/intelligence/briefs/latest",
      "/api/intelligence/trends/generate",
      "/api/intelligence/briefs",
      "/api/intelligence/briefs/schedule",
      "/api/intelligence/briefs/schedule",
    ]);
    expect(fetchMock.mock.calls[2]?.[1]?.method).toBe("POST");
    expect(fetchMock.mock.calls[3]?.[1]?.body).toContain(
      '"regenerate":true',
    );
    expect(fetchMock.mock.calls[5]?.[1]?.method).toBe("PUT");
  });
});
