import Link from "next/link";
import type { ReactNode } from "react";

// A glassy pill CTA — backdrop-blur over a translucent dark fill, with an inset light ring that
// brightens on hover and a press-down scale on click. Modeled on the "Hover Button" reference
// (twitter.com/aaroniker_me via 21st.dev), re-tinted to Calypr's brand cyan so it reads as part
// of the dithered-globe hero rather than a generic UI button.
export function HoverButton({ href, children }: { href: string; children: ReactNode }) {
  return (
    <Link
      href={href}
      className="group/cta relative isolate inline-flex items-center gap-2 overflow-hidden rounded-full bg-[rgba(20,28,42,0.55)] px-8 py-3.5 text-base font-medium text-foreground backdrop-blur-lg transition-transform duration-300 before:pointer-events-none before:absolute before:inset-0 before:z-[1] before:rounded-[inherit] before:shadow-[inset_0_0_0_1px_rgba(34,211,238,0.35),inset_0_0_18px_0_rgba(34,211,238,0.12),inset_0_-3px_14px_0_rgba(34,211,238,0.18),0_1px_3px_0_rgba(0,0,0,0.5),0_8px_24px_-4px_rgba(34,211,238,0.25)] before:transition-shadow before:duration-300 hover:scale-[1.03] hover:before:shadow-[inset_0_0_0_1px_rgba(34,211,238,0.6),inset_0_0_24px_0_rgba(34,211,238,0.24),inset_0_-3px_16px_0_rgba(34,211,238,0.32),0_2px_6px_0_rgba(0,0,0,0.5),0_10px_32px_-4px_rgba(34,211,238,0.5)] active:scale-[0.975]"
    >
      {children}
    </Link>
  );
}
