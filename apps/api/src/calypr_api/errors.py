"""Map an engine exception to a safe, human message for the client SSE `error` event.

The run endpoints (`/runs`, `/share/{token}/runs`) stream to clients — including the **public**
share surface — so a raw `str(exc)` must never reach them: it can carry tracebacks, provider
errors, or internals. This narrows the output to three cases and falls back to a generic message
for everything else (the real error type is still captured to PostHog by the caller)."""

from __future__ import annotations

from calypr_compiler import CompileError
from calypr_runtime import RunError

_GENERIC = "Something went wrong running this agent. Check its settings and try again."


#: Machine-readable hint the web app keys a "Fix it" action off. Kept out of the message text so
#: the copy can change without breaking the client.
PROVIDER_KEY_REJECTED = "provider_key_rejected"

_KEY_REJECTED = (
    "Your {provider} API key was rejected. Check the key saved for this workspace — "
    "it may be revoked, expired, or missing a billing plan."
)
_KEY_REJECTED_UNKNOWN = (
    "A provider rejected the API key saved for this workspace. It may be revoked, "
    "expired, or missing a billing plan."
)


def is_provider_auth_error(exc: Exception) -> bool:
    """True when a provider rejected our credentials (401/403).

    Duck-typed rather than importing every provider SDK: the OpenAI and Anthropic clients both
    expose `status_code`, and their exception classes share the `AuthenticationError` /
    `PermissionDeniedError` names. A new provider that follows neither convention simply falls
    through to the generic message — safe, just less helpful."""
    if getattr(exc, "status_code", None) in (401, 403):
        return True
    return type(exc).__name__ in ("AuthenticationError", "PermissionDeniedError")


def provider_key_error_message(provider: str | None) -> str:
    """Actionable copy for a rejected BYO key. Never includes the key or the provider's raw
    error text — only that the stored key was refused."""
    if provider:
        return _KEY_REJECTED.format(provider=provider)
    return _KEY_REJECTED_UNKNOWN


def run_error_message(exc: Exception) -> str:
    """A client-safe message for an engine failure.

    Deliberately generic about provider auth: this is also what the **public** share surface
    renders, and a share viewer is not the key's owner — telling them the owner's key was
    rejected is neither actionable nor theirs to know. Owner-facing surfaces (`/runs`,
    `/assist`) call `provider_key_error_message` instead."""
    if isinstance(exc, RunError):
        # Already vetted as safe to show verbatim (e.g. the recursion-loop message).
        return str(exc)
    if isinstance(exc, CompileError) and exc.issues:
        # The first issue is already human ("Nodes form a loop with no exit (…)"); drop the
        # "N compile error(s): [code] …" wrapper.
        return exc.issues[0].message
    return _GENERIC
