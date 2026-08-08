import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useId, useState } from "react";

import { cn } from "../../lib/utils";

interface CollapsibleSectionProps {
  title: ReactNode;
  count?: number | string;
  description?: ReactNode;
  children: ReactNode;
  defaultOpen?: boolean;
  className?: string;
  contentClassName?: string;
}

export function CollapsibleSection({
  title,
  count,
  description,
  children,
  defaultOpen = false,
  className,
  contentClassName,
}: CollapsibleSectionProps) {
  const [open, setOpen] = useState(defaultOpen);
  const contentId = useId();
  return (
    <section className={cn("rounded-xl border border-line bg-white", className)}>
      <button
        type="button"
        className="flex w-full items-center gap-3 px-4 py-3 text-left"
        aria-expanded={open}
        aria-controls={contentId}
        onClick={() => setOpen((value) => !value)}
      >
        <ChevronDown className={cn("size-4 shrink-0 text-muted transition-transform", open && "rotate-180")} aria-hidden="true" />
        <span className="min-w-0 flex-1">
          <span className="block text-sm font-semibold">{title}</span>
          {description ? <span className="mt-0.5 block text-xs text-muted">{description}</span> : null}
        </span>
        {count !== undefined ? <span className="shrink-0 text-xs text-muted">{count}</span> : null}
      </button>
      {open ? <div id={contentId} className={cn("border-t border-line p-4", contentClassName)}>{children}</div> : null}
    </section>
  );
}
