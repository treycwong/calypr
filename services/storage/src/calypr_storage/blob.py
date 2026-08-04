"""Upload bytes to Vercel Blob and return a public URL; delete them again.

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

    POST https://blob.vercel-storage.com/delete
    authorization / x-api-version as above
    body: {"urls": ["https://…", …]}
    -> 200

Isolated in this one module so an API-version bump is a one-line fix. The `image` node is the
first caller; any future run artifact can reuse it.
"""

from __future__ import annotations

import os
from collections.abc import Iterable

import httpx

_BASE_URL = "https://blob.vercel-storage.com"
_DEFAULT_API_VERSION = "10"
_TOKEN_ENV = "BLOB_READ_WRITE_TOKEN"

#: Vercel's delete endpoint takes a batch. 100 keeps the request body small enough to be
#: retried cheaply and matches the chunk the purge job drains with.
_DELETE_CHUNK = 100


class BlobError(RuntimeError):
    """A Vercel Blob upload failed (missing token, non-200, or malformed response)."""


def _auth(token: str | None) -> str:
    """The bearer value, or raise if there isn't one.

    Strip whitespace and stray quotes — pasting the `.env`-style snippet (`"vercel_blob_rw_…"`)
    into a dashboard stores the quotes literally, which Vercel rejects with an opaque 403. Shared
    by `put_blob` and `delete_blob` rather than inlined in each, so the two cannot drift: a token
    good enough to upload with must be good enough to delete with.
    """
    auth = (token or os.environ.get(_TOKEN_ENV) or "").strip().strip("'\"")
    if not auth:
        raise BlobError(f"{_TOKEN_ENV} is not set — cannot reach Vercel Blob")
    return auth


def _headers(auth: str) -> dict[str, str]:
    """The two headers every Vercel Blob call carries."""
    return {
        "authorization": f"Bearer {auth}",
        "x-api-version": os.environ.get("VERCEL_BLOB_API_VERSION", _DEFAULT_API_VERSION),
    }


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
    headers = {
        **_headers(_auth(token)),
        "access": "public",
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


async def delete_blob(
    urls: str | Iterable[str],
    *,
    token: str | None = None,
    timeout: float = 30.0,
) -> None:
    """Delete these blob urls. Raises `BlobError` if any chunk is rejected.

    Deleting a url that is already gone is a 200 on Vercel's side, so this is idempotent and
    callers may safely retry. Empty input is a no-op rather than an error — "delete nothing" is
    a perfectly ordinary thing for the purge job to be asked to do, and making it raise would
    push a `if urls:` guard onto every call site.

    **Deliberately returns nothing rather than a partial-success report.** Which urls made it
    when a chunk fails is a policy question — retry? give up? bill for them? — and the answer
    belongs to the caller that owns the retry state (`purge.py` moves failed chunks to
    `account_purge.blob_urls_failed`), not to a transport helper that would have to guess.
    """
    # A bare string is one url, not an iterable of characters. Filter *after* wrapping so an
    # empty string is "nothing to delete" rather than a one-element batch of "".
    batch = [u for u in ([urls] if isinstance(urls, str) else urls) if u]
    if not batch:
        return
    headers = _headers(_auth(token))

    async with httpx.AsyncClient(timeout=timeout) as client:
        for start in range(0, len(batch), _DELETE_CHUNK):
            chunk = batch[start : start + _DELETE_CHUNK]
            try:
                resp = await client.post(
                    f"{_BASE_URL}/delete", json={"urls": chunk}, headers=headers
                )
            except httpx.HTTPError as exc:
                raise BlobError(f"Vercel Blob delete failed: {exc}") from exc
            if resp.status_code != 200:
                raise BlobError(
                    f"Vercel Blob delete error (status {resp.status_code}): {resp.text}"
                )
