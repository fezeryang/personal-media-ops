import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, Route, Routes } from "react-router";

import * as researchApi from "../api/research";
import type { ResearchSpaceItem, ResearchSpaceItemLookup } from "../api/research";
import { ResearchSpacesPage } from "./research-spaces-page";

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  render(<QueryClientProvider client={queryClient}><MemoryRouter initialEntries={["/spaces/space-1"]}><Routes><Route path="/spaces/:spaceId" element={<ResearchSpacesPage />} /></Routes></MemoryRouter></QueryClientProvider>);
}

describe("ResearchSpacesPage", () => {
  beforeEach(() => {
    vi.spyOn(researchApi, "listResearchSpaces").mockResolvedValue([{
      id: "space-1",
      name: "个人 AI 机会",
      description: "持续追踪产品机会",
      status: "active",
      item_count: 1,
      created_at: "2026-08-03T00:00:00Z",
      updated_at: "2026-08-03T00:00:00Z",
    }]);
    vi.spyOn(researchApi, "getResearchSpace").mockResolvedValue({
      id: "space-1",
      name: "个人 AI 机会",
      description: "持续追踪产品机会",
      status: "active",
      item_count: 1,
      created_at: "2026-08-03T00:00:00Z",
      updated_at: "2026-08-03T00:00:00Z",
      items: [{
        id: "item-1",
        space_id: "space-1",
        item_type: "discovery_candidate",
        item_id: "candidate-1",
        position: 0,
        note: "后续验证",
        source_candidate_id: "candidate-1",
        item: { id: "candidate-1", title: "登录摩擦候选", final_score: 0.7 },
        created_at: "2026-08-03T00:00:00Z",
        updated_at: "2026-08-03T00:00:00Z",
      }],
    });
  });

  it("renders typed items without exposing IDs in the normal workflow", async () => {
    const user = userEvent.setup();
    renderPage();
    expect(await screen.findByRole("heading", { name: "个人 AI 机会" }, { timeout: 10_000 })).toBeInTheDocument();
    await user.click(screen.getByRole("tab", { name: /^发现/ }));
    expect(screen.getByText("登录摩擦候选")).toBeInTheDocument();
    expect(screen.getByText("后续验证")).toBeInTheDocument();
    expect(document.querySelector("details[open]")).not.toBeInTheDocument();
    await user.click(screen.getByText("技术详情"));
    expect(screen.getByText("对象标识：candidate-1")).toBeInTheDocument();
  }, 10_000);

  it("selects an existing material through the picker", async () => {
    const lookup: ResearchSpaceItemLookup = {
      item_type: "discovery_candidate",
      item_id: "candidate-2",
      title: "另一个登录摩擦候选",
      summary: "来自已有发现收件箱的候选。",
      source_type: "发现收件箱",
      updated_at: "2026-08-04T00:00:00Z",
    };
    const added: ResearchSpaceItem = {
      id: "item-2",
      space_id: "space-1",
      item_type: "discovery_candidate",
      item_id: "candidate-2",
      position: 1,
      note: null,
      source_candidate_id: "candidate-2",
      item: { id: "candidate-2", title: lookup.title },
      created_at: "2026-08-04T00:00:00Z",
      updated_at: "2026-08-04T00:00:00Z",
    };
    vi.spyOn(researchApi, "listResearchSpaceItems").mockResolvedValue([lookup]);
    const add = vi.spyOn(researchApi, "addResearchSpaceItem").mockResolvedValue(added);
    const user = userEvent.setup();
    renderPage();
    await screen.findByRole("heading", { name: "个人 AI 机会" }, { timeout: 10_000 });
    await user.click(screen.getAllByRole("button", { name: "添加材料" })[0]);
    expect(screen.getByText("从已有材料中按标题和来源查找，不需要记住内部标识。")).toBeInTheDocument();
    expect(await screen.findByRole("option", { name: /另一个登录摩擦候选/ })).toBeInTheDocument();
    await user.click(screen.getByRole("option", { name: /另一个登录摩擦候选/ }));
    await user.click(screen.getByRole("button", { name: "加入空间" }));
    await waitFor(() => expect(add).toHaveBeenCalledWith("space-1", {
      item_type: "discovery_candidate",
      item_id: "candidate-2",
      note: undefined,
    }));
  });
});
