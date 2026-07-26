import {
  cancelCrawlerTask,
  createCrawlerTask,
  getCrawlerTask,
  getCrawlerTaskLogs,
  getCrawlerTaskQrcode,
  getCrawlerTaskResults,
  listCrawlerTasks,
} from "./crawler";

const task = {
  id: "task-1",
  platform: "bili",
  crawler_type: "search",
  keywords: "AI Agent",
  login_type: "qrcode",
  status: "pending",
  requested_count: 20,
  actual_count: 0,
  output_dir: "/private/output",
  log_path: "/private/log",
  qrcode_path: "/private/qrcode",
  pid: null,
  error_message: null,
  created_at: "2026-07-26T12:00:00Z",
  started_at: null,
  finished_at: null,
  cancel_requested: false,
};

function jsonResponse(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "content-type": "application/json" },
  });
}

describe("crawler API", () => {
  it("lists, reads, creates, and cancels tasks", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse([task]))
      .mockResolvedValueOnce(jsonResponse(task))
      .mockResolvedValueOnce(jsonResponse(task, 201))
      .mockResolvedValueOnce(
        jsonResponse({ ...task, status: "cancelled", cancel_requested: true }),
      );

    await expect(listCrawlerTasks()).resolves.toHaveLength(1);
    await expect(getCrawlerTask("task/unsafe")).resolves.toMatchObject({
      id: "task-1",
    });
    await expect(
      createCrawlerTask({
        platform: "bili",
        crawler_type: "search",
        keywords: "AI Agent",
        requested_count: 20,
      }),
    ).resolves.toMatchObject({ keywords: "AI Agent" });
    await expect(cancelCrawlerTask("task-1")).resolves.toMatchObject({
      status: "cancelled",
    });

    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/crawler/tasks/task%2Funsafe",
    );
    expect(fetchMock.mock.calls[2]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        platform: "bili",
        crawler_type: "search",
        keywords: "AI Agent",
        requested_count: 20,
      }),
    });
    expect(fetchMock.mock.calls[3]?.[1]).toMatchObject({ method: "POST" });
  });

  it("reads bounded logs and paginated results", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("latest log", { status: 200 }))
      .mockResolvedValueOnce(
        jsonResponse({
          items: [{ title: "Video" }],
          offset: 12,
          limit: 12,
          next_offset: 24,
          has_more: true,
        }),
      );

    await expect(getCrawlerTaskLogs("task-1", 300)).resolves.toBe(
      "latest log",
    );
    await expect(
      getCrawlerTaskResults("task-1", 12, 12),
    ).resolves.toMatchObject({ next_offset: 24, has_more: true });
    expect(fetchMock.mock.calls[0]?.[0]).toBe(
      "/api/crawler/tasks/task-1/logs?tail=300",
    );
    expect(fetchMock.mock.calls[1]?.[0]).toBe(
      "/api/crawler/tasks/task-1/results?offset=12&limit=12",
    );
  });

  it("returns QR blobs and treats a missing QR as not ready", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(new Uint8Array([137, 80, 78, 71]), {
          status: 200,
          headers: { "content-type": "image/png" },
        }),
      )
      .mockResolvedValueOnce(
        jsonResponse({ detail: "QR code is not available yet" }, 404),
    );

    const image = await getCrawlerTaskQrcode("task-1");
    expect(image).toMatchObject({ size: 4, type: "image/png" });
    await expect(getCrawlerTaskQrcode("task-1")).resolves.toBeNull();
  });

  it("rejects a non-PNG QR response", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response("<html>not a QR code</html>", {
        status: 200,
        headers: { "content-type": "text/html" },
      }),
    );

    await expect(getCrawlerTaskQrcode("task-1")).rejects.toMatchObject({
      status: 502,
      message: "服务返回的二维码格式无效",
    });
  });
});
