"use client";

import { ArrowLeft, ArrowRight } from "lucide-react";
import { useCallback, useEffect, useRef, useState, type ReactNode } from "react";

import { cn } from "@/lib/utils";

/**
 * A scroll-snap carousel: the track is a native horizontally-scrolling flex row (so touch,
 * trackpad and keyboard all work with zero JS), and the JS on top is only chrome — prev/next
 * buttons that scroll by one slide, and a cyan progress bar. Slides mark themselves with
 * `data-slide` so the step size matches the real rendered width at any breakpoint.
 */
export function Carousel({ children, className }: { children: ReactNode; className?: string }) {
  const trackRef = useRef<HTMLDivElement>(null);
  const [progress, setProgress] = useState(0);
  const [canPrev, setCanPrev] = useState(false);
  const [canNext, setCanNext] = useState(true);

  const update = useCallback(() => {
    const el = trackRef.current;
    if (!el) return;
    const max = el.scrollWidth - el.clientWidth;
    setProgress(max > 0 ? el.scrollLeft / max : 1);
    setCanPrev(el.scrollLeft > 4);
    setCanNext(el.scrollLeft < max - 4);
  }, []);

  useEffect(() => {
    update();
    // slide widths are viewport-relative, so the button/progress state is too
    window.addEventListener("resize", update);
    return () => window.removeEventListener("resize", update);
  }, [update]);

  const step = (dir: 1 | -1) => {
    const el = trackRef.current;
    if (!el) return;
    const slide = el.querySelector<HTMLElement>("[data-slide]");
    const gap = 24;
    const width = slide ? slide.getBoundingClientRect().width + gap : el.clientWidth * 0.8;
    el.scrollBy({ left: dir * width, behavior: "smooth" });
  };

  return (
    <div className={className}>
      <div
        ref={trackRef}
        onScroll={update}
        className="flex snap-x snap-mandatory gap-6 overflow-x-auto pb-2 [-ms-overflow-style:none] [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
      >
        {children}
      </div>

      <div className="mt-6 flex items-center gap-5">
        <div className="flex gap-2">
          <button
            type="button"
            aria-label="Previous template"
            onClick={() => step(-1)}
            disabled={!canPrev}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground disabled:opacity-30 disabled:hover:border-border disabled:hover:text-muted-foreground"
          >
            <ArrowLeft className="h-4 w-4" />
          </button>
          <button
            type="button"
            aria-label="Next template"
            onClick={() => step(1)}
            disabled={!canNext}
            className="flex h-9 w-9 items-center justify-center rounded-full border border-border text-muted-foreground transition-colors hover:border-brand/40 hover:text-foreground disabled:opacity-30 disabled:hover:border-border disabled:hover:text-muted-foreground"
          >
            <ArrowRight className="h-4 w-4" />
          </button>
        </div>
        <div className="h-px flex-1 overflow-hidden rounded-full bg-border">
          <div
            aria-hidden
            className="h-full origin-left bg-brand transition-transform duration-200"
            style={{ transform: `scaleX(${Math.max(progress, 0.06)})` }}
          />
        </div>
      </div>
    </div>
  );
}

/** One slide — a plain wrapper carrying the snap + sizing contract for the track. */
export function CarouselSlide({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div data-slide className={cn("w-[86vw] max-w-2xl shrink-0 snap-start", className)}>
      {children}
    </div>
  );
}
