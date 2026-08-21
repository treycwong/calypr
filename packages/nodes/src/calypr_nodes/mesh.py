"""3D node — turn an image into a downloadable 3D model (fal, default `fal-ai/trellis`).

The third media block, after Image and Voice, and the first that takes an image *in*: it reads an
image URL from state, generates a GLB, stores it, and appends a Markdown block carrying the source
image plus a download link. Because the Playground renders streamed `token` events as Markdown,
that shows up live with no new SSE event type — the same trick Image and Voice use.

**Where the image comes from** is the one thing this node does that its siblings don't. Two
producers already exist and neither had to change: the Upload node seeds URLs into the `images`
channel, and the Image node appends `![alt](url)` to `messages`. So `image_channel` is read first
and, when it's empty, the last Markdown image in `messages` is used. That fallback is what makes
`Image → 3D` work on the canvas without widening the Image node's `writes()`, which would ripple
through the wiring matrix and the round-trip parser for no gain.

Metering reuses the chat seam: mesh generation is billed per *generation*, so the node reports the
unit count in the `input_tokens` field and `pricing.MEDIA_PRICES` prices it — exactly how the Voice
node reports characters. `RunRecorder` and the spend kill-switch cover it unchanged.

Storage: uploads to Vercel Blob via `store_asset`. Where Image and Voice fall back to an inline
`data:` URI, this node **says the mesh wasn't saved instead**. Two reasons, and both are specific
to this modality: a GLB runs to megabytes where a preview PNG or a short clip does not, and the
assistant turn is persisted (`conversations.py`), so the fallback would write that base64 straight
into a `message` row. The chat renderer also refuses `data:` hrefs by construction, so the link
would not even render — it would print the base64 as text.
"""

from __future__ import annotations

import re
from typing import Any

from calypr_dsl import Reducer, StateChannel
from calypr_model import MESH_MODELS
from langchain_core.messages import AIMessage
from pydantic import BaseModel

from calypr_nodes._assets import store_asset
from calypr_nodes._context import current_node_id
from calypr_nodes._convert import safe_stream_writer, text_of
from calypr_nodes._parse import (
    calls_named,
    docstring,
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
    mesh_model_for_node,
    register,
)

_DOCSTRING = "Generate a 3D model from the image and append it as a download link."

#: The canonical message channel every node defaults to — where the Image node leaves its
#: `![alt](url)`. Hardcoded rather than exposed as config: it is the fallback source, and a second
#: channel field would be a knob with one sensible value.
_MESSAGES = "messages"

_MD_IMAGE = re.compile(r"!\[[^\]]*\]\(\s*(\S+?)\s*\)")

#: What the run says when the mesh was generated but there is nowhere durable to put it. See the
#: module docstring for why this is a sentence rather than an inline `data:` URI.
_NO_STORAGE_NOTICE = (
    "*The 3D model was generated, but file storage isn\u2019t configured on this deployment, "
    "so there is no link to download it.*"
)


def _md_image_url(text: str) -> str:
    """The last Markdown image URL in `text`, or "". Last rather than first: a transcript
    accumulates, and the mesh should be built from the most recently generated image."""
    matches = _MD_IMAGE.findall(text or "")
    return matches[-1] if matches else ""


def _image_url_from(value: Any) -> str:
    """Resolve an image URL from a channel: a plain string, a list of URLs (the `images` channel
    the Upload node seeds), or a message list carrying a Markdown image. Most recent wins."""
    if isinstance(value, str):
        return value.strip() if value.strip().startswith(("http", "data:")) else ""
    if isinstance(value, list):
        for item in reversed(value):
            if isinstance(item, str) and item.strip():
                return item.strip()
            url = _md_image_url(text_of(item))
            if url:
                return url
    return ""


class MeshConfig(BaseModel):
    model: str = "fal-ai/trellis"
    #: Where the source image URL comes from. Falls back to the last Markdown image in `messages`.
    image_channel: str = "images"
    output_channel: str = "messages"  # the source image + download link are appended here


@register
class MeshNode(BaseNode):
    type = "mesh"
    meta = NodeMeta(
        label="3D",
        category="io",
        icon="box",
        description="Turn an image into a downloadable 3D model (GLB) and surface it in the run.",
    )
    config_model = MeshConfig

    @classmethod
    def reads(cls, cfg: MeshConfig) -> list[str]:
        return [cfg.image_channel]

    @classmethod
    def writes(cls, cfg: MeshConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def channels(cls, cfg: MeshConfig) -> list[StateChannel]:
        # Mirrors the Image node: declare the output so a non-default channel exists even if the
        # canvas omits it. The *input* channel isn't declared — `images` is owned by Upload, and
        # the fallback reads `messages`, which every graph already has.
        return [StateChannel(key=cfg.output_channel, type="messages", reducer=Reducer.append)]

    @classmethod
    def compile(cls, cfg: MeshConfig, ctx: NodeContext) -> NodeFn:
        # Fail at compile time, not mid-run: an unpriced mesh model would be recorded at a token
        # rate (≈ $0) rather than its real flat cost. See `MESH_MODELS`.
        if ctx.mesh_model is None and cfg.model.lower().strip() not in (*MESH_MODELS, "fake"):
            raise ValueError(
                f"unknown 3D model {cfg.model!r} — choose one of {', '.join(MESH_MODELS)}"
            )
        client = mesh_model_for_node(ctx, cfg.model)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            image_url = _image_url_from(state.get(cfg.image_channel))
            # Where the image came from decides whether it is worth showing again. From the
            # `images` channel (an Upload node) it is *not* in the transcript, so the run would
            # otherwise never say what it was built from. From `messages` it already is — and
            # echoing it there prints the same picture twice, which is exactly what the shipped
            # `Image → 3D` template does.
            # True also when `image_channel` *is* `messages` — the source is what matters, not
            # which branch found it.
            from_transcript = bool(image_url) and cfg.image_channel == _MESSAGES
            if not image_url and cfg.image_channel != _MESSAGES:
                image_url = _image_url_from(state.get(_MESSAGES))
                from_transcript = bool(image_url)
            if not image_url:
                return {}
            writer = safe_stream_writer()
            # Show the source image *before* the call when it isn't already on screen. Generation
            # runs tens of seconds, and this is honest progress the user can see — the poster is
            # part of the final message anyway, so nothing extra is written to achieve it.
            poster = "" if from_transcript else f"![source]({image_url})"
            if poster:
                writer({"type": "token", "text": poster + "\n\n"})

            result = await client.generate(model=cfg.model, image_url=image_url)
            # Meter like a chat call — same payload shape RunRecorder expects. Flat-rate per
            # generation, so the unit count rides in `input_tokens` (as TTS does with characters).
            writer(
                {
                    "type": "usage",
                    "node_id": current_node_id.get(None),
                    "model": cfg.model,
                    "input_tokens": result.units,
                    "output_tokens": 0,
                }
            )
            stored = await store_asset(
                result.data, ext="glb", content_type=result.content_type, b64=result.b64
            )
            # Record only what durably landed — a `data:` fallback is the file itself, so there is
            # no object to list or delete later. See `_assets.StoredAsset`.
            if stored.durable:
                writer(
                    {
                        "type": "asset",
                        "node_id": current_node_id.get(None),
                        "kind": "3d",
                        "url": stored.url,
                        "pathname": stored.pathname,
                        "content_type": stored.content_type,
                        "bytes": stored.bytes,
                        "caption": "3D model",
                        "model": cfg.model,
                    }
                )
            link = f"[⬇ Download model.glb]({stored.url})" if stored.durable else _NO_STORAGE_NOTICE
            writer({"type": "token", "text": link})
            content = f"{poster}\n\n{link}" if poster else link
            return {cfg.output_channel: [AIMessage(content=content)]}

        return _run

    @classmethod
    def codegen(cls, cfg: MeshConfig, fn_name: str, ctx=None) -> CodeFragment:
        imports = [
            "import fal_client",
            "from langchain_core.messages import AIMessage",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            f'    """{_DOCSTRING}"""',
            f'    value = state.get("{cfg.image_channel}")',
            '    image_url = value if isinstance(value, str) else (value[-1] if value else "")',
            "    if not image_url:",
            "        return {}",
            "    result = fal_client.subscribe(",
            f'        {cfg.model!r}, arguments={{"image_url": image_url}}',
            "    )",
            "    # Persist result['model_mesh']['url'] to your own store if you need it to last.",
            '    url = result["model_mesh"]["url"]',
            '    markdown = f"![source]({image_url})\\n\\n[⬇ Download model.glb]({url})"',
            f'    return {{"{cfg.output_channel}": [AIMessage(content=markdown)]}}',
        ]
        return CodeFragment(fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports)

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> MeshConfig | None:
        """Recover a 3D node. `model` is the first positional argument of the
        `fal_client.subscribe(...)` call; the channels come from the state read and the return."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        subscribe = calls_named(fn, "subscribe")
        keys = state_get_keys(fn)
        out = return_dict_key(fn)
        if not subscribe or not keys or out is None:
            return None
        cfg = MeshConfig(image_channel=keys[0], output_channel=out)
        args = subscribe[0].args
        model = str_const(args[0]) if args else None
        if isinstance(model, str):
            cfg.model = model
        return cfg
