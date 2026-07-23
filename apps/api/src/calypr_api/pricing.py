"""Per-model token pricing → USD cost (METERING-ANALYTICS-PLAN §5, WEEK2 plan Phase A).

Pure module: no DB, no I/O, integrated with nothing yet. `RunRecorder` (Phase B) will call
`cost_usd()` to turn buffered usage events into a `run.cost_usd` total.

Prices are per **1M tokens**, per direction (input / output), in USD. They are a *recording*
input, not a billing source of truth — Month-3 credits (PRICING-SPEC) re-verify margins. Still:

    ⚠️  Verify against provider price pages before each release — do NOT trust these blindly.
        Verified 2026-07-07 (Anthropic via the claude-api skill catalog; others from provider
        pricing pages). Non-Anthropic rates below carry more staleness risk — re-check them.

Resolution is **longest-prefix**: `gpt-4.1-mini` resolves to the `gpt-4.1-mini` entry, not the
shorter `gpt-4.1`. Unknown models **fail closed** to the most expensive known rate, so an
un-priced model can never silently record as cheap. The `fake` model (keyless dev/CI) is $0.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class ModelPrice:
    """USD per 1M tokens, per direction."""

    input_per_1m: float
    output_per_1m: float


# Keys are model-id **prefixes** (see `_resolve`). Order doesn't matter — longest match wins.
MODEL_PRICES: dict[str, ModelPrice] = {
    # --- Anthropic (verified 2026-07-07, claude-api skill catalog) ---
    "claude-fable-5": ModelPrice(10.00, 50.00),
    "claude-opus-4": ModelPrice(5.00, 25.00),  # 4.6 / 4.7 / 4.8 all $5 / $25
    "claude-sonnet-5": ModelPrice(3.00, 15.00),
    "claude-sonnet-4": ModelPrice(3.00, 15.00),
    "claude-haiku-4": ModelPrice(1.00, 5.00),
    "claude-3-opus": ModelPrice(15.00, 75.00),
    "claude-3-5-sonnet": ModelPrice(3.00, 15.00),
    "claude-3-5-haiku": ModelPrice(0.80, 4.00),
    "claude-3-haiku": ModelPrice(0.25, 1.25),
    # --- OpenAI (verify against https://openai.com/api/pricing) ---
    # GPT-5.6 is not offered in the pickers (Terra was pulled), but all three tiers stay priced
    # so an id arriving another way isn't recorded at the fail-closed rate. Sol is the flagship,
    # Luna the cheap tier. Sourced 2026-07-21 from pricing aggregators, NOT OpenAI's own page —
    # re-verify before these rates inform a margin decision.
    "gpt-5.6-sol": ModelPrice(5.00, 30.00),
    "gpt-5.6-terra": ModelPrice(2.50, 15.00),
    "gpt-5.6-luna": ModelPrice(1.00, 6.00),
    "gpt-4.1-nano": ModelPrice(0.10, 0.40),
    "gpt-4.1-mini": ModelPrice(0.40, 1.60),
    "gpt-4.1": ModelPrice(2.00, 8.00),
    "gpt-4o-mini": ModelPrice(0.15, 0.60),
    "gpt-4o": ModelPrice(2.50, 10.00),
    "o4-mini": ModelPrice(1.10, 4.40),
    "o3-mini": ModelPrice(1.10, 4.40),
    "o3": ModelPrice(2.00, 8.00),
    "o1-mini": ModelPrice(1.10, 4.40),
    "o1": ModelPrice(15.00, 60.00),
    # --- OpenAI image models (verify against https://developers.openai.com/api/docs/pricing) ---
    # Image generation is token-billed: input_per_1m = text-input tokens, output_per_1m = image
    # OUTPUT tokens (image-INPUT tokens, used only for edits, aren't modelled here — v1 is
    # generation-only). gpt-image-1 is legacy (dropped from the current price page); rate below is
    # its historical image-output tier, kept fail-safe-high. Prefer gpt-image-1.5 / gpt-image-2.
    "gpt-image-1-mini": ModelPrice(2.00, 8.00),
    "gpt-image-1.5": ModelPrice(5.00, 32.00),
    "gpt-image-2": ModelPrice(5.00, 30.00),
    "gpt-image-1": ModelPrice(5.00, 40.00),
    # --- OpenAI text-to-speech (verify against https://developers.openai.com/api/docs/pricing) ---
    # TTS is billed per CHARACTER; the speech API returns no token usage, so the TTS node records
    # the input character count in the `input_tokens` field and we price per 1M characters here
    # (output rate 0). gpt-4o-mini-tts is token-billed upstream — the rate below is an approximate
    # per-character proxy; re-check before relying on it for margins.
    "tts-1-hd": ModelPrice(30.00, 0.00),
    "tts-1": ModelPrice(15.00, 0.00),
    "gpt-4o-mini-tts": ModelPrice(15.00, 0.00),
    # --- Moonshot / Kimi (verify against https://platform.kimi.ai/docs/pricing) ---
    # K3 is a *reasoning* model and costs 5×/6× the older K-family rate — it MUST keep its own
    # entry, or the bare "kimi" prefix would under-bill it by ~6× (and reasoning tokens are
    # billed as output, so real K3 runs skew output-heavy).
    "kimi-k3": ModelPrice(3.00, 15.00),
    "kimi": ModelPrice(0.60, 2.50),
    "moonshot": ModelPrice(0.60, 2.50),
    # --- DeepSeek (verify against https://api-docs.deepseek.com/quick_start/pricing) ---
    "deepseek-reasoner": ModelPrice(0.55, 2.19),
    "deepseek": ModelPrice(0.27, 1.10),
}

# Fail-closed rate for unknown models: the most expensive known input+output pair.
_MOST_EXPENSIVE = ModelPrice(
    input_per_1m=max(p.input_per_1m for p in MODEL_PRICES.values()),
    output_per_1m=max(p.output_per_1m for p in MODEL_PRICES.values()),
)


def _resolve(model_id: str) -> ModelPrice | None:
    """Longest-prefix match against MODEL_PRICES. `fake` → free ($0). Unknown → None."""
    m = model_id.lower().strip()
    if m == "fake":
        return ModelPrice(0.0, 0.0)
    best: ModelPrice | None = None
    best_len = -1
    for prefix, price in MODEL_PRICES.items():
        if m.startswith(prefix) and len(prefix) > best_len:
            best, best_len = price, len(prefix)
    return best


def price_for(model_id: str) -> ModelPrice:
    """Resolve a model id to its price, failing closed to the most expensive known rate."""
    return _resolve(model_id) or _MOST_EXPENSIVE


def cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """USD cost of `input_tokens` + `output_tokens` for `model_id`.

    `fake` ⇒ 0. Unknown model ⇒ most-expensive known rate (never under-records)."""
    price = price_for(model_id)
    return (
        input_tokens / 1_000_000 * price.input_per_1m
        + output_tokens / 1_000_000 * price.output_per_1m
    )


def platform_cost_usd(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """What this usage costs *the platform* — i.e. what the spend kill-switch should sum.

    Identical to `cost_usd` except that frontier models are $0: they run only on a workspace's
    own key (`model_access`), so the tokens are billed to that workspace by the provider and
    never hit our account. Counting them would let one BYO-key user trip the platform-wide
    monthly cap for everyone else."""
    from calypr_api.model_access import is_frontier  # local: avoids a DSL import cycle

    if is_frontier(model_id):
        return 0.0
    return cost_usd(model_id, input_tokens, output_tokens)


# --- credits (PRICING-SPEC §2) -------------------------------------------------------------------
#
# 1 credit = $0.002 of model COGS = $0.01 retail, a constant 5× margin applied per direction:
#
#     credits_per_1M = provider_usd_per_1M × M / CREDIT_RETAIL_USD = usd × 500
#
# Deriving credits from the USD table rather than keeping a second hand-maintained table is what
# makes the margin hold on *every* model automatically — including the two the spec never listed:
#
#   * **Image** is already token-billed here (image-OUTPUT tokens in `output_per_1m`), so a
#     generation converts like any other model call.
#   * **TTS** is billed per character, and the node records the character count in the
#     `input_tokens` field (see the table above), so "per 1M characters" flows through the same
#     arithmetic with an output rate of 0.
#
# So the "Image and TTS have no credit rate" gap was a documentation gap, not a pricing one: the
# moment they were priced in USD they were priced in credits. What still needs a human is
# verifying the underlying USD rates — the ⚠️ at the top of this module.

#: Retail price of one credit, in USD.
CREDIT_RETAIL_USD = 0.01
#: Margin multiplier over model COGS.
CREDIT_MARGIN = 5.0


def credits_for(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Credits this usage costs a workspace.

    Fractional on purpose: rounding *here* would let a graph of many cheap nodes round to zero
    on every one of them. Round once, when a ledger entry is written, not per node."""
    return cost_usd(model_id, input_tokens, output_tokens) * CREDIT_MARGIN / CREDIT_RETAIL_USD


def platform_credits_for(model_id: str, input_tokens: int, output_tokens: int) -> float:
    """Credits to charge a *workspace* for this usage — the billing counterpart of
    `platform_cost_usd`.

    Frontier models are 0 for the same reason they cost the platform nothing: they run only on
    the workspace's own key (`model_access`), so the provider already billed them directly.
    Charging credits on top would be charging twice for one call."""
    from calypr_api.model_access import is_frontier  # local: avoids a DSL import cycle

    if is_frontier(model_id):
        return 0.0
    return credits_for(model_id, input_tokens, output_tokens)
