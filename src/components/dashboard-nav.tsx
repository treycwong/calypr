"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const navItems = [
  { href: "/dashboard/templates", label: "Templates" },
  { href: "/dashboard/settings", label: "Settings" },
  { href: "/dashboard/support", label: "Support" },
  { href: "/dashboard/customize", label: "Customize" },
];

export function DashboardNav() {
  const pathname = usePathname();

  return (
    <nav className="flex gap-6 border-b border-border pb-px">
      {navItems.map((item) => {
        const active = pathname.startsWith(item.href);
        return (
          <Link
            key={item.href}
            href={item.href}
            className={`text-sm pb-2 transition-colors ${
              active
                ? "text-foreground border-b-2 border-foreground font-medium"
                : "text-muted-foreground hover:text-foreground"
            }`}
          >
            {item.label}
          </Link>
        );
      })}
    </nav>
  );
}
