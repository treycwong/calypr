"use client";

import { useEffect, useState } from "react";

import { AsciiField } from "./AsciiField";
import { ShareChat } from "./ShareChat";

type State =
  | { status: "loading" }
  | { status: "ready"; name: string }
  | { status: "unavailable" };

// The public surface for a share link. Fetches the agent NAME (never the spec) from the
// anonymous proxy, then floats a glass chat terminal over an interactive ASCII field. A 404
// (unknown/revoked token) resolves to a tasteful "unavailable" state. Everything sits on a
// single full-height, mobile-first stage.
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

  return (
    <main className="relative flex h-[100dvh] w-full flex-col overflow-hidden bg-[#04060a] text-white">
      <AsciiField />
      {/* Vignette: darken the edges so the chat reads clearly over the field. */}
      <div
        aria-hidden="true"
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(120% 90% at 50% 45%, transparent 30%, rgba(4,6,10,0.85) 100%)",
        }}
      />

      <div className="relative z-10 flex h-full w-full items-center justify-center p-4 sm:p-6">
        {state.status === "loading" ? (
          <p className="animate-pulse font-mono text-sm text-cyan-200/70">
            {"> connecting"}
            <span className="ml-0.5 inline-block animate-pulse">▋</span>
          </p>
        ) : state.status === "unavailable" ? (
          <div
            className="flex max-w-sm flex-col items-center gap-3 rounded-2xl border border-white/10 bg-black/40 px-8 py-10 text-center backdrop-blur-xl"
            data-testid="share-unavailable"
          >
            <span className="font-mono text-3xl text-cyan-300/50">⌁</span>
            <h1 className="text-lg font-medium">This link is unavailable</h1>
            <p className="text-sm text-white/50">
              It may have been revoked, or it never existed.
            </p>
          </div>
        ) : (
          <div className="h-full max-h-[720px] w-full max-w-2xl">
            <ShareChat token={token} agentName={state.name} />
          </div>
        )}
      </div>
    </main>
  );
}
