"""Shared asset persistence for media nodes (Image, TTS): upload bytes to blob storage and return
a durable URL, degrading to an inline `data:` URI when blob isn't configured so the run still
succeeds. Both nodes stream the returned URL in a Markdown embed the chat renders.

`store_asset` returns a `StoredAsset` rather than a bare string because the caller needs to know
whether the bytes actually *landed* somewhere. Only a durable upload gets recorded in the
`asset` table — a `data:` URI is the whole file inlined, and writing megabytes of base64 into
Postgres to populate a Media tab would be a worse bug than the missing row. Nothing tenant-aware
appears here: no workspace, no run, no session. That is deliberate, and it is what keeps these
nodes safe to code-generate into a user's exported script."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from uuid import uuid4

from calypr_storage import BlobError, put_blob

log = logging.getLogger("calypr_nodes")


@dataclass(frozen=True)
class StoredAsset:
    """Where a generated file ended up, and whether that place outlives the response."""

    #: A blob URL when `durable`, otherwise an inline `data:<mime>;base64,…` URI.
    url: str
    #: False ⇒ blob storage isn't configured and `url` is the file itself. Callers must not
    #: record a non-durable asset: there is nothing to list later and nothing to delete.
    durable: bool
    pathname: str | None
    bytes: int
    content_type: str


async def store_asset(data: bytes, *, ext: str, content_type: str, b64: str) -> StoredAsset:
    """Upload `data` to Vercel Blob (→ durable URL); fall back to an inline `data:` URI if blob
    isn't configured, so the run surfaces the asset instead of hard-failing. `ext` groups uploads
    by kind (e.g. `png`, `mp3`) and names the object."""
    pathname = f"runs/{ext}/{uuid4().hex}.{ext}"
    try:
        url = await put_blob(data, pathname=pathname, content_type=content_type)
        return StoredAsset(
            url=url,
            durable=True,
            pathname=pathname,
            bytes=len(data),
            content_type=content_type,
        )
    except BlobError as exc:
        log.warning("media node: blob upload unavailable, inlining data URI (%s)", exc)
        return StoredAsset(
            url=f"data:{content_type};base64,{b64}",
            durable=False,
            pathname=None,
            bytes=len(data),
            content_type=content_type,
        )
