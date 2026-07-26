import type { InputHTMLAttributes } from "react";

import { cn } from "../../lib/utils";

export function Input({
  className,
  ...props
}: InputHTMLAttributes<HTMLInputElement>) {
  return (
    <input
      className={cn(
        "h-10 w-full rounded-lg border border-line bg-white px-3 text-sm text-ink outline-none placeholder:text-muted/60 focus:border-signal focus:ring-2 focus:ring-signal/12 disabled:bg-paper disabled:text-muted",
        className,
      )}
      {...props}
    />
  );
}
