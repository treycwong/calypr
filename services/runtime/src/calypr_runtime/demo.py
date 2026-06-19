"""Run the golden Input → Agent → Output graph and stream the reply to stdout.

Picks a provider by available key (override with CALYPR_PROVIDER=openai|anthropic|fake):
OpenAI → Anthropic → fake. Loads a repo-root .env if present.

    uv run python -m calypr_runtime.demo "Say hello to Calypr in one sentence."
"""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from calypr_compiler.golden import input_agent_output
from calypr_nodes import NodeContext

from calypr_runtime import run_stream


def _load_dotenv() -> None:
    """Minimal, dependency-free .env loader (only sets vars that aren't already set)."""
    env = Path.cwd() / ".env"
    if not env.exists():
        return
    for line in env.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def _pick_model() -> tuple[object, str, str]:
    provider = os.environ.get("CALYPR_PROVIDER", "auto").lower()
    use_openai = provider == "openai" or (
        provider == "auto" and os.environ.get("OPENAI_API_KEY")
    )
    use_anthropic = provider == "anthropic" or (
        provider == "auto" and os.environ.get("ANTHROPIC_API_KEY")
    )

    if use_openai:
        from calypr_model import OpenAIModelClient

        model_id = os.environ.get("CALYPR_DEMO_MODEL", "gpt-4o-mini")
        return OpenAIModelClient(), model_id, f"openai · {model_id}"
    if use_anthropic:
        from calypr_model import AnthropicModelClient

        model_id = os.environ.get("CALYPR_DEMO_MODEL", "claude-sonnet-4-5")
        return AnthropicModelClient(), model_id, f"anthropic · {model_id}"

    from calypr_model import FakeModelClient

    return FakeModelClient(), "fake", "fake — set OPENAI_API_KEY for a live run"


async def main() -> None:
    _load_dotenv()
    message = " ".join(sys.argv[1:]) or "Say hello to Calypr in one sentence."
    model, model_id, label = _pick_model()
    print(f"[model: {label}]")

    spec = input_agent_output(model=model_id)
    ctx = NodeContext(model=model)

    print(f"You:   {message}")
    print("Agent: ", end="", flush=True)
    async for event in run_stream(spec, ctx, message):
        if event.type == "token":
            print(event.text, end="", flush=True)
    print()


if __name__ == "__main__":
    asyncio.run(main())
