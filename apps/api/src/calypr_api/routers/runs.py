"""Run an agent graph and stream the result as Server-Sent Events.

Each SSE `data:` line is a JSON event: {type: "token"|"usage"|"final"|"error", ...},
terminated by `data: [DONE]`. The web app proxies this stream to the browser.
"""

from __future__ import annotations

import json
from collections.abc import AsyncIterator

from calypr_runtime import run_stream
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from calypr_api.engine import checkpointer, context_for
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import RunRequest

router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


@router.post("/runs", tags=["engine"])
async def create_run(req: RunRequest) -> StreamingResponse:
    posthog_client.capture(
        "agent_run_started",
        properties={
            "node_count": len(req.graph.nodes) if req.graph.nodes else 0,
            "has_thread": req.thread_id is not None,
        },
    )

    async def event_stream() -> AsyncIterator[str]:
        completed = False
        try:
            ctx = context_for(req.graph)  # may raise if a provider key is missing
            async for ev in run_stream(
                req.graph,
                ctx,
                req.message,
                thread_id=req.thread_id,
                checkpointer=checkpointer,
            ):
                if ev.type == "token":
                    yield _sse({"type": "token", "text": ev.text})
                elif ev.type == "usage":
                    yield _sse({"type": "usage", **(ev.state or {})})
                elif ev.type == "final":
                    completed = True
                    yield _sse({"type": "final", "output": ev.output})
            posthog_client.capture(
                "agent_run_completed",
                properties={"node_count": len(req.graph.nodes) if req.graph.nodes else 0},
            )
            yield "data: [DONE]\n\n"
        except Exception as exc:  # surface engine errors to the client stream
            if not completed:
                posthog_client.capture(
                    "agent_run_failed",
                    properties={"error": type(exc).__name__},
                )
            yield _sse({"type": "error", "message": str(exc)})

    return StreamingResponse(event_stream(), media_type="text/event-stream")
