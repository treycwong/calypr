"""Image node: generate a visual (fake, keyless) and surface it as a Markdown image, while
emitting the standard `usage` payload so run metering prices it like any model call."""

from __future__ import annotations

from calypr_nodes import ImageConfig, NodeContext
from calypr_nodes.image import ImageNode
from langchain_core.messages import AIMessage, HumanMessage


async def test_image_node_appends_markdown_image():
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    update = await run({"messages": [HumanMessage(content="a red bicycle")]})
    msgs = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], AIMessage)
    # No blob token in tests → data-URI fallback, but still a valid Markdown image.
    assert msgs[0].content.startswith("![a red bicycle](data:image/png;base64,")


async def test_image_node_reads_plain_string_channel():
    run = ImageNode.compile(
        ImageConfig(model="fake", prompt_channel="input"), NodeContext()
    )
    update = await run({"input": "a blue cat"})
    assert update["messages"][0].content.startswith("![a blue cat](")


async def test_image_node_no_prompt_is_noop():
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    assert await run({"messages": []}) == {}


async def test_image_node_style_specializes_prompt():
    """`style` fixes the look: the model receives style+prompt, but the caption stays the raw
    request. This is what makes a specialized (e.g. anime) generator."""
    seen: dict = {}

    class _Capture:
        async def generate(self, *, model, prompt, size, quality, n):
            seen["prompt"] = prompt
            from calypr_model import ImageResult, Usage

            return ImageResult(images=[b"x"], usage=Usage(0, 0), b64=["eA=="])

    ctx = NodeContext(image_model=_Capture())  # injected client (mirrors model_for_node)
    run = ImageNode.compile(ImageConfig(model="gpt-image-2", style="anime style, cel shading"), ctx)
    update = await run({"messages": [HumanMessage(content="a dog")]})
    assert seen["prompt"] == "anime style, cel shading, a dog"  # style folded in for the model
    assert update["messages"][0].content.startswith("![a dog](")  # caption is the raw request


async def test_image_node_style_placeholder():
    seen: dict = {}

    class _Capture:
        async def generate(self, *, model, prompt, size, quality, n):
            seen["prompt"] = prompt
            from calypr_model import ImageResult, Usage

            return ImageResult(images=[b"x"], usage=Usage(0, 0), b64=["eA=="])

    ctx = NodeContext(image_model=_Capture())
    run = ImageNode.compile(ImageConfig(model="gpt-image-2", style="a {prompt} in watercolor"), ctx)
    await run({"messages": [HumanMessage(content="fox")]})
    assert seen["prompt"] == "a fox in watercolor"


async def test_image_node_emits_usage_for_metering(monkeypatch):
    """The node must emit a `{type:'usage', model, input_tokens, output_tokens}` payload with the
    keys `RunRecorder` buffers — that's the whole metering integration."""
    captured: list[dict] = []
    monkeypatch.setattr(
        "calypr_nodes.image.safe_stream_writer", lambda: captured.append
    )
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    await run({"messages": [HumanMessage(content="a fox")]})

    usage = [p for p in captured if p.get("type") == "usage"]
    assert len(usage) == 1
    assert usage[0]["model"] == "fake"
    assert "input_tokens" in usage[0] and "output_tokens" in usage[0]
    # And it streams the image so the Playground renders it live.
    tokens = [p for p in captured if p.get("type") == "token"]
    assert tokens and tokens[0]["text"].startswith("![a fox](")
