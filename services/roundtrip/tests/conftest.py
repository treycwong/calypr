"""Make the sibling helper modules (`_equivalence`, `mutations`) importable from the test
modules. The repo runs pytest with `--import-mode=importlib`, which does not put a test file's
own directory on `sys.path`."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
