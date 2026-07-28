import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import * as authApi from "../api/auth";
import { IntegrationsPage } from "./integrations-page";

function renderPage() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <IntegrationsPage />
    </QueryClientProvider>,
  );
}

describe("IntegrationsPage", () => {
  it("shows a full API key once, then retains only its prefix", async () => {
    const oneTimeValue = "synthetic-one-time-key";
    const summary = {
      id: "key-1",
      name: "Codex read-only",
      prefix: "abc12345",
      scopes: ["library:read", "intelligence:read"],
      created_at: "2026-07-28T00:00:00Z",
      last_used_at: null,
      expires_at: null,
      revoked_at: null,
    };
    vi.spyOn(authApi, "listApiKeys")
      .mockResolvedValueOnce([])
      .mockResolvedValue([summary]);
    vi.spyOn(authApi, "createApiKey").mockResolvedValue({
      api_key: oneTimeValue,
      key: summary,
    });
    vi.spyOn(authApi, "revokeApiKey").mockResolvedValue();
    const user = userEvent.setup();
    renderPage();

    await user.click(
      screen.getByRole("button", { name: "创建 API Key" }),
    );
    await user.type(screen.getByLabelText("名称"), "Codex read-only");
    await user.click(
      screen.getByRole("button", { name: "生成一次性 Key" }),
    );

    expect(
      await screen.findByText(oneTimeValue),
    ).toBeInTheDocument();
    await user.click(
      screen.getByRole("button", { name: "关闭完整 API Key" }),
    );
    expect(
      screen.queryByText("synthetic-one-time-key"),
    ).not.toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText("abc12345…")).toBeInTheDocument(),
    );
  });
});
