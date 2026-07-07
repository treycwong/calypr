"""Live provider smoke tests. Opt-in only: set CALYPR_RUN_LIVE_TESTS=1 *and* the relevant
key. (A key alone is not enough, so a normal `pytest` never makes real API calls even when
a .env is loaded.) Run with: CALYPR_RUN_LIVE_TESTS=1 uv run pytest services/model/tests."""

from __future__ import annotations

import os

import pytest
from calypr_model import Done, Msg, Role

_PING = [Msg(role=Role.user, content="Reply with exactly the single word: pong")]
_LIVE = os.environ.get("CALYPR_RUN_LIVE_TESTS") == "1"


@pytest.mark.skipif(
    not (_LIVE and os.environ.get("OPENAI_API_KEY")),
    reason="set CALYPR_RUN_LIVE_TESTS=1 and OPENAI_API_KEY",
)
async def test_openai_streams_a_reply():
    from calypr_model import OpenAIModelClient

    model = os.environ.get("CALYPR_TEST_OPENAI_MODEL", "gpt-4o-mini")
    events = [
        e async for e in OpenAIModelClient().stream(model=model, messages=_PING, max_tokens=20)
    ]
    assert isinstance(events[-1], Done)
    assert events[-1].text.strip() != ""


@pytest.mark.skipif(
    not (_LIVE and os.environ.get("ANTHROPIC_API_KEY")),
    reason="set CALYPR_RUN_LIVE_TESTS=1 and ANTHROPIC_API_KEY",
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


@pytest.mark.skipif(
    not (_LIVE and os.environ.get("MOONSHOT_API_KEY")),
    reason="set CALYPR_RUN_LIVE_TESTS=1 and MOONSHOT_API_KEY",
)
async def test_moonshot_streams_a_reply():
    from calypr_model import model_for

    model = os.environ.get("CALYPR_TEST_MOONSHOT_MODEL", "kimi-k2-0711-preview")
    events = [
        e async for e in model_for(model).stream(model=model, messages=_PING, max_tokens=20)
    ]
    assert isinstance(events[-1], Done)
    assert events[-1].text.strip() != ""


@pytest.mark.skipif(
    not (_LIVE and os.environ.get("DEEPSEEK_API_KEY")),
    reason="set CALYPR_RUN_LIVE_TESTS=1 and DEEPSEEK_API_KEY",
)
async def test_deepseek_streams_a_reply():
    from calypr_model import model_for

    model = os.environ.get("CALYPR_TEST_DEEPSEEK_MODEL", "deepseek-chat")
    events = [
        e async for e in model_for(model).stream(model=model, messages=_PING, max_tokens=20)
    ]
    assert isinstance(events[-1], Done)
    assert events[-1].text.strip() != ""
