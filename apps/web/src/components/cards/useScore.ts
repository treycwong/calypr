"use client";

import { useCallback, useMemo, useSyncExternalStore } from "react";

/** One graded card, in the order it was answered — the order is what makes `streak` meaningful. */
type Entry = { id: string; correct: boolean };

export type Score = { correct: number; total: number; streak: number };

const key = (scope: string) => `calypr:score:${scope}`;

// localStorage is an external store, so it is read through `useSyncExternalStore` rather than
// mirrored into state by an effect. That is not ceremony: this component is server-rendered, and
// any render-time read of localStorage would make the server and client markup disagree.
// `getServerSnapshot` returns the shared EMPTY, so the hydration render matches the server and
// React re-renders with the stored tally immediately after.
const EMPTY: Entry[] = [];
const listeners = new Set<() => void>();

/** Snapshots must be reference-stable between changes or `useSyncExternalStore` loops forever,
 *  so parsed values are cached and only ever replaced wholesale. */
const cache = new Map<string, Entry[]>();

const isEntry = (e: unknown): e is Entry =>
  typeof e === "object" &&
  e !== null &&
  typeof (e as Entry).id === "string" &&
  typeof (e as Entry).correct === "boolean";

function read(scope: string): Entry[] {
  const hit = cache.get(scope);
  if (hit) return hit;
  let parsed: Entry[] = EMPTY;
  try {
    const raw = window.localStorage.getItem(key(scope));
    if (raw) {
      const value: unknown = JSON.parse(raw);
      if (Array.isArray(value)) parsed = value.filter(isEntry);
    }
  } catch {
    // Corrupt, full, or blocked storage (private mode, quota) — start clean rather than break.
  }
  cache.set(scope, parsed);
  return parsed;
}

function write(scope: string, next: Entry[]) {
  cache.set(scope, next);
  try {
    window.localStorage.setItem(key(scope), JSON.stringify(next));
  } catch {
    // The in-memory tally still works for this session; only persistence is lost.
  }
  for (const fn of listeners) fn();
}

function subscribe(fn: () => void) {
  listeners.add(fn);
  return () => void listeners.delete(fn);
}

/** The learner's running tally for one study session.
 *
 *  Deliberately client-only. A share link has no identity to hang a score row on — every visitor
 *  is anonymous on the same public token — so persisting server-side would either attribute
 *  strangers' answers to the owner's workspace or invent an account nobody asked for. localStorage
 *  keyed by the conversation gives the one property that actually matters to a learner (a refresh
 *  doesn't wipe the streak) and collects nothing.
 *
 *  `scope` should identify the conversation, not just the project, so two sessions on the same
 *  share link keep separate tallies. */
export function useScore(scope: string) {
  const entries = useSyncExternalStore(
    subscribe,
    useCallback(() => read(scope), [scope]),
    () => EMPTY,
  );

  /** Record a grade. First answer wins — a card locks once answered, and re-grading the same id
   *  (a re-render, a restored transcript) must not inflate the total. */
  const grade = useCallback(
    (id: string, correct: boolean) => {
      const cur = read(scope);
      if (cur.some((e) => e.id === id)) return;
      write(scope, [...cur, { id, correct }]);
    },
    [scope],
  );

  const graded = useMemo(() => {
    const m: Record<string, boolean> = {};
    for (const e of entries) m[e.id] = e.correct;
    return m;
  }, [entries]);

  const score = useMemo<Score>(() => {
    let streak = 0;
    for (let i = entries.length - 1; i >= 0 && entries[i].correct; i--) streak++;
    return { correct: entries.filter((e) => e.correct).length, total: entries.length, streak };
  }, [entries]);

  const reset = useCallback(() => write(scope, EMPTY), [scope]);

  return { graded, grade, score, reset };
}
