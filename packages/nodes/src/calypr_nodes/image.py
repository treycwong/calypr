"""Image node — generate a visual from a text prompt (OpenAI image models, default gpt-image-2).

The modality counterpart to the LLM blocks: it reads a prompt from a channel, calls the image
provider, uploads the bytes to blob storage, and appends a Markdown image (`![alt](url)`) to the
output channel. Because the Playground renders streamed `token` events as Markdown, streaming that
same `![](url)` shows the image live with no new frontend rendering path or SSE event type.

Metering reuses the chat seam: the node emits the standard `usage` payload (the gpt-image models
are token-billed), so `RunRecorder` prices it and the spend kill-switch covers it — unchanged.

Storage: uploads to Vercel Blob (`put_blob`) for a small, durable URL. If blob isn't configured
(or `fake`), it degrades to an inline `data:` URI so the run still succeeds end-to-end.
"""

from __future__ import annotations

from typing import Any

from calypr_dsl import GraphSpec, Reducer, StateChannel
from calypr_model import is_image_to_video
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from calypr_nodes._assets import store_asset
from calypr_nodes._codegen import assign_str
from calypr_nodes._context import current_node_id
from calypr_nodes._convert import safe_stream_writer
from calypr_nodes._media import (
    PROMPT_INSTRUCTIONS,
    prompt_from,
    tag_producer,
    with_instructions,
)
from calypr_nodes._parse import (
    calls_named,
    docstring,
    kwarg_const,
    return_dict_key,
    state_get_keys,
    string_assign,
)
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    image_model_for_node,
    register,
)

_DOCSTRING = "Generate an image from the prompt and append it as a Markdown image."


class ImageConfig(BaseModel):
    model: str = "gpt-image-2"
    prompt_channel: str = "messages"  # where the prompt comes from (last message, or a string)
    output_channel: str = "messages"  # Markdown image is appended here
    size: str = "1024x1024"
    quality: str = "auto"
    n: int = 1
    style: str = Field(
        default="",
        description=(
            "A fixed style/instruction applied to every prompt, so this block generates a "
            "consistent look no matter what the user asks. Set it to specialize the generator — "
            "e.g. 'anime style illustration, vibrant colors, cel shading'. It is prepended to the "
            "user's request (or use a {prompt} placeholder to control the wording). Leave empty "
            "to pass the user's prompt through unchanged."
        ),
    )
    use_upload: bool | None = Field(
        default=None,
        description=(
            "When the user attaches a photo, use it instead of generating one. The block then "
            "makes nothing and costs nothing, and a media block downstream (Video, 3D) works from "
            "the photo. Runs without an attachment generate as usual. Unset (the default) means "
            "automatic: on when this block feeds an image-to-video or 3D block, off otherwise "
            "(see `resolve_use_upload`)."
        ),
    )
    images_channel: str = "images"  # where the run seeds the uploaded image URLs (see Upload)


def _feeds_photo_consumer(node_id: str, graph: GraphSpec) -> bool:
    """Whether `node_id` wires straight into a block that works *from* a picture: an
    image-to-video Video block, or a 3D block."""
    by_id = {n.id: n for n in graph.nodes}
    for edge in graph.edges:
        if edge.source != node_id or edge.target not in by_id:
            continue
        target = by_id[edge.target]
        cfg = target.config if isinstance(target.config, dict) else {}
        if target.type == "mesh":
            return True
        if target.type == "video":
            from calypr_nodes.video import VideoConfig  # local: video imports this module's peers

            if is_image_to_video(VideoConfig.model_validate(cfg).model):
                return True
    return False


def resolve_use_upload(graph: GraphSpec) -> GraphSpec:
    """Settle every Image block's automatic `use_upload` from the wiring (CAL-61).

    An Image block that feeds image-to-video or 3D is there to supply *a picture to work from*,
    so when the user attaches one, that is the picture. Projects saved before the setting existed
    have no value at all, and making them opt in was the bug the first fix left behind: a saved
    Image to video project still generated a new still over the user's photo.

    An explicit True/False is never changed. Called by everything that reads Image settings as a
    whole graph (compile, code export, the credit estimate) so they cannot disagree. Returns the
    graph unchanged when there is nothing to settle."""
    pending = [
        n
        for n in graph.nodes
        if n.type == "image"
        and (n.config if isinstance(n.config, dict) else {}).get("use_upload") is None
    ]
    if not pending:
        return graph
    resolved = graph.model_copy(deep=True)
    for node in resolved.nodes:
        if node.type == "image" and (node.config or {}).get("use_upload") is None:
            node.config = {
                **(node.config or {}),
                "use_upload": _feeds_photo_consumer(node.id, graph),
            }
    return resolved


def _uploaded(value: Any) -> list[str]:
    """The attached image URLs on the run's `images` channel, if any."""
    return [u for u in (value or []) if isinstance(u, str) and u.strip()]


def _apply_style(style: str, prompt: str) -> str:
    """Fold a fixed `style` into the user's prompt. `{prompt}` in the style is substituted;
    otherwise the style is prepended as a comma-led descriptor (how image models read style)."""
    style = style.strip()
    if not style:
        return prompt
    if "{prompt}" in style:
        return style.replace("{prompt}", prompt)
    return f"{style}, {prompt}"


@register
class ImageNode(BaseNode):
    type = "image"
    meta = NodeMeta(
        label="Image",
        category="io",
        icon="image",
        description="Generate an image from a prompt (gpt-image-2) and surface it in the run.",
    )
    config_model = ImageConfig

    @classmethod
    def reads(cls, cfg: ImageConfig) -> list[str]:
        return [cfg.prompt_channel, cfg.images_channel] if cfg.use_upload else [cfg.prompt_channel]

    @classmethod
    def writes(cls, cfg: ImageConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def channels(cls, cfg: ImageConfig) -> list[StateChannel]:
        # The output is a message list (appended Markdown-image AIMessages); declare it so a
        # non-default output channel still exists even if the canvas omits it.
        channels = [StateChannel(key=cfg.output_channel, type="messages", reducer=Reducer.append)]
        if cfg.use_upload:
            # Declared here, exactly as Upload declares it, because a graph with no Upload block
            # (Image to video) otherwise has no `images` channel at all, and LangGraph silently
            # drops the attachment from the run's input before any block can see it (CAL-61).
            channels.append(StateChannel(key=cfg.images_channel, type="list", reducer=Reducer.last))
        return channels

    @classmethod
    def compile(cls, cfg: ImageConfig, ctx: NodeContext) -> NodeFn:
        client = image_model_for_node(ctx, cfg.model)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            if cfg.use_upload and _uploaded(state.get(cfg.images_channel)):
                # Stand aside: the photo is already on the `images` channel, which is where a
                # Video or 3D block downstream looks first. Writing nothing keeps the transcript
                # free of a second copy (the user's own message already shows it), records no
                # usage, and stores no asset, because nothing was made.
                return {}
            raw = prompt_from(state.get(cfg.prompt_channel))
            if not raw:
                return {}
            # Style first, then the run's Prompt Instructions. The block's own `style` governs
            # the *form* of the prompt — on the shipped Image → 3D template it is what makes the
            # mesh usable — so the Input field adds criteria after it rather than replacing it.
            prompt = _apply_style(cfg.style, raw)
            prompt = with_instructions(prompt, state.get(PROMPT_INSTRUCTIONS))
            writer = safe_stream_writer()
            result = await client.generate(
                model=cfg.model,
                prompt=prompt,
                size=cfg.size,
                quality=cfg.quality,
                n=cfg.n,
            )
            # Meter like a chat call — same payload shape RunRecorder expects.
            writer(
                {
                    "type": "usage",
                    "node_id": current_node_id.get(None),
                    "model": cfg.model,
                    "input_tokens": result.usage.input_tokens,
                    "output_tokens": result.usage.output_tokens,
                }
            )
            # Single-line alt so `![…](…)` stays on one line for the line-based Markdown renderer.
            alt = " ".join(raw.split()).replace("]", "")[:80]
            stored = [
                await store_asset(data, ext="png", content_type=result.content_type, b64=b64)
                for data, b64 in zip(result.images, result.b64, strict=False)
            ]
            for asset in stored:
                # Record only what durably landed. A `data:` fallback is the file itself, so
                # there is no object to list or delete later — see `_assets.StoredAsset`.
                if not asset.durable:
                    continue
                writer(
                    {
                        "type": "asset",
                        "node_id": current_node_id.get(None),
                        "kind": "image",
                        "url": asset.url,
                        "pathname": asset.pathname,
                        "content_type": asset.content_type,
                        "bytes": asset.bytes,
                        "caption": alt,
                        "model": cfg.model,
                    }
                )
            markdown = "\n\n".join(f"![{alt}]({a.url})" for a in stored)
            # Stream it so the Playground renders the image live (token → <Markdown>).
            writer({"type": "token", "text": markdown})
            # Tagged with the node that made it, so a media block downstream can tell this
            # branch's picture from a parallel branch's — see `_media.image_url_from`.
            return {
                cfg.output_channel: [
                    AIMessage(
                        content=markdown,
                        additional_kwargs=tag_producer(current_node_id.get(None)),
                    )
                ]
            }

        return _run

    @classmethod
    def codegen(cls, cfg: ImageConfig, fn_name: str, ctx=None) -> CodeFragment:
        imports = [
            "from langchain_core.messages import AIMessage",
            "from openai import OpenAI",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Generate an image from the prompt and append it as a Markdown image."""',
            f'    value = state.get("{cfg.prompt_channel}")',
            "    prompt = value if isinstance(value, str) else "
            '(value[-1].content if value else "")',
        ]
        if cfg.use_upload:
            # After the prompt read on purpose: `parse` takes the prompt channel from the first
            # `state.get` and the upload channel from the second.
            ch = cfg.images_channel
            lines += [
                "    # A photo was attached: use it instead of generating. A Video or 3D step",
                f'    # reads it from "{ch}" directly, so there is nothing to make here.',
                f'    if [u for u in (state.get("{ch}") or []) if isinstance(u, str)]:',
                "        return {}",
            ]
        lines += [
            "    if not prompt:",
            "        return {}",
        ]
        if cfg.style.strip():
            # Fold the fixed style into the prompt (mirrors _apply_style's prepend semantics).
            lines += assign_str("style", cfg.style.strip())
            lines.append('    styled = f"{style}, {prompt}"')
        else:
            lines.append("    styled = prompt")
        if ctx is not None and getattr(ctx, "graph_instructions", False):
            # Emitted *after* the prompt read above, and it has to stay that way: `parse` recovers
            # the prompt channel as `state_get_keys(fn)[0]`, so an earlier read here would hand it
            # the wrong channel.
            lines += [
                f'    instructions = state.get("{PROMPT_INSTRUCTIONS}") or ""',
                "    if instructions:",
                '        styled = f"{styled}. {instructions}"',
            ]
        lines += [
            "    resp = OpenAI().images.generate(",
            f"        model={cfg.model!r}, prompt=styled, size={cfg.size!r}, "
            f"quality={cfg.quality!r}, n={cfg.n}",
            "    )",
            "    # Persist resp.data[i].b64_json to your blob store and use the returned URL.",
            '    data_uri = "data:image/png;base64," + resp.data[0].b64_json',
            '    markdown = f"![{prompt[:80]}]({data_uri})"',
            f'    return {{"{cfg.output_channel}": [AIMessage(content=markdown)]}}',
        ]
        return CodeFragment(fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports)

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> ImageConfig | None:
        """Recover an Image node. `model`/`size`/`quality`/`n` come from the
        `OpenAI().images.generate(...)` call; the prompt/output channels from the state read and
        return; the optional `style` from the emitted `style = "..."` literal (absent → none)."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        gen = calls_named(fn, "generate")
        keys = state_get_keys(fn)
        out = return_dict_key(fn)
        if not gen or not keys or out is None:
            return None
        call = gen[0]
        cfg = ImageConfig(prompt_channel=keys[0], output_channel=out, style="")
        # The second `state.get`, when present and not the run's Prompt Instructions, is the
        # attached-photo check that `use_upload` emits.
        uploads = [k for k in keys[1:] if k != PROMPT_INSTRUCTIONS]
        if uploads:
            cfg.use_upload = True
            cfg.images_channel = uploads[0]
        for field, attr in (("model", "model"), ("size", "size"), ("quality", "quality")):
            val = kwarg_const(call, attr)
            if isinstance(val, str):
                setattr(cfg, field, val)
        n = kwarg_const(call, "n")
        if isinstance(n, int):
            cfg.n = n
        style = string_assign(fn, "style")
        if style is not None:
            cfg.style = style
        return cfg
