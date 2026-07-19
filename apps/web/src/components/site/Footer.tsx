import { Star } from "lucide-react";
import Link from "next/link";

import { Wordmark } from "@/components/site/Wordmark";

// Shared site footer (landing + blog). Anchor links are rooted for use off the landing page.
export function SiteFooter() {
  return (
    <footer className="mt-auto border-t border-border">
      <div className="mx-auto flex w-full max-w-6xl flex-col items-start justify-between gap-6 px-5 py-10 sm:flex-row sm:items-center">
        <div className="space-y-2">
          <Wordmark />
          <p className="font-mono text-[11px] text-muted-foreground">
            prompt → canvas → code · {new Date().getFullYear()}
          </p>
        </div>
        <div className="flex items-center gap-6 text-xs text-muted-foreground">
          <Link href="/canvas" className="transition-colors hover:text-foreground">
            Canvas
          </Link>
          <Link href="/#templates" className="transition-colors hover:text-foreground">
            Templates
          </Link>
          <Link href="/blog" className="transition-colors hover:text-foreground">
            Blog
          </Link>
          <a
            href="https://github.com/treycwong/calypr"
            className="inline-flex items-center gap-1.5 transition-colors hover:text-foreground"
          >
            <Star className="h-3.5 w-3.5" /> GitHub
          </a>
        </div>
      </div>
    </footer>
  );
}
