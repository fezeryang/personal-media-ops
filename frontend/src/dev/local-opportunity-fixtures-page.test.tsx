import { render, screen } from "@testing-library/react";

import { LocalOpportunityFixturesPage } from "./local-opportunity-fixtures-page";

describe("LocalOpportunityFixturesPage", () => {
  it("renders the opportunity, validation, content, and outcome fixture states", () => {
    render(<LocalOpportunityFixturesPage />);

    expect(screen.getByRole("heading", { name: "8F Opportunity & Action" })).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "机会卡与证据成熟度" })).toBeInTheDocument();
    expect(screen.getByText("Opportunity Card · detail")).toBeInTheDocument();
    expect(screen.getAllByText("Validation Plan").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Content Opportunity").length).toBeGreaterThan(0);
    expect(screen.getAllByText("Action & Outcome").length).toBeGreaterThan(0);
    expect(screen.getByText("no fabricated business result")).toBeInTheDocument();
  });
});
