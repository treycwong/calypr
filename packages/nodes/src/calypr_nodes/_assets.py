"""Shared asset persistence for media nodes (Image, TTS): upload bytes to blob storage and return
a durable URL, degrading to an inline `data:` URI when blob isn't configured so the run still
succeeds. Both nodes stream the returned URL in a Markdown embed the chat renders."""

from __future__ import annotations

import logging
from uuid import uuid4

from calypr_storage import BlobError, put_blob

log = logging.getLogger("calypr_nodes")


async def store_asset(data: bytes, *, ext: str, content_type: str, b64: str) -> str:
    """Upload `data` to Vercel Blob (→ durable URL); fall back to an inline `data:` URI if blob
    isn't configured, so the run surfaces the asset instead of hard-failing. `ext` groups uploads
    by kind (e.g. `png`, `mp3`) and names the object."""
    try:
        return await put_blob(
            data,
            pathname=f"runs/{ext}/{uuid4().hex}.{ext}",
            content_type=content_type,
        )
    except BlobError as exc:
        log.warning("media node: blob upload unavailable, inlining data URI (%s)", exc)
        return f"data:{content_type};base64,{b64}"
