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

from calypr_dsl import Reducer, StateChannel
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from calypr_nodes._assets import store_asset
from calypr_nodes._codegen import assign_str
from calypr_nodes._context import current_node_id
from calypr_nodes._convert import safe_stream_writer, text_of
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


def _prompt_from(value: Any) -> str:
    """Resolve the prompt: a plain string channel, or the last message's text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return text_of(value[-1])
    return ""


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
        return [cfg.prompt_channel]

    @classmethod
    def writes(cls, cfg: ImageConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def channels(cls, cfg: ImageConfig) -> list[StateChannel]:
        # The output is a message list (appended Markdown-image AIMessages); declare it so a
        # non-default output channel still exists even if the canvas omits it.
        return [StateChannel(key=cfg.output_channel, type="messages", reducer=Reducer.append)]

    @classmethod
    def compile(cls, cfg: ImageConfig, ctx: NodeContext) -> NodeFn:
        client = image_model_for_node(ctx, cfg.model)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            raw = _prompt_from(state.get(cfg.prompt_channel))
            if not raw:
                return {}
            prompt = _apply_style(cfg.style, raw)  # what the model sees (raw + fixed style)
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
            urls = [
                await store_asset(data, ext="png", content_type=result.content_type, b64=b64)
                for data, b64 in zip(result.images, result.b64, strict=False)
            ]
            markdown = "\n\n".join(f"![{alt}]({url})" for url in urls)
            # Stream it so the Playground renders the image live (token → <Markdown>).
            writer({"type": "token", "text": markdown})
            return {cfg.output_channel: [AIMessage(content=markdown)]}

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
            "    if not prompt:",
            "        return {}",
        ]
        if cfg.style.strip():
            # Fold the fixed style into the prompt (mirrors _apply_style's prepend semantics).
            lines += assign_str("style", cfg.style.strip())
            lines.append('    styled = f"{style}, {prompt}"')
        else:
            lines.append("    styled = prompt")
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
