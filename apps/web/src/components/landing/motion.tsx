"use client";

/**
 * The landing page's motion primitives — the only client JS below the hero.
 *
 * Built on `motion` (the framer-motion successor) behind LazyMotion in `strict` mode: only the
 * `m.` components compile, so the bundle carries the ~15kB `domAnimation` feature set rather
 * than the full library. LazyMotion features are module-level, so repeating the provider per
 * primitive costs nothing — each section stays a server component and mounts only these leaves.
 *
 * Everything animates transform/opacity only (no layout properties, so no CLS), fires once on
 * first view, and collapses to opacity-only under prefers-reduced-motion. Continuous motion
 * (marquees, equalizers, glow) is deliberately CSS — the WebGL hero backdrop taught us that
 * per-frame React work on this page swallows the main thread.
 */

import {
  LazyMotion,
  domAnimation,
  m,
  useReducedMotion,
  useScroll,
  useTransform,
} from "motion/react";
import { useRef, type ReactNode } from "react";

const EASE = [0.21, 0.47, 0.32, 0.98] as const;

export function Reveal({
  children,
  delay = 0,
  className,
}: {
  children: ReactNode;
  delay?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  return (
    <LazyMotion features={domAnimation} strict>
      <m.div
        className={className}
        initial={{ opacity: 0, y: reduced ? 0 : 16 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, margin: "-80px" }}
        transition={{ duration: 0.55, ease: EASE, delay }}
      >
        {children}
      </m.div>
    </LazyMotion>
  );
}

export function Stagger({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <LazyMotion features={domAnimation} strict>
      <m.div
        className={className}
        variants={{ hidden: {}, show: { transition: { staggerChildren: 0.08 } } }}
        initial="hidden"
        whileInView="show"
        viewport={{ once: true, margin: "-60px" }}
      >
        {children}
      </m.div>
    </LazyMotion>
  );
}

/** A child of `Stagger` — must be a direct descendant so the parent variants cascade. */
export function StaggerItem({
  children,
  className,
}: {
  children: ReactNode;
  className?: string;
}) {
  const reduced = useReducedMotion();
  return (
    <m.div
      className={className}
      variants={{
        hidden: { opacity: 0, y: reduced ? 0 : 14 },
        show: { opacity: 1, y: 0, transition: { duration: 0.5, ease: EASE } },
      }}
    >
      {children}
    </m.div>
  );
}

/** A few pixels of scroll parallax — decorative only, gone under reduced motion. */
export function Parallax({
  children,
  distance = 6,
  className,
}: {
  children: ReactNode;
  distance?: number;
  className?: string;
}) {
  const reduced = useReducedMotion();
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start end", "end start"] });
  const y = useTransform(scrollYProgress, [0, 1], [distance, -distance]);
  return (
    <LazyMotion features={domAnimation} strict>
      <m.div ref={ref} className={className} style={reduced ? undefined : { y }}>
        {children}
      </m.div>
    </LazyMotion>
  );
}
