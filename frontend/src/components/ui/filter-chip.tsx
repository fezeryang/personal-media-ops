import { X } from "lucide-react";

interface FilterChipProps {
  label: string;
  onRemove: () => void;
}

export function FilterChip({ label, onRemove }: FilterChipProps) {
  return (
    <span className="inline-flex max-w-full items-center gap-1 rounded-full border border-signal/20 bg-signal/8 px-2.5 py-1 text-xs font-medium text-signal-strong">
      <span className="truncate">{label}</span>
      <button
        type="button"
        aria-label={`移除筛选：${label}`}
        className="grid size-4 shrink-0 place-items-center rounded-full hover:bg-signal/15"
        onClick={onRemove}
      >
        <X className="size-3" aria-hidden="true" />
      </button>
    </span>
  );
}
