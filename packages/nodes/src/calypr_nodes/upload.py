"""Upload node — bring the user's image into the conversation for a vision Agent.

The input counterpart to the Image/Voice media blocks: the Playground uploads the file to blob
storage and passes its URL in the run request; the runtime seeds it into the `images` state
channel; this node turns those URLs into a multimodal HumanMessage (langchain `image_url` content
blocks) appended to `messages`. A downstream Agent on an OpenAI vision model (gpt-4o / gpt-4o-mini)
then *sees* the image — `lc_to_msgs` lifts the blocks into `Msg.images` and the OpenAI adapter
builds the vision payload.

With no image attached the node is a no-op, so upload-capable graphs still answer plain text.
No metering here — vision input tokens are counted by the provider in the Agent's usage event.
"""

from __future__ import annotations

import ast
from typing import Any

from calypr_dsl import Reducer, StateChannel
from langchain_core.messages import HumanMessage
from pydantic import BaseModel

from calypr_nodes._parse import docstring, return_dict_key, state_get_keys
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
)

_DOCSTRING = "Append the uploaded image(s) as a vision message for the next agent."


class UploadConfig(BaseModel):
    images_channel: str = "images"  # where the run seeds the uploaded image URLs
    target_channel: str = "messages"  # the multimodal message is appended here
    max_images: int = 4


def _image_message(urls: list[str]) -> HumanMessage:
    return HumanMessage(
        content=[{"type": "image_url", "image_url": {"url": u}} for u in urls]
    )


@register
class UploadNode(BaseNode):
    type = "upload"
    meta = NodeMeta(
        label="Upload",
        category="io",
        icon="paperclip",
        description="Attach the user's uploaded image(s) so a vision Agent can review them.",
    )
    config_model = UploadConfig

    @classmethod
    def reads(cls, cfg: UploadConfig) -> list[str]:
        return [cfg.images_channel]

    @classmethod
    def writes(cls, cfg: UploadConfig) -> list[str]:
        return [cfg.target_channel]

    @classmethod
    def channels(cls, cfg: UploadConfig) -> list[StateChannel]:
        # `last` (not append): each run/turn's uploads replace the previous ones — attachments
        # are per-message, not an ever-growing archive.
        return [StateChannel(key=cfg.images_channel, type="list", reducer=Reducer.last)]

    @classmethod
    def compile(cls, cfg: UploadConfig, ctx: NodeContext) -> NodeFn:
        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            urls = [u for u in (state.get(cfg.images_channel) or []) if isinstance(u, str)]
            if not urls:
                return {}  # no attachment → pass through; the graph still answers text-only
            return {cfg.target_channel: [_image_message(urls[: cfg.max_images])]}

        return _run

    @classmethod
    def codegen(cls, cfg: UploadConfig, fn_name: str, ctx=None) -> CodeFragment:
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Append the uploaded image(s) as a vision message for the next agent."""',
            f'    urls = [u for u in (state.get("{cfg.images_channel}") or [])',
            "            if isinstance(u, str)]",
            "    if not urls:",
            "        return {}",
            "    blocks = [",
            '        {"type": "image_url", "image_url": {"url": u}}',
            f"        for u in urls[:{cfg.max_images}]",
            "    ]",
            f'    return {{"{cfg.target_channel}": [HumanMessage(content=blocks)]}}',
        ]
        return CodeFragment(
            fn_name=fn_name,
            function="\n".join(lines) + "\n",
            imports=["from langchain_core.messages import HumanMessage"],
        )

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> UploadConfig | None:
        """Recover an Upload node: it reads the uploaded URLs from `state.get("<images_channel>")`
        and appends a vision `HumanMessage`. `max_images` is the `urls[:<n>]` slice bound."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        keys = state_get_keys(fn)
        target = return_dict_key(fn)
        if not keys or target is None:
            return None
        cfg = UploadConfig(images_channel=keys[0], target_channel=target)
        for sub in (n for n in ast.walk(fn) if isinstance(n, ast.Subscript)):
            sl = sub.slice
            if isinstance(sl, ast.Slice) and isinstance(sl.upper, ast.Constant):
                if isinstance(sl.upper.value, int):
                    cfg.max_images = sl.upper.value
                    break
        return cfg
