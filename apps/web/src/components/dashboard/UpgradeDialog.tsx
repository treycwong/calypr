"use client";

import { Check } from "lucide-react";
import Link from "next/link";

import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Button, buttonVariants } from "@/components/ui/button";
import { track } from "@/lib/analytics";
import { PLAN_LIMITS } from "@/lib/plans";
import { cn } from "@/lib/utils";

/** What the account ran out of. `message` is the server's own sentence, sent with the 402 — it
 *  knows the exact count and plan, so when it speaks we quote it rather than reconstruct it. */
export type CapDetail = { limit?: number; message?: string };

/** The two plans as one row each, so the columns line up and the difference is readable across.
 *
 *  A vertical feature list per plan makes the reader hold Free in their head while they scan
 *  Plus. Four rows, same order, both columns — the comparison is the product here, not the
 *  feature copy. Numbers come from `@/lib/plans`, the module /pricing and checkout also read. */
const ROWS: { label: string; free: string; plus: string }[] = [
  { label: "Projects", free: `${PLAN_LIMITS.free.projects}`, plus: `${PLAN_LIMITS.plus.projects}` },
  {
    label: "Workspaces",
    free: `${PLAN_LIMITS.free.workspaces}`,
    plus: `${PLAN_LIMITS.plus.workspaces}`,
  },
  {
    label: "Credits / month",
    free: PLAN_LIMITS.free.credits.toLocaleString(),
    plus: PLAN_LIMITS.plus.credits.toLocaleString(),
  },
  { label: "Code export", free: "—", plus: "Included" },
];

/** The paywall a free account meets when it runs out of project slots.
 *
 *  Creating a project is the one action on this dashboard a plan can refuse, and it used to fail
 *  with "save failed (402)" — a status code, shown to someone in the middle of starting work.
 */
export function UpgradeDialog({
  open,
  onOpenChange,
  detail,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  detail?: CapDetail;
}) {
  const limit = detail?.limit ?? PLAN_LIMITS.free.projects;

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm" data-testid="upgrade-dialog">
        <DialogHeader>
          <DialogTitle className="text-base">You&rsquo;ve used all {limit} projects</DialogTitle>
          <DialogDescription className="text-xs">
            {detail?.message ?? `Your plan includes ${limit} projects, pooled across workspaces.`}{" "}
            Upgrade for more room, or delete one you&rsquo;re done with.
          </DialogDescription>
        </DialogHeader>

        <div className="overflow-hidden rounded-lg border border-border">
          <div className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-4 border-b border-border bg-muted/40 px-3 py-2">
            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">Plan</span>
            <span className="text-right text-[11px] font-medium text-muted-foreground">
              Free
              <span className="ml-1 font-normal opacity-70">now</span>
            </span>
            <span className="text-right text-[11px] font-medium">
              Plus
              <span className="ml-1 font-normal text-muted-foreground">$20/mo</span>
            </span>
          </div>
          {ROWS.map((row) => (
            <div
              key={row.label}
              className="grid grid-cols-[1fr_auto_auto] items-baseline gap-x-4 px-3 py-1.5 text-xs"
              data-testid="plan-row"
            >
              <span className="text-muted-foreground">{row.label}</span>
              <span className="text-right tabular-nums text-muted-foreground">{row.free}</span>
              <span className="flex items-center justify-end gap-1 text-right font-medium tabular-nums">
                {row.plus === "Included" ? (
                  <Check className="h-3 w-3" />
                ) : null}
                {row.plus === "Included" ? "Yes" : row.plus}
              </span>
            </div>
          ))}
        </div>

        <DialogFooter className="gap-2 sm:justify-end">
          <Button variant="outline" size="sm" onClick={() => onOpenChange(false)} data-testid="upgrade-dismiss">
            Cancel
          </Button>
          <Link
            href="/checkout?plan=plus"
            className={cn(buttonVariants({ size: "sm" }))}
            data-testid="upgrade-cta"
            onClick={() => track("project_cap_upgrade_clicked")}
          >
            Upgrade to Plus
          </Link>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
