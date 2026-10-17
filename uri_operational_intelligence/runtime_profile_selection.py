"""Brain resource-profile selection for the integrated worker (RUNTIME-PROFILES-INTEG; beyond the URI-RUNTIME-VRAM-R1
accepted scope, reviewed separately).

The worker verifies the Brain it talks to against an exact expected argv (`runtime_v1.expected_argv`). With only the
frozen config it treats a Brain host started on a resource profile as FOREIGN_INSTANCE (ARGV_MISMATCH), and the app
never sees a ready Brain. This module lets the worker verify against the SAME derived profile config the host was
started with, read from one explicit selection file next to the host report:

    <client root>/control/oi/brain_profile.json
    {"schema": "uri.runtime.profile_selection.v1", "ctx": 65536, "vision": "gpu", "mtp": false}

Rules:
  * absent file = the frozen config, exactly as before (default unchanged);
  * only a combination with a measured request (`runtime_profiles.MEASURED_MIB`) is accepted; the argv is derived
    locally from the frozen config, so the file can only select another measured launch shape of the same pinned
    binary and model, never a different binary, model, port or flag;
  * an invalid or unreadable file keeps the frozen config and is reported (`error`), never guessed;
  * the file is read once at worker start, before the worker's file guard is installed.
"""
from __future__ import annotations

import json
from pathlib import Path

from . import runtime_profiles as RP

SCHEMA = "uri.runtime.profile_selection.v1"
SELECTION_FILE = "brain_profile.json"


def selection_path(client_root) -> Path:
    return Path(client_root) / "control" / "oi" / SELECTION_FILE


def select(frozen_cfg: dict, path) -> tuple:
    """(cfg, note). cfg is the frozen config object itself unless a valid selection names a measured profile."""
    p = Path(path)
    if not p.exists():
        return frozen_cfg, {"source": "frozen", "file": None}
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return frozen_cfg, {"source": "frozen", "file": str(p), "error": "PROFILE_SELECTION_UNREADABLE"}
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return frozen_cfg, {"source": "frozen", "file": str(p), "error": "PROFILE_SELECTION_SCHEMA"}
    ctx, vision, mtp = data.get("ctx"), data.get("vision"), data.get("mtp")
    if not isinstance(ctx, int) or isinstance(ctx, bool) or not isinstance(vision, str) or not isinstance(mtp, bool):
        return frozen_cfg, {"source": "frozen", "file": str(p), "error": "PROFILE_SELECTION_INVALID"}
    try:
        cfg = RP.derive_config(frozen_cfg, ctx, vision, mtp)
    except RP.ProfileError as exc:
        return frozen_cfg, {"source": "frozen", "file": str(p), "error": exc.code}
    return cfg, {"source": "selection", "file": str(p), "profile": RP.describe(cfg)}


def write(client_root, ctx: int, vision: str, mtp: bool) -> Path:
    """Write a selection (development/launcher use). Validates first, so an invalid selection is never written."""
    RP.required_mib(RP.key_for(ctx, vision, mtp))
    p = selection_path(client_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"schema": SCHEMA, "ctx": int(ctx), "vision": vision, "mtp": bool(mtp)}), encoding="utf-8")
    tmp.replace(p)
    return p
