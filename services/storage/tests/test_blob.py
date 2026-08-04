"""put_blob / delete_blob: the Vercel Blob wire contract. We stub the httpx transport so the
tests are offline — asserting the endpoint, auth header, x-content-type, pathname and the URL
parse, plus the fail-closed behaviour with no token.

`delete_blob` is the destructive half, so its tests lean on the things that would be expensive
to get wrong: that an empty list issues **no** request at all, and that a large batch is chunked
rather than sent as one enormous body."""

from __future__ import annotations

import json

import httpx
import pytest
from calypr_storage import BlobError, delete_blob, put_blob


def _stub_transport(captured: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = request.content
        return httpx.Response(200, json={"url": "https://store.public.blob.vercel-storage.com/x.png"})

    return httpx.MockTransport(handler)


def _use(transport: httpx.MockTransport, monkeypatch) -> None:
    """Route every AsyncClient this module opens through `transport`."""
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)


async def test_put_blob_uploads_and_returns_url(monkeypatch):
    captured: dict = {}
    _use(_stub_transport(captured), monkeypatch)

    url = await put_blob(
        b"\x89PNG...", pathname="runs/images/abc.png", content_type="image/png", token="tok_123"
    )
    assert url == "https://store.public.blob.vercel-storage.com/x.png"
    assert captured["url"].startswith("https://blob.vercel-storage.com/")
    assert "pathname=runs/images/abc.png" in captured["url"]
    assert captured["headers"]["authorization"] == "Bearer tok_123"
    assert captured["headers"]["x-content-type"] == "image/png"
    assert captured["body"] == b"\x89PNG..."


async def test_put_blob_without_token_raises(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    with pytest.raises(BlobError):
        await put_blob(b"data", pathname="x.png")


async def test_put_blob_strips_pasted_quotes(monkeypatch):
    """A token pasted with its `.env`-style quotes must still authenticate — the quotes are
    stripped before building the Bearer header (a real prod incident: Vercel 403s otherwise)."""
    captured: dict = {}
    _use(_stub_transport(captured), monkeypatch)
    await put_blob(b"x", pathname="a.png", content_type="image/png", token='"tok_123"\n')
    assert captured["headers"]["authorization"] == "Bearer tok_123"


# --- delete_blob -------------------------------------------------------------------------------


def _delete_transport(requests: list[httpx.Request], status: int = 200) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(status, json={})

    return httpx.MockTransport(handler)


async def test_delete_blob_posts_urls(monkeypatch):
    """The wire contract: POST /delete, `{"urls": [...]}`, same bearer + api version as put."""
    requests: list[httpx.Request] = []
    _use(_delete_transport(requests), monkeypatch)

    await delete_blob(
        ["https://store.public.blob.vercel-storage.com/a.png", "https://…/b.png"],
        token="tok_123",
    )

    assert len(requests) == 1
    req = requests[0]
    assert req.method == "POST"
    assert str(req.url) == "https://blob.vercel-storage.com/delete"
    assert req.headers["authorization"] == "Bearer tok_123"
    assert req.headers["x-api-version"] == "10"
    assert json.loads(req.content) == {
        "urls": ["https://store.public.blob.vercel-storage.com/a.png", "https://…/b.png"]
    }


async def test_delete_blob_accepts_a_single_url(monkeypatch):
    """A bare string is one url, not an iterable of characters."""
    requests: list[httpx.Request] = []
    _use(_delete_transport(requests), monkeypatch)

    await delete_blob("https://store.public.blob.vercel-storage.com/a.png", token="tok_123")

    assert json.loads(requests[0].content) == {
        "urls": ["https://store.public.blob.vercel-storage.com/a.png"]
    }


async def test_delete_blob_empty_makes_no_request(monkeypatch):
    """Nothing to delete must cost nothing — no HTTP call, and no token required to discover
    that. The purge job calls this with whatever is left in `blob_urls`, which is routinely
    empty, and an account with no uploads must not fail its purge on a missing token."""
    requests: list[httpx.Request] = []
    _use(_delete_transport(requests), monkeypatch)
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)

    await delete_blob([])
    await delete_blob("")

    assert requests == []


async def test_delete_blob_without_token_raises(monkeypatch):
    monkeypatch.delenv("BLOB_READ_WRITE_TOKEN", raising=False)
    with pytest.raises(BlobError):
        await delete_blob(["https://store.public.blob.vercel-storage.com/a.png"])


async def test_delete_blob_chunks_at_100(monkeypatch):
    """250 urls go out as 100 / 100 / 50, not one body Vercel would reject."""
    requests: list[httpx.Request] = []
    _use(_delete_transport(requests), monkeypatch)
    urls = [f"https://store.public.blob.vercel-storage.com/{i}.png" for i in range(250)]

    await delete_blob(urls, token="tok_123")

    sizes = [len(json.loads(r.content)["urls"]) for r in requests]
    assert sizes == [100, 100, 50]
    # Every url is sent exactly once, in order — a chunker that drops or repeats one would
    # silently leak or double-delete.
    sent = [u for r in requests for u in json.loads(r.content)["urls"]]
    assert sent == urls


async def test_delete_blob_non_200_raises(monkeypatch):
    requests: list[httpx.Request] = []
    _use(_delete_transport(requests, status=403), monkeypatch)
    with pytest.raises(BlobError):
        await delete_blob(["https://store.public.blob.vercel-storage.com/a.png"], token="t")
