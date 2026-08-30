import type { ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A CSS-keyframe marquee — server-renderable, no JS. The content is rendered twice and the
 * track slides one copy's width, so the loop is seamless at any content length. Keyframes and
 * the reduced-motion/hover-pause guards live in globals.css (`.marquee-*`).
 */
export function Marquee({
  children,
  reverse = false,
  duration = 40,
  className,
}: {
  children: ReactNode;
  reverse?: boolean;
  duration?: number;
  className?: string;
}) {
  return (
    <div className={cn("marquee-mask overflow-hidden", className)}>
      <div
        className={cn("marquee-track", reverse && "marquee-reverse")}
        style={{ "--marquee-duration": `${duration}s` } as React.CSSProperties}
      >
        <div className="marquee-group">{children}</div>
        <div className="marquee-group" aria-hidden>
          {children}
        </div>
      </div>
    </div>
  );
}
