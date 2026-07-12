"""Public share-link surface (WEEK3 plan §B) — the anonymous run path.

These endpoints are **public by construction**: no workspace dependency, no auth headers. A
logged-out visitor holding an unguessable token can read the agent's *name* and run it, but the
GraphSpec is loaded server-side inside the run handler and is **never** serialized to the client.
Anonymous reads bypass RLS through the `share_agent_name` / `claim_share_run` SECURITY DEFINER
functions (defined in migration 0005), not the app role's privilege.

The run path streams byte-identically to `/runs` (same SSE envelope + `[DONE]`), so the web
playground renders share runs and errors unchanged.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from calypr_dsl import GraphSpec
from calypr_runtime import run_stream
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy import text

from calypr_api import engine, spend
from calypr_api.db.session import SessionLocal
from calypr_api.engine import context_for
from calypr_api.metering import RunRecorder
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import ShareRunRequest

router = APIRouter()

# Human-readable reason → the message the visitor sees. `not_found` is handled as a 404 on GET
# but as an in-stream error on POST (the stream has already started 200-ing).
_DENY_MESSAGE = {
    "revoked": "This link was revoked.",
    "cap": "This link has reached its run limit.",
    "not_found": "This link is no longer available.",
}


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _agent_name(token: str) -> str | None:
    """The shared agent's name, or None if the token is unknown/revoked. Never the spec."""
    with SessionLocal() as session:
        return session.execute(
            text("SELECT share_agent_name(:t)"), {"t": token}
        ).scalar()


def _claim(token: str) -> tuple[str, uuid.UUID | None, uuid.UUID | None, dict | None]:
    """Atomically claim one run against the token's cap. Returns
    (status, workspace_id, agent_id, graph_spec). Only status='ok' carries the spec."""
    with SessionLocal() as session:
        row = session.execute(
            text(
                "SELECT status, workspace_id, agent_id, graph_spec FROM claim_share_run(:t)"
            ),
            {"t": token},
        ).one()
        session.commit()  # the UPDATE inside claim_share_run must persist the incremented count
        return row.status, row.workspace_id, row.agent_id, row.graph_spec


@router.get("/share/{token}", tags=["share"])
async def get_share(token: str) -> dict:
    """The shared agent's name only — 404 if the token is unknown or revoked. This response is
    asserted (in tests) to never contain the spec: it's just the name."""
    name = await asyncio.to_thread(_agent_name, token)
    if name is None:
        raise HTTPException(status_code=404, detail="share link not found")
    return {"agent_name": name}


@router.post("/share/{token}/runs", tags=["share"])
async def create_share_run(token: str, req: ShareRunRequest) -> StreamingResponse:
    # Anonymous visitors must not collide on / resume each other's threads.
    thread_id = f"share:{token}:{req.thread_id or uuid.uuid4()}"

    async def event_stream() -> AsyncIterator[str]:
        # Platform loss firewall first — anonymous share traffic can't blow past the monthly cap.
        if await asyncio.to_thread(spend.over_spend_cap):
            posthog_client.capture("share_run_spend_capped")
            yield _sse(
                {"type": "error", "message": "Service temporarily unavailable. Try again later."}
            )
            yield "data: [DONE]\n\n"
            return

        # Atomic cap gate: the conditional UPDATE both checks and increments (race-free).
        status_, workspace_id, agent_id, graph_spec = await asyncio.to_thread(_claim, token)
        if status_ != "ok":
            yield _sse({"type": "error", "message": _DENY_MESSAGE.get(status_, "Unavailable.")})
            yield "data: [DONE]\n\n"
            return

        spec = GraphSpec.model_validate(graph_spec)  # loaded server-side; never sent to client
        recorder = await asyncio.to_thread(
            RunRecorder.start,
            workspace_id,
            source="share",
            agent_id=agent_id,
            thread_id=thread_id,
        )
        completed = False
        try:
            ctx = context_for(spec)
            async for ev in run_stream(
                spec,
                ctx,
                req.message,
                thread_id=thread_id,
                checkpointer=engine.checkpointer,  # call-time read (durable saver if swapped in)
            ):
                if ev.type == "token":
                    yield _sse({"type": "token", "text": ev.text})
                elif ev.type == "usage":
                    recorder.add_usage(ev.state or {})
                    yield _sse({"type": "usage", **(ev.state or {})})
                elif ev.type == "final":
                    completed = True
                    yield _sse({"type": "final", "output": ev.output})
            posthog_client.capture("share_run", properties={"agent_id": str(agent_id)})
            await asyncio.to_thread(recorder.finish, "completed")
            yield "data: [DONE]\n\n"
        except Exception as exc:  # surface engine errors to the client stream, like /runs
            if not completed:
                posthog_client.capture("share_run_failed", properties={"error": type(exc).__name__})
            await asyncio.to_thread(recorder.fail)
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
