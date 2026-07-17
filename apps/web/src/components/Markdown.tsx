import { Fragment, type ReactNode } from "react";

import { ChatAudio } from "@/components/ChatAudio";
import { ChatImage } from "@/components/ChatImage";

// A tiny, dependency-free markdown renderer for chat output — images, audio players, bold, italic,
// inline code, headings, and ordered/unordered lists. It builds React nodes (never
// dangerouslySetInnerHTML), so it's XSS-safe by construction. Covers what agents emit — including
// the Image node's `![alt](url)` and the Voice node's `[label](audio-url)`; not full CommonMark.

// Inline, in order: ![alt](url) image, [label](audio-url) audio player, **bold**, `code`,
// *italic* / _italic_. The image (http/data:image) and audio (data:audio / audio-extension URL)
// alternatives only accept media URLs, so nothing else slips into an <img>/<audio> src, and plain
// text links stay untouched.
const INLINE =
  /(!\[([^\]]*)\]\((https?:\/\/[^)\s]+|data:image\/[^)\s]+)\)|\[([^\]]*)\]\((data:audio\/[^)\s]+|https?:\/\/[^)\s]+\.(?:mp3|wav|opus|aac|flac|ogg|m4a)(?:\?[^)\s]*)?)\)|\*\*([^*]+)\*\*|`([^`]+)`|\*([^*\n]+)\*|_([^_\n]+)_)/g;

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
    else nodes.push(<em key={key}>{m[8] ?? m[9]}</em>);
    last = m.index + m[0].length;
  }
  if (last < text.length) nodes.push(text.slice(last));
  return nodes;
}

export function Markdown({ text }: { text: string }) {
  const blocks: ReactNode[] = [];
  let para: string[] = [];
  let list: { ordered: boolean; items: string[] } | null = null;
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

  for (const line of text.split("\n")) {
    const heading = /^(#{1,3})\s+(.*)$/.exec(line);
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

  return <div className="space-y-2">{blocks}</div>;
}
