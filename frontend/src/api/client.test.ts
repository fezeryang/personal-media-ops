import { z } from "zod";

import { requestJson, requestText } from "./client";

describe("API client", () => {
  it("validates successful JSON responses", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(JSON.stringify({ status: "ok" }), {
        status: 200,
        headers: { "content-type": "application/json" },
      }),
    );

    const result = await requestJson(
      "/api/health",
      z.object({ status: z.literal("ok") }),
    );

    expect(result).toEqual({ status: "ok" });
  });

  it("normalizes FastAPI validation errors", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      new Response(
        JSON.stringify({
          detail: [{ loc: ["body", "keywords"], msg: "Field required" }],
        }),
        {
          status: 422,
          headers: { "content-type": "application/json" },
        },
      ),
    );

    await expect(
      requestJson("/api/crawler/tasks", z.object({ id: z.string() })),
    ).rejects.toMatchObject({
      status: 422,
      message: "keywords：Field required",
    });
  });

  it("normalizes string, location-free, and malformed JSON errors", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ detail: "Mode is disabled" }), {
          status: 409,
          headers: { "content-type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response(
          JSON.stringify({ detail: [{ msg: "Invalid request" }] }),
          {
            status: 422,
            headers: { "content-type": "application/json" },
          },
        ),
      )
      .mockResolvedValueOnce(
        new Response("{not json", {
          status: 500,
          headers: { "content-type": "application/json" },
        }),
      );

    await expect(
      requestJson("api/crawler/tasks", z.object({ id: z.string() })),
    ).rejects.toMatchObject({ status: 409, message: "Mode is disabled" });
    await expect(
      requestJson("/api/crawler/tasks", z.object({ id: z.string() })),
    ).rejects.toMatchObject({ status: 422, message: "Invalid request" });
    await expect(
      requestJson("/api/crawler/tasks", z.object({ id: z.string() })),
    ).rejects.toMatchObject({
      status: 500,
      message: "请求失败（HTTP 500）",
    });
  });

  it("forwards AbortSignal and reads text responses", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValue(new Response("line one", { status: 200 }));
    const controller = new AbortController();

    await expect(
      requestText("/api/crawler/tasks/id/logs?tail=300", {
        signal: controller.signal,
      }),
    ).resolves.toBe("line one");
    expect(fetchMock).toHaveBeenCalledWith(
      "/api/crawler/tasks/id/logs?tail=300",
      expect.objectContaining({ signal: controller.signal }),
    );
  });

  it("normalizes non-JSON and network failures", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(new Response("bad gateway", { status: 502 }))
      .mockRejectedValueOnce(new TypeError("network down"));

    await expect(
      requestJson("/api/health", z.object({ status: z.string() })),
    ).rejects.toMatchObject({
      status: 502,
      message: "请求失败（HTTP 502）",
    });
    await expect(
      requestJson("/api/health", z.object({ status: z.string() })),
    ).rejects.toMatchObject({
      status: 0,
      message: "无法连接服务，请检查网络后重试",
    });
  });

  it("preserves abort errors for callers to ignore intentionally", async () => {
    const abortError = new DOMException("cancelled", "AbortError");
    vi.spyOn(globalThis, "fetch").mockRejectedValueOnce(abortError);

    await expect(
      requestJson("/api/health", z.object({ status: z.string() })),
    ).rejects.toBe(abortError);
  });

  it("rejects successful responses with an invalid contract", async () => {
    vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ unexpected: true }), {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(
        new Response("{not json", {
          status: 200,
          headers: { "content-type": "application/json" },
        }),
      );

    await expect(
      requestJson("/api/health", z.object({ status: z.literal("ok") })),
    ).rejects.toMatchObject({
      status: 502,
      message: "服务返回了无法识别的数据格式",
    });
    await expect(
      requestJson("/api/health", z.object({ status: z.literal("ok") })),
    ).rejects.toMatchObject({
      status: 502,
      message: "服务返回了无法识别的数据格式",
    });
  });
});
