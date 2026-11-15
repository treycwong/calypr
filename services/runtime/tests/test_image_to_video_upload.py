"""CAL-61: on Image to video, an attached photo is what gets animated, not a generated one.

Runs the shipped template end to end on the fake models and captures the image URL each media
client actually received, which is the thing the user saw go wrong in production (a generated
lion animated instead of their photo)."""

from __future__ import annotations

from typing import Any

from calypr_compiler.templates import STARTERS
from calypr_model import FakeModelClient
from calypr_nodes import NodeContext
from calypr_runtime.run import run_stream
from langgraph.checkpoint.memory import InMemorySaver

PHOTO = "https://blob.example/my-photo.jpg"


class _Video:
    def __init__(self) -> None:
        self.calls: list[str] = []

    async def generate(self, *, image_url: str = "", **_: Any):
        from calypr_model.video_client import FakeVideoClient

        self.calls.append(image_url)
        return await FakeVideoClient().generate(image_url=image_url, **_)


class _Image:
    def __init__(self) -> None:
        self.calls = 0

    async def generate(self, **kw: Any):
        from calypr_model.image_client import FakeImageClient

        self.calls += 1
        return await FakeImageClient().generate(**kw)


def _graph():
    return next(s for s in STARTERS if s.id == "tpl-image-to-video").model_copy(deep=True)


async def _run(images, ctx, thread="t", saver=None):
    return [
        ev
        async for ev in run_stream(
            _graph(),
            ctx,
            "Can you turn this image into a video?",
            images=images,
            thread_id=thread,
            checkpointer=saver,
        )
    ]


async def test_an_attached_photo_is_animated_and_nothing_is_generated():
    video, image = _Video(), _Image()
    ctx = NodeContext(model=FakeModelClient(reply="x"), image_model=image, video_model=video)
    events = await _run([PHOTO], ctx)
    assert image.calls == 0
    assert video.calls == [PHOTO]
    # Nothing generated means nothing metered for the image block.
    assert not [
        e for e in events if e.type == "usage" and (e.state or {}).get("node_id") == "image"
    ]


async def test_without_a_photo_the_generated_still_is_animated():
    video, image = _Video(), _Image()
    ctx = NodeContext(model=FakeModelClient(reply="x"), image_model=image, video_model=video)
    await _run([], ctx)
    assert image.calls == 1
    assert video.calls and video.calls[0] != PHOTO


async def test_a_later_text_only_turn_does_not_reuse_the_old_photo():
    """`images` is last-value and checkpointed; it is reset every turn so turn 2 generates."""
    saver = InMemorySaver()
    video, image = _Video(), _Image()
    ctx = NodeContext(model=FakeModelClient(reply="x"), image_model=image, video_model=video)
    await _run([PHOTO], ctx, thread="same", saver=saver)
    await _run([], ctx, thread="same", saver=saver)
    assert image.calls == 1  # only the second turn generated
    assert video.calls[0] == PHOTO and video.calls[1] != PHOTO


def _saved_before_the_fix():
    """An Image to video project saved before `use_upload` existed: the key is simply absent.
    This is the production project that still animated a generated dog over the user's photo."""
    g = _graph()
    for n in g.nodes:
        if n.type == "image":
            n.config = {k: v for k, v in n.config.items() if k != "use_upload"}
    return g


async def test_a_project_saved_before_the_setting_uses_the_photo_automatically():
    video, image = _Video(), _Image()
    ctx = NodeContext(model=FakeModelClient(reply="x"), image_model=image, video_model=video)
    events = [
        ev
        async for ev in run_stream(
            _saved_before_the_fix(),
            ctx,
            "Can you turn this image into an animated video",
            images=[PHOTO],
        )
    ]
    assert events
    assert image.calls == 0
    assert video.calls == [PHOTO]


async def test_an_explicit_generate_is_respected_even_before_video():
    g = _graph()
    for n in g.nodes:
        if n.type == "image":
            n.config = {**n.config, "use_upload": False}
    video, image = _Video(), _Image()
    ctx = NodeContext(model=FakeModelClient(reply="x"), image_model=image, video_model=video)
    _ = [ev async for ev in run_stream(g, ctx, "a dog in snow", images=[PHOTO])]
    assert image.calls == 1
