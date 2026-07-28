import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router";

import { LibraryContentPage } from "./library-content-page";

function jsonResponse(payload: unknown): Response {
  return new Response(JSON.stringify(payload), {
    status: 200,
    headers: { "content-type": "application/json" },
  });
}

describe("LibraryContentPage", () => {
  it("shows provenance, creator, and comments as escaped text", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValueOnce(
      jsonResponse({
        id: "content-1",
        platform: "bili",
        source_content_id: "BV1",
        content_type: "video",
        title: "<script>alert(1)</script>Title",
        description: null,
        source_url: "https://www.bilibili.com/video/BV1",
        cover_url: null,
        author_source_id: "42",
        author_name: "Creator",
        published_at: null,
        first_collected_at: "2026-07-28T00:00:00Z",
        last_collected_at: "2026-07-28T00:01:00Z",
        source_keyword: "AI",
        view_count: null,
        like_count: 2,
        favorite_count: null,
        comment_count: 1,
        share_count: null,
        has_comments: true,
        raw_payload: null,
        creator: {
          id: "creator-1",
          platform: "bili",
          source_creator_id: "42",
          display_name: "Creator",
          profile_url: null,
          avatar_url: null,
          description: null,
          follower_count: null,
          following_count: null,
          content_count: null,
          first_collected_at: "2026-07-28T00:00:00Z",
          last_collected_at: "2026-07-28T00:01:00Z",
        },
        comments: [
          {
            id: "comment-1",
            platform: "bili",
            source_comment_id: "100",
            source_content_id: "BV1",
            parent_comment_id: null,
            author_source_id: null,
            author_name: "Reader",
            body: "<img src=x onerror=alert(1)>plain",
            like_count: null,
            reply_count: 0,
            published_at: null,
            collected_at: "2026-07-28T00:01:00Z",
          },
        ],
        tasks: [
          {
            task_id: "task-1",
            collected_at: "2026-07-28T00:01:00Z",
          },
        ],
      }),
    );
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/library/contents/content-1"]}>
          <Routes>
            <Route
              path="/library/contents/:contentId"
              element={<LibraryContentPage />}
            />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(
      await screen.findByText("<script>alert(1)</script>Title"),
    ).toBeInTheDocument();
    expect(
      screen.getByText("<img src=x onerror=alert(1)>plain"),
    ).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "task-1" })).toHaveAttribute(
      "href",
      "/crawler/tasks/task-1",
    );
    expect(container.querySelector("script")).toBeNull();
  });
});
