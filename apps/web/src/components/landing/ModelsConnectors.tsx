import { Blocks, FileText, GitBranch, Globe, Image as ImageIcon, Plug, Search } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Marquee } from "@/components/landing/Marquee";
import { Reveal } from "@/components/landing/motion";
import { CONNECTORS, MODEL_PROVIDERS, TOOL_PROVIDERS } from "@/components/landing/landing-data";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { SectionLabel } from "@/components/spectra/SectionLabel";
import { SECTION_INNER, Section } from "@/components/site/Section";

/**
 * Models & connectors — two counter-scrolling marquee rows of typographic chips. Wordmarks
 * only, no brand logo SVGs: nominative text is trademark-safe and needs zero assets. The
 * marquee is pure CSS (pauses on hover, static under reduced motion).
 */

const TOOL_ICONS: Record<string, LucideIcon> = {
  Tavily: Search,
  Unsplash: ImageIcon,
  MCP: Blocks,
  HTTP: Globe,
  Notion: FileText,
  GitHub: GitBranch,
  "Custom MCP": Plug,
};

function Chip({
  kind,
  name,
  detail,
  soon = false,
}: {
  kind: "model" | "tool" | "connector";
  name: string;
  detail: string;
  soon?: boolean;
}) {
  const Icon = TOOL_ICONS[name];
  return (
    <span className="flex shrink-0 items-center gap-3 rounded-lg border border-border bg-card/40 px-4 py-3 transition-colors hover:border-brand/40">
      {Icon ? <Icon className="h-4 w-4 text-muted-foreground" aria-hidden /> : null}
      <span>
        <span className="flex items-center gap-2">
          <span className="text-sm font-medium tracking-tight">{name}</span>
          {soon && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-brand/30 px-2 py-0.5 font-mono text-[9px] uppercase tracking-[0.18em] text-brand">
              <span className="relative flex h-1 w-1">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-brand opacity-60 motion-reduce:animate-none" />
                <span className="relative inline-flex h-1 w-1 rounded-full bg-brand" />
              </span>
              soon
            </span>
          )}
        </span>
        <span className="mt-0.5 block font-mono text-[11px] text-muted-foreground">
          {detail} · <span className="opacity-70">{kind}</span>
        </span>
      </span>
    </span>
  );
}

export function ModelsConnectors() {
  return (
    <Section id="models" bleed>
      <div className={SECTION_INNER}>
        <Reveal>
          <div className="grid items-start gap-10 lg:grid-cols-2">
            <div>
              <SectionLabel index="04">bring your stack</SectionLabel>
              <SectionHeading className="mt-6" accent="Your tools wired up.">
                Frontier models in.
              </SectionHeading>
            </div>
            <p className="max-w-[430px] text-pretty text-lg leading-[1.55] text-[var(--text-on-dark-muted)] lg:pt-12">
              Pick a model per agent, hand it tools, and connect the apps you already live in —
              all from the same canvas.
            </p>
          </div>
        </Reveal>
      </div>

      <Reveal delay={0.1} className="mt-12 space-y-4">
        <Marquee duration={45} className="[--marquee-gap:1rem]">
          {MODEL_PROVIDERS.map((p) => (
            <Chip
              key={p.name}
              kind="model"
              name={p.name}
              detail={p.detail}
              soon={"soon" in p && p.soon === true}
            />
          ))}
        </Marquee>
        <Marquee reverse duration={38} className="[--marquee-gap:1rem]">
          {TOOL_PROVIDERS.map((p) => (
            <Chip key={p.name} kind="tool" name={p.name} detail={p.detail} />
          ))}
          {CONNECTORS.map((p) => (
            <Chip key={p.name} kind="connector" name={p.name} detail={p.detail} />
          ))}
        </Marquee>
      </Reveal>

      <div className={`${SECTION_INNER} mt-10`}>
        <p className="font-mono text-[11px] font-bold uppercase tracking-[0.14em] text-[var(--text-on-dark-faint)]">
          Fake model built in — no API key needed to start.
        </p>
      </div>
    </Section>
  );
}
