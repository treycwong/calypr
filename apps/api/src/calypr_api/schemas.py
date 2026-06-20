"""Request/response models for the engine endpoints. The GraphSpec is reused directly
from the DSL contract, so the API speaks the exact same shape the canvas serializes."""

from __future__ import annotations

from calypr_compiler import Issue
from calypr_dsl import GraphSpec
from pydantic import BaseModel


class CompileResponse(BaseModel):
    ok: bool
    issues: list[Issue]


class RunRequest(BaseModel):
    graph: GraphSpec
    message: str
    thread_id: str | None = None


class AgentCreate(BaseModel):
    name: str
    graph: GraphSpec


class AgentUpdate(BaseModel):
    name: str | None = None
    graph: GraphSpec | None = None


class AgentSummary(BaseModel):
    id: str
    name: str


class AgentDetail(BaseModel):
    id: str
    name: str
    graph: GraphSpec
