"""The 0019 tables: tenant isolation and the constraints the write path relies on.

Two things are worth a test at this layer. The RLS policies, because a transcript is the most
personal thing this product stores and "conversation" is a table another tenant must never read
through. And `uq_conversation_thread`, because `ConversationRecorder` leans on it for an
idempotent per-turn upsert — without the constraint the upsert silently becomes an insert and
every turn starts a new conversation.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api.db.models import Asset, Conversation, Message, OrphanBlob
from calypr_api.db.session import SessionLocal, engine, set_tenant
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


def _seed(session, workspace_id: uuid.UUID, *, suffix: str = "abc123") -> Conversation:
    """A conversation with one turn and one generated asset."""
    convo = Conversation(workspace_id=workspace_id, thread_suffix=suffix, title="Austria trip")
    session.add(convo)
    session.flush()
    session.add(
        Message(
            conversation_id=convo.id,
            workspace_id=workspace_id,
            role="user",
            seq=0,
            text="Generate a realistic image of street photography in Austria",
        )
    )
    session.add(
        Asset(
            workspace_id=workspace_id,
            conversation_id=convo.id,
            kind="image",
            blob_url="https://blob.example/runs/png/deadbeef.png",
            bytes=2048,
            caption="street photography in Austria",
        )
    )
    session.commit()
    return convo


@requires_db
def test_rows_are_invisible_to_another_tenant(tenant_factory):
    """Tenant B cannot see tenant A's transcript through the query shape the API issues.

    Be precise about what this proves. The app connects as table owner and therefore *bypasses*
    RLS today — 0001_baseline documents the non-owner role as a later phase — so the isolation
    exercised here is the explicit `workspace_id` predicate, not the policy. The policy is
    defence-in-depth for when that role lands, and it is asserted structurally by
    `test_policies_exist` below rather than behaviourally, which would silently pass for the
    wrong reason while we are still the owner."""
    a = tenant_factory()
    b = tenant_factory()

    with SessionLocal() as s:
        set_tenant(s, str(a.workspace_id))
        _seed(s, a.workspace_id)

    with SessionLocal() as s:
        set_tenant(s, str(b.workspace_id))
        # Explicit predicate *and* RLS — the belt-and-braces pattern `agents.py` uses. This is
        # the query shape the API actually issues, so it is the one worth asserting.
        visible = (
            s.query(Conversation).filter(Conversation.workspace_id == b.workspace_id).count()
        )
        assert visible == 0
        assert s.query(Message).filter(Message.workspace_id == b.workspace_id).count() == 0
        assert s.query(Asset).filter(Asset.workspace_id == b.workspace_id).count() == 0


@requires_db
def test_policies_exist():
    """Every new table carries the tenant-isolation policy. Structural, because behavioural
    proof is impossible while the app is the table owner — see the note above."""
    with SessionLocal() as s:
        rows = {
            r[0]
            for r in s.execute(
                text(
                    "SELECT tablename FROM pg_policies"
                    " WHERE tablename IN ('conversation','message','asset','orphan_blob')"
                    "   AND policyname = tablename || '_tenant_isolation'"
                )
            )
        }
    assert rows == {"conversation", "message", "asset", "orphan_blob"}


@requires_db
def test_thread_suffix_is_unique_per_workspace(tenant_factory):
    """What makes the per-turn write an upsert instead of a duplicate conversation."""
    t = tenant_factory()
    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        _seed(s, t.workspace_id, suffix="dup")

    with SessionLocal() as s, pytest.raises(IntegrityError):
        set_tenant(s, str(t.workspace_id))
        s.add(Conversation(workspace_id=t.workspace_id, thread_suffix="dup"))
        s.commit()


@requires_db
def test_the_same_suffix_in_two_workspaces_is_fine(tenant_factory):
    """The client mints the suffix, so two workspaces colliding is expected, not an error."""
    a = tenant_factory()
    b = tenant_factory()
    for t in (a, b):
        with SessionLocal() as s:
            set_tenant(s, str(t.workspace_id))
            s.add(Conversation(workspace_id=t.workspace_id, thread_suffix="web-same"))
            s.commit()


@requires_db
def test_deleting_a_conversation_cascades_to_messages_and_assets(tenant_factory):
    """`DELETE /conversations/{id}` relies on this rather than deleting children itself — and it
    is why the confirm dialog has to name the media count."""
    t = tenant_factory()
    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        convo = _seed(s, t.workspace_id, suffix="cascade")
        convo_id = convo.id

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        s.query(Conversation).filter(Conversation.id == convo_id).delete()
        s.commit()

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        assert s.query(Message).filter(Message.conversation_id == convo_id).count() == 0
        assert s.query(Asset).filter(Asset.conversation_id == convo_id).count() == 0


@requires_db
def test_orphan_blob_round_trips(tenant_factory):
    """The parking spot for a blob delete that failed. Small, but the GC arm reads it."""
    t = tenant_factory()
    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        s.add(
            OrphanBlob(
                workspace_id=t.workspace_id,
                blob_url="https://blob.example/runs/png/gone.png",
                last_error="503",
            )
        )
        s.commit()

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        row = s.query(OrphanBlob).filter(OrphanBlob.workspace_id == t.workspace_id).one()
        assert row.attempts == 0
        assert row.failed_at is not None
