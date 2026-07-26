import { cva, type VariantProps } from "class-variance-authority";
import type { HTMLAttributes } from "react";

import { cn } from "../../lib/utils";

const badgeVariants = cva(
  "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-semibold",
  {
    variants: {
      variant: {
        neutral: "border-line bg-paper text-muted",
        info: "border-signal/20 bg-signal/8 text-signal-strong",
        success: "border-success/20 bg-success/8 text-success",
        warning: "border-warning/25 bg-warning/10 text-warning-strong",
        danger: "border-danger/20 bg-danger/8 text-danger",
      },
    },
    defaultVariants: { variant: "neutral" },
  },
);

interface BadgeProps
  extends HTMLAttributes<HTMLSpanElement>,
    VariantProps<typeof badgeVariants> {}

export function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <span className={cn(badgeVariants({ variant }), className)} {...props} />
  );
}
