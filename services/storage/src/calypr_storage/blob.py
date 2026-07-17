"""Upload bytes to Vercel Blob and return a public URL.

Vercel documents only the JS `@vercel/blob` SDK; the wire protocol it speaks is stable but
undocumented, so we implement it directly (as the maintained `vercel_blob` PyPI client does):

    PUT https://blob.vercel-storage.com/?pathname={path}
    authorization: Bearer $BLOB_READ_WRITE_TOKEN
    x-api-version: 10                 # override with VERCEL_BLOB_API_VERSION if Vercel bumps it
    x-content-type: <mime>
    access: public
    x-add-random-suffix: 1            # unique url per upload (no collisions)
    body: <raw bytes>
    -> 200 { "url": "https://<store>.public.blob.vercel-storage.com/<path>-<suffix>", ... }

Isolated in this one module so an API-version bump is a one-line fix. The `image` node is the
first caller; any future run artifact can reuse it.
"""

from __future__ import annotations

import os

import httpx

_BASE_URL = "https://blob.vercel-storage.com"
_DEFAULT_API_VERSION = "10"
_TOKEN_ENV = "BLOB_READ_WRITE_TOKEN"


class BlobError(RuntimeError):
    """A Vercel Blob upload failed (missing token, non-200, or malformed response)."""


async def put_blob(
    data: bytes,
    *,
    pathname: str,
    content_type: str = "application/octet-stream",
    add_random_suffix: bool = True,
    token: str | None = None,
    timeout: float = 30.0,
) -> str:
    """Upload `data` to Vercel Blob at `pathname`; return the resulting public URL.

    Raises `BlobError` if `BLOB_READ_WRITE_TOKEN` is unset or the API rejects the upload.
    """
    auth = token or os.environ.get(_TOKEN_ENV)
    if not auth:
        raise BlobError(f"{_TOKEN_ENV} is not set — cannot upload to Vercel Blob")

    headers = {
        "access": "public",
        "authorization": f"Bearer {auth}",
        "x-api-version": os.environ.get("VERCEL_BLOB_API_VERSION", _DEFAULT_API_VERSION),
        "x-content-type": content_type,
    }
    if add_random_suffix:
        headers["x-add-random-suffix"] = "1"

    # Pathname goes in the query string raw (slashes preserved) to match Vercel's blob API —
    # httpx `params=` would percent-encode `/` to `%2F`, which changes the stored key.
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.put(
                f"{_BASE_URL}/?pathname={pathname}",
                content=data,
                headers=headers,
            )
    except httpx.HTTPError as exc:
        raise BlobError(f"Vercel Blob upload failed: {exc}") from exc

    if resp.status_code != 200:
        raise BlobError(f"Vercel Blob upload error (status {resp.status_code}): {resp.text}")
    url = resp.json().get("url")
    if not url:
        raise BlobError(f"Vercel Blob response missing 'url': {resp.text}")
    return url
