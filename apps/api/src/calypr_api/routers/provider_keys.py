"""BYO model-provider API keys — the Settings "API Keys" section (MCP-NODE-PLAN §5).

A workspace can supply its own OpenAI/Anthropic/Tavily key; it is Fernet-encrypted in the vault
and, at run time, overrides the server env for that provider. Keys are write-only — no endpoint
ever returns one; the list reports only which providers have a key on file. Same `Depends(tenant)`
+ RLS scoping as the rest of the API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select, text

from calypr_api import entitlements
from calypr_api.db.models import ProviderKey
from calypr_api.deps import Tenant, tenant
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import (
    PROVIDER_KEY_PROVIDERS,
    ProviderKeyInfo,
    ProviderKeySet,
)
from calypr_api.vault import encrypt

router = APIRouter()


def _plan_of(t: Tenant) -> str | None:
    """This workspace's plan, through the account join every other gate uses (migration 0016).

    Reuses `deps._PLAN_FOR_WORKSPACE` rather than restating the SQL: two copies of the join is how
    two gates end up disagreeing about who is paying."""
    from calypr_api.deps import _PLAN_FOR_WORKSPACE

    row = t.session.execute(text(_PLAN_FOR_WORKSPACE), {"id": str(t.workspace_id)})
    return row.scalar_one_or_none()


def _stored_providers(t: Tenant) -> set[str]:
    rows = (
        t.session.execute(select(ProviderKey).where(ProviderKey.workspace_id == t.workspace_id))
        .scalars()
        .all()
    )
    return {r.provider for r in rows}


@router.get("/provider-keys", response_model=list[ProviderKeyInfo], tags=["provider-keys"])
def list_provider_keys(t: Tenant = Depends(tenant)) -> list[ProviderKeyInfo]:
    """One row per supported provider with a `has_key` flag (never the key itself)."""
    rows = (
        t.session.execute(select(ProviderKey).where(ProviderKey.workspace_id == t.workspace_id))
        .scalars()
        .all()
    )
    by_provider = {r.provider: r for r in rows}
    # Filtered by plan, not just labelled: a key a Free workspace can never spend is dead config,
    # and the field offering it reads as a feature the plan includes. `usable_providers` keeps a
    # provider visible when a key is already stored, so a downgrade never strands a credential
    # somewhere the owner can't reach it.
    return [
        ProviderKeyInfo(
            provider=p,
            has_key=p in by_provider,
            key_hint=by_provider[p].key_hint if p in by_provider else None,
        )
        for p in entitlements.usable_providers(_plan_of(t), set(by_provider))
    ]


@router.put("/provider-keys/{provider}", response_model=ProviderKeyInfo, tags=["provider-keys"])
def set_provider_key(
    provider: str, body: ProviderKeySet, t: Tenant = Depends(tenant)
) -> ProviderKeyInfo:
    """Upsert a provider's BYO key (encrypted). Replaces any existing key for that provider."""
    if provider not in PROVIDER_KEY_PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
    # The list above hides these; this is what makes the hiding a rule rather than a decoration,
    # since the endpoint is reachable directly. A stored key is still replaceable — only a *new*
    # one is refused — so a downgraded workspace can rotate what it has until it clears it.
    if provider in entitlements.PLUS_ONLY_PROVIDERS and provider not in _stored_providers(t):
        if not entitlements.has_media_nodes(_plan_of(t)):
            raise HTTPException(
                status_code=402,
                detail={"reason": "plan", "feature": f"{provider}_key"},
            )
    existing = (
        t.session.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == t.workspace_id,
                ProviderKey.provider == provider,
            )
        )
        .scalars()
        .first()
    )
    # The hint is derived here, at the only point the plaintext is in hand. Short keys would make
    # a 4-character suffix a large fraction of the secret, so anything under 8 gets no hint at
    # all rather than a revealing one.
    hint = body.key[-4:] if len(body.key) >= 8 else None
    if existing is None:
        t.session.add(
            ProviderKey(
                workspace_id=t.workspace_id,
                provider=provider,
                key_encrypted=encrypt(body.key),
                key_hint=hint,
            )
        )
    else:
        existing.key_encrypted = encrypt(body.key)
        existing.key_hint = hint
    t.session.commit()
    posthog_client.capture(
        "provider_key_set",
        distinct_id=str(t.workspace_id),
        properties={"provider": provider},
    )
    return ProviderKeyInfo(provider=provider, has_key=True, key_hint=hint)


@router.delete(
    "/provider-keys/{provider}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["provider-keys"],
)
def delete_provider_key(provider: str, t: Tenant = Depends(tenant)) -> Response:
    row = (
        t.session.execute(
            select(ProviderKey).where(
                ProviderKey.workspace_id == t.workspace_id,
                ProviderKey.provider == provider,
            )
        )
        .scalars()
        .first()
    )
    if row is not None:
        t.session.delete(row)
        t.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
