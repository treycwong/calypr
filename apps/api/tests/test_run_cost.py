"""Pre-run media cost estimates (CAL-37). No database needed.

The estimate exists so a run can't overdraw an account by a whole video: the gate compares it to
the balance before the run starts. It must never be *below* what the run is billed.
"""

from __future__ import annotations

from calypr_api.run_cost import describe, estimate_media_credits
from calypr_compiler.templates import STARTERS
from calypr_dsl import NodeSpec


def _tpl(tid: str):
    return next(g for g in STARTERS if g.id == tid).model_copy(deep=True)


def test_a_default_video_costs_what_it_is_billed():
    """720p × 5 s of Seedance 1.0 at $0.0216/s, ×5 margin, $0.01/credit = 54 credits, the figure
    the CAL-9 audit was actually charged (54.03)."""
    cost = estimate_media_credits(_tpl("tpl-text-to-video"), set())
    assert round(cost.credits, 2) == 54.0
    assert cost.items == ("a 5-second 720p video",)


def test_image_to_video_counts_both_blocks_and_errs_high():
    cost = estimate_media_credits(_tpl("tpl-image-to-video"), set())
    assert cost.credits >= 57.09  # what the audit was actually charged
    assert describe(cost.items) == "an image and a 5-second 720p video"


def test_an_openai_key_pays_for_the_image_but_never_the_video():
    with_key = estimate_media_credits(_tpl("tpl-image-to-video"), {"openai"})
    assert round(with_key.credits, 2) == 54.0
    assert with_key.items == ("a 5-second 720p video",)


def test_a_bigger_better_image_is_estimated_higher():
    """Street film photography (1024x1536, medium) was billed 20.65; the estimate must cover it."""
    street = estimate_media_credits(_tpl("tpl-street-photography"), set()).credits
    plain = estimate_media_credits(_tpl("tpl-image-generation"), set()).credits
    assert street >= 20.65
    assert plain < street


def test_longer_and_sharper_clips_cost_more():
    g = _tpl("tpl-text-to-video")
    video = next(n for n in g.nodes if n.type == "video")
    base = estimate_media_credits(g, set()).credits
    video.config = {**video.config, "duration": "10", "resolution": "1080p"}
    assert estimate_media_credits(g, set()).credits > base * 2


def test_text_only_and_fake_media_cost_nothing():
    assert estimate_media_credits(_tpl("tpl-flashcards"), set()).credits == 0
    g = _tpl("tpl-text-to-video")
    g.nodes = [
        n if n.type != "video" else NodeSpec(id=n.id, type="video", config={"model": "fake"})
        for n in g.nodes
    ]
    assert estimate_media_credits(g, set()).credits == 0
