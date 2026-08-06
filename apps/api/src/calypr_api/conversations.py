"""Best-effort transcript + generated-media persistence for the Playground.

`ConversationRecorder` is `metering.RunRecorder`'s sibling and copies its contract deliberately:
its own session, scoped to the tenant, **every failure degrades to a silent no-op**, and the DB
is touched exactly twice — once at `start` (conversation upsert + the user's turn) and once at
`finish`/`fail` (the assistant's turn + any assets). Nothing happens per streamed token.

**Why not fold this into `RunRecorder`.** That class deliberately writes its usage rows and the
credit debit in one transaction, because "a run that was metered but not charged is free usage,
and one charged without a usage row is unexplainable." Adding a transcript to that transaction
would let an oversized message payload roll back a credit debit. Separate session, separate
failure domain; the two-round-trip discipline holds per recorder.

**Only the Playground records.** `share.py` does not: anonymous visitors have no identity to
attribute a transcript to, and the workspace owner finding strangers' messages in their History
tab is a privacy surprise, not a feature — their threads live under `share:<token>:`, a
namespace with no workspace binding by construction. `assist.py` does not either: it is a
different surface with its own message model and no thread, and mixing "draft me a graph" turns
into "Playground chat history" would make the tab lie. Neither omission is an oversight.

Note for anyone reading a suspiciously busy History tab locally: without `CALYPR_INTERNAL_KEY`,
`deps.py` resolves every caller to the shared dev workspace, so all local and CI runs write into
one conversation list. Metering has always behaved this way; this is just the first surface that
makes it visible.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert

from calypr_api.db.models import Asset, Conversation, Message
from calypr_api.db.session import SessionLocal, set_tenant

log = logging.getLogger("calypr_api")

#: Hard ceiling on a single stored assistant turn. The transcript write is best-effort and must
#: never be the thing that fails, so a runaway agent has to hit a wall well before it produces a
#: row large enough to matter. Truncation is marked in the text rather than done silently.
MAX_MESSAGE_CHARS = 200_000

_TRUNCATED = "\n\n…[truncated]"

#: How much of the first user message becomes the conversation's title in the list.
TITLE_CHARS = 60


def title_from(text: str) -> str:
    """A one-line label for the History list. Collapses whitespace so a pasted multi-line prompt
    doesn't turn into a ragged title, and ellipsises rather than hard-cutting."""
    flat = " ".join(text.split())
    if len(flat) <= TITLE_CHARS:
        return flat
    return flat[: TITLE_CHARS - 1].rstrip() + "…"


class ConversationRecorder:
    """A handle to one in-flight turn's transcript. Construct via `start`; if that fails the
    returned recorder is *disabled* and every method is a silent no-op."""

    def __init__(
        self,
        session,
        conversation_id,
        workspace_id,
        *,
        run_id: uuid.UUID | None = None,
        agent_id: uuid.UUID | None = None,
    ) -> None:
        self._session = session
        self._conversation_id = conversation_id
        self._workspace_id = workspace_id
        self._run_id = run_id
        self._agent_id = agent_id
        self._chunks: list[str] = []
        self._chars = 0
        self._truncated = False
        self._assets: list[dict[str, Any]] = []
        self._enabled = session is not None

    @classmethod
    def _disabled(cls) -> ConversationRecorder:
        return cls(session=None, conversation_id=None, workspace_id=None)

    @property
    def conversation_id(self) -> uuid.UUID | None:
        """The row this turn belongs to — `None` when disabled. `runs.py` streams it to the
        client so the History tab can highlight the active conversation without a fetch."""
        return self._conversation_id

    @classmethod
    def start(
        cls,
        workspace_id: uuid.UUID,
        *,
        thread_suffix: str,
        user_text: str,
        images: list[str] | None = None,
        agent_id: uuid.UUID | None = None,
        run_id: uuid.UUID | None = None,
    ) -> ConversationRecorder:
        """Upsert the conversation and append the user's turn, in one transaction. Any failure
        ⇒ a disabled (no-op) recorder — never raises.

        The upsert is what makes this idempotent per turn: `uq_conversation_thread` turns a
        resumed suffix into an `updated_at` bump instead of a second conversation. `title` is set
        only on insert, so a rename the user made survives their next message.
        """
        session = None
        try:
            session = SessionLocal()
            set_tenant(session, str(workspace_id))
            stmt = pg_insert(Conversation).values(
                workspace_id=workspace_id,
                agent_id=agent_id,
                thread_suffix=thread_suffix,
                title=title_from(user_text),
            )
            convo_id = session.execute(
                stmt.on_conflict_do_update(
                    constraint="uq_conversation_thread",
                    set_={
                        "updated_at": func.now(),
                        # A conversation started before the canvas was saved has no agent; adopt
                        # one the first time a run supplies it, but never overwrite it with null.
                        "agent_id": func.coalesce(
                            stmt.excluded.agent_id, Conversation.agent_id
                        ),
                    },
                ).returning(Conversation.id)
            ).scalar_one()
            session.execute(
                pg_insert(Message).values(
                    conversation_id=convo_id,
                    workspace_id=workspace_id,
                    run_id=run_id,
                    role="user",
                    seq=_next_seq(convo_id),
                    text=user_text,
                    images=images or [],
                )
            )
            session.commit()
            return cls(
                session=session,
                conversation_id=convo_id,
                workspace_id=workspace_id,
                run_id=run_id,
                agent_id=agent_id,
            )
        except Exception:
            log.warning("conversation history disabled: could not start turn", exc_info=True)
            if session is not None:
                session.close()
            return cls._disabled()

    def add_token(self, text: str) -> None:
        """Buffer streamed text (in memory, no DB). Stops accumulating past `MAX_MESSAGE_CHARS`
        and marks the stored turn as truncated."""
        if not self._enabled or self._truncated or not text:
            return
        room = MAX_MESSAGE_CHARS - self._chars
        if len(text) >= room:
            self._chunks.append(text[:room])
            self._chars = MAX_MESSAGE_CHARS
            self._truncated = True
            return
        self._chunks.append(text)
        self._chars += len(text)

    def add_asset(self, payload: dict[str, Any]) -> None:
        """Buffer one generated-media event. Mirrors `RunRecorder.add_usage`."""
        if self._enabled:
            self._assets.append(payload)

    def finish(self, status: str = "complete") -> None:
        """`complete` for a run that reached its `final` event, `partial` for one the user
        stopped mid-answer — the text they watched arrive is kept either way."""
        self._flush(status)

    def fail(self) -> None:
        self._flush("errored")

    def _flush(self, status: str) -> None:
        """Write the assistant turn and any assets, then close. Swallows all errors after one
        warning — the stream already reached the user, so this must not raise."""
        if not self._enabled:
            return
        self._enabled = False  # one-shot; guards a fail-after-finish double flush
        try:
            text = "".join(self._chunks)
            if self._truncated:
                text += _TRUNCATED
            # An assistant turn with no text *and* no media is not an empty bubble worth storing.
            # The transcript then shows the user's message with no answer, which is what happened.
            if text or self._assets:
                self._session.execute(
                    pg_insert(Message).values(
                        conversation_id=self._conversation_id,
                        workspace_id=self._workspace_id,
                        run_id=self._run_id,
                        role="assistant",
                        seq=_next_seq(self._conversation_id),
                        text=text,
                        status=status,
                    )
                )
            if self._assets:
                self._session.add_all(
                    [
                        Asset(
                            workspace_id=self._workspace_id,
                            conversation_id=self._conversation_id,
                            run_id=self._run_id,
                            agent_id=self._agent_id,
                            node_id=a.get("node_id"),
                            kind=str(a.get("kind") or "image"),
                            blob_url=str(a["url"]),
                            pathname=a.get("pathname"),
                            content_type=a.get("content_type"),
                            bytes=int(a.get("bytes") or 0),
                            caption=str(a.get("caption") or ""),
                            model=a.get("model"),
                        )
                        for a in self._assets
                        # `url` is the one field with no sane default: a row without it can
                        # neither be rendered nor deleted from blob storage.
                        if a.get("url")
                    ]
                )
            self._session.execute(
                update(Conversation)
                .where(Conversation.id == self._conversation_id)
                .values(updated_at=func.now())
            )
            self._session.commit()
        except Exception:
            log.warning("conversation history: flush failed", exc_info=True)
        finally:
            if self._session is not None:
                self._session.close()


def _next_seq(conversation_id):
    """Ordering within a conversation, as a scalar subquery so the INSERT stays one statement.
    `created_at` alone would tie: a user turn and its assistant reply can land in the same
    millisecond on a short run."""
    return (
        select(func.coalesce(func.max(Message.seq) + 1, 0))
        .where(Message.conversation_id == conversation_id)
        .scalar_subquery()
    )
