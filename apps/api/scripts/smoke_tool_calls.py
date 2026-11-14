"""Prove that the tool-using templates actually *call* their tools in production.

The anonymous prod smoke (TODO §2b) proves each template *answers*. For a ReAct template that is
not the same thing: with no connector or key on file, `tpl-mcp-react`, `tpl-notion-assistant` and
`tpl-image-finder` can all answer from the model's own knowledge and never touch MCP, Notion or
Unsplash. This runs each one as a real, signed-in user, with that user's own connectors and keys,
and passes only when the run stream reports the Tool node executing.

    railway run --service calypr-api -- uv run python scripts/smoke_tool_calls.py \\
        --email you@example.com

What counts as proof is the stream's own `{"type": "node", "node_id": "tools", "phase": ...}`
events: a `start` *and* an `end` for the Tool node. The answer text is never trusted on its own —
a model can describe search results it never fetched. On top of that:

- **Image Finder** must show a real Unsplash photo url *from a live search*. The fallback serves
  three fixed demo photos (no key on file, or the key is rate-limited); one of those in the answer
  is reported as STUB, not PASS. The query is chosen so none of the demo photos would match it.
- **Notion** uses the workspace's first Notion connector; the run is SKIP if there isn't one.
- **MCP ReAct** points at `--mcp-url` (a public, no-auth server by default), since the template
  ships with an empty one.
- Any `notice` that an MCP node "resolved to no server" is a FAIL: the run had no tools at all.

Needs `CALYPR_INTERNAL_KEY` and `CALYPR_DATABASE_URL` from the API's environment (hence
`railway run`); neither is printed. Each run is a real run on the user's account and costs a
handful of credits. Exits non-zero if anything FAILs.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field

import httpx
import psycopg
from calypr_compiler.templates import STARTERS
from calypr_dsl import GraphSpec

DEFAULT_API = "https://calypr-api-production.up.railway.app"
#: Public, unauthenticated streamable-HTTP MCP server (repository Q&A). Any server works.
DEFAULT_MCP_URL = "https://mcp.deepwiki.com/mcp"

#: The fallback's demo photos (`tools_catalog._UNSPLASH_DEMO_PHOTOS`).
STUB_URL = re.compile(
    r"photo-(1603979649806-5299879db16b|1533073526757-2c8ca1df9f1c|1517842645767-c639042777db)"
)
REAL_PHOTO = re.compile(r"images\.unsplash\.com/photo-")


@dataclass
class Result:
    template: str
    verdict: str = "FAIL"  # PASS | STUB | SKIP | FAIL
    reason: str = ""
    tool_phases: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    answer: str = ""


def _user_id(email: str) -> str:
    url = os.environ["CALYPR_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    with psycopg.connect(url) as conn:
        row = conn.execute('SELECT id FROM "user" WHERE lower(email) = lower(%s)', (email,))
        found = row.fetchone()
    if not found:
        sys.exit(f"no user with email {email!r}")
    return str(found[0])


def _template(tid: str) -> GraphSpec:
    return next(g for g in STARTERS if g.id == tid).model_copy(deep=True)


def _with_tool_config(graph: GraphSpec, **config: str) -> GraphSpec:
    nodes = [
        n.model_copy(update={"config": {**n.config, **config}}) if n.id == "tools" else n
        for n in graph.nodes
    ]
    return graph.model_copy(update={"nodes": nodes})


def _run(client: httpx.Client, graph: GraphSpec, message: str, result: Result) -> None:
    body = {"graph": graph.model_dump(mode="json"), "message": message}
    tokens: list[str] = []
    final = ""
    with client.stream("POST", "/runs", json=body, timeout=180) as r:
        if r.status_code != 200:
            result.reason = f"HTTP {r.status_code}: {r.read().decode()[:200]}"
            return
        for line in r.iter_lines():
            if not line.startswith("data: ") or line == "data: [DONE]":
                continue
            ev = json.loads(line[6:])
            kind = ev.get("type")
            if kind == "node" and ev.get("node_id") == "tools":
                result.tool_phases.append(ev.get("phase", "?"))
            elif kind == "token":
                tokens.append(ev.get("text", ""))
            elif kind == "notice":
                result.notices.append(ev.get("message", ""))
            elif kind == "final":
                out = ev.get("output")
                final = out if isinstance(out, str) else json.dumps(out)
            elif kind == "error":
                result.reason = f"run error: {ev.get('message')}"
                return
    result.answer = "".join(tokens) or final


def _judge(result: Result, *, images: bool = False) -> None:
    if result.reason:  # transport or run error already recorded
        return
    if any("no server resolved" in n for n in result.notices):
        result.reason = "MCP node resolved to no server — the run had no tools"
        return
    if "start" not in result.tool_phases or "end" not in result.tool_phases:
        result.reason = "the Tool node never ran — answered from the model alone"
        return
    if images and STUB_URL.search(result.answer):
        result.verdict = "STUB"
        result.reason = "tool served the demo photos (no Unsplash key, or rate-limited)"
        return
    if images and not REAL_PHOTO.search(result.answer):
        result.reason = "tool ran, but the answer shows no Unsplash photo url"
        return
    result.verdict = "PASS"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    who = ap.add_mutually_exclusive_group(required=True)
    who.add_argument("--email", help="run as this user (their workspace + keys)")
    who.add_argument("--user-id", help="run as this Better Auth user id (skips the DB lookup)")
    ap.add_argument("--api", default=os.environ.get("SMOKE_API_URL", DEFAULT_API))
    ap.add_argument("--mcp-url", default=DEFAULT_MCP_URL)
    ap.add_argument("-v", "--verbose", action="store_true", help="print each answer")
    args = ap.parse_args()

    key = os.environ.get("CALYPR_INTERNAL_KEY", "")
    # Without an internal key the API is in dev mode: every request is the shared dev workspace
    # and the user id is ignored, so there is nothing to look up (handy for a local dry run).
    headers = (
        {"x-calypr-internal-key": key, "x-calypr-user-id": args.user_id or _user_id(args.email)}
        if key
        else {}
    )
    results: list[Result] = []
    with httpx.Client(base_url=args.api, headers=headers) as client:
        # 1. Image Finder — the Unsplash key comes from the workspace vault, server-side.
        r = Result("tpl-image-finder")
        # Not a starter chip: the demo photos include a mountain lake, and a live search for one
        # can legitimately return that very photo.
        _run(client, _template(r.template), "A red bicycle leaning on a brick wall", r)
        _judge(r, images=True)
        results.append(r)

        # 2. Notion assistant — the workspace's own Notion connector.
        r = Result("tpl-notion-assistant")
        conns = client.get("/connectors").raise_for_status().json()
        notion = next((c for c in conns if c["kind"] == "notion"), None)
        if notion is None:
            r.verdict, r.reason = "SKIP", "no Notion connector in this workspace"
        else:
            graph = _with_tool_config(_template(r.template), mcp_connector_ref=notion["id"])
            _run(client, graph, "Search my Notion and name one page you find.", r)
            _judge(r)
        results.append(r)

        # 3. MCP ReAct — the template ships with an empty URL; point it at a real server.
        r = Result("tpl-mcp-react")
        graph = _with_tool_config(
            _template(r.template), mcp_url=args.mcp_url, mcp_transport="streamable_http"
        )
        _run(
            client,
            graph,
            "Use your tools to find out what the GitHub repository langchain-ai/langgraph is, "
            "and answer in two sentences.",
            r,
        )
        _judge(r)
        results.append(r)

    width = max(len(r.template) for r in results)
    for r in results:
        phases = ",".join(r.tool_phases) or "-"
        print(f"{r.verdict:<4}  {r.template:<{width}}  tools[{phases}]  {r.reason}")
        for n in r.notices:
            print(f"      notice: {n[:160]}")
        if args.verbose and r.answer:
            print("      answer: " + r.answer[:400].replace("\n", " ") + "\n")
    sys.exit(1 if any(r.verdict == "FAIL" for r in results) else 0)


if __name__ == "__main__":
    main()
