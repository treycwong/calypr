"""Video-generation seam — the fourth modality, after image, audio and mesh (ByteDance Seedance
on fal).

Same shape as its siblings: a provider-neutral result carrying raw bytes plus the billable unit
count, so the *same* metering path a chat node uses works unchanged (the node emits a `usage`
payload; `RunRecorder` prices it). `fal_client` is imported lazily inside `FalVideoClient.__init__`
for the reason `mesh_client` documents — the keyless `fake` path must keep working whether or not
the fal SDK is installed.

Three things differ from the mesh seam, and each one is a price or a schema fact rather than a
preference:

* **The billable unit is a second, not a generation.** fal charges per second of output and the
  rate roughly doubles between 480p and 720p, so a single per-model price cannot be honest. The
  price key is therefore `"<model>@<resolution>"` (see `priced_model`) and `VideoResult.units` is
  the clip length in seconds.
* **`duration="auto"` is deliberately not offered**, though both families accept it. Letting fal
  choose the length means not knowing the length, and the length *is* the billable unit — we would
  be recording a cost we cannot compute. Explicit durations also bound the file size.
* **The two families do not share a schema.** Seedance 1.0 takes `camera_fixed` and reaches
  1080p; Seedance 2.0 takes `generate_audio` and stops at 720p; only 2.0 accepts `"auto"` for
  duration and aspect ratio. This block sends **only the arguments all four endpoints accept** and
  lets each family's own defaults cover the rest, so one config shape drives all of them and no
  endpoint is ever sent a key it will reject. The per-family knobs are a later pass, and adding one
  means widening the config, the codegen fragment and the parser together (they round-trip as a
  set).
"""

from __future__ import annotations

import os
import struct
from collections.abc import Callable
from dataclasses import dataclass

import httpx

#: What every Seedance endpoint returns.
MP4_CONTENT_TYPE = "video/mp4"

#: Video models a Video node may name. An allowlist, exactly as `MESH_MODELS` is one: a per-second
#: model has no honest fail-closed price (`pricing._MOST_EXPENSIVE` is a *token* rate, so an
#: unknown video id would record as ~nothing rather than as expensive), so an unknown id must
#: refuse the run.
#:
#: Two families, cheapest first. Seedance **1.0 Lite is deprecated** on fal and re-routes to Pro
#: Fast — don't add it back. `calypr_nodes` can't import `calypr_api.pricing` (wrong direction), so
#: the prices live there and a test asserts every (model, resolution) pair here is priced.
SEEDANCE_1_T2V = "fal-ai/bytedance/seedance/v1/pro/fast/text-to-video"
SEEDANCE_1_I2V = "fal-ai/bytedance/seedance/v1/pro/fast/image-to-video"
SEEDANCE_2_T2V = "bytedance/seedance-2.0/fast/text-to-video"
SEEDANCE_2_I2V = "bytedance/seedance-2.0/fast/image-to-video"

VIDEO_MODELS: tuple[str, ...] = (
    SEEDANCE_1_T2V,
    SEEDANCE_1_I2V,
    SEEDANCE_2_T2V,
    SEEDANCE_2_I2V,
)

#: Resolutions each model actually accepts. Per-model rather than one global tuple because
#: Seedance 2.0 has no 1080p tier and answers a validation error for it — a lost run, after the
#: queue has already been joined.
VIDEO_RESOLUTIONS: dict[str, tuple[str, ...]] = {
    SEEDANCE_1_T2V: ("480p", "720p", "1080p"),
    SEEDANCE_1_I2V: ("480p", "720p", "1080p"),
    SEEDANCE_2_T2V: ("480p", "720p"),
    SEEDANCE_2_I2V: ("480p", "720p"),
}

#: Clip lengths offered, in seconds. The intersection of what both families accept (1.0 takes
#: 2–12, 2.0 takes 4–15) and short enough that one careless click can't generate a 40 MB file or a
#: multi-dollar charge. **Strings**, because that is what fal's schema declares — see the note on
#: `arguments_for`.
VIDEO_DURATIONS: tuple[str, ...] = ("4", "5", "8", "10")

#: Frame shapes. The intersection again: 1.0's text-to-video enum has no `"auto"`, so offering it
#: would break exactly one of the four endpoints.
VIDEO_ASPECT_RATIOS: tuple[str, ...] = ("21:9", "16:9", "4:3", "1:1", "3:4", "9:16")

DEFAULT_VIDEO_MODEL = SEEDANCE_1_T2V
DEFAULT_VIDEO_RESOLUTION = "720p"
DEFAULT_VIDEO_DURATION = "5"
DEFAULT_VIDEO_ASPECT_RATIO = "16:9"

#: How long to wait for the finished clip to download. The generation itself is bounded by the fal
#: queue; this covers only the file fetch that follows it. Larger than the mesh seam's 60s because
#: a 10-second 1080p mp4 is tens of megabytes where a GLB is a few.
_DOWNLOAD_TIMEOUT = 180.0


def is_image_to_video(model: str) -> bool:
    """Whether this endpoint animates a supplied image rather than a bare prompt.

    Derived from the endpoint id instead of being stored as a `mode` field on the node config: the
    id already carries the fact, and two copies of it are two things to keep in step."""
    return model.strip().lower().endswith("/image-to-video")


def priced_model(model: str, resolution: str) -> str:
    """The key this generation is billed under — `"<model>@<resolution>"`.

    Video is the first modality whose price depends on more than the model id, so the resolution
    rides in the string the node reports as `model`. That keeps `pricing._resolve` a single exact
    lookup and puts the resolution in front of the customer on the Usage tab, where a per-second
    charge is otherwise unexplainable."""
    return f"{model}@{resolution}"


def arguments_for(
    *,
    prompt: str,
    image_url: str = "",
    resolution: str = DEFAULT_VIDEO_RESOLUTION,
    duration: str = DEFAULT_VIDEO_DURATION,
    aspect_ratio: str = DEFAULT_VIDEO_ASPECT_RATIO,
) -> dict[str, object]:
    """The `arguments={...}` payload for one Seedance call.

    **`resolution` and `duration` are strings, and that is not incidental.** fal's schema declares
    them as string enums (`"720p"`, `"5"`), and the 3D block already lost a run to the mirror-image
    mistake — its docs rendered `texture_size` as `"1024"` while the API demanded a literal `1024`,
    and the failure landed *after* the upstream Image node had generated and billed. `str(...)`
    here rather than trusting the caller, because a saved graph or hand-edited export can carry an
    int just as easily.

    Only the four arguments every Seedance endpoint accepts are sent (plus `image_url` for the
    image-to-video pair). See the module docstring for why the per-family extras are left out
    rather than unioned into one dict.
    """
    args: dict[str, object] = {
        "prompt": prompt,
        "resolution": str(resolution),
        "duration": str(duration),
        "aspect_ratio": aspect_ratio,
    }
    if image_url:
        args["image_url"] = image_url
    return args


def _minimal_mp4() -> bytes:
    """The smallest structurally valid ISO base-media file: an `ftyp` box plus an empty `moov`.

    Built rather than pasted as a base64 blob, for the same reason `mesh_client._minimal_glb` is —
    a reader can see that it really is a well-formed container, which matters because the Fake
    client's output is what every test asserts against. It contains no frames, so nothing plays;
    that is correct for a keyless placeholder and is what the `fake` model promises.
    """

    def box(kind: bytes, payload: bytes) -> bytes:
        return struct.pack(">I", 8 + len(payload)) + kind + payload

    # major brand `isom`, minor version 512, compatible brands — the conventional mp4 preamble.
    ftyp = box(b"ftyp", b"isom" + struct.pack(">I", 512) + b"isomiso2mp41")
    return ftyp + box(b"moov", b"")


_FAKE_MP4 = _minimal_mp4()


@dataclass
class VideoResult:
    """One video-generation turn: the raw mp4 bytes plus what it is billed on."""

    data: bytes
    content_type: str = MP4_CONTENT_TYPE
    #: Billable **seconds** — the clip length. The node reports it as `input_tokens` (as TTS does
    #: with characters and 3D with generations) and `pricing.MEDIA_PRICES` turns it into USD.
    units: int = 0
    #: The resolution actually generated. Half of the price key; see `priced_model`.
    resolution: str = DEFAULT_VIDEO_RESOLUTION
    #: Deliberately empty, unlike `ImageResult.b64` / `MeshResult.b64`. There is no `data:`
    #: fallback for a video — megabytes of base64 in a persisted `message` row is a worse bug than
    #: a missing link, and the chat renderer refuses `data:` hrefs anyway — so base64-encoding an
    #: 8 MB clip on every run would buy nothing. Kept as a field for signature parity with
    #: `store_asset`.
    b64: str = ""


class FalVideoClient:
    """Generate a video with fal (Seedance, default `fal-ai/bytedance/seedance/v1/pro/fast`).

    Uses fal's **queue** (`subscribe`) rather than a direct call. Generation runs one to three
    minutes — several times longer than image→3D — so `on_progress` reporting queue position is
    what lets the caller keep an SSE stream warm instead of going silent for the duration.
    """

    def __init__(self, api_key: str | None = None) -> None:
        # Lazy on purpose — see the module docstring.
        try:
            import fal_client
        except ImportError as exc:  # pragma: no cover - depends on the install, not the logic
            raise RuntimeError(
                "Video generation needs the `fal-client` package. Install it, or use model='fake'."
            ) from exc
        self._client = fal_client.AsyncClient(key=api_key or os.environ.get("FAL_KEY"))

    async def generate(
        self,
        *,
        model: str = DEFAULT_VIDEO_MODEL,
        prompt: str,
        image_url: str = "",
        resolution: str = DEFAULT_VIDEO_RESOLUTION,
        duration: str = DEFAULT_VIDEO_DURATION,
        aspect_ratio: str = DEFAULT_VIDEO_ASPECT_RATIO,
        on_progress: Callable[[str], None] | None = None,
    ) -> VideoResult:
        def _update(status: object) -> None:
            if on_progress is None:
                return
            position = getattr(status, "position", None)
            on_progress(f"queued (position {position})" if position is not None else "generating")

        payload = await self._client.subscribe(
            model,
            arguments=arguments_for(
                prompt=prompt,
                image_url=image_url,
                resolution=resolution,
                duration=duration,
                aspect_ratio=aspect_ratio,
            ),
            on_queue_update=_update if on_progress else None,
        )
        video = (payload or {}).get("video") or {}
        url = video.get("url")
        if not url:
            keys = sorted((payload or {}).keys())
            raise RuntimeError(f"{model} returned no video (keys: {keys})")
        async with httpx.AsyncClient(timeout=_DOWNLOAD_TIMEOUT) as http:
            resp = await http.get(url)
            resp.raise_for_status()
        return VideoResult(
            data=resp.content,
            content_type=video.get("content_type") or MP4_CONTENT_TYPE,
            # The configured duration, not one read back from the response: fal returns no length,
            # and this is exactly why `"auto"` is not on the menu.
            units=int(duration),
            resolution=resolution,
        )


class FakeVideoClient:
    """Deterministic, key-free video client for tests/CI — a minimal valid mp4, no network.

    Still reports the real `units` (the requested seconds): the fake path must exercise the same
    metering arithmetic the real one does, or a pricing regression would only ever show up in
    production."""

    async def generate(
        self,
        *,
        model: str = "fake",
        prompt: str,
        image_url: str = "",
        resolution: str = DEFAULT_VIDEO_RESOLUTION,
        duration: str = DEFAULT_VIDEO_DURATION,
        aspect_ratio: str = DEFAULT_VIDEO_ASPECT_RATIO,
        on_progress: Callable[[str], None] | None = None,
    ) -> VideoResult:
        return VideoResult(
            data=_FAKE_MP4,
            content_type=MP4_CONTENT_TYPE,
            units=int(duration),
            resolution=resolution,
        )
