"use client";

import { useMemo } from "react";

import type { CardRenderer } from "@/components/Markdown";

import { CardSkeleton, StudyCard, type CardVariant } from "./StudyCard";
import { useScore } from "./useScore";

/** The fence marker, as it appears in the raw reply. */
const FENCE = "```calypr-card";

/** Whether a transcript has produced any card yet.
 *
 *  This — not a field on the project — is what flips a surface into study chrome. A study project
 *  is recognised by what its agent *emits*, so the same detection works on the canvas, on a share
 *  link, and on a transcript reloaded from history, with nothing to configure and no way for the
 *  setting and the behaviour to disagree. A substring scan is cheap enough to run per render. */
export function hasCards(texts: string[]): boolean {
  return texts.some((t) => t.includes(FENCE));
}

/** Scoring plus the card renderer for one surface. `scope` identifies the conversation, so two
 *  sessions on the same share link keep separate tallies. */
export function useStudy(scope: string, variant: CardVariant) {
  const { graded, grade, score, reset } = useScore(scope);

  const cards = useMemo<CardRenderer>(
    () => ({
      render: (card) => (
        <StudyCard
          card={card}
          locked={graded[card.id] !== undefined}
          variant={variant}
          onGrade={(correct) => grade(card.id, correct)}
        />
      ),
      skeleton: () => <CardSkeleton variant={variant} />,
    }),
    [graded, grade, variant],
  );

  return { cards, score, reset };
}
