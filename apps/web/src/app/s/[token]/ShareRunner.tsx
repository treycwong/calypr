"use client";

import { useEffect, useState } from "react";

import { Playground } from "@/components/canvas/Playground";

type State =
  | { status: "loading" }
  | { status: "ready"; name: string }
  | { status: "unavailable" };

// The public, view+run-only surface for a share link. Fetches the agent NAME (never the spec)
// from the anonymous proxy, then runs the agent through `Playground` in share mode. A 404 means
// the link is unknown or revoked → an "unavailable" state.
export function ShareRunner({ token }: { token: string }) {
  const [state, setState] = useState<State>({ status: "loading" });

  useEffect(() => {
    let alive = true;
    fetch(`/api/s/${token}`, { cache: "no-store" })
      .then(async (r) => {
        if (!alive) return;
        if (!r.ok) return setState({ status: "unavailable" });
        const { agent_name } = (await r.json()) as { agent_name: string };
        setState({ status: "ready", name: agent_name });
      })
      .catch(() => alive && setState({ status: "unavailable" }));
    return () => {
      alive = false;
    };
  }, [token]);

  if (state.status === "loading") {
    return (
      <main className="flex h-screen items-center justify-center text-sm text-muted-foreground">
        Loading…
      </main>
    );
  }

  if (state.status === "unavailable") {
    return (
      <main
        className="flex h-screen flex-col items-center justify-center gap-2"
        data-testid="share-unavailable"
      >
        <h1 className="text-lg font-medium">This link is unavailable</h1>
        <p className="text-sm text-muted-foreground">
          It may have been revoked or never existed.
        </p>
      </main>
    );
  }

  return (
    <main className="flex h-screen flex-col">
      <header className="flex items-center gap-2 border-b border-border px-4 py-2">
        <span className="flex h-7 w-7 items-center justify-center rounded-md bg-gradient-to-br from-cyan-400 to-cyan-600 text-sm font-bold text-black">
          C
        </span>
        <span className="text-sm font-medium" data-testid="share-agent-name">
          {state.name}
        </span>
        <span className="text-xs text-muted-foreground">· shared agent</span>
      </header>
      <div className="mx-auto flex w-full max-w-2xl flex-1 flex-col overflow-hidden">
        <Playground shareToken={token} />
      </div>
    </main>
  );
}
