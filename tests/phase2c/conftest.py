"""Phase 2C fixtures: reuse the Phase 2B synthetic authority and the REAL paired stack (fake executor).

Everything here is SYNTHETIC at the executor level; the native-executor evidence lives in
evidence/phase2c/*.json produced by scripts/phase2c_native_qualification.py (not a pytest run).
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from phase2b.conftest import authority, bridge, bridge_stack  # noqa: E402,F401  (re-exported fixtures)
