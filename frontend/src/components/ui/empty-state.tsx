import type { ReactNode } from "react";

interface EmptyStateProps {
  title: string;
  description?: string;
  icon?: ReactNode;
  action?: ReactNode;
  className?: string;
}

export function EmptyState({ title, description, icon, action, className }: EmptyStateProps) {
  return (
    <div className={`grid min-h-40 place-items-center rounded-xl bg-paper p-6 text-center ${className ?? ""}`}>
      <div className="max-w-md">
        {icon ? <div className="mx-auto grid size-10 place-items-center text-signal">{icon}</div> : null}
        <h3 className="mt-2 text-sm font-semibold">{title}</h3>
        {description ? <p className="mt-2 text-sm leading-6 text-muted">{description}</p> : null}
        {action ? <div className="mt-4 flex justify-center">{action}</div> : null}
      </div>
    </div>
  );
}
