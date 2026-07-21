"""Voice / TTS node — speak text aloud (OpenAI speech, default gpt-4o-mini-tts).

The audio counterpart to the Image node: it reads text from a channel, synthesizes speech, stores
the audio, and appends a Markdown **audio link** (`[▶ caption](url)`) the chat turns into an inline
player. Streaming that link as a `token` shows the player live with no new SSE event type.

Metering reuses the chat seam: OpenAI's speech API returns no usage, so we meter by input character
count — the node emits it as `input_tokens`, and `pricing.py` prices TTS models per-1M-characters,
so `RunRecorder` + the spend kill-switch cover it unchanged.

Storage: uploads to Vercel Blob via `store_asset`; degrades to a `data:audio/…` URI when blob isn't
configured, so the run still surfaces the audio.
"""

from __future__ import annotations

from typing import Any

from calypr_dsl import Reducer, StateChannel
from langchain_core.messages import AIMessage
from pydantic import BaseModel, Field

from calypr_nodes._assets import store_asset
from calypr_nodes._context import current_node_id
from calypr_nodes._convert import safe_stream_writer, text_of
from calypr_nodes._parse import (
    calls_named,
    docstring,
    kwarg_const,
    return_dict_key,
    state_get_keys,
)
from calypr_nodes.registry import (
    BaseNode,
    CodeFragment,
    NodeContext,
    NodeFn,
    NodeMeta,
    NodeParseContext,
    register,
    tts_model_for_node,
)

_DOCSTRING = "Synthesize speech from the text and append it as a Markdown audio link."

# response_format → file extension (identity for the ones we expose).
_FORMAT_EXT = {"mp3": "mp3", "opus": "opus", "aac": "aac", "flac": "flac", "wav": "wav"}


class TTSConfig(BaseModel):
    model: str = "gpt-4o-mini-tts"
    voice: str = "alloy"
    instructions: str = Field(
        default="",
        description=(
            "How the voice should sound — tone, emotion, pacing, accent — applied to every "
            "utterance so this block has a consistent character (e.g. 'cheerful and upbeat, "
            "speaking quickly'). Only gpt-4o-mini-tts honors it. Leave empty for a neutral read."
        ),
    )
    speed: float = 1.0  # tts-1 / tts-1-hd only (0.25–4.0)
    response_format: str = "mp3"
    input_channel: str = "messages"  # where the text comes from (last message, or a string)
    output_channel: str = "messages"  # Markdown audio link is appended here


def _text_from(value: Any) -> str:
    """Resolve the text to speak: a plain string channel, or the last message's text."""
    if isinstance(value, str):
        return value
    if isinstance(value, list) and value:
        return text_of(value[-1])
    return ""


@register
class TTSNode(BaseNode):
    type = "tts"
    meta = NodeMeta(
        label="Voice",
        category="io",
        icon="volume-2",
        description="Speak text aloud (gpt-4o-mini-tts) and surface an audio player in the run.",
    )
    config_model = TTSConfig

    @classmethod
    def reads(cls, cfg: TTSConfig) -> list[str]:
        return [cfg.input_channel]

    @classmethod
    def writes(cls, cfg: TTSConfig) -> list[str]:
        return [cfg.output_channel]

    @classmethod
    def channels(cls, cfg: TTSConfig) -> list[StateChannel]:
        # Output is a message list (appended audio-link AIMessages); declare it so a non-default
        # output channel exists even if the canvas omits it (same as Image).
        return [StateChannel(key=cfg.output_channel, type="messages", reducer=Reducer.append)]

    @classmethod
    def compile(cls, cfg: TTSConfig, ctx: NodeContext) -> NodeFn:
        client = tts_model_for_node(ctx, cfg.model)

        async def _run(state: dict[str, Any]) -> dict[str, Any]:
            text = _text_from(state.get(cfg.input_channel))
            if not text:
                return {}
            writer = safe_stream_writer()
            result = await client.synthesize(
                model=cfg.model,
                text=text,
                voice=cfg.voice,
                instructions=cfg.instructions,
                speed=cfg.speed,
                response_format=cfg.response_format,
            )
            # Meter by characters — the field carries chars for TTS models (priced per 1M chars).
            writer(
                {
                    "type": "usage",
                    "node_id": current_node_id.get(None),
                    "model": cfg.model,
                    "input_tokens": result.chars,
                    "output_tokens": 0,
                }
            )
            ext = _FORMAT_EXT.get(cfg.response_format, "mp3")
            url = await store_asset(
                result.audio, ext=ext, content_type=result.content_type, b64=result.b64
            )
            # Collapse whitespace/newlines and drop `]` so the audio link stays on ONE line — the
            # Markdown renderer is line-based, and a multi-line `[…](…)` would render as raw text.
            caption = " ".join(text.split()).replace("]", "")[:60]
            markdown = f"[▶ {caption}]({url})"
            # Stream it so the Playground renders the player live (token → <Markdown>). Prepend a
            # blank line so the player sits on its own line below any upstream text (e.g. an Agent's
            # answer streamed into the same bubble), instead of jamming onto its last line.
            writer({"type": "token", "text": f"\n\n{markdown}"})
            return {cfg.output_channel: [AIMessage(content=markdown)]}

        return _run

    @classmethod
    def codegen(cls, cfg: TTSConfig, fn_name: str, ctx=None) -> CodeFragment:
        imports = [
            "from langchain_core.messages import AIMessage",
            "from openai import OpenAI",
        ]
        lines = [
            f"def {fn_name}(state: State) -> dict:",
            '    """Synthesize speech from the text and append it as a Markdown audio link."""',
            f'    value = state.get("{cfg.input_channel}")',
            "    text = value if isinstance(value, str) else "
            '(value[-1].content if value else "")',
            "    if not text:",
            "        return {}",
            "    resp = OpenAI().audio.speech.create(",
            f"        model={cfg.model!r}, voice={cfg.voice!r}, input=text, "
            f"response_format={cfg.response_format!r}",
            "    )",
            "    # Persist resp.read() (the audio bytes) to your blob store and use the URL.",
            "    import base64",
            f'    data_uri = "data:audio/{_FORMAT_EXT.get(cfg.response_format, "mp3")};base64," '
            "+ base64.b64encode(resp.read()).decode()",
            '    markdown = f"[▶ {text[:60]}]({data_uri})"',
            f'    return {{"{cfg.output_channel}": [AIMessage(content=markdown)]}}',
        ]
        return CodeFragment(fn_name=fn_name, function="\n".join(lines) + "\n", imports=imports)

    @classmethod
    def parse(cls, ctx: NodeParseContext) -> TTSConfig | None:
        """Recover a Voice/TTS node. `model`/`voice`/`response_format` come from the
        `OpenAI().audio.speech.create(...)` call; channels from the state read and return.
        `speed`/`instructions` aren't emitted into code, so they keep their defaults."""
        fn = ctx.func
        if fn is None or docstring(fn) != _DOCSTRING:
            return None
        create = calls_named(fn, "create")
        keys = state_get_keys(fn)
        out = return_dict_key(fn)
        if not create or not keys or out is None:
            return None
        call = create[0]
        cfg = TTSConfig(input_channel=keys[0], output_channel=out)
        for field, attr in (
            ("model", "model"),
            ("voice", "voice"),
            ("response_format", "response_format"),
        ):
            val = kwarg_const(call, attr)
            if isinstance(val, str):
                setattr(cfg, field, val)
        return cfg
