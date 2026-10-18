"""Brain quick controls (BRAIN-QUICK-CONTROLS): the user's Vision / Context / Speed choice as a Runtime v1 profile.

The resource profiles themselves are URI-RUNTIME-VRAM-R1's (`runtime_profiles`): measured, derived in memory from
the frozen configuration, never written into `local_brain.json`. This module adds only:

  * OFFERED: the subset of measured profiles the quick controls offer. Vision has priority over MTP (owner,
    2026-10-17/18): Vision On is always MTP off; MTP ("speed boost") is offered only with Vision off at 16K / 32K,
    the measured MTP profiles that fit. Measured profiles that were demoted at load (128K + MTP) or that leave no
    margin with vision (128K + vision) are not offered.
  * the choice file `brain_profile.json` (`uri.oi.brain_profile.v1`) in the client's control/oi directory: written
    by the worker after validation, read by the Brain host at start and on a `reconfigure` request;
  * `ProfileStatus`: readiness of the live server checked against the ACTIVE profile's derived config (exact argv,
    n_ctx, artifacts) and against its live modalities, so Vision is never shown on unless the server has it.

Thinking is not a profile: it is the per-turn `depth` (reasoning_policy), no reload.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path

from . import runtime_profiles as RP
from . import runtime_v1 as R

SCHEMA = "uri.oi.brain_profile.v1"
CHOICE_FILE = "brain_profile.json"

# (ctx, vision, mtp) keys the controls may select. Every key must be in RP.MEASURED_MIB (tested).
OFFERED = (
    (32768, "gpu", False), (65536, "gpu", False),
    (16384, "off", False), (32768, "off", False), (65536, "off", False), (131072, "off", False),
    (16384, "off", True), (32768, "off", True),
)
# Owner decision BQC-D1 (asked 2026-10-18; development default = the recommended option): 32K, Vision on, MTP off.
DEFAULT_KEY = (32768, "gpu", False)
# Free device memory on the owner's desktop when the R1 profiles were measured (URI UI + Chrome open, 2026-10-17).
# Only used to label an option "tight"; admission is the host's live fit check with the measured request.
REFERENCE_FREE_MIB = 15072
TIGHT_MARGIN_MIB = 512
SWITCH_COST_S = 30          # measured: real host restart 29.1 s to READY (R1 section 8), before the re-prefill


class ChoiceError(ValueError):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code, self.detail = code, detail


def key_from_controls(vision: bool, context: int, speed: bool = False) -> tuple:
    """Quick-control values -> profile key. Vision wins over MTP: speed is ignored (never silently set) with
    vision on; such a request is refused, so the UI never shows a speed boost that is not running."""
    if not isinstance(vision, bool) or not isinstance(speed, bool) or isinstance(context, bool):
        raise ChoiceError("CONTROL_INVALID")
    if vision and speed:
        raise ChoiceError("SPEED_NEEDS_VISION_OFF")
    key = (int(context), "gpu" if vision else "off", bool(speed))
    if key not in OFFERED:
        raise ChoiceError("PROFILE_NOT_OFFERED", RP.profile_id(key) if context in RP.CONTEXTS else context)
    return key


def controls(key) -> dict:
    ctx, vision, mtp = key
    return {"vision": vision != "off", "context": ctx, "speed": bool(mtp)}


def offer() -> dict:
    """What the controls may show: each option with its measured request and whether it is tight."""
    rows = []
    for key in OFFERED:
        req = RP.required_mib(key)
        margin = REFERENCE_FREE_MIB - req
        rows.append({"id": RP.profile_id(key), **controls(key), "required_mib": req,
                     "margin_mib": margin, "tight": margin < TIGHT_MARGIN_MIB})
    return {"schema": SCHEMA, "options": rows, "default": controls(DEFAULT_KEY), "switch_cost_s": SWITCH_COST_S,
            "reference_free_mib": REFERENCE_FREE_MIB, "measured_by": "URI-RUNTIME-VRAM-R1 (2026-10-17)"}


# ---- choice file -------------------------------------------------------------------------------------------------
def _validate(doc) -> tuple:
    if not isinstance(doc, dict) or doc.get("schema") != SCHEMA:
        raise ChoiceError("CHOICE_SCHEMA")
    try:
        key = (int(doc["ctx"]), str(doc["vision"]), doc["mtp"])
    except (KeyError, TypeError, ValueError):
        raise ChoiceError("CHOICE_SCHEMA") from None
    if not isinstance(key[2], bool) or key not in OFFERED:
        raise ChoiceError("PROFILE_NOT_OFFERED")
    return key


def read_choice(directory) -> tuple:
    """(key, source, error). No file -> the default. An unreadable or invalid file -> the default, with the error
    reported (the host and the UI show it; nothing is guessed from a damaged file)."""
    path = Path(directory) / CHOICE_FILE
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return DEFAULT_KEY, "default", None
    except (OSError, ValueError):
        return DEFAULT_KEY, "default", "CHOICE_UNREADABLE"
    try:
        return _validate(doc), "user", None
    except ChoiceError as exc:
        return DEFAULT_KEY, "default", exc.code


def write_choice(directory, key) -> dict:
    if key not in OFFERED:
        raise ChoiceError("PROFILE_NOT_OFFERED")
    ctx, vision, mtp = key
    doc = {"schema": SCHEMA, "ctx": ctx, "vision": vision, "mtp": mtp, "id": RP.profile_id(key),
           "set_at": round(time.time(), 3)}
    path = Path(directory) / CHOICE_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(doc), encoding="utf-8")
    os.replace(tmp, path)
    return doc


def config_for(frozen_cfg, key) -> dict:
    """The config a key runs with (derive_config: measured profiles only; the frozen key returns the frozen object)."""
    return RP.derive_config(frozen_cfg, *key)


def key_of_described(desc) -> tuple | None:
    """Profile key from a host report's `profile` (RP.describe). None when it is missing or not a measured key."""
    if not isinstance(desc, dict):
        return None
    try:
        key = (int(desc["ctx"]), str(desc["vision"]), bool(desc["mtp"]))
    except (KeyError, TypeError, ValueError):
        return None
    return key if key in RP.MEASURED_MIB else None


# ---- readiness against the active profile ------------------------------------------------------------------------
class ProfileStatus:
    """Callable -> Readiness of the live server, checked against the active profile.

    The active profile is the one the live Brain host reports. Without a live host it is the persisted choice (the
    profile the host will start). One RuntimeManager per profile (read-only `status()`; this never starts anything)."""

    def __init__(self, frozen_cfg, state_dir, host_report, choice_dir, manager_factory=None):
        self.frozen, self.state_dir = frozen_cfg, state_dir
        self._host_report, self.choice_dir = host_report, choice_dir
        self._factory = manager_factory or (lambda cfg: R.RuntimeManager(cfg, state_dir=state_dir))
        self._managers = {}

    def active_key(self) -> tuple | None:
        rep, alive = self._host_report() if self._host_report else (None, False)
        if alive and rep is not None:
            return key_of_described(rep.get("profile"))     # None = unknown profile: UNAVAILABLE
        return read_choice(self.choice_dir)[0]

    def active_cfg(self, key=False):
        key = self.active_key() if key is False else key
        if key is None:
            return None
        try:
            return config_for(self.frozen, key)
        except RP.ProfileError:
            return None

    def __call__(self):
        key = self.active_key()          # read once: the config and the manager cache follow the same profile (R1-02)
        cfg = self.active_cfg(key)
        if cfg is None:
            return R.Readiness(R.IDENTITY_MISMATCH, R.base_url(self.frozen), model_id=self.frozen["model"]["id"],
                               detail="PROFILE_UNKNOWN")
        pid = RP.profile_id(key)
        mgr = self._managers.get(pid)
        if mgr is None:
            mgr = self._managers[pid] = self._factory(cfg)
        r = mgr.status()
        if r.state == R.READY:
            problem = modality_problem(cfg, (r.live_identity or {}).get("server") or {})
            if problem:
                r.state, r.detail = R.IDENTITY_MISMATCH, problem
        return r


def modality_problem(cfg, probe) -> str | None:
    """The live server's vision modality must match the profile. Unknown modalities are not a match for vision on."""
    want = bool(cfg["runtime"].get("vision_enabled"))
    mods = probe.get("modalities")
    have = bool(mods.get("vision")) if isinstance(mods, dict) else None
    if want and have is not True:
        return "VISION_NOT_LIVE"
    if not want and have is True:
        return "VISION_UNEXPECTED"
    return None
