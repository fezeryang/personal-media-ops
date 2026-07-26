import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import { CreateTaskDialog } from "./create-task-dialog";

const capabilities = {
  max_concurrent_tasks: 1,
  platforms: [
    {
      platform: "bili",
      display_name: "哔哩哔哩",
      enabled: true,
      verification_status: "verified",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 20 },
      supports_comments: false,
      supports_sub_comments: false,
    },
    {
      platform: "xhs",
      display_name: "小红书",
      enabled: true,
      verification_status: "code_ready",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 20 },
      supports_comments: false,
      supports_sub_comments: false,
    },
    {
      platform: "dy",
      display_name: "抖音",
      enabled: false,
      verification_status: "code_ready",
      crawler_types: [{ value: "search", label: "关键词搜索" }],
      login_types: [{ value: "qrcode", label: "二维码登录" }],
      requested_count: { minimum: 1, maximum: 20, default: 20 },
      supports_comments: false,
      supports_sub_comments: false,
    },
  ],
};

const createdTask = {
  id: "28a58041-9be7-4b39-9dea-2493fe10c249",
  platform: "xhs",
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

describe("CreateTaskDialog", () => {
  it("builds the platform choice from the capability API", async () => {
    const fetchMock = vi
      .spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse(capabilities))
      .mockResolvedValueOnce(jsonResponse(createdTask, 201));
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const user = userEvent.setup();

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

    await user.click(
      screen.getByRole("button", { name: "创建采集任务" }),
    );
    const platformSelect = await screen.findByRole("combobox", {
      name: "平台",
    });
    expect(
      screen.getByRole("option", { name: "抖音（代码就绪，未启用）" }),
    ).toBeDisabled();

    await user.selectOptions(platformSelect, "xhs");
    await user.type(screen.getByLabelText("关键词"), "AI Agent");
    await user.click(
      screen.getByRole("button", { name: "创建并进入任务" }),
    );

    expect(await screen.findByText("已进入任务详情")).toBeInTheDocument();
    expect(fetchMock.mock.calls[1]?.[1]).toMatchObject({
      method: "POST",
      body: JSON.stringify({
        platform: "xhs",
        crawler_type: "search",
        keywords: "AI Agent",
        requested_count: 20,
      }),
    });
  });
});
