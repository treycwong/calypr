"""`/conversations` + `/assets`: what the Playground's History and Media tabs call.

The delete tests are the ones that matter most. Deleting a conversation crosses three stores
that share no transaction — Postgres rows, LangGraph's checkpoint tables, and Vercel Blob — and
each has its own way of half-failing. `purge.py` learned this the hard way for account deletion;
these pin the same reasoning at row granularity.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import deps
from calypr_api.config import settings
from calypr_api.db.models import Account, Asset, Conversation, Message, OrphanBlob
from calypr_api.db.session import SessionLocal, engine, set_tenant
from calypr_api.main import app
from calypr_api.routers import history
from fastapi.testclient import TestClient
from sqlalchemy import text

client = TestClient(app)

INTERNAL_KEY = "prod-key"


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


def _hdr(user_id: str, workspace_id: uuid.UUID | str | None = None) -> dict[str, str]:
    h = {"x-calypr-internal-key": INTERNAL_KEY, "x-calypr-user-id": user_id}
    if workspace_id is not None:
        h[deps.WORKSPACE_HEADER] = str(workspace_id)
    return h


@pytest.fixture
def user(monkeypatch):
    """A signed-in user with enforcement on, cleaned up afterwards."""
    monkeypatch.setattr(settings, "internal_key", INTERNAL_KEY)
    uid = f"hist-test-{uuid.uuid4().hex[:10]}"
    yield uid
    with SessionLocal() as s:
        s.query(Account).filter(Account.owner_user_id == uid).delete(synchronize_session=False)
        s.commit()


def _seed(
    workspace_id,
    *,
    suffix: str,
    title: str,
    user_text: str = "hello",
    assistant_text: str = "hi back",
    assets: int = 0,
    agent_id: uuid.UUID | None = None,
) -> uuid.UUID:
    with SessionLocal() as s:
        set_tenant(s, str(workspace_id))
        convo = Conversation(
            workspace_id=workspace_id, thread_suffix=suffix, title=title, agent_id=agent_id
        )
        s.add(convo)
        s.flush()
        s.add(
            Message(
                conversation_id=convo.id,
                workspace_id=workspace_id,
                role="user",
                seq=0,
                text=user_text,
            )
        )
        s.add(
            Message(
                conversation_id=convo.id,
                workspace_id=workspace_id,
                role="assistant",
                seq=1,
                text=assistant_text,
            )
        )
        for i in range(assets):
            s.add(
                Asset(
                    workspace_id=workspace_id,
                    conversation_id=convo.id,
                    kind="image",
                    blob_url=f"https://blob.example/runs/png/{uuid.uuid4().hex}.png",
                    bytes=1024,
                    caption=f"{title} picture {i}",
                )
            )
        s.commit()
        return convo.id


def _workspace_of(user_id: str) -> uuid.UUID:
    """The workspace the API resolves this user to — the one the seed has to write into."""
    r = client.get("/workspaces/current", headers=_hdr(user_id))
    assert r.status_code == 200, r.text
    return uuid.UUID(r.json()["id"])


# --------------------------------------------------------------------------- pure helpers


def test_like_escapes_user_wildcards():
    """A search for `100%` must not silently become "anything starting with 100"."""
    assert history._like("100%") == "%100\\%%"
    assert history._like("a_b") == "%a\\_b%"


def test_a_malformed_cursor_starts_the_list_over():
    """A stale cursor from a reloaded tab should reset the list, not 400 it."""
    assert history._parse_cursor("garbage") is None
    assert history._parse_cursor(None) is None
    assert history._parse_cursor("not-a-date|not-a-uuid") is None


# --------------------------------------------------------------------------- list + search


@requires_db
def test_lists_newest_first_and_searches_title_and_body(user):
    ws = _workspace_of(user)
    _seed(ws, suffix="s-one", title="Austria trip", user_text="street photography")
    _seed(ws, suffix="s-two", title="Invoice parser", user_text="parse a PDF")

    r = client.get("/conversations", headers=_hdr(user))
    assert r.status_code == 200
    items = r.json()["items"]
    assert [i["title"] for i in items] == ["Invoice parser", "Austria trip"]
    assert items[0]["message_count"] == 2
    assert items[0]["preview"] == "parse a PDF"
    # No checkpoint rows were written, so the agent remembers none of these.
    assert all(i["has_state"] is False for i in items)

    # Title match.
    r = client.get("/conversations", params={"q": "austria"}, headers=_hdr(user))
    assert [i["title"] for i in r.json()["items"]] == ["Austria trip"]
    # Body match — the reason search isn't a client-side filter over titles.
    r = client.get("/conversations", params={"q": "PDF"}, headers=_hdr(user))
    assert [i["title"] for i in r.json()["items"]] == ["Invoice parser"]
    r = client.get("/conversations", params={"q": "nothing here"}, headers=_hdr(user))
    assert r.json()["items"] == []


@requires_db
def test_keyset_pagination_walks_every_row_once(user):
    """The property OFFSET loses: no duplicates, no gaps."""
    ws = _workspace_of(user)
    for i in range(5):
        _seed(ws, suffix=f"page-{i}", title=f"conversation {i}")

    seen: list[str] = []
    cursor = None
    for _ in range(5):
        params = {"limit": 2}
        if cursor:
            params["cursor"] = cursor
        body = client.get("/conversations", params=params, headers=_hdr(user)).json()
        seen += [i["id"] for i in body["items"]]
        cursor = body["next_cursor"]
        if not cursor:
            break
    assert len(seen) == 5
    assert len(set(seen)) == 5


@requires_db
def test_has_state_is_true_while_the_checkpoint_survives(user):
    """The distinction the History tab badges: the transcript is durable, the agent's memory of
    it is not."""
    from calypr_api import threads

    ws = _workspace_of(user)
    _seed(ws, suffix="alive", title="remembered")
    with SessionLocal() as s:
        s.execute(
            text(
                "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type,"
                " checkpoint, metadata) VALUES (:t, '', :c, 'test', '{}'::jsonb, '{}'::jsonb)"
            ),
            {"t": threads.workspace_thread(ws, "alive"), "c": str(uuid.uuid4())},
        )
        s.commit()

    items = client.get("/conversations", headers=_hdr(user)).json()["items"]
    assert [i["has_state"] for i in items if i["title"] == "remembered"] == [True]


# --------------------------------------------------------------------------- detail + rename


@requires_db
def test_detail_returns_the_transcript_in_order(user):
    ws = _workspace_of(user)
    cid = _seed(ws, suffix="detail", title="a chat")
    body = client.get(f"/conversations/{cid}", headers=_hdr(user)).json()
    assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
    assert body["truncated"] is False
    assert body["message_count"] == 2


@requires_db
def test_rename_sticks(user):
    ws = _workspace_of(user)
    cid = _seed(ws, suffix="rename", title="old name")
    r = client.patch(
        f"/conversations/{cid}", json={"title": "new name"}, headers=_hdr(user)
    )
    assert r.status_code == 200
    assert r.json()["title"] == "new name"
    assert client.get(f"/conversations/{cid}", headers=_hdr(user)).json()["title"] == "new name"


# --------------------------------------------------------------------------- delete


@requires_db
def test_delete_removes_rows_checkpoint_and_blobs(user, monkeypatch):
    from calypr_api import threads

    ws = _workspace_of(user)
    cid = _seed(ws, suffix="doomed", title="delete me", assets=2)
    thread_id = threads.workspace_thread(ws, "doomed")
    with SessionLocal() as s:
        s.execute(
            text(
                "INSERT INTO checkpoints (thread_id, checkpoint_ns, checkpoint_id, type,"
                " checkpoint, metadata) VALUES (:t, '', :c, 'test', '{}'::jsonb, '{}'::jsonb)"
            ),
            {"t": thread_id, "c": str(uuid.uuid4())},
        )
        s.commit()

    deleted: list[list[str]] = []

    async def fake_delete_blob(urls):
        deleted.append(list(urls))

    monkeypatch.setattr(history, "delete_blob", fake_delete_blob)

    r = client.delete(f"/conversations/{cid}", headers=_hdr(user))
    assert r.status_code == 204

    # Both blob objects were asked for.
    assert sum(len(chunk) for chunk in deleted) == 2
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        assert s.get(Conversation, cid) is None
        assert s.query(Message).filter(Message.conversation_id == cid).count() == 0
        assert s.query(Asset).filter(Asset.conversation_id == cid).count() == 0
        left = s.execute(
            text("SELECT count(*) FROM checkpoints WHERE thread_id = :t"), {"t": thread_id}
        ).scalar_one()
        assert left == 0
        # Nothing failed, so nothing is parked.
        assert s.query(OrphanBlob).filter(OrphanBlob.workspace_id == ws).count() == 0


@requires_db
def test_a_blob_failure_parks_the_url_and_still_deletes(user, monkeypatch):
    """A storage provider we don't control must not be able to veto a user deleting their own
    data — but the leak must not be invisible either."""
    from calypr_storage import BlobError

    ws = _workspace_of(user)
    cid = _seed(ws, suffix="blob-fail", title="stubborn", assets=1)

    async def boom(urls):
        raise BlobError("503 from the store")

    monkeypatch.setattr(history, "delete_blob", boom)

    assert client.delete(f"/conversations/{cid}", headers=_hdr(user)).status_code == 204
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        assert s.get(Conversation, cid) is None
        parked = s.query(OrphanBlob).filter(OrphanBlob.workspace_id == ws).all()
        assert len(parked) == 1
        assert "503" in (parked[0].last_error or "")


@requires_db
def test_delete_one_asset(user, monkeypatch):
    ws = _workspace_of(user)
    cid = _seed(ws, suffix="one-asset", title="media", assets=1)

    async def noop(urls):
        return None

    monkeypatch.setattr(history, "delete_blob", noop)
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        aid = s.query(Asset).filter(Asset.conversation_id == cid).one().id

    assert client.delete(f"/assets/{aid}", headers=_hdr(user)).status_code == 204
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        assert s.get(Asset, aid) is None
        # The conversation itself is untouched — deleting a file is not deleting the chat.
        assert s.get(Conversation, cid) is not None


# --------------------------------------------------------------------------- tenancy


@requires_db
def test_another_tenant_gets_404_not_403(user, monkeypatch):
    """A 403 would confirm the row exists to someone who cannot see it."""
    ws = _workspace_of(user)
    cid = _seed(ws, suffix="private", title="not yours")

    other = f"hist-other-{uuid.uuid4().hex[:10]}"
    try:
        assert client.get(f"/conversations/{cid}", headers=_hdr(other)).status_code == 404
        assert client.delete(f"/conversations/{cid}", headers=_hdr(other)).status_code == 404
        assert (
            client.patch(
                f"/conversations/{cid}", json={"title": "hijack"}, headers=_hdr(other)
            ).status_code
            == 404
        )
        # And it does not appear in their list.
        assert client.get("/conversations", headers=_hdr(other)).json()["items"] == []
    finally:
        with SessionLocal() as s:
            s.query(Account).filter(Account.owner_user_id == other).delete(
                synchronize_session=False
            )
            s.commit()


@requires_db
def test_a_bad_id_is_404_not_500(user):
    assert client.get("/conversations/not-a-uuid", headers=_hdr(user)).status_code == 404
    assert client.delete("/assets/not-a-uuid", headers=_hdr(user)).status_code == 404


# --------------------------------------------------------------------------- media list


@requires_db
def test_media_lists_filters_and_searches(user):
    ws = _workspace_of(user)
    _seed(ws, suffix="media-a", title="Foxes", assets=2)
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        s.add(
            Asset(
                workspace_id=ws,
                kind="audio",
                blob_url="https://blob.example/runs/mp3/a.mp3",
                bytes=64,
                caption="a spoken summary",
            )
        )
        s.commit()

    body = client.get("/assets", headers=_hdr(user)).json()
    assert len(body["items"]) == 3
    assert {i["kind"] for i in body["items"]} == {"image", "audio"}

    audio = client.get("/assets", params={"kind": "audio"}, headers=_hdr(user)).json()
    assert [i["caption"] for i in audio["items"]] == ["a spoken summary"]

    found = client.get("/assets", params={"q": "spoken"}, headers=_hdr(user)).json()
    assert len(found["items"]) == 1


# --------------------------------------------------------------------------- project scoping


@requires_db
def test_conversations_scope_to_one_project(user):
    """Switching projects has to switch history with it.

    This list started out unscoped, on the theory that conversations predating a save have no
    `agent_id` and would vanish. In practice that meant every project showed every other
    project's chats, which reads as a bug — so the canvas now always sends a scope, and the
    unsaved case is served by `agent_id=none` rather than by showing everything."""
    from calypr_api.db.models import Agent

    ws = _workspace_of(user)
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        one = Agent(workspace_id=ws, name="Street Photography", graph_spec={})
        two = Agent(workspace_id=ws, name="Invoice Parser", graph_spec={})
        s.add_all([one, two])
        s.commit()
        one_id, two_id = one.id, two.id

    _seed(ws, suffix="p1", title="ansel adams", agent_id=one_id)
    _seed(ws, suffix="p2", title="parse this pdf", agent_id=two_id)
    _seed(ws, suffix="p0", title="scratch chat")  # never saved to a project

    def titles(**params):
        body = client.get("/conversations", params=params, headers=_hdr(user)).json()
        return [i["title"] for i in body["items"]]

    assert titles(agent_id=str(one_id)) == ["ansel adams"]
    assert titles(agent_id=str(two_id)) == ["parse this pdf"]
    # The sentinel: conversations belonging to no project, which a UUID cannot express.
    assert titles(agent_id="none") == ["scratch chat"]
    # Unscoped still returns everything — the API default is unchanged, the canvas just always
    # sends a scope now.
    assert len(titles()) == 3


@requires_db
def test_assets_scope_to_one_project_too(user):
    """Kept symmetrical with conversations so Media can be scoped later without an API change."""
    from calypr_api.db.models import Agent

    ws = _workspace_of(user)
    with SessionLocal() as s:
        set_tenant(s, str(ws))
        agent = Agent(workspace_id=ws, name="Street Photography", graph_spec={})
        s.add(agent)
        s.commit()
        agent_id = agent.id
        s.add_all(
            [
                Asset(
                    workspace_id=ws,
                    agent_id=agent_id,
                    kind="image",
                    blob_url="https://blob.example/runs/png/owned.png",
                    caption="owned by a project",
                ),
                Asset(
                    workspace_id=ws,
                    kind="image",
                    blob_url="https://blob.example/runs/png/loose.png",
                    caption="owned by none",
                ),
            ]
        )
        s.commit()

    def captions(**params):
        body = client.get("/assets", params=params, headers=_hdr(user)).json()
        return [i["caption"] for i in body["items"]]

    assert captions(agent_id=str(agent_id)) == ["owned by a project"]
    assert captions(agent_id="none") == ["owned by none"]
