"""PostHog ASGI middleware: wraps each HTTP request in a PostHog context.

Extracts X-POSTHOG-DISTINCT-ID and X-POSTHOG-SESSION-ID headers (set automatically
by posthog-js when tracing_headers is configured) for frontend/backend event
correlation. Falls back to X-Calypr-User-Id for authenticated server-side calls.
"""

from __future__ import annotations

from posthog import identify_context, new_context, set_context_session


class PostHogMiddleware:
    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        headers = {k.lower(): v for k, v in scope.get("headers", [])}

        distinct_id: str | None = (
            headers.get(b"x-posthog-distinct-id", b"").decode("utf-8")
            or headers.get(b"x-calypr-user-id", b"").decode("utf-8")
            or None
        )
        session_id: str | None = headers.get(b"x-posthog-session-id", b"").decode("utf-8") or None

        with new_context():
            if distinct_id:
                identify_context(distinct_id)
            if session_id:
                set_context_session(session_id)
            await self.app(scope, receive, send)
