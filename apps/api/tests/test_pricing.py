"""Unit tests for pricing.py (WEEK2 Phase A gate): arithmetic, prefix resolution,
fail-closed on unknown models, and fake=0."""

import pytest
from calypr_api import pricing


def test_cost_arithmetic():
    # gpt-4.1-mini = $0.40 / $1.60 per 1M. 1M in + 1M out = 0.40 + 1.60.
    assert pricing.cost_usd("gpt-4.1-mini", 1_000_000, 1_000_000) == pytest.approx(2.00)
    # Half a million output only.
    assert pricing.cost_usd("gpt-4.1-mini", 0, 500_000) == pytest.approx(0.80)


def test_zero_tokens_is_zero():
    assert pricing.cost_usd("claude-opus-4-8", 0, 0) == 0.0


def test_prefix_resolution_longest_wins():
    # "gpt-4.1-mini" must resolve to the mini entry, not the broader "gpt-4.1".
    assert pricing.price_for("gpt-4.1-mini") is pricing.MODEL_PRICES["gpt-4.1-mini"]
    assert pricing.price_for("gpt-4.1-nano") is pricing.MODEL_PRICES["gpt-4.1-nano"]
    assert pricing.price_for("gpt-4.1-2025-04-14") is pricing.MODEL_PRICES["gpt-4.1"]
    # Anthropic opus variants share one prefix entry.
    assert pricing.price_for("claude-opus-4-8") is pricing.MODEL_PRICES["claude-opus-4"]
    assert pricing.price_for("claude-opus-4-6") is pricing.MODEL_PRICES["claude-opus-4"]


def test_case_insensitive():
    assert pricing.price_for("GPT-4o") is pricing.MODEL_PRICES["gpt-4o"]


def test_unknown_model_fails_closed_to_most_expensive():
    price = pricing.price_for("some-brand-new-frontier-model")
    assert price.input_per_1m == max(p.input_per_1m for p in pricing.MODEL_PRICES.values())
    assert price.output_per_1m == max(p.output_per_1m for p in pricing.MODEL_PRICES.values())
    # An unknown model must never record cheaper than any known model.
    unknown = pricing.cost_usd("some-brand-new-frontier-model", 1_000, 1_000)
    for model_id in pricing.MODEL_PRICES:
        assert unknown >= pricing.cost_usd(model_id, 1_000, 1_000)


def test_fake_model_is_free():
    assert pricing.cost_usd("fake", 1_000_000, 1_000_000) == 0.0
    assert pricing.price_for("fake").input_per_1m == 0.0


def test_image_models_priced_not_fail_closed():
    # gpt-image-1 must resolve to its own entry (image-output tier), not the fail-closed default.
    assert pricing.price_for("gpt-image-1") is pricing.MODEL_PRICES["gpt-image-1"]
    # 1M image-output tokens on gpt-image-1 = its output rate.
    assert pricing.cost_usd("gpt-image-1", 0, 1_000_000) == pytest.approx(
        pricing.MODEL_PRICES["gpt-image-1"].output_per_1m
    )
    # Longest-prefix: the mini id must not collapse onto the base gpt-image-1 entry.
    assert pricing.price_for("gpt-image-1-mini") is pricing.MODEL_PRICES["gpt-image-1-mini"]
    assert pricing.price_for("gpt-image-1.5") is pricing.MODEL_PRICES["gpt-image-1.5"]


def test_tts_models_priced_per_character():
    # TTS records the input character count in `input_tokens`; priced per 1M characters, output 0.
    assert pricing.cost_usd("tts-1", 1_000_000, 0) == pytest.approx(15.0)
    assert pricing.cost_usd("tts-1-hd", 1_000_000, 0) == pytest.approx(30.0)
    assert pricing.price_for("gpt-4o-mini-tts") is pricing.MODEL_PRICES["gpt-4o-mini-tts"]
    # tts-1-hd must win over tts-1 by longest-prefix.
    assert pricing.price_for("tts-1-hd") is pricing.MODEL_PRICES["tts-1-hd"]


# --- credits (PRICING-SPEC §2) -------------------------------------------------------------------


def test_the_margin_holds_on_every_priced_model():
    """The point of deriving credits from USD instead of a second table: a constant 5× on every
    model and every direction, so no usage mix can erode the margin. A hand-maintained credit
    table is exactly where that guarantee would rot."""
    for model_id in pricing.MODEL_PRICES:
        for tokens_in, tokens_out in ((1_000_000, 0), (0, 1_000_000), (500_000, 500_000)):
            usd = pricing.cost_usd(model_id, tokens_in, tokens_out)
            credits = pricing.credits_for(model_id, tokens_in, tokens_out)
            assert credits * pricing.CREDIT_RETAIL_USD == pytest.approx(
                usd * pricing.CREDIT_MARGIN
            ), model_id


def test_image_generation_has_a_credit_rate():
    """The gap PRICING-SPEC left open. Image is token-billed (image-output tokens), so it
    converts like any other model call — a ~1024x1024 generation lands around 16 credits."""
    credits = pricing.credits_for("gpt-image-2", 20, 1056)
    assert 10 < credits < 25


def test_speech_has_a_credit_rate():
    """TTS is billed per character, and the node records characters in `input_tokens`, so the
    same arithmetic prices it — 7.5 credits per 1,000 characters."""
    assert pricing.credits_for("gpt-4o-mini-tts", 1000, 0) == pytest.approx(7.5)


def test_the_plus_grant_buys_a_sane_amount_of_media():
    """A sanity floor on the plan: 2,000 credits should be a month of real use, not a demo.
    If a repricing makes an image cost 200 credits, that is a product decision — this fails so
    it gets made deliberately."""
    per_image = pricing.credits_for("gpt-image-2", 20, 1056)
    assert 2000 / per_image > 50, "Plus should buy well over 50 images a month"


def test_credits_are_not_rounded_per_call():
    """Rounding here would let a graph of many cheap nodes round to zero on every node. Round
    once when a ledger row is written, not per call."""
    assert pricing.credits_for("gpt-4o-mini", 10, 0) > 0


def test_the_fake_model_is_free_in_credits_too():
    assert pricing.credits_for("fake", 1_000_000, 1_000_000) == 0.0
