// The study-card protocol: agents emit cards as ```calypr-card fences holding one JSON object.
//
// The protocol lives in the *token stream* rather than in a new SSE event type, and that is a
// deliberate product decision, not a shortcut. An exported project is a single headless .py that
// owns no Calypr dependency — so anything carried on our wire would be lost the moment someone
// exports. A fenced block survives export intact: the generated agent emits the same text, and a
// buyer's own UI can parse it with this file's ~50 lines. It also means transcripts, history
// replay, and share links carry cards for free, since to every other layer this is just message
// text.
//
// Parsing is total: every failure path returns null and the caller falls back to rendering the
// fence as a plain code block. A model that emits slightly wrong JSON should degrade to visible
// text, never to a crashed transcript.

export type QuizCard = {
  id: string;
  kind: "quiz";
  q: string;
  choices: string[];
  answer: number;
  explain?: string;
};

export type FlashCard = {
  id: string;
  kind: "flashcard";
  front: string;
  back: string;
};

export type Card = QuizCard | FlashCard;

/** A stable id derived from the card's own text (FNV-1a).
 *
 *  This is what keeps a card's answered/flipped state alive while the rest of the reply is still
 *  streaming: every token re-renders the whole message, so a positional key would reset the card
 *  under the learner's cursor mid-answer. Content-derived means the same card keeps the same
 *  identity across every re-render of the turn that contains it. */
function cardId(raw: string): string {
  let h = 0x811c9dc5;
  for (let i = 0; i < raw.length; i++) {
    h ^= raw.charCodeAt(i);
    h = Math.imul(h, 0x01000193);
  }
  return `card-${(h >>> 0).toString(36)}`;
}

const isText = (v: unknown): v is string => typeof v === "string" && v.trim() !== "";

/** Parse one `calypr-card` fence body. Returns null for anything malformed or unrecognised. */
export function parseCard(body: string): Card | null {
  let raw: unknown;
  try {
    raw = JSON.parse(body);
  } catch {
    return null;
  }
  if (typeof raw !== "object" || raw === null) return null;
  const o = raw as Record<string, unknown>;
  const id = cardId(body);

  if (o.kind === "quiz") {
    const { q, choices, answer, explain } = o;
    if (!isText(q) || !Array.isArray(choices) || choices.length < 2) return null;
    if (!choices.every(isText)) return null;
    // A quiz whose answer doesn't point at a choice can't be graded, so it isn't a quiz.
    if (typeof answer !== "number" || !Number.isInteger(answer)) return null;
    if (answer < 0 || answer >= choices.length) return null;
    return {
      id,
      kind: "quiz",
      q,
      choices,
      answer,
      ...(isText(explain) ? { explain } : {}),
    };
  }

  if (o.kind === "flashcard") {
    const { front, back } = o;
    if (!isText(front) || !isText(back)) return null;
    return { id, kind: "flashcard", front, back };
  }

  return null;
}
