import { Metadata } from "next";
import Link from "next/link";
import { Button } from "@/components/ui/button";

export const metadata: Metadata = {
  title: "How It Works — Calypr",
  description:
    "Learn how Calypr templates work with Claude Code to give you a custom website in minutes.",
};

export default function DocsPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-medium tracking-tight mb-3">How It Works</h1>
      <p className="text-muted-foreground mb-12 max-w-lg">
        Calypr templates are designed from the ground up for AI customization.
        Here&apos;s how the workflow looks end to end.
      </p>

      <div className="space-y-16">
        <section>
          <div className="flex items-center gap-4 mb-4">
            <span className="font-mono text-sm text-muted-foreground">01</span>
            <h2 className="text-xl font-medium tracking-tight">
              Choose a Template
            </h2>
          </div>
          <p className="text-muted-foreground leading-relaxed max-w-2xl">
            Browse our catalog of premium templates. Each one is a complete,
            production-ready website with thoughtful design, smooth animations,
            and optimized performance. Templates are priced at $149 — pay once,
            yours forever.
          </p>
        </section>

        <section>
          <div className="flex items-center gap-4 mb-4">
            <span className="font-mono text-sm text-muted-foreground">02</span>
            <h2 className="text-xl font-medium tracking-tight">
              Get GitHub Access
            </h2>
          </div>
          <p className="text-muted-foreground leading-relaxed max-w-2xl">
            After purchase, you&apos;re added as a collaborator to the template&apos;s
            GitHub repository. Clone it, push to your own Vercel or Netlify
            account. The repo includes full source code, dependencies, and
            deployment configuration.
          </p>
        </section>

        <section>
          <div className="flex items-center gap-4 mb-4">
            <span className="font-mono text-sm text-muted-foreground">03</span>
            <h2 className="text-xl font-medium tracking-tight">
              Customize with AI
            </h2>
          </div>
          <div className="rounded-xl border border-border bg-muted/30 p-6 max-w-2xl mb-4">
            <p className="font-mono text-sm text-muted-foreground mb-2">
              # Open the template in Claude Code
            </p>
            <code className="text-sm">claude &quot;make this about my SaaS startup, use a blue color scheme, and rewrite the hero section&quot;</code>
          </div>
          <p className="text-muted-foreground leading-relaxed max-w-2xl">
            Every template ships with a CLAUDE.md file — a comprehensive
            design document that gives Claude Code full context about the
            template&apos;s components, design tokens, animation patterns, and
            conventions. The AI rewrites your site while preserving the design
            integrity. No more breaking layouts when customizing.
          </p>
        </section>

        <section>
          <div className="flex items-center gap-4 mb-4">
            <span className="font-mono text-sm text-muted-foreground">04</span>
            <h2 className="text-xl font-medium tracking-tight">Deploy</h2>
          </div>
          <div className="rounded-xl border border-border bg-muted/30 p-6 max-w-2xl mb-4">
            <code className="text-sm">git push origin main</code>
          </div>
          <p className="text-muted-foreground leading-relaxed max-w-2xl">
            Push to your connected Vercel or Netlify project. One command. Your
            customized site is live. CLAUDE.md ensures deployment configs are
            already correct.
          </p>
        </section>

        <section>
          <div className="flex items-center gap-4 mb-4">
            <span className="font-mono text-sm text-muted-foreground">05</span>
            <h2 className="text-xl font-medium tracking-tight">
              Get Support Anytime
            </h2>
          </div>
          <p className="text-muted-foreground leading-relaxed max-w-2xl">
            Use the <code className="text-sm">/support</code> slash command in
            Claude Code to create a structured support ticket. Or submit
            through the dashboard. We respond within 48 hours. For non-developers,
            our white-glove customization service handles everything — fill out
            a brief, get a PR with your customizations.
          </p>
        </section>
      </div>

      <div className="mt-16 rounded-xl border border-border bg-muted/30 p-12 text-center">
        <h2 className="text-2xl font-medium tracking-tight mb-3">
          Ready to get started?
        </h2>
        <p className="text-muted-foreground mb-8 max-w-md mx-auto">
          Three premium templates at launch. Each with embedded AI intelligence.
        </p>
        <Link href="/templates">
          <Button size="lg" className="rounded-full h-11 px-8">
            Browse Templates
          </Button>
        </Link>
      </div>
    </div>
  );
}
