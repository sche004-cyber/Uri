"""Brain Quick Controls (BRAIN-QC-20261018): which Thinking / Vision / Context choices URI offers, and which it refuses.

This module owns no runtime behaviour. It is the single, reviewed list of resource profiles a user may switch to from
the controls under the chat box, with the evidence that qualifies each one. The worker uses it to build the controls'
state and to refuse a request; the Brain host uses it to refuse a reconfigure request a second time (the host is the
authority: a request that names anything outside this list is ignored, whoever wrote it).

  * Thinking is per turn (reasoning_policy depth): Off = fast, On = normal (768-token budget), Auto = policy. No
    reload. It is not a profile.
  * Vision and Context are load-time parameters (llama.cpp b11425 cannot unload only the projector): a change is a
    controlled Brain host reconfigure (stop, VRAM release wait, start on the derived config, calibration). The
    conversation history lives in the worker and survives the switch (runtime-profiles CONTEXT-1, sw4).
  * Only QUALIFIED profiles are switchable. A measured but unqualified profile is listed with the reason it is not
    offered, so the UI can show it disabled instead of hiding why. Unmeasured combinations do not exist here.

Qualification sources (runtime-profiles candidate, docs/operational_intelligence/profiles_live/
RUNTIME_PROFILES_LIVE_RESULTS.md section 2; subagent-reviewed, not driver-accepted):
  * Standard = the frozen Runtime v1 (32K, vision on the GPU, MTP draft): the verified default and fallback.
  * Long context = P2 64K main only (13,658 MiB): UI V2 journeys 68/68 + 12/12, soak 60 min, switch sw4 PASS.
  * Standard, draft off = P3 32K + GPU vision, MTP off (14,360 MiB, about 1.2 GB less than Standard): journeys 68/68
    + 12/12, soak 60 min, Assist 3/3, switch sw5/sw6 PASS. Switchable (owner closure decision D2/D3 2026-10-18,
    which replaces the earlier "never offer P3" coordinator note): the Draft chip chooses between Standard and this
    profile. Vision stays on either way.
  * 64K + vision = P1 (14,764 MiB): UNQUALIFIED (CRASH-1 and DEMOTE-P1 open). Listed, never switchable.
"""
from __future__ import annotations

from . import runtime_profiles as RP

SCHEMA = "uri.brain.quick_controls.v1"
EVIDENCE = "docs/operational_intelligence/profiles_live/RUNTIME_PROFILES_LIVE_RESULTS.md"

# Catalog order is the resolution preference: the first qualified entry that matches a requested (context, vision)
# wins. Standard (frozen) therefore stays the choice for 32K + vision.
CATALOG = (
    {"id": "standard", "key": RP.FROZEN_KEY, "label": "Standard",
     "summary": "32K context, vision on (the default Runtime v1)", "qualified": True,
     "evidence": "Runtime v1 freeze record (frozen 2026-10-07); verified default and fallback"},
    {"id": "long", "key": (65536, "off", False), "label": "Long context",
     "summary": "64K context, vision off", "qualified": True,
     "evidence": EVIDENCE + " section 2, P2: journeys 68/68 + 12/12, soak 60 min, switch sw4"},
    {"id": "standard-nodraft", "key": (32768, "gpu", False), "label": "Standard, draft off",
     "summary": "32K context, vision on, no speculative draft (about 1.2 GB less GPU memory)", "qualified": True,
     "evidence": EVIDENCE + " section 2, P3: journeys 68/68 + 12/12, soak 60 min, Assist 3/3, switch sw5/sw6"},
    {"id": "long-vision", "key": (65536, "gpu", False), "label": "Long context with vision",
     "summary": "64K context, vision on", "qualified": False,
     "reason": "Not qualified yet: in tests it crashed once and slowed to a fifth of its speed next to a browser "
               "(findings CRASH-1, DEMOTE-P1).",
     "evidence": EVIDENCE + " section 2, P1: FAIL"},
)
VISION_ON = ("gpu", "cpu")


class QuickControlError(ValueError):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code, self.detail = code, detail


def _key(entry):
    return tuple(entry["key"])


def entry_by_id(profile_id):
    for e in CATALOG:
        if e["id"] == profile_id:
            return e
    return None


def entry_by_key(key):
    key = tuple(key)
    for e in CATALOG:
        if _key(e) == key:
            return e
    return None


def key_of(desc: dict) -> tuple:
    """(ctx, vision, mtp) of a `runtime_profiles.describe()` result."""
    return (int(desc["ctx"]), str(desc["vision"]), bool(desc["mtp"]))


def switch_target(profile) -> tuple:
    """Validate a reconfigure target (`{"ctx", "vision", "mtp"}` or a catalog id). Returns the profile key, or raises
    QuickControlError. Used by the worker AND by the Brain host: only a qualified catalog entry is ever a target."""
    if isinstance(profile, str):
        entry = entry_by_id(profile)
    elif isinstance(profile, dict):
        ctx, vision, mtp = profile.get("ctx"), profile.get("vision"), profile.get("mtp")
        if (not isinstance(ctx, int) or isinstance(ctx, bool) or not isinstance(vision, str)
                or not isinstance(mtp, bool)):
            raise QuickControlError("PROFILE_INVALID")
        entry = entry_by_key((ctx, vision, mtp))
    else:
        raise QuickControlError("PROFILE_INVALID")
    if entry is None:
        raise QuickControlError("PROFILE_UNKNOWN")
    if not entry["qualified"]:
        raise QuickControlError("PROFILE_NOT_QUALIFIED", entry.get("reason"))
    if not entry.get("switchable", True):
        raise QuickControlError("PROFILE_NOT_OFFERED")
    key = _key(entry)
    RP.required_mib(key)                 # measured, or ProfileError: admission never runs on an estimate
    return key


def target_dict(key) -> dict:
    return {"ctx": int(key[0]), "vision": key[1], "mtp": bool(key[2])}


def _view(entry, active_key=None):
    key = _key(entry)
    out = {"id": entry["id"], "label": entry["label"], "summary": entry["summary"], "ctx": key[0],
           "vision": key[1], "vision_on": key[1] in VISION_ON, "mtp": key[2], "qualified": entry["qualified"],
           "switchable": bool(entry["qualified"] and entry.get("switchable", True)),
           "required_mib": RP.MEASURED_MIB.get(key), "evidence": entry["evidence"],
           "active": active_key is not None and tuple(active_key) == key}
    if entry.get("reason"):
        out["reason"] = entry["reason"]
    return out


def describe_key(key) -> dict:
    """A view of any measured profile, including one outside the catalog (e.g. a harness-started profile)."""
    e = entry_by_key(key)
    if e is not None:
        return _view(e, key)
    return {"id": RP.profile_id(key), "label": "Custom profile", "summary": "%dK context, vision %s"
            % (key[0] // 1024, "on" if key[1] in VISION_ON else "off"), "ctx": key[0], "vision": key[1],
            "vision_on": key[1] in VISION_ON, "mtp": key[2], "qualified": False, "active": True,
            "required_mib": RP.MEASURED_MIB.get(tuple(key)),
            "reason": "Started outside the Quick Controls (not a qualified choice).", "evidence": None}


SERVING_STATES = ("READY", "BUSY", "DEGRADED")


def mismatch(configured_key, host_profile, host_selection_error=None, host_alive=True):
    """Closure D3: the host, the worker and the persisted selection must never disagree silently. None when they
    agree (or no host report is available); otherwise what each side runs and why, for the UI to show."""
    if not host_alive:
        return None
    try:
        hkey = key_of(host_profile) if host_profile else RP.FROZEN_KEY
    except (KeyError, TypeError, ValueError):
        return {"code": "HOST_PROFILE_UNREADABLE", "host": "an unreadable setting", "host_id": None,
                "worker": describe_key(configured_key)["label"], "worker_id": RP.profile_id(configured_key),
                "host_qualified": False, "selection_error": host_selection_error}
    if hkey == tuple(configured_key):
        if not host_selection_error:
            return None
        # Review QCC-R1-05: both run the same profile, but the host could not record its selection file.
        return {"code": "HOST_SELECTION_ERROR", "host": describe_key(hkey)["label"], "host_id": RP.profile_id(hkey),
                "worker": describe_key(configured_key)["label"], "worker_id": RP.profile_id(configured_key),
                "host_qualified": bool((entry_by_key(hkey) or {}).get("qualified")),
                "selection_error": host_selection_error}
    return {"code": host_selection_error or "HOST_WORKER_PROFILE_MISMATCH",
            "host": describe_key(hkey)["label"], "host_id": RP.profile_id(hkey),
            "worker": describe_key(configured_key)["label"], "worker_id": RP.profile_id(configured_key),
            "host_qualified": bool((entry_by_key(hkey) or {}).get("qualified")),
            "selection_error": host_selection_error}


def controls(cfg: dict, health_state, *, host_profile=None, switch=None, can_switch=True,
             cannot_switch_reason=None, host_selection_error=None, host_alive=None, assist=None) -> dict:
    """The controls' state for the UI. `active` is set only when the worker's own readiness check verified the
    running server against `cfg` (health READY / BUSY / DEGRADED): never before the runtime confirms.
    `assist` = {"asking": bool, "granted": bool} from the worker's Assist commands (closure D2/D6): while a grant is
    active, vision stays on (`vision_locked`)."""
    configured = RP.describe(cfg)
    ckey = key_of(configured)
    serving = health_state in SERVING_STATES and not (switch or {}).get("pending")
    if host_profile and serving:
        try:
            serving = key_of(host_profile) == ckey
        except (KeyError, TypeError, ValueError):
            serving = False
    return {"schema": SCHEMA,
            "active": describe_key(ckey) if serving else None,
            "configured": configured,
            "host_profile": host_profile,
            "switch": switch or {"pending": False},
            "options": [_view(e, ckey if serving else None) for e in CATALOG],
            "thinking": {"off": RP.thinking_depth(False), "on": RP.thinking_depth(True), "auto": "auto",
                         "reload": False},
            "can_switch": bool(can_switch), "cannot_switch_reason": cannot_switch_reason,
            # A switch in progress is a known, shown transition (the "Switching to" chip), not a disagreement.
            "mismatch": None if (switch or {}).get("pending") else mismatch(
                ckey, host_profile, host_selection_error,
                host_alive if host_alive is not None else host_profile is not None),
            "assist": dict(assist) if assist else None,
            "vision_locked": bool(assist and assist.get("granted"))}
