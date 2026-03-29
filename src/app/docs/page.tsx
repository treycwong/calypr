import { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "Docs — Calypr",
  description: "Documentation and guides for Calypr templates.",
};

const docs = [
  {
    href: "/docs/how-it-works",
    title: "How It Works",
    description: "End-to-end workflow: buy, clone, customize, deploy.",
  },
];

export default function DocsIndexPage() {
  return (
    <div className="mx-auto max-w-4xl px-6 py-16">
      <h1 className="text-3xl font-medium tracking-tight mb-8">Docs</h1>
      <div className="space-y-4">
        {docs.map((doc) => (
          <Link
            key={doc.href}
            href={doc.href}
            className="block rounded-xl border border-border p-5 hover:bg-muted/30 transition-colors"
          >
            <h3 className="font-medium mb-1">{doc.title}</h3>
            <p className="text-sm text-muted-foreground">{doc.description}</p>
          </Link>
        ))}
      </div>
    </div>
  );
}
