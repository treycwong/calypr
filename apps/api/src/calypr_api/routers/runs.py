"""Run an agent graph and stream the result as Server-Sent Events.

Each SSE `data:` line is a JSON event: {type: "token"|"node"|"usage"|"notice"|"final"
|"error", ...},
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

from calypr_api import engine, run_access, spend
from calypr_api.connectors import assert_tool_urls_allowed, resolve_graph
from calypr_api.deps import run_workspace
from calypr_api.engine import context_for
from calypr_api.errors import (
    PROVIDER_KEY_REJECTED,
    is_provider_auth_error,
    provider_key_error_message,
    run_error_message,
)
from calypr_api.metering import RunRecorder
from calypr_api.model_access import (
    FALLBACK_MODEL,
    byo_providers_in_play,
    frontier_substitution_notice,
    provider_label,
    substitute_missing_frontier_models,
)
from calypr_api.posthog_client import posthog_client
from calypr_api.provider_keys import resolve_tool_keys
from calypr_api.schemas import RunRequest

router = APIRouter()


def _sse(payload: dict) -> str:
    return f"data: {json.dumps(payload)}\n\n"


def _error_payload(exc: Exception, graph=None, ctx=None) -> dict:
    """The client `error` event. A rejected BYO key gets actionable copy plus a `code` the web
    app turns into a "Fix it" link; everything else stays generic. `graph`/`ctx` are optional
    because the failure may predate their assignment."""
    if not is_provider_auth_error(exc):
        return {"type": "error", "message": run_error_message(exc)}
    provider = None
    if graph is not None:
        in_play = byo_providers_in_play(graph, getattr(ctx, "model_keys", None))
        # Only name it when there is no ambiguity about which key was refused.
        if len(in_play) == 1:
            provider = provider_label(next(iter(in_play)))
    return {
        "type": "error",
        "message": provider_key_error_message(provider),
        "code": PROVIDER_KEY_REJECTED,
    }


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

        # The plan's ceiling — skipped when every node runs on the workspace's own keys, because
        # then the run costs us nothing and there is nothing to refuse. Checked before the run
        # rather than during, so a refusal is a clear answer instead of a half-finished one; a
        # run already started always finishes (`credits.debit_run` may take the balance
        # negative).
        if gate := await asyncio.to_thread(run_access.check_run_gates, workspace_id, req.graph):
            code, message = gate
            posthog_client.capture(
                "agent_run_credits_exhausted",
                distinct_id=str(workspace_id),
                properties={"workspace_id": str(workspace_id)},
            )
            yield _sse({"type": "error", "message": message, "code": code})
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
        graph = ctx = None
        try:
            # Resolve MCP connector refs → live url + headers (vault-decrypted, server-side)
            # before compile, off the event loop (DB I/O). No-ops when no connector is used.
            graph = await asyncio.to_thread(resolve_graph, req.graph, workspace_id)
            # Same idea for key-backed Tool providers (Unsplash): the DSL carries only the
            # provider name; the key is vault-decrypted into the node just before compile.
            graph = await asyncio.to_thread(resolve_tool_keys, graph, workspace_id)
            assert_tool_urls_allowed(graph)  # SSRF guard on user-supplied HTTP tool URLs
            # Resolve the workspace's BYO provider keys (vault) so the run uses them over env.
            ctx = await asyncio.to_thread(context_for, graph, workspace_id)
            # Frontier models are BYO-key only. Without a key we degrade to the cheap
            # platform-served model rather than dead-ending the run — but never silently:
            # the notice below is what stops this from being an invisible downgrade. The
            # frontier model itself is still never served on the platform key.
            graph, substituted = substitute_missing_frontier_models(graph, ctx.model_keys)
            if substituted:
                posthog_client.capture(
                    "agent_run_model_substituted",
                    properties={
                        "providers": sorted({p for _, p in substituted}),
                        "fallback": FALLBACK_MODEL,
                    },
                )
                yield _sse(
                    {
                        "type": "notice",
                        "message": frontier_substitution_notice(substituted),
                    }
                )
            async for ev in run_stream(
                graph,
                ctx,
                req.message,
                images=req.images,
                thread_id=req.thread_id,
                # Read at call time (not import time) so a lifespan swap to the durable
                # Postgres checkpointer is visible here (WEEK2 plan §C1).
                checkpointer=engine.checkpointer,
            ):
                if ev.type == "token":
                    yield _sse({"type": "token", "text": ev.text})
                elif ev.type == "node":
                    # Display-only: drives the canvas run animation. Not metered.
                    yield _sse({"type": "node", "node_id": ev.node_id, "phase": ev.phase})
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
            yield _sse(_error_payload(exc, graph, ctx))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
