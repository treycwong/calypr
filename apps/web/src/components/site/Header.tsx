import Link from "next/link";

import { Wordmark } from "@/components/site/Wordmark";
import { buttonVariants } from "@/components/ui/button";

// Shared sticky site nav (landing + blog). Anchor links are rooted (`/#how`) so they
// navigate home first when clicked from another route.
export function SiteHeader() {
  return (
    <header className="sticky top-0 z-20 border-b border-border/60 bg-background/70 backdrop-blur">
      <div className="mx-auto flex h-14 w-full max-w-6xl items-center justify-between px-5">
        <Link href="/" aria-label="Calypr home">
          <Wordmark />
        </Link>
        <nav className="hidden items-center gap-7 font-mono text-xs text-muted-foreground md:flex">
          <Link href="/#how" className="transition-colors hover:text-foreground">
            How it works
          </Link>
          <Link href="/#templates" className="transition-colors hover:text-foreground">
            Templates
          </Link>
          <Link href="/#code" className="transition-colors hover:text-foreground">
            The code
          </Link>
          <Link href="/blog" className="transition-colors hover:text-foreground">
            Blog
          </Link>
        </nav>
        <div className="flex items-center gap-2">
          <Link href="/sign-in" className={buttonVariants({ variant: "ghost", size: "sm" })}>
            Sign in
          </Link>
          <Link href="/canvas" className={buttonVariants({ size: "sm" })}>
            Open canvas
          </Link>
        </div>
      </div>
    </header>
  );
}
