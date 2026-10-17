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
  * the file is read at worker start (before the file guard) and then re-read by `ProfileFollower` on every
    readiness check (content comparison), so a profile switch is a Brain host restart only: the worker process, and with it the
    answer-channel conversation history it keeps in memory, survives the switch (live finding CONTEXT-1);
  * the file lives in the client's own control directory (the worker guard's state root): anything that can write
    there can change the selection, effective at the next readiness check. Impact is bounded to the measured
    profiles, and the host must have been started on the same profile, or the worker reports FOREIGN_INSTANCE
    (fails closed). No product code writes the file; the launcher/harness does (reviewer finding R1-07).
"""
from __future__ import annotations

import json
import threading
from pathlib import Path

from . import runtime_profiles as RP
from . import runtime_v1 as R

SCHEMA = "uri.runtime.profile_selection.v1"
SELECTION_FILE = "brain_profile.json"


def selection_path(client_root) -> Path:
    return Path(client_root) / "control" / "oi" / SELECTION_FILE


def _read(path: Path):
    """The file's bytes, or None when it does not exist (or cannot be opened)."""
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError:
        return b""                       # exists but unreadable: reported as PROFILE_SELECTION_UNREADABLE


def select_bytes(frozen_cfg: dict, raw, path) -> tuple:
    """(cfg, note) from the file's bytes as read once (no second read: no time-of-check/time-of-use gap)."""
    if raw is None:
        return frozen_cfg, {"source": "frozen", "file": None}
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError):
        return frozen_cfg, {"source": "frozen", "file": str(path), "error": "PROFILE_SELECTION_UNREADABLE"}
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        return frozen_cfg, {"source": "frozen", "file": str(path), "error": "PROFILE_SELECTION_SCHEMA"}
    ctx, vision, mtp = data.get("ctx"), data.get("vision"), data.get("mtp")
    if not isinstance(ctx, int) or isinstance(ctx, bool) or not isinstance(vision, str) or not isinstance(mtp, bool):
        return frozen_cfg, {"source": "frozen", "file": str(path), "error": "PROFILE_SELECTION_INVALID"}
    try:
        cfg = RP.derive_config(frozen_cfg, ctx, vision, mtp)
    except RP.ProfileError as exc:
        return frozen_cfg, {"source": "frozen", "file": str(path), "error": exc.code}
    return cfg, {"source": "selection", "file": str(path), "profile": RP.describe(cfg)}


def select(frozen_cfg: dict, path) -> tuple:
    """(cfg, note). cfg is the frozen config object itself unless a valid selection names a measured profile."""
    p = Path(path)
    return select_bytes(frozen_cfg, _read(p), p)


def write(client_root, ctx: int, vision: str, mtp: bool) -> Path:
    """Write a selection (development/launcher use). Validates first, so an invalid selection is never written."""
    RP.required_mib(RP.key_for(ctx, vision, mtp))
    p = selection_path(client_root)
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps({"schema": SCHEMA, "ctx": int(ctx), "vision": vision, "mtp": bool(mtp)}), encoding="utf-8")
    tmp.replace(p)
    return p


class ProfileFollower:
    """The worker's Runtime v1 readiness, following the selection file.

    `status()` re-reads the (tiny) selection file and compares its bytes. When the selection names a
    different derived config, a new readiness manager is made for it (`make_manager(cfg)`) and `on_change(cfg, note)`
    is called. The previous manager is dropped: the worker never owns the Brain server (the host does), so nothing is
    stopped. The same validation as `select()` applies; an invalid file means the frozen config."""

    def __init__(self, frozen_cfg: dict, path, make_manager, on_change=None):
        self.frozen, self.path, self._make, self._on_change = frozen_cfg, Path(path), make_manager, on_change
        self._lock = threading.Lock()
        # Change detection by content (review R2-06): the file is a few dozen bytes, so it is read on every check.
        # A rewrite of equal size within one timestamp tick is still seen; the bytes read are the bytes validated.
        self._raw = _read(self.path)
        self.cfg, self.note = select_bytes(frozen_cfg, self._raw, self.path)
        self.manager = make_manager(self.cfg)
        self.generation = 0
        self.changes = []

    def refresh(self) -> bool:
        """True when the active config changed."""
        with self._lock:
            raw = _read(self.path)
            if raw == self._raw:
                return False
            self._raw = raw
            cfg, note = select_bytes(self.frozen, raw, self.path)
            self.note = note
            if R.config_digest(cfg) == R.config_digest(self.cfg):
                return False
            before = RP.describe(self.cfg)["id"]
            self.cfg, self.manager = cfg, self._make(cfg)
            self.generation += 1
            self.changes = (self.changes + [{"generation": self.generation, "from": before,
                                             "to": RP.describe(cfg)["id"], "note": note}])[-16:]
            # Delivered under the lock (review R2-05): consumers see changes in order, never a stale profile last.
            if self._on_change is not None:
                self._on_change(cfg, note)
        return True

    def status(self):
        self.refresh()
        return self.manager.status()
