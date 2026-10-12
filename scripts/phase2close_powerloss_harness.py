"""Phase 2 closure: controlled power-loss qualification harness for the supervisor ledger
(implements `docs/plans/PHASE2A_POWER_LOSS_TEST_PLAN.md`; procedure in `PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md`).

The durability claim (WAL + synchronous=FULL survives power loss) can only be QUALIFIED on a machine whose power is
really cut: a throwaway VM powered off by its hypervisor. Killing a process cannot qualify it (the OS page cache
survives a process kill). This harness therefore has four roles:

  guest     runs INSIDE the VM at every boot: first `verify` (report the ledger left by the previous boot to the host),
            then an endless REAL supervisor workload (submit -> admit -> declare intents -> run a real attempt of the
            fake NDJSON executor writing a local file). After each supervisor call RETURNS (= its transaction committed)
            it sends an acknowledgement to the host over TCP. Acks never touch the guest disk.
  host      runs OUTSIDE the VM: records every ack to its own disk (fsync per line), powers the VM off with the
            hypervisor at a random instant, powers it on, waits for the guest's verify report, and compares: every
            acknowledged step must be present after the power cut. Repeats N iterations, then writes a SERIES verdict
            (`SERIES_ALL_PASS` / `SERIES_FAIL`), never a qualification. A failed power command stops the series; an
            iteration with no acknowledged work fails (`NO_ACKED_WORK`).
  assess    the only verdict on durability, RECOMPUTED from each series' raw `acks.jsonl` (review round 2, D4; the
            summary and iterations files must agree with it): a FULL series (>= 200, all pass) AND a NORMAL control
            that lost >= 1 acknowledged step -> `EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION`; else `INSUFFICIENT`.
            `qualified` is always false: the owner attests the power method and records PA-11.
  verify    the checks, also callable alone on a ledger file: (a) acknowledged steps present (host side), (b) PRAGMA
            integrity_check == ok, (c) no attempt SPAWNING/RUNNING without its admission and intents, (d) startup
            recovery leaves no task RUNNING/RECOVERING, (e) recovery never relaunches anything (no attempt in the
            verification epoch for a task from an earlier boot).
  simulate  LOCAL PLUMBING CHECK ONLY: the same host logic with "power off" = kill of a local guest process. Its
            result is labelled SIMULATED and can never qualify durability (see above).

Control: `guest --synchronous NORMAL` weakens the ledger for a negative-control series. The plan's pass criterion
needs the control series to LOSE at least one acknowledged commit; otherwise the rig is not strong enough and a FULL
result means nothing.

Usage (VM):    python scripts/phase2close_powerloss_harness.py guest --ledger D:\\pl\\ledger.db --host 10.0.0.1 --port 47710
Usage (host):  python scripts/phase2close_powerloss_harness.py host --port 47710 --iterations 200 --out <dir>
                   --power-off "powershell -NoProfile -Command Stop-VM -Name URI-PL -TurnOff -Force"
                   --power-on  "powershell -NoProfile -Command Start-VM -Name URI-PL"
Usage (local): python scripts/phase2close_powerloss_harness.py simulate --iterations 10 --out <dir>
"""
from __future__ import annotations

import argparse
import json
import os
import random
import re
import socket
import sqlite3
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STEPS = ("submitted", "admitted", "intents", "ended")
RANK = {s: i for i, s in enumerate(STEPS)}
FAKE = ROOT / "tests" / "phase2a" / "helpers" / "fake_executor.py"


# ---------------------------------------------------------------------------------------------- verification (pure)
def ledger_facts(ledger_path, boot_prefix=None):
    """Read-only facts of a ledger file: integrity, per-task highest durable step, attempts in flight."""
    db = sqlite3.connect(f"file:{ledger_path}?mode=ro", uri=True)
    try:
        integrity = db.execute("PRAGMA integrity_check").fetchone()[0]
        like = (boot_prefix or "") + "%"
        tasks = {r[0]: r[1] for r in db.execute("SELECT task_id, state FROM task WHERE task_id LIKE ?", (like,))}
        steps = {t: "submitted" for t in tasks}
        for (t,) in db.execute("SELECT DISTINCT task_id FROM admission WHERE task_id LIKE ?", (like,)):
            steps[t] = "admitted"
        for (t,) in db.execute("SELECT DISTINCT task_id FROM effect_intent WHERE task_id LIKE ?", (like,)):
            steps[t] = "intents"
        for (t,) in db.execute("SELECT DISTINCT task_id FROM attempt WHERE status IN ('ENDED','FENCED') AND task_id LIKE ?", (like,)):
            steps[t] = "ended"
        orphans = []
        for aid, t, st in db.execute("SELECT attempt_id, task_id, status FROM attempt WHERE status IN ('SPAWNING','RUNNING')"):
            has_adm = db.execute("SELECT 1 FROM admission WHERE attempt_id=?", (aid,)).fetchone() is not None
            has_int = db.execute("SELECT 1 FROM effect_intent WHERE attempt_id=?", (aid,)).fetchone() is not None
            if not (has_adm and has_int):
                orphans.append({"attempt_id": aid, "task_id": t, "status": st, "admission": has_adm, "intents": has_int})
        in_flight = [r[0] for r in db.execute("SELECT task_id FROM task WHERE state IN ('RUNNING','RECOVERING')")]
        return {"integrity": integrity, "tasks": tasks, "steps": steps, "orphan_attempts": orphans, "in_flight_before_recovery": in_flight}
    finally:
        db.close()


def compare(acked: dict, present: dict) -> list:
    """acked/present: task_id -> highest step. Returns every acknowledged step that is missing after the cut."""
    lost = []
    for task, step in sorted(acked.items()):
        have = present.get(task)
        if have is None or RANK[have] < RANK[step]:
            lost.append({"task_id": task, "acked": step, "present": have})
    return lost


def unclean_shutdown_witnessed(ready_msg, report_msg):
    """D8 (operational qualification, 2026-10-08): the GUEST's own operating system must have recorded that the boot
    which acknowledged the work ended WITHOUT a clean shutdown: a System-log Kernel-Power 41 or EventLog 6008 event
    created after that boot's `ready` (both times on the guest clock), and a later OS boot time. A guest shutdown,
    a reboot, or a host that never cut anything leaves no such event. None when the record carries no witness (a
    SIMULATED series); False when it does and the witness is missing. This is evidence from a second, independent
    source; it is still not proof that the HYPERVISOR cut the power, so the owner's attestation stays required."""
    if not isinstance(report_msg, dict) or "os_witness" not in report_msg:
        return None
    w = report_msg.get("os_witness")
    t0 = (ready_msg or {}).get("guest_wall")
    if not isinstance(w, dict) or isinstance(t0, bool) or not isinstance(t0, (int, float)):
        return False
    events = w.get("unclean_event_times")
    boot_time = w.get("boot_time")
    if not isinstance(events, list) or isinstance(boot_time, bool) or not isinstance(boot_time, (int, float)):
        return False
    return boot_time > t0 and any(isinstance(e, (int, float)) and not isinstance(e, bool) and e > t0 for e in events)


def build_row(i, boot, delay_s, acked: dict, report: dict, ready_msg=None, report_msg=None) -> dict:
    """The iteration row exactly as the campaign writes it (shared with `replay_series`, so the two cannot drift)."""
    lost = compare(acked, report.get("steps") or {})
    return {"iteration": i, "boot": boot, "delay_s": delay_s, "acked_tasks": len(acked),
            "acked_ended": sum(1 for s_ in acked.values() if s_ == "ended"), "lost": lost,
            "integrity": report.get("integrity"), "orphans": len(report.get("orphan_attempts") or []),
            "still_in_flight": report.get("still_in_flight"), "relaunched": report.get("relaunched_by_recovery"),
            "os_unclean_shutdown": unclean_shutdown_witnessed(ready_msg, report_msg),
            "verdict": iteration_verdict(acked, report, lost)}


def build_summary(label, power_method, iterations, rows, report_sync) -> dict:
    """The series summary exactly as the campaign writes it, minus the wall-clock `finished` stamp."""
    summary = {"label": label, "power_method": power_method, "iterations_requested": iterations, "iterations_run": len(rows),
               "passed": sum(1 for r in rows if r.get("verdict") == "PASS"),
               "failed": sum(1 for r in rows if r.get("verdict") != "PASS"),
               "lost_acknowledged_steps": sum(len(r.get("lost") or []) for r in rows),
               "synchronous": sorted(x for x in report_sync if x)}
    # D2: a series verdict is never a qualification. Only `assess` combines a FULL series and a NORMAL control, and even
    # then the result waits for the owner's attestation that the power method was a real hypervisor power cut.
    if label == "SIMULATED":
        summary["verdict"] = "SIMULATED_ONLY_NOT_A_QUALIFICATION"
    else:
        summary["verdict"] = "SERIES_ALL_PASS" if summary["failed"] == 0 and summary["iterations_run"] == iterations else "SERIES_FAIL"
        summary["note"] = "A series verdict is not a qualification; run `assess` with a FULL series and a NORMAL control."
    return summary


def report_invariants_hold(report: dict) -> bool:
    """D4 (closure review round 4): the guest's own `invariants_ok` flag is NOT trusted alone. Each invariant is checked
    from the report's facts: (b) integrity_check == "ok", (c) no orphan SPAWNING/RUNNING attempt, (d) nothing still in
    flight after recovery, (e) nothing relaunched by recovery; the facts must be present (a list, not missing)."""
    return (report.get("invariants_ok") is True and report.get("integrity") == "ok"
            and report.get("orphan_attempts") == [] and report.get("still_in_flight") == []
            and report.get("relaunched_by_recovery") == [])


def iteration_verdict(acked: dict, report: dict, lost: list) -> str:
    """D2 (closure review round 1): an iteration in which the guest acknowledged nothing proves nothing."""
    if not acked:
        return "NO_ACKED_WORK"
    return "PASS" if not lost and report_invariants_hold(report) else "FAIL"


def verify(ledger_path, boot_prefix=None, recover=True):
    """Full guest-side verification of the ledger left by the previous boot (prefix = that boot's task-id prefix)."""
    if not Path(ledger_path).is_file():
        return {"ledger": "ABSENT"}
    facts = ledger_facts(ledger_path, boot_prefix)
    out = {"integrity": facts["integrity"], "steps": facts["steps"], "orphan_attempts": facts["orphan_attempts"],
           "in_flight_before_recovery": facts["in_flight_before_recovery"]}
    if recover and facts["integrity"] == "ok":
        from uri_supervisor.supervisor import Supervisor
        sup = Supervisor(ledger_path, run_recovery=False)
        try:
            results = sup.recover_all()
            L = sup.ledger
            still = [r[0] for r in L.q("SELECT task_id FROM task WHERE state IN ('RUNNING','RECOVERING')")]
            relaunched = [r[0] for r in L.q("SELECT DISTINCT task_id FROM attempt WHERE epoch=? AND task_id NOT LIKE ?",
                                            (sup.epoch, "unused-%"))]
            out.update(recovery_decisions=len(results), still_in_flight=still, relaunched_by_recovery=relaunched,
                       durability=L.durability_report())
        finally:
            sup.close()
    out["invariants_ok"] = (out["integrity"] == "ok" and not out["orphan_attempts"]
                            and not out.get("still_in_flight") and not out.get("relaunched_by_recovery"))
    return out


# ---------------------------------------------------------------------------------------------- guest
class Acker:
    def __init__(self, host, port):
        self.sock = socket.create_connection((host, port), timeout=10)
        self.sock.settimeout(None)
        self.lock = threading.Lock()

    def send(self, obj):
        with self.lock:
            self.sock.sendall((json.dumps(obj, separators=(",", ":")) + "\n").encode())


OS_WITNESS_PS = ("$e = @(Get-WinEvent -FilterHashtable @{LogName='System'; Id=41,6008; StartTime=(Get-Date).AddDays(-3)} "
                 "-MaxEvents 20 -ErrorAction SilentlyContinue | ForEach-Object { [int64]($_.TimeCreated.ToUniversalTime() - "
                 "[datetime]'1970-01-01').TotalSeconds }); $b = [int64]((Get-CimInstance Win32_OperatingSystem).LastBootUpTime"
                 ".ToUniversalTime() - [datetime]'1970-01-01').TotalSeconds; @{events=$e; boot=$b} | ConvertTo-Json -Compress")


def os_witness():
    """D8: the guest OS's own record of unclean shutdowns (Kernel-Power 41, EventLog 6008) and its last boot time, read
    from the System event log at boot. Read-only; a failure is reported, never hidden."""
    try:
        p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", OS_WITNESS_PS], capture_output=True,
                           text=True, timeout=60, stdin=subprocess.DEVNULL)
        data = json.loads(p.stdout.strip() or "{}")
        events = data.get("events") or []
        events = [events] if isinstance(events, (int, float)) else events
        return {"unclean_event_times": sorted(int(e) for e in events if isinstance(e, (int, float)))[-20:],
                "boot_time": data.get("boot"), "source": "System log Kernel-Power 41 / EventLog 6008"}
    except Exception as exc:  # noqa: BLE001
        return {"error": type(exc).__name__}


def guest(a):
    ledger = Path(a.ledger)
    ledger.parent.mkdir(parents=True, exist_ok=True)
    counter = ledger.with_name("boot_counter.txt")
    previous = int(counter.read_text().strip()) if counter.exists() else 0
    boot = previous + 1
    with open(counter, "w") as fh:            # the boot number is written durably BEFORE any workload
        fh.write(str(boot))
        fh.flush()
        os.fsync(fh.fileno())
    ack = Acker(a.host, a.port)
    report = verify(str(ledger), boot_prefix=f"pl-b{previous}-") if previous else {"ledger": "FIRST_BOOT"}
    msg = {"type": "report", "boot": boot, "previous_boot": previous, "synchronous": a.synchronous, "report": report}
    if not a.no_os_witness:
        msg["os_witness"] = os_witness()
    ack.send(msg)
    from uri_supervisor.executors import GENERIC_NDJSON
    from uri_supervisor.supervisor import Supervisor
    from dataclasses import replace
    sup = Supervisor(str(ledger))
    if a.synchronous == "NORMAL":               # negative control ONLY: weaken durability on purpose
        sup.ledger._db.execute("PRAGMA synchronous=NORMAL")
    if not sup.ledger.q("SELECT 1 FROM resource_pool WHERE name='slot'"):
        sup.registry.create_pool("slot", 1)
    if not sup.ledger.q("SELECT 1 FROM executor_registration WHERE executor_id='plfake'"):
        sup.registry.register_executor(replace(GENERIC_NDJSON, executor_id="plfake"), capabilities=("run",), claims={"slot": 1},
                                       quota_pools=(), preemptible=False, version="pl-1")
    ack.send({"type": "ready", "boot": boot, "durability": sup.ledger.durability_report(), "guest_wall": time.time()})
    work = ledger.parent / "work"
    work.mkdir(exist_ok=True)
    seq = 0
    while True:
        seq += 1
        tid = f"pl-b{boot}-{seq:06d}"
        target = work / f"{tid}.txt"
        sup.submit_task(tid, "powerloss", {"seq": seq}, authorization={"scope": {"workspace": str(work)}},
                        effects=[{"op_class": "local_write", "operation": "write", "target": str(target), "paths": [str(target)]}],
                        postconditions=[{"kind": "file_exists", "spec": {"path": str(target)}}],
                        requirements={"capabilities": ["run"]})
        ack.send({"type": "ack", "boot": boot, "task_id": tid, "step": "submitted"})
        adm = sup.admit_next(only_task_id=tid)
        if adm is None:
            ack.send({"type": "note", "boot": boot, "task_id": tid, "note": "NOT_ADMITTED"})
            continue
        ack.send({"type": "ack", "boot": boot, "task_id": tid, "step": "admitted"})
        sup.declare_intents(adm)
        ack.send({"type": "ack", "boot": boot, "task_id": tid, "step": "intents"})
        sup.run_attempt(adm, cwd=str(work), resolved_executable=sys.executable,
                        extra_argv=[str(FAKE), "--scenario", "ok_write", "--path", str(target), "--content", tid],
                        timeout_s=60, inactivity_s=30)
        ack.send({"type": "ack", "boot": boot, "task_id": tid, "step": "ended"})


# ---------------------------------------------------------------------------------------------- host
class AckLog:
    """Host-side record of every guest message: append + fsync per line, so the host's own crash loses nothing."""

    def __init__(self, path):
        self.path = Path(path)
        self.fh = open(self.path, "a", encoding="utf-8")
        self.lock = threading.Lock()
        self.reports = {}
        self.ready = {}
        self.acked = {}          # boot -> {task_id: highest step}

    def add(self, msg):
        with self.lock:
            self.fh.write(json.dumps(msg, separators=(",", ":")) + "\n")
            self.fh.flush()
            os.fsync(self.fh.fileno())
            t = msg.get("type")
            if t == "ack":
                cur = self.acked.setdefault(msg["boot"], {})
                if RANK[msg["step"]] >= RANK.get(cur.get(msg["task_id"]), -1):
                    cur[msg["task_id"]] = msg["step"]
            elif t == "report":
                self.reports[msg["boot"]] = msg
            elif t == "ready":
                self.ready[msg["boot"]] = msg


def serve(port, log: AckLog):
    srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    srv.bind(("0.0.0.0" if port else "127.0.0.1", port))
    srv.listen(8)

    def client(conn):
        buf = b""
        with conn:
            while True:
                try:
                    chunk = conn.recv(65536)
                except OSError:
                    return
                if not chunk:
                    return
                buf += chunk
                while b"\n" in buf:
                    line, buf = buf.split(b"\n", 1)
                    try:
                        log.add(json.loads(line))
                    except ValueError:
                        pass

    def loop():
        while True:
            try:
                conn, _ = srv.accept()
            except OSError:
                return
            threading.Thread(target=client, args=(conn,), daemon=True).start()
    threading.Thread(target=loop, daemon=True).start()
    return srv


def wait_for(pred, timeout):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if pred():
            return True
        time.sleep(0.2)
    return False


def campaign(out, iterations, power_off, power_on, min_s, max_s, boot_timeout, port, label, power_method=None):
    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    log = AckLog(out / "acks.jsonl")
    srv = serve(port, log)
    port = srv.getsockname()[1]
    rows, rng = [], random.Random()
    try:
        power_on(port)
        if not wait_for(lambda: 1 in log.ready, boot_timeout):
            raise SystemExit("GUEST_NEVER_READY (boot 1)")
        for i in range(1, iterations + 1):
            boot = max(log.ready)
            delay = rng.uniform(min_s, max_s)
            time.sleep(delay)
            off_ok = power_off()
            acked = dict(log.acked.get(boot, {}))
            if off_ok is False:
                rows.append({"iteration": i, "boot": boot, "delay_s": round(delay, 3), "verdict": "POWER_OFF_COMMAND_FAILED"})
                break
            if power_on(port) is False:
                rows.append({"iteration": i, "boot": boot, "delay_s": round(delay, 3), "verdict": "POWER_ON_COMMAND_FAILED"})
                break
            if not wait_for(lambda: (boot + 1) in log.reports, boot_timeout):
                rows.append({"iteration": i, "boot": boot, "delay_s": round(delay, 3), "verdict": "NO_REPORT"})
                break
            rows.append(build_row(i, boot, round(delay, 3), acked, log.reports[boot + 1]["report"], log.ready.get(boot),
                                  log.reports[boot + 1]))
            (out / "iterations.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
            if not wait_for(lambda: (boot + 1) in log.ready, boot_timeout):
                rows.append({"iteration": i + 1, "verdict": "GUEST_NEVER_READY"})
                break
    finally:
        try:
            power_off()
        except Exception:  # noqa: BLE001
            pass
        srv.close()
    summary = build_summary(label, power_method, iterations, rows, {m.get("synchronous") for m in log.reports.values()})
    summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    (out / "summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    (out / "iterations.json").write_text(json.dumps(rows, indent=1), encoding="utf-8")
    print(json.dumps(summary, indent=1))
    return summary


def _shell_ok(cmd, timeout):
    try:
        return subprocess.run(cmd, shell=True, check=False, stdin=subprocess.DEVNULL, timeout=timeout).returncode == 0
    except subprocess.TimeoutExpired:
        return False


def host(a):
    s = campaign(a.out, a.iterations, lambda: _shell_ok(a.power_off, 120), lambda _port: _shell_ok(a.power_on, 300),
                 a.min_s, a.max_s, a.boot_timeout, a.port, "VM_SERIES",
                 power_method={"power_off": a.power_off, "power_on": a.power_on})
    return 0 if s["verdict"] == "SERIES_ALL_PASS" else 1


MIN_FULL_ITERATIONS = 200


def load_raw(series_dir):
    """Parse the host's raw record (`acks.jsonl`). Returns (acked per boot, reports per boot, ready per boot, problems).
    Every structural rule a complete campaign obeys is checked: unique report/ready per boot, contiguous boots, report
    B+1 names `previous_boot` B, acknowledgements only for a boot that was ready."""
    acked, reports, ready, problems = {}, {}, {}, []
    with open(Path(series_dir) / "acks.jsonl", encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            m = json.loads(line)
            t = m.get("type")
            b = m.get("boot")
            if type(b) is not int:
                problems.append(f"line {n}: boot is not an integer")
                continue
            if t == "ack":
                if b not in ready:
                    problems.append(f"line {n}: acknowledgement for boot {b} before it was ready")
                if m.get("step") not in RANK:
                    problems.append(f"line {n}: unknown step")
                    continue
                cur = acked.setdefault(b, {})
                if RANK[m["step"]] >= RANK.get(cur.get(m["task_id"]), -1):
                    cur[m["task_id"]] = m["step"]
            elif t == "report":
                if b in reports:
                    problems.append(f"line {n}: second report for boot {b}")
                if m.get("previous_boot") != b - 1:
                    problems.append(f"line {n}: report for boot {b} names previous_boot {m.get('previous_boot')!r}")
                reports[b] = m
            elif t == "ready":
                if b in ready:
                    problems.append(f"line {n}: second ready for boot {b}")
                if b not in reports:
                    problems.append(f"line {n}: boot {b} ready before its report")
                ready[b] = m
    if sorted(ready) != list(range(1, len(ready) + 1)) or sorted(reports) != list(range(1, len(reports) + 1)):
        problems.append("boots are not contiguous from 1")
    return acked, reports, ready, problems


def replay_series(series_dir) -> dict:
    """D4 (closure review rounds 2-3): rebuild the series from the raw host record with the campaign's OWN row and
    summary builders. The caller compares the rebuild with the recorded files field by field."""
    acked, reports, ready, problems = load_raw(series_dir)
    rows = []
    for b in sorted(ready):
        if b + 1 in reports:
            rows.append(build_row(len(rows) + 1, b, None, acked.get(b, {}), reports[b + 1].get("report") or {}, ready.get(b),
                                  reports[b + 1]))
    if rows and (rows[-1]["boot"] + 1) not in ready:
        problems.append(f"the last report (boot {rows[-1]['boot'] + 1}) has no following ready record: truncated")
    guest_sync = sorted({m.get("synchronous") for m in reports.values() if m.get("synchronous")})
    ledger_sync = sorted({(m.get("durability") or {}).get("synchronous") for m in ready.values() if m.get("durability")})
    return {"rows": rows, "iterations": rows, "problems": problems, "report_sync": {m.get("synchronous") for m in reports.values()},
            "guest_synchronous": guest_sync, "ledger_synchronous": ledger_sync,
            "passed": sum(1 for r in rows if r["verdict"] == "PASS"),
            "lost_acknowledged_steps": sum(len(r["lost"]) for r in rows)}


# D7 / method (closure review round 5): the power-off command must be a recognised hypervisor HARD power-off form.
# This raises the bar; it cannot prove the command was run against the right VM, so owner attestation stays required.
KNOWN_HARD_OFF = (
    re.compile(r"\bstop-vm\b.*-turnoff\b", re.I),                  # Hyper-V: Stop-VM -TurnOff
    re.compile(r"\bvboxmanage(\.exe)?\s+controlvm\s+\S+\s+poweroff\b", re.I),   # VirtualBox
    re.compile(r"\bvmrun(\.exe)?\b.*\bstop\b.*\bhard\b", re.I),    # VMware Workstation
    re.compile(r"\bvirsh\s+destroy\b", re.I),                       # libvirt / KVM
)


def _real_power_method(pm) -> bool:
    return (isinstance(pm, dict) and set(pm) == {"power_off", "power_on"}
            and all(isinstance(v, str) and v.strip() and "simulat" not in v.lower() for v in pm.values())
            and any(rx.search(pm["power_off"]) for rx in KNOWN_HARD_OFF))


def assess_series(series_dir, want_sync) -> tuple:
    """Load one series directory, rebuild it from `acks.jsonl`, and list every reason it cannot be used: the recorded
    `iterations.json` and `summary.json` must equal the rebuild exactly (only `delay_s`, which only the host knew, and
    the `finished` stamp are taken from the record, and must be well-formed). Returns (facts, reasons)."""
    d = Path(series_dir)
    reasons = []
    try:
        summary = json.loads((d / "summary.json").read_text(encoding="utf-8"))
        rows = json.loads((d / "iterations.json").read_text(encoding="utf-8"))
        facts = replay_series(d)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return {}, [f"{d.name}: series record unreadable ({type(exc).__name__})"]
    if not isinstance(summary, dict) or not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        return {}, [f"{d.name}: series record malformed"]
    reasons += [f"{d.name}: raw record: {p_}" for p_ in facts["problems"]]
    if summary.get("label") != "VM_SERIES":
        reasons.append(f"{d.name}: label {summary.get('label')!r} is not a VM series")
    if not _real_power_method(summary.get("power_method")):
        reasons.append(f"{d.name}: power method is not a recorded power-off/power-on pair with a recognised hypervisor hard power-off")
    # D7 (closure review round 5): a usable series is COMPLETE: it ran exactly what was requested.
    if summary.get("iterations_requested") != len(facts["rows"]) or len(rows) != len(facts["rows"]):
        reasons.append(f"{d.name}: incomplete series ({len(facts['rows'])} replayed of {summary.get('iterations_requested')!r} requested)")
    if facts["guest_synchronous"] != [want_sync] or facts["ledger_synchronous"] != [want_sync]:
        reasons.append(f"{d.name}: guest/ledger synchronous {facts['guest_synchronous']}/{facts['ledger_synchronous']} != [{want_sync!r}]")
    if not facts["rows"]:
        reasons.append(f"{d.name}: no replayable iteration")
    # D8: every VM iteration must carry the guest OS's own unclean-shutdown witness (see unclean_shutdown_witnessed).
    unwitnessed = [f["iteration"] for f in facts["rows"] if f.get("os_unclean_shutdown") is not True]
    if summary.get("label") == "VM_SERIES" and unwitnessed:
        reasons.append(f"{d.name}: {len(unwitnessed)} iteration(s) without a guest unclean-shutdown witness "
                       f"(Kernel-Power 41 / EventLog 6008 after the boot's ready), first {unwitnessed[:5]}")
    rebuilt = []
    for r, f in zip(rows, facts["rows"]):
        delay = r.get("delay_s")
        rebuilt.append({**f, "delay_s": delay})
        if isinstance(delay, bool) or not isinstance(delay, (int, float)) or delay < 0:
            reasons.append(f"{d.name}: iteration {f['iteration']} has no valid delay_s")
    if rows != rebuilt or len(rows) != len(facts["rows"]):
        reasons.append(f"{d.name}: iterations.json differs from the rebuild of the raw record")
    expected = build_summary(summary.get("label"), summary.get("power_method"), summary.get("iterations_requested"),
                             rebuilt, facts["report_sync"])
    recorded = {k: v for k, v in summary.items() if k != "finished"}
    if recorded != expected:
        diff = sorted(k for k in set(recorded) | set(expected) if recorded.get(k) != expected.get(k))
        reasons.append(f"{d.name}: summary.json differs from the rebuild in {diff}")
    facts["recorded_verdict"] = summary.get("verdict")
    return facts, reasons


def assess(full_dir, control_dir) -> dict:
    """The only place a power-loss verdict is formed (D2), computed from the RAW records (D4). Sufficient evidence
    needs a FULL series of >= 200 replayed iterations, every one PASS with acknowledged work, guest and ledger at
    `synchronous` FULL, AND a NORMAL control whose replay loses at least one acknowledged step. Even then the result
    waits for the owner's attestation that the recorded power method was a real hypervisor power cut."""
    full, reasons = assess_series(full_dir, "FULL")
    control, creasons = assess_series(control_dir, "NORMAL")
    reasons += creasons
    if full:
        if len(full["rows"]) < MIN_FULL_ITERATIONS:
            reasons.append(f"full: {len(full['rows'])} < {MIN_FULL_ITERATIONS} replayed iterations")
        if full["passed"] != len(full["rows"]):
            reasons.append(f"full: {len(full['rows']) - full['passed']} replayed iteration(s) did not pass")
        if full.get("recorded_verdict") != "SERIES_ALL_PASS":
            reasons.append(f"full: recorded series verdict {full.get('recorded_verdict')!r} is not SERIES_ALL_PASS")
    if control and control["lost_acknowledged_steps"] < 1:
        reasons.append("control: the replay lost no acknowledged step; the rig cannot detect loss")
    verdict = "EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION" if not reasons else "INSUFFICIENT"
    return {"verdict": verdict, "reasons": reasons, "qualified": False,
            "full": {k: full.get(k) for k in ("passed", "lost_acknowledged_steps", "guest_synchronous")} | {"iterations": len(full.get("iterations") or [])} if full else None,
            "control": {k: control.get(k) for k in ("passed", "lost_acknowledged_steps", "guest_synchronous")} | {"iterations": len(control.get("iterations") or [])} if control else None,
            "power_method_attestation_required": True,
            "note": "computed from acks.jsonl; the power-off command only matches a recognised hard-off FORM and every iteration carries the guest OS's own unclean-shutdown event (D8); neither proves the hypervisor cut THIS VM's power; qualified is always false here: PA-11 becomes PASS only by the owner's recorded attestation"}


def local_power(out, ledger, synchronous):
    """SIMULATED power functions: start a local guest process / kill its process tree. Plumbing only."""
    from uri_supervisor import winproc
    state = {"proc": None}

    def power_on(port):
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
        state["proc"] = subprocess.Popen([sys.executable, "-I", "-B", str(Path(__file__).resolve()), "guest", "--ledger", str(ledger),
                                          "--host", "127.0.0.1", "--port", str(port), "--synchronous", synchronous, "--no-os-witness"],
                                         cwd=str(ROOT), stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                         stderr=open(Path(out) / "guest_stderr.txt", "ab"), env=env)
        return True

    def power_off():
        p = state["proc"]
        if p is not None and p.poll() is None:
            if winproc.IS_WINDOWS:
                subprocess.run(["taskkill", "/F", "/T", "/PID", str(p.pid)], capture_output=True, stdin=subprocess.DEVNULL)
            else:  # pragma: no cover
                p.kill()
            p.wait(30)
        return True
    return power_off, power_on


def simulate(a):
    """Process-kill stand-in for the hypervisor: proves the plumbing (acks, verify, compare, recovery) only."""
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    power_off, power_on = local_power(out, out / "guest" / "ledger.db", a.synchronous)
    s = campaign(out, a.iterations, power_off, power_on, a.min_s, a.max_s, a.boot_timeout, 0, "SIMULATED",
                 power_method={"simulated": "local process-tree kill"})
    return 0 if s["failed"] == 0 and s["iterations_run"] == a.iterations else 1


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="role", required=True)
    g = sub.add_parser("guest")
    g.add_argument("--ledger", required=True)
    g.add_argument("--host", required=True)
    g.add_argument("--port", type=int, required=True)
    g.add_argument("--synchronous", choices=("FULL", "NORMAL"), default="FULL")
    g.add_argument("--no-os-witness", action="store_true", help="local simulation only: do not read the System event log")
    h = sub.add_parser("host")
    h.add_argument("--port", type=int, default=47710)
    h.add_argument("--iterations", type=int, default=200)
    h.add_argument("--out", required=True)
    h.add_argument("--power-off", required=True)
    h.add_argument("--power-on", required=True)
    h.add_argument("--min-s", type=float, default=2.0)
    h.add_argument("--max-s", type=float, default=20.0)
    h.add_argument("--boot-timeout", type=float, default=600.0)
    x = sub.add_parser("assess")
    x.add_argument("--full", required=True, help="output DIRECTORY of the FULL series (acks.jsonl, iterations.json, summary.json)")
    x.add_argument("--control", required=True, help="output DIRECTORY of the NORMAL control series")
    x.add_argument("--out", default=None)
    v = sub.add_parser("verify")
    v.add_argument("--ledger", required=True)
    v.add_argument("--prefix", default=None)
    v.add_argument("--no-recover", action="store_true")
    s = sub.add_parser("simulate")
    s.add_argument("--iterations", type=int, default=10)
    s.add_argument("--out", required=True)
    s.add_argument("--synchronous", choices=("FULL", "NORMAL"), default="FULL")
    s.add_argument("--min-s", type=float, default=1.0)
    s.add_argument("--max-s", type=float, default=4.0)
    s.add_argument("--boot-timeout", type=float, default=120.0)
    a = ap.parse_args()
    if a.role == "guest":
        return guest(a)
    if a.role == "host":
        return host(a)
    if a.role == "simulate":
        return simulate(a)
    if a.role == "assess":
        res = assess(a.full, a.control)
        if a.out:
            Path(a.out).write_text(json.dumps(res, indent=1), encoding="utf-8")
        print(json.dumps(res, indent=1))
        return 0 if res["verdict"] != "INSUFFICIENT" else 1
    print(json.dumps(verify(a.ledger, a.prefix, recover=not a.no_recover), indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
