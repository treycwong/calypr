"""Run an agent graph and stream the result as Server-Sent Events.

Each SSE `data:` line is a JSON event: {type: "token"|"node"|"usage"|"asset"|"notice"|"final"
|"conversation"|"error", ...},
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

from calypr_api import conversations, engine, run_access, spend, threads
from calypr_api.connectors import (
    assert_tool_urls_allowed,
    mcp_nodes_without_a_server,
    missing_server_notice,
    resolve_graph,
)
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
    # Namespace the caller's conversation id under their resolved workspace. The request body no
    # longer decides which thread is loaded — `threads.py` explains why that mattered.
    # Clean once and compose, so the suffix stored on `conversation` is exactly the one the
    # thread id was built from.
    thread_suffix = threads.clean_suffix(req.thread_id)
    thread_id = threads.workspace_thread(workspace_id, thread_suffix)

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
            thread_id=thread_id,
        )
        # The durable transcript, on its own session and its own failure domain — see
        # `conversations.py` for why this isn't folded into `RunRecorder`. Started after the
        # gates so a refused run leaves no conversation behind.
        convo = await asyncio.to_thread(
            conversations.ConversationRecorder.start,
            workspace_id,
            thread_suffix=thread_suffix,
            user_text=req.message,
            images=req.images,
            agent_id=agent_id,
            run_id=recorder.run_id,
        )
        if convo.conversation_id is not None:
            # Lets the History tab highlight the active conversation without a fetch. Mirrors the
            # `thread` event the share path already emits.
            yield _sse(
                {
                    "type": "conversation",
                    "conversation_id": str(convo.conversation_id),
                    "thread_id": thread_suffix,
                }
            )
        completed = False
        graph = ctx = None
        try:
            # Resolve MCP connector refs → live url + headers (vault-decrypted, server-side)
            # before compile, off the event loop (DB I/O). No-ops when no connector is used.
            graph = await asyncio.to_thread(resolve_graph, req.graph, workspace_id)
            # An MCP node that resolved to nothing binds zero tools and the run continues — the
            # graceful degradation is deliberate, the silence was not. Same reasoning as the
            # frontier-model notice below: degrade, but never invisibly.
            if toolless := mcp_nodes_without_a_server(graph):
                posthog_client.capture(
                    "agent_run_mcp_no_server",
                    distinct_id=str(workspace_id),
                    properties={"node_count": len(toolless)},
                )
                yield _sse({"type": "notice", "message": missing_server_notice(toolless)})
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
                thread_id=thread_id,
                # Read at call time (not import time) so a lifespan swap to the durable
                # Postgres checkpointer is visible here (WEEK2 plan §C1).
                checkpointer=engine.checkpointer,
            ):
                if ev.type == "token":
                    convo.add_token(ev.text)
                    yield _sse({"type": "token", "text": ev.text})
                elif ev.type == "node":
                    # Display-only: drives the canvas run animation. Not metered.
                    yield _sse({"type": "node", "node_id": ev.node_id, "phase": ev.phase})
                elif ev.type == "usage":
                    recorder.add_usage(ev.state or {})
                    yield _sse({"type": "usage", **(ev.state or {})})
                elif ev.type == "asset":
                    # Media a node generated and durably stored. Recorded so the Media tab can
                    # list it, and forwarded so the tab knows to refetch — the same
                    # record-and-forward the `usage` arm above does.
                    convo.add_asset(ev.state or {})
                    yield _sse({"type": "asset", **(ev.state or {})})
                elif ev.type == "final":
                    completed = True
                    yield _sse({"type": "final", "output": ev.output})
            posthog_client.capture(
                "agent_run_completed",
                properties={"node_count": len(req.graph.nodes) if req.graph.nodes else 0},
            )
            await asyncio.to_thread(recorder.finish, "completed")
            await asyncio.to_thread(convo.finish, "complete")
            yield "data: [DONE]\n\n"
        except (asyncio.CancelledError, GeneratorExit):
            # The client went away mid-answer — closed the Playground, navigated, hit Stop.
            #
            # **Both exceptions, deliberately.** Starlette cancels the task on disconnect
            # (`CancelledError`), but an async generator that is closed or finalized instead
            # gets `GeneratorExit`, and neither is an `Exception` — so the arm below never saw
            # either one and a stopped run left both recorders unflushed with their sessions
            # open. Catching only the first would fix the common path and leave the leak.
            #
            # Both are re-raised at the end: swallowing `GeneratorExit` in particular is a
            # RuntimeError waiting to happen.
            #
            # Flushed synchronously, not through `asyncio.to_thread`: awaiting anything inside a
            # cancelled task re-raises immediately, so the write would never happen. One small
            # transaction on the loop during teardown is the cheaper trade.
            #
            # The `run` row goes to `errored` rather than a new status — the run genuinely did
            # not complete, and "running|completed|errored" is the vocabulary the rest of the
            # metering code and the usage views already read.
            recorder.fail()
            convo.finish("partial")
            raise
        except Exception as exc:  # surface engine errors to the client stream
            if not completed:
                posthog_client.capture(
                    "agent_run_failed",
                    properties={"error": type(exc).__name__},
                )
            await asyncio.to_thread(recorder.fail)
            await asyncio.to_thread(convo.fail)
            yield _sse(_error_payload(exc, graph, ctx))

    return StreamingResponse(event_stream(), media_type="text/event-stream")
