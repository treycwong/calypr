"""BYO model-provider API keys — the Settings "API Keys" section (MCP-NODE-PLAN §5).

A workspace can supply its own OpenAI/Anthropic/Tavily key; it is Fernet-encrypted in the vault
and, at run time, overrides the server env for that provider. Keys are write-only — no endpoint
ever returns one; the list reports only which providers have a key on file. Same `Depends(tenant)`
+ RLS scoping as the rest of the API.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

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


@router.get("/provider-keys", response_model=list[ProviderKeyInfo], tags=["provider-keys"])
def list_provider_keys(t: Tenant = Depends(tenant)) -> list[ProviderKeyInfo]:
    """One row per supported provider with a `has_key` flag (never the key itself)."""
    rows = (
        t.session.execute(select(ProviderKey).where(ProviderKey.workspace_id == t.workspace_id))
        .scalars()
        .all()
    )
    on_file = {r.provider for r in rows}
    return [ProviderKeyInfo(provider=p, has_key=p in on_file) for p in PROVIDER_KEY_PROVIDERS]


@router.put("/provider-keys/{provider}", response_model=ProviderKeyInfo, tags=["provider-keys"])
def set_provider_key(
    provider: str, body: ProviderKeySet, t: Tenant = Depends(tenant)
) -> ProviderKeyInfo:
    """Upsert a provider's BYO key (encrypted). Replaces any existing key for that provider."""
    if provider not in PROVIDER_KEY_PROVIDERS:
        raise HTTPException(status_code=404, detail="unknown provider")
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
    if existing is None:
        t.session.add(
            ProviderKey(
                workspace_id=t.workspace_id,
                provider=provider,
                key_encrypted=encrypt(body.key),
            )
        )
    else:
        existing.key_encrypted = encrypt(body.key)
    t.session.commit()
    posthog_client.capture(
        "provider_key_set",
        distinct_id=str(t.workspace_id),
        properties={"provider": provider},
    )
    return ProviderKeyInfo(provider=provider, has_key=True)


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
