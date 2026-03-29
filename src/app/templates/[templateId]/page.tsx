import { Metadata } from "next";
import { notFound } from "next/navigation";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { BuyButton } from "@/components/buy-button";
import { getTemplate } from "@/lib/templates";

type Props = { params: Promise<{ templateId: string }> };

export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { templateId } = await params;
  const template = getTemplate(templateId);
  if (!template) return { title: "Not Found — Calypr" };

  return {
    title: `${template.name} — Calypr`,
    description: template.description,
    openGraph: {
      title: `${template.name} — Calypr`,
      description: template.description,
      type: "website",
    },
  };
}

export default async function TemplateDetailPage({ params }: Props) {
  const { templateId } = await params;
  const template = getTemplate(templateId);
  if (!template) notFound();

  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <Link
        href="/templates"
        className="text-sm text-muted-foreground hover:text-foreground transition-colors mb-8 inline-block"
      >
        &larr; All Templates
      </Link>

      <div className="grid gap-12 lg:grid-cols-5 mt-4">
        <div className="lg:col-span-3">
          <div className="rounded-xl border border-border bg-muted aspect-[16/10] flex items-center justify-center">
            <span className="text-muted-foreground">
              Live Preview — {template.name}
            </span>
          </div>
          <p className="mt-4 text-xs text-muted-foreground text-center">
            Preview loads from deployed demo. Fallback shown if unavailable.
          </p>
        </div>

        <div className="lg:col-span-2">
          <div className="flex items-center gap-3 mb-2">
            <h1 className="text-2xl font-medium tracking-tight">
              {template.name}
            </h1>
            {template.status === "coming-soon" && (
              <Badge variant="secondary" className="text-xs">
                Coming Soon
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground leading-relaxed mb-6">
            {template.description}
          </p>

          <div className="flex flex-wrap gap-1.5 mb-6">
            {template.tags.map((tag) => (
              <Badge
                key={tag}
                variant="outline"
                className="text-xs font-normal"
              >
                {tag}
              </Badge>
            ))}
          </div>

          <Separator className="my-6" />

          <div className="text-3xl font-medium mb-6">${template.price}</div>

          <div className="space-y-3">
            <BuyButton
              templateId={template.id}
              disabled={template.status === "coming-soon"}
            />
            <Link href="/docs/how-it-works">
              <Button
                variant="outline"
                size="lg"
                className="w-full rounded-full h-11"
              >
                Customize with AI
              </Button>
            </Link>
          </div>

          <Separator className="my-6" />

          <div className="space-y-4">
            <h3 className="font-medium text-sm">What you get</h3>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>GitHub repo access with full source code</li>
              <li>CLAUDE.md with template intelligence</li>
              <li>Framer Motion animations pre-built</li>
              <li>AI slash commands for customization</li>
              <li>One-command Vercel deployment</li>
              <li>30-day money-back guarantee</li>
            </ul>
          </div>

          <Separator className="my-6" />

          <div className="space-y-3">
            <h3 className="font-medium text-sm">Need help customizing?</h3>
            <p className="text-sm text-muted-foreground">
              Our white-glove service. Fill out a brief, we handle everything.
            </p>
            <Button
              variant="outline"
              size="sm"
              className="rounded-full"
              disabled={template.status === "coming-soon"}
            >
              Customize for Me — $199
            </Button>
          </div>
        </div>
      </div>

      <Separator className="my-16" />

      <section>
        <h2 className="text-xl font-medium tracking-tight mb-6">
          Frequently Asked Questions
        </h2>
        <div className="grid gap-6 md:grid-cols-2">
          <div>
            <h4 className="font-medium text-sm mb-1">
              How does AI customization work?
            </h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Each template includes a CLAUDE.md file that gives Claude Code
              full context about the design system. Open the repo in Claude
              Code, describe your changes, and the AI rewrites components while
              preserving the design integrity.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-sm mb-1">
              Do I need to know how to code?
            </h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Basic familiarity with git and the terminal helps, but Claude Code
              handles the heavy lifting. For non-developers, our white-glove
              customization service handles everything for you.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-sm mb-1">
              Can I get a refund?
            </h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Yes. 30-day money-back guarantee. No questions asked. Your GitHub
              access is revoked on refund.
            </p>
          </div>
          <div>
            <h4 className="font-medium text-sm mb-1">
              Do I get updates?
            </h4>
            <p className="text-sm text-muted-foreground leading-relaxed">
              Yes. Template repos use semver tags. Your dashboard shows when
              updates are available. Migration is manual (no auto-merge) to
              protect your customizations.
            </p>
          </div>
        </div>
      </section>
    </div>
  );
}
