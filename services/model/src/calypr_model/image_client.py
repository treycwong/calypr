"""Image-generation seam — the modality sibling of `ModelClient` (chat is text-only).

`ModelClient.stream` is deliberately chat/tool oriented, so image generation gets its own thin
client rather than overloading it. The shape mirrors the chat seam: a provider-neutral result
carrying raw bytes plus a `Usage` event, so the *same* metering path a chat node uses works for
images unchanged (the node emits a `usage` payload; `RunRecorder` prices it).

gpt-image-1 always returns base64 (`b64_json`) and rejects `response_format`, so we never send it.
"""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, field

from openai import AsyncOpenAI

from calypr_model.events import Usage

# A 1×1 transparent PNG — the Fake client's deterministic, key-free output (like FakeModelClient).
_FAKE_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


@dataclass
class ImageResult:
    """One image-generation turn: the raw image bytes plus token usage for metering."""

    images: list[bytes]
    usage: Usage
    content_type: str = "image/png"
    # b64 kept around for callers (e.g. the Fake path) that want a data URI without re-encoding.
    b64: list[str] = field(default_factory=list)


class OpenAIImageClient:
    """Generate images with OpenAI's images API (gpt-image-1). Reads OPENAI_API_KEY from env."""

    def __init__(self, api_key: str | None = None) -> None:
        self._client = AsyncOpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    async def generate(
        self,
        *,
        model: str = "gpt-image-1",
        prompt: str,
        size: str = "1024x1024",
        quality: str = "auto",
        n: int = 1,
    ) -> ImageResult:
        resp = await self._client.images.generate(
            model=model, prompt=prompt, size=size, quality=quality, n=n
        )
        b64 = [d.b64_json for d in (resp.data or []) if d.b64_json]
        images = [base64.b64decode(s) for s in b64]
        u = resp.usage
        usage = Usage(
            input_tokens=getattr(u, "input_tokens", 0) or 0,
            output_tokens=getattr(u, "output_tokens", 0) or 0,
        )
        return ImageResult(images=images, usage=usage, b64=b64)


class FakeImageClient:
    """Deterministic, key-free image client for tests/CI — a 1×1 PNG, no network, $0 usage."""

    async def generate(
        self,
        *,
        model: str = "fake",
        prompt: str,
        size: str = "1024x1024",
        quality: str = "auto",
        n: int = 1,
    ) -> ImageResult:
        images = [_FAKE_PNG for _ in range(max(1, n))]
        b64 = [base64.b64encode(b).decode() for b in images]
        return ImageResult(images=images, usage=Usage(0, 0), b64=b64)
