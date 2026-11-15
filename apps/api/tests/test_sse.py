"""`with_heartbeat`: keep a quiet SSE stream flowing without disturbing the run (CAL-61)."""

from __future__ import annotations

import asyncio

import pytest
from calypr_api.sse import PING, with_heartbeat


async def _slow(items, gap):
    for item in items:
        await asyncio.sleep(gap)
        yield item


async def test_items_pass_through_in_order_with_pings_in_the_quiet_gaps():
    out = [x async for x in with_heartbeat(_slow(["a", "b"], 0.25), interval=0.1)]
    assert [x for x in out if x != PING] == ["a", "b"]
    assert out.count(PING) >= 2  # at least one ping in each 0.25 s gap
    assert out[-1] == "b"


async def test_a_busy_stream_gets_no_pings():
    out = [x async for x in with_heartbeat(_slow(["a", "b", "c"], 0), interval=1)]
    assert out == ["a", "b", "c"]


async def test_an_error_in_the_run_reaches_the_consumer():
    async def boom():
        yield "a"
        raise ValueError("engine broke")

    got = []
    with pytest.raises(ValueError, match="engine broke"):
        async for x in with_heartbeat(boom(), interval=1):
            got.append(x)
    assert got == ["a"]


async def test_closing_the_stream_cancels_the_run_so_its_cleanup_runs():
    """The run routes catch `CancelledError` on disconnect to flush their recorders; the
    heartbeat must deliver exactly that, not leave the run going in the background."""
    seen: list[str] = []

    async def run():
        try:
            yield "first"
            await asyncio.sleep(10)
            yield "never"
        except asyncio.CancelledError:
            seen.append("cancelled")
            raise

    stream = with_heartbeat(run(), interval=5)
    assert await anext(stream) == "first"
    await stream.aclose()
    await asyncio.sleep(0.05)  # let the cancelled task run its except arm
    assert seen == ["cancelled"]
