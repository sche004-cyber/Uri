"""Machine-wide GPU ownership for URI workloads (WS hardening T1, finding GPU-1).

Problem (measured, Adaptive Runtime R1 and WS PERF-W1): the frozen Runtime v1 server asks for 15.26 GiB of
device-local memory on a 16 GiB card. When another process holds about 1 GB, the driver demotes whole 1 GiB blocks to
system memory and decode falls from 110-127 to about 25 tok/s for the life of the process. Two URI sessions (a Brain
host and a benchmark, or two Brain hosts in different trees) can therefore ruin each other without any error.

This module gives every URI GPU workload one lease, held through an OS byte lock on a file in
`%LOCALAPPDATA%\\URI\\gpu\\`:

  * acquire / wait with a timeout / release;
  * the OS frees the lock when the holder process dies, so a crashed holder never blocks the GPU (stale-owner
    recovery). The next holder records the recovery in the history;
  * a holder that keeps the lease past its declared `max_hold_s` is reported as overdue. It is never broken or
    terminated: active jobs are preserved, and only the owner can stop that process;
  * nothing in this module terminates, suspends or signals any process.

Processes that do not use the lease (Ollama, games, other tools) are still seen: `census()` reads the Windows
"GPU Process Memory" and "GPU Adapter Memory" counters and `assess_fit()` applies the measured budget rule.

App windows are not lease clients (P-GOV-1). `advise_window()` is a read-only hint for a script that is about to open
a URI window: it never takes the lock and never writes a lease file, and the user's own Companion is never blocked.

CLI (for benchmarks in other sessions):
    python -m uri_operational_intelligence.gpu_lease status
    python -m uri_operational_intelligence.gpu_lease census
    python -m uri_operational_intelligence.gpu_lease run --purpose benchmark --label "my bench" -- <command ...>
    python -m uri_operational_intelligence.gpu_lease advise --window [--mib 480] [--wait 1800]
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "uri.gpu.lease.v1"

# Measured device-local request of the frozen Runtime v1 server (Adaptive Runtime R1: weights 12.34, vision 1.08,
# MTP draft 1.13, KV/compute 0.73 GiB = 15.26 GiB). Host-visible memory (0.85 GiB) is not counted.
RUNTIME_V1_DEVICE_MIB = 15626
# A process below this is not listed as a separate consumer (it still counts in the budget).
LIST_MIN_MIB = 128
# Margin below which a start is reported as AT_RISK (half a demotion block; R1 blocks are 1 GiB).
AT_RISK_MARGIN_MIB = 512
# Shortfall at which a start is refused as CONTENDED: half a 1 GiB demotion block. Measured starts on this card
# (WS hardening evidence, 2026-10-09): shortfall 78 MB -> 90.8 tok/s (healthy); shortfall 913 MB next to another
# session's three app windows -> 29.9 tok/s (slow); ~1.2-1.4 GB next to a 1.6 GB consumer -> ~25 tok/s (R1, R2, WS).
# Even with a positive margin (desktop only, +340 MB) 1 of 5 loads came up slow, so the budget cannot promise a fast
# load: below the threshold the start is AT_RISK and the post-start calibration classifies the instance. (First set to
# 1024 MiB; tightened after the 913 MB slow start, see WS_HARDENING_PLAN.md change log.)
CONTENDED_SHORTFALL_MIB = 512
DESKTOP = {"dwm.exe": "desktop compositor"}

FITS, AT_RISK, CONTENDED, UNKNOWN = "FITS", "AT_RISK", "CONTENDED", "UNKNOWN"


def lease_dir() -> Path:
    base = os.environ.get("URI_GPU_LEASE_DIR")
    if base:
        return Path(base)
    return Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "URI" / "gpu"


class GpuBusy(RuntimeError):
    def __init__(self, holder):
        super().__init__("GPU_LEASE_HELD")
        self.code = "GPU_LEASE_HELD"
        self.holder = holder


# ---- process helpers ---------------------------------------------------------------------------------------------
def _proc_info(pid):
    try:
        import psutil
        p = psutil.Process(pid)
        with p.oneshot():
            info = {"pid": pid, "name": p.name(), "create_time": round(p.create_time(), 3)}
            try:
                parent = p.parent()
                info["parent"] = parent.name() if parent else None
            except Exception:
                info["parent"] = None
            return info
    except Exception:
        return {"pid": pid, "name": None, "create_time": None, "parent": None}


def holder_alive(holder) -> bool:
    if not holder or not holder.get("pid"):
        return False
    info = _proc_info(holder["pid"])
    return info["create_time"] is not None and (holder.get("create_time") is None
                                                or abs(info["create_time"] - holder["create_time"]) < 1.0)


def _descendants(pid):
    try:
        import psutil
        return {c.pid for c in psutil.Process(pid).children(recursive=True)}
    except Exception:
        return set()


def _atomic_json(path: Path, data):
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)


def _read_json(path: Path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


# ---- the lease ---------------------------------------------------------------------------------------------------
class GpuLease:
    """One held lease. Use `acquire()`; release with `release()` or as a context manager."""

    def __init__(self, fd, record, directory):
        self._fd, self.record, self.dir = fd, record, directory

    @property
    def held(self):
        return self._fd is not None

    def heartbeat(self, **extra):
        if self._fd is None:
            return
        self.record.update(extra, heartbeat_at=round(time.time(), 3))
        _atomic_json(self.dir / "lease.json", self.record)

    def release(self, reason="released"):
        if self._fd is None:
            return
        import msvcrt
        self.record.update(state="released", released_at=round(time.time(), 3), release_reason=reason)
        try:
            _atomic_json(self.dir / "lease.json", self.record)
            _history(self.dir, "RELEASED", self.record)
        finally:
            try:
                os.lseek(self._fd, 0, 0)
                msvcrt.locking(self._fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            os.close(self._fd)
            self._fd = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.release()


def _history(directory: Path, event, record):
    line = json.dumps({"t": round(time.time(), 3), "event": event,
                       **{k: record.get(k) for k in ("pid", "purpose", "label", "session", "override")}})
    with open(directory / "history.jsonl", "a", encoding="utf-8") as f:
        f.write(line + "\n")


def _try_lock(directory: Path):
    import msvcrt
    directory.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(directory / "gpu.lock"), os.O_RDWR | os.O_CREAT)
    try:
        msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        return fd
    except OSError:
        os.close(fd)
        return None


def status(directory: Path | None = None) -> dict:
    """Who holds the lease, without taking it."""
    d = Path(directory or lease_dir())
    rec = _read_json(d / "lease.json") or {}
    fd = _try_lock(d)
    if fd is not None:
        import msvcrt
        os.lseek(fd, 0, 0)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        os.close(fd)
        stale = rec.get("state") == "held"
        return {"state": "FREE", "last": rec or None, "stale_record": stale}
    alive = holder_alive(rec) if rec.get("state") == "held" else False
    out = {"state": "HELD" if alive else "HELD_UNKNOWN", "holder": rec if alive else None}
    if alive and rec.get("max_hold_s"):
        out["overdue"] = time.time() > rec.get("acquired_at", 0) + rec["max_hold_s"]
    return out


def acquire(purpose, *, label="", session="", expected_vram_mib=None, max_hold_s=None, wait_s=0.0,
            poll_s=0.5, override=None, directory=None, pid=None) -> GpuLease:
    """Take the lease or raise GpuBusy after `wait_s`. `override` records an owner-authorized start next to foreign
    (non-lease) GPU consumers; it never takes a lease another URI workload holds."""
    d = Path(directory or lease_dir())
    deadline = time.monotonic() + max(0.0, wait_s)
    while True:
        fd = _try_lock(d)
        if fd is not None:
            break
        if time.monotonic() >= deadline:
            raise GpuBusy(status(d).get("holder"))
        time.sleep(poll_s)
    prev = _read_json(d / "lease.json") or {}
    me = _proc_info(pid or os.getpid())
    record = {"schema": SCHEMA, "state": "held", "pid": me["pid"], "create_time": me["create_time"],
              "process": me["name"], "purpose": purpose, "label": label, "session": session,
              "expected_vram_mib": expected_vram_mib, "max_hold_s": max_hold_s, "override": override,
              "acquired_at": round(time.time(), 3), "heartbeat_at": round(time.time(), 3)}
    if prev.get("state") == "held" and prev.get("pid") != record["pid"]:
        # The previous holder died without releasing (its OS lock went with it).
        record["recovered_from"] = {k: prev.get(k) for k in ("pid", "purpose", "label", "acquired_at", "heartbeat_at")}
        _history(d, "STALE_RECOVERED", prev)
    _atomic_json(d / "lease.json", record)
    _history(d, "ACQUIRED", record)
    return GpuLease(fd, record, d)


def record_contention(directory=None, fit=None):
    """Machine-wide memory of the last time a URI GPU workload saw the GPU CONTENDED (wall time), so a quiet window
    survives a restart of the process that observed it."""
    d = Path(directory or lease_dir())
    d.mkdir(parents=True, exist_ok=True)
    _atomic_json(d / "contention.json", {"t": round(time.time(), 3), "pid": os.getpid(),
                                         "consumers": (fit or {}).get("consumers")})


def last_contention(directory=None):
    rec = _read_json(Path(directory or lease_dir()) / "contention.json") or {}
    t = rec.get("t")
    return float(t) if isinstance(t, (int, float)) else None


# ---- census and budget -------------------------------------------------------------------------------------------
_PS_CENSUS = (
    "$ErrorActionPreference='SilentlyContinue';"
    "$p=(Get-Counter '\\GPU Process Memory(*)\\Dedicated Usage','\\GPU Process Memory(*)\\Non Local Usage').CounterSamples"
    " | Where-Object CookedValue -gt 0 | ForEach-Object { @{i=$_.InstanceName; c=($_.Path -split '\\\\')[-1]; v=[int64]$_.CookedValue} };"
    "$a=(Get-Counter '\\GPU Adapter Memory(*)\\Dedicated Usage').CounterSamples"
    " | ForEach-Object { @{i=$_.InstanceName; v=[int64]$_.CookedValue} };"
    "@{p=@($p); a=@($a)} | ConvertTo-Json -Compress -Depth 4")


def card_mib():
    """Dedicated memory of the largest display adapter (registry), or None."""
    try:
        import winreg
        key = r"SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}"
        best = None
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as k:
            for i in range(64):
                try:
                    sub = winreg.EnumKey(k, i)
                except OSError:
                    break
                try:
                    with winreg.OpenKey(k, sub) as s:
                        v, _ = winreg.QueryValueEx(s, "HardwareInformation.qwMemorySize")
                        name, _ = winreg.QueryValueEx(s, "DriverDesc")
                        mib = int(v) // 2**20
                        if best is None or mib > best[0]:
                            best = (mib, name)
                except OSError:
                    continue
        return best
    except Exception:
        return None


def raw_counters(timeout=25):
    out = subprocess.run(["powershell", "-NoProfile", "-Command", _PS_CENSUS], capture_output=True, text=True,
                         timeout=timeout, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
    return json.loads(out or "{}")


def census(raw=None, card=None) -> dict:
    """Per-process dedicated / non-local GPU memory on the main adapter (MiB), plus adapter totals."""
    t0 = time.time()
    try:
        raw = raw if raw is not None else raw_counters()
    except (OSError, ValueError, subprocess.TimeoutExpired) as exc:
        return {"ok": False, "error": type(exc).__name__}
    adapters = {a["i"].split("_phys")[0]: a["v"] for a in raw.get("a") or []}
    if not adapters:
        return {"ok": False, "error": "NO_ADAPTER_COUNTERS"}
    luid = max(adapters, key=adapters.get)            # the card that carries the desktop and the models
    procs = {}
    for s in raw.get("p") or []:
        inst = s["i"]
        if luid not in inst or not inst.startswith("pid_"):
            continue
        pid = int(inst.split("_")[1])
        e = procs.setdefault(pid, {"pid": pid, "dedicated_mib": 0.0, "non_local_mib": 0.0})
        key = "dedicated_mib" if s["c"].startswith("dedicated") else "non_local_mib"
        e[key] += s["v"] / 2**20
    for e in procs.values():
        e.update({k: v for k, v in _proc_info(e["pid"]).items() if k != "pid"})
        e["dedicated_mib"], e["non_local_mib"] = round(e["dedicated_mib"], 1), round(e["non_local_mib"], 1)
    card = card if card is not None else card_mib()
    adapter_used = round(adapters[luid] / 2**20, 1)
    attributed = round(sum(e["dedicated_mib"] for e in procs.values()), 1)
    return {"ok": True, "t": round(t0, 3), "sample_s": round(time.time() - t0, 2), "luid": luid,
            "card_mib": card[0] if card else None, "card_name": card[1] if card else None,
            "adapter_dedicated_mib": adapter_used, "attributed_mib": attributed,
            "unattributed_mib": round(max(0.0, adapter_used - attributed), 1),
            "processes": sorted(procs.values(), key=lambda e: -e["dedicated_mib"])}


def owner_pids(lease_pid=None, extra=()):
    s = set(p for p in extra if p)
    if lease_pid:
        s.add(lease_pid)
        s |= _descendants(lease_pid)
    return s


def assess_fit(c: dict, *, owners=(), required_mib=RUNTIME_V1_DEVICE_MIB) -> dict:
    """Budget rule: free = card - (dedicated memory of every non-owner process) - unattributed adapter memory
    (memory still committed after a process exit); margin = free - required (the measured request). CONTENDED when the
    shortfall reaches half a demotion block, AT_RISK when the margin is below half a block, FITS otherwise. Owner
    processes (the lease holder and its children, e.g. our own server) are excluded, so an already loaded Brain does
    not count against itself."""
    if not c.get("ok") or not c.get("card_mib"):
        return {"verdict": UNKNOWN, "reason": c.get("error") or "CARD_SIZE_UNKNOWN"}
    owners = set(owners)
    others = [p for p in c["processes"] if p["pid"] not in owners]
    others_mib = round(sum(p["dedicated_mib"] for p in others), 1)
    owner_mib = round(sum(p["dedicated_mib"] for p in c["processes"] if p["pid"] in owners), 1)
    free = round(c["card_mib"] - others_mib - c["unattributed_mib"], 1)
    margin = round(free - required_mib, 1)
    verdict = CONTENDED if margin <= -CONTENDED_SHORTFALL_MIB else AT_RISK if margin < AT_RISK_MARGIN_MIB else FITS
    consumers = [{"pid": p["pid"], "name": p.get("name"), "parent": p.get("parent"),
                  "dedicated_mib": p["dedicated_mib"], "role": DESKTOP.get((p.get("name") or "").lower())}
                 for p in others if p["dedicated_mib"] >= LIST_MIN_MIB]
    return {"verdict": verdict, "card_mib": c["card_mib"], "required_mib": required_mib,
            "others_mib": others_mib, "unattributed_mib": c["unattributed_mib"], "owner_mib": owner_mib,
            "free_mib": free, "margin_mib": margin, "consumers": consumers}


def explain(fit: dict) -> str:
    """One sentence for the user (no process is touched)."""
    v = fit.get("verdict")
    if v == UNKNOWN:
        return "GPU memory could not be measured (%s)." % fit.get("reason")
    def who(c):
        name = c.get("name") or "pid %d" % c["pid"]
        if c.get("parent") and c["parent"].lower() not in ("explorer.exe", "svchost.exe", "winlogon.exe", "services.exe"):
            name += " from " + c["parent"]
        return "%s (%s%.1f GB)" % (name, c["role"] + ", " if c.get("role") else "", c["dedicated_mib"] / 1024)
    named = [who(c) for c in fit.get("consumers", [])]
    if v == CONTENDED:
        return ("The Brain needs %.1f GB of GPU memory but only %.1f GB is free. In use by: %s. Close those or wait; "
                "URI will not stop them." % (fit["required_mib"] / 1024, max(0, fit["free_mib"]) / 1024,
                                             ", ".join(named) or "unattributed memory still being released"))
    if v == AT_RISK:
        if fit["margin_mib"] < 0:
            return ("GPU memory is %.0f MB short of the Brain's full request; it may run slowly. URI checks its speed "
                    "after loading." % -fit["margin_mib"])
        return "The Brain fits with a small margin (%.0f MB); other GPU apps may slow it down." % fit["margin_mib"]
    return "The Brain fits in GPU memory (margin %.0f MB)." % fit["margin_mib"]


# ---- window advisory (P-GOV-1) -----------------------------------------------------------------------------------
# A Living window takes 126-480 MiB (P_GOV_1_HANDOFF.md, measured); the default asks for the top of that range.
WINDOW_MIB = 480
# A process at or above this is a resident Runtime v1 server: every measured Brain load holds 13.4-15.8 GB local
# (Adaptive Runtime R1/R2, all four planner profiles); Ollama's runner and app windows stay below 2 GB.
RESIDENT_BRAIN_MIN_MIB = 12000
# Adapter memory no process accounts for, above which the census cannot rule out a hidden Brain (Codex P-GOV-1 r9).
# Twice the Brain host's release threshold (512 MiB); a healthy desktop sample leaves tens of MiB unattributed.
UNATTRIBUTED_MAX_MIB = 1024
GO, WAIT_HEAVY, WILL_DEGRADE_BRAIN = "GO", "WAIT_HEAVY", "WILL_DEGRADE_BRAIN"
ADVISE_EXIT = {GO: 0, WAIT_HEAVY: 75, WILL_DEGRADE_BRAIN: 76}
HEAVY_PURPOSES = ("benchmark", "regression_chain")
HEAVY_LABEL_WORDS = ("live", "bench")


def _lock_held(directory: Path):
    """True when another handle holds the lease byte lock, False when not, None when it cannot be told. It only
    READS the lock file: a read of a byte-locked range fails on Windows (ERROR_LOCK_VIOLATION), so no lock is ever
    taken and a concurrent acquire() cannot fail because of this probe (unlike status())."""
    try:
        with open(directory / "gpu.lock", "rb") as f:
            f.read(1)
        return False
    except FileNotFoundError:
        return False
    except PermissionError:
        return True
    except OSError:
        return None


def peek(directory=None) -> dict:
    """Who holds the lease, without taking the lock or writing anything. A held lock whose record does not (yet) name a
    live holder, e.g. an acquire() between taking the lock and publishing lease.json, is UNREADABLE (fail closed)."""
    d = Path(directory or lease_dir())
    held = _lock_held(d)
    if held is None:
        return {"state": "UNREADABLE", "holder": None}
    path = d / "lease.json"
    rec = _read_json(path) if path.exists() else {}
    if not isinstance(rec, dict):
        return {"state": "UNREADABLE", "holder": None}   # an existing record that cannot be read (A2: fail closed)
    if not held:
        return {"state": "FREE", "holder": None}          # a "held" record without the lock is a dead holder's
    if rec.get("state") == "held" and holder_alive(rec):
        return {"state": "HELD", "holder": rec}
    return {"state": "UNREADABLE", "holder": None}


def _ancestors(pid=None):
    """This process and its parents: a script that runs inside its own `gpu_lease run` lease is not waiting for
    itself."""
    try:
        import psutil
        p = psutil.Process(pid or os.getpid())
        return {p.pid} | {a.pid for a in p.parents()}
    except Exception:
        return {pid or os.getpid()}


def _heavy(holder) -> bool:
    purpose = (holder.get("purpose") or "").lower()
    label = (holder.get("label") or "").lower()
    if purpose in HEAVY_PURPOSES:
        return True
    return purpose == "runtime_v1_brain" and any(w in label for w in HEAVY_LABEL_WORDS)


def assess_window(lease: dict, c: dict, expected_mib=WINDOW_MIB, own_pids=()) -> dict:
    """GO / WAIT_HEAVY / WILL_DEGRADE_BRAIN for opening one more window now. Unmeasurable state is WAIT_HEAVY (fail
    closed for test windows; the user is never blocked because the app does not need to ask). A lease held by one of
    `own_pids` (the caller's own `gpu_lease run`) is not a reason to wait."""
    out = {"expected_mib": expected_mib, "lease": lease.get("state"),
           "holder": {k: (lease.get("holder") or {}).get(k) for k in ("pid", "purpose", "label")}
           if lease.get("holder") else None}
    if lease.get("state") not in ("FREE", "HELD"):
        return dict(out, verdict=WAIT_HEAVY, reason="LEASE_UNREADABLE",
                    explain="The GPU lease state cannot be read; a test window should wait.")
    own = lease.get("state") == "HELD" and lease["holder"].get("pid") in set(own_pids)
    out["own_lease"] = own
    if lease.get("state") == "HELD" and not own and _heavy(lease["holder"]):
        h = lease["holder"]
        return dict(out, verdict=WAIT_HEAVY, reason="HEAVY_HOLDER",
                    explain="%s (%s) holds the GPU; a test or capture window should wait." % (
                        h.get("label") or h.get("purpose"), h.get("purpose")))
    if not c.get("ok") or not c.get("card_mib"):
        return dict(out, verdict=WAIT_HEAVY, reason=c.get("error") or "CARD_SIZE_UNKNOWN",
                    explain="GPU memory cannot be measured; a test window should wait.")
    if not c.get("processes"):
        # The adapter counter answered but no process did (Codex P-GOV-1 r8): a resident Brain could be invisible.
        # The desktop compositor always holds memory, so an empty list means the per-process counters are missing.
        return dict(out, verdict=WAIT_HEAVY, reason="PROCESS_COUNTERS_MISSING",
                    explain="Per-process GPU memory cannot be read; a test window should wait.")
    if (c.get("unattributed_mib") or 0) >= UNATTRIBUTED_MAX_MIB:
        # Memory that no process accounts for (counters partly missing, or a server still releasing): a Brain could be
        # hidden in it.
        return dict(out, verdict=WAIT_HEAVY, reason="UNATTRIBUTED_GPU_MEMORY",
                    explain="%.0f MB of GPU memory is not attributed to any process; a test window should wait."
                            % c["unattributed_mib"])
    large = [p for p in c["processes"] if p["dedicated_mib"] >= RESIDENT_BRAIN_MIN_MIB]
    if any(not p.get("name") for p in large):
        # A Brain-sized process whose identity could not be read (e.g. it exited between the two samples).
        return dict(out, verdict=WAIT_HEAVY, reason="UNIDENTIFIED_LARGE_GPU_PROCESS",
                    explain="A large GPU process could not be identified; a test window should wait.")
    # Only a llama-server holding Brain-sized memory is a resident Brain (Codex P-GOV-1 r9); another large GPU
    # workload (a game) gets no Brain verdict.
    brains = [p for p in large if p["name"].lower().startswith("llama-server")]
    out["other_large"] = [{"pid": p["pid"], "name": p["name"], "dedicated_mib": p["dedicated_mib"]}
                          for p in large if p not in brains]
    free = round(c["card_mib"] - c["adapter_dedicated_mib"], 1)
    margin = round(free - expected_mib, 1)
    out.update(free_mib=free, margin_mib=margin,
               brain=[{"pid": p["pid"], "name": p.get("name"), "dedicated_mib": p["dedicated_mib"]} for p in brains])
    if not brains:
        return dict(out, verdict=GO, reason="NO_RESIDENT_BRAIN", explain="No Brain is resident; the window can open.")
    if margin < 0:
        b = brains[0]
        return dict(out, verdict=WILL_DEGRADE_BRAIN, reason="MARGIN_BELOW_WINDOW",
                    explain="The Brain (%s, pid %d) is resident and only %.0f MB of GPU memory is free; a %d MB window "
                            "will probably slow it until it restarts. Open windows before the Brain starts, or use "
                            "Restart Brain afterwards." % (b.get("name") or "llama-server", b["pid"], max(0, free),
                                                           expected_mib))
    return dict(out, verdict=GO, reason="MARGIN_OK", explain="The window fits next to the Brain (margin %.0f MB)." % margin)


def advise_window(expected_mib=WINDOW_MIB, *, wait_s=0.0, poll_s=5.0, directory=None, census_fn=None,
                  own_pids=None) -> dict:
    """Read-only advisory for a script about to open a URI window. Waits (polling) only while the verdict is
    WAIT_HEAVY. Takes no lock, writes no file, stops nothing."""
    deadline = time.monotonic() + max(0.0, wait_s)
    census_fn = census_fn or census
    own = _ancestors() if own_pids is None else set(own_pids)
    while True:
        res = assess_window(peek(directory), census_fn(), expected_mib, own_pids=own)
        res["t"] = round(time.time(), 3)
        if res["verdict"] != WAIT_HEAVY or time.monotonic() >= deadline:
            return res
        time.sleep(poll_s)


# ---- CLI ---------------------------------------------------------------------------------------------------------
def main(argv=None):
    ap = argparse.ArgumentParser(prog="python -m uri_operational_intelligence.gpu_lease")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    sub.add_parser("census")
    r = sub.add_parser("run")
    r.add_argument("--purpose", required=True)
    r.add_argument("--label", default="")
    r.add_argument("--wait", type=float, default=0.0, help="seconds to wait for the lease")
    r.add_argument("--max-hold", type=float, default=None)
    r.add_argument("command", nargs=argparse.REMAINDER)
    adv = sub.add_parser("advise")
    adv.add_argument("--window", action="store_true", required=True)
    adv.add_argument("--mib", type=int, default=WINDOW_MIB)
    adv.add_argument("--wait", type=float, default=0.0, help="seconds to wait while the verdict is WAIT_HEAVY")
    a = ap.parse_args(argv)
    if a.cmd == "advise":
        res = advise_window(a.mib, wait_s=a.wait)
        print(json.dumps(res, indent=1))
        return ADVISE_EXIT[res["verdict"]]
    if a.cmd == "status":
        print(json.dumps(status(), indent=1))
        return 0
    if a.cmd == "census":
        c = census()
        fit = assess_fit(c)
        print(json.dumps({"census": c, "fit_for_runtime_v1": fit, "explain": explain(fit)}, indent=1))
        return 0
    cmd = a.command[1:] if a.command[:1] == ["--"] else a.command
    if not cmd:
        ap.error("run needs a command after --")
    try:
        lease = acquire(a.purpose, label=a.label, wait_s=a.wait, max_hold_s=a.max_hold)
    except GpuBusy as exc:
        print(json.dumps({"refused": exc.code, "holder": exc.holder}), file=sys.stderr)
        return 75
    with lease:
        # The workload lives in a kill-on-close job owned by this holder (the accepted Supervisor containment): if
        # the holder dies, the OS ends the workload with it, so the workload never keeps using the GPU
        # after its lease is gone (Codex H-r4).
        import uuid
        from uri_supervisor.winproc import spawn_contained
        c = spawn_contained(cmd, "uri-gpu-lease-" + uuid.uuid4().hex, stdin=subprocess.DEVNULL,
                            stdout=sys.stdout, stderr=sys.stderr)
        try:
            return c.proc.wait()
        finally:
            c.close()


if __name__ == "__main__":
    sys.exit(main())
