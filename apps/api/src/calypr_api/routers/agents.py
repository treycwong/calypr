"""Agent CRUD + graph compile/validate.

Each request resolves its workspace via the `tenant` dependency (the signed-in user's personal
workspace in prod, the shared dev workspace locally); queries scope to it explicitly, with the
RLS policy as defense-in-depth.
"""

from __future__ import annotations

import secrets
import uuid

from calypr_codegen import generate_python
from calypr_compiler import FRAMEWORKS, TEMPLATES, validate_graph
from calypr_dsl import GraphSpec
from calypr_roundtrip import parse_python
from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from calypr_api import entitlements
from calypr_api.assistant_models import (
    AssistantModelOption,
    assistant_model_options,
    is_allowed,
)
from calypr_api.db.models import Agent, ShareLink, Workspace
from calypr_api.deps import Tenant, may_export_code, require_code_export, tenant
from calypr_api.llm_providers import LLMProvider, llm_providers
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import (
    AgentCreate,
    AgentDetail,
    AgentSummary,
    AgentUpdate,
    CodegenResponse,
    CompileResponse,
    ParseRequest,
    ParseResponse,
    ShareCreate,
    ShareInfo,
    TemplateInfo,
    WorkspaceInfo,
    WorkspaceUpdate,
)

router = APIRouter()

# Default per-link run cap when the owner doesn't specify one. Share links are public and
# unauthenticated, so we fail safe with a finite cap; owners can raise it per link.
DEFAULT_SHARE_RUN_CAP = 25


@router.post("/compile", response_model=CompileResponse, tags=["engine"])
def compile_spec(graph: GraphSpec) -> CompileResponse:
    issues = validate_graph(graph)
    ok = not any(i.severity == "error" for i in issues)
    posthog_client.capture(
        "graph_compiled",
        properties={
            "ok": ok,
            "error_count": sum(1 for i in issues if i.severity == "error"),
            "warning_count": sum(1 for i in issues if i.severity == "warning"),
            "node_count": len(graph.nodes) if graph.nodes else 0,
        },
    )
    return CompileResponse(ok=ok, issues=issues)


#: Lines of the generated file an unentitled workspace sees. Enough to reach the `State` class —
#: real imports, real channel names — because a preview that shows nothing proves nothing: the
#: pitch is that this code is good, so the reader has to see some of it to want the rest.
PREVIEW_LINES = 14


@router.post("/codegen", response_model=CodegenResponse, tags=["engine"])
def codegen_spec(graph: GraphSpec, request: Request) -> CodegenResponse:
    """The 'code' altitude: render the graph as ownable Python (LangGraph).

    Entitled workspaces get the whole file; everyone else gets `PREVIEW_LINES` of it and a
    `truncated` flag the client turns into a blurred tail plus an upgrade prompt. The cut is
    made **here** rather than in the browser — a CSS blur over the full text is a decoration,
    not a paywall, since the response sits in the network tab either way."""
    code = generate_python(graph)
    total_lines = code.count("\n") + 1
    truncated = not may_export_code(request)
    if truncated:
        code = "\n".join(code.split("\n")[:PREVIEW_LINES]) + "\n"
    posthog_client.capture(
        "graph_codegen_requested",
        properties={
            "node_count": len(graph.nodes) if graph.nodes else 0,
            "truncated": truncated,
        },
    )
    return CodegenResponse(code=code, truncated=truncated, total_lines=total_lines)


@router.post(
    "/parse",
    response_model=ParseResponse,
    tags=["engine"],
    dependencies=[Depends(require_code_export)],
)
def parse_code(body: ParseRequest) -> ParseResponse:
    """The reverse of `/codegen`: edited Python back to a GraphSpec the canvas can render.

    Pure — it reads no workspace data, only the code in the request — but **entitlement-gated**,
    because code export is what a paid plan buys (`require_code_export`; unenforced in dev/CI).
    Never raises on bad input: `parse_python` degrades unrecognised functions to Code nodes and
    reports them, so an entitled caller always gets a renderable graph plus an honest account of
    what wasn't understood."""
    result = parse_python(body.code)
    posthog_client.capture(
        "graph_parse_requested",
        properties={
            "node_count": len(result.spec.nodes) if result.spec.nodes else 0,
            "degraded_count": len(result.degraded_nodes),
            "warning_count": len(result.warnings),
            "bytes": len(body.code),
        },
    )
    return ParseResponse(
        graph=result.spec,
        warnings=result.warnings,
        degraded_nodes=result.degraded_nodes,
    )


@router.get("/templates", response_model=list[TemplateInfo], tags=["engine"])
def list_templates() -> list[TemplateInfo]:
    """The canvas starter gallery: frameworks (agent patterns) + templates (use cases)."""
    return [
        TemplateInfo(id=t.id, name=t.name, description=t.description or "", kind=kind, graph=t)
        for kind, group in (("framework", FRAMEWORKS), ("template", TEMPLATES))
        for t in group
    ]


def _get_owned(session: Session, workspace_id: uuid.UUID, agent_id: str) -> Agent:
    try:
        pk = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    agent = session.get(Agent, pk)
    if agent is None or agent.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.post("/agents", response_model=AgentDetail, tags=["agents"])
def create_agent(body: AgentCreate, t: Tenant = Depends(tenant)) -> AgentDetail:
    agent = Agent(workspace_id=t.workspace_id, name=body.name, graph_spec=body.graph.model_dump())
    t.session.add(agent)
    t.session.commit()
    t.session.refresh(agent)
    posthog_client.capture(
        "agent_created",
        distinct_id=str(t.workspace_id),
        properties={
            "agent_id": str(agent.id),
            "node_count": len(body.graph.nodes) if body.graph.nodes else 0,
        },
    )
    return AgentDetail(
        id=str(agent.id), name=agent.name, graph=GraphSpec.model_validate(agent.graph_spec)
    )


@router.get("/agents", response_model=list[AgentSummary], tags=["agents"])
def list_agents(t: Tenant = Depends(tenant)) -> list[AgentSummary]:
    rows = (
        t.session.execute(
            select(Agent)
            .where(Agent.workspace_id == t.workspace_id)
            .order_by(Agent.updated_at.desc())
        )
        .scalars()
        .all()
    )
    return [AgentSummary(id=str(a.id), name=a.name, updated_at=a.updated_at) for a in rows]


@router.get("/agents/{agent_id}", response_model=AgentDetail, tags=["agents"])
def get_agent(agent_id: str, t: Tenant = Depends(tenant)) -> AgentDetail:
    a = _get_owned(t.session, t.workspace_id, agent_id)
    return AgentDetail(id=str(a.id), name=a.name, graph=GraphSpec.model_validate(a.graph_spec))


@router.put("/agents/{agent_id}", response_model=AgentDetail, tags=["agents"])
def update_agent(agent_id: str, body: AgentUpdate, t: Tenant = Depends(tenant)) -> AgentDetail:
    a = _get_owned(t.session, t.workspace_id, agent_id)
    changed: list[str] = []
    if body.name is not None:
        a.name = body.name
        changed.append("name")
    if body.graph is not None:
        a.graph_spec = body.graph.model_dump()
        changed.append("graph")
    t.session.commit()
    t.session.refresh(a)
    posthog_client.capture(
        "agent_updated",
        distinct_id=str(t.workspace_id),
        properties={
            "agent_id": str(a.id),
            "fields_changed": changed,
        },
    )
    return AgentDetail(id=str(a.id), name=a.name, graph=GraphSpec.model_validate(a.graph_spec))


@router.delete("/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["agents"])
def delete_agent(agent_id: str, t: Tenant = Depends(tenant)) -> Response:
    a = _get_owned(t.session, t.workspace_id, agent_id)
    t.session.delete(a)
    t.session.commit()
    posthog_client.capture(
        "agent_deleted",
        distinct_id=str(t.workspace_id),
        properties={"agent_id": agent_id},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)


def _share_info(s: ShareLink) -> ShareInfo:
    return ShareInfo(
        token=s.token,
        run_cap=s.run_cap,
        run_count=s.run_count,
        created_at=s.created_at,
        revoked_at=s.revoked_at,
    )


@router.post("/agents/{agent_id}/share", response_model=ShareInfo, tags=["share"])
def create_share(agent_id: str, body: ShareCreate, t: Tenant = Depends(tenant)) -> ShareInfo:
    _get_owned(t.session, t.workspace_id, agent_id)  # 404s if not the tenant's agent
    cap = body.run_cap if body.run_cap is not None else DEFAULT_SHARE_RUN_CAP
    link = ShareLink(
        token=secrets.token_urlsafe(16),  # 128-bit, unguessable
        agent_id=uuid.UUID(agent_id),
        workspace_id=t.workspace_id,
        run_cap=cap,
    )
    t.session.add(link)
    t.session.commit()
    t.session.refresh(link)
    posthog_client.capture(
        "share_created",
        distinct_id=str(t.workspace_id),
        properties={"agent_id": agent_id, "run_cap": cap},
    )
    return _share_info(link)


@router.get("/agents/{agent_id}/shares", response_model=list[ShareInfo], tags=["share"])
def list_shares(agent_id: str, t: Tenant = Depends(tenant)) -> list[ShareInfo]:
    _get_owned(t.session, t.workspace_id, agent_id)
    rows = (
        t.session.execute(
            select(ShareLink)
            .where(
                ShareLink.agent_id == uuid.UUID(agent_id),
                ShareLink.workspace_id == t.workspace_id,
            )
            .order_by(ShareLink.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_share_info(s) for s in rows]


@router.delete("/agents/{agent_id}/share/{token}", response_model=ShareInfo, tags=["share"])
def revoke_share(agent_id: str, token: str, t: Tenant = Depends(tenant)) -> ShareInfo:
    _get_owned(t.session, t.workspace_id, agent_id)
    link = (
        t.session.execute(
            select(ShareLink).where(
                ShareLink.token == token,
                ShareLink.agent_id == uuid.UUID(agent_id),
                ShareLink.workspace_id == t.workspace_id,
            )
        )
        .scalars()
        .first()
    )
    if link is None:
        raise HTTPException(status_code=404, detail="share link not found")
    if link.revoked_at is None:  # idempotent: re-revoking keeps the original timestamp
        link.revoked_at = func.now()
        t.session.commit()
        t.session.refresh(link)
        posthog_client.capture(
            "share_revoked",
            distinct_id=str(t.workspace_id),
            properties={"agent_id": agent_id},
        )
    return _share_info(link)


@router.get("/workspaces/current", response_model=WorkspaceInfo, tags=["workspace"])
def get_current_workspace(t: Tenant = Depends(tenant)) -> WorkspaceInfo:
    ws = t.session.get(Workspace, t.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    # Redeem a beta invite here rather than on every request: the client asks for its workspace
    # once per page load, and this is exactly when it needs to know what it's entitled to.
    if entitlements.grant_beta_if_invited(t.session, ws, t.email):
        t.session.commit()
        posthog_client.capture(
            "beta_access_granted",
            distinct_id=str(ws.id),
            properties={"workspace_id": str(ws.id)},
        )
    return WorkspaceInfo(
        id=str(ws.id),
        name=ws.name,
        plan=ws.plan,
        signed_in_as=t.email,
        assistant_model=ws.assistant_model,
    )


@router.get("/assistant-models", response_model=list[AssistantModelOption], tags=["workspace"])
def list_assistant_models() -> list[AssistantModelOption]:
    """The models the assistant may be pointed at. Served from the API so the settings picker
    can never offer a value the PATCH below would reject."""
    return assistant_model_options()


@router.get("/llm-providers", response_model=list[LLMProvider], tags=["workspace"])
def list_llm_providers() -> list[LLMProvider]:
    """The BYO-key provider list for Settings, each row carrying whether it's wired up yet."""
    return llm_providers()


@router.patch("/workspaces/current", response_model=WorkspaceInfo, tags=["workspace"])
def update_workspace(body: WorkspaceUpdate, t: Tenant = Depends(tenant)) -> WorkspaceInfo:
    """Partial update of the current workspace (name and/or assistant model)."""
    ws = t.session.get(Workspace, t.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    if body.name is not None:
        ws.name = body.name
    if body.assistant_model is not None:
        # Allow-listed: this value is persisted and later handed to the model factory, so an
        # arbitrary string here would point the assistant at an unpriced model.
        if not is_allowed(body.assistant_model):
            raise HTTPException(status_code=422, detail="unsupported assistant model")
        ws.assistant_model = body.assistant_model
    t.session.commit()
    posthog_client.capture(
        "workspace_updated",
        distinct_id=str(t.workspace_id),
        properties={
            "workspace_id": str(t.workspace_id),
            "renamed": body.name is not None,
            "assistant_model": body.assistant_model,
        },
    )
    return WorkspaceInfo(
        id=str(ws.id),
        name=ws.name,
        plan=ws.plan,
        assistant_model=ws.assistant_model,
    )
