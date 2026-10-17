"""Resource-aware Runtime v1 profiles (URI-RUNTIME-VRAM-R1 candidate; NOT qualified, NOT the default).

The frozen Runtime v1 configuration (`model_lab/integration/local_brain.json`) is never edited. A profile is a
derived, in-memory copy of it that changes only allocation-level launch parameters:

  * context length `-c` (16K / 32K / 64K / 128K);
  * vision projector placement: off (`--no-mmproj`), GPU (frozen), CPU (`--no-mmproj-offload`);
  * MTP draft on (frozen) or off (the draft arguments and the draft artifact are dropped).

Model, quantization, binary, KV cache type, batch sizes and checkpoint flags stay frozen. The frozen combination
(32K, vision GPU, MTP on) returns the frozen configuration object unchanged, so its argv, artifact list and config
digest stay byte-identical (verified fallback).

Each profile carries its MEASURED device request (`required_mib`, sum of llama-server's own Vulkan0 buffer lines, URI-
RUNTIME-VRAM-R1 evidence). The GPU lease fit check uses it instead of the frozen 15,626 MiB. A combination without a
measured request cannot be selected: admission never runs on an estimate.

What needs a reload and what does not (llama.cpp b11425, verified): thinking on/off and the thinking budget are
per-request parameters (no reload). Context length, vision placement and MTP are load-time parameters; b11425 has no
endpoint that unloads only the projector or only the draft, so any change is a server restart (~20-28 s load from
NVMe). The conversation history is kept by URI; the KV cache is rebuilt (or restored, see `slot_restore`).
"""
from __future__ import annotations

import copy

from . import runtime_v1 as R

SCHEMA = "uri.runtime.profiles.v1"
CONTEXTS = (16384, 32768, 65536, 131072)
VISION = ("off", "gpu", "cpu")
FROZEN_KEY = (32768, "gpu", True)
MTP_ARGS = ("-md", "--spec-type", "--spec-draft-n-max", "-otd")   # flags that take one value each

# Measured device request (MiB) per (ctx, vision, mtp). Source: research/runtime_vram_r1/evidence/probe/*/probe.json
# ("buffers.device_total_mib"). Filled only from COMPLETED_WITH_RESULT probes; a missing key is NOT_MEASURED.
# Vision on the CPU adds no device memory (projector and its compute buffer are host buffers).
# The lease fit check applies these per start, so a profile larger than what the desktop leaves (e.g. 128K + MTP,
# 16,107 MiB: demoted at load on 2026-10-17, decode 22-30 tok/s) waits as GPU_CONTENDED instead of starting slow.
MEASURED_MIB: dict = {
    (32768, "gpu", True): 15626,     # frozen; lease constant (R1), re-measured 15,620.5 on 2026-10-17
    (16384, "off", False): 13052,
    (32768, "off", False): 13254,
    (65536, "off", False): 13658,
    (131072, "off", False): 14466,
    (16384, "off", True): 14265,
    (32768, "off", True): 14515,
    (65536, "off", True): 15043,
    (131072, "off", True): 16107,
    (32768, "gpu", False): 14360,
    (65536, "gpu", False): 14764,
    (131072, "gpu", False): 15572,
    (65536, "cpu", True): 15043,
}


class ProfileError(ValueError):
    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code, self.detail = code, detail


def key_for(ctx: int, vision: str, mtp: bool) -> tuple:
    if ctx not in CONTEXTS:
        raise ProfileError("CONTEXT_UNSUPPORTED", ctx)
    if vision not in VISION:
        raise ProfileError("VISION_MODE_UNKNOWN", vision)
    return (int(ctx), vision, bool(mtp))


def profile_id(key) -> str:
    ctx, vision, mtp = key
    return "frozen" if key == FROZEN_KEY else f"c{ctx // 1024}k-vis{vision}-mtp{'on' if mtp else 'off'}"


def required_mib(key, measured=None) -> int:
    table = MEASURED_MIB if measured is None else measured
    if key not in table:
        raise ProfileError("PROFILE_NOT_MEASURED", profile_id(key))
    return int(table[key])


def _strip_mtp(args):
    out, i = [], 0
    while i < len(args):
        if args[i] in MTP_ARGS:
            i += 2
            continue
        out.append(args[i])
        i += 1
    return out


def derive_config(frozen_cfg: dict, ctx: int, vision: str, mtp: bool, measured=None) -> dict:
    """In-memory profile config. The frozen combination returns `frozen_cfg` itself (identity)."""
    key = key_for(ctx, vision, mtp)
    req = required_mib(key, measured)
    if key == FROZEN_KEY:
        return frozen_cfg
    cfg = copy.deepcopy(frozen_cfg)
    r, m = cfg["runtime"], cfg["model"]
    r["ctx"] = key[0]
    r["vision_enabled"] = vision != "off"
    if vision == "cpu":
        r["vision_offload"] = False
    if not mtp:
        r["extra_args"] = _strip_mtp(list(r.get("extra_args", [])))
        m.pop("mtp_draft", None)
    cfg["profile"] = {"schema": SCHEMA, "id": profile_id(key), "ctx": key[0], "vision": vision, "mtp": bool(mtp),
                      "required_mib": req, "derived_from_digest": R.config_digest(frozen_cfg), "qualified": False}
    return cfg


def cfg_required_mib(cfg: dict, default: int) -> int:
    """The device request the lease must budget for this config (frozen config: the frozen constant)."""
    return int((cfg.get("profile") or {}).get("required_mib") or default)


def describe(cfg: dict) -> dict:
    p = cfg.get("profile")
    if not p:
        r = cfg["runtime"]
        return {"id": "frozen", "ctx": r["ctx"], "vision": "gpu" if r.get("vision_enabled") else "off",
                "mtp": bool(cfg["model"].get("mtp_draft")), "frozen": True}
    return {k: p[k] for k in ("id", "ctx", "vision", "mtp", "required_mib", "qualified")} | {"frozen": False}


# ---- UI controls (Thinking / Vision / Context) ----------------------------------------------------------------------
def plan_change(current: dict, *, context=None, vision=None, live_tokens: int = 0, confirm_shrink=False,
                mtp=None) -> dict:
    """Decide what a control change means. `current` is `describe(cfg)` of the running profile.

    Returns {"reload": bool, "target": key or None, "refused": code or None}. Never shrinks the context below the
    live conversation without `confirm_shrink` (URI never silently discards context); thinking never reaches here
    (it is per request: reasoning_policy depth fast / normal)."""
    ctx = int(context or current["ctx"])
    vis = vision or current["vision"]
    want_mtp = current["mtp"] if mtp is None else bool(mtp)
    try:
        target = key_for(ctx, vis, want_mtp)
        required_mib(target)
    except ProfileError as exc:
        return {"reload": False, "target": None, "refused": exc.code, "detail": exc.detail}
    if live_tokens and ctx < live_tokens and not confirm_shrink:
        return {"reload": False, "target": target, "refused": "CONTEXT_SMALLER_THAN_CONVERSATION",
                "detail": {"live_tokens": live_tokens, "ctx": ctx}}
    same = (current["ctx"], current["vision"], current["mtp"]) == target
    return {"reload": not same, "target": target, "refused": None, "profile_id": profile_id(target)}


def thinking_depth(thinking_on: bool) -> str:
    """UI Thinking Off / On -> reasoning_policy user depth. On = NORMAL tier (768-token budget, qualified);
    Core seams stay FAST either way (reasoning_policy rule 1). Unbounded thinking is never offered."""
    return "normal" if thinking_on else "fast"
