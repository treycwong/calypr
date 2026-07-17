"""put_blob: uploads bytes to Vercel Blob and returns the public URL. We stub the httpx
transport so the test is offline — asserting the wire contract (endpoint, auth header,
x-content-type, pathname) and the URL parse, plus the fail-closed behaviour with no token."""

from __future__ import annotations

import httpx
import pytest
from calypr_storage import BlobError, put_blob


def _stub_transport(captured: dict) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = request.headers
        captured["body"] = request.content
        return httpx.Response(200, json={"url": "https://store.public.blob.vercel-storage.com/x.png"})

    return httpx.MockTransport(handler)


async def test_put_blob_uploads_and_returns_url(monkeypatch):
    captured: dict = {}
    transport = _stub_transport(captured)

    # Patch AsyncClient so put_blob uses our in-memory transport.
    real_init = httpx.AsyncClient.__init__

    def patched_init(self, *args, **kwargs):
        kwargs["transport"] = transport
        real_init(self, *args, **kwargs)

    monkeypatch.setattr(httpx.AsyncClient, "__init__", patched_init)

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
