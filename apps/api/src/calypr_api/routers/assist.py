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
from calypr_model import provider_of
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from calypr_api.config import settings
from calypr_api.deps import request_workspace
from calypr_api.metering import RunRecorder
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import AssistRequest

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
    model_id = req.model or settings.assistant_model or "fake"
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
        try:
            if provider_of(model_id) == "fake":
                gen = FakeAssistant().draft(messages, req.current_graph)
            else:
                gen = draft_graph(messages, req.current_graph, model_id)
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
