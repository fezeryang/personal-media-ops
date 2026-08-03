import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import * as researchApi from "../api/research";
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

  it("renders typed items with their real IDs", async () => {
    renderPage();
    expect(await screen.findByRole("heading", { name: "个人 AI 机会" })).toBeInTheDocument();
    expect(screen.getByText("登录摩擦候选")).toBeInTheDocument();
    expect(screen.getByText("对象 ID：candidate-1")).toBeInTheDocument();
    expect(screen.getByText("后续验证")).toBeInTheDocument();
  });
});
