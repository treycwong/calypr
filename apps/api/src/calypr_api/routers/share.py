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

from calypr_api import engine, spend, threads
from calypr_api.db.session import SessionLocal
from calypr_api.engine import context_for
from calypr_api.errors import run_error_message
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
        return session.execute(text("SELECT share_agent_name(:t)"), {"t": token}).scalar()


def _claim(token: str) -> tuple[str, uuid.UUID | None, uuid.UUID | None, dict | None]:
    """Atomically claim one run against the token's cap. Returns
    (status, workspace_id, agent_id, graph_spec). Only status='ok' carries the spec."""
    with SessionLocal() as session:
        row = session.execute(
            text("SELECT status, workspace_id, agent_id, graph_spec FROM claim_share_run(:t)"),
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
    """Run a shared agent for an anonymous visitor.

    Every visitor to a share link is anonymous on the same public token, so the conversation id
    is the *only* thing separating two strangers — which makes it a credential, not a convenience.
    The server therefore mints it (`secrets`, 128 bits) and hands it back on the first turn; the
    client echoes it to continue. Accepting the browser's own value, as this used to, meant a
    visitor could name another visitor's thread and resume their conversation. See `threads.py`.
    """
    # A continuation carries a suffix we minted; a first turn gets a fresh one.
    suffix = req.thread_id or threads.new_share_suffix()
    thread_id = threads.share_thread(token, suffix)

    async def event_stream() -> AsyncIterator[str]:
        # Told to the client before anything can fail, so a continuation always has an id to
        # send back even if the run itself is refused.
        yield _sse({"type": "thread", "thread_id": suffix})
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
            # Shared runs execute under the owner's workspace, so they use the owner's BYO keys.
            ctx = await asyncio.to_thread(context_for, spec, workspace_id)
            async for ev in run_stream(
                spec,
                ctx,
                req.message,
                images=req.images,
                thread_id=thread_id,
                checkpointer=engine.checkpointer,  # call-time read (durable saver if swapped in)
            ):
                if ev.type == "token":
                    yield _sse({"type": "token", "text": ev.text})
                elif ev.type == "usage":
                    recorder.add_usage(ev.state or {})
                    yield _sse({"type": "usage", **(ev.state or {})})
                # **`asset` events are deliberately dropped here.** Media still renders for the
                # visitor — the node streams the URL as Markdown in the token above — but nothing
                # is recorded. A share link has no identity to attribute media to, so the only
                # workspace available to hang an `asset` row on is the *owner's*, and filling
                # their Media tab with files strangers generated is a privacy surprise, not a
                # feature. `conversations.py` refuses the transcript for the same reason. Do not
                # "fix" this by symmetry with the `usage` arm above.
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
            yield _sse({"type": "error", "message": run_error_message(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
