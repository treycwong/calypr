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
