"""Agent CRUD + graph compile/validate.

Each request resolves its workspace via the `tenant` dependency (the signed-in user's personal
workspace in prod, the shared dev workspace locally); queries scope to it explicitly, with the
RLS policy as defense-in-depth.
"""

from __future__ import annotations

import uuid

from calypr_codegen import generate_python
from calypr_compiler import FRAMEWORKS, TEMPLATES, validate_graph
from calypr_dsl import GraphSpec
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from calypr_api.db.models import Agent, Workspace
from calypr_api.deps import Tenant, tenant
from calypr_api.schemas import (
    AgentCreate,
    AgentDetail,
    AgentSummary,
    AgentUpdate,
    CodegenResponse,
    CompileResponse,
    TemplateInfo,
    WorkspaceInfo,
    WorkspaceUpdate,
)

router = APIRouter()


@router.post("/compile", response_model=CompileResponse, tags=["engine"])
def compile_spec(graph: GraphSpec) -> CompileResponse:
    issues = validate_graph(graph)
    ok = not any(i.severity == "error" for i in issues)
    return CompileResponse(ok=ok, issues=issues)


@router.post("/codegen", response_model=CodegenResponse, tags=["engine"])
def codegen_spec(graph: GraphSpec) -> CodegenResponse:
    """The 'code' altitude: render the graph as ownable Python (LangGraph)."""
    return CodegenResponse(code=generate_python(graph))


@router.get("/templates", response_model=list[TemplateInfo], tags=["engine"])
def list_templates() -> list[TemplateInfo]:
    """The canvas starter gallery: frameworks (agent patterns) + templates (use cases)."""
    return [
        TemplateInfo(
            id=t.id, name=t.name, description=t.description or "", kind=kind, graph=t
        )
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
    agent = Agent(
        workspace_id=t.workspace_id, name=body.name, graph_spec=body.graph.model_dump()
    )
    t.session.add(agent)
    t.session.commit()
    t.session.refresh(agent)
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
    return [
        AgentSummary(id=str(a.id), name=a.name, updated_at=a.updated_at) for a in rows
    ]


@router.get("/agents/{agent_id}", response_model=AgentDetail, tags=["agents"])
def get_agent(agent_id: str, t: Tenant = Depends(tenant)) -> AgentDetail:
    a = _get_owned(t.session, t.workspace_id, agent_id)
    return AgentDetail(
        id=str(a.id), name=a.name, graph=GraphSpec.model_validate(a.graph_spec)
    )


@router.put("/agents/{agent_id}", response_model=AgentDetail, tags=["agents"])
def update_agent(
    agent_id: str, body: AgentUpdate, t: Tenant = Depends(tenant)
) -> AgentDetail:
    a = _get_owned(t.session, t.workspace_id, agent_id)
    if body.name is not None:
        a.name = body.name
    if body.graph is not None:
        a.graph_spec = body.graph.model_dump()
    t.session.commit()
    t.session.refresh(a)
    return AgentDetail(
        id=str(a.id), name=a.name, graph=GraphSpec.model_validate(a.graph_spec)
    )


@router.delete(
    "/agents/{agent_id}", status_code=status.HTTP_204_NO_CONTENT, tags=["agents"]
)
def delete_agent(agent_id: str, t: Tenant = Depends(tenant)) -> Response:
    a = _get_owned(t.session, t.workspace_id, agent_id)
    t.session.delete(a)
    t.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.patch("/workspaces/current", response_model=WorkspaceInfo, tags=["workspace"])
def rename_workspace(
    body: WorkspaceUpdate, t: Tenant = Depends(tenant)
) -> WorkspaceInfo:
    ws = t.session.get(Workspace, t.workspace_id)
    if ws is None:
        raise HTTPException(status_code=404, detail="workspace not found")
    ws.name = body.name
    t.session.commit()
    return WorkspaceInfo(id=str(ws.id), name=ws.name)
