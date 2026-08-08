import { Search } from "lucide-react";
import type { InputHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

interface SearchInputProps extends Omit<InputHTMLAttributes<HTMLInputElement>, "type"> {
  label?: string;
}

export function SearchInput({ className, label = "搜索", ...props }: SearchInputProps) {
  return (
    <div className="relative min-w-0">
      <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted" aria-hidden="true" />
      <input
        {...props}
        type="search"
        aria-label={props["aria-label"] ?? label}
        className={cn(
          "h-10 w-full rounded-lg border border-line bg-white pl-9 pr-3 text-sm text-ink outline-none placeholder:text-muted/60 focus:border-signal focus:ring-2 focus:ring-signal/12",
          className,
        )}
      />
    </div>
  );
}
