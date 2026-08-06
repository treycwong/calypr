"""store_asset: the shared media-persistence helper used by the Image and Voice nodes. Uploads to
blob storage when configured, else degrades to an inline data: URI (so runs never hard-fail).

`durable` is the field that matters beyond the URL: it is what stops a multi-megabyte `data:`
URI from being recorded as an `asset` row and handed to `delete_blob` later."""

from __future__ import annotations

from calypr_nodes._assets import store_asset


async def test_store_asset_uploads_when_blob_available(monkeypatch):
    seen: dict = {}

    async def fake_put_blob(data, *, pathname, content_type):
        seen.update(data=data, pathname=pathname, content_type=content_type)
        return "https://store.public.blob.vercel-storage.com/x.mp3"

    monkeypatch.setattr("calypr_nodes._assets.put_blob", fake_put_blob)
    asset = await store_asset(b"\x00\x01", ext="mp3", content_type="audio/mpeg", b64="AAE=")
    assert asset.url == "https://store.public.blob.vercel-storage.com/x.mp3"
    assert asset.durable is True
    assert asset.bytes == 2
    assert asset.content_type == "audio/mpeg"
    # The pathname the caller records has to be the one actually uploaded to, or the ops trail
    # points at an object that doesn't exist.
    assert asset.pathname == seen["pathname"]
    assert seen["pathname"].startswith("runs/mp3/") and seen["pathname"].endswith(".mp3")
    assert seen["content_type"] == "audio/mpeg"


async def test_store_asset_falls_back_to_data_uri(monkeypatch):
    from calypr_storage import BlobError

    async def boom(*a, **k):
        raise BlobError("no token")

    monkeypatch.setattr("calypr_nodes._assets.put_blob", boom)
    asset = await store_asset(b"x", ext="png", content_type="image/png", b64="eA==")
    assert asset.url == "data:image/png;base64,eA=="
    # Not durable ⇒ the nodes emit no `asset` event ⇒ no row, no orphaned blob url.
    assert asset.durable is False
    assert asset.pathname is None
