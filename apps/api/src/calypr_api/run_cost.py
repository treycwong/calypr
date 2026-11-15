"""Estimate, before a run starts, what its media blocks will cost in credits (CAL-37).

The run gate used to ask only "is the balance above zero?". That is right for text, where a run
costs a fraction of a credit, but a run that has started always finishes and may take the balance
negative. So a Free account with 0.9 credits left could start a 57-credit Image → Video run and
end at −56 credits, with real fal cost behind it.

Media prices are predictable from a block's settings, so the gate can ask the honest question
("does the balance cover this run?") for the blocks that cost real money:

- **Video** (credit-only): per second × resolution, exactly as billed (`priced_model`).
- **3D** (credit-only): a flat price per generation.
- **Image**: billed by output tokens, which depend on size and quality. Estimated from OpenAI's
  published output-token counts and rounded up, so the estimate errs high, not low.

Text blocks and Voice are left out: each run costs well under a credit, and the existing
"above zero" rule is the right one for them. A block running on the workspace's own key costs us
nothing and is left out too. A media block inside a loop is counted once: this is a floor, not a
quote, and it closes the gap that matters (one large overdraft) without guessing at loop counts.
"""

from __future__ import annotations

from dataclasses import dataclass

from calypr_dsl import GraphSpec
from calypr_model import priced_model
from calypr_nodes.image import ImageConfig, resolve_use_upload
from calypr_nodes.mesh import MeshConfig
from calypr_nodes.video import VideoConfig

from calypr_api import pricing
from calypr_api.model_access import runs_on_own_key

#: Output tokens per image, by (long edge, quality), from OpenAI's gpt-image token table.
#: `auto` resolves to the cheapest tier in practice (the audit's default-quality image billed
#: about 3 credits), but is counted as `low` here rather than guessed lower.
_IMAGE_TOKENS = {
    (1024, "low"): 272,
    (1024, "medium"): 1056,
    (1024, "high"): 4160,
    (1536, "low"): 408,
    (1536, "medium"): 1584,
    (1536, "high"): 6240,
}


@dataclass(frozen=True)
class MediaCost:
    credits: float
    #: What it's for, in words a person can act on: "a 5-second 720p video".
    items: tuple[str, ...]


def _image_credits(cfg: ImageConfig) -> float:
    try:
        long_edge = max(int(x) for x in str(cfg.size).lower().split("x"))
    except ValueError:
        long_edge = 1536
    edge = 1024 if long_edge <= 1024 else 1536
    quality = cfg.quality if cfg.quality in ("low", "medium", "high") else "low"
    tokens = _IMAGE_TOKENS[(edge, quality)] * max(1, int(cfg.n or 1))
    return pricing.credits_for(cfg.model, 0, tokens)


def estimate_media_credits(
    graph: GraphSpec, providers: set[str] | None, *, has_upload: bool = False
) -> MediaCost:
    """Credits this graph's media blocks will spend on the platform's keys, at least.

    `has_upload`: the run carries an attached photo. An Image block set to `use_upload` then
    generates nothing (CAL-61), so it costs nothing and must not count toward the gate."""
    graph = resolve_use_upload(graph)
    total = 0.0
    items: list[str] = []
    for node in graph.nodes:
        cfg = node.config if isinstance(node.config, dict) else {}
        if cfg.get("model") == "fake":
            continue
        if node.type == "video":
            v = VideoConfig.model_validate(cfg)
            seconds = int(v.duration)
            total += pricing.credits_for(priced_model(v.model, v.resolution), seconds, 0)
            items.append(f"a {seconds}-second {v.resolution} video")
        elif node.type == "mesh":
            m = MeshConfig.model_validate(cfg)
            total += pricing.credits_for(m.model, 1, 0)
            items.append("a 3D model")
        elif node.type == "image":
            i = ImageConfig.model_validate(cfg)
            if runs_on_own_key(i.model, providers):
                continue  # their OpenAI key pays
            if has_upload and i.use_upload:
                continue  # it uses the attached photo instead of generating one
            total += _image_credits(i)
            items.append("an image")
    return MediaCost(credits=total, items=tuple(items))


def describe(items: tuple[str, ...]) -> str:
    """"a 5-second 720p video and an image" from the items above."""
    if not items:
        return "this run"
    if len(items) == 1:
        return items[0]
    return ", ".join(items[:-1]) + " and " + items[-1]
