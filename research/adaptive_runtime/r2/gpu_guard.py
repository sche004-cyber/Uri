"""GPU-owner guard (research, read-only).

Before a research load starts, make sure no process outside this session holds a significant share of the
adapter. The guard never terminates or pauses anything; it only waits and reports. Processes whose name is on
the allow list (the intentional pressure consumer, e.g. Ollama) and explicitly allowed PIDs are ignored.

  python gpu_guard.py --min-mib 1500 --allow ollama --timeout 0 --json
  exit 0 = clear, exit 2 = foreign owner still present at timeout
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time

import psutil

_BS = chr(92)
_Q = ("(Get-Counter '@@GPU Process Memory(*)@@Local Usage','@@GPU Process Memory(*)@@Non Local Usage').CounterSamples "
      "| ForEach-Object { $_.Path + '=' + [int64]($_.CookedValue/1MB) }").replace("@@", _BS)
_PID = re.compile(r"pid_(\d+)_")


def gpu_processes() -> dict[int, dict]:
    """{pid: {"local_mib", "nonlocal_mib", "name", "cmd"}} for every process the GPU counters know about."""
    try:
        out = subprocess.run(["powershell", "-NoProfile", "-Command", _Q], capture_output=True, text=True, timeout=40).stdout
    except Exception:
        return {}
    procs: dict[int, dict] = {}
    for line in out.splitlines():
        if "=" not in line:
            continue
        path, v = line.rsplit("=", 1)
        m = _PID.search(path)
        if not m:
            continue
        pid = int(m.group(1))
        key = "nonlocal_mib" if "non local usage" in path.lower() else "local_mib"
        d = procs.setdefault(pid, {"local_mib": 0, "nonlocal_mib": 0, "name": None, "cmd": None})
        d[key] += int(v)
    for pid, d in procs.items():
        d["parent_name"] = None
        try:
            p = psutil.Process(pid)
            d["name"] = p.name()
            d["cmd"] = " ".join(p.cmdline())[:200]
            par = p.parent()
            d["parent_name"] = par.name() if par else None
        except Exception:
            d["name"] = d["name"] or "?"
    return procs


def foreign_owners(min_mib: int, allow_names=("ollama",), allow_pids=()) -> list[dict]:
    allow_names = tuple(a.lower() for a in allow_names)
    own = {psutil.Process().pid}
    try:
        own.add(psutil.Process().ppid())
    except Exception:
        pass
    out = []
    for pid, d in gpu_processes().items():
        if pid in allow_pids or pid in own:
            continue
        # Ollama 0.34 runs its model in a child `lib\ollama\llama-server.exe`: match the process name, the
        # parent's name and the executable path against the allow list.
        ident = " ".join(x for x in ((d.get("name") or ""), (d.get("parent_name") or ""), (d.get("cmd") or "")[:120]) if x).lower()
        if any(a in ident for a in allow_names):
            continue
        if d["local_mib"] + d["nonlocal_mib"] >= min_mib:
            out.append({"pid": pid, **d})
    return sorted(out, key=lambda x: -x["local_mib"])


def blocking_commands(substrings: tuple[str, ...]) -> list[dict]:
    """Processes whose command line contains one of the substrings (e.g. another session's Brain host
    that restarts its server between journeys): their presence blocks a start even while the GPU is idle."""
    if not substrings:
        return []
    out = []
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            cmd = " ".join(p.info["cmdline"] or [])
        except Exception:
            continue
        # skip the guard itself and the shells that launched it (their command lines quote the substring)
        if "--block-cmd" in cmd or "gpu_guard" in cmd:
            continue
        if any(s in cmd for s in substrings):
            out.append({"pid": p.pid, "name": p.info["name"], "cmd": cmd[:160]})
    return out


def wait_clear(min_mib=1500, allow_names=("ollama",), allow_pids=(), timeout_s: float | None = None,
               interval_s=15.0, log=print, quiet_s: float = 0.0, block_cmds: tuple[str, ...] = ()) -> dict:
    """Block until no foreign owner holds >= min_mib and no blocking command runs, continuously for quiet_s.
    Returns a record of the wait (never raises)."""
    t0 = time.monotonic()
    waits = 0
    clear_since = None
    while True:
        owners = foreign_owners(min_mib, allow_names, allow_pids)
        blockers = blocking_commands(block_cmds)
        now = time.monotonic()
        if not owners and not blockers:
            clear_since = clear_since or now
            if now - clear_since >= quiet_s:
                return {"clear": True, "waited_s": round(now - t0, 1), "polls": waits + 1, "quiet_s": quiet_s}
        else:
            clear_since = None
        if timeout_s is not None and now - t0 >= timeout_s:
            return {"clear": False, "waited_s": round(now - t0, 1), "polls": waits + 1, "owners": owners, "blockers": blockers}
        if waits % 4 == 0:
            log(f"[gpu_guard] waiting: foreign GPU owner(s) {[(o['pid'], o['name'], o['local_mib']) for o in owners]} "
                f"blockers {[(b['pid'], b['cmd'][:60]) for b in blockers]} clear_for={round(now - clear_since, 0) if clear_since else 0}s")
        waits += 1
        time.sleep(interval_s)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--min-mib", type=int, default=1500)
    ap.add_argument("--allow", action="append", default=["ollama"], help="process-name substrings to ignore")
    ap.add_argument("--allow-pid", action="append", type=int, default=[])
    ap.add_argument("--timeout", type=float, default=0, help="seconds to wait; 0 = report once; <0 = wait forever")
    ap.add_argument("--interval", type=float, default=15.0)
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--quiet-s", type=float, default=0.0, help="GPU must stay clear this long before 'clear'")
    ap.add_argument("--block-cmd", action="append", default=[], help="command-line substring that blocks a start")
    a = ap.parse_args()
    timeout = None if a.timeout < 0 else a.timeout
    rec = wait_clear(a.min_mib, tuple(a.allow), tuple(a.allow_pid), timeout, a.interval,
                     log=lambda m: print(m, file=sys.stderr, flush=True), quiet_s=a.quiet_s, block_cmds=tuple(a.block_cmd))
    if a.json:
        print(json.dumps(rec))
    else:
        print("clear" if rec["clear"] else f"BLOCKED by {rec.get('owners')}")
    sys.exit(0 if rec["clear"] else 2)


if __name__ == "__main__":
    main()
