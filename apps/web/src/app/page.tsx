import { ArrowRight } from "lucide-react";
import Image from "next/image";

import { Capabilities } from "@/components/landing/Capabilities";
import { HoverButton } from "@/components/landing/HoverButton";
import { LandingCta } from "@/components/landing/LandingCta";
import { LandingHeader } from "@/components/landing/LandingHeader";
import { ModelsConnectors } from "@/components/landing/ModelsConnectors";
import { TemplatesShowcase } from "@/components/landing/TemplatesShowcase";
import { UiBuilderTeaser } from "@/components/landing/UiBuilderTeaser";
import { SiteFooter } from "@/components/site/Footer";

export default function Home() {
  return (
    <div className="relative flex min-h-screen flex-col">
      {/* hero — full-bleed background image with a floating nav overlaid */}
      <section className="relative isolate min-h-screen overflow-hidden bg-black text-white">
        {/* background image (public/hero.png) — the LCP element, so eager + priority */}
        <Image
          src="/hero.png"
          alt=""
          aria-hidden
          fill
          priority
          sizes="100vw"
          className="pointer-events-none -z-10 object-cover"
        />
        {/* legibility scrims: darken top (behind nav) and bottom (behind headline) */}
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-gradient-to-b from-black/50 via-transparent to-black/70"
        />

        <LandingHeader />

        {/* headline block, bottom-left */}
        <div className="relative mx-auto flex min-h-screen w-full max-w-7xl flex-col justify-end px-6 pb-20 pt-32">
          <div className="animate-in fade-in slide-in-from-bottom-4 max-w-2xl duration-700">
            <h1 className="text-balance text-[36px] font-medium leading-[1.05] tracking-tight">
              Build your dreams
            </h1>
            <p className="mt-3 text-sm text-white/70 sm:text-base">
              Create your own AI apps easily.
            </p>
            <div className="mt-8">
              {/* Billing is live (Plus is self-serve from /pricing), so the hero now sends
                  people straight to sign-in rather than the waitlist. "Join Beta" in the nav
                  is the separate, still-invite-only path onto the free beta cohort. */}
              <HoverButton href="/sign-in">
                Get Started <ArrowRight className="h-4 w-4 transition-transform duration-300 group-hover/cta:translate-x-0.5" />
              </HoverButton>
            </div>
          </div>
        </div>
      </section>

      {/* inner sections — see components/landing/. Capabilities keeps the #features anchor,
          TemplatesShowcase keeps #templates; the old #how/#code sections folded into them. */}
      <Capabilities />
      <TemplatesShowcase />
      <ModelsConnectors />
      <UiBuilderTeaser />
      <LandingCta />

      {/* footer */}
      <SiteFooter />
    </div>
  );
}
