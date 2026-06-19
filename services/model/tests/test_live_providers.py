"""Live provider smoke tests. Each is skipped unless its API key is in the environment,
so CI (key-free) stays green. Run locally with the key exported to verify a real call."""

from __future__ import annotations

import os

import pytest
from calypr_model import Done, Msg, Role

_PING = [Msg(role=Role.user, content="Reply with exactly the single word: pong")]


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), reason="no OPENAI_API_KEY")
async def test_openai_streams_a_reply():
    from calypr_model import OpenAIModelClient

    model = os.environ.get("CALYPR_TEST_OPENAI_MODEL", "gpt-4o-mini")
    events = [
        e async for e in OpenAIModelClient().stream(model=model, messages=_PING, max_tokens=20)
    ]
    assert isinstance(events[-1], Done)
    assert events[-1].text.strip() != ""


@pytest.mark.skipif(
    not os.environ.get("ANTHROPIC_API_KEY"), reason="no ANTHROPIC_API_KEY"
)
async def test_anthropic_streams_a_reply():
    from calypr_model import AnthropicModelClient

    model = os.environ.get("CALYPR_TEST_ANTHROPIC_MODEL", "claude-sonnet-4-5")
    events = [
        e
        async for e in AnthropicModelClient().stream(
            model=model, messages=_PING, max_tokens=20
        )
    ]
    assert isinstance(events[-1], Done)
    assert events[-1].text.strip() != ""
