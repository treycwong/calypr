"use client";

import { Lock } from "lucide-react";
import Link from "next/link";

/**
 * Says what a downgrade locked, and the two ways back.
 *
 * **Not optional.** Everything else about locking is a refusal — a disabled menu item, a 402, a
 * badge. Without this, someone whose subscription lapsed finds their work mysteriously read-only
 * and has no way to learn that it is all still there, or what to do about it. The lock is
 * defensible; a silent lock is not.
 *
 * It names both exits deliberately. "Upgrade" alone would read as a paywall on the user's own
 * data, and it isn't: deleting down to the cap unlocks the rest, for free, permanently.
 */
export function LockedBanner({
  workspaces,
  projects,
  plan,
}: {
  /** How many workspaces are locked. */
  workspaces: number;
  /** How many projects are locked. */
  projects: number;
  plan: string;
}) {
  if (workspaces === 0 && projects === 0) return null;

  const parts: string[] = [];
  if (workspaces > 0) {
    parts.push(`${workspaces} workspace${workspaces === 1 ? "" : "s"}`);
  }
  if (projects > 0) {
    parts.push(`${projects} project${projects === 1 ? "" : "s"}`);
  }

  return (
    <div
      className="mb-4 rounded-lg border border-amber-500/40 bg-amber-500/5 p-4"
      data-testid="locked-banner"
    >
      <div className="flex items-center gap-2">
        <Lock className="h-3.5 w-3.5 shrink-0 text-amber-600 dark:text-amber-500" />
        <span className="text-sm font-medium">
          {parts.join(" and ")} {parts.length === 1 && !parts[0].endsWith("s") ? "is" : "are"}{" "}
          read-only
        </span>
      </div>
      <p className="mt-1.5 text-xs text-muted-foreground">
        {/* The reassurance comes first. "Nothing has been deleted" is the question someone
            actually has when they find their own work locked. */}
        Nothing has been deleted — you can still open, read and export all of it.{" "}
        {plan.charAt(0).toUpperCase() + plan.slice(1)}
        {" includes fewer than you currently have, so the newest are read-only until you’re back"}
        {" under the limit."}
      </p>
      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs">
        <Link
          href="/pricing"
          className="font-medium underline underline-offset-4"
          data-testid="locked-banner-upgrade"
        >
          Upgrade to unlock them
        </Link>
        <span className="text-muted-foreground">
          or delete down to the limit to unlock the rest — free, and permanent.
        </span>
      </div>
    </div>
  );
}
