"""Request/response models for the engine endpoints. The GraphSpec is reused directly
from the DSL contract, so the API speaks the exact same shape the canvas serializes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from calypr_compiler import Issue
from calypr_dsl import GraphSpec
from pydantic import BaseModel, field_validator

#: Attachment URLs a run may carry: our own blob store or an inline image data URI. Rejecting
#: arbitrary URLs keeps runs from hotlinking/SSRF-ing third-party hosts through the vision path.
_MAX_RUN_IMAGES = 4


def _validate_run_images(images: list[str]) -> list[str]:
    if len(images) > _MAX_RUN_IMAGES:
        raise ValueError(f"at most {_MAX_RUN_IMAGES} images per run")
    for url in images:
        ok = (
            url.startswith("data:image/")
            or (url.startswith("https://") and ".blob.vercel-storage.com/" in url)
        )
        if not ok:
            raise ValueError("image URLs must be uploads (blob storage) or data:image/ URIs")
    return images


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
    # Uploaded attachment URLs for a vision run (seeded into state.images; see the Upload node).
    images: list[str] = []

    @field_validator("images")
    @classmethod
    def _images_ok(cls, v: list[str]) -> list[str]:
        return _validate_run_images(v)


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


class ShareCreate(BaseModel):
    """Mint a share link. `run_cap` omitted ⇒ the endpoint applies the default cap; an explicit
    `null` would mean unlimited, but the endpoint only reads a positive int or the default."""

    run_cap: int | None = None


class ShareInfo(BaseModel):
    token: str
    run_cap: int | None
    run_count: int
    created_at: datetime
    revoked_at: datetime | None


class ShareRunRequest(BaseModel):
    """A run against a share link. Spec-free by design — the graph is loaded server-side from
    the token; anonymous callers only send a message (+ optional client-chosen thread id)."""

    message: str
    thread_id: str | None = None
    images: list[str] = []

    @field_validator("images")
    @classmethod
    def _images_ok(cls, v: list[str]) -> list[str]:
        return _validate_run_images(v)


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
