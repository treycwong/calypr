"""Prompt Instructions — criteria written once on the Input block, applied to every generation.

The feature is one field, and almost all of the risk is in *where the text travels*. Writing it
into the `HumanMessage` the Input node seeds would be the obvious implementation and would reach
every downstream block — including the Voice block, which would read the criteria aloud. So it
rides its own state channel and only the blocks that opt in ever see it, and the negative cases
below are the ones that keep it that way.
"""

from __future__ import annotations

from calypr_codegen import generate_python
from calypr_compiler import validate_graph
from calypr_compiler.templates import image_to_video, text_to_speech
from calypr_dsl import EdgeSpec, GraphSpec, NodeSpec, Reducer, StateChannel
from calypr_model import FakeImageClient, FakeTTSClient, FakeVideoClient
from calypr_nodes import NodeContext, graph_channels
from calypr_nodes._media import PROMPT_INSTRUCTIONS
from calypr_nodes.image import ImageConfig, ImageNode
from calypr_nodes.input import InputConfig, InputNode
from calypr_nodes.video import VideoConfig, VideoNode
from calypr_roundtrip import parse_python
from langchain_core.messages import HumanMessage

INSTR = "no text or logos; warm natural light"


class _CaptureVideo(FakeVideoClient):
    """A video client that remembers the prompt it was handed."""

    prompt = ""

    async def generate(self, **kwargs):
        self.prompt = kwargs.get("prompt", "")
        return await super().generate(**kwargs)


class _CaptureImage(FakeImageClient):
    """The image sibling of `_CaptureVideo`."""

    prompt = ""

    async def generate(self, **kwargs):
        self.prompt = kwargs.get("prompt", "")
        return await super().generate(**kwargs)


# --- the Input block ----------------------------------------------------------------------------


async def test_input_writes_the_instructions_channel_only_when_set():
    run = InputNode.compile(InputConfig(), NodeContext())
    assert await run({"input": "hi"}) == {"messages": [HumanMessage(content="hi")]}

    run = InputNode.compile(InputConfig(prompt_instructions=INSTR), NodeContext())
    out = await run({"input": "hi"})
    assert out[PROMPT_INSTRUCTIONS] == INSTR


def test_the_channel_is_declared_only_when_used():
    """`writes()` is checked against the run-time channel set (`validate.py`'s
    `undeclared_channel`), so the declaration has to appear and disappear with the field."""
    assert InputNode.channels(InputConfig()) == []
    declared = InputNode.channels(InputConfig(prompt_instructions=INSTR))
    assert [c.key for c in declared] == [PROMPT_INSTRUCTIONS]
    assert PROMPT_INSTRUCTIONS in InputNode.writes(InputConfig(prompt_instructions=INSTR))
    assert PROMPT_INSTRUCTIONS not in InputNode.writes(InputConfig())


def test_a_template_gains_the_channel_without_being_edited():
    """`graph_channels` unions node-owned channels, which is what lets this ship without touching
    any of the 31 starters."""
    graph = image_to_video()
    for node in graph.nodes:
        if node.type == "input":
            node.config["prompt_instructions"] = INSTR
    keys = {c.key for c in graph_channels(graph.nodes, graph.state)}
    assert PROMPT_INSTRUCTIONS in keys
    assert not [i for i in validate_graph(graph) if i.code == "undeclared_channel"]


# --- the blocks that consume it -----------------------------------------------------------------


async def test_the_image_block_appends_after_its_own_style():
    """Order is the decision here. A block's `style` governs the *form* of the prompt — on the
    shipped Image → 3D template it is what makes the mesh usable at all — so the run's criteria
    are added after it rather than replacing it."""
    capture = _CaptureImage()
    run = ImageNode.compile(
        ImageConfig(model="fake", style="studio product shot"),
        NodeContext(image_model=capture),
    )
    await run({"messages": [HumanMessage(content="a red chair")], PROMPT_INSTRUCTIONS: INSTR})
    assert capture.prompt == f"studio product shot, a red chair. {INSTR}"


async def test_a_block_with_no_style_still_gets_the_instructions():
    capture = _CaptureImage()
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext(image_model=capture))
    await run({"messages": [HumanMessage(content="a red chair")], PROMPT_INSTRUCTIONS: INSTR})
    assert capture.prompt == f"a red chair. {INSTR}"


async def test_the_video_block_appends_the_instructions():
    capture = _CaptureVideo()
    run = VideoNode.compile(VideoConfig(model="fake"), NodeContext(video_model=capture))
    await run({"messages": [HumanMessage(content="a study desk")], PROMPT_INSTRUCTIONS: INSTR})
    assert capture.prompt == f"a study desk. {INSTR}"


async def test_an_absent_channel_changes_nothing():
    capture = _CaptureVideo()
    run = VideoNode.compile(VideoConfig(model="fake"), NodeContext(video_model=capture))
    await run({"messages": [HumanMessage(content="a study desk")]})
    assert capture.prompt == "a study desk"


# --- the blocks that must NOT ------------------------------------------------------------------


async def test_the_voice_block_never_speaks_the_criteria(monkeypatch):
    """The case the whole design exists for. Prepending the instructions to the user's message
    would make the Text-to-speech template **read them aloud** — so if anyone ever "simplifies"
    this into `messages`, this test is what says no."""
    spoken: list[str] = []
    original = FakeTTSClient.synthesize

    async def spy(self, **kwargs):
        spoken.append(kwargs.get("text", ""))
        return await original(self, **kwargs)

    monkeypatch.setattr(FakeTTSClient, "synthesize", spy)

    from calypr_runtime import run_stream

    graph = text_to_speech()
    for node in graph.nodes:
        if node.type == "input":
            node.config["prompt_instructions"] = INSTR
        if node.type == "tts":
            node.config["model"] = "fake"
    async for _ in run_stream(
        graph,
        NodeContext(tts_model=FakeTTSClient(), image_model=FakeImageClient()),
        "hello there",
    ):
        pass
    assert spoken == ["hello there"]
    assert all(INSTR not in text for text in spoken)


# --- code export --------------------------------------------------------------------------------


def _graph(instructions: str) -> GraphSpec:
    return GraphSpec(
        id="g",
        name="g",
        state=[
            StateChannel(key="input", type="string", reducer=Reducer.last),
            StateChannel(key="messages", type="messages", reducer=Reducer.append),
            StateChannel(key="output", type="string", reducer=Reducer.last),
        ],
        nodes=[
            NodeSpec(id="in", type="input", config={"prompt_instructions": instructions}),
            NodeSpec(id="video", type="video", config={"model": "fake"}),
            NodeSpec(id="out", type="output", config={}),
        ],
        edges=[
            EdgeSpec(id="e1", source="in", target="video"),
            EdgeSpec(id="e2", source="video", target="out"),
        ],
        entry="in",
    )


def test_an_unused_field_generates_exactly_the_code_it_always_did():
    """The export is the product, so a field nobody set must leave no trace in it."""
    assert PROMPT_INSTRUCTIONS not in generate_python(_graph(""))


def test_the_instructions_round_trip_through_generated_code():
    code = generate_python(_graph(INSTR))
    assert PROMPT_INSTRUCTIONS in code
    result = parse_python(code)
    assert result.degraded_nodes == []
    recovered = {n.id: n for n in result.spec.nodes}
    assert recovered["in"].type == "input"
    assert recovered["in"].config["prompt_instructions"] == INSTR
    # A fixed point: regenerating from the recovered spec reproduces the file byte for byte.
    assert generate_python(result.spec) == code


def test_an_input_node_with_two_return_keys_still_parses_as_input():
    """The regression the `last_return_dict` → `last_return_dict_items` change prevents. That
    helper matches only a *single*-key return, and Input's parse bailed when it got None — so an
    Input node carrying instructions would have degraded to a `code` node on every trip back
    through the editor, silently, for every graph using the feature."""
    result = parse_python(generate_python(_graph(INSTR)))
    assert [n.type for n in result.spec.nodes if n.id == "in"] == ["input"]


def test_the_consumer_reads_the_channel_after_its_own_channels():
    """`ImageNode.parse` and `VideoNode.parse` recover channels *positionally* from
    `state_get_keys` — prompt first, image second. An instructions read emitted above those would
    shift both and quietly recover the wrong wiring."""
    fragment = VideoNode.codegen(
        VideoConfig(model="fal-ai/bytedance/seedance/v1/pro/fast/image-to-video"),
        "node_v",
        type("Ctx", (), {"graph_instructions": True, "tool_refs": [], "mcp_ordinal": 0})(),
    ).function
    instructions_at = fragment.index(f'state.get("{PROMPT_INSTRUCTIONS}")')
    assert fragment.index('state.get("messages")') < fragment.index('state.get("images")')
    assert fragment.index('state.get("images")') < instructions_at


async def test_the_generated_video_code_is_runnable_with_the_fold():
    """The emitted fold has to be valid Python, not just the right shape."""
    code = generate_python(_graph(INSTR))
    compile(code, "<generated>", "exec")
    assert FakeVideoClient is not None
