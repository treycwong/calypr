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
    # --- Moonshot / Kimi (verify against https://platform.moonshot.ai/docs/pricing) ---
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
