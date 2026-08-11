"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import { getUsage, type WorkspaceInfo } from "@/lib/api";

/** Bytes as something a person reads. Deliberately coarse — "0.4 GB" is the useful precision
 * for a quota, and more decimal places just invite arithmetic. */
function formatBytes(bytes: number): string {
  if (bytes >= 1024 ** 3) return `${(bytes / 1024 ** 3).toFixed(1)} GB`;
  if (bytes >= 1024 ** 2) return `${Math.round(bytes / 1024 ** 2)} MB`;
  if (bytes >= 1024) return `${Math.round(bytes / 1024)} KB`;
  return `${bytes} B`;
}

function Meter({ used, total }: { used: number; total: number }) {
  const pct = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  return (
    <div
      className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted"
      role="progressbar"
      aria-valuenow={Math.min(used, total)}
      aria-valuemin={0}
      aria-valuemax={total}
    >
      <div
        className="h-full rounded-full bg-foreground transition-[width]"
        style={{ width: `${pct}%` }}
      />
    </div>
  );
}

function Row({
  label,
  used,
  total,
  suffix,
  testId,
  note,
}: {
  label: string;
  used: number;
  total: number;
  suffix?: string;
  testId: string;
  note?: string;
}) {
  return (
    <div className="rounded-lg border border-border p-5" data-testid={testId}>
      <div className="flex items-baseline justify-between gap-4">
        <h2 className="text-sm font-medium">{label}</h2>
        <span className="text-xs text-muted-foreground">
          <span className="text-foreground">{used.toLocaleString()}</span> of{" "}
          {total.toLocaleString()}
          {suffix ? ` ${suffix}` : ""}
        </span>
      </div>
      <Meter used={used} total={total} />
      {note ? <p className="mt-3 text-xs text-muted-foreground">{note}</p> : null}
    </div>
  );
}

export function UsageView() {
  const [info, setInfo] = useState<WorkspaceInfo | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    getUsage()
      .then(setInfo)
      .catch(() => setError(true));
  }, []);

  if (error) {
    return (
      <div className="w-full max-w-3xl px-10 py-8">
        <h1 className="font-heading text-2xl">Usage</h1>
        <p className="mt-4 text-sm text-muted-foreground">
          Couldn&rsquo;t load your usage just now. Try refreshing.
        </p>
      </div>
    );
  }

  const credits = info?.credits;
  const limits = info?.limits;
  const usage = info?.usage;
  const plan = info?.plan ?? "free";

  return (
    <div className="w-full max-w-3xl px-10 py-8">
      <h1 className="font-heading text-2xl">Usage</h1>
      <p className="mt-1 text-sm text-muted-foreground">
        Everything here is shared across all of your workspaces.
      </p>

      <div className="mt-6 space-y-4">
        {credits && credits.allowance > 0 ? (
          <div className="rounded-lg border border-border p-5" data-testid="ws-credits">
            <div className="flex items-baseline justify-between gap-4">
              <h2 className="text-sm font-medium">Usage this month</h2>
              <span className="text-xs text-muted-foreground">
                <span data-testid="ws-credits-remaining" className="text-foreground">
                  {credits.remaining.toLocaleString()}
                </span>{" "}
                {/* "N of M" only reads as sense while N ≤ M. Someone who cancels Plus
                    mid-month keeps the 2,000 credits they paid for while their plan drops to a
                    100 allowance, and the pair rendered as "1,999 of 100 credits left". Drop
                    the denominator rather than the balance: the balance is the true and useful
                    number, and the allowance is explained below. */}
                {credits.remaining > credits.allowance
                  ? "credits left"
                  : `of ${credits.allowance.toLocaleString()} credits left`}
              </span>
            </div>
            <div
              className="mt-3 h-1.5 w-full overflow-hidden rounded-full bg-muted"
              role="progressbar"
              aria-valuenow={Math.min(credits.used, credits.allowance)}
              aria-valuemin={0}
              aria-valuemax={credits.allowance}
              aria-label="Credits used this month"
            >
              <div
                className="h-full rounded-full bg-foreground transition-[width]"
                style={{
                  // Carrying more than a full allowance shows a full bar. `used` is
                  // `max(0, allowance - remaining)`, so that case computes 0% — an empty bar
                  // next to a balance twenty times the allowance, which reads as "you have
                  // nothing" at precisely the moment they have the most.
                  width:
                    credits.remaining > credits.allowance
                      ? "100%"
                      : `${Math.min(100, (credits.used / credits.allowance) * 100)}%`,
                }}
              />
            </div>
            <p className="mt-3 text-xs text-muted-foreground">
              Credits meter what our keys spend on your behalf — runs and the AI assistant. They
              reset each month. Runs on{" "}
              <Link href="/dashboard/settings?tab=workspace" className="text-foreground underline">
                your own API key
              </Link>{" "}
              cost nothing.
            </p>
            {credits.remaining > credits.allowance ? (
              // Said out loud, because "reset" above otherwise reads as a promise. Grants
              // replace rather than accumulate (`credits.grant_monthly`), so next month this
              // balance goes *down* to the plan's allowance. Better they hear it here than
              // discover it as a number that fell overnight.
              <p className="mt-2 text-xs text-muted-foreground" data-testid="ws-credits-carry">
                You&rsquo;re carrying credits from a previous plan. Your plan grants{" "}
                <span className="text-foreground">
                  {credits.allowance.toLocaleString()} a month
                </span>
                , so this balance drops to that at the next reset — spend them before then.
              </p>
            ) : null}
            {credits.remaining === 0 ? (
              <p className="mt-2 text-xs text-amber-600 dark:text-amber-500">
                You&rsquo;re out of credits until they reset. Add your own key in Settings to keep
                running{plan === "free" ? ", or upgrade to Plus" : ""}.
              </p>
            ) : null}
          </div>
        ) : null}

        {limits && usage ? (
          <>
            <Row
              testId="usage-projects"
              label="Projects"
              used={usage.projects}
              total={limits.projects}
              note="Counted across every workspace, so moving a project between them changes nothing."
            />
            <Row
              testId="usage-workspaces"
              label="Workspaces"
              used={usage.workspaces}
              total={limits.workspaces}
            />
            <div className="rounded-lg border border-border p-5" data-testid="usage-storage">
              <div className="flex items-baseline justify-between gap-4">
                <h2 className="text-sm font-medium">Storage</h2>
                <span className="text-xs text-muted-foreground">
                  <span className="text-foreground">{formatBytes(usage.storage_bytes)}</span> of{" "}
                  {formatBytes(limits.storage_bytes)}
                </span>
              </div>
              <Meter used={usage.storage_bytes} total={limits.storage_bytes} />
              <p className="mt-3 text-xs text-muted-foreground">
                {/* Said plainly, because the number is not live and a stale figure that looks
                    live is worse than an honest "as of". */}
                {usage.storage_measured_at
                  ? `Your saved canvases, run history and uploads. Measured daily — last checked ${new Date(
                      usage.storage_measured_at,
                    ).toLocaleDateString()}.`
                  : "Your saved canvases, run history and uploads. Not measured yet — this is checked daily."}
              </p>
            </div>
          </>
        ) : null}

        {plan === "free" ? (
          <p className="text-xs text-muted-foreground">
            Need more?{" "}
            <Link href="/pricing" className="underline">
              See plans
            </Link>
            .
          </p>
        ) : null}
      </div>
    </div>
  );
}
