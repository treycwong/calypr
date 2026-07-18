"""Upload endpoints: the server-side gate for vision attachments — 5MB cap, image-type
allowlist, magic-byte sniff — plus the share variant's token check and the RunRequest image-URL
validator. Blob storage is mocked; no network."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from calypr_api.main import app
from calypr_api.schemas import RunRequest
from calypr_compiler.golden import input_agent_output
from fastapi.testclient import TestClient

client = TestClient(app)

_PNG = b"\x89PNG\r\n\x1a\n" + b"0" * 64
_BLOB_URL = "https://s.public.blob.vercel-storage.com/uploads/x.png"


def _mock_blob():
    return patch("calypr_api.routers.uploads.put_blob", new=AsyncMock(return_value=_BLOB_URL))


def test_upload_accepts_valid_png():
    with _mock_blob():
        r = client.post("/uploads", content=_PNG, headers={"content-type": "image/png"})
    assert r.status_code == 200
    assert r.json() == {"url": _BLOB_URL}


def test_upload_rejects_wrong_content_type():
    r = client.post("/uploads", content=_PNG, headers={"content-type": "application/pdf"})
    assert r.status_code == 415


def test_upload_rejects_mismatched_magic_bytes():
    r = client.post("/uploads", content=b"not-an-image", headers={"content-type": "image/png"})
    assert r.status_code == 400


def test_upload_rejects_over_5mb():
    big = b"\x89PNG\r\n\x1a\n" + b"0" * (5 * 1024 * 1024)
    r = client.post("/uploads", content=big, headers={"content-type": "image/png"})
    assert r.status_code == 413


def test_share_upload_unknown_token_404s():
    # No DB in unit tests → the resolver returns None → 404 (fail closed, never uploads).
    r = client.post(
        "/share/no-such-token/uploads", content=_PNG, headers={"content-type": "image/png"}
    )
    assert r.status_code == 404


def test_run_request_rejects_arbitrary_image_urls():
    graph = input_agent_output(model="fake")
    with pytest.raises(ValueError):
        RunRequest(graph=graph, message="hi", images=["https://evil.example.com/x.png"])
    # blob-store URLs and data URIs pass
    ok = RunRequest(graph=graph, message="hi", images=[_BLOB_URL, "data:image/png;base64,AA"])
    assert len(ok.images) == 2
    with pytest.raises(ValueError):  # cap at 4
        RunRequest(graph=graph, message="hi", images=[_BLOB_URL] * 5)
