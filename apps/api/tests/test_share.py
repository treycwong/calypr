"""Share links: mint/list/revoke + the anonymous SECURITY DEFINER resolvers (WEEK3 plan §A).

Every share path touches the DB (minting needs a session, the resolvers need real rows), so
this whole module is DB-backed — skipped without Postgres, run in CI. The security-critical
piece is `claim_share_run`: its single conditional UPDATE is the race-free cap gate, so its
ok/revoked/cap/not_found behavior is asserted directly against seeded rows.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.db.models import Agent, ShareLink, Workspace
from calypr_api.db.session import SessionLocal, engine, set_tenant
from calypr_api.main import app
from calypr_compiler.golden import input_agent_output
from fastapi.testclient import TestClient
from sqlalchemy import select, text

client = TestClient(app)


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


pytest_db = pytest.mark.skipif(not _db_available(), reason="Postgres not available")


def _make_agent(workspace_id: str) -> uuid.UUID:
    """Insert an agent directly under a workspace and return its id."""
    graph = input_agent_output(model="fake").model_dump()
    with SessionLocal() as s:
        set_tenant(s, workspace_id)
        agent = Agent(workspace_id=uuid.UUID(workspace_id), name="Shared", graph_spec=graph)
        s.add(agent)
        s.commit()
        s.refresh(agent)
        return agent.id


def _make_foreign_workspace_agent() -> tuple[uuid.UUID, uuid.UUID]:
    """A workspace + agent that is NOT the dev workspace (for isolation checks)."""
    with SessionLocal() as s:
        ws = Workspace(name="Other")
        s.add(ws)
        s.commit()
        s.refresh(ws)
        set_tenant(s, str(ws.id))
        agent = Agent(
            workspace_id=ws.id,
            name="Foreign",
            graph_spec=input_agent_output(model="fake").model_dump(),
        )
        s.add(agent)
        s.commit()
        s.refresh(agent)
        return ws.id, agent.id


# --------------------------------------------------------------------------- routes


@pytest_db
def test_mint_list_revoke_roundtrip():
    agent_id = _make_agent(DEV_WORKSPACE_ID)

    # Mint — default cap applies when run_cap is omitted.
    r = client.post(f"/agents/{agent_id}/share", json={})
    assert r.status_code == 200, r.text
    minted = r.json()
    token = minted["token"]
    assert token and minted["run_cap"] == 25
    assert minted["run_count"] == 0 and minted["revoked_at"] is None

    # List — the new link shows up.
    r = client.get(f"/agents/{agent_id}/shares")
    assert r.status_code == 200
    assert any(s["token"] == token for s in r.json())

    # Revoke — sets revoked_at, idempotent.
    r = client.delete(f"/agents/{agent_id}/share/{token}")
    assert r.status_code == 200
    first_revoked = r.json()["revoked_at"]
    assert first_revoked is not None
    r2 = client.delete(f"/agents/{agent_id}/share/{token}")
    assert r2.status_code == 200 and r2.json()["revoked_at"] == first_revoked


@pytest_db
def test_mint_honors_explicit_cap():
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    r = client.post(f"/agents/{agent_id}/share", json={"run_cap": 3})
    assert r.status_code == 200 and r.json()["run_cap"] == 3


@pytest_db
def test_mint_unknown_agent_404():
    assert client.post(f"/agents/{uuid.uuid4()}/share", json={}).status_code == 404
    assert client.post("/agents/not-a-uuid/share", json={}).status_code == 404


@pytest_db
def test_tenant_isolation_cannot_touch_foreign_agent_shares():
    """The dev-workspace client can't list or revoke another workspace's shares."""
    _ws, foreign_agent = _make_foreign_workspace_agent()
    # Seed a share under the foreign agent directly.
    with SessionLocal() as s:
        set_tenant(s, str(_ws))
        link = ShareLink(
            token=f"foreign-{uuid.uuid4().hex}",
            agent_id=foreign_agent,
            workspace_id=_ws,
            run_cap=25,
        )
        s.add(link)
        s.commit()
        foreign_token = link.token

    # `_get_owned` gates every share route → 404 for a foreign agent.
    assert client.get(f"/agents/{foreign_agent}/shares").status_code == 404
    assert client.post(f"/agents/{foreign_agent}/share", json={}).status_code == 404
    assert (
        client.delete(f"/agents/{foreign_agent}/share/{foreign_token}").status_code == 404
    )


# --------------------------------------------------------------------- SQL resolvers


def _seed_link(*, revoked: bool = False, run_cap=None, run_count: int = 0) -> str:
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    token = f"tok-{uuid.uuid4().hex}"
    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        link = ShareLink(
            token=token,
            agent_id=agent_id,
            workspace_id=uuid.UUID(DEV_WORKSPACE_ID),
            run_cap=run_cap,
            run_count=run_count,
        )
        s.add(link)
        s.commit()
        if revoked:
            s.execute(
                text("UPDATE share_link SET revoked_at = now() WHERE token = :t"),
                {"t": token},
            )
            s.commit()
    return token


@pytest_db
def test_share_agent_name_resolves_and_hides_revoked():
    live = _seed_link()
    revoked = _seed_link(revoked=True)
    with engine.connect() as conn:
        assert (
            conn.execute(text("SELECT share_agent_name(:t)"), {"t": live}).scalar() == "Shared"
        )
        assert conn.execute(text("SELECT share_agent_name(:t)"), {"t": revoked}).scalar() is None
        assert conn.execute(text("SELECT share_agent_name('nope')")).scalar() is None


@pytest_db
def test_claim_share_run_ok_increments():
    token = _seed_link(run_cap=5, run_count=0)
    with engine.connect() as conn:
        row = conn.execute(
            text("SELECT status, workspace_id, graph_spec FROM claim_share_run(:t)"),
            {"t": token},
        ).one()
        assert row.status == "ok"
        assert str(row.workspace_id) == DEV_WORKSPACE_ID
        assert row.graph_spec is not None  # the spec is returned server-side, never to clients
        conn.commit()
    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        link = s.execute(select(ShareLink).where(ShareLink.token == token)).scalar_one()
        assert link.run_count == 1


@pytest_db
def test_claim_share_run_denies_cap_revoked_unknown():
    capped = _seed_link(run_cap=2, run_count=2)
    revoked = _seed_link(revoked=True)
    with engine.connect() as conn:
        assert (
            conn.execute(
                text("SELECT status FROM claim_share_run(:t)"), {"t": capped}
            ).scalar()
            == "cap"
        )
        assert (
            conn.execute(
                text("SELECT status FROM claim_share_run(:t)"), {"t": revoked}
            ).scalar()
            == "revoked"
        )
        assert (
            conn.execute(
                text("SELECT status FROM claim_share_run('missing')")
            ).scalar()
            == "not_found"
        )
        conn.commit()


@pytest_db
def test_claim_share_run_cap_gate_is_atomic():
    """Two claims against a cap of 1: exactly one 'ok', one 'cap'. The conditional UPDATE
    (not check-then-update) is what makes this race-free."""
    token = _seed_link(run_cap=1, run_count=0)
    with engine.connect() as conn:
        first = conn.execute(
            text("SELECT status FROM claim_share_run(:t)"), {"t": token}
        ).scalar()
        conn.commit()
        second = conn.execute(
            text("SELECT status FROM claim_share_run(:t)"), {"t": token}
        ).scalar()
        conn.commit()
    assert {first, second} == {"ok", "cap"}


@pytest_db
def test_mint_then_public_run_streams_and_meters():
    """End-to-end: mint via the authenticated route, then run the link anonymously (no headers).
    The stream delivers tokens + [DONE] and a `run` row lands with source='share' + the owner's
    workspace."""
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    token = client.post(f"/agents/{agent_id}/share", json={}).json()["token"]

    r = client.post(f"/share/{token}/runs", json={"message": "hello", "thread_id": "t1"})
    assert r.status_code == 200
    assert "Echo:" in r.text and "[DONE]" in r.text
    assert '"type": "error"' not in r.text

    with SessionLocal() as s:
        set_tenant(s, DEV_WORKSPACE_ID)
        from calypr_api.db.models import Run

        run = s.execute(
            select(Run).where(Run.thread_id == f"share:{token}:t1")
        ).scalar_one()
        assert run.source == "share"
        assert str(run.workspace_id) == DEV_WORKSPACE_ID
        assert run.agent_id == agent_id
        assert run.status == "completed"


@pytest_db
def test_get_share_returns_name_only_never_spec():
    """The core promise: the public GET exposes the agent name and nothing that could
    reconstruct the graph."""
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    token = client.post(f"/agents/{agent_id}/share", json={}).json()["token"]

    r = client.get(f"/share/{token}")
    assert r.status_code == 200
    body = r.json()
    assert body == {"agent_name": "Shared"}
    raw = r.text
    for leaked in ("graph_spec", "nodes", "edges", "system_prompt"):
        assert leaked not in raw


@pytest_db
def test_get_share_unknown_or_revoked_404():
    assert client.get(f"/share/{uuid.uuid4().hex}").status_code == 404
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    token = client.post(f"/agents/{agent_id}/share", json={}).json()["token"]
    client.delete(f"/agents/{agent_id}/share/{token}")
    assert client.get(f"/share/{token}").status_code == 404


@pytest_db
def test_public_run_refused_when_cap_reached():
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    token = client.post(f"/agents/{agent_id}/share", json={"run_cap": 1}).json()["token"]
    # First run consumes the only slot.
    assert "[DONE]" in client.post(f"/share/{token}/runs", json={"message": "a"}).text
    # Second run is refused in-stream (200 SSE, but an error envelope, no tokens).
    r = client.post(f"/share/{token}/runs", json={"message": "b"})
    assert r.status_code == 200
    assert "run limit" in r.text and "[DONE]" in r.text
    assert "Echo:" not in r.text


@pytest_db
def test_public_run_refused_when_revoked():
    agent_id = _make_agent(DEV_WORKSPACE_ID)
    token = client.post(f"/agents/{agent_id}/share", json={}).json()["token"]
    client.delete(f"/agents/{agent_id}/share/{token}")
    r = client.post(f"/share/{token}/runs", json={"message": "a"})
    assert r.status_code == 200
    assert "revoked" in r.text and "Echo:" not in r.text


@pytest_db
def test_public_run_unknown_token_errors_in_stream():
    r = client.post(f"/share/{uuid.uuid4().hex}/runs", json={"message": "a"})
    assert r.status_code == 200
    assert '"type": "error"' in r.text and "[DONE]" in r.text
    assert "Echo:" not in r.text


@pytest_db
def test_share_link_has_rls_enabled():
    with engine.connect() as conn:
        rls_on = conn.execute(
            text("SELECT relrowsecurity FROM pg_class WHERE relname = 'share_link'")
        ).scalar()
        assert rls_on is True
        policies = conn.execute(
            text("SELECT count(*) FROM pg_policies WHERE tablename = 'share_link'")
        ).scalar()
        assert policies >= 1
