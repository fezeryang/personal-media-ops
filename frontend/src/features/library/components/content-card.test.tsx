import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router";

import { ContentCard } from "./content-card";

const content = {
  id: "content-1",
  platform: "wb",
  source_content_id: "post-1",
  content_type: "post",
  title: "<script>alert(1)</script>正文",
  description: "<img src=x onerror=alert(1)>安全文本",
  source_url: "https://weibo.com/post/1",
  cover_url: "https://example.test/missing.jpg",
  author_source_id: "42",
  author_name: "Author",
  published_at: null,
  first_collected_at: "2026-07-28T00:00:00Z",
  last_collected_at: "2026-07-28T00:01:00Z",
  source_keyword: null,
  view_count: null,
  like_count: 3,
  favorite_count: null,
  comment_count: null,
  share_count: null,
  has_comments: false,
};

describe("ContentCard", () => {
  it("renders untrusted markup as text and uses a safe external link", () => {
    const { container } = render(
      <MemoryRouter>
        <ContentCard content={content} />
      </MemoryRouter>,
    );

    expect(screen.getByText(content.title)).toBeInTheDocument();
    expect(screen.getByText(content.description)).toBeInTheDocument();
    expect(container.querySelector("script")).toBeNull();
    expect(container.querySelector("img[onerror]")).toBeNull();
    expect(screen.getByRole("link", { name: /原始链接/ })).toHaveAttribute(
      "rel",
      expect.stringContaining("noopener"),
    );
  });

  it("falls back when a cover image fails", () => {
    render(
      <MemoryRouter>
        <ContentCard content={content} />
      </MemoryRouter>,
    );

    fireEvent.error(screen.getByRole("img", { name: content.title }));
    expect(screen.getByLabelText("图片加载失败")).toBeInTheDocument();
  });
});
