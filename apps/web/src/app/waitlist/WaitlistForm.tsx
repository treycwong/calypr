"use client";

import { useState } from "react";

import { buttonVariants } from "@/components/ui/button";

// NOTE: submission is not wired to storage yet — pending a decision on where waitlist
// emails go (API route + DB vs. third-party form). This shows the success state locally
// so the flow is testable; replace `handleSubmit` with a real POST when confirmed.
export function WaitlistForm() {
  const [email, setEmail] = useState("");
  const [done, setDone] = useState(false);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!email) return;
    // TODO: POST to a waitlist endpoint once storage target is confirmed.
    setDone(true);
  }

  if (done) {
    return (
      <p className="mt-8 text-sm text-foreground">
        You&rsquo;re on the list — we&rsquo;ll be in touch before launch.
      </p>
    );
  }

  return (
    <form onSubmit={handleSubmit} className="mt-8 flex w-full max-w-md flex-col gap-3 sm:flex-row">
      <input
        type="email"
        required
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        placeholder="you@example.com"
        aria-label="Email address"
        className="flex-1 rounded-md border border-border bg-card/40 px-4 py-2 text-sm text-foreground outline-none transition-colors placeholder:text-muted-foreground focus:border-foreground/40"
      />
      <button type="submit" className={buttonVariants()}>
        Join Waitlist
      </button>
    </form>
  );
}
