import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ActionMenu } from "./action-menu";
import { CollapsibleSection } from "./collapsible-section";
import { FilterBar } from "./filter-bar";
import { MasterDetailLayout } from "./master-detail-layout";
import { SegmentedTabs } from "./segmented-tabs";

describe("UX primitives", () => {
  it("toggles a collapsible section with aria state", async () => {
    const user = userEvent.setup();
    render(
      <CollapsibleSection title="高级设置" count={3}>
        <p>advanced value</p>
      </CollapsibleSection>,
    );

    const trigger = screen.getByRole("button", { name: /高级设置/ });
    expect(trigger).toHaveAttribute("aria-expanded", "false");
    expect(screen.queryByText("advanced value")).not.toBeInTheDocument();
    await user.click(trigger);
    expect(trigger).toHaveAttribute("aria-expanded", "true");
    expect(screen.getByText("advanced value")).toBeInTheDocument();
  });

  it("supports keyboard-friendly tabs and action menus", async () => {
    const user = userEvent.setup();
    const onTabChange = vi.fn();
    const onAction = vi.fn();
    render(
      <>
        <SegmentedTabs
          value="overview"
          onChange={onTabChange}
          label="研究详情"
          items={[{ value: "overview", label: "概览" }, { value: "evidence", label: "证据" }]}
        />
        <ActionMenu label="更多" items={[{ label: "稍后处理", onSelect: onAction }]} />
      </>,
    );

    await user.click(screen.getByRole("tab", { name: "证据" }));
    expect(onTabChange).toHaveBeenCalledWith("evidence");
    await user.click(screen.getByRole("button", { name: "更多" }));
    await user.click(screen.getByRole("menuitem", { name: "稍后处理" }));
    expect(onAction).toHaveBeenCalledOnce();
  });

  it("renders search, filters, chips, and clear behavior", async () => {
    const user = userEvent.setup();
    const onSearchChange = vi.fn();
    const onClear = vi.fn();
    render(
      <FilterBar
        search="工具"
        onSearchChange={onSearchChange}
        searchPlaceholder="搜索机会"
        filters={<select aria-label="状态"><option>全部</option></select>}
        chips={[{ label: "状态：全部", onRemove: vi.fn() }]}
        onClear={onClear}
      />,
    );

    await user.type(screen.getByRole("searchbox", { name: "搜索" }), "箱");
    expect(onSearchChange).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "清除筛选" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "清除筛选" }));
    expect(onClear).toHaveBeenCalledOnce();
  });

  it("moves filters into an escapable mobile panel", async () => {
    const user = userEvent.setup();
    render(
      <FilterBar
        search=""
        onSearchChange={vi.fn()}
        filters={<label>状态<select aria-label="状态"><option>全部</option></select></label>}
      />,
    );

    await user.click(screen.getByRole("button", { name: "筛选" }));
    const panel = screen.getByRole("dialog", { name: "筛选" });
    expect(panel).toBeInTheDocument();
    expect(within(panel).getByRole("combobox", { name: "状态" })).toBeInTheDocument();
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("dialog", { name: "筛选" })).not.toBeInTheDocument();
  });

  it("lets a master-detail surface hide and restore its list", async () => {
    const user = userEvent.setup();
    render(
      <MasterDetailLayout
        list={<p>list content</p>}
        detail={<p>detail content</p>}
        listLabel="任务列表"
      />,
    );

    expect(screen.getByText("list content")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "收起任务列表" }));
    expect(screen.queryByText("list content")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "显示任务列表" }));
    expect(screen.getByText("list content")).toBeInTheDocument();
  });
});
