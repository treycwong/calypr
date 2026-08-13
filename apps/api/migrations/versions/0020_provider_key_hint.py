"""store the last 4 characters of a BYO provider key, so the UI can say *which* key is on file

Revision ID: 0020_provider_key_hint
Revises: 0019_conversations_and_assets
Create Date: 2026-08-13

`provider_key.key_encrypted` is Fernet ciphertext that is decrypted only at run time and has
never been returned to a client — `ProviderKeySet` is documented write-only and an e2e test
asserts a stored key is never echoed back. That property is worth keeping, but it left the
Settings panel able to say only "a key exists", which is not enough to answer the question people
actually have in front of it: *is the key on file the one I think it is?* Rotating a key meant
overwriting blind and hoping.

Four trailing characters is the standard answer (Stripe, AWS and GitHub all show exactly this).
They are not a secret: every provider's keys share a long fixed prefix and the entropy is in the
middle, so a 4-character suffix identifies a key you already hold without materially helping
anyone who doesn't. It is stored in the clear precisely so that showing it never requires
decrypting the real value — the hint and the secret travel separately, and the read path for the
hint cannot be turned into a read path for the key.

**Nullable, and NULL means "saved before this migration".** There is no way to backfill it: the
plaintext isn't recoverable without the Fernet key, and doing it at run time would mean decrypting
every stored key during a schema migration. Rows saved before today therefore show as a keyless
hint until the key is next replaced, and the UI renders that as plain "key on file" — the same
thing it said yesterday.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0020_provider_key_hint"
down_revision: str | None = "0019_conversations_and_assets"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("provider_key", sa.Column("key_hint", sa.String(), nullable=True))
    # No index: the only reader is the per-workspace list, which already fetches whole rows.


def downgrade() -> None:
    """Safe to run — it drops a display hint, not a credential. Every key keeps working."""
    op.drop_column("provider_key", "key_hint")
