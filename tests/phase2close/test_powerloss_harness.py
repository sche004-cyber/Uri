"""Phase 2 closure: the power-loss harness's own logic (not a durability qualification; see the harness docstring)."""
import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("pl", ROOT / "scripts" / "phase2close_powerloss_harness.py")
pl = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pl)


def test_compare_flags_missing_and_regressed_steps_only():
    acked = {"t1": "ended", "t2": "intents", "t3": "submitted", "t4": "admitted"}
    present = {"t1": "ended", "t2": "admitted", "t4": "ended"}
    lost = pl.compare(acked, present)
    assert lost == [{"task_id": "t2", "acked": "intents", "present": "admitted"},
                    {"task_id": "t3", "acked": "submitted", "present": None}]
    assert pl.compare({}, present) == [] and pl.compare(acked, {**present, "t2": "ended", "t3": "submitted"}) == []


def _ledger_with_one_admitted_task(tmp_path):
    from dataclasses import replace
    from uri_supervisor.executors import GENERIC_NDJSON
    from uri_supervisor.supervisor import Supervisor
    db = tmp_path / "ledger.db"
    sup = Supervisor(str(db))
    sup.registry.create_pool("slot", 1)
    sup.registry.register_executor(replace(GENERIC_NDJSON, executor_id="plfake"), capabilities=("run",), claims={"slot": 1},
                                   quota_pools=(), preemptible=False, version="pl-1")
    sup.submit_task("pl-b1-000001", "t", {}, authorization={"scope": {}}, effects=[{"op_class": "read", "operation": "noop"}],
                    postconditions=[{"kind": "terminal_success"}], requirements={"capabilities": ["run"]})
    adm = sup.admit_next(only_task_id="pl-b1-000001")
    return sup, db, adm


def test_facts_report_the_highest_durable_step(tmp_path):
    sup, db, adm = _ledger_with_one_admitted_task(tmp_path)
    try:
        assert pl.ledger_facts(db, "pl-b1-")["steps"] == {"pl-b1-000001": "admitted"}
        sup.declare_intents(adm)
        facts = pl.ledger_facts(db, "pl-b1-")
        assert facts["steps"] == {"pl-b1-000001": "intents"} and facts["integrity"] == "ok" and facts["orphan_attempts"] == []
        assert pl.ledger_facts(db, "pl-b2-")["steps"] == {}
    finally:
        sup.close()


def test_the_ledger_itself_refuses_spawning_without_a_durable_intent(tmp_path):
    """Invariant (c) is enforced by the ledger's own trigger; the harness check is a second, read-only witness."""
    sup, db, adm = _ledger_with_one_admitted_task(tmp_path)
    sup.close()
    raw = sqlite3.connect(db)
    try:
        with pytest.raises(sqlite3.DatabaseError, match="NO_DURABLE_EFFECT_INTENT"):
            raw.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (adm.attempt_id,))
    finally:
        raw.close()


def test_facts_flag_an_orphan_attempt_in_a_damaged_ledger(tmp_path):
    """If a power cut ever left an attempt SPAWNING/RUNNING without its admission or intents (the trigger above makes
    that impossible in a consistent file), the read-only check must say so and fail the invariants."""
    db = tmp_path / "damaged.db"
    raw = sqlite3.connect(db)
    raw.executescript("""
        CREATE TABLE task(task_id TEXT, state TEXT);
        CREATE TABLE admission(task_id TEXT, attempt_id INTEGER);
        CREATE TABLE effect_intent(task_id TEXT, attempt_id INTEGER);
        CREATE TABLE attempt(attempt_id INTEGER, task_id TEXT, status TEXT);
        INSERT INTO task VALUES ('pl-b1-000001', 'RUNNING');
        INSERT INTO admission VALUES ('pl-b1-000001', 1);
        INSERT INTO attempt VALUES (1, 'pl-b1-000001', 'SPAWNING');
    """)
    raw.commit()
    raw.close()
    out = pl.verify(str(db), "pl-b1-", recover=False)
    assert out["orphan_attempts"] == [{"attempt_id": 1, "task_id": "pl-b1-000001", "status": "SPAWNING", "admission": True, "intents": False}]
    assert out["in_flight_before_recovery"] == ["pl-b1-000001"] and out["invariants_ok"] is False


def test_verify_on_an_absent_ledger_says_so(tmp_path):
    assert pl.verify(str(tmp_path / "none.db")) == {"ledger": "ABSENT"}


def test_simulated_campaign_plumbing_end_to_end(tmp_path):
    """Two process-kill iterations through the real guest workload and the real host logic. SIMULATED: it proves the
    acks, the boot report, the comparison and the recovery checks work; it says nothing about power loss."""
    import subprocess
    out = tmp_path / "sim"
    r = subprocess.run([sys.executable, "-I", str(ROOT / "scripts" / "phase2close_powerloss_harness.py"), "simulate",
                        "--iterations", "2", "--out", str(out), "--min-s", "1.5", "--max-s", "2.5"],
                       cwd=str(ROOT), capture_output=True, text=True, timeout=600, stdin=subprocess.DEVNULL)
    assert r.returncode == 0, (r.stdout[-2000:], r.stderr[-2000:])
    import json
    summary = json.loads((out / "summary.json").read_text())
    rows = json.loads((out / "iterations.json").read_text())
    assert summary["verdict"] == "SIMULATED_ONLY_NOT_A_QUALIFICATION" and summary["passed"] == 2
    assert all(row["integrity"] == "ok" and row["lost"] == [] and row["acked_tasks"] >= 1 for row in rows)


# ---- closure review rounds 1-2, D2/D4: no harness output can be mistaken for a physical qualification, and the
# assessment is recomputed from the raw host record, never from the summary's word ----
import json as _json


PM = {"power_off": "powershell -NoProfile -Command Stop-VM -Name URI-PL -TurnOff -Force",
      "power_on": "powershell -NoProfile -Command Start-VM -Name URI-PL"}


def _series(d, *, n=200, sync="FULL", label="VM_SERIES", lose_at=(), method=PM, tasks=3, requested=None):
    """Write a COHERENT synthetic series directory (raw acks.jsonl + iterations.json + summary.json) in the exact
    shape `campaign` writes, using the harness's own row/summary builders."""
    d.mkdir(parents=True, exist_ok=True)
    msgs, rows = [], []
    msgs.append({"type": "report", "boot": 1, "previous_boot": 0, "synchronous": sync, "report": {"ledger": "FIRST_BOOT"}})
    for b in range(1, n + 1):
        msgs.append({"type": "ready", "boot": b, "durability": {"synchronous": sync}})
        acked = {f"pl-b{b}-{k:06d}": "ended" for k in range(1, tasks + 1)}
        msgs += [{"type": "ack", "boot": b, "task_id": t_, "step": "ended"} for t_ in acked]
        present = dict(acked)
        if b in lose_at:
            present.pop(next(iter(present)))
        report = {"steps": present, "invariants_ok": True, "integrity": "ok", "orphan_attempts": [], "still_in_flight": [],
                  "relaunched_by_recovery": []}
        msgs.append({"type": "report", "boot": b + 1, "previous_boot": b, "synchronous": sync, "report": report})
        rows.append(pl.build_row(b, b, 1.0, acked, report))
    msgs.append({"type": "ready", "boot": n + 1, "durability": {"synchronous": sync}})
    (d / "acks.jsonl").write_text("".join(_json.dumps(m) + chr(10) for m in msgs), encoding="utf-8")
    (d / "iterations.json").write_text(_json.dumps(rows), encoding="utf-8")
    summary = pl.build_summary(label, method, n if requested is None else requested, rows, {sync})
    summary["finished"] = "2026-10-08T00:00:00"
    (d / "summary.json").write_text(_json.dumps(summary), encoding="utf-8")
    return d


def _edit(path, fn):
    data = _json.loads(path.read_text(encoding="utf-8"))
    path.write_text(_json.dumps(fn(data)), encoding="utf-8")


def _edit_raw(d, fn):
    lines = [_json.loads(l) for l in (d / "acks.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    (d / "acks.jsonl").write_text("".join(_json.dumps(m) + chr(10) for m in fn(lines)), encoding="utf-8")


def test_assess_accepts_only_coherent_raw_evidence_and_never_qualifies(tmp_path):
    full = _series(tmp_path / "full")
    control = _series(tmp_path / "ctl", n=5, sync="NORMAL", lose_at=(3,))
    ok = pl.assess(full, control)
    assert ok["verdict"] == "EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION" and ok["qualified"] is False and ok["reasons"] == [], ok
    assert ok["full"]["iterations"] == 200 and ok["control"]["lost_acknowledged_steps"] == 1


def _insufficient(res, why):
    assert res["verdict"] == "INSUFFICIENT" and res["qualified"] is False and any(why in r for r in res["reasons"]), (why, res)


def test_assess_rejects_the_round2_contradictory_summaries(tmp_path):
    """Reviewer probe (round 2): FULL summary claims SERIES_ALL_PASS over 200 failed iterations; NORMAL control has
    zero iterations but claims one lost step. Both must be refused from the raw record."""
    full = _series(tmp_path / "full", lose_at=tuple(range(1, 201)))
    _edit(full / "summary.json", lambda s: {**s, "verdict": "SERIES_ALL_PASS", "passed": 0, "failed": 200, "lost_acknowledged_steps": 200})
    ctl = tmp_path / "ctl"
    ctl.mkdir()
    (ctl / "acks.jsonl").write_text("", encoding="utf-8")
    (ctl / "iterations.json").write_text("[]", encoding="utf-8")
    (ctl / "summary.json").write_text(_json.dumps({"label": "VM_SERIES", "power_method": PM, "iterations_requested": 0,
                                                   "iterations_run": 0, "passed": 0, "failed": 0, "lost_acknowledged_steps": 1,
                                                   "synchronous": ["NORMAL"], "verdict": "SERIES_ALL_PASS"}), encoding="utf-8")
    res = pl.assess(full, ctl)
    _insufficient(res, "did not pass")
    _insufficient(res, "no replayable iteration")
    _insufficient(res, "lost no acknowledged step")


def test_assess_rejects_the_round3_probes(tmp_path):
    """Reviewer probes (round 3), each on an otherwise coherent pair."""
    good_ctl = _series(tmp_path / "c0", n=4, sync="NORMAL", lose_at=(2,))
    cases = []
    d = _series(tmp_path / "r1")
    _edit(d / "summary.json", lambda s: {**s, "verdict": "SERIES_FAIL", "failed": 200, "synchronous": ["NORMAL"]})
    cases.append((d, good_ctl, "summary.json differs"))
    cases.append((_series(tmp_path / "r2", method={"simulated": "local process kill"}), good_ctl, "power method"))
    cases.append((_series(tmp_path / "r2b", method={"power_off": "simulated kill", "power_on": "start"}), good_ctl, "power method"))
    ctl = _series(tmp_path / "c3", n=4, sync="NORMAL", lose_at=(2,))
    _edit(ctl / "iterations.json", lambda rows: [{**r, "lost": [{**x, "task_id": "pl-b9-999999"} for x in r["lost"]]} for r in rows])
    cases.append((_series(tmp_path / "r3"), ctl, "iterations.json differs"))
    d = _series(tmp_path / "r4")
    _edit_raw(d, lambda ms: ms[:-1])                                         # final ready removed (clean truncation)
    cases.append((d, good_ctl, "truncated"))
    d = _series(tmp_path / "r5")
    _edit_raw(d, lambda ms: [({**m, "previous_boot": 999} if m["type"] == "report" and m["boot"] == 2 else m) for m in ms])
    cases.append((d, good_ctl, "previous_boot"))
    d = _series(tmp_path / "r6")
    _edit_raw(d, lambda ms: ms + [{"type": "report", "boot": 5, "previous_boot": 4, "synchronous": "FULL", "report": {}}])
    cases.append((d, good_ctl, "second report"))
    d = _series(tmp_path / "r7")
    _edit_raw(d, lambda ms: [{"type": "ack", "boot": 300, "task_id": "x", "step": "ended"}] + ms)
    cases.append((d, good_ctl, "before it was ready"))
    for f, c, why in cases:
        _insufficient(pl.assess(f, c), why)


def test_assess_refuses_every_tampered_or_weak_series(tmp_path):
    good_ctl = _series(tmp_path / "c0", n=4, sync="NORMAL", lose_at=(2,))
    cases = []
    d = _series(tmp_path / "f1", lose_at=(7,))                               # raw loss, iterations.json says PASS
    _edit(d / "iterations.json", lambda rows: [{**r, "verdict": "PASS", "lost": []} for r in rows])
    cases.append((d, good_ctl, "iterations.json differs"))
    d = _series(tmp_path / "f2")
    _edit(d / "summary.json", lambda s: {**s, "passed": 201})
    cases.append((d, good_ctl, "summary.json differs"))
    cases.append((_series(tmp_path / "f3", n=199), good_ctl, "199 < 200"))
    cases.append((_series(tmp_path / "f4", sync="NORMAL"), good_ctl, "synchronous"))
    cases.append((_series(tmp_path / "f5", label="SIMULATED"), good_ctl, "not a VM series"))
    cases.append((_series(tmp_path / "f6", method=None), good_ctl, "power method"))
    d = _series(tmp_path / "f7")
    _edit(d / "iterations.json", lambda rows: rows + [{"iteration": 201, "boot": 201, "verdict": "POWER_OFF_COMMAND_FAILED"}])
    cases.append((d, good_ctl, "iterations.json differs"))
    d = _series(tmp_path / "f8")
    (d / "acks.jsonl").unlink()
    cases.append((d, good_ctl, "unreadable"))
    full_ok = _series(tmp_path / "f9")
    cases.append((full_ok, _series(tmp_path / "c1", n=4, sync="NORMAL"), "lost no acknowledged step"))
    cases.append((full_ok, _series(tmp_path / "c2", n=4, sync="FULL", lose_at=(1,)), "synchronous"))
    d = _series(tmp_path / "f10")
    _edit(d / "summary.json", lambda s: {**s, "iterations_requested": 300})
    cases.append((d, good_ctl, "summary.json differs"))
    d = _series(tmp_path / "f11")
    _edit(d / "iterations.json", lambda rows: [{**r, "delay_s": -1} for r in rows])
    cases.append((d, good_ctl, "delay_s"))
    for f, c, why in cases:
        _insufficient(pl.assess(f, c), why)


def test_replay_agrees_with_a_real_campaign_output(tmp_path):
    """REAL local guest (SIMULATED power): the rebuild from the raw record equals the campaign's own iterations.json and
    summary.json; only the SIMULATED label and the simulated power method keep it from being usable."""
    out = tmp_path / "real"
    out.mkdir()
    off, on = pl.local_power(out, out / "guest" / "ledger.db", "FULL")
    pl.campaign(out, 2, off, on, 1.0, 1.5, 120, 0, "SIMULATED", power_method={"simulated": "kill"})
    facts, reasons = pl.assess_series(out, "FULL")
    assert len(facts["rows"]) == 2 and facts["guest_synchronous"] == ["FULL"] and facts["ledger_synchronous"] == ["FULL"]
    assert facts["problems"] == []
    assert reasons == ["real: label 'SIMULATED' is not a VM series",
                       "real: power method is not a recorded power-off/power-on pair with a recognised hypervisor hard power-off"], reasons


def test_a_failed_power_command_stops_the_series_and_fails_it(tmp_path):
    """REAL local guest; the 'power off' reports failure: the series stops with POWER_OFF_COMMAND_FAILED."""
    out = tmp_path / "pf"
    out.mkdir()
    off, on = pl.local_power(out, out / "guest" / "ledger.db", "FULL")

    def failing_off():
        off()                    # really stop the guest so nothing is left running
        return False
    s = pl.campaign(out, 3, failing_off, on, 1.0, 1.5, 120, 0, "VM_SERIES", power_method={"power_off": "test"})
    rows = __import__("json").loads((out / "iterations.json").read_text())
    assert rows[-1]["verdict"] == "POWER_OFF_COMMAND_FAILED" and s["verdict"] == "SERIES_FAIL" and s["iterations_run"] == 1


def test_iteration_verdict_rules():
    ok = {"invariants_ok": True, "integrity": "ok", "orphan_attempts": [], "still_in_flight": [], "relaunched_by_recovery": []}
    assert pl.iteration_verdict({}, ok, []) == "NO_ACKED_WORK"
    assert pl.iteration_verdict({"t": "ended"}, ok, []) == "PASS"
    assert pl.iteration_verdict({"t": "ended"}, ok, [{"task_id": "t"}]) == "FAIL"
    assert pl.iteration_verdict({"t": "ended"}, {"invariants_ok": False}, []) == "FAIL"
    assert pl.iteration_verdict({"t": "ended"}, {}, []) == "FAIL"


def test_assess_rejects_the_round4_probes(tmp_path):
    """Reviewer probes (round 4): a raw report (and the matching row) that records corrupt integrity, an orphan attempt,
    a task still in flight or a relaunch, while claiming invariants_ok, must fail the iteration and the series."""
    good_ctl = _series(tmp_path / "c0", n=4, sync="NORMAL", lose_at=(2,))
    bad_facts = [{"integrity": "*** in database main ***"}, {"orphan_attempts": [{"attempt_id": 1}]},
                 {"still_in_flight": ["pl-b3-000001"]}, {"relaunched_by_recovery": ["pl-b3-000001"]},
                 {"still_in_flight": None}]
    for k, facts in enumerate(bad_facts):
        d = _series(tmp_path / f"r{k}")

        def corrupt(ms, facts=facts):
            out = []
            for m in ms:
                if m["type"] == "report" and m["boot"] == 4:
                    m = {**m, "report": {**m["report"], **facts, "invariants_ok": True}}
                out.append(m)
            return out
        _edit_raw(d, corrupt)
        acks = [_json.loads(l) for l in (d / "acks.jsonl").read_text(encoding="utf-8").splitlines()]
        rep4 = next(m["report"] for m in acks if m["type"] == "report" and m["boot"] == 4)
        acked3 = {m["task_id"]: m["step"] for m in acks if m["type"] == "ack" and m["boot"] == 3}
        _edit(d / "iterations.json", lambda rows: [pl.build_row(r["iteration"], r["boot"], r["delay_s"], acked3, rep4)
                                                   if r["boot"] == 3 else r for r in rows])
        _edit(d / "summary.json", lambda s_: {**pl.build_summary(s_["label"], s_["power_method"], s_["iterations_requested"],
                                              _json.loads((d / "iterations.json").read_text()), {"FULL"}), "finished": s_["finished"]})
        res = pl.assess(d, good_ctl)
        _insufficient(res, "did not pass")
        assert pl.report_invariants_hold(rep4) is False, facts


def test_assess_rejects_the_round5_probes(tmp_path):
    """Reviewer probes (round 5): a self-consistent FULL record whose requested count is not what ran (so its own
    verdict is SERIES_FAIL), and a power method made of arbitrary commands."""
    good_ctl = _series(tmp_path / "c0", n=4, sync="NORMAL", lose_at=(2,))
    for k, req in enumerate((0, 201)):
        d = _series(tmp_path / f"q{k}", requested=req)
        assert _json.loads((d / "summary.json").read_text())["verdict"] == "SERIES_FAIL"
        res = pl.assess(d, good_ctl)
        _insufficient(res, "incomplete series")
        _insufficient(res, "is not SERIES_ALL_PASS")
    _insufficient(pl.assess(_series(tmp_path / "e1", method={"power_off": "echo hello", "power_on": "echo world"}), good_ctl),
                  "recognised hypervisor hard power-off")
    _insufficient(pl.assess(_series(tmp_path / "e2", method={"power_off": "Stop-VM -Name URI-PL", "power_on": "Start-VM URI-PL"}),
                            good_ctl), "recognised hypervisor hard power-off")         # graceful stop, not -TurnOff
    _insufficient(pl.assess(_series(tmp_path / "c5"), _series(tmp_path / "c6", n=4, sync="NORMAL", lose_at=(2,), requested=9)),
                  "incomplete series")


def test_each_recognised_hard_off_form_is_accepted(tmp_path):
    good_ctl = _series(tmp_path / "c0", n=4, sync="NORMAL", lose_at=(2,))
    for k, off in enumerate(("powershell -NoProfile -Command Stop-VM -Name URI-PL -TurnOff -Force",
                             "VBoxManage controlvm URI-PL poweroff",
                             '"C:/Program Files (x86)/VMware/vmrun.exe" stop D:/vm/uri.vmx hard',
                             "virsh destroy uri-pl")):
        res = pl.assess(_series(tmp_path / f"h{k}", method={"power_off": off, "power_on": "start it"}), good_ctl)
        assert res["verdict"] == "EVIDENCE_SUFFICIENT_PENDING_OWNER_ATTESTATION" and res["qualified"] is False, (off, res)
        assert res["power_method_attestation_required"] is True


def test_series_verdicts_never_say_qualified(tmp_path):
    src = (ROOT / "scripts" / "phase2close_powerloss_harness.py").read_text(encoding="utf-8")
    assert "ALL_ITERATIONS_PASS" not in src and "PHYSICAL_VM" not in src and '"qualified": False' in src
