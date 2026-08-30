"""Video node — generate a clip with ByteDance Seedance on fal.

The fourth media block, after Image, Voice and 3D, and the first that can be driven *either* way:
Seedance publishes separate text-to-video and image-to-video endpoints, and this node covers both
from one config. Which one applies is read off the endpoint id (`is_image_to_video`) rather than
stored as a `mode` field — the id already carries the fact, and a second copy of it is a second
thing to keep in step.

That gives three canonical wirings with no change to any producer node: `Input → Video`
(text-to-video), `Upload → Video` and `Image → Video` (image-to-video, resolving the source picture
exactly the way the 3D block does, via `_media.image_url_from` and its `messages` fallback).

Metering reuses the chat seam, with one twist. fal bills video **per second and per resolution**,
and the rate roughly doubles between 480p and 720p — so a single per-model price would be a lie at
one of them. The node therefore reports `model` as `"<endpoint>@<resolution>"` (see
`calypr_model.priced_model`) and puts the clip length in `input_tokens`, so `pricing.MEDIA_PRICES`
still prices it with one exact lookup and `RunRecorder` needs no new path.

Storage follows the 3D block rather than Image/Voice: **no `data:` fallback**. An mp4 runs to
megabytes, the assistant turn is persisted (`conversations.py`) so the base64 would land in a
`message` row, and the chat renderer refuses `data:` hrefs by construction — it would print the
base64 as text. When blob storage isn't configured the run says the clip wasn't saved.

Video is **Plus and bring-your-own-fal-key**: `entitlements.PLUS_NODE_TYPES` gates the plan and
`model_access.missing_media_keys` refuses a run with no workspace fal key on file, so a clip always
runs on the customer's own key and contributes $0 to platform COGS. At $0.02–$0.24 a second that is
the difference between a block and a liability.
"""

from __future__ import annotations

from typing import Any

from calypr_dsl import Reducer, StateChannel
from calypr_model import (
    DEFAULT_VIDEO_ASPECT_RATIO,
    DEFAULT_VIDEO_DURATION,
    DEFAULT_VIDEO_MODEL,
    DEFAULT_VIDEO_RESOLUTION,
    VIDEO_ASPECT_RATIOS,
    VIDEO_DURATIONS,
    VIDEO_MODELS,
    VIDEO_RESOLUTIONS,
    is_image_to_video,
    priced_model,
)
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from calypr_nodes._assets import store_asset
from calypr_nodes._codegen import image_pick_lines
from calypr_nodes._context import current_node_id
from calypr_nodes._convert import safe_stream_writer
from calypr_nodes._media import (
    MESSAGES,
    PROMPT_INSTRUCTIONS,
    image_url_from,
    text_prompt_from,
    with_instructions,
)
from calypr_nodes._parse import (
    calls_named,
    docstring,
    kwarg_dict,
    return_dict_key,
    state_get_keys,
    str_const,
)
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
    video_model_for_node,
)

_DOCSTRING = "Generate a video from the prompt and append it as a playable link."

#: What the run says when the clip was generated but there is nowhere durable to put it. A sentence
#: rather than an inline `data:` URI — see the module docstring.
_NO_STORAGE_NOTICE = (
    "*The video was generated, but file storage isn’t configured on this deployment, "
    "so there is no link to play it.*"
)


class VideoConfig(BaseModel):
    model: str = DEFAULT_VIDEO_MODEL
    #: Where the prompt comes from. Used by every endpoint — Seedance requires a prompt even when
    #: animating an image, since the prompt is what describes the *motion*. Resolved with
    #: `text_prompt_from`, which walks past an upstream Image node's `![alt](url)`: taking the last
    #: message outright sent fal a blob URL as the motion description.
    prompt_channel: str = MESSAGES
    #: Where the source image URL comes from, for the image-to-video endpoints. Falls back to the
    #: last Markdown image in `messages`, which is what makes `Image → Video` work unwired.
    image_channel: str = "images"
    output_channel: str = MESSAGES  # the playable link is appended here
    #: 480p | 720p | 1080p, per model — 1080p is Seedance 1.0 only. **This is half the price**, not
    #: just a quality knob: 720p costs about twice 480p per second.
    resolution: str = DEFAULT_VIDEO_RESOLUTION
    #: Clip length in seconds, as a string (fal's schema declares a string enum). The billable unit.
    duration: str = DEFAULT_VIDEO_DURATION
    aspect_ratio: str = DEFAULT_VIDEO_ASPECT_RATIO


@register
class VideoNode(BaseNode):
    type = "video"
    meta = NodeMeta(
        label="Video",
        category="io",
        icon="clapperboard",
        description="Generate a short video from a prompt, or animate an image, with Seedance.",
    )
    config_model = VideoConfig

    @classmethod
    def reads(cls, cfg: VideoConfig) -> list[str]:
        # The prompt is read by every endpoint; the image only by the image-to-video pair. Naming
        # the image channel unconditionally would make the validator demand a picture for a plain
        # text-to-video graph.
        if is_image_to_video(cfg.model):
            return [cfg.prompt_channel, cfg.image_channel]
        return [cfg.prompt_channel]

    @classmethod
    def writes(cls, cfg: VideoConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def channels(cls, cfg: VideoConfig) -> list[StateChannel]:
        # Mirrors the Image and 3D nodes: declare the output so a non-default channel exists even
        # if the canvas omits it. The *input* channels aren't declared — `images` is owned by
        # Upload, and the fallbacks read `messages`, which every graph already has.
        return [StateChannel(key=cfg.output_channel, type="messages", reducer=Reducer.append)]

    @classmethod
    def compile(cls, cfg: VideoConfig, ctx: NodeContext) -> NodeFn:
        # Fail at compile time, not mid-run. Two distinct reasons, and neither is style:
        #   * an unpriced model or resolution would be recorded at a *token* rate (≈ $0) rather
        #     than its real per-second cost — see `VIDEO_MODELS`;
        #   * fal validates the enums server-side, so a bad value is a 422 that arrives *after* the
        #     queue has been joined and, in an `Image → Video` graph, after the upstream Image node
        #     has already generated and billed.
        injected = ctx.video_model is not None
        model = cfg.model.lower().strip()
        if not injected and model not in (*VIDEO_MODELS, "fake"):
            raise ValueError(
                f"unknown video model {cfg.model!r} — choose one of {', '.join(VIDEO_MODELS)}"
            )
        allowed = VIDEO_RESOLUTIONS.get(cfg.model)
        if allowed is not None and cfg.resolution not in allowed:
            raise ValueError(
                f"{cfg.model} does not offer {cfg.resolution!r} — choose one of "
                f"{', '.join(allowed)}"
            )
        if cfg.duration not in VIDEO_DURATIONS:
            raise ValueError(
                f"unsupported clip length {cfg.duration!r} — choose one of "
                f"{', '.join(VIDEO_DURATIONS)} (seconds)"
            )
        if cfg.aspect_ratio not in VIDEO_ASPECT_RATIOS:
            raise ValueError(
                f"unsupported aspect ratio {cfg.aspect_ratio!r} — choose one of "
                f"{', '.join(VIDEO_ASPECT_RATIOS)}"
            )
        client = video_model_for_node(ctx, cfg.model)
        wants_image = is_image_to_video(cfg.model)
        # The blocks this one is actually downstream of, so a fan-out animates the picture its
        # own branch produced rather than whichever landed in `messages` last.
        sources = set(ctx.upstream_ids)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            prompt = text_prompt_from(state.get(cfg.prompt_channel))
            # The run's Prompt Instructions, appended. This block has no `style` of its own —
            # the Input field is where a Video block gets steered.
            prompt = with_instructions(prompt, state.get(PROMPT_INSTRUCTIONS))
            image_url = ""
            poster = ""
            if wants_image:
                image_url = image_url_from(state.get(cfg.image_channel), sources)
                # Where the image came from decides whether it is worth showing again. From the
                # `images` channel (an Upload node) it is *not* in the transcript, so the run would
                # otherwise never say what it animated. From `messages` it already is — and echoing
                # it there prints the same picture twice, which is what `Image → Video` would do.
                from_transcript = bool(image_url) and cfg.image_channel == MESSAGES
                if not image_url and cfg.image_channel != MESSAGES:
                    image_url = image_url_from(state.get(MESSAGES), sources)
                    from_transcript = bool(image_url)
                if not image_url:
                    return {}
                poster = "" if from_transcript else f"![source]({image_url})"
            if not prompt:
                return {}

            writer = safe_stream_writer()
            # Show the source frame *before* the call when it isn't already on screen. Generation
            # runs one to three minutes — several times longer than image→3D — and this is honest
            # progress the user can see. The poster is part of the final message anyway, so nothing
            # extra is written to achieve it.
            if poster:
                writer({"type": "token", "text": poster + "\n\n"})

            result = await client.generate(
                model=cfg.model,
                prompt=prompt,
                image_url=image_url,
                resolution=cfg.resolution,
                duration=cfg.duration,
                aspect_ratio=cfg.aspect_ratio,
            )
            # Meter like a chat call — same payload shape RunRecorder expects. Per *second*, so the
            # clip length rides in `input_tokens` (as TTS does with characters), and the resolution
            # rides in the model key because it doubles the rate.
            writer(
                {
                    "type": "usage",
                    "node_id": current_node_id.get(None),
                    "model": priced_model(cfg.model, result.resolution),
                    "input_tokens": result.units,
                    "output_tokens": 0,
                }
            )
            stored = await store_asset(
                result.data, ext="mp4", content_type=result.content_type, b64=result.b64
            )
            # Record only what durably landed — a `data:` fallback is the file itself, so there is
            # no object to list or delete later. See `_assets.StoredAsset`.
            if stored.durable:
                writer(
                    {
                        "type": "asset",
                        "node_id": current_node_id.get(None),
                        "kind": "video",
                        "url": stored.url,
                        "pathname": stored.pathname,
                        "content_type": stored.content_type,
                        "bytes": stored.bytes,
                        "caption": " ".join(prompt.split()).replace("]", "")[:80],
                        "model": cfg.model,
                    }
                )
            link = f"[▶ Play video.mp4]({stored.url})" if stored.durable else _NO_STORAGE_NOTICE
            writer({"type": "token", "text": link})
            content = f"{poster}\n\n{link}" if poster else link
            return {cfg.output_channel: [AIMessage(content=content)]}

        return _run

    @classmethod
    def codegen(cls, cfg: VideoConfig, fn_name: str, ctx=None) -> CodeFragment:
        imports = [
            "import re",
            "import fal_client",
            "from langchain_core.messages import AIMessage",
        ]
        wants_image = is_image_to_video(cfg.model)
        # Every knob `parse()` recovers has to be emitted here, and nothing else: the round-trip
        # mutation suite edits these literals and expects the config back. They ride *inside* the
        # `arguments={...}` dict rather than as kwargs, the same shape the 3D block uses. The two
        # runtime values are emitted as bare variable names, which is exactly why the parser skips
        # non-constant entries instead of refusing the dict.
        entries = ['"prompt": prompt']
        if wants_image:
            entries.append('"image_url": image_url')
        entries += [
            f'"resolution": {cfg.resolution!r}',
            f'"duration": {cfg.duration!r}',
            f'"aspect_ratio": {cfg.aspect_ratio!r}',
        ]
        literal = ", ".join(entries)
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            f'    """{_DOCSTRING}"""',
            f'    value = state.get("{cfg.prompt_channel}")',
            "    if isinstance(value, str):",
            "        prompt = value",
            "    else:",
            "        # Skip messages that are only a media embed. An Image block upstream leaves",
            "        # `![alt](url)` as the last message, and passing that through would send the",
            "        # model a URL where it expects a description of the motion.",
            '        texts = [re.sub(r"!\\[[^\\]]*\\]\\([^)]*\\)", "", '
            'str(m.content)).strip() for m in value or []]',
            '        prompt = next((t for t in reversed(texts) if t), "")',
        ]
        if wants_image:
            sources = list(getattr(ctx, "image_sources", []) or [])
            lines += image_pick_lines(cfg.image_channel, sources, "image_url")
            lines += [
                "    if not prompt or not image_url:",
                "        return {}",
            ]
            if sources:
                imports.append("import re")
        else:
            lines += [
                "    if not prompt:",
                "        return {}",
            ]
        if ctx is not None and getattr(ctx, "graph_instructions", False):
            # After the prompt and image reads above, and it must stay there: `parse` recovers the
            # prompt channel as `state_get_keys(fn)[0]` and the image channel as `[1]`, so a read
            # inserted earlier would silently shift both.
            lines += [
                f'    instructions = state.get("{PROMPT_INSTRUCTIONS}") or ""',
                "    if instructions:",
                '        prompt = f"{prompt}. {instructions}"',
            ]
        lines += [
            "    result = fal_client.subscribe(",
            f"        {cfg.model!r}, arguments={{{literal}}}",
            "    )",
            "    # Persist result['video']['url'] to your own store if you need it to last —",
            "    # fal's URLs expire.",
            '    url = result["video"]["url"]',
            '    markdown = f"[▶ Play video.mp4]({url})"',
            f'    return {{"{cfg.output_channel}": [AIMessage(content=markdown)]}}',
        ]
        return CodeFragment(fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports)

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> VideoConfig | None:
        """Recover a Video node. `model` is the first positional argument of the
        `fal_client.subscribe(...)` call; the channels come from the state reads and the return.

        The 3D block generates a `subscribe(...)` call too, so the docstring — checked first here
        and there — is what keeps the two recognisers from claiming each other's functions."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        subscribe = calls_named(fn, "subscribe")
        keys = state_get_keys(fn)
        out = return_dict_key(fn)
        if not subscribe or not keys or out is None:
            return None
        cfg = VideoConfig(prompt_channel=keys[0], output_channel=out)
        call = subscribe[0]
        model = str_const(call.args[0]) if call.args else None
        if isinstance(model, str):
            cfg.model = model
        # An image-to-video export reads a second channel; a text-to-video one doesn't, and must
        # keep the default rather than inheriting the prompt channel.
        if is_image_to_video(cfg.model) and len(keys) > 1:
            cfg.image_channel = keys[1]
        # The knobs ride inside the `arguments={...}` literal rather than as kwargs, so they
        # come back through `kwarg_dict` rather than `kwarg_const` (which only reads constants,
        # and a dict literal isn't one). `resolution` is half the price, so it has to survive a
        # round trip or an edited export would bill differently from the graph it came from.
        args = kwarg_dict(call, "arguments")
        for field in ("resolution", "duration", "aspect_ratio"):
            if isinstance(value := args.get(field), str):
                setattr(cfg, field, value)
        return cfg
