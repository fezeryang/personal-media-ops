import type { ReactNode } from "react";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from "./dialog";

interface SideDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  description?: string;
  children: ReactNode;
  className?: string;
}

export function SideDrawer({
  open,
  onOpenChange,
  title,
  description,
  children,
  className,
}: SideDrawerProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent
        className={`left-auto right-0 top-0 h-full max-h-none w-[min(23rem,calc(100%-1rem))] translate-x-0 translate-y-0 rounded-l-2xl rounded-r-none p-5 sm:w-96 ${className ?? ""}`}
      >
        <DialogTitle>{title}</DialogTitle>
        {description ? <DialogDescription>{description}</DialogDescription> : null}
        <div className="mt-5 min-h-0 overflow-y-auto">{children}</div>
      </DialogContent>
    </Dialog>
  );
}
