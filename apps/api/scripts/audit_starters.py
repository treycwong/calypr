"""Run every first-run starter template as one real account, and report what a newcomer gets.

#109 drops new accounts into a template with first messages to try (`TEMPLATE_STARTERS`). This
runs each of those templates with its **first** suggested message, exactly as a newcomer would on
day one, against the live API, as the account you name, and reports per template:

- **verdict:** OK (answered), ERROR (the run failed), REFUSED (refused before running, e.g. out of
  credits), or EMPTY (finished with no answer and no media).
- **credits** used, read from the account's credit ledger before and after (1 credit = 1,000
  micro-credits), plus the balance left.
- **seconds**, the media produced (`asset` events), any `notice` (e.g. "no MCP server"), and the
  first lines of the answer.

Order matters: text templates run first and paid media last, so a Free account's 100 credits are
spent the way a newcomer trying everything would spend them. Where the credits run out is itself a
finding, so the script doesn't stop there; refusals are recorded too.

    railway run --service calypr-api -- uv run python scripts/audit_starters.py \\
        --user-id <better-auth user id> --label-image /path/to/label.jpg

This makes real, billed runs on that account, and the media templates call paid models (images,
3D, video). `--only` / `--skip` limit what runs, and `--dry-run` lists the plan without running
anything. Needs `CALYPR_INTERNAL_KEY` and `CALYPR_DATABASE_URL` from Railway; neither is printed.
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx
import psycopg
from calypr_compiler.templates import STARTERS, TEMPLATE_STARTERS

DEFAULT_API = "https://calypr-api-production.up.railway.app"
MICRO = 1_000
REPO = Path(__file__).resolve().parents[3]
DEFAULT_ALT_IMAGE = REPO / "apps/web/public/workflows/street-photography.jpg"

#: Paid media last. Everything not listed keeps its catalogue order, ahead of these.
MEDIA_LAST = [
    "tpl-text-to-speech",
    "tpl-translate-speak",
    "tpl-image-generation",
    "tpl-street-photography",
    "tpl-image-to-3d",
    "tpl-text-to-video",
    "tpl-image-to-video",
]
#: Templates that read an attached image, and which test image they get.
NEEDS_IMAGE = {"tpl-alt-text": "alt", "tpl-label-reader": "label"}


@dataclass
class Result:
    template: str
    message: str
    verdict: str = "ERROR"
    reason: str = ""
    credits: float = 0.0
    balance_after: float = 0.0
    seconds: float = 0.0
    nodes: list[str] = field(default_factory=list)
    assets: list[str] = field(default_factory=list)
    notices: list[str] = field(default_factory=list)
    answer: str = ""


def _db():
    url = os.environ["CALYPR_DATABASE_URL"].replace("postgresql+psycopg://", "postgresql://")
    return psycopg.connect(url)


def _account(user_id: str) -> tuple[str, str]:
    with _db() as conn:
        row = conn.execute(
            "SELECT id, plan FROM billing_account WHERE owner_user_id = %s AND deleted_at IS NULL",
            (user_id,),
        ).fetchone()
    if not row:
        sys.exit(f"no account for user {user_id!r} (has it signed in at least once?)")
    return str(row[0]), str(row[1])


def _balance(account_id: str) -> float:
    with _db() as conn:
        micro = conn.execute(
            "SELECT COALESCE(SUM(delta_micro), 0) FROM credit_ledger WHERE account_id = %s",
            (account_id,),
        ).fetchone()[0]
    return float(micro) / MICRO  # SUM() comes back as Decimal, which json can't write


def _data_uri(path: Path) -> str:
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    return f"data:{mime};base64," + base64.b64encode(path.read_bytes()).decode()


def _run(client: httpx.Client, r: Result, graph, images: list[str]) -> None:
    body = {"graph": graph.model_dump(mode="json"), "message": r.message, "images": images}
    tokens: list[str] = []
    final = ""
    started = time.monotonic()
    try:
        with client.stream("POST", "/runs", json=body, timeout=600) as resp:
            if resp.status_code != 200:
                r.reason = f"HTTP {resp.status_code}: {resp.read().decode()[:200]}"
                return
            for line in resp.iter_lines():
                if not line.startswith("data: ") or line == "data: [DONE]":
                    continue
                ev = json.loads(line[6:])
                kind = ev.get("type")
                if kind == "token":
                    tokens.append(ev.get("text", ""))
                elif kind == "node" and ev.get("phase") == "start":
                    r.nodes.append(ev.get("node_id", "?"))
                elif kind == "asset":
                    r.assets.append(str(ev.get("kind", "?")))
                elif kind == "notice":
                    r.notices.append(ev.get("message", ""))
                elif kind == "final":
                    out = ev.get("output")
                    final = out if isinstance(out, str) else json.dumps(out)
                elif kind == "error":
                    msg = ev.get("message", "")
                    r.verdict = "REFUSED" if ev.get("code") else "ERROR"
                    r.reason = f"{ev.get('code') or 'error'}: {msg}"
                    return
    except httpx.HTTPError as exc:
        r.reason = f"transport: {exc!r}"[:200]
        return
    finally:
        r.seconds = round(time.monotonic() - started, 1)
    r.answer = ("".join(tokens) or final).strip()
    r.verdict = "OK" if (r.answer or r.assets) else "EMPTY"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    ap.add_argument("--user-id", required=True, help="Better Auth user id of the account to use")
    ap.add_argument("--api", default=os.environ.get("SMOKE_API_URL", DEFAULT_API))
    ap.add_argument("--alt-image", type=Path, default=DEFAULT_ALT_IMAGE)
    ap.add_argument("--label-image", type=Path, help="photo of a food label (label reader)")
    ap.add_argument("--only", nargs="*", default=[], help="template ids to run (default: all)")
    ap.add_argument("--skip", nargs="*", default=[], help="template ids to leave out")
    ap.add_argument("--dry-run", action="store_true", help="list the plan, run nothing")
    ap.add_argument("--json", type=Path, help="also write the full results here")
    args = ap.parse_args()

    by_id = {g.id: g for g in STARTERS}
    order = [t for t in TEMPLATE_STARTERS if t not in MEDIA_LAST] + [
        t for t in MEDIA_LAST if t in TEMPLATE_STARTERS
    ]
    order = [t for t in order if (not args.only or t in args.only) and t not in args.skip]
    images = {"alt": args.alt_image, "label": args.label_image}

    if args.dry_run:
        for t in order:
            print(f"{t:<24} {TEMPLATE_STARTERS[t][0]!r}")
        return

    account_id, plan = _account(args.user_id)
    headers = {
        "x-calypr-internal-key": os.environ["CALYPR_INTERNAL_KEY"],
        "x-calypr-user-id": args.user_id,
    }
    start_balance = _balance(account_id)
    print(f"plan={plan} start balance={start_balance:.2f} credits, {len(order)} templates\n")

    results: list[Result] = []
    with httpx.Client(base_url=args.api, headers=headers) as client:
        for t in order:
            r = Result(template=t, message=TEMPLATE_STARTERS[t][0])
            need = NEEDS_IMAGE.get(t)
            path = images.get(need) if need else None
            if need and (path is None or not path.exists()):
                r.verdict, r.reason = "SKIP", f"needs --{need}-image"
                results.append(r)
                continue
            before = _balance(account_id)
            _run(client, r, by_id[t].model_copy(deep=True), [_data_uri(path)] if path else [])
            time.sleep(1.5)  # let the debit land
            r.balance_after = _balance(account_id)
            r.credits = round(before - r.balance_after, 3)
            results.append(r)
            print(
                f"{r.verdict:<7} {t:<24} {r.credits:>8.3f} cr  {r.seconds:>5.1f}s  "
                f"assets={','.join(r.assets) or '-'}  {r.reason}"
            )
            for n in r.notices:
                print(f"        notice: {n[:180]}")
            if r.answer:
                print("        answer: " + r.answer[:220].replace("\n", " "))

    spent = sum(r.credits for r in results)
    end = _balance(account_id)
    print(f"\nspent {spent:.2f} credits; balance {end:.2f} (started {start_balance:.2f})")
    if args.json:
        rows = [r.__dict__ for r in results]
        args.json.write_text(json.dumps(rows, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
