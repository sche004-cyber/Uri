"""Phase 2 operational qualification fixtures: the Phase 2 UI/operations stack (real paired server, real client,
real supervisor, FIXTURE_ONLY fake harness) plus the helpers of tests/phase2ops."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from phase2ops.conftest import TEXT, begin, stack, wait_terminal  # noqa: E402,F401
