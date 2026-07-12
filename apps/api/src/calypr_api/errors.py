"""Map an engine exception to a safe, human message for the client SSE `error` event.

The run endpoints (`/runs`, `/share/{token}/runs`) stream to clients — including the **public**
share surface — so a raw `str(exc)` must never reach them: it can carry tracebacks, provider
errors, or internals. This narrows the output to three cases and falls back to a generic message
for everything else (the real error type is still captured to PostHog by the caller)."""

from __future__ import annotations

from calypr_compiler import CompileError
from calypr_runtime import RunError

_GENERIC = "Something went wrong running this agent. Check its settings and try again."


def run_error_message(exc: Exception) -> str:
    """A client-safe message for an engine failure."""
    if isinstance(exc, RunError):
        # Already vetted as safe to show verbatim (e.g. the recursion-loop message).
        return str(exc)
    if isinstance(exc, CompileError) and exc.issues:
        # The first issue is already human ("Nodes form a loop with no exit (…)"); drop the
        # "N compile error(s): [code] …" wrapper.
        return exc.issues[0].message
    return _GENERIC
