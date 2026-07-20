"""Connector CRUD + live test — the Settings panel's backend (MCP-NODE-PLAN §5).

The one place workspace secrets are entered and stored: a Tier B MCP server (URL + optional
bearer) or a Tier A OAuth connector (Notion). Secrets are Fernet-encrypted via the vault before
they touch the DB and are never returned to the client. Same `Depends(tenant)` + RLS scoping as
`agents.py`.
"""

from __future__ import annotations

import base64
import urllib.parse
import uuid

import httpx
from calypr_nodes.tools_catalog import mcp_tools
from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select

from calypr_api.config import settings
from calypr_api.connectors import (
    ConnectorResolutionError,
    assert_egress_allowed,
    resolve,
)
from calypr_api.db.models import ConnectorCredential
from calypr_api.deps import Tenant, tenant
from calypr_api.posthog_client import posthog_client
from calypr_api.schemas import (
    ConnectorCreate,
    ConnectorInfo,
    ConnectorTestResult,
    NotionCallback,
    OAuthStart,
)
from calypr_api.vault import encrypt

router = APIRouter()

NOTION_AUTHORIZE_URL = "https://api.notion.com/v1/oauth/authorize"
NOTION_TOKEN_URL = "https://api.notion.com/v1/oauth/token"
# Where Notion returns the browser — a web route that forwards the code to /notion/callback.
NOTION_REDIRECT_PATH = "/api/connectors/notion/callback"


def _info(c: ConnectorCredential) -> ConnectorInfo:
    return ConnectorInfo(
        id=str(c.id),
        kind=c.kind,
        name=c.name,
        url=c.url,
        transport=c.transport,
        has_secret=c.secret_encrypted is not None,
        meta=c.meta or {},
        created_at=c.created_at,
    )


def _get_owned(t: Tenant, connector_id: str) -> ConnectorCredential:
    try:
        pk = uuid.UUID(connector_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail="connector not found") from exc
    c = t.session.get(ConnectorCredential, pk)
    if c is None or c.workspace_id != t.workspace_id:
        raise HTTPException(status_code=404, detail="connector not found")
    return c


@router.get("/connectors", response_model=list[ConnectorInfo], tags=["connectors"])
def list_connectors(t: Tenant = Depends(tenant)) -> list[ConnectorInfo]:
    rows = (
        t.session.execute(
            select(ConnectorCredential)
            .where(ConnectorCredential.workspace_id == t.workspace_id)
            .order_by(ConnectorCredential.created_at.desc())
        )
        .scalars()
        .all()
    )
    return [_info(c) for c in rows]


@router.post("/connectors", response_model=ConnectorInfo, tags=["connectors"])
def create_connector(
    body: ConnectorCreate, t: Tenant = Depends(tenant)
) -> ConnectorInfo:
    """Save a Tier B MCP server. The bearer secret (if any) is encrypted before storage."""
    try:
        assert_egress_allowed(body.url)  # reject private/loopback hosts early (SSRF guard)
    except ConnectorResolutionError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    c = ConnectorCredential(
        workspace_id=t.workspace_id,
        kind="mcp",
        name=body.name,
        url=body.url,
        transport=body.transport,
        secret_encrypted=encrypt(body.secret) if body.secret else None,
    )
    t.session.add(c)
    t.session.commit()
    t.session.refresh(c)
    posthog_client.capture(
        "connector_created",
        distinct_id=str(t.workspace_id),
        properties={"connector_id": str(c.id), "kind": "mcp"},
    )
    return _info(c)


@router.post(
    "/connectors/{connector_id}/test",
    response_model=ConnectorTestResult,
    tags=["connectors"],
)
def test_connector(
    connector_id: str, t: Tenant = Depends(tenant)
) -> ConnectorTestResult:
    """Resolve the connector and list its tools — the canvas/Settings 'Test' button. Errors are
    surfaced as a friendly message, never a stack trace or a leaked secret."""
    c = _get_owned(t, connector_id)
    try:
        conn = resolve(c)
        tools = mcp_tools(conn.url, conn.transport, headers=conn.headers)
        return ConnectorTestResult(ok=True, tools=sorted(tt.name for tt in tools))
    except ConnectorResolutionError as exc:
        return ConnectorTestResult(ok=False, error=str(exc))
    except Exception:
        # Never surface the underlying error (could echo a URL/header); keep it generic.
        return ConnectorTestResult(
            ok=False, error="could not connect to the MCP server — check the URL and token."
        )


def _notion_redirect_uri() -> str:
    if not settings.oauth_redirect_base:
        raise HTTPException(
            status_code=501,
            detail="CALYPR_OAUTH_REDIRECT_BASE is not configured.",
        )
    return f"{settings.oauth_redirect_base.rstrip('/')}{NOTION_REDIRECT_PATH}"


@router.get("/connectors/notion/connect", response_model=OAuthStart, tags=["connectors"])
def notion_connect(t: Tenant = Depends(tenant)) -> OAuthStart:
    """Start the Notion OAuth consent flow — returns the URL the browser should open. Requires a
    configured Notion public integration (client id/secret)."""
    if not settings.notion_client_id or not settings.notion_client_secret:
        raise HTTPException(
            status_code=501, detail="Notion connector is not configured on this server."
        )
    params = {
        "client_id": settings.notion_client_id,
        "redirect_uri": _notion_redirect_uri(),
        "response_type": "code",
        "owner": "user",
    }
    return OAuthStart(
        authorize_url=f"{NOTION_AUTHORIZE_URL}?{urllib.parse.urlencode(params)}"
    )


@router.post("/connectors/notion/callback", response_model=ConnectorInfo, tags=["connectors"])
def notion_callback(body: NotionCallback, t: Tenant = Depends(tenant)) -> ConnectorInfo:
    """Exchange the OAuth code for a Notion bot token and save it as an encrypted connector.

    The token never leaves the server: it is Fernet-encrypted immediately and only the
    non-secret workspace name is stored in `meta` for display."""
    if not settings.notion_client_id or not settings.notion_client_secret:
        raise HTTPException(
            status_code=501, detail="Notion connector is not configured on this server."
        )
    basic = base64.b64encode(
        f"{settings.notion_client_id}:{settings.notion_client_secret}".encode()
    ).decode()
    try:
        resp = httpx.post(
            NOTION_TOKEN_URL,
            headers={
                "Authorization": f"Basic {basic}",
                "Content-Type": "application/json",
            },
            json={
                "grant_type": "authorization_code",
                "code": body.code,
                "redirect_uri": _notion_redirect_uri(),
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=502, detail="Notion token exchange failed."
        ) from exc

    access_token = data.get("access_token")
    if not access_token:
        raise HTTPException(status_code=502, detail="Notion did not return an access token.")

    c = ConnectorCredential(
        workspace_id=t.workspace_id,
        kind="notion",
        name=data.get("workspace_name") or "Notion",
        url=None,  # resolved from server config at run time
        transport="streamable_http",
        secret_encrypted=encrypt(access_token),
        meta={
            "workspace_name": data.get("workspace_name"),
            "workspace_icon": data.get("workspace_icon"),
            "bot_id": data.get("bot_id"),
        },
    )
    t.session.add(c)
    t.session.commit()
    t.session.refresh(c)
    posthog_client.capture(
        "connector_created",
        distinct_id=str(t.workspace_id),
        properties={"connector_id": str(c.id), "kind": "notion"},
    )
    return _info(c)


@router.delete(
    "/connectors/{connector_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["connectors"],
)
def delete_connector(connector_id: str, t: Tenant = Depends(tenant)) -> Response:
    c = _get_owned(t, connector_id)
    t.session.delete(c)
    t.session.commit()
    posthog_client.capture(
        "connector_deleted",
        distinct_id=str(t.workspace_id),
        properties={"connector_id": connector_id, "kind": c.kind},
    )
    return Response(status_code=status.HTTP_204_NO_CONTENT)
