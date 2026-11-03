"use client";

import { Flame } from "lucide-react";

import type { CardVariant } from "./StudyCard";
import type { Score } from "./useScore";

const tone: Record<CardVariant, { bar: string; track: string; label: string; fill: string }> = {
  glass: {
    bar: "border-white/5 bg-black/30 text-white",
    track: "bg-white/10",
    label: "text-white/50",
    fill: "bg-gradient-to-r from-cyan-300 to-cyan-500",
  },
  panel: {
    bar: "border-border bg-muted/40 text-foreground",
    track: "bg-border",
    label: "text-muted-foreground",
    fill: "bg-primary",
  },
};

/** The running tally. Appears the moment the first card arrives and pins above the transcript —
 *  it is the single clearest signal that this project is a drill and not a chat.
 *
 *  The bar is **progress** (answered of the cards shown), and the count beside it is labelled.
 *  It used to be correct-of-answered with bare numbers, so answering the first of three cards
 *  read "1 / 1 · 100%" — a finished drill with two cards still unflipped. */
export function ScoreStrip({
  score,
  variant,
  shown,
}: {
  score: Score;
  variant: CardVariant;
  /** Cards on screen so far (`countCards`). Never below the number answered. */
  shown: number;
}) {
  const t = tone[variant];
  const total = Math.max(shown, score.total);
  const pct = total === 0 ? 0 : Math.round((score.total / total) * 100);

  return (
    <div
      className={`flex items-center gap-3 border-b px-4 py-2.5 ${t.bar}`}
      data-testid="score-strip"
    >
      <div className="flex min-w-0 shrink-0 items-baseline gap-1">
        <span className="text-sm font-semibold tabular-nums" data-testid="score-correct">
          {score.correct}
        </span>
        <span className={`text-xs ${t.label}`}>correct</span>
      </div>

      <div className={`h-1.5 min-w-0 flex-1 overflow-hidden rounded-full ${t.track}`}>
        <div
          className={`h-full rounded-full transition-[width] duration-500 ${t.fill}`}
          style={{ width: `${pct}%` }}
        />
      </div>

      {/* A streak only reads as an achievement once it's actually a run of answers. */}
      {score.streak >= 2 ? (
        <span className="flex shrink-0 items-center gap-1 text-xs" data-testid="score-streak">
          <Flame className="h-3.5 w-3.5 text-amber-400" />
          <span className="tabular-nums">{score.streak}</span>
        </span>
      ) : null}

      <span className={`shrink-0 text-xs tabular-nums ${t.label}`} data-testid="score-progress">
        {score.total} of {total} answered
      </span>
    </div>
  );
}
