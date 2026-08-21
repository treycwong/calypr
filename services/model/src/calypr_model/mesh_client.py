"""3D-mesh generation seam — the modality sibling of `image_client` (image → GLB).

Same shape as the image and TTS seams: a provider-neutral result carrying raw bytes plus the
billable unit count, so the *same* metering path a chat node uses works unchanged (the node emits
a `usage` payload; `RunRecorder` prices it).

Two things differ from the image seam and both are deliberate:

* **Billing is per generation, not per token.** fal charges a flat price per output, so
  `MeshResult.units` counts generations and `pricing.MEDIA_PRICES` prices them. See the note there
  on why a flat rate must not live in the token table.
* **`fal_client` is imported lazily**, inside `FalMeshClient.__init__` rather than at module
  scope. `calypr_model.factory` imports this module eagerly, and the keyless `fake` path — CI,
  local dev, every node test — must keep working whether or not the fal SDK is installed. A hard
  top-level import would make one optional provider a prerequisite for importing the model layer.
"""

from __future__ import annotations

import base64
import json
import os
import struct
from collections.abc import Callable
from dataclasses import dataclass

import httpx

#: What fal returns for a Trellis-style image→3D model. GLB is the binary glTF container.
GLB_CONTENT_TYPE = "model/gltf-binary"

#: Mesh models a 3D node may name. An allowlist rather than a free-text field because a flat-rate
#: model has no honest fail-closed price: `pricing._MOST_EXPENSIVE` is a *token* rate, so an
#: unknown mesh id would record as ~nothing rather than as expensive. Better to refuse the run.
#:
#: `calypr_nodes` can't import `calypr_api.pricing` (wrong direction), so the prices live there and
#: a test asserts every entry here is priced. Adding a model means editing both.
MESH_MODELS: tuple[str, ...] = ("fal-ai/trellis",)

#: How long to wait for the generated mesh to download. The generation itself is bounded by
#: `AsyncClient(default_timeout=...)`; this covers only the file fetch that follows it.
_DOWNLOAD_TIMEOUT = 60.0


def _minimal_glb() -> bytes:
    """The smallest structurally valid GLB: a 12-byte header plus one JSON chunk.

    Built rather than pasted as a base64 blob so it is auditable — a reader can see that it really
    is a well-formed glTF 2.0 container, which matters because the Fake client's output is what
    every test asserts against.
    """
    body = json.dumps({"asset": {"version": "2.0"}, "scenes": [], "nodes": []}).encode()
    body += b" " * (-len(body) % 4)  # glTF chunks are 4-byte aligned; JSON pads with spaces
    chunk = struct.pack("<II", len(body), 0x4E4F534A) + body  # 0x4E4F534A == b"JSON"
    return struct.pack("<4sII", b"glTF", 2, 12 + len(chunk)) + chunk


_FAKE_GLB = _minimal_glb()


@dataclass
class MeshResult:
    """One mesh-generation turn: the raw GLB bytes plus the billable unit count for metering."""

    data: bytes
    content_type: str = GLB_CONTENT_TYPE
    #: Billable generations. Flat-rate per output, so this is 1 for a single call — the node
    #: reports it as `input_tokens` and `pricing.MEDIA_PRICES` turns it into USD.
    units: int = 1
    #: base64 of `data`, so a caller can build a `data:` URI without re-encoding (mirrors
    #: `ImageResult.b64`). Populated lazily by `_result_from`.
    b64: str = ""


def _result_from(data: bytes, content_type: str) -> MeshResult:
    return MeshResult(
        data=data,
        content_type=content_type or GLB_CONTENT_TYPE,
        units=1,
        b64=base64.b64encode(data).decode(),
    )


class FalMeshClient:
    """Generate a 3D mesh from an image with fal (default `fal-ai/trellis`).

    Uses fal's **queue** (`subscribe`) rather than a direct call: image→3D runs tens of seconds,
    and the queue is what lets `on_progress` report position/logs while it waits, so the caller can
    keep an SSE stream warm instead of going silent until the mesh lands.
    """

    def __init__(self, api_key: str | None = None) -> None:
        # Lazy on purpose — see the module docstring.
        try:
            import fal_client
        except ImportError as exc:  # pragma: no cover - depends on the install, not the logic
            raise RuntimeError(
                "3D generation needs the `fal-client` package. Install it, or use model='fake'."
            ) from exc
        self._client = fal_client.AsyncClient(key=api_key or os.environ.get("FAL_KEY"))

    async def generate(
        self,
        *,
        model: str = "fal-ai/trellis",
        image_url: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> MeshResult:
        def _update(status: object) -> None:
            if on_progress is None:
                return
            position = getattr(status, "position", None)
            on_progress(f"queued (position {position})" if position is not None else "generating")

        payload = await self._client.subscribe(
            model,
            arguments={"image_url": image_url},
            on_queue_update=_update if on_progress else None,
        )
        mesh = (payload or {}).get("model_mesh") or {}
        url = mesh.get("url")
        if not url:
            raise RuntimeError(f"{model} returned no mesh (keys: {sorted((payload or {}).keys())})")
        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as http:
            resp = await http.get(url)
            resp.raise_for_status()
            return _result_from(resp.content, mesh.get("content_type") or GLB_CONTENT_TYPE)


class FakeMeshClient:
    """Deterministic, key-free mesh client for tests/CI — a minimal valid GLB, no network.

    Still reports `units=1`: the fake path must exercise the same metering arithmetic the real one
    does, or a pricing regression would only ever show up in production.
    """

    async def generate(
        self,
        *,
        model: str = "fake",
        image_url: str,
        on_progress: Callable[[str], None] | None = None,
    ) -> MeshResult:
        return _result_from(_FAKE_GLB, GLB_CONTENT_TYPE)
