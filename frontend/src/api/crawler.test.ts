import {
  cancelCrawlerTask,
  createCrawlerTask,
  getCrawlerCapabilities,
  getCrawlerTask,
  getCrawlerTaskLogs,
  getCrawlerTaskQrcode,
  getCrawlerTaskResults,
  listCrawlerTasks,
} from "./crawler";

const task = {
  id: "task-1",
  platform: "bili",
  mode: "search",
  crawler_type: "search",
  keywords: "AI Agent",
  target_ids: [],
  target_urls: [],
  creator_ids: [],
  creator_urls: [],
  parent_content_id: null,
  parent_comment_id: null,
  login_type: "qrcode",
  status: "pending",
  requested_count: 20,
  actual_count: 0,
  requested_comment_count: 0,
  requested_sub_comment_count: 0,
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
  it("loads the platform capability registry", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({
        max_concurrent_tasks: 1,
        platforms: [
          {
            platform: "bili",
            display_name: "哔哩哔哩",
            icon_label: "哔",
            enabled: true,
            verification_status: "production_verified",
            availability_status: "enabled",
            login_prompt: "使用哔哩哔哩客户端扫码登录",
            crawler_types: [{ value: "search", label: "关键词搜索" }],
            login_types: [{ value: "qrcode", label: "二维码登录" }],
            requested_count: { minimum: 1, maximum: 20, default: 20 },
            supports_comments: true,
            supports_sub_comments: true,
            modes: [
              {
                mode: "search",
                label: "关键词搜索",
                status: "production_verified",
                enabled: true,
                reason: null,
                input_fields: ["keywords"],
                requested_count: { minimum: 1, maximum: 20, default: 20 },
                requested_comment_count: null,
                requested_sub_comment_count: null,
                requires_browser: true,
                login_type: "qrcode",
              },
              ...(["detail", "creator", "comments", "sub_comments"] as const).map(
                (mode) => ({
                  mode,
                  label: mode,
                  status: "enabled",
                  enabled: true,
                  reason: null,
                  input_fields: [],
                  requested_count: { minimum: 1, maximum: 20, default: 1 },
                  requested_comment_count:
                    mode === "comments"
                      ? { minimum: 1, maximum: 10, default: 10 }
                      : null,
                  requested_sub_comment_count:
                    mode === "sub_comments"
                      ? { minimum: 1, maximum: 5, default: 5 }
                      : null,
                  requires_browser: true,
                  login_type: "qrcode",
                }),
              ),
            ],
          },
          {
            platform: "xhs",
            display_name: "小红书",
            icon_label: "红",
            enabled: false,
            verification_status: "code_ready",
            availability_status: "disabled",
            login_prompt: "使用小红书客户端扫码登录",
            crawler_types: [{ value: "search", label: "关键词搜索" }],
            login_types: [{ value: "qrcode", label: "二维码登录" }],
            requested_count: { minimum: 1, maximum: 20, default: 20 },
            supports_comments: true,
            supports_sub_comments: true,
            modes: ([
              "search",
              "detail",
              "creator",
              "comments",
              "sub_comments",
            ] as const).map((mode) => ({
              mode,
              label: mode,
              status: "disabled",
              enabled: false,
              reason: "未启用",
              input_fields: [],
              requested_count: { minimum: 1, maximum: 20, default: 1 },
              requested_comment_count: null,
              requested_sub_comment_count: null,
              requires_browser: true,
              login_type: "qrcode",
            })),
          },
        ],
      }),
    );

    await expect(getCrawlerCapabilities()).resolves.toMatchObject({
      max_concurrent_tasks: 1,
      platforms: [
        { platform: "bili", enabled: true },
        { platform: "xhs", enabled: false },
      ],
    });
    expect(globalThis.fetch).toHaveBeenCalledWith(
      "/api/crawler/capabilities",
      expect.objectContaining({ signal: undefined }),
    );
  });

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
        mode: "search",
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
        mode: "search",
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
          items: [
            {
              platform: "bili",
              content_id: "BV1",
              content_type: "video",
              title: "Video",
              description: null,
              author_name: "Uploader",
              content_url: "https://www.bilibili.com/video/BV1",
              cover_url: null,
              published_at: 1700000000,
              source_keyword: "AI",
              raw_payload: {
                video_id: "BV1",
                title: "<b>Video</b>",
              },
              metrics: {
                play_count: 10,
                like_count: 9,
                favorite_count: 8,
                comment_count: 7,
                share_count: 6,
              },
            },
          ],
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
    ).resolves.toMatchObject({
      next_offset: 24,
      has_more: true,
      items: [{ platform: "bili", content_id: "BV1" }],
    });
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
