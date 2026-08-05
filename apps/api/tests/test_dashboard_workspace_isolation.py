"""The dashboard remounts its pages when the workspace changes.

Creating a second workspace renamed the sidebar and left the *previous* workspace's projects
listed underneath it — alarming to look at, though never a data leak: `/agents` filters on the
resolved workspace and always did. The staleness was purely client-side. `router.refresh()`,
which the switcher triggers after setting the cookie, re-renders server components but preserves
client state, so the dashboard pages — client components that fetch in a mount effect — kept the
rows they had already loaded.

The fix is a `key` on `<main>` in the dashboard layout, derived from the resolved workspace, so
a switch remounts the subtree and every mount effect runs again.

**Why this is a source assertion rather than a browser test.** Two independent walls: the e2e
suite pins `CALYPR_INTERNAL_KEY=""` (see `e2e/playwright.config.ts`, which explains why), so
every request there resolves to the one shared dev workspace and a real switch cannot happen;
and a React key leaves no trace in the DOM even if it could. So this pins the invariant at the
only place it is observable — the source — following `test_config_panel_coverage.py`, which
reads the canvas panel's TSX for the same reason. Crude, and honest about it: it cannot prove
the remount works, only that the mechanism has not been quietly deleted.
"""

from __future__ import annotations

import re
from pathlib import Path

LAYOUT = Path(__file__).resolve().parents[3] / "apps/web/src/app/dashboard/layout.tsx"


def test_dashboard_layout_keys_main_on_the_resolved_workspace():
    src = LAYOUT.read_text()
    # The key has to come from the workspace the *API* resolved (`is_current`), not from the
    # cookie: a stale or foreign cookie falls back by design, and keying on the claim would
    # remount to a workspace the user is not actually in.
    assert "is_current" in src, "layout no longer reads which workspace resolved"
    main = re.search(r"<main\b[^>]*>", src)
    assert main, "no <main> in the dashboard layout"
    assert "key=" in main.group(0), (
        "<main> lost its key — switching workspaces will leave the previous workspace's "
        "projects on screen (see this module's docstring)"
    )
