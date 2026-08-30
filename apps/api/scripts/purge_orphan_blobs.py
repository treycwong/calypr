"""Delete blobs the database has no record of.

The app records every file it stores in `asset` (generated media) or `upload` (images a user
attached). Anything else in the store is unreachable: nothing lists it, nothing links to it,
nothing will ever delete it — and it counts against the store's quota for as long as it exists.

They come from before migration `0019` introduced the `asset` table, and from any path that
uploaded without recording a row. TODO.md has carried "the orphan sweep for pre-0019 objects" as
an open item since; this is it.

**Dry run by default.** Deleting a blob is irreversible and there is no undo, so `--apply` is
required to act. Run it without first and read the summary.

    railway run --service calypr-api -- uv run python scripts/purge_orphan_blobs.py
    railway run --service calypr-api -- uv run python scripts/purge_orphan_blobs.py --apply

The keep-set is built from the *database*, never from a pattern on the pathname. A rule like
"keep anything under runs/" would silently protect orphans and, worse, would delete a real asset
the day someone changes the prefix. If a row references it, it stays.
"""

from __future__ import annotations

import argparse
import asyncio
import os

import psycopg
from calypr_storage import delete_blob, list_blobs

#: Tables whose rows point at a blob that must survive. `orphan_blob` and `account_purge` are
#: deliberately absent — those hold urls already queued for deletion, so a sweep that spared them
#: would be undoing the other half of the system.
_REFERENCING = (("asset", "blob_url"), ("upload", "blob_url"))


def _referenced_urls() -> set[str]:
    url = os.environ["CALYPR_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    keep: set[str] = set()
    with psycopg.connect(url) as conn:
        for table, column in _REFERENCING:
            rows = conn.execute(f"SELECT {column} FROM {table} WHERE {column} IS NOT NULL")
            keep.update(r[0] for r in rows.fetchall())
    return keep


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--apply", action="store_true", help="actually delete (default: dry run)")
    ap.add_argument("--limit", type=int, default=0, help="delete at most N (0 = no cap)")
    args = ap.parse_args()

    keep = _referenced_urls()
    blobs = await list_blobs()
    orphans = [b for b in blobs if b.get("url") not in keep]

    def size(bs: list[dict]) -> int:
        return sum(int(b.get("size") or 0) for b in bs)

    print(f"in store    {len(blobs):>6} objects")
    print(f"referenced  {len(keep):>6}  ({', '.join(t for t, _ in _REFERENCING)})")
    print(f"orphaned    {len(orphans):>6}  {size(orphans) / 1048576:.1f} MB")

    if not orphans:
        return
    # Sliced *before* the totals below, so a capped run reports what it actually deleted
    # rather than what it found.
    if args.limit:
        orphans = orphans[: args.limit]
    if not args.apply:
        print("\ndry run — nothing deleted. Re-run with --apply.")
        for b in orphans[:5]:
            print(f"  would delete  {b.get('pathname')}")
        if len(orphans) > 5:
            print(f"  … and {len(orphans) - 5} more")
        return

    await delete_blob([b["url"] for b in orphans])
    print(f"\ndeleted {len(orphans)} objects, freeing {size(orphans) / 1048576:.1f} MB")


if __name__ == "__main__":
    asyncio.run(main())
