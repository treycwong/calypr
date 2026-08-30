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

def image_pick_lines(channel: str, sources: list[str], var: str) -> list[str]:
    """The generated lines that resolve a source image from `channel`.

    With one Image block in the graph this is the plain "last value wins" read. With several, the
    read has to say *which* branch's picture it wants: they all append to the same channel, so the
    unqualified version hands two parallel Video blocks the same image. The producing node stamps
    each message it writes, and this filters on that.
    """
    if not sources:
        return [
            f'    source = state.get("{channel}")',
            f'    {var} = source if isinstance(source, str) else (source[-1] if source else "")',
        ]
    md = r'r"!\[[^\]]*\]\(([^)]+)\)"'
    return [
        "    # This graph has more than one Image block and they share a channel, so take the",
        "    # picture *this* branch produced rather than whichever was written last.",
        f"    sources = {tuple(sources)!r}",
        "    mine = [",
        "        m",
        f'        for m in state.get("{channel}") or []',
        '        if getattr(m, "additional_kwargs", {}).get("calypr_node") in sources',
        "    ]",
        f'    found = re.findall({md}, str(mine[-1].content) if mine else "")',
        f'    {var} = found[-1] if found else ""',
    ]
