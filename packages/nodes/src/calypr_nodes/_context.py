"""Task-local execution context for nodes.

`current_node_id` carries the id of the node currently executing so deep helpers (the LLM
streaming writers) can tag usage events without threading the id through every signature.
ContextVars are task-local, so parallel fan-out nodes each observe their own id.
"""

from __future__ import annotations

from contextvars import ContextVar

current_node_id: ContextVar[str | None] = ContextVar("current_node_id", default=None)
