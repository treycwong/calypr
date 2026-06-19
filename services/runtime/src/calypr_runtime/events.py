"""Events surfaced by a streaming run."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal


@dataclass
class RunEvent:
    type: Literal["token", "usage", "final"]
    text: str = ""
    output: str = ""
    state: dict[str, Any] | None = None
