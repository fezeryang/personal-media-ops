import type { ReactNode } from "react";
import { useEffect, useState } from "react";

interface MasterDetailLayoutProps {
  list: ReactNode;
  detail: ReactNode;
  listLabel: string;
  storageKey?: string;
  defaultCollapsed?: boolean;
  listWidthClassName?: string;
  className?: string;
}

function readCollapsed(storageKey: string | undefined): boolean {
  if (!storageKey) return false;
  try {
    return window.localStorage.getItem(storageKey) === "true";
  } catch {
    return false;
  }
}

export function MasterDetailLayout({
  list,
  detail,
  listLabel,
  storageKey,
  defaultCollapsed = false,
  listWidthClassName = "lg:w-[330px]",
  className,
}: MasterDetailLayoutProps) {
  const [collapsed, setCollapsed] = useState(() => storageKey ? readCollapsed(storageKey) : defaultCollapsed);
  useEffect(() => {
    if (!storageKey) return;
    try {
      window.localStorage.setItem(storageKey, String(collapsed));
    } catch {
      // A storage failure must not affect the workbench layout.
    }
  }, [collapsed, storageKey]);
  return (
    <section className={`flex min-w-0 flex-col gap-4 lg:flex-row ${className ?? ""}`} data-list-collapsed={collapsed}>
      {!collapsed ? <aside className={`min-w-0 shrink-0 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto ${listWidthClassName}`} aria-label={listLabel}>{list}</aside> : null}
      <div className="min-w-0 flex-1">
        <div className="mb-3 flex justify-end">
          <button
            type="button"
            className="text-xs font-semibold text-muted underline decoration-line underline-offset-2 hover:text-ink"
            aria-label={collapsed ? `显示${listLabel}` : `收起${listLabel}`}
            onClick={() => setCollapsed((value) => !value)}
          >
            {collapsed ? `显示${listLabel}` : `收起${listLabel}`}
          </button>
        </div>
        {detail}
      </div>
    </section>
  );
}
