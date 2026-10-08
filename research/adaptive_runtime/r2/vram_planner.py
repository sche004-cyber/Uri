"""Launch-time VRAM budget planner (research prototype; never activated, never writes runtime config).

Decides, before the Brain server starts, which Runtime v1 profile fits the VRAM that is actually free on the
adapter at that moment, keeping a headroom for the desktop and other GPU workloads. The profile table carries
the device-local request of each configuration measured in Adaptive Runtime R1 (`GGML_VK_MEMORY_LOGGER`,
`expM_b11425_memlog`) and the per-process residency observed in R1/R2 loads.

  python vram_planner.py --live                      # read the adapter now and plan
  python vram_planner.py --total 16368 --used 871     # plan for given numbers (tests, what-if)
  python vram_planner.py --live --baseline-seconds 30 # also measure the desktop usage band first

The output is a JSON decision: inputs, budget arithmetic, the chosen profile, the llama-server argument delta
and environment it implies, and the risk class. Nothing here edits `local_brain.json` or starts a server.
"""
from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import time
from dataclasses import asdict, dataclass, field

_BS = chr(92)
_Q_DED = ("(Get-Counter '@@GPU Adapter Memory(*)@@Dedicated Usage').CounterSamples | "
          "Measure-Object -Property CookedValue -Maximum | ForEach-Object { [int64]($_.Maximum/1MB) }").replace("@@", _BS)
_Q_TOTAL = ("Get-ChildItem 'HKLM:@@SYSTEM@@CurrentControlSet@@Control@@Class@@{4d36e968-e325-11ce-bfc1-08002be10318}' "
            "-ErrorAction SilentlyContinue | ForEach-Object { try { $v = Get-ItemProperty $_.PSPath -ErrorAction Stop; "
            "if ($v.'HardwareInformation.qwMemorySize') { [int64]($v.'HardwareInformation.qwMemorySize'/1MB) } } catch {} } "
            "| Select-Object -First 1").replace("@@", _BS)

PINNED_TOTAL_MIB = 16368   # RX 7900 GRE as reported by llama.cpp/Vulkan and the registry (17,163,091,968 bytes)
BLOCKS_128_MIB_ENV = {"GGML_VK_SUBALLOCATION_BLOCK_SIZE": "134217728"}


@dataclass(frozen=True)
class Profile:
    name: str
    device_request_mib: int          # device-local bytes llama-server asks for at steady state (R1 ledger)
    host_visible_mib: int            # host-visible share by design (not demotion)
    features: tuple                  # what the profile keeps
    arg_delta: tuple = ()            # llama-server args relative to the frozen Runtime v1 command line
    drop: tuple = ()                 # frozen args removed (MTP draft flags) for this profile
    notes: str = ""


# Device-local requests from the R1 allocation ledger (section 4.1 / 7). "full" is the frozen Runtime v1.
PROFILES: tuple[Profile, ...] = (
    Profile("full", 15626, 872, ("vision-gpu", "mtp", "ctx32k"), (), (),
            "frozen Runtime v1: weights 12,636 + vision 1,106 + MTP 1,135 + KV 340 + recurrent 188 + compute 216"),
    Profile("vision_cpu", 15626 - 1106, 872 + 28, ("vision-cpu", "mtp", "ctx32k"), ("--no-mmproj-offload",), (),
            "vision encoder runs on the CPU (image encode 5.0 s vs 1.6 s); measured resident 14,693-14,826 / 872-900"),
    Profile("no_mtp", 15626 - 1135, 498, ("vision-gpu", "ctx32k"), (),
            ("-md", "--spec-type", "--spec-draft-n-max", "-otd"),
            "no MTP draft (decode 104 vs 115 tok/s); measured resident 14,532-14,599 / 498"),
    Profile("vision_cpu_no_mtp", 15626 - 1106 - 1135, 498, ("vision-cpu", "ctx32k"), ("--no-mmproj-offload",),
            ("-md", "--spec-type", "--spec-draft-n-max", "-otd"),
            "measured resident 13,424-13,491 / 498 next to a 1.09 GB consumer (103.5 tok/s)"),
)

DEFAULT_HEADROOM_MIB = 768   # see headroom_rationale()


def headroom_rationale() -> dict:
    return {
        "desktop_idle_band_mib": "433-900 observed across R1/R2 sessions (dwm 337, Edge WebView 56, Claude app 50-124, ExitLag 83, CPU embedding server 222)",
        "desktop_burst_mib": "window redraw / browser video adds ~200-400 on top of idle",
        "driver_reserve_mib": "adapter peaked at 16,277-16,313 of 16,368 with memory priority, i.e. 55-90 MiB never handed out",
        "release_lag": "a previous server's VRAM is released seconds (once ~2 min) after exit; the planner samples after the guard",
        "rule": "headroom = 768 MiB default (burst 400 + reserve 90 + margin); the owner may raise it for heavier desktops",
    }


def adapter_total_mib() -> tuple[int, str]:
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", _Q_TOTAL], capture_output=True, text=True, timeout=30).stdout.strip()
        v = int(out.splitlines()[0]) if out else 0
        if v > 1024:
            return v, "registry HardwareInformation.qwMemorySize"
    except Exception:
        pass
    return PINNED_TOTAL_MIB, "pinned constant (registry unavailable)"


def adapter_used_mib() -> int | None:
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", _Q_DED], capture_output=True, text=True, timeout=30).stdout.strip()
        return int(out.splitlines()[-1]) if out else None
    except Exception:
        return None


def sample_desktop_band(seconds: float, interval: float = 1.0) -> dict:
    """Measure the adapter usage band while nothing of ours runs (headroom evidence)."""
    vals = []
    t_end = time.monotonic() + seconds
    while time.monotonic() < t_end:
        v = adapter_used_mib()
        if v is not None:
            vals.append(v)
        time.sleep(interval)
    if not vals:
        return {"n": 0}
    return {"n": len(vals), "min": min(vals), "p50": statistics.median(vals), "max": max(vals), "seconds": seconds}


@dataclass
class Plan:
    total_mib: int
    total_source: str
    used_by_others_mib: int
    headroom_mib: int
    budget_mib: int
    order: list
    chosen: str
    fits: bool
    margin_mib: int
    expected_demotion_mib: int
    risk: str
    env: dict
    arg_delta: list
    drop_args: list
    candidates: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def plan(total_mib: int, used_by_others_mib: int, headroom_mib: int = DEFAULT_HEADROOM_MIB,
         order=("full", "vision_cpu", "no_mtp", "vision_cpu_no_mtp"), blocks_policy: str = "always",
         total_source: str = "given", profiles=PROFILES) -> Plan:
    """Pick the first profile in `order` whose device request fits total - used - headroom.

    blocks_policy: "always" (128 MiB suballocation blocks on every profile), "when_oversubscribed" (only when
    the chosen profile does not fit) or "never".
    """
    by = {p.name: p for p in profiles}
    budget = total_mib - used_by_others_mib - headroom_mib
    cands = []
    chosen = None
    for name in order:
        p = by[name]
        margin = budget - p.device_request_mib
        cands.append({"profile": name, "request_mib": p.device_request_mib, "margin_mib": margin, "fits": margin >= 0})
        if margin >= 0 and chosen is None:
            chosen = p
    fits = chosen is not None
    notes = []
    if not fits:
        # Nothing fits with headroom: take the smallest request, report the expected demotion honestly.
        chosen = min((by[n] for n in order), key=lambda p: p.device_request_mib)
        notes.append("no profile fits with headroom; smallest profile chosen, demotion expected")
    margin = budget - chosen.device_request_mib
    no_headroom_free = total_mib - used_by_others_mib
    expected_demotion = max(0, chosen.device_request_mib - no_headroom_free)
    if fits and margin >= headroom_mib // 2:
        risk = "low"
    elif fits:
        risk = "edge"
    elif expected_demotion == 0:
        risk = "oversubscribed_within_headroom"
        notes.append("request exceeds the budget only because of the headroom; a desktop burst would demote blocks")
    else:
        risk = "oversubscribed"
    env = {}
    if blocks_policy == "always" or (blocks_policy == "when_oversubscribed" and not fits):
        env = dict(BLOCKS_128_MIB_ENV)
        notes.append("128 MiB suballocation blocks (R1/R2 candidate): softens the demotion cliff, no idle cost measured")
    return Plan(total_mib, total_source, used_by_others_mib, headroom_mib, budget, list(order), chosen.name, fits, margin,
                expected_demotion, risk, env, list(chosen.arg_delta), list(chosen.drop), cands, notes)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", action="store_true", help="read the adapter counters now")
    ap.add_argument("--total", type=int, help="adapter VRAM MiB (what-if)")
    ap.add_argument("--used", type=int, help="dedicated usage by other processes MiB (what-if)")
    ap.add_argument("--headroom", type=int, default=DEFAULT_HEADROOM_MIB)
    ap.add_argument("--order", default="full,vision_cpu,no_mtp,vision_cpu_no_mtp")
    ap.add_argument("--blocks", default="always", choices=["always", "when_oversubscribed", "never"])
    ap.add_argument("--baseline-seconds", type=float, default=0, help="sample the desktop band first (live only)")
    a = ap.parse_args()
    rec = {"headroom_rationale": headroom_rationale()}
    if a.live:
        total, src = adapter_total_mib()
        if a.baseline_seconds > 0:
            rec["desktop_band"] = sample_desktop_band(a.baseline_seconds)
            used = int(rec["desktop_band"]["max"])
        else:
            used = adapter_used_mib()
            if used is None:
                raise SystemExit("adapter counters unavailable")
    else:
        if a.total is None or a.used is None:
            raise SystemExit("--live or --total and --used")
        total, src, used = a.total, "given", a.used
    p = plan(total, used, a.headroom, tuple(a.order.split(",")), a.blocks, src)
    rec["plan"] = asdict(p)
    print(json.dumps(rec, indent=1))


if __name__ == "__main__":
    main()
