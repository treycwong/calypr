"""3D node: turn an image into a GLB (fake, keyless), surface it as a download link, and emit the
standard `usage` payload so run metering prices it per generation."""

from __future__ import annotations

import pytest
from calypr_nodes import MeshConfig, NodeContext
from calypr_nodes.mesh import MeshNode
from langchain_core.messages import AIMessage, HumanMessage


async def test_mesh_node_appends_source_image_and_download_link():
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    update = await run({"images": ["https://example.test/chair.png"]})
    msgs = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], AIMessage)
    assert "![source](https://example.test/chair.png)" in msgs[0].content
    # No blob token in tests, so this run says so rather than inlining the file — see below.
    assert "storage isn\u2019t configured" in msgs[0].content


async def test_mesh_node_falls_back_to_the_last_markdown_image_in_messages():
    """This is what makes `Image → 3D` work on the canvas: the Image node appends
    `![alt](url)` to `messages` and never touches the `images` channel.

    Asserted on what the *client* received rather than on the rendered message, because a
    transcript image is deliberately not echoed back — see the poster tests below."""
    seen: dict = {}

    class _Capture:
        async def generate(self, *, model, image_url, **kwargs):
            seen["image_url"] = image_url
            seen.update(kwargs)
            from calypr_model import FakeMeshClient

            return await FakeMeshClient().generate(model=model, image_url=image_url)

    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext(mesh_model=_Capture()))
    await run(
        {
            "messages": [
                HumanMessage(content="a chair"),
                AIMessage(content="![a chair](https://example.test/first.png)"),
                AIMessage(content="![a chair](https://example.test/latest.png)"),
            ]
        }
    )
    # Most recent image wins — a transcript accumulates.
    assert seen["image_url"] == "https://example.test/latest.png"


async def test_mesh_node_reads_plain_string_channel():
    run = MeshNode.compile(MeshConfig(model="fake", image_channel="photo"), NodeContext())
    update = await run({"photo": "https://example.test/lamp.png"})
    assert "![source](https://example.test/lamp.png)" in update["messages"][0].content


async def test_mesh_node_no_image_is_noop():
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    assert await run({"images": [], "messages": []}) == {}


async def test_mesh_node_ignores_non_url_text_in_the_image_channel():
    """A bare string channel carrying prose is not an image URL. Passing it to the provider would
    turn a wiring mistake into a confusing provider error."""
    run = MeshNode.compile(MeshConfig(model="fake", image_channel="input"), NodeContext())
    assert await run({"input": "a chair"}) == {}


async def test_mesh_node_rejects_an_unpriced_model():
    """Fail at compile, not mid-run: an unknown flat-rate model has no honest fail-closed price —
    `pricing._MOST_EXPENSIVE` is a *token* rate, so one generation would record as ≈$0."""
    with pytest.raises(ValueError, match="unknown 3D model"):
        MeshNode.compile(MeshConfig(model="fal-ai/not-a-real-model"), NodeContext())


async def test_mesh_node_emits_usage_for_metering(monkeypatch):
    """The node must emit a `{type:'usage', model, input_tokens, output_tokens}` payload with the
    keys `RunRecorder` buffers. Flat-rate per generation, so the unit count rides in
    `input_tokens` — the same move the Voice node makes with characters."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.mesh.safe_stream_writer", lambda: captured.append)
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    await run({"images": ["https://example.test/chair.png"]})

    usage = [p for p in captured if p.get("type") == "usage"]
    assert len(usage) == 1
    assert usage[0]["model"] == "fake"
    assert usage[0]["input_tokens"] == 1  # one generation
    assert usage[0]["output_tokens"] == 0

    # The source image streams *before* the provider call, so a run that takes tens of seconds
    # shows something immediately rather than going silent.
    tokens = [p for p in captured if p.get("type") == "token"]
    assert tokens[0]["text"].startswith("![source](https://example.test/chair.png)")


async def test_mesh_node_emits_asset_when_the_upload_is_durable(monkeypatch):
    """The `asset` event is what puts a generated mesh in the Media tab, and `kind` is what lets
    the tab filter it apart from images and audio."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.mesh.safe_stream_writer", lambda: captured.append)

    async def fake_put_blob(data, *, pathname, content_type):
        return f"https://store.public.blob.vercel-storage.com/{pathname}"

    monkeypatch.setattr("calypr_nodes._assets.put_blob", fake_put_blob)
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    await run({"images": ["https://example.test/chair.png"]})

    assets = [p for p in captured if p.get("type") == "asset"]
    assert len(assets) == 1
    a = assets[0]
    assert a["kind"] == "3d"
    assert a["url"].startswith("https://store.public.blob.vercel-storage.com/runs/glb/")
    assert a["pathname"].startswith("runs/glb/")
    assert a["content_type"] == "model/gltf-binary"
    assert a["model"] == "fake"
    assert a["bytes"] > 0


async def test_mesh_node_says_so_when_there_is_nowhere_to_store_the_mesh(monkeypatch):
    """Where Image and Voice inline a `data:` URI, this node reports the failure.

    A GLB runs to megabytes, and the assistant turn is persisted — so the fallback would write
    that base64 into a `message` row. The chat renderer refuses `data:` hrefs anyway, so it would
    print as text rather than render. Nothing is recorded as an asset either: there is no object
    to list or delete."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.mesh.safe_stream_writer", lambda: captured.append)
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    update = await run({"images": ["https://example.test/chair.png"]})

    assert [p for p in captured if p.get("type") == "asset"] == []
    assert not any("base64" in p.get("text", "") for p in captured)
    assert "storage isn\u2019t configured" in update["messages"][0].content
    # The source image still renders, so the run isn't a blank turn.
    assert "![source](https://example.test/chair.png)" in update["messages"][0].content


async def test_fake_mesh_client_returns_a_structurally_valid_glb():
    """Every test above asserts against the Fake client's bytes, so those bytes must really be a
    GLB — otherwise the suite would pass on a placeholder no viewer could open."""
    from calypr_model import FakeMeshClient

    result = await FakeMeshClient().generate(image_url="https://example.test/chair.png")
    assert result.data[:4] == b"glTF"
    assert int.from_bytes(result.data[8:12], "little") == len(result.data)  # header length
    assert result.units == 1


async def test_mesh_node_does_not_echo_an_image_already_in_the_transcript():
    """The `Image → 3D` case. The Image node has already put `![alt](url)` in `messages`, so
    echoing a `![source](url)` poster prints the same picture twice — which is what the shipped
    template did."""
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    update = await run({"messages": [AIMessage(content="![a chair](https://example.test/c.png)")]})
    assert "![source]" not in update["messages"][0].content


async def test_mesh_node_echoes_an_uploaded_image():
    """The Upload → 3D case, and why the poster exists at all: a URL seeded into `images` is not
    in the transcript, so without this the run never says what it was built from."""
    run = MeshNode.compile(MeshConfig(model="fake"), NodeContext())
    update = await run({"images": ["https://example.test/c.png"]})
    assert "![source](https://example.test/c.png)" in update["messages"][0].content


async def test_mesh_node_does_not_echo_when_the_channel_is_messages_itself():
    """Same rule when someone points `image_channel` at `messages` by hand — what matters is
    where the image came from, not which branch found it."""
    run = MeshNode.compile(MeshConfig(model="fake", image_channel="messages"), NodeContext())
    update = await run({"messages": [AIMessage(content="![c](https://example.test/c.png)")]})
    assert "![source]" not in update["messages"][0].content


async def test_mesh_node_passes_the_quality_knobs_through():
    """`texture_size` and `mesh_simplify` are the two levers on a bad mesh, so they have to reach
    the provider — a config field that never leaves the node is worse than no field."""
    seen: dict = {}

    class _Capture:
        async def generate(self, *, model, image_url, **kwargs):
            seen.update(kwargs)
            from calypr_model import FakeMeshClient

            return await FakeMeshClient().generate(model=model, image_url=image_url)

    cfg = MeshConfig(model="fake", texture_size=2048, mesh_simplify=0.9)
    run = MeshNode.compile(cfg, NodeContext(mesh_model=_Capture()))
    await run({"images": ["https://example.test/c.png"]})
    assert seen["texture_size"] == 2048
    assert seen["mesh_simplify"] == 0.9


async def test_texture_size_reaches_fal_as_an_integer():
    """fal validates an integer literal and answers `Input should be 512, 1024 or 2048` for the
    string — after the upstream Image node has already generated and billed. Pinned at the client
    boundary, which is the last place the type is still ours to fix."""
    sent: dict = {}

    class _Subscribe:
        async def subscribe(self, model, arguments, on_queue_update=None):
            sent.update(arguments)
            raise RuntimeError("stop here — the arguments are what is under test")

    from calypr_model.mesh_client import FalMeshClient

    client = FalMeshClient.__new__(FalMeshClient)  # skip __init__: no fal SDK, no key needed
    client._client = _Subscribe()
    with pytest.raises(RuntimeError, match="stop here"):
        # A stringy value, as a saved graph or hand-edited code could carry.
        await client.generate(image_url="https://example.test/c.png", texture_size="2048")
    assert sent["texture_size"] == 2048
    assert isinstance(sent["texture_size"], int)
