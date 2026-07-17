"""Voice/TTS node: synthesize speech (fake, keyless) and surface it as a Markdown audio link the
chat renders as a player, while emitting a character-count `usage` payload for metering."""

from __future__ import annotations

from calypr_nodes import NodeContext, TTSConfig
from calypr_nodes.tts import TTSNode
from langchain_core.messages import AIMessage, HumanMessage


async def test_tts_node_appends_audio_link():
    run = TTSNode.compile(TTSConfig(model="fake"), NodeContext())
    update = await run({"messages": [HumanMessage(content="Hello there")]})
    msgs = update["messages"]
    assert len(msgs) == 1
    assert isinstance(msgs[0], AIMessage)
    # No blob token in tests → data-URI fallback, but still a valid audio link the chat renders.
    assert msgs[0].content.startswith("[▶ Hello there](data:audio/wav;base64,")


async def test_tts_node_reads_plain_string_channel():
    run = TTSNode.compile(
        TTSConfig(model="fake", input_channel="input"), NodeContext()
    )
    update = await run({"input": "read this"})
    assert update["messages"][0].content.startswith("[▶ read this](")


async def test_tts_node_no_text_is_noop():
    run = TTSNode.compile(TTSConfig(model="fake"), NodeContext())
    assert await run({"messages": []}) == {}


async def test_tts_node_caption_is_single_line():
    """A multi-line input (e.g. an agent's joke with a newline) must yield a single-line audio
    link — the line-based Markdown renderer would otherwise show a multi-line link as raw text."""
    run = TTSNode.compile(TTSConfig(model="fake"), NodeContext())
    joke = "Why don't scientists trust atoms?\nBecause they make up everything!"
    update = await run({"messages": [HumanMessage(content=joke)]})
    content = update["messages"][0].content
    assert "\n" not in content  # the whole `[▶ …](…)` stays on one line
    assert content.startswith("[▶ Why don't scientists trust atoms? Because they make up")


async def test_tts_node_meters_by_characters(monkeypatch):
    """The node emits the standard `usage` payload with `input_tokens == len(text)` (chars are the
    TTS metering unit) so `RunRecorder` prices it per-1M-characters."""
    captured: list[dict] = []
    monkeypatch.setattr("calypr_nodes.tts.safe_stream_writer", lambda: captured.append)
    run = TTSNode.compile(TTSConfig(model="fake"), NodeContext())
    await run({"messages": [HumanMessage(content="abcdef")]})

    usage = [p for p in captured if p.get("type") == "usage"]
    assert len(usage) == 1
    assert usage[0]["model"] == "fake"
    assert usage[0]["input_tokens"] == 6 and usage[0]["output_tokens"] == 0
    tokens = [p for p in captured if p.get("type") == "token"]
    assert tokens and tokens[0]["text"].strip().startswith("[▶ abcdef](")


async def test_tts_node_passes_instructions():
    seen: dict = {}

    class _Capture:
        async def synthesize(self, *, model, text, voice, instructions, speed, response_format):
            seen.update(voice=voice, instructions=instructions)
            from calypr_model import TTSResult

            return TTSResult(
                audio=b"RIFF....", chars=len(text), content_type="audio/wav", b64="eA=="
            )

    ctx = NodeContext(tts_model=_Capture())  # injected client (mirrors model_for_node)
    run = TTSNode.compile(
        TTSConfig(model="gpt-4o-mini-tts", voice="verse", instructions="calm and slow"), ctx
    )
    await run({"messages": [HumanMessage(content="hi")]})
    assert seen == {"voice": "verse", "instructions": "calm and slow"}
