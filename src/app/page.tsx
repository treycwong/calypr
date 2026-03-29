import Link from "next/link";
import { Button } from "@/components/ui/button";
import { TemplateCard } from "@/components/template-card";
import { templates } from "@/lib/templates";

export default function Home() {
  return (
    <div className="flex flex-col">
      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-24 lg:py-32">
          <h1 className="text-4xl font-medium tracking-tight sm:text-5xl lg:text-6xl">
            Premium templates.
            <br />
            <span className="text-muted-foreground">Built for AI.</span>
          </h1>
          <p className="mt-6 max-w-lg text-lg text-muted-foreground leading-relaxed">
            Beautiful website templates with embedded Claude Code intelligence.
            Clone. Customize with natural language. Deploy.
          </p>
          <div className="mt-8 flex gap-3">
            <Link href="/templates">
              <Button size="lg" className="rounded-full h-11 px-6">
                Browse Templates
              </Button>
            </Link>
            <Link href="/docs/how-it-works">
              <Button
                variant="outline"
                size="lg"
                className="rounded-full h-11 px-6"
              >
                How It Works
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <h2 className="text-2xl font-medium tracking-tight mb-12">
            Templates
          </h2>
          <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
            {templates.map((template) => (
              <TemplateCard key={template.id} template={template} />
            ))}
          </div>
        </div>
      </section>

      <section className="border-b border-border">
        <div className="mx-auto max-w-6xl px-6 py-24">
          <h2 className="text-2xl font-medium tracking-tight mb-12">
            How it works
          </h2>
          <div className="grid gap-12 sm:grid-cols-3">
            <div>
              <div className="font-mono text-sm text-muted-foreground mb-3">
                01
              </div>
              <h3 className="text-lg font-medium mb-2">Buy a template</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Choose a premium template. Pay once. Get access to the GitHub
                repo instantly.
              </p>
            </div>
            <div>
              <div className="font-mono text-sm text-muted-foreground mb-3">
                02
              </div>
              <h3 className="text-lg font-medium mb-2">Clone and customize</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Open in Claude Code. Say &quot;make this about my SaaS
                startup.&quot; The AI already knows every component and design
                token.
              </p>
            </div>
            <div>
              <div className="font-mono text-sm text-muted-foreground mb-3">
                03
              </div>
              <h3 className="text-lg font-medium mb-2">Deploy</h3>
              <p className="text-sm text-muted-foreground leading-relaxed">
                Push to Vercel or Netlify. One command. Your site is live with
                your customizations.
              </p>
            </div>
          </div>
        </div>
      </section>

      <section>
        <div className="mx-auto max-w-6xl px-6 py-24">
          <div className="rounded-xl border border-border bg-muted/30 p-12 text-center">
            <h2 className="text-2xl font-medium tracking-tight mb-3">
              Ready to build something beautiful?
            </h2>
            <p className="text-muted-foreground mb-8 max-w-md mx-auto">
              Three premium templates at launch. Each with embedded AI
              intelligence. No subscription required.
            </p>
            <Link href="/templates">
              <Button size="lg" className="rounded-full h-11 px-8">
                Get Started
              </Button>
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-border">
        <div className="mx-auto max-w-6xl px-6 py-8 flex items-center justify-between">
          <span className="font-mono text-xs text-muted-foreground">
            calypr
          </span>
          <span className="text-xs text-muted-foreground">
            &copy; {new Date().getFullYear()} Calypr. All rights reserved.
          </span>
        </div>
      </footer>
    </div>
  );
}
