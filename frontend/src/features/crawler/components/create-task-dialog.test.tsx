import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import { CreateTaskDialog } from "./create-task-dialog";

const modeLabels = {
  search: "关键词搜索",
  detail: "内容详情",
  creator: "创作者主页",
  comments: "一级评论",
  sub_comments: "二级评论",
} as const;

function modes(enabled = true) {
  return Object.entries(modeLabels).map(([mode, label]) => ({
    mode,
    label,
    status: enabled ? (mode === "search" ? "production_verified" : "enabled") : "disabled",
    enabled,
    reason: mode === "comments" ? "评论任务严格限量" : null,
    input_fields: [],
    requested_count: {
      minimum: 1,
      maximum: 20,
      default: mode === "search" ? 20 : 1,
    },
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
  }));
}

const capabilities = {
  max_concurrent_tasks: 1,
  platforms: [
    {
      platform: "bili",
      display_name: "哔哩哔哩",
      icon_label: "哔",
      enabled: false,
      verification_status: "production_verified",
      availability_status: "disabled",
      login_prompt: "使用哔哩哔哩客户端扫码登录",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 20 },
      supports_comments: true,
      supports_sub_comments: true,
      modes: modes(false),
    },
    {
      platform: "xhs",
      display_name: "小红书",
      icon_label: "红",
      enabled: true,
      verification_status: "production_verified",
      availability_status: "enabled",
      login_prompt: "使用小红书客户端扫码登录",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 20 },
      supports_comments: true,
      supports_sub_comments: true,
      modes: modes(true),
    },
    {
      platform: "dy",
      display_name: "抖音",
      icon_label: "抖",
      enabled: false,
      verification_status: "code_ready",
      availability_status: "deferred_resource_constrained",
      login_prompt: "资源条件允许后使用抖音客户端扫码登录",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 3 },
      supports_comments: true,
      supports_sub_comments: true,
      modes: modes(false).map((mode) => ({
        ...mode,
        status: "deferred_resource_constrained",
      })),
    },
    ...[
      ["zhihu", "知乎", "知"],
      ["wb", "微博", "微"],
      ["tieba", "百度贴吧", "贴"],
      ["ks", "快手", "快"],
    ].map(([platform, display_name, icon_label]) => ({
      platform,
      display_name,
      icon_label,
      enabled: false,
      verification_status: "code_ready",
      availability_status: "disabled",
      login_prompt: `使用${display_name}客户端扫码登录`,
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 5 },
      supports_comments: true,
      supports_sub_comments: true,
      modes: modes(false),
    })),
  ],
};

const createdTask = {
  id: "28a58041-9be7-4b39-9dea-2493fe10c249",
  platform: "xhs",
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

function renderDialog() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <Routes>
          <Route path="/" element={<CreateTaskDialog />} />
          <Route
            path="/crawler/tasks/:taskId"
            element={<p>已进入任务详情</p>}
          />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("CreateTaskDialog", () => {
  it("builds platform and mode choices from the capability API", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockResolvedValueOnce(jsonResponse(createdTask, 201));
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole("button", { name: "创建采集任务" }));
    const platformSelect = await screen.findByRole("combobox", {
      name: "平台",
    });
    expect(
      screen.getByRole("option", { name: "哔哩哔哩（已生产验证，未启用）" }),
    ).toBeDisabled();
    expect(
      screen.getByRole("option", { name: "小红书（已生产验证）" }),
    ).toBeEnabled();
    expect(
      screen.getByRole("option", { name: "抖音（资源限制，暂不可用）" }),
    ).toBeDisabled();
    expect(screen.getAllByRole("option")).toHaveLength(12);

    await user.selectOptions(platformSelect, "xhs");
    await user.type(screen.getByLabelText("关键词"), "AI Agent");
    await user.click(screen.getByRole("button", { name: "创建并进入任务" }));

    expect(await screen.findByText("已进入任务详情")).toBeInTheDocument();
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({ method: "POST" });
    const requestBody = fetchMock.mock.calls[1]?.[1]?.body;
    expect(typeof requestBody).toBe("string");
    if (typeof requestBody !== "string") {
      throw new TypeError("expected a serialized request body");
    }
    const parsedBody: unknown = JSON.parse(requestBody);
    expect(parsedBody).toEqual({
      platform: "xhs",
      mode: "search",
      requested_count: 20,
      keywords: "AI Agent",
    });
  });

  it("renders bounded comment fields and submits one content target", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockResolvedValueOnce(
        jsonResponse({
          ...createdTask,
          mode: "comments",
          crawler_type: "comments",
          keywords: null,
          target_urls: ["https://example.test/content/1"],
          requested_count: 1,
          requested_comment_count: 10,
        }),
      );
    const user = userEvent.setup();
    renderDialog();

    await user.click(screen.getByRole("button", { name: "创建采集任务" }));
    await user.selectOptions(
      await screen.findByRole("combobox", { name: "平台" }),
      "xhs",
    );
    await user.selectOptions(
      screen.getByRole("combobox", { name: "采集模式" }),
      "comments",
    );
    await user.type(
      screen.getByLabelText("内容 URL 或 ID"),
      "https://example.test/content/1",
    );
    expect(screen.getByText(/一级评论最多 10 条/)).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "创建并进入任务" }));

    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      body: JSON.stringify({
        platform: "xhs",
        mode: "comments",
        requested_count: 1,
        target_urls: ["https://example.test/content/1"],
        requested_comment_count: 10,
      }),
    });
  });
});
