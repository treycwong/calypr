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
    run = ImageNode.compile(ImageConfig(model="fake", prompt_channel="input"), NodeContext())
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
    monkeypatch.setattr("calypr_nodes.image.safe_stream_writer", lambda: captured.append)
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    await run({"messages": [HumanMessage(content="a fox")]})

    usage = [p for p in captured if p.get("type") == "usage"]
    assert len(usage) == 1
    assert usage[0]["model"] == "fake"
    assert "input_tokens" in usage[0] and "output_tokens" in usage[0]
    # And it streams the image so the Playground renders it live.
    tokens = [p for p in captured if p.get("type") == "token"]
    assert tokens and tokens[0]["text"].startswith("![a fox](")


async def test_image_node_emits_asset_when_the_upload_is_durable(monkeypatch):
    """The `asset` event is what puts a generated image in the Media tab. It rides the same
    custom-event writer as `usage` so nothing tenant-aware has to reach into this package."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.image.safe_stream_writer", lambda: captured.append)

    async def fake_put_blob(data, *, pathname, content_type):
        return f"https://store.public.blob.vercel-storage.com/{pathname}"

    monkeypatch.setattr("calypr_nodes._assets.put_blob", fake_put_blob)
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    await run({"messages": [HumanMessage(content="a fox")]})

    assets = [p for p in captured if p.get("type") == "asset"]
    assert len(assets) == 1
    a = assets[0]
    assert a["kind"] == "image"
    assert a["url"].startswith("https://store.public.blob.vercel-storage.com/runs/png/")
    assert a["pathname"].startswith("runs/png/")
    assert a["caption"] == "a fox"
    assert a["model"] == "fake"
    assert a["bytes"] > 0


async def test_image_node_emits_no_asset_without_blob_storage(monkeypatch):
    """Blob-less deployments still *render* the image (data: URI in the token markdown) but must
    record nothing — otherwise a multi-MB base64 string lands in Postgres."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.image.safe_stream_writer", lambda: captured.append)
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    await run({"messages": [HumanMessage(content="a fox")]})

    assert [p for p in captured if p.get("type") == "asset"] == []
    tokens = [p for p in captured if p.get("type") == "token"]
    assert tokens and "data:image/png;base64," in tokens[0]["text"]


# --- CAL-61: use the attached photo instead of generating -------------------------------------


class _Boom:
    """An image client that fails the test if it is ever called."""

    async def generate(self, **_):  # pragma: no cover - reaching here is the failure
        raise AssertionError("generated an image although a photo was attached")


async def test_use_upload_with_a_photo_generates_nothing():
    """The user's photo is already on `images`, where a Video/3D block looks first. The block
    makes nothing, writes nothing and so is never metered."""
    run = ImageNode.compile(
        ImageConfig(model="gpt-image-2", use_upload=True), NodeContext(image_model=_Boom())
    )
    update = await run(
        {
            "messages": [HumanMessage(content="Can you turn this image into a video?")],
            "images": ["https://blob.example/mine.jpg"],
        }
    )
    assert update == {}


async def test_use_upload_without_a_photo_generates_as_usual():
    run = ImageNode.compile(ImageConfig(model="fake", use_upload=True), NodeContext())
    update = await run({"messages": [HumanMessage(content="a lion at dawn")], "images": []})
    assert update["messages"][0].content.startswith("![a lion at dawn](")


async def test_without_use_upload_a_photo_is_not_a_reason_to_skip():
    """Default off: on the Image generation template an attachment must not silence the block."""
    run = ImageNode.compile(ImageConfig(model="fake"), NodeContext())
    update = await run(
        {
            "messages": [HumanMessage(content="a red bicycle")],
            "images": ["https://blob.example/x.jpg"],
        }
    )
    assert update["messages"][0].content.startswith("![a red bicycle](")


def test_use_upload_declares_the_images_channel():
    """Without this, a graph with no Upload block has no `images` channel and LangGraph drops the
    attachment from the run input before any block sees it."""
    keys = {c.key for c in ImageNode.channels(ImageConfig(use_upload=True))}
    assert "images" in keys
    assert "images" not in {c.key for c in ImageNode.channels(ImageConfig())}
    assert ImageNode.reads(ImageConfig(use_upload=True)) == ["messages", "images"]
