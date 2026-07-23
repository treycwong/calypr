"""Best-effort run metering (WEEK2 plan §B2).

`RunRecorder` turns the usage events a run streams into durable `run` + `run_usage` rows.
Its one hard rule: **persistence must never break or delay the hot path.** Every DB touch is
wrapped so that a failure (Postgres down, RLS reject, bad payload) logs one warning and
degrades to a no-op — the stream has already been delivered to the user regardless.

Usage is buffered in memory and written only twice: one INSERT at `start`, one flush at
`finish`/`fail`. So a run costs at most two round-trips, both off the event loop (callers use
`asyncio.to_thread`), and none per streamed token.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

from sqlalchemy import func, update

from calypr_api import credits
from calypr_api.db.models import Run, RunUsage
from calypr_api.db.session import SessionLocal, set_tenant
from calypr_api.pricing import platform_cost_usd, platform_credits_for

log = logging.getLogger("calypr_api")


class RunRecorder:
    """A handle to one in-flight run's metering. Construct via `start`; if that fails the
    returned recorder is *disabled* and every method is a silent no-op."""

    def __init__(self, session, run_id, workspace_id, source: str = "run") -> None:
        self._session = session
        self._run_id = run_id
        self._workspace_id = workspace_id
        # Carried so the credit debit can say where the spend came from (`run|assist|share`),
        # which is what makes a ledger line explainable to the customer who's reading it.
        self._source = source
        self._usage: list[dict[str, Any]] = []
        self._enabled = session is not None

    @classmethod
    def _disabled(cls) -> RunRecorder:
        return cls(session=None, run_id=None, workspace_id=None)

    @classmethod
    def start(
        cls,
        workspace_id: uuid.UUID,
        *,
        source: str,
        agent_id: uuid.UUID | None = None,
        thread_id: str | None = None,
    ) -> RunRecorder:
        """Open a dedicated session, scope it to the tenant, INSERT the `run` row, and return
        a live recorder. Any failure ⇒ a disabled (no-op) recorder — never raises."""
        session = None
        try:
            session = SessionLocal()
            set_tenant(session, str(workspace_id))
            run = Run(
                workspace_id=workspace_id,
                agent_id=agent_id,
                thread_id=thread_id,
                source=source,
                status="running",
            )
            session.add(run)
            session.commit()
            run_id = run.id
            return cls(
                session=session, run_id=run_id, workspace_id=workspace_id, source=source
            )
        except Exception:
            log.warning("run metering disabled: could not start run", exc_info=True)
            if session is not None:
                session.close()
            return cls._disabled()

    def add_usage(self, payload: dict[str, Any]) -> None:
        """Buffer one usage event (in memory, no DB). Safe to call on a disabled recorder."""
        if self._enabled:
            self._usage.append(payload)

    def finish(self, status: str = "completed") -> None:
        self._flush(status)

    def fail(self) -> None:
        self._flush("errored")

    def _flush(self, status: str) -> None:
        """Write buffered usage + run totals, then close. Swallows all errors after one
        warning — the stream already completed, so metering must not raise."""
        if not self._enabled:
            return
        self._enabled = False  # flush is one-shot; guard against a fail-after-finish double
        try:
            total_in = total_out = 0
            total_cost = 0.0
            total_credits = 0.0
            rows: list[RunUsage] = []
            for u in self._usage:
                in_tok = int(u.get("input_tokens") or 0)
                out_tok = int(u.get("output_tokens") or 0)
                model = u.get("model")
                rows.append(
                    RunUsage(
                        run_id=self._run_id,
                        workspace_id=self._workspace_id,
                        node_id=u.get("node_id"),
                        model=model,
                        input_tokens=in_tok,
                        output_tokens=out_tok,
                    )
                )
                total_in += in_tok
                total_out += out_tok
                # Platform COGS, not provider list price: BYO-key frontier models add $0
                # (model_access) so they can't trip the platform spend cap.
                total_cost += platform_cost_usd(model or "", in_tok, out_tok)
                # Credits follow the same rule for the same reason: a model running on the
                # workspace's own key is billed to them by the provider, so charging credits
                # for it too would be charging twice. `platform_credits_for` returns 0 there.
                total_credits += platform_credits_for(model or "", in_tok, out_tok)
            if rows:
                self._session.add_all(rows)
            self._session.execute(
                update(Run)
                .where(Run.id == self._run_id)
                .values(
                    status=status,
                    input_tokens=total_in,
                    output_tokens=total_out,
                    cost_usd=total_cost,
                    finished_at=func.now(),
                )
            )
            # Debit in the *same* transaction as the usage rows: a run that was metered but not
            # charged is free usage, and one charged without a usage row is unexplainable to the
            # customer. They land together or not at all.
            if total_credits > 0:
                credits.debit_run(
                    self._session,
                    self._workspace_id,
                    total_credits,
                    source=self._source,
                    ref_id=str(self._run_id),
                )
            self._session.commit()
        except Exception:
            log.warning("run metering: flush failed", exc_info=True)
        finally:
            if self._session is not None:
                self._session.close()
