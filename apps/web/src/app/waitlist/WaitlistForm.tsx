"use client";

import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";
import { track } from "@/lib/analytics";
import { joinWaitlist } from "@/lib/api";

export function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email || busy) return;
    setBusy(true);
    setError("");
    try {
      await joinWaitlist(email);
      track("waitlist_joined");
      setDone(true);
    } catch {
      setError("Something went wrong — please try again.");
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <p className="mt-8 text-sm text-foreground">
        You&rsquo;re on the list — we&rsquo;ll be in touch before launch.
      </p>
    );
  }

  return (
    <div className="mt-8 w-full max-w-md">
      <form
        onSubmit={(e) => void handleSubmit(e)}
        className="flex w-full flex-col gap-3 sm:flex-row"
      >
        <input
          type="email"
          required
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="you@example.com"
          aria-label="Email address"
          className="flex-1 rounded-md border border-border bg-card/40 px-4 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-foreground/40"
        />
        <button type="submit" className={buttonVariants()} disabled={busy}>
          {busy ? "Joining…" : "Join Waitlist"}
        </button>
      </form>
      {error ? (
        <p role="alert" className="mt-3 text-sm text-destructive">
          {error}
        </p>
      ) : null}
    </div>
  );
}
