"""Configure the Stripe customer portal for the Starter/Plus retier — test or live, same code.

The portal is where a subscriber switches between Starter and Plus, and the pricing FAQ makes
promises about how that behaves. This script is those promises, written down once, so the test
and live accounts can't be configured differently by hand:

- **Upgrade (Starter → Plus) starts now** and is charged the prorated difference on the spot
  (`always_invoice`). The webhook then sees the Plus price and tops credits up straight away.
- **Downgrade (Plus → Starter) waits for the period end** (`schedule_at_period_end` on a
  decreasing amount), because the customer has already paid for Plus this month.
- **Cancel waits for the period end** too, with no proration: "you keep your plan until the end
  of the period you've paid for".

It edits the account's **default** configuration (creating one if there is none), because
`POST /billing/portal` opens sessions without naming a configuration.

The prices come from the same env the API reads, `STRIPE_STARTER_PRICE_ID` and
`STRIPE_PLUS_PRICE_ID`, with `STRIPE_SECRET_KEY` deciding test or live:

    # look first: prints the current default and what would change
    uv run python scripts/configure_portal.py

    # then act
    uv run python scripts/configure_portal.py --yes
"""

from __future__ import annotations

import argparse
import sys

import stripe
from calypr_api import billing, entitlements


def _products() -> list[dict[str, object]]:
    """One portal product entry per sellable plan, in the order the pricing page lists them."""
    entries = []
    for plan in entitlements.PAID_PLANS:
        price_id = billing.price_id_for(plan)
        if not price_id:
            sys.exit(f"no price configured for {plan}; set its STRIPE_*_PRICE_ID first")
        price = stripe.Price.retrieve(price_id, api_key=billing.secret_key())
        if not price.active:
            sys.exit(f"{plan} price {price_id} is archived; the portal can't offer it")
        entries.append({"product": price.product, "prices": [price_id]})
    return entries


def _features(products: list[dict[str, object]]) -> dict[str, object]:
    return {
        "invoice_history": {"enabled": True},
        "payment_method_update": {"enabled": True},
        "customer_update": {"enabled": True, "allowed_updates": ["email", "address"]},
        "subscription_cancel": {
            "enabled": True,
            "mode": "at_period_end",
            "proration_behavior": "none",
        },
        "subscription_update": {
            "enabled": True,
            "default_allowed_updates": ["price"],
            "products": products,
            "proration_behavior": "always_invoice",
            "schedule_at_period_end": {"conditions": [{"type": "decreasing_item_amount"}]},
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--yes", action="store_true", help="write the configuration")
    args = parser.parse_args()

    key = billing.secret_key()
    if not key:
        sys.exit("STRIPE_SECRET_KEY is not set")
    mode = "LIVE" if key.startswith(("sk_live_", "rk_live_")) else "test"

    configs = stripe.billing_portal.Configuration.list(api_key=key, limit=100).data
    default = next((c for c in configs if c.is_default), None)
    features = _features(_products())

    print(f"mode: {mode}")
    if default is None:
        print("default portal configuration: none (one will be created)")
    else:
        current = default.to_dict()["features"]["subscription_update"]
        print(f"default portal configuration: {default.id}")
        print(f"  plan switching now: enabled={current['enabled']} products={current['products']}")
    print(f"  plan switching after: products={features['subscription_update']['products']}")

    if not args.yes:
        print("\nnothing written; pass --yes to apply")
        return

    if default is None:
        default = stripe.billing_portal.Configuration.create(
            api_key=key,
            features=features,
            business_profile={"headline": "Manage your Calypr plan"},
        )
    else:
        default = stripe.billing_portal.Configuration.modify(
            default.id, api_key=key, features=features
        )
    print(f"\nwrote {default.id} (default={default.is_default})")


if __name__ == "__main__":
    main()
