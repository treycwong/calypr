"""Binding a conversation thread to the tenant that owns it.

LangGraph resumes state by `thread_id` and asks no questions: hand the checkpointer a thread id
and it loads that conversation. So the id **is** the authorization token for the conversation,
and until now it was chosen by the browser (`web-${Math.random()…}`) and passed straight through.
Anyone who named another caller's thread resumed their state — verified end to end, both parties'
messages landing in one thread. Not easy to hit (you had to guess ~57 bits of `Math.random`), but
the only thing standing in the way was that guess. There was no check.

The fix is to stop treating the client's value as an identity and start treating it as a *suffix*
inside a namespace the server controls:

    ws:<workspace_id>:<suffix>      authenticated runs — the prefix is the tenant
    share:<token>:<suffix>          share links — the prefix is the link

The prefix is always server-supplied and always first, so a suffix can extend a thread id but
never re-address it into someone else's namespace.

For **authenticated** runs that is the whole fix: the workspace comes from the resolved tenant, so
the worst a caller can do is collide with themselves. For **share** links there is no identity to
bind to — every visitor is anonymous on the same public token — so the server mints the suffix
instead of accepting one, from `secrets`. 128 unguessable bits is what separates two strangers on
the same link, rather than 57 bits of a non-cryptographic PRNG the caller picked.

The prefix is also what makes storage attributable. `checkpoint_blobs` has no `workspace_id` and
never will (LangGraph owns the table), so the only alternative was joining `run.thread_id` — and
`run` rows are written best-effort, so a metering failure left real bytes belonging to nobody. A
prefix match needs no join and catches those orphans. See `storage_usage.measure_account`.
"""

from __future__ import annotations

import re
import secrets
import uuid

#: Conservative on purpose. The suffix is client-supplied on the authenticated path, and it ends
#: up inside an id we later match on by prefix — so keep it to characters that can't be confused
#: with the `:` separator or with SQL `LIKE` metacharacters.
_SUFFIX_OK = re.compile(r"[^A-Za-z0-9_-]")
_MAX_SUFFIX = 64

WORKSPACE_PREFIX = "ws"
SHARE_PREFIX = "share"


def _clean(suffix: str | None) -> str:
    """A safe conversation suffix, or a fresh one when the caller didn't supply a usable value."""
    if not suffix:
        return uuid.uuid4().hex
    cleaned = _SUFFIX_OK.sub("", suffix)[:_MAX_SUFFIX]
    # An all-punctuation suffix would collapse to "" and make every such caller share one thread.
    return cleaned or uuid.uuid4().hex


def workspace_thread(workspace_id: uuid.UUID | str, suffix: str | None) -> str:
    """The thread id for an authenticated run.

    The workspace comes from the resolved tenant, never from the request body, so this is what
    makes resuming another tenant's conversation structurally impossible rather than merely
    unlikely."""
    return f"{WORKSPACE_PREFIX}:{workspace_id}:{_clean(suffix)}"


def share_thread(token: str, suffix: str | None) -> str:
    """The thread id for an anonymous share-link visitor.

    Unlike `workspace_thread` this deliberately ignores a client-supplied suffix that isn't one we
    minted — see `new_share_suffix`."""
    return f"{SHARE_PREFIX}:{token}:{_clean(suffix)}"


def new_share_suffix() -> str:
    """A fresh, unguessable conversation id for an anonymous visitor.

    `secrets`, not `uuid4()` or the browser's `Math.random`: on a public share link this value is
    the *only* thing separating two strangers' conversations, so it has to be a credential rather
    than a convenience."""
    return secrets.token_urlsafe(16)


def workspace_prefix(workspace_id: uuid.UUID | str) -> str:
    """The `LIKE` prefix matching every thread belonging to this workspace."""
    return f"{WORKSPACE_PREFIX}:{workspace_id}:"


def share_prefix(token: str) -> str:
    """The `LIKE` prefix matching every thread belonging to this share link.

    The sibling of `workspace_prefix`, and account deletion is what needs it: a share link's
    conversations hang off the *token*, not off any workspace, so deleting an account has to
    name them separately or they survive as unreachable checkpoint rows."""
    return f"{SHARE_PREFIX}:{token}:"
