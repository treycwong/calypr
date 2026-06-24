"""Agent CRUD + graph compile/validate.

Phase 2 attaches everything to a fixed dev workspace (pre-Clerk) and filters queries by
it explicitly; the RLS policy is defense-in-depth for when a non-owner app role lands.
"""

from __future__ import annotations

import uuid

from calypr_codegen import generate_python
from calypr_compiler import FRAMEWORKS, TEMPLATES, validate_graph
from calypr_dsl import GraphSpec
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Agent
from calypr_api.db.session import get_session, set_tenant
from calypr_api.schemas import (
    AgentCreate,
    AgentDetail,
    AgentSummary,
    AgentUpdate,
    CodegenResponse,
    CompileResponse,
    TemplateInfo,
)

router = APIRouter()
_WS = uuid.UUID(DEV_WORKSPACE_ID)


def _scoped(session: Session) -> None:
    set_tenant(session, DEV_WORKSPACE_ID)


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


@router.post("/agents", response_model=AgentDetail, tags=["agents"])
def create_agent(
    body: AgentCreate, session: Session = Depends(get_session)
) -> AgentDetail:
    _scoped(session)
    agent = Agent(
        workspace_id=_WS, name=body.name, graph_spec=body.graph.model_dump()
    )
    session.add(agent)
    session.commit()
    session.refresh(agent)
    return AgentDetail(
        id=str(agent.id), name=agent.name, graph=GraphSpec.model_validate(agent.graph_spec)
    )


@router.get("/agents", response_model=list[AgentSummary], tags=["agents"])
def list_agents(session: Session = Depends(get_session)) -> list[AgentSummary]:
    _scoped(session)
    rows = (
        session.execute(
            select(Agent)
            .where(Agent.workspace_id == _WS)
            .order_by(Agent.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [AgentSummary(id=str(a.id), name=a.name) for a in rows]


def _get_owned(session: Session, agent_id: str) -> Agent:
    try:
        pk = uuid.UUID(agent_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="agent not found") from exc
    agent = session.get(Agent, pk)
    if agent is None or agent.workspace_id != _WS:
        raise HTTPException(status_code=404, detail="agent not found")
    return agent


@router.get("/agents/{agent_id}", response_model=AgentDetail, tags=["agents"])
def get_agent(agent_id: str, session: Session = Depends(get_session)) -> AgentDetail:
    _scoped(session)
    a = _get_owned(session, agent_id)
    return AgentDetail(id=str(a.id), name=a.name, graph=GraphSpec.model_validate(a.graph_spec))


@router.put("/agents/{agent_id}", response_model=AgentDetail, tags=["agents"])
def update_agent(
    agent_id: str, body: AgentUpdate, session: Session = Depends(get_session)
) -> AgentDetail:
    _scoped(session)
    a = _get_owned(session, agent_id)
    if body.name is not None:
        a.name = body.name
    if body.graph is not None:
        a.graph_spec = body.graph.model_dump()
    session.commit()
    session.refresh(a)
    return AgentDetail(id=str(a.id), name=a.name, graph=GraphSpec.model_validate(a.graph_spec))
