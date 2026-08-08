import type { ReactNode } from "react";

interface PageHeaderProps {
  /** Kept for compatibility with older callers; product headers no longer render phase copy. */
  eyebrow?: string;
  title: string;
  description?: string;
  action?: ReactNode;
}

export function PageHeader({ title, description, action }: PageHeaderProps) {
  return (
    <header className="flex min-w-0 flex-col gap-2 border-b border-line pb-4 sm:flex-row sm:items-center sm:justify-between sm:gap-4">
      <div className="min-w-0">
        <h1 className="font-display text-2xl font-semibold tracking-[-0.03em] text-ink sm:text-3xl">{title}</h1>
        {description ? <p className="mt-1 line-clamp-1 max-w-3xl text-sm leading-5 text-muted sm:line-clamp-2">{description}</p> : null}
      </div>
      {action ? <div className="flex shrink-0 flex-wrap gap-2">{action}</div> : null}
    </header>
  );
}
