import { Filter } from "lucide-react";
import type { ReactNode } from "react";
import { useState } from "react";

import { FilterChip } from "./filter-chip";
import { SideDrawer } from "./side-drawer";
import { SearchInput } from "./search-input";

export interface FilterBarChip {
  label: string;
  onRemove: () => void;
}

interface FilterBarProps {
  search: string;
  onSearchChange: (value: string) => void;
  searchPlaceholder?: string;
  filters?: ReactNode;
  sort?: ReactNode;
  chips?: FilterBarChip[];
  onClear?: () => void;
  resultCount?: number;
}

export function FilterBar({
  search,
  onSearchChange,
  searchPlaceholder = "搜索",
  filters,
  sort,
  chips = [],
  onClear,
  resultCount,
}: FilterBarProps) {
  const [mobileOpen, setMobileOpen] = useState(false);
  const hasFilters = Boolean(filters || sort);
  const hasActive = Boolean(search.trim() || chips.length);
  const clear = () => onClear?.();
  return (
    <section className="rounded-xl border border-line bg-white p-3" aria-label="筛选工具">
      <div className="flex min-w-0 items-center gap-2">
        <SearchInput
          value={search}
          onChange={(event) => onSearchChange(event.currentTarget.value)}
          placeholder={searchPlaceholder}
          className="min-w-0 flex-1"
        />
        {hasFilters ? <button type="button" className="inline-flex h-10 shrink-0 items-center gap-2 rounded-lg border border-line bg-white px-3 text-sm font-semibold hover:bg-paper md:hidden" onClick={() => setMobileOpen(true)}><Filter className="size-4" />筛选</button> : null}
        {resultCount !== undefined ? <span className="hidden shrink-0 text-xs text-muted sm:inline">{resultCount} 条</span> : null}
      </div>
      {hasFilters ? <div className="mt-3 hidden min-w-0 items-center gap-2 md:flex">{filters ? <div className="flex min-w-0 flex-1 flex-wrap gap-2">{filters}</div> : null}{sort ? <div className="shrink-0">{sort}</div> : null}</div> : null}
      {hasActive ? <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2">{chips.map((chip) => <FilterChip key={chip.label} {...chip} />)}{onClear ? <button type="button" className="text-xs font-semibold text-muted underline decoration-line underline-offset-2 hover:text-ink" onClick={clear}>清除筛选</button> : null}</div> : null}
      {hasFilters ? <SideDrawer open={mobileOpen} onOpenChange={setMobileOpen} title="筛选" description="选择条件后关闭面板，列表会立即更新。"><div className="space-y-4">{filters ? <div className="space-y-3">{filters}</div> : null}{sort ? <div className="border-t border-line pt-4">{sort}</div> : null}{onClear && hasActive ? <button type="button" className="w-full rounded-lg border border-line px-3 py-2 text-sm font-semibold" onClick={() => { clear(); setMobileOpen(false); }}>清除筛选</button> : null}<button type="button" className="w-full rounded-lg bg-ink px-3 py-2 text-sm font-semibold text-white" onClick={() => setMobileOpen(false)}>完成</button></div></SideDrawer> : null}
    </section>
  );
}
