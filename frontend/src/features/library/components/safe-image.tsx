import { ImageOff } from "lucide-react";
import { useState } from "react";

import { cn } from "../../../lib/utils";

interface SafeImageProps {
  src: string | null;
  alt: string;
  className?: string;
}

export function SafeImage({ src, alt, className }: SafeImageProps) {
  const [failedSource, setFailedSource] = useState<string | null>(null);
  const failed = src !== null && failedSource === src;

  if (!src || failed) {
    return (
      <div
        className={cn(
          "grid place-items-center bg-paper text-muted",
          className,
        )}
        aria-label={src ? "图片加载失败" : "暂无图片"}
      >
        <ImageOff className="size-5" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      className={cn("object-cover", className)}
      loading="lazy"
      referrerPolicy="no-referrer"
      onError={() => setFailedSource(src)}
    />
  );
}
