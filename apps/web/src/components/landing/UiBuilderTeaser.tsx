import { ArrowRight } from "lucide-react";

import { Parallax, Reveal } from "@/components/landing/motion";
import { Badge } from "@/components/spectra/Badge";
import { ButtonLink } from "@/components/spectra/Button";
import { SectionHeading } from "@/components/spectra/SectionHeading";
import { StatusDot } from "@/components/spectra/StatusDot";
import { Section } from "@/components/site/Section";

/**
 * The UI Builder teaser — the next product surface: design chatbot interfaces and sites on
 * top of the agents you drew. The wireframe is pure inline SVG (decorative, aria-hidden,
 * pointer-events-none — never a canvas/WebGL layer) with a few pixels of scroll parallax.
 */

function WireframeVisual() {
  return (
    <div aria-hidden className="pointer-events-none select-none">
      <svg viewBox="0 0 360 260" className="w-full max-w-md">
        {/* browser frame */}
        <rect x="1" y="1" width="358" height="258" rx="10" fill="none" stroke="color-mix(in oklab, var(--foreground) 22%, transparent)" strokeWidth="1" />
        <line x1="1" y1="32" x2="359" y2="32" stroke="color-mix(in oklab, var(--foreground) 18%, transparent)" strokeWidth="1" />
        <circle cx="18" cy="16" r="3.5" fill="none" stroke="color-mix(in oklab, var(--foreground) 30%, transparent)" />
        <circle cx="32" cy="16" r="3.5" fill="none" stroke="color-mix(in oklab, var(--foreground) 30%, transparent)" />
        <rect x="120" y="9" width="120" height="14" rx="7" fill="none" stroke="color-mix(in oklab, var(--foreground) 18%, transparent)" />

        {/* ghost layout blocks */}
        <rect x="20" y="52" width="90" height="188" rx="6" fill="none" stroke="color-mix(in oklab, var(--foreground) 18%, transparent)" strokeDasharray="4 4" />
        <rect x="126" y="52" width="214" height="56" rx="6" fill="none" stroke="color-mix(in oklab, var(--foreground) 18%, transparent)" strokeDasharray="4 4" />
        {/* the lit block — a chat surface taking shape */}
        <rect x="126" y="122" width="214" height="86" rx="6" fill="rgba(92,201,155,0.06)" stroke="#5cc99b" strokeWidth="1" className="glow-breathe" />
        <line x1="142" y1="144" x2="288" y2="144" stroke="rgba(92,201,155,0.45)" strokeWidth="2" strokeLinecap="round" />
        <line x1="142" y1="160" x2="252" y2="160" stroke="rgba(92,201,155,0.3)" strokeWidth="2" strokeLinecap="round" />
        <rect x="142" y="180" width="182" height="16" rx="8" fill="none" stroke="rgba(92,201,155,0.4)" />
        <rect x="126" y="220" width="102" height="20" rx="6" fill="none" stroke="color-mix(in oklab, var(--foreground) 18%, transparent)" strokeDasharray="4 4" />
        {/* cursor */}
        <path d="M300 190 l 10 24 3.5 -9.5 9.5 -3.5 z" fill="#5cc99b" opacity="0.9" />
      </svg>
    </div>
  );
}

export function UiBuilderTeaser() {
  return (
    <Section id="ui-builder">
      <div className="dotted overflow-hidden rounded-[24px] border border-[var(--border-dark)] bg-[var(--surface-card-dark)] shadow-[var(--inner-hairline)]">
        <div className="grid items-center gap-10 p-8 sm:p-12 lg:grid-cols-2">
          <Reveal>
            <Badge tone="accent">
              <StatusDot pulse />
              coming soon
            </Badge>
            <SectionHeading className="mt-6" accent="the UI Builder.">
              Next:
            </SectionHeading>
            <p className="mt-5 max-w-md text-pretty text-lg leading-[1.55] text-[var(--text-on-dark-muted)]">
              Design chatbot interfaces, websites and more — wired straight to the agents you
              drew. The canvas builds the brain; the builder gives it a face.
            </p>
            <ButtonLink href="/waitlist" variant="secondary" className="mt-8">
              Join Beta
              <ArrowRight className="h-4 w-4" strokeWidth={1.75} />
            </ButtonLink>
          </Reveal>
          <Reveal delay={0.15}>
            <Parallax distance={8} className="flex justify-center lg:justify-end">
              <WireframeVisual />
            </Parallax>
          </Reveal>
        </div>
      </div>
    </Section>
  );
}
