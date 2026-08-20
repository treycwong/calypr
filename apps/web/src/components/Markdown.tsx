import { Fragment, type ReactNode } from "react";

import { type Card, parseCard } from "@/components/cards/parseCards";
import { ChatAudio } from "@/components/ChatAudio";
import { ChatImage } from "@/components/ChatImage";

// A tiny, dependency-free markdown renderer for chat output — images, audio players, links, bold,
// italic, inline code, headings, and ordered/unordered lists. It builds React nodes (never
// dangerouslySetInnerHTML), so it's XSS-safe by construction. Covers what agents emit — including
// the Image node's `![alt](url)` and the Voice node's `[label](audio-url)`; not full CommonMark.

// Inline, in order: ![alt](url) image, [label](audio-url) audio player, **bold**, `code`,
// *italic* / _italic_, [label](url) link. The image (http/data:image) and audio (data:audio /
// audio-extension URL) alternatives only accept media URLs, so nothing else slips into an
// <img>/<audio> src.
//
// The link alternative is deliberately LAST: appending leaves every earlier capture-group index
// untouched, so adding it can't silently renumber the branches below. Ordering is still correct
// because only this alternative can match at a bare `[`.
//
// It also only accepts http/https — the same trick the media alternatives use, which is what keeps
// `javascript:` and `data:` out of an href by construction rather than by a downstream check. That
// matters more than it looks: this renderer displays text an agent read from GitHub issues and
// Notion pages, so link targets are third-party content, not just model output.
const INLINE =
  /(!\[([^\]]*)\]\((https?:\/\/[^)\s]+|data:image\/[^)\s]+)\)|\[([^\]]*)\]\((data:audio\/[^)\s]+|https?:\/\/[^)\s]+\.(?:mp3|wav|opus|aac|flac|ogg|m4a)(?:\?[^)\s]*)?)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*\n]+)\*|_([^_\n]+)_|\[([^\]]*)\]\((https?:\/\/[^)\s]+)\))/g;

function renderInline(text: string, keyPrefix: string): ReactNode[] {
  const nodes: ReactNode[] = [];
  let last = 0;
  let m: RegExpExecArray | null;
  let i = 0;
  INLINE.lastIndex = 0;
  while ((m = INLINE.exec(text)) !== null) {
    if (m.index > last) nodes.push(text.slice(last, m.index));
    const key = `${keyPrefix}-${i++}`;
    if (m[3] !== undefined) nodes.push(<ChatImage key={key} src={m[3]} alt={m[2] ?? ""} />);
    else if (m[5] !== undefined)
      nodes.push(<ChatAudio key={key} src={m[5]} label={(m[4] ?? "").replace(/^▶\s*/, "")} />);
    else if (m[6] !== undefined) nodes.push(<strong key={key}>{m[6]}</strong>);
    else if (m[7] !== undefined)
      nodes.push(
        <code key={key} className="rounded bg-white/10 px-1 py-0.5 font-mono text-[0.85em]">
          {m[7]}
        </code>,
      );
    else if (m[11] !== undefined)
      nodes.push(
        // New tab + noopener/noreferrer: the href can come from a GitHub issue or Notion page the
        // agent read, so it is untrusted content — never hand it the opener window.
        <a
          key={key}
          href={m[11]}
          target="_blank"
          rel="noopener noreferrer"
          className="underline underline-offset-2 hover:no-underline"
        >
          {m[10] || m[11]}
        </a>,
      );
    else nodes.push(<em key={key}>{m[8] ?? m[9]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

/** How a surface renders a `calypr-card` fence. Passed in rather than imported here so this
 *  renderer stays free of scoring logic — the share page and the canvas playground grade into
 *  different tallies, and a plain transcript (no handler) still renders the fence as code. */
export type CardRenderer = {
  render: (card: Card) => ReactNode;
  /** The fence has opened but its closing ``` hasn't streamed in yet. */
  skeleton: () => ReactNode;
};

export function Markdown({ text, cards }: { text: string; cards?: CardRenderer }) {
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
  let fence: { lang: string; lines: string[] } | null = null;
  let key = 0;

  const flushPara = () => {
    if (para.length === 0) return;
    const lines = para;
    blocks.push(
      <p key={key++} className="whitespace-pre-wrap">
        {lines.map((ln, i) => (
          <Fragment key={i}>
            {i > 0 ? <br /> : null}
            {renderInline(ln, `p${key}-${i}`)}
          </Fragment>
        ))}
      </p>,
    );
    para = [];
  };

  const flushList = () => {
    if (!list) return;
    const cur = list;
    const items = cur.items.map((it, i) => <li key={i}>{renderInline(it, `li${key}-${i}`)}</li>);
    blocks.push(
      cur.ordered ? (
        <ol key={key++} className="list-decimal space-y-1 pl-5">
          {items}
        </ol>
      ) : (
        <ul key={key++} className="list-disc space-y-1 pl-5">
          {items}
        </ul>
      ),
    );
    list = null;
  };

  // `open` means the closing ``` never arrived — the reply is still streaming. A half-written
  // card is shown as a skeleton rather than as raw braces, which is what keeps a drill from
  // flickering JSON at the learner on every token.
  const flushFence = (open: boolean) => {
    if (!fence) return;
    const cur = fence;
    fence = null;
    const body = cur.lines.join("\n");
    if (cur.lang === "calypr-card" && cards) {
      if (open) {
        blocks.push(<Fragment key={key++}>{cards.skeleton()}</Fragment>);
        return;
      }
      const card = parseCard(body);
      // A model that emits slightly wrong JSON degrades to a visible code block. Never a crash,
      // and never a silently swallowed card.
      if (card) {
        blocks.push(<Fragment key={key++}>{cards.render(card)}</Fragment>);
        return;
      }
    }
    blocks.push(
      <pre
        key={key++}
        className="overflow-x-auto rounded-lg bg-white/[0.06] p-3 font-mono text-xs leading-relaxed"
      >
        {body}
      </pre>,
    );
  };

  for (const line of text.split("\n")) {
    // Fences first: everything between them is literal, so no inline or list rule may run here.
    if (fence) {
      if (/^\s*```\s*$/.test(line)) flushFence(false);
      else fence.lines.push(line);
      continue;
    }
    const opening = /^\s*```([\w-]*)\s*$/.exec(line);
    if (opening) {
      flushPara();
      flushList();
      fence = { lang: opening[1], lines: [] };
      continue;
    }

    // #### and deeper matter: models reach for h4 inside a numbered outline without being asked,
    // and anything unmatched here falls through to a paragraph and prints its own `#` marks.
    const heading = /^(#{1,6})\s+(.*)$/.exec(line);
    const ordered = /^\s*\d+\.\s+(.*)$/.exec(line);
    const bullet = /^\s*[-*+]\s+(.*)$/.exec(line);

    if (heading) {
      flushPara();
      flushList();
      const level = heading[1].length;
      const cls =
        level === 1 ? "text-base font-semibold" : level === 2 ? "font-semibold" : "font-medium";
      blocks.push(
        <p key={key++} className={cls}>
          {renderInline(heading[2], `h${key}`)}
        </p>,
      );
    } else if (ordered) {
      flushPara();
      if (!list || !list.ordered) {
        flushList();
        list = { ordered: true, items: [] };
      }
      list.items.push(ordered[1]);
    } else if (bullet) {
      flushPara();
      if (!list || list.ordered) {
        flushList();
        list = { ordered: false, items: [] };
      }
      list.items.push(bullet[1]);
    } else if (line.trim() === "") {
      flushPara();
      flushList();
    } else {
      flushList();
      para.push(line);
    }
  }
  flushPara();
  flushList();
  flushFence(true);

  return <div className="space-y-2">{blocks}</div>;
}
