import Link from "next/link";
import { Badge } from "@/components/ui/badge";

export type TemplateStatus = "coming-soon" | "available";

export interface Template {
  id: string;
  name: string;
  description: string;
  price: number;
  tags: string[];
  previewUrl: string;
  image: string;
  status: TemplateStatus;
}

export function TemplateCard({ template }: { template: Template }) {
  return (
    <Link href={`/templates/${template.id}`} className="group block">
      <div className="rounded-xl border border-border overflow-hidden bg-card transition-shadow group-hover:shadow-md">
        <div className="aspect-[16/10] bg-muted relative">
          <div className="absolute inset-0 flex items-center justify-center">
            <span className="text-sm text-muted-foreground">
              {template.name} Preview
            </span>
          </div>
          {template.status === "coming-soon" && (
            <Badge
              variant="secondary"
              className="absolute top-3 right-3 text-xs"
            >
              Coming Soon
            </Badge>
          )}
        </div>
        <div className="p-5">
          <div className="flex items-start justify-between gap-3 mb-2">
            <h3 className="font-medium tracking-tight">{template.name}</h3>
            <span className="text-sm font-medium text-foreground whitespace-nowrap">
              ${template.price}
            </span>
          </div>
          <p className="text-sm text-muted-foreground leading-relaxed mb-4">
            {template.description}
          </p>
          <div className="flex flex-wrap gap-1.5">
            {template.tags.map((tag) => (
              <Badge key={tag} variant="outline" className="text-xs font-normal">
                {tag}
              </Badge>
            ))}
          </div>
        </div>
      </div>
    </Link>
  );
}
