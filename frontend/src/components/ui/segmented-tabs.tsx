import type { KeyboardEvent } from "react";

import { cn } from "../../lib/utils";

export interface SegmentedTabItem<Value extends string = string> {
  value: Value;
  label: string;
  count?: number | string;
  disabled?: boolean;
}

interface SegmentedTabsProps<Value extends string = string> {
  value: Value;
  items: SegmentedTabItem<Value>[];
  onChange: (value: Value) => void;
  label: string;
  className?: string;
}

export function SegmentedTabs<Value extends string = string>({
  value,
  items,
  onChange,
  label,
  className,
}: SegmentedTabsProps<Value>) {
  function onKeyDown(event: KeyboardEvent<HTMLButtonElement>, index: number) {
    if (!["ArrowRight", "ArrowLeft", "Home", "End"].includes(event.key)) return;
    event.preventDefault();
    const direction = event.key === "ArrowLeft" ? -1 : 1;
    const nextIndex = event.key === "Home"
      ? 0
      : event.key === "End"
        ? items.length - 1
        : (index + direction + items.length) % items.length;
    const next = items[nextIndex];
    if (next && !next.disabled) onChange(next.value);
    document.getElementById(`tab-${next?.value}`)?.focus();
  }

  return (
    <div className={cn("flex min-w-0 gap-1 overflow-x-auto border-b border-line pb-px", className)} role="tablist" aria-label={label}>
      {items.map((item, index) => (
        <button
          key={item.value}
          id={`tab-${item.value}`}
          type="button"
          role="tab"
          aria-selected={value === item.value}
          tabIndex={value === item.value ? 0 : -1}
          disabled={item.disabled}
          onClick={() => onChange(item.value)}
          onKeyDown={(event) => onKeyDown(event, index)}
          className={cn(
            "shrink-0 border-b-2 px-3 py-2 text-sm font-semibold transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-signal/40",
            value === item.value ? "border-signal text-signal-strong" : "border-transparent text-muted hover:text-ink",
          )}
        >
          {item.label}
          {item.count !== undefined ? <span className="ml-1 text-xs text-muted">{item.count}</span> : null}
        </button>
      ))}
    </div>
  );
}
