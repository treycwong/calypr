"""Read and delete Playground conversations and the media their runs generated.

The write side lives in `calypr_api.conversations` (the recorder); this module is everything the
History and Media tabs call. Named `history` rather than `conversations` so there is exactly one
module by that name — a second one would make `from calypr_api import conversations` ambiguous
to a reader even though the import system copes.
Three things here are deliberate and easy to undo by accident:

**Search is `ILIKE`, not full-text.** Every query is already narrowed to one workspace, so the
candidate set is that workspace's messages — hundreds to low thousands. `plainto_tsquery` would
also need `:*` hand-appended to match `invoic` against "invoices", which is the behaviour a
search box actually needs, and a generated `tsvector` forces a language config that is wrong for
any non-English workspace. Revisit around ~50k messages in a single workspace; the upgrade is
`ALTER TABLE message ADD COLUMN tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', text))
STORED` plus a GIN index and a swap of `_ilike` for a `@@` predicate.

**Pagination is keyset, not OFFSET.** Rows land while the user is scrolling; OFFSET would
duplicate or skip them.

**Delete is real, and it crosses three stores that share no transaction.** Blobs go first
(a provider we don't control must never veto a user's delete), then the checkpoint rows and the
database row commit together, with any failed blob url parked in `orphan_blob` in that same
transaction — so the pointer to a still-billing object is never the thing that goes missing.
This is `purge.py`'s reasoning at row granularity; read that module before changing the order.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import datetime

from calypr_storage import BlobError, delete_blob
from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from sqlalchemy import delete as sa_delete
from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from calypr_api import storage_usage, threads
from calypr_api.db.models import Asset, Conversation, Message, OrphanBlob
from calypr_api.deps import Tenant, tenant
from calypr_api.purge import BLOB_CHUNK
from calypr_api.schemas import (
    AssetList,
    AssetOut,
    ConversationDetail,
    ConversationList,
    ConversationRename,
    ConversationSummary,
)

log = logging.getLogger(__name__)

router = APIRouter()

#: Turns returned by `GET /conversations/{id}`. A transcript longer than this is truncated at
#: the *oldest* end — the recent turns are what a user reopening a chat is looking for.
MAX_DETAIL_MESSAGES = 500

#: Characters of the first user turn shown under a History row.
PREVIEW_CHARS = 120

#: `agent_id=none` means "conversations belonging to no project", which a UUID cannot express.
#: A sentinel rather than a separate boolean parameter so there is exactly one way to say what
#: the list is scoped to, and no way to ask for two contradictory scopes at once.
UNASSIGNED = "none"


def _like(q: str) -> str:
    """An `ILIKE` pattern with the user's own wildcards neutralised, so a search for `100%`
    doesn't silently become "anything starting with 100"."""
    escaped = q.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"%{escaped}%"


def _cursor(ts: datetime | None, row_id: uuid.UUID) -> str:
    return f"{ts.isoformat() if ts else ''}|{row_id}"


def _parse_cursor(cursor: str | None) -> tuple[datetime, uuid.UUID] | None:
    """Opaque to the client, and a malformed one is ignored rather than 400'd — a stale cursor
    from a reloaded tab should start the list over, not break it."""
    if not cursor:
        return None
    try:
        raw_ts, raw_id = cursor.split("|", 1)
        return datetime.fromisoformat(raw_ts), uuid.UUID(raw_id)
    except (ValueError, AttributeError):
        return None


def _uuid_or_404(value: str, what: str) -> uuid.UUID:
    try:
        return uuid.UUID(value)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=f"{what} not found") from exc


def _owned_conversation(session: Session, workspace_id: uuid.UUID, cid: str) -> Conversation:
    """A miss is 404, never 403 — a 403 would confirm the row exists to someone who can't see
    it. Same rule as `agents._get_owned`."""
    row = session.get(Conversation, _uuid_or_404(cid, "conversation"))
    if row is None or row.workspace_id != workspace_id:
        raise HTTPException(status_code=404, detail="conversation not found")
    return row


def _threads_with_state(
    session: Session, workspace_id: uuid.UUID, suffixes: list[str]
) -> set[str]:
    """Which of these conversations the agent still remembers.

    One statement for the whole page rather than a query per row. `checkpoints` carries no
    `workspace_id` and no RLS, but every id handed to it here is composed by
    `threads.workspace_thread` from *our* resolved workspace — safety by construction, the same
    argument `storage_usage.measure_account` makes."""
    if not suffixes:
        return set()
    composed = {threads.workspace_thread(workspace_id, s): s for s in suffixes}
    rows = session.execute(
        text("SELECT DISTINCT thread_id FROM checkpoints WHERE thread_id = ANY(:ids)"),
        {"ids": list(composed)},
    )
    return {composed[r[0]] for r in rows if r[0] in composed}


# --------------------------------------------------------------------------- conversations


@router.get("/conversations", response_model=ConversationList, tags=["history"])
def list_conversations(
    q: str = "",
    agent_id: str | None = None,
    limit: int = Query(50, ge=1, le=100),
    cursor: str | None = None,
    t: Tenant = Depends(tenant),
) -> ConversationList:
    """Newest-first, filtered by title *or* message body.

    **`agent_id` scopes the list to one project, and `agent_id=none` to the conversations that
    belong to no project yet.** The canvas always sends one or the other, so switching projects
    switches history with it. This started out unscoped — on the theory that conversations
    predating a save have no `agent_id` and would vanish — but in practice that just meant every
    project showed every other project's chats, which reads as a bug. The unsaved case is served
    by `none` instead, and `ConversationRecorder`'s upsert adopts a conversation into a project
    the first time a run supplies an agent id, so nothing is stranded."""
    stmt = select(Conversation).where(Conversation.workspace_id == t.workspace_id)
    if agent_id == UNASSIGNED:
        stmt = stmt.where(Conversation.agent_id.is_(None))
    elif agent_id:
        stmt = stmt.where(Conversation.agent_id == _uuid_or_404(agent_id, "agent"))
    if q.strip():
        pattern = _like(q.strip())
        stmt = stmt.where(
            Conversation.title.ilike(pattern, escape="\\")
            | select(Message.id)
            .where(Message.conversation_id == Conversation.id)
            .where(Message.text.ilike(pattern, escape="\\"))
            .exists()
        )
    if (seek := _parse_cursor(cursor)) is not None:
        ts, last_id = seek
        # Tuple comparison, so the id breaks ties at equal timestamps instead of a row being
        # skipped or repeated when two conversations share an `updated_at`.
        stmt = stmt.where(
            func.row(Conversation.updated_at, Conversation.id) < func.row(ts, last_id)
        )
    stmt = stmt.order_by(Conversation.updated_at.desc(), Conversation.id.desc()).limit(limit + 1)

    rows = list(t.session.execute(stmt).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    if not rows:
        return ConversationList(items=[], next_cursor=None)

    ids = [r.id for r in rows]
    counts = dict(
        t.session.execute(
            select(Message.conversation_id, func.count())
            .where(Message.conversation_id.in_(ids))
            .group_by(Message.conversation_id)
        ).all()
    )
    previews = dict(
        t.session.execute(
            select(Message.conversation_id, Message.text)
            .where(Message.conversation_id.in_(ids))
            .where(Message.role == "user")
            .where(Message.seq == 0)
        ).all()
    )
    with_state = _threads_with_state(t.session, t.workspace_id, [r.thread_suffix for r in rows])

    return ConversationList(
        items=[
            ConversationSummary(
                id=str(r.id),
                title=r.title,
                thread_id=r.thread_suffix,
                agent_id=str(r.agent_id) if r.agent_id else None,
                message_count=counts.get(r.id, 0),
                has_state=r.thread_suffix in with_state,
                preview=(previews.get(r.id) or "")[:PREVIEW_CHARS],
                created_at=r.created_at,
                updated_at=r.updated_at,
            )
            for r in rows
        ],
        next_cursor=_cursor(rows[-1].updated_at, rows[-1].id) if has_more else None,
    )


@router.get("/conversations/{cid}", response_model=ConversationDetail, tags=["history"])
def get_conversation(cid: str, t: Tenant = Depends(tenant)) -> ConversationDetail:
    row = _owned_conversation(t.session, t.workspace_id, cid)
    total = t.session.execute(
        select(func.count()).select_from(Message).where(Message.conversation_id == row.id)
    ).scalar_one()
    # Keep the *newest* turns when a transcript is over the cap, then restore reading order.
    tail = list(
        t.session.execute(
            select(Message)
            .where(Message.conversation_id == row.id)
            .order_by(Message.seq.desc())
            .limit(MAX_DETAIL_MESSAGES)
        )
        .scalars()
        .all()
    )
    tail.reverse()
    has_state = bool(_threads_with_state(t.session, t.workspace_id, [row.thread_suffix]))
    return ConversationDetail(
        id=str(row.id),
        title=row.title,
        thread_id=row.thread_suffix,
        agent_id=str(row.agent_id) if row.agent_id else None,
        message_count=total,
        has_state=has_state,
        preview=(tail[0].text if tail else "")[:PREVIEW_CHARS],
        created_at=row.created_at,
        updated_at=row.updated_at,
        truncated=total > len(tail),
        messages=[
            {
                "id": str(m.id),
                "role": m.role,
                "text": m.text,
                "images": list(m.images or []),
                "status": m.status,
                "created_at": m.created_at,
            }
            for m in tail
        ],
    )


@router.patch("/conversations/{cid}", response_model=ConversationSummary, tags=["history"])
def rename_conversation(
    cid: str, body: ConversationRename, t: Tenant = Depends(tenant)
) -> ConversationSummary:
    """A rename sticks: `ConversationRecorder` sets `title` only on insert, so the next turn in
    this conversation won't overwrite it."""
    row = _owned_conversation(t.session, t.workspace_id, cid)
    t.session.execute(
        update(Conversation).where(Conversation.id == row.id).values(title=body.title)
    )
    t.session.commit()
    return ConversationSummary(
        id=str(row.id),
        title=body.title,
        thread_id=row.thread_suffix,
        agent_id=str(row.agent_id) if row.agent_id else None,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _delete_blobs(session: Session, workspace_id: uuid.UUID, urls: list[str]) -> None:
    """Delete blob objects in chunks, parking whatever the provider refused.

    Called *before* the database transaction that removes the rows, and the parking rows are
    added to that same transaction — so the two cannot disagree about what still exists. A blob
    failure never blocks the delete: a storage provider we don't control must not be able to veto
    a user removing their own data."""
    for start in range(0, len(urls), BLOB_CHUNK):
        chunk = urls[start : start + BLOB_CHUNK]
        try:
            asyncio.run(delete_blob(chunk))
        except BlobError as exc:
            log.warning("blob delete failed for %d urls; parking them", len(chunk), exc_info=True)
            session.add_all(
                [
                    OrphanBlob(workspace_id=workspace_id, blob_url=u, last_error=str(exc)[:500])
                    for u in chunk
                ]
            )


@router.delete("/conversations/{cid}", status_code=status.HTTP_204_NO_CONTENT, tags=["history"])
def delete_conversation(cid: str, t: Tenant = Depends(tenant)) -> Response:
    """Remove the transcript, the agent's memory of it, and the media it produced.

    The media going too is a direct consequence of `asset.conversation_id ON DELETE CASCADE`,
    and it is why the confirm dialog names the file count — a user deleting a chat should not be
    surprised to find their generated images gone."""
    row = _owned_conversation(t.session, t.workspace_id, cid)
    urls = [
        r[0]
        for r in t.session.execute(
            select(Asset.blob_url).where(Asset.conversation_id == row.id)
        ).all()
    ]
    composed = threads.workspace_thread(t.workspace_id, row.thread_suffix)

    _delete_blobs(t.session, t.workspace_id, urls)
    # One transaction: the checkpoint rows, any parked urls, and the conversation itself.
    # `message` and `asset` cascade.
    storage_usage.delete_threads(t.session, [composed])
    t.session.execute(sa_delete(Conversation).where(Conversation.id == row.id))
    t.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --------------------------------------------------------------------------- media


@router.get("/assets", response_model=AssetList, tags=["history"])
def list_assets(
    q: str = "",
    kind: str | None = None,
    agent_id: str | None = None,
    limit: int = Query(60, ge=1, le=120),
    cursor: str | None = None,
    t: Tenant = Depends(tenant),
) -> AssetList:
    stmt = select(Asset).where(Asset.workspace_id == t.workspace_id)
    if kind:
        stmt = stmt.where(Asset.kind == kind)
    if agent_id == UNASSIGNED:
        stmt = stmt.where(Asset.agent_id.is_(None))
    elif agent_id:
        stmt = stmt.where(Asset.agent_id == _uuid_or_404(agent_id, "agent"))
    if q.strip():
        stmt = stmt.where(Asset.caption.ilike(_like(q.strip()), escape="\\"))
    if (seek := _parse_cursor(cursor)) is not None:
        ts, last_id = seek
        stmt = stmt.where(func.row(Asset.created_at, Asset.id) < func.row(ts, last_id))
    stmt = stmt.order_by(Asset.created_at.desc(), Asset.id.desc()).limit(limit + 1)

    rows = list(t.session.execute(stmt).scalars().all())
    has_more = len(rows) > limit
    rows = rows[:limit]
    return AssetList(
        items=[
            AssetOut(
                id=str(r.id),
                kind=r.kind,
                url=r.blob_url,
                caption=r.caption,
                content_type=r.content_type,
                bytes=r.bytes,
                model=r.model,
                conversation_id=str(r.conversation_id) if r.conversation_id else None,
                created_at=r.created_at,
            )
            for r in rows
        ],
        next_cursor=_cursor(rows[-1].created_at, rows[-1].id) if has_more and rows else None,
    )


@router.delete("/assets/{aid}", status_code=status.HTTP_204_NO_CONTENT, tags=["history"])
def delete_asset(aid: str, t: Tenant = Depends(tenant)) -> Response:
    """One file. Same ordering as a conversation delete, without a thread to collect."""
    row = t.session.get(Asset, _uuid_or_404(aid, "asset"))
    if row is None or row.workspace_id != t.workspace_id:
        raise HTTPException(status_code=404, detail="asset not found")
    _delete_blobs(t.session, t.workspace_id, [row.blob_url])
    t.session.execute(sa_delete(Asset).where(Asset.id == row.id))
    t.session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
