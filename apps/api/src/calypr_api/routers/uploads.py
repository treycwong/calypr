"""Image uploads for vision runs (the Upload node's input).

The browser POSTs the raw file body (`content-type: image/…`) — no multipart, so no extra
dependency and the 5MB cap is enforced *while streaming* the body, not after buffering it.
Server-side gate: content-type allowlist + magic-byte sniff + size cap, then the bytes land in
the existing Vercel Blob store under `uploads/` and the client gets back the public URL to pass
in `RunRequest.images`.

Two variants: `/uploads` (playground; workspace-resolved like `/runs`) and
`/share/{token}/uploads` (public share page; gated on a valid unrevoked token so it is not an
open anonymous upload endpoint — per-token rate limiting is a logged follow-up).
"""

from __future__ import annotations

import asyncio
import logging
import uuid as uuid_mod
from uuid import uuid4

from calypr_storage import BlobError, put_blob
from fastapi import APIRouter, Depends, HTTPException, Request

from calypr_api.db.models import Upload
from calypr_api.db.session import SessionLocal, set_tenant
from calypr_api.deps import run_workspace
from calypr_api.routers.share import _agent_name

log = logging.getLogger(__name__)

router = APIRouter()

MAX_UPLOAD_BYTES = 5 * 1024 * 1024  # 5MB

# content-type → (file extension, magic-byte prefixes that must match the body)
_ALLOWED: dict[str, tuple[str, tuple[bytes, ...]]] = {
    "image/png": ("png", (b"\x89PNG\r\n\x1a\n",)),
    "image/jpeg": ("jpg", (b"\xff\xd8\xff",)),
    "image/gif": ("gif", (b"GIF87a", b"GIF89a")),
    "image/webp": ("webp", (b"RIFF",)),  # + "WEBP" at offset 8, checked below
}


async def _read_capped(request: Request) -> bytes:
    """Read the request body, aborting with 413 as soon as it exceeds the cap."""
    chunks: list[bytes] = []
    size = 0
    async for chunk in request.stream():
        size += len(chunk)
        if size > MAX_UPLOAD_BYTES:
            raise HTTPException(status_code=413, detail="image exceeds the 5MB limit")
        chunks.append(chunk)
    return b"".join(chunks)


def _record(workspace_id: uuid_mod.UUID | None, url: str, pathname: str, size: int, ct: str):
    """Note the blob against its workspace, so its bytes are attributable.

    Best-effort, exactly like run metering: the file is already stored and handed to the user, so
    failing here must not turn a successful upload into an error. The cost of a missed row is one
    unaccounted file in the storage figure — the cost of raising would be a broken upload."""
    if workspace_id is None:
        return
    try:
        with SessionLocal() as session:
            set_tenant(session, str(workspace_id))
            session.add(
                Upload(
                    workspace_id=workspace_id,
                    blob_url=url,
                    pathname=pathname,
                    bytes=size,
                    content_type=ct,
                )
            )
            session.commit()
    except Exception:
        log.warning("upload accounting failed for %s", pathname, exc_info=True)


async def _handle_upload(request: Request, workspace_id: uuid_mod.UUID | None = None) -> dict:
    content_type = (request.headers.get("content-type") or "").split(";")[0].strip().lower()
    allowed = _ALLOWED.get(content_type)
    if allowed is None:
        raise HTTPException(
            status_code=415, detail="only PNG, JPEG, WebP, or GIF images are accepted"
        )
    ext, magics = allowed

    data = await _read_capped(request)
    if not data:
        raise HTTPException(status_code=400, detail="empty upload")
    # Magic-byte sniff: the body must actually be the claimed image type.
    if not any(data.startswith(m) for m in magics) or (
        content_type == "image/webp" and data[8:12] != b"WEBP"
    ):
        raise HTTPException(status_code=400, detail="file content does not match its image type")

    pathname = f"uploads/{uuid4().hex}.{ext}"
    try:
        url = await put_blob(data, pathname=pathname, content_type=content_type)
    except BlobError as exc:
        raise HTTPException(status_code=503, detail="upload storage unavailable") from exc
    await asyncio.to_thread(_record, workspace_id, url, pathname, len(data), content_type)
    return {"url": url}


@router.post("/uploads", tags=["engine"])
async def create_upload(
    request: Request, workspace_id: uuid_mod.UUID = Depends(run_workspace)
) -> dict:
    """Playground upload — same workspace resolution as `/runs`."""
    return await _handle_upload(request, workspace_id)


@router.post("/share/{token}/uploads", tags=["share"])
async def create_share_upload(token: str, request: Request) -> dict:
    """Share-page upload — requires a valid, unrevoked share token (404 otherwise)."""
    if await asyncio.to_thread(_agent_name, token) is None:
        raise HTTPException(status_code=404, detail="share link not found")
    return await _handle_upload(request)
