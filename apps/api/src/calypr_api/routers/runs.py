"""Run an agent graph and stream the result as Server-Sent Events.

Each SSE `data:` line is a JSON event: {type: "token"|"usage"|"final"|"error", ...},
terminated by `data: [DONE]`. The web app proxies this stream to the browser.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections.abc import AsyncIterator

from calypr_runtime import run_stream
from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from calypr_api import engine, spend
from calypr_api.deps import run_workspace
from calypr_api.engine import context_for
from calypr_api.errors import run_error_message
from calypr_api.metering import RunRecorder
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import RunRequest

router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/runs", tags=["engine"])
async def create_run(
    req: RunRequest, workspace_id: uuid.UUID = Depends(run_workspace)
) -> StreamingResponse:
    posthog_client.capture(
        "agent_run_started",
        properties={
            "node_count": len(req.graph.nodes) if req.graph.nodes else 0,
            "has_thread": req.thread_id is not None,
        },
    )
    agent_id = uuid.UUID(req.agent_id) if req.agent_id else None

    async def event_stream() -> AsyncIterator[str]:
        # Platform loss firewall: refuse before running if the monthly spend cap is hit.
        if await asyncio.to_thread(spend.over_spend_cap):
            posthog_client.capture("agent_run_spend_capped")
            yield _sse(
                {"type": "error", "message": "Service temporarily unavailable. Try again later."}
            )
            yield "data: [DONE]\n\n"
            return

        # Best-effort metering: self-disables if the DB is unreachable (start.sh's DB-less
        # promise holds). Off-loop so the INSERT never delays the first token.
        recorder = await asyncio.to_thread(
            RunRecorder.start,
            workspace_id,
            source="playground",
            agent_id=agent_id,
            thread_id=req.thread_id,
        )
        completed = False
        try:
            ctx = context_for(req.graph)  # may raise if a provider key is missing
            async for ev in run_stream(
                req.graph,
                ctx,
                req.message,
                thread_id=req.thread_id,
                # Read at call time (not import time) so a lifespan swap to the durable
                # Postgres checkpointer is visible here (WEEK2 plan §C1).
                checkpointer=engine.checkpointer,
            ):
                if ev.type == "token":
                    yield _sse({"type": "token", "text": ev.text})
                elif ev.type == "usage":
                    recorder.add_usage(ev.state or {})
                    yield _sse({"type": "usage", **(ev.state or {})})
                elif ev.type == "final":
                    completed = True
                    yield _sse({"type": "final", "output": ev.output})
            posthog_client.capture(
                "agent_run_completed",
                properties={"node_count": len(req.graph.nodes) if req.graph.nodes else 0},
            )
            await asyncio.to_thread(recorder.finish, "completed")
            yield "data: [DONE]\n\n"
        except Exception as exc:  # surface engine errors to the client stream
            if not completed:
                posthog_client.capture(
                    "agent_run_failed",
                    properties={"error": type(exc).__name__},
                )
            await asyncio.to_thread(recorder.fail)
            yield _sse({"type": "error", "message": run_error_message(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
