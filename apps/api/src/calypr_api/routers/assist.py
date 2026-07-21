"""The AI assistant: turn a prompt into a validated GraphSpec, streamed as SSE.

Same envelope/termination as `/runs` (JSON `data:` lines, ending with `data: [DONE]`).
The assistant only ever emits a *validated* GraphSpec — never executed code, never a DB
write — so the injection surface is a schema, not a shell (AI-ASSISTANT-SPEC.md §8)."""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator
from datetime import date

from calypr_assistant import FakeAssistant, draft_graph
from calypr_model import model_for, provider_of
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from calypr_api import spend
from calypr_api.config import settings
from calypr_api.deps import request_workspace
from calypr_api.metering import RunRecorder
from calypr_api.model_access import (
    FALLBACK_MODEL,
    frontier_provider,
    frontier_substitution_notice,
)
from calypr_api.posthog_client import posthog_client
from calypr_api.provider_keys import resolve_model_keys
from calypr_api.schemas import AssistRequest
from calypr_api.workspace_settings import workspace_assistant_model

router = APIRouter()

# In-memory per-workspace daily counter: {workspace_id: (day, count)}. Reset lazily when the
# day rolls over. An interim guardrail until assist calls are metered as `run_usage` rows.
_daily: dict[uuid.UUID, tuple[date, int]] = {}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _over_daily_cap(workspace_id: uuid.UUID) -> bool:
    today = date.today()
    day, count = _daily.get(workspace_id, (today, 0))
    if day != today:
        count = 0
    if count >= settings.assist_daily_cap:
        return True
    _daily[workspace_id] = (today, count + 1)
    return False


@router.post("/assist", tags=["engine"])
async def create_assist(
    req: AssistRequest, workspace_id: uuid.UUID = Depends(request_workspace)
) -> StreamingResponse:
    # Precedence: an explicit per-request model, then the workspace's Settings choice, then
    # the server-wide env default, then the keyless `fake` path.
    model_id = (
        req.model
        or await asyncio.to_thread(workspace_assistant_model, workspace_id)
        or settings.assistant_model
        or "fake"
    )
    messages = [m.model_dump() for m in req.messages]

    async def event_stream() -> AsyncIterator[str]:
        if _over_daily_cap(workspace_id):
            posthog_client.capture(
                "assist_daily_cap_reached",
                distinct_id=str(workspace_id),
                properties={
                    "daily_cap": settings.assist_daily_cap,
                    "model": model_id,
                },
            )
            yield _sse(
                {
                    "type": "error",
                    "message": f"Daily assistant limit reached ({settings.assist_daily_cap}). "
                    "Try again tomorrow.",
                    "issues": [],
                }
            )
            yield "data: [DONE]\n\n"
            return

        # Platform-wide loss firewall (supersedes the per-workspace daily cap above).
        if await asyncio.to_thread(spend.over_spend_cap):
            posthog_client.capture("assist_spend_capped", distinct_id=str(workspace_id))
            yield _sse(
                {
                    "type": "error",
                    "message": "Service temporarily unavailable. Try again later.",
                    "issues": [],
                }
            )
            yield "data: [DONE]\n\n"
            return

        posthog_client.capture(
            "assist_requested",
            distinct_id=str(workspace_id),
            properties={
                "model": model_id,
                "message_count": len(messages),
                "has_current_graph": req.current_graph is not None,
                "is_refinement": req.current_graph is not None,
            },
        )

        # This is the moment the assistant becomes metered (PRICING-SPEC): same best-effort
        # recorder as `/runs`, tagged source="assist". Self-disables with no DB.
        recorder = await asyncio.to_thread(RunRecorder.start, workspace_id, source="assist")
        # A separate name, not a rebind of `model_id`: assigning the closed-over variable makes
        # it local to this generator and the read on the daily-cap path above would raise
        # UnboundLocalError.
        run_model = model_id
        try:
            if provider_of(run_model) == "fake":
                gen = FakeAssistant().draft(messages, req.current_graph)
            else:
                # BYO keys apply to the assistant exactly as they do to a run: the workspace's
                # key overrides the server env, and a frontier model with no key is refused
                # rather than quietly served on ours.
                keys = await asyncio.to_thread(resolve_model_keys, workspace_id)
                provider = frontier_provider(run_model)
                if provider is not None and provider not in keys:
                    # Degrade to the cheap platform model rather than refusing, and say so —
                    # the notice is what keeps this from being an invisible downgrade.
                    substituted = [(run_model, provider)]
                    run_model = FALLBACK_MODEL
                    posthog_client.capture(
                        "assist_model_substituted",
                        distinct_id=str(workspace_id),
                        properties={"provider": provider, "fallback": FALLBACK_MODEL},
                    )
                    yield _sse(
                        {
                            "type": "notice",
                            "message": frontier_substitution_notice(substituted),
                        }
                    )
                gen = draft_graph(
                    messages,
                    req.current_graph,
                    run_model,
                    client=model_for(run_model, keys or None),
                )
            async for ev in gen:
                payload = ev.payload()
                if payload.get("type") == "usage":
                    recorder.add_usage(payload)
                yield _sse(payload)
            await asyncio.to_thread(recorder.finish, "completed")
            yield "data: [DONE]\n\n"
        except Exception as exc:  # missing provider key, provider outage, etc.
            await asyncio.to_thread(recorder.fail)
            yield _sse({"type": "error", "message": str(exc), "issues": []})
            yield "data: [DONE]\n\n"

    return StreamingResponse(event_stream(), media_type="text/event-stream")
