"use client";

import { Check, Lock } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { joinWaitlist, startCheckout } from "@/lib/api";

/** Mirrors the Plus column on /pricing. Short on purpose — this page confirms a decision that
 * was already made a click ago, it doesn't re-sell it. */
const INCLUDED = [
  "Code export — the generated Python, yours to edit and run",
  "20 projects",
  "2,000 credits a month across runs and the assistant",
  "Platform keys on every model",
];

export function CheckoutView({
  email: initialEmail,
  enabled,
}: {
  email: string;
  /** Whether the API can take a payment right now (Stripe keys present). */
  enabled: boolean;
}) {
  const [email, setEmail] = useState(initialEmail);
  const [state, setState] = useState<"idle" | "saving" | "done" | "error">("idle");
  // Seeded from the server so the page is honest on first paint; a 503 from checkout can still
  // flip it off, which covers keys being pulled between render and click.
  const [payable, setPayable] = useState(enabled);
  const [payError, setPayError] = useState("");

  async function pay() {
    setPayError("");
    setState("saving");
    try {
      const url = await startCheckout();
      if (url) {
        window.location.href = url; // Stripe hosts the form; no card data touches us.
        return;
      }
      setPayable(false); // 503 — billing isn't configured yet.
    } catch {
      setPayError("Could not start checkout. Try again in a moment.");
    }
    setState("idle");
  }

  async function notifyMe() {
    if (!email.trim()) return;
    setState("saving");
    try {
      // `source` separates these from landing-page signups: someone who reached checkout is a
      // materially stronger signal than someone who left an address on the home page.
      await joinWaitlist(email.trim(), "checkout");
      setState("done");
    } catch {
      setState("error");
    }
  }

  return (
    <>
      <h1 className="text-2xl font-semibold tracking-tight">Upgrade to Plus</h1>

      <div className="mt-8 rounded-xl border border-border bg-card/40 p-6">
        <div className="flex items-baseline justify-between gap-4">
          <div>
            <div className="font-medium">Calypr Plus</div>
            <div className="text-xs text-muted-foreground">Monthly, cancel any time</div>
          </div>
          <div className="text-right">
            <span className="text-2xl font-semibold tracking-tight">$20</span>
            <span className="text-sm text-muted-foreground">/month</span>
          </div>
        </div>

        <ul className="mt-6 space-y-2.5 border-t border-border pt-6">
          {INCLUDED.map((item) => (
            <li key={item} className="flex gap-2.5 text-sm leading-relaxed">
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
              <span>{item}</span>
            </li>
          ))}
        </ul>
      </div>

      {payable ? (
        <div className="mt-6 flex flex-col items-start gap-2">
          <Button onClick={() => void pay()} disabled={state === "saving"} data-testid="checkout-pay">
            {state === "saving" ? "Starting…" : "Continue to payment"}
          </Button>
          {payError ? <span className="text-xs text-destructive">{payError}</span> : null}
          <p className="text-xs text-muted-foreground">
            Payment is handled by Stripe — your card details never reach us.
          </p>
        </div>
      ) : null}

      {/* Shown only once the API has told us billing isn't on yet. A fake card form would be
          worse than a delay, and this way the honest message is never a guess. */}
      {!payable ? (
      <div className="mt-6 rounded-xl border border-border bg-card/40 p-6" data-testid="checkout-pending">
        <div className="flex items-center gap-2 text-sm font-medium">
          <Lock className="h-4 w-4 text-muted-foreground" />
          Card payments open shortly
        </div>
        <p className="mt-2 text-sm leading-relaxed text-muted-foreground">
          We&rsquo;re finishing billing now. Leave your address and we&rsquo;ll switch Plus on
          for your workspace the day it opens — nothing to pay until then.
        </p>

        {state === "done" ? (
          <p className="mt-4 text-sm text-emerald-600 dark:text-emerald-500" data-testid="checkout-done">
            You&rsquo;re on the list. We&rsquo;ll email {email} when Plus opens.
          </p>
        ) : (
          <div className="mt-4 flex flex-wrap items-center gap-2">
            <Input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@company.com"
              className="max-w-xs"
              data-testid="checkout-email"
              aria-label="Email address"
            />
            <Button
              onClick={() => void notifyMe()}
              disabled={!email.trim() || state === "saving"}
              data-testid="checkout-notify"
            >
              {state === "saving" ? "Saving…" : "Notify me"}
            </Button>
            {state === "error" ? (
              <span className="text-xs text-destructive">
                That didn&rsquo;t save — try again in a moment.
              </span>
            ) : null}
          </div>
        )}
      </div>
      ) : null}

      <p className="mt-6 text-center text-xs text-muted-foreground">
        <Link href="/pricing" className="underline underline-offset-4">
          Back to pricing
        </Link>
      </p>
    </>
  );
}
