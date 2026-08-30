"""Fan-out: two media branches must not silently share one picture.

Blocks communicate through named state channels, and every Image block appends to `messages`. So
a graph that fans out — two Image blocks, each feeding its own Video block — had both Video blocks
resolve the *most recent* image in that shared channel, and both clips came from the same picture.
The edge from a producer to its consumer carried control flow and no data, which is precisely the
thing a canvas is supposed to make true.

The fix is that a media block prefers an image produced by a node upstream of *it*. These tests
are the ones that would fail if that ever regressed to "last image wins".
"""

from __future__ import annotations

import asyncio
import itertools

import calypr_nodes  # noqa: F401  (registers the node types)
import pytest
from calypr_compiler import validate_graph
from calypr_compiler.compile import compile_graph
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import FakeImageClient, FakeVideoClient
from calypr_nodes import NodeContext

I2V = "fal-ai/bytedance/seedance/v1/pro/fast/image-to-video"

BASE_STATE = [
    StateChannel(key="input", type="string", reducer=Reducer.last),
    StateChannel(key="messages", type="messages", reducer=Reducer.append),
    StateChannel(key="output", type="string", reducer=Reducer.last),
]


@pytest.fixture(autouse=True)
def distinct_blobs(monkeypatch):
    """A unique URL per upload.

    Without this every branch is indistinguishable: `FakeImageClient` returns the same 1×1 PNG
    each time and, with no blob storage configured, `store_asset` inlines it as the same `data:`
    URI — so the test could not tell "each branch used its own picture" from the bug it is meant
    to catch."""
    counter = itertools.count(1)

    async def fake_put_blob(data, *, pathname, content_type):
        return f"https://store.example/{next(counter)}-{pathname}"

    monkeypatch.setattr("calypr_nodes._assets.put_blob", fake_put_blob)


class _SlowImage(FakeImageClient):
    """Slow enough that the branches really do overlap — the bug only showed once both were in
    flight, because it turned on which of them wrote to the shared channel last."""

    async def generate(self, **kwargs):
        await asyncio.sleep(0.05)
        return await super().generate(**kwargs)


class _RecordingVideo(FakeVideoClient):
    def __init__(self) -> None:
        self.seen: list[str] = []

    async def generate(self, **kwargs):
        self.seen.append(kwargs.get("image_url", ""))
        await asyncio.sleep(0.05)
        return await super().generate(**kwargs)


def _fan_out(branches: int = 2) -> GraphSpec:
    """Input fans out to N Image blocks, each feeding its own Video block."""
    nodes = [NodeSpec(id="in", type="input", config={})]
    edges = []
    for i in range(1, branches + 1):
        nodes += [
            NodeSpec(id=f"img{i}", type="image", config={"model": "fake"}),
            NodeSpec(id=f"vid{i}", type="video", config={"model": I2V}),
        ]
        edges += [
            EdgeSpec(id=f"a{i}", source="in", target=f"img{i}"),
            EdgeSpec(id=f"b{i}", source=f"img{i}", target=f"vid{i}"),
            EdgeSpec(id=f"c{i}", source=f"vid{i}", target="out"),
        ]
    nodes.append(NodeSpec(id="out", type="output", config={}))
    return GraphSpec(id="fan", name="fan", state=BASE_STATE, nodes=nodes, edges=edges, entry="in")


async def _run(spec: GraphSpec) -> _RecordingVideo:
    video = _RecordingVideo()
    ctx = NodeContext(image_model=_SlowImage(), video_model=video)
    graph = compile_graph(spec, ctx)
    await graph.ainvoke({"input": "a chair"})
    return video


async def test_each_video_block_animates_its_own_branchs_image():
    """The regression. Both Video blocks used to receive the same URL — whichever Image block
    happened to finish last — so one branch's picture was silently discarded and the other was
    animated twice."""
    video = await _run(_fan_out(2))
    assert len(video.seen) == 2
    assert len(set(video.seen)) == 2, f"both branches used the same image: {video.seen}"


async def test_a_single_branch_is_unchanged():
    """The common shape has to keep working exactly as it did — the fan-out fix prefers an
    upstream producer and falls back to the plain scan, so one branch takes the same path."""
    video = await _run(_fan_out(1))
    assert len(video.seen) == 1
    assert video.seen[0].startswith(("http", "data:"))


async def test_three_branches_stay_distinct():
    video = await _run(_fan_out(3))
    assert len(set(video.seen)) == 3


def test_two_image_blocks_feeding_one_video_is_flagged():
    """What the fix deliberately cannot resolve: both Image blocks are that Video block's own
    branch, so "the most recent of mine" is decided by whichever finished first. Named rather than
    guessed at."""
    spec = _fan_out(2)
    # Re-point the second branch's Video edge at the first Video block.
    spec.edges = [e for e in spec.edges if e.id != "b2"]
    spec.edges.append(EdgeSpec(id="b2", source="img2", target="vid1"))
    codes = [i.code for i in validate_graph(spec)]
    assert "ambiguous_image_source" in codes


def test_the_ordinary_chain_is_not_flagged():
    """One Image block per Video block is the shape the fix makes correct, so it must stay silent
    — a warning on a graph that now works would be noise."""
    codes = [i.code for i in validate_graph(_fan_out(2))]
    assert "ambiguous_image_source" not in codes
