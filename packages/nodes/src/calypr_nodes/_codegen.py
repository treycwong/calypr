"""Small shared helpers for node `codegen()` methods.

Generated code must stay under the 100-col limit and read like a person wrote it, so long
string literals are wrapped with implicit (parenthesised) concatenation at word boundaries.
"""

from __future__ import annotations

import json


def chunks(s: str, size: int = 60) -> list[str]:
    """Split into ~size pieces, preferring a space boundary so wrapped string literals
    read naturally (the trailing space stays on the left chunk → content is preserved)."""
    out: list[str] = []
    i = 0
    while i < len(s):
        end = min(i + size, len(s))
        if end < len(s):
            sp = s.rfind(" ", i + size // 2, end)
            if sp != -1:
                end = sp + 1
        out.append(s[i:end])
        i = end
    return out or [""]


def assign_str(name: str, value: str, indent: str = "    ") -> list[str]:
    """Emit `name = "..."`, wrapping long literals with implicit string concatenation."""
    literal = json.dumps(value)
    if len(indent) + len(name) + 3 + len(literal) <= 99:
        return [f"{indent}{name} = {literal}"]
    inner = indent + "    "
    return [
        f"{indent}{name} = (",
        *[f"{inner}{json.dumps(chunk)}" for chunk in chunks(value)],
        f"{indent})",
    ]
