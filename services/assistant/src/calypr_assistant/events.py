"""Events the assistant streams while drafting a graph.

Each event knows how to serialize itself into the SSE payload dict the API contract in
AI-ASSISTANT-SPEC.md §6 defines. The router wraps `payload()` output as an SSE `data:`
frame — events stay transport-agnostic (no FastAPI/web imports here)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from calypr_dsl import GraphSpec


@dataclass
class Status:
    """Progress line for the panel: drafting | validating | repairing."""

    phase: str

    def payload(self) -> dict[str, Any]:
        return {"type": "status", "phase": self.phase}


@dataclass
class Note:
    """One short sentence the assistant says about what it built."""

    text: str

    def payload(self) -> dict[str, Any]:
        return {"type": "note", "text": self.text}


@dataclass
class Graph:
    """The deliverable: a validated GraphSpec. At most one per request."""

    spec: GraphSpec

    def payload(self) -> dict[str, Any]:
        return {"type": "graph", "spec": self.spec.model_dump(mode="json")}


@dataclass
class Usage:
    """Token usage for one model call — cost visibility for the panel and metering."""

    input_tokens: int
    output_tokens: int
    model: str

    def payload(self) -> dict[str, Any]:
        return {
            "type": "usage",
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "model": self.model,
        }


@dataclass
class Error:
    """A validation failure after retries, or a provider/config error."""

    message: str
    issues: list[dict[str, Any]] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        return {"type": "error", "message": self.message, "issues": self.issues}


AssistEvent = Status | Note | Graph | Usage | Error

__all__ = ["Status", "Note", "Graph", "Usage", "Error", "AssistEvent"]
