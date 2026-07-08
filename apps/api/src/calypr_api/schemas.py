"""Request/response models for the engine endpoints. The GraphSpec is reused directly
from the DSL contract, so the API speaks the exact same shape the canvas serializes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from calypr_compiler import Issue
from calypr_dsl import GraphSpec
from pydantic import BaseModel


class CompileResponse(BaseModel):
    ok: bool
    issues: list[Issue]


class CodegenResponse(BaseModel):
    code: str


class RunRequest(BaseModel):
    graph: GraphSpec
    message: str
    thread_id: str | None = None
    # Optional: when the playground runs a saved agent, its id lets metering attribute the run.
    agent_id: str | None = None


class AssistMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class AssistRequest(BaseModel):
    """A prompt (with history) for the AI assistant. `current_graph` is the canvas's current
    spec in refine mode; `model` overrides the server default."""

    messages: list[AssistMessage]
    current_graph: GraphSpec | None = None
    model: str | None = None


class AgentCreate(BaseModel):
    name: str
    graph: GraphSpec


class AgentUpdate(BaseModel):
    name: str | None = None
    graph: GraphSpec | None = None


class AgentSummary(BaseModel):
    id: str
    name: str
    updated_at: datetime


class AgentDetail(BaseModel):
    id: str
    name: str
    graph: GraphSpec


class WorkspaceInfo(BaseModel):
    id: str
    name: str


class WorkspaceUpdate(BaseModel):
    name: str


class TemplateInfo(BaseModel):
    """A starter graph for the canvas gallery — a `framework` (agent pattern) or a
    `template` (multi-agent use case)."""

    id: str
    name: str
    description: str
    kind: Literal["framework", "template"]
    graph: GraphSpec
