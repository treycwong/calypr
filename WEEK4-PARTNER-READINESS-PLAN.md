# Calypr — Week 4: Partner-readiness polish (execution plan)

**Date:** 2026-07-12 · **Status:** PLAN · Tracks `MVP-EXECUTION-PLAN.md` Month 1 → Week 4
("partner-readiness polish + buffer"). Builds on shipped Week 3 (share links) + the cyclic-graph
fix.

## Context

**Why:** Before inviting design partners, the app must fail gracefully. Today it doesn't: a render
crash white-screens the canvas (no error boundary), failed saves/runs surface as easy-to-miss
inline text (no toasts), and raw engine errors — `CompileError`, `GraphRecursionError` — leak
verbatim into the chat (we saw both in prod this week). Week 4 hardens exactly these edges. Two
PRs, each green-CI'd + prod-verified.

**Verified current state (2026-07-12):** no toast system (no `sonner`, no `Toaster`); no error
boundaries (`error.tsx`/`global-error.tsx` absent); canvas save errors → a `saveMsg` span
(`page.tsx:99,326`); chat errors render `⚠️ {raw message}` (`ShareChat.tsx`, `Playground.tsx`);
run endpoints yield `str(exc)` verbatim (`runs.py:97`, `share.py:135`) — which leaks internals to
the **public** share surface.

## PR-1 — Backend: friendly, safe run errors (API)

**Goal:** never leak a raw exception to a client; give known failures human copy.

- **`services/runtime/.../run.py`** — in `run_stream`, wrap the `astream` loop in
  `try/except GraphRecursionError` and re-raise a `RuntimeError` with clean copy: *"This agent
  looped without finishing — its graph has a cycle with no exit. Remove the back-edge, or add a
  Router/Tool step that can break out."* (Covers conditional loops that slip past the Week-3
  cycle-validation, which only catches all-unconditional cycles.)
- **`routers/runs.py` + `routers/share.py`** — replace the single `except Exception: yield str(exc)`
  with tiered handling (a shared helper, e.g. `calypr_api/errors.py::run_error_message(exc)`):
  - `CompileError` → the first issue's `.message` (already human: "Nodes form a loop with no exit
    (…)"), not the `"N compile error(s): [code] …"` wrapper.
  - `RuntimeError` from the recursion guard → its message.
  - anything else → a generic *"Something went wrong running this agent. Please try again."*
    (raw `str(exc)` is **not** shown — avoids leaking internals on the public surface). Keep the
    existing PostHog capture of the real `type(exc).__name__`.
- **Gates:** pytest — a conditional infinite-loop graph (fake model) yields the friendly loop
  message with no raw traceback; an unknown engine error yields the generic message (not the raw
  string); the cyclic (unconditional) case still yields the compile message. Full pytest + ruff.
- **Ships via Railway** (Python) — independent of the Vercel preview-build issue.

## PR-2 — Web: error boundaries + toasts + wired failures

**Goal:** no white-screens; every failed save/run/share is visible.

- **Toasts (dependency-free).** New `components/ui/toast.tsx` — a small `ToastProvider` +
  `useToast()` (context + a bottom-right stack, auto-dismiss, `variant: default|error`), mounted
  once in `app/layout.tsx`. ~80 lines, no new dep (keeps the minimal-deps stance; avoids adding
  `sonner` while Vercel previews are flaky). Style with the existing tokens
  (`bg-popover`, `border-border`, `text-destructive`).
- **Error boundaries (idiomatic Next App Router).** Add `error.tsx` to the key segments —
  `app/canvas/`, `app/dashboard/`, `app/s/[token]/` — plus a root `app/global-error.tsx`. Each is
  a client component with a friendly message + a "Reload"/"Back to dashboard" action, so a render
  crash degrades to a card instead of a blank page.
- **Wire the failures to toasts:**
  - `canvas/page.tsx` — Save failure, agent-load failure, and Share-mint failure fire an error
    toast (keep the concise inline `saveMsg`/popover states; the toast is the can't-miss signal).
  - `ShareChat.tsx` / `Playground.tsx` — keep the inline `⚠️` in-thread, and additionally toast on
    a run error so it's noticed even when scrolled up.
- **Gates:** `pnpm typecheck` + `pnpm lint` + production `next build`; Playwright
  `phase11-polish.spec.ts` — Save with the API stubbed to fail → an error toast appears; (optional)
  a thrown render error shows the boundary fallback. Verify in-browser (toast on failed save; a
  forced error shows the boundary).
- **Ships via Vercel** — production builds work (preview builds are a separate open issue).

## Verification (end-to-end)

- Backend: `uv run pytest` (new error tests green) against local Postgres; prod smoke — run a
  known-cyclic share link → friendly message (already true for unconditional; add a conditional-loop
  agent to confirm the recursion guard).
- Web: production `next build`; drive the canvas with the API failing (toast) and a forced render
  error (boundary) in the Browser pane.

## Rollout

1. **PR-1** (backend) → CI green → merge → Railway auto-deploy → prod-verify a friendly run error.
2. **PR-2** (web) → CI green → merge → Vercel production build → prod-verify toast + boundary.

Each: full pytest/typecheck/lint/build + Playwright green before merge; `main` is unprotected so a
red **preview** Vercel check doesn't block (production build is what deploys).

## Out of scope (Week 4)

The optional extra template (only if partner calls reveal a gap) and the **blind code-review panel**
(a non-eng Month-1 gate you drive: ~5–8 engineers review generated code, target ≥70% would-merge —
its result decides whether Month-2 buffer goes to codegen quality). Also still open, tracked in
`TODO.md`: Neon cred rotation, the Vercel preview-build issue, and the Week-2 follow-ups.
