"""Text-to-speech seam — the audio sibling of the image client (chat is text-only).

Mirrors `image_client.py`: a provider-neutral result carrying raw bytes plus the metering unit, so
the same `usage` → `RunRecorder` path meters TTS unchanged. OpenAI's speech API returns raw audio
with **no usage object**, so the metering unit is the input **character count** (`chars`), which the
node emits as `input_tokens` and `pricing.py` prices per-1M-characters.

`instructions` (tone/style steering) is only honored by `gpt-4o-mini-tts`; `speed` only by the
`tts-1` family — so we send each only when it applies.
"""

from __future__ import annotations

import base64
import os
import struct
from dataclasses import dataclass

from openai import AsyncOpenAI

_INSTRUCTABLE = ("gpt-4o-mini-tts",)  # models that accept the `instructions` steering field


def _silent_wav(ms: int = 1200) -> bytes:
    """A tiny valid silent WAV (mono, 8kHz, 16-bit) — the Fake client's deterministic, key-free
    output. Real bytes, so the browser <audio> still loads/plays (mirrors FakeImageClient)."""
    rate, samples = 8000, int(8000 * ms / 1000)
    data = b"\x00\x00" * samples
    return (
        b"RIFF"
        + struct.pack("<I", 36 + len(data))
        + b"WAVEfmt "
        + struct.pack("<IHHIIHH", 16, 1, 1, rate, rate * 2, 2, 16)
        + b"data"
        + struct.pack("<I", len(data))
        + data
    )


_FAKE_WAV = _silent_wav()
_FORMAT_MIME = {
    "mp3": "audio/mpeg",
    "opus": "audio/opus",
    "aac": "audio/aac",
    "flac": "audio/flac",
    "wav": "audio/wav",
    "pcm": "audio/pcm",
}


@dataclass
class TTSResult:
    """One speech turn: the raw audio bytes plus the character count used for metering."""

    audio: bytes
    chars: int
    content_type: str = "audio/mpeg"
    b64: str = ""


class OpenAITTSClient:
    """Synthesize speech with OpenAI's audio API. Reads OPENAI_API_KEY from env."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    async def synthesize(
        self,
        *,
        model: str = "gpt-4o-mini-tts",
        text: str,
        voice: str = "alloy",
        instructions: str = "",
        speed: float = 1.0,
        response_format: str = "mp3",
    ) -> TTSResult:
        kwargs: dict = {
            "model": model,
            "input": text,
            "voice": voice,
            "response_format": response_format,
        }
        if instructions and model in _INSTRUCTABLE:
            kwargs["instructions"] = instructions
        if speed and speed != 1.0 and model not in _INSTRUCTABLE:
            kwargs["speed"] = speed
        resp = await self._client.audio.speech.create(**kwargs)
        audio = await resp.aread()
        return TTSResult(
            audio=audio,
            chars=len(text),
            content_type=_FORMAT_MIME.get(response_format, "audio/mpeg"),
            b64=base64.b64encode(audio).decode(),
        )


class FakeTTSClient:
    """Deterministic, key-free TTS for tests/CI — a short silent WAV, no network, chars=len."""

    async def synthesize(
        self,
        *,
        model: str = "fake",
        text: str,
        voice: str = "alloy",
        instructions: str = "",
        speed: float = 1.0,
        response_format: str = "mp3",
    ) -> TTSResult:
        return TTSResult(
            audio=_FAKE_WAV,
            chars=len(text),
            content_type="audio/wav",
            b64=base64.b64encode(_FAKE_WAV).decode(),
        )
