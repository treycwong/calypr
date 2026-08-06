"""ConversationRecorder: the durable Playground transcript.

Two tiers, mirroring `test_metering.py`:
- **DB-less** (always run): the recorder self-disables when Postgres is unreachable and every
  method stays a no-op, because a transcript write must never break a run that already streamed.
- **DB-backed** (skipped without Postgres, run in CI): the rows, the upsert on a resumed thread,
  and the statuses a stopped or errored run leaves behind.
"""

from __future__ import annotations

import uuid

import pytest
from calypr_api import conversations
from calypr_api.constants import DEV_WORKSPACE_ID
from calypr_api.conversations import MAX_MESSAGE_CHARS, ConversationRecorder, title_from
from calypr_api.db.models import Asset, Conversation, Message
from calypr_api.db.session import SessionLocal, engine, set_tenant
from sqlalchemy import text


def _db_available() -> bool:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


requires_db = pytest.mark.skipif(not _db_available(), reason="no database")


def _boom() -> None:
    raise RuntimeError("db down")


def _turns(session, convo_id) -> list[Message]:
    return (
        session.query(Message)
        .filter(Message.conversation_id == convo_id)
        .order_by(Message.seq)
        .all()
    )


# --------------------------------------------------------------------------- DB-less


def test_recorder_disables_and_is_noop_when_db_down(monkeypatch):
    """start.sh's DB-less promise, extended to history: no database, no crash, no history."""
    monkeypatch.setattr(conversations, "SessionLocal", _boom)
    rec = ConversationRecorder.start(
        uuid.UUID(DEV_WORKSPACE_ID), thread_suffix="web-abc", user_text="hi"
    )
    assert rec._enabled is False
    assert rec.conversation_id is None
    # Every method a safe no-op — nothing escapes onto the hot path.
    rec.add_token("some text")
    rec.add_asset({"url": "https://blob.example/x.png"})
    rec.finish("complete")
    rec.fail()


def test_token_buffer_caps_and_marks_truncation():
    """The only thing between a runaway agent and a multi-MB row on a best-effort write path."""
    rec = ConversationRecorder(session=object(), conversation_id=uuid.uuid4(), workspace_id=None)
    rec.add_token("a" * (MAX_MESSAGE_CHARS - 5))
    rec.add_token("b" * 50)
    assert rec._chars == MAX_MESSAGE_CHARS
    assert rec._truncated is True
    # Further tokens are dropped rather than growing the buffer.
    rec.add_token("c" * 1000)
    assert rec._chars == MAX_MESSAGE_CHARS
    assert "".join(rec._chunks).endswith("b" * 5)


def test_title_collapses_whitespace_and_ellipsises():
    assert title_from("  hello \n  world  ") == "hello world"
    long = "generate " * 40
    out = title_from(long)
    assert len(out) <= conversations.TITLE_CHARS
    assert out.endswith("…")


# --------------------------------------------------------------------------- DB-backed


@requires_db
def test_a_normal_turn_writes_a_conversation_and_two_messages(tenant_factory):
    t = tenant_factory()
    rec = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-normal", user_text="Draw me a fox"
    )
    assert rec.conversation_id is not None
    rec.add_token("Here ")
    rec.add_token("you go.")
    rec.finish("complete")

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        convo = s.get(Conversation, rec.conversation_id)
        assert convo.title == "Draw me a fox"
        assert convo.agent_id is None
        turns = _turns(s, convo.id)
        assert [(m.role, m.text) for m in turns] == [
            ("user", "Draw me a fox"),
            ("assistant", "Here you go."),
        ]
        assert [m.seq for m in turns] == [0, 1]
        assert turns[1].status == "complete"


@requires_db
def test_resuming_a_thread_appends_instead_of_duplicating(tenant_factory):
    """`uq_conversation_thread` is what makes the per-turn write an upsert. Without it every
    message would start a new conversation and History would be a list of one-liners."""
    t = tenant_factory()
    first = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-resume", user_text="first question"
    )
    first.add_token("first answer")
    first.finish("complete")

    second = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-resume", user_text="second question"
    )
    assert second.conversation_id == first.conversation_id
    second.add_token("second answer")
    second.finish("complete")

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        assert s.query(Conversation).filter(
            Conversation.workspace_id == t.workspace_id
        ).count() == 1
        turns = _turns(s, first.conversation_id)
        assert [m.seq for m in turns] == [0, 1, 2, 3]
        # The title came from the *first* message and a later turn must not rewrite it.
        assert s.get(Conversation, first.conversation_id).title == "first question"


@requires_db
def test_a_stopped_run_keeps_what_streamed_as_partial(tenant_factory):
    """Closing the panel mid-answer saves the tokens the user watched arrive. Dropping them
    silently would be the worse failure — `runs.py`'s CancelledError arm is what calls this."""
    t = tenant_factory()
    rec = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-stopped", user_text="long one"
    )
    rec.add_token("I was halfway through")
    rec.finish("partial")

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        turns = _turns(s, rec.conversation_id)
        assert turns[1].status == "partial"
        assert turns[1].text == "I was halfway through"


@requires_db
def test_an_errored_run_keeps_the_partial_as_errored(tenant_factory):
    t = tenant_factory()
    rec = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-errored", user_text="boom"
    )
    rec.add_token("partial output")
    rec.fail()

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        assert _turns(s, rec.conversation_id)[1].status == "errored"


@requires_db
def test_an_empty_assistant_turn_writes_no_row(tenant_factory):
    """No text and no media is not an empty bubble worth storing. The transcript then shows the
    user's message with no answer, which is exactly what happened."""
    t = tenant_factory()
    rec = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-empty", user_text="hello?"
    )
    rec.fail()

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        turns = _turns(s, rec.conversation_id)
        assert [m.role for m in turns] == ["user"]


@requires_db
def test_assets_are_recorded_against_the_conversation(tenant_factory):
    t = tenant_factory()
    rec = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-media", user_text="draw a fox"
    )
    rec.add_asset(
        {
            "kind": "image",
            "url": "https://blob.example/runs/png/abc.png",
            "pathname": "runs/png/abc.png",
            "content_type": "image/png",
            "bytes": 4096,
            "caption": "a fox",
            "model": "gpt-image-2",
            "node_id": "pic",
        }
    )
    # A payload with no url is unusable — it can neither render nor be deleted from blob storage.
    rec.add_asset({"kind": "image", "caption": "dropped"})
    rec.finish("complete")

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        rows = s.query(Asset).filter(Asset.conversation_id == rec.conversation_id).all()
        assert len(rows) == 1
        assert rows[0].blob_url == "https://blob.example/runs/png/abc.png"
        assert rows[0].bytes == 4096
        assert rows[0].caption == "a fox"
        assert rows[0].kind == "image"
        # Media alone is enough to justify an assistant turn even with no text.
        assert [m.role for m in _turns(s, rec.conversation_id)] == ["user", "assistant"]


@requires_db
def test_flush_is_one_shot(tenant_factory):
    """A fail-after-finish double flush must not write a second assistant turn."""
    t = tenant_factory()
    rec = ConversationRecorder.start(
        t.workspace_id, thread_suffix="web-oneshot", user_text="hi"
    )
    rec.add_token("bye")
    rec.finish("complete")
    rec.fail()

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        assert len(_turns(s, rec.conversation_id)) == 2


@requires_db
def test_a_stream_closed_mid_answer_still_records_the_partial(tenant_factory, monkeypatch):
    """The Stop button, end to end through `runs.py`'s event stream.

    The recorder's own `finish("partial")` is covered above; what this pins is that the *route*
    reaches it when the client goes away. It nearly didn't: `CancelledError` and `GeneratorExit`
    are both `BaseException`, so the route's `except Exception` arm saw neither and a stopped run
    left the transcript unwritten and the session open. Closing the generator is the closest
    faithful stand-in for a browser disconnect that a test can stage."""
    import asyncio as aio

    from calypr_api.config import settings
    from calypr_api.routers import runs as runs_mod
    from calypr_api.schemas import RunRequest
    from calypr_compiler.golden import input_agent_output

    monkeypatch.setattr(settings, "internal_key", "")
    t = tenant_factory()
    suffix = f"stopped-{uuid.uuid4().hex[:8]}"

    async def _slow_stream(*a, **k):
        """Two tokens, then a hang — so the close lands mid-answer, not after it."""
        from calypr_runtime.events import RunEvent

        yield RunEvent(type="token", text="half an ")
        yield RunEvent(type="token", text="answer")
        await aio.sleep(30)

    monkeypatch.setattr(runs_mod, "run_stream", _slow_stream)

    async def _drive() -> None:
        response = await runs_mod.create_run(
            RunRequest(
                graph=input_agent_output(model="fake"),
                message="write me something long",
                thread_id=suffix,
            ),
            workspace_id=t.workspace_id,
        )
        agen = response.body_iterator
        seen = ""
        async for chunk in agen:
            seen += chunk
            if "answer" in seen:
                break  # the user hits Stop
        # Closing throws GeneratorExit in at the yield — the disconnect path.
        await agen.aclose()

    aio.run(_drive())

    with SessionLocal() as s:
        set_tenant(s, str(t.workspace_id))
        convo = (
            s.query(Conversation)
            .filter(Conversation.workspace_id == t.workspace_id)
            .filter(Conversation.thread_suffix == suffix)
            .one()
        )
        turns = _turns(s, convo.id)
    assert [m.role for m in turns] == ["user", "assistant"]
    # What the user watched arrive is kept, and labelled honestly.
    assert turns[1].text == "half an answer"
    assert turns[1].status == "partial"
