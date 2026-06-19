"""Emit the canonical JSON Schema for the DSL.

Pydantic is the source of truth. This writes a stable, sorted JSON Schema; a Node step
(`scripts/gen-ts.mjs`) turns it into TypeScript. Run via `pnpm --filter @calypr/dsl gen`.

Output path defaults to `ts/schema/graphspec.schema.json` relative to the current working
directory (the pnpm script runs this from `packages/dsl`). Override with
`CALYPR_DSL_SCHEMA_OUT`.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from calypr_dsl.spec import GraphSpec

DEFAULT_OUT = "ts/schema/graphspec.schema.json"


def _strip_property_titles(schema: dict[str, Any]) -> dict[str, Any]:
    """Drop Pydantic's per-field `title`s so the TS generator inlines primitives.

    Model-level titles (root + each `$defs` entry) are kept — they name the generated
    interfaces. Only property-level titles, which otherwise produce noisy alias types
    like `Id1`/`Type1`, are removed.
    """
    models = [schema, *schema.get("$defs", {}).values()]
    for model in models:
        for prop in model.get("properties", {}).values():
            prop.pop("title", None)
    return schema


def main() -> None:
    out = Path(os.environ.get("CALYPR_DSL_SCHEMA_OUT", DEFAULT_OUT))
    out.parent.mkdir(parents=True, exist_ok=True)
    schema = _strip_property_titles(GraphSpec.model_json_schema())
    # Stable, deterministic output so the drift check is meaningful.
    out.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"wrote {out.resolve()}")


if __name__ == "__main__":
    main()
