"""Video node — the fourth media block, and the first billed per second.

Mirrors `test_mesh_node.py` case for case, because the two nodes share a seam and most of a shape.
The cases that are *not* in that file are the ones worth reading: the price key carries the
resolution, the arguments reach fal as the string types its schema declares, and the two endpoint
families are validated against different resolution sets.
"""

from __future__ import annotations

import pytest
from calypr_model import (
    VIDEO_DURATIONS,
    VIDEO_MODELS,
    VIDEO_RESOLUTIONS,
    FakeVideoClient,
    VideoResult,
    is_image_to_video,
)
from calypr_nodes import NodeContext
from calypr_nodes.video import VideoConfig, VideoNode
from langchain_core.messages import AIMessage, HumanMessage

_T2V = "fal-ai/bytedance/seedance/v1/pro/fast/text-to-video"
_I2V = "fal-ai/bytedance/seedance/v1/pro/fast/image-to-video"


class _Capture:
    """A video client that records what it was asked for and returns a fixed clip."""

    def __init__(self) -> None:
        self.seen: dict = {}

    async def generate(self, **kwargs) -> VideoResult:
        self.seen = kwargs
        return VideoResult(
            data=b"mp4", units=int(kwargs.get("duration", 5)), resolution=kwargs["resolution"]
        )


def _run_node(cfg: VideoConfig, client=None):
    return VideoNode.compile(cfg, NodeContext(video_model=client or FakeVideoClient()))


@pytest.fixture
def blob(monkeypatch):
    """Blob storage configured. `conftest.py` unsets `BLOB_READ_WRITE_TOKEN` for the whole suite,
    so without this every run takes the "storage isn't configured" branch — which is a real case
    worth testing, but not the one most of these tests are about."""

    async def fake_put_blob(data, *, pathname, content_type):
        return f"https://store.public.blob.vercel-storage.com/{pathname}"

    monkeypatch.setattr("calypr_nodes._assets.put_blob", fake_put_blob)


async def test_video_node_appends_a_playable_link(blob):
    run = _run_node(VideoConfig(model="fake"))
    out = await run({"messages": [HumanMessage(content="a kite over the sea")]})
    assert "Play video.mp4" in out["messages"][0].content


async def test_video_node_reads_a_plain_string_channel(blob):
    run = _run_node(VideoConfig(model="fake", prompt_channel="input"))
    out = await run({"input": "a kite over the sea"})
    assert "Play video.mp4" in out["messages"][0].content


async def test_video_node_with_no_prompt_is_a_noop():
    run = _run_node(VideoConfig(model="fake"))
    assert await run({"messages": []}) == {}


async def test_image_to_video_falls_back_to_the_last_markdown_image_in_messages(blob):
    """What makes `Image → Video` work with nothing but an edge between the two blocks: the Image
    node appends `![alt](url)` to `messages` and this node picks the URL back out of it."""
    capture = _Capture()
    run = _run_node(VideoConfig(model=_I2V), capture)
    out = await run(
        {
            "messages": [
                AIMessage(content="![old](https://example.com/a.png)"),
                AIMessage(content="![new](https://example.com/b.png)"),
                HumanMessage(content="pan slowly to the left"),
            ]
        }
    )
    # Most recent wins — a transcript accumulates, and the clip should animate the latest frame.
    assert capture.seen["image_url"] == "https://example.com/b.png"
    assert "Play video.mp4" in out["messages"][0].content


async def test_the_prompt_skips_an_upstream_image_blocks_markdown(blob):
    """The bug the shipped `Image → Video` template had on day one, and it succeeded loudly enough
    to hide: the Image node leaves `![alt](url)` as the last message, so taking the last message
    outright sent fal a **blob URL** as the description of the motion. The only visible symptom was
    a `![` at the front of the generated clip's caption.

    The prompt has to walk back past the embed to what a human or an agent actually wrote."""
    capture = _Capture()
    run = _run_node(VideoConfig(model=_I2V), capture)
    await run(
        {
            "messages": [
                HumanMessage(content="a dreamy landscape of hills and valleys"),
                AIMessage(content="![a dreamy landscape](https://blob.example/runs/png/a.png)"),
            ]
        }
    )
    assert capture.seen["prompt"] == "a dreamy landscape of hills and valleys"
    assert "https://" not in capture.seen["prompt"]
    assert "![" not in capture.seen["prompt"]


async def test_a_message_that_mixes_text_and_an_embed_keeps_its_text(blob):
    """Only the embed is stripped, not the sentence around it — a walk-back that skipped the whole
    message would throw away the words the model needs."""
    capture = _Capture()
    run = _run_node(VideoConfig(model=_I2V), capture)
    await run({"messages": [AIMessage(content="pan slowly ![x](https://e.com/a.png) to the left")]})
    assert capture.seen["prompt"] == "pan slowly  to the left"


async def test_the_generated_caption_is_the_real_prompt(monkeypatch, blob):
    """The caption is what names the clip in the Media rail, so it inherits the same fix."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.video.safe_stream_writer", lambda: captured.append)
    run = _run_node(VideoConfig(model=_I2V), _Capture())
    await run(
        {
            "messages": [
                HumanMessage(content="a dreamy landscape"),
                AIMessage(content="![a dreamy landscape](https://blob.example/a.png)"),
            ]
        }
    )
    asset = next(e for e in captured if e["type"] == "asset")
    assert asset["caption"] == "a dreamy landscape"


async def test_image_to_video_with_no_image_anywhere_is_a_noop():
    run = _run_node(VideoConfig(model=_I2V))
    assert await run({"messages": [HumanMessage(content="pan left")]}) == {}


async def test_image_to_video_echoes_an_uploaded_image_but_not_one_already_in_the_transcript(
    blob,
):
    """The poster is progress, not decoration: generation runs minutes. It is shown when the
    source came from the `images` channel (invisible to the reader) and withheld when it came from
    `messages` (already on screen), so `Image → Video` doesn't print the same picture twice."""
    uploaded = _run_node(VideoConfig(model=_I2V), _Capture())
    out = await uploaded(
        {"images": ["https://example.com/up.png"], "messages": [HumanMessage(content="zoom in")]}
    )
    assert "![source](https://example.com/up.png)" in out["messages"][0].content

    from_chat = _run_node(VideoConfig(model=_I2V), _Capture())
    out = await from_chat(
        {
            "messages": [
                AIMessage(content="![generated](https://example.com/gen.png)"),
                HumanMessage(content="zoom in"),
            ]
        }
    )
    assert "![source]" not in out["messages"][0].content


# --- what fal is actually sent -----------------------------------------------------------------


async def test_the_knobs_reach_the_client_as_the_string_types_fal_validates():
    """fal's schema declares `resolution` and `duration` as string enums and rejects an int. The
    3D block lost a whole run to the mirror-image mistake (its docs showed `"1024"` where the API
    wanted `1024`), and here the failure would land *after* an upstream Image node had billed."""
    capture = _Capture()
    run = _run_node(
        VideoConfig(model=_T2V, resolution="1080p", duration="10", aspect_ratio="9:16"), capture
    )
    await run({"messages": [HumanMessage(content="a kite")]})
    assert capture.seen["resolution"] == "1080p"
    assert capture.seen["duration"] == "10"
    assert isinstance(capture.seen["duration"], str)
    assert capture.seen["aspect_ratio"] == "9:16"


async def test_text_to_video_sends_no_image_url():
    capture = _Capture()
    run = _run_node(VideoConfig(model=_T2V), capture)
    await run({"images": ["https://example.com/a.png"], "messages": [HumanMessage(content="hi")]})
    assert capture.seen["image_url"] == ""


# --- refusals ----------------------------------------------------------------------------------


def test_video_node_rejects_an_unpriced_model():
    with pytest.raises(ValueError, match="unknown video model"):
        VideoNode.compile(VideoConfig(model="fal-ai/some-new-thing"), NodeContext())


def test_video_node_rejects_a_resolution_the_model_does_not_offer():
    """Seedance 2.0 has no 1080p tier. Caught here rather than by fal, because fal catches it after
    the queue has been joined."""
    cfg = VideoConfig(model="bytedance/seedance-2.0/fast/text-to-video", resolution="1080p")
    with pytest.raises(ValueError, match="does not offer"):
        VideoNode.compile(cfg, NodeContext())


def test_video_node_rejects_an_unsupported_clip_length():
    with pytest.raises(ValueError, match="unsupported clip length"):
        VideoNode.compile(VideoConfig(model=_T2V, duration="30"), NodeContext())


def test_video_node_rejects_an_unsupported_aspect_ratio():
    with pytest.raises(ValueError, match="unsupported aspect ratio"):
        VideoNode.compile(VideoConfig(model=_T2V, aspect_ratio="auto"), NodeContext())


def test_every_offered_duration_is_accepted_by_every_model():
    """`VIDEO_DURATIONS` is the *intersection* of two families' ranges (1.0 takes 2–12, 2.0 takes
    4–15). If someone widens it to one family's range, this fails rather than shipping a menu item
    that 422s on half the endpoints."""
    for model in VIDEO_MODELS:
        for duration in VIDEO_DURATIONS:
            VideoNode.compile(VideoConfig(model=model, duration=duration), NodeContext())


# --- metering and storage ----------------------------------------------------------------------


async def test_usage_reports_seconds_and_carries_the_resolution_in_the_model_key(monkeypatch):
    """The whole reason video needs a compound price key: fal bills per second, and the rate
    roughly doubles between 480p and 720p, so `model` alone cannot price a clip."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.video.safe_stream_writer", lambda: captured.append)
    run = _run_node(VideoConfig(model=_T2V, resolution="480p", duration="8"), _Capture())
    await run({"messages": [HumanMessage(content="a kite")]})
    usage = next(e for e in captured if e["type"] == "usage")
    assert usage["model"] == f"{_T2V}@480p"
    assert usage["input_tokens"] == 8
    assert usage["output_tokens"] == 0


async def test_video_node_emits_an_asset_when_the_upload_is_durable(monkeypatch, blob):
    """The `asset` event is what puts a clip in the Media tab, and `kind` is what lets the tab
    filter it and the canvas show it in the block that made it."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.video.safe_stream_writer", lambda: captured.append)

    async def fake_put_blob(data, *, pathname, content_type):
        return f"https://store.public.blob.vercel-storage.com/{pathname}"

    monkeypatch.setattr("calypr_nodes._assets.put_blob", fake_put_blob)
    run = _run_node(VideoConfig(model="fake"))
    await run({"messages": [HumanMessage(content="a kite over the sea")]})
    asset = next(e for e in captured if e["type"] == "asset")
    assert asset["kind"] == "video"
    assert asset["pathname"].startswith("runs/mp4/")
    assert asset["content_type"] == "video/mp4"
    assert asset["caption"] == "a kite over the sea"
    assert asset["bytes"] > 0


async def test_video_node_says_so_when_there_is_nowhere_to_store_the_clip(monkeypatch):
    """No `data:` fallback, unlike Image and Voice: megabytes of base64 would land in a persisted
    `message` row and the chat renderer refuses `data:` hrefs anyway, so it would print as text."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.video.safe_stream_writer", lambda: captured.append)
    run = _run_node(VideoConfig(model="fake"))
    out = await run({"messages": [HumanMessage(content="a kite")]})
    assert "storage isn’t configured" in out["messages"][0].content
    assert "data:" not in out["messages"][0].content
    assert not [e for e in captured if e["type"] == "asset"]


# --- the model seam ----------------------------------------------------------------------------


async def test_the_fake_client_returns_a_structurally_valid_mp4():
    """The fixture every test above asserts against has to really be an mp4 container, or `fake`
    is a placeholder that no player will open — which is the one thing it promises to be."""
    result = await FakeVideoClient().generate(prompt="hi", duration="4")
    # ISO base media: a 4-byte big-endian box length, then the `ftyp` box type.
    assert result.data[4:8] == b"ftyp"
    assert result.content_type == "video/mp4"
    assert result.units == 4
    # No base64 companion: see `VideoResult.b64` for why encoding an 8 MB clip buys nothing.
    assert result.b64 == ""


def test_the_endpoint_id_is_the_only_record_of_which_direction_a_block_runs():
    assert is_image_to_video(_I2V)
    assert not is_image_to_video(_T2V)
    assert VideoNode.reads(VideoConfig(model=_I2V)) == ["messages", "images"]
    assert VideoNode.reads(VideoConfig(model=_T2V)) == ["messages"]


def test_every_model_declares_its_resolutions():
    assert set(VIDEO_RESOLUTIONS) == set(VIDEO_MODELS)
