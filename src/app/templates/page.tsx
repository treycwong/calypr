import { Metadata } from "next";
import { TemplateCard } from "@/components/template-card";
import { templates } from "@/lib/templates";

export const metadata: Metadata = {
  title: "Templates — Calypr",
  description:
    "Premium website templates with embedded AI intelligence. Browse our catalog.",
};

export default function TemplatesPage() {
  return (
    <div className="mx-auto max-w-6xl px-6 py-16">
      <h1 className="text-3xl font-medium tracking-tight mb-2">Templates</h1>
      <p className="text-muted-foreground mb-12 max-w-lg">
        Premium templates built for AI customization. Buy once, customize
        forever.
      </p>
      <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-3">
        {templates.map((template) => (
          <TemplateCard key={template.id} template={template} />
        ))}
      </div>
    </div>
  );
}
