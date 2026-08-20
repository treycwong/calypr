"use client";

import { useState } from "react";
import { Check, RotateCcw, X } from "lucide-react";

import type { Card, FlashCard, QuizCard } from "./parseCards";

/** The two surfaces that render cards look nothing alike — the share page is a dark glass terminal
 *  over an ASCII field, the canvas playground is a design-system panel — and neither theme can be
 *  inferred from context. An explicit variant beats guessing at inherited colors. */
export type CardVariant = "glass" | "panel";

const shell: Record<CardVariant, string> = {
  glass: "border-white/10 bg-white/[0.04] text-white",
  panel: "border-border bg-card text-card-foreground",
};

const choiceIdle: Record<CardVariant, string> = {
  glass: "border-white/10 bg-white/[0.02] hover:border-cyan-400/40 hover:bg-white/[0.06]",
  panel: "border-border bg-background hover:border-primary/40 hover:bg-muted",
};

const correctTone: Record<CardVariant, string> = {
  glass: "border-emerald-400/50 bg-emerald-400/10 text-emerald-100",
  panel: "border-emerald-500/50 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
};

const wrongTone: Record<CardVariant, string> = {
  glass: "border-rose-400/50 bg-rose-400/10 text-rose-100",
  panel: "border-rose-500/50 bg-rose-500/10 text-rose-700 dark:text-rose-300",
};

const muted: Record<CardVariant, string> = {
  glass: "text-white/50",
  panel: "text-muted-foreground",
};

function Quiz({
  card,
  locked,
  variant,
  onGrade,
}: {
  card: QuizCard;
  locked: boolean;
  variant: CardVariant;
  onGrade: (correct: boolean) => void;
}) {
  const [picked, setPicked] = useState<number | null>(null);
  // `locked` (a grade already recorded) and `picked` (answered just now) are different facts: a
  // restored session knows the card was answered but not which choice the learner touched, so the
  // answer is revealed without highlighting a pick.
  const answered = picked !== null || locked;

  return (
    <div className={`rounded-xl border p-4 ${shell[variant]}`} data-testid="quiz-card">
      <p className="text-sm font-medium leading-snug">{card.q}</p>
      <div className="mt-3 space-y-2">
        {card.choices.map((choice, i) => {
          const isAnswer = i === card.answer;
          const tone = !answered
            ? choiceIdle[variant]
            : isAnswer
              ? correctTone[variant]
              : picked === i
                ? wrongTone[variant]
                : `${choiceIdle[variant]} opacity-50`;
          return (
            <button
              key={i}
              type="button"
              disabled={answered}
              data-testid="quiz-choice"
              onClick={() => {
                if (answered) return;
                setPicked(i);
                onGrade(isAnswer);
              }}
              className={`flex w-full items-center gap-2.5 rounded-lg border px-3 py-2 text-left text-sm transition disabled:cursor-default ${tone}`}
            >
              <span className="shrink-0 font-mono text-xs opacity-60">
                {String.fromCharCode(65 + i)}
              </span>
              <span className="min-w-0 flex-1">{choice}</span>
              {answered && isAnswer ? <Check className="h-4 w-4 shrink-0" /> : null}
              {answered && picked === i && !isAnswer ? <X className="h-4 w-4 shrink-0" /> : null}
            </button>
          );
        })}
      </div>
      {answered && card.explain ? (
        <p className={`mt-3 text-xs leading-relaxed ${muted[variant]}`} data-testid="quiz-explain">
          {card.explain}
        </p>
      ) : null}
    </div>
  );
}

function Flip({
  card,
  locked,
  variant,
  onGrade,
}: {
  card: FlashCard;
  locked: boolean;
  variant: CardVariant;
  onGrade: (correct: boolean) => void;
}) {
  const [flipped, setFlipped] = useState(false);

  return (
    <div className={`rounded-xl border p-4 ${shell[variant]}`} data-testid="flash-card">
      <p className={`font-mono text-[10px] uppercase tracking-[0.2em] ${muted[variant]}`}>
        {flipped ? "back" : "front"}
      </p>
      <button
        type="button"
        onClick={() => setFlipped((f) => !f)}
        data-testid="flash-flip"
        className="mt-2 flex min-h-20 w-full items-center justify-center px-2 py-3 text-center text-lg font-medium leading-snug"
      >
        {flipped ? card.back : card.front}
      </button>

      {!flipped ? (
        <p className={`text-center text-xs ${muted[variant]}`}>Tap to reveal</p>
      ) : locked ? (
        <p className={`text-center text-xs ${muted[variant]}`} data-testid="flash-done">
          Graded
        </p>
      ) : (
        // Self-grading only appears after the back is revealed — grading a card you haven't seen
        // the answer to would put noise in the tally.
        <div className="mt-1 flex gap-2">
          <button
            type="button"
            data-testid="flash-missed"
            onClick={() => onGrade(false)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs transition ${choiceIdle[variant]}`}
          >
            <RotateCcw className="h-3.5 w-3.5" />
            Missed it
          </button>
          <button
            type="button"
            data-testid="flash-got"
            onClick={() => onGrade(true)}
            className={`flex flex-1 items-center justify-center gap-1.5 rounded-lg border px-3 py-2 text-xs transition ${correctTone[variant]}`}
          >
            <Check className="h-3.5 w-3.5" />
            Got it
          </button>
        </div>
      )}
    </div>
  );
}

/** A card mid-stream: the fence has opened but its closing ``` hasn't arrived yet, so there is no
 *  JSON to parse. Showing the skeleton (rather than the half-written JSON) is what keeps a study
 *  session from flickering raw braces at the learner on every token. */
export function CardSkeleton({ variant }: { variant: CardVariant }) {
  return (
    <div
      className={`animate-pulse rounded-xl border p-4 ${shell[variant]}`}
      data-testid="card-skeleton"
    >
      <div className="h-3 w-2/3 rounded bg-current opacity-10" />
      <div className="mt-3 space-y-2">
        <div className="h-8 rounded-lg bg-current opacity-[0.06]" />
        <div className="h-8 rounded-lg bg-current opacity-[0.06]" />
      </div>
    </div>
  );
}

export function StudyCard({
  card,
  locked,
  variant,
  onGrade,
}: {
  card: Card;
  /** A grade for this card is already recorded — lock it and reveal the answer. */
  locked: boolean;
  variant: CardVariant;
  onGrade: (correct: boolean) => void;
}) {
  return card.kind === "quiz" ? (
    <Quiz card={card} locked={locked} variant={variant} onGrade={onGrade} />
  ) : (
    <Flip card={card} locked={locked} variant={variant} onGrade={onGrade} />
  );
}
