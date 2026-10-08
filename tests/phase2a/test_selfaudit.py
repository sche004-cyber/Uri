"""Regression tests for defects found by the author's own adversarial self-audit (NOT an independent audit).

Each test was written to fail against the pre-repair code; see docs/plans/PHASE2A_REPORT.md section J for the
defect list and which tests failed before repair.
"""
import json
import sqlite3
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest

from phase2a.conftest import Env, FAKE
from uri_supervisor import crashpoints, postconditions, winproc
from uri_supervisor.clock import FakeClock
from uri_supervisor.executors import GENERIC_NDJSON, ExecutorSpecError
from uri_supervisor.ledger import LedgerRefused
from uri_supervisor.stream import LineSplitter


class Crash(BaseException):
    pass


def mk(tmp_path, clock=None, pools=None, **reg):
    e = Env(tmp_path, clock=clock)
    e.setup_pools(**(pools or {"slot": 3}))
    e.register(**({"claims": {"slot": 1}} | reg))
    return e


# D1: breaker feedback must commit atomically with the recovery decision ---------------------------------
def test_d1_quota_breaker_is_committed_with_the_decision_even_if_supervisor_dies_right_after(tmp_path, monkeypatch):
    e = Env(tmp_path, clock=FakeClock())
    e.setup_pools(slot=3, prov=1)
    e.register(claims={"slot": 1, "prov": 1}, quota_pools=("prov",))
    e.task("t")
    adm = e.sup.admit_next()
    real = crashpoints.hit

    def boom(name):
        if name == "recovery_after_decision":
            raise Crash()
        real(name)
    monkeypatch.setattr(crashpoints, "hit", boom)
    with pytest.raises(Crash):
        e.run(adm, "quota")
    monkeypatch.setattr(crashpoints, "hit", real)
    assert e.L.task("t")["state"] == "RETRY_SAFE"
    assert e.L.q1("SELECT breaker_state FROM resource_pool WHERE name='prov'")[0] == "open"


# D2: authority clock must never run backwards -----------------------------------------------------------
def test_d2_wall_clock_rollback_cannot_revive_an_expired_authorization(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk)
    now = clk.wall_us()
    e.sup.submit_task("t", "u", {}, authorization={"valid_until_us": now + 10_000_000}, effects=[{"op_class": "read", "operation": "x"}],
                      postconditions=[{"kind": "terminal_success"}], requirements={"capabilities": ["run"]})
    clk.advance(20)
    assert e.sup.admit_next() is None                      # expired
    clk.set_wall(now)                                      # clock stepped back into the validity window
    assert e.sup.admit_next() is None, "an expired grant came back to life after a wall-clock step"


# D3: a terminal-success claim from a process that exited non-zero is not completion ---------------------------
def test_d3_terminal_success_claim_with_nonzero_exit_does_not_complete_read_task(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    r = e.run(e.sup.admit_next(), "done_then_exit3")
    assert r.exit_code == 3
    assert e.state("t") == "RETRY_SAFE"


def test_d3b_terminal_then_hang_killed_still_counts_for_read_task(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    r = e.run(e.sup.admit_next(), "terminal_hang", path=str(tmp_path / "z"), terminal_grace_s=1)
    assert r.end_reason == "terminal_then_hang_killed" and e.state("t") == "COMPLETE"


# D4: leaving UNCERTAIN needs evidence ABOUT THE EFFECT, not any new observation --------------------------------
def test_d4_unrelated_new_observation_cannot_release_an_uncertain_task(tmp_path):
    e = mk(tmp_path)
    e.task("t", effects=[{"op_class": "external", "operation": "pay"}],
           postconditions=[{"kind": "external_object", "spec": {"reconciler": "none", "key": "k"}}])
    e.run(e.sup.admit_next(), "error_claim")
    assert e.state("t") in ("UNCERTAIN", "NEEDS_USER")
    ev = e.L._db.execute("INSERT INTO evidence(task_id,source,kind,payload,occurred_at_us,recorded_at_us,recorded_by) "
                         "VALUES ('t','uri_observed','process_identity','{}',1,1,'recovery')").lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="UNCERTAIN_EXIT"):
        e.L._db.execute("UPDATE task SET state='RETRY_SAFE', basis_kind='evidence', basis_ref=? WHERE task_id='t'", (ev,))


# D5: authorization scope is enforced where Phase 2A can understand it ---------------------------------------------
def test_d5_scope_limits_op_classes_executors_and_workspace(tmp_path):
    e = mk(tmp_path)
    ws = tmp_path / "ws"; ws.mkdir()
    kw = dict(postconditions=[{"kind": "file_exists", "spec": {"path": "x"}}], requirements={"capabilities": ["run"]})
    with pytest.raises(LedgerRefused, match="OP_CLASS_NOT_AUTHORIZED"):
        e.sup.submit_task("a", "u", {}, authorization={"scope": {"allowed_op_classes": ["read"]}},
                          effects=[{"op_class": "local_write", "operation": "w", "paths": [str(ws / "f")]}], **kw)
    with pytest.raises(LedgerRefused, match="EFFECT_OUTSIDE_WORKSPACE"):
        e.sup.submit_task("b", "u", {}, authorization={"scope": {"workspace": str(ws)}},
                          effects=[{"op_class": "local_write", "operation": "w", "paths": [str(tmp_path / "elsewhere" / "f")]}], **kw)
    with pytest.raises(LedgerRefused, match="EFFECT_OUTSIDE_WORKSPACE"):
        e.sup.submit_task("b2", "u", {}, authorization={"scope": {"workspace": str(ws)}},
                          effects=[{"op_class": "local_write", "operation": "w", "paths": [str(ws / ".." / "escape")]}], **kw)
    e.sup.submit_task("c", "u", {}, authorization={"scope": {"allowed_executors": ["someone_else"]}},
                      effects=[{"op_class": "read", "operation": "x"}], postconditions=[{"kind": "terminal_success"}],
                      requirements={"capabilities": ["run"]})
    assert e.sup.admit_next() is None                       # executor not in scope => never admitted
    e.sup.submit_task("d", "u", {}, authorization={"scope": {"workspace": str(ws)}}, effects=[{"op_class": "read", "operation": "x"}],
                      postconditions=[{"kind": "terminal_success"}], requirements={"capabilities": ["run"]})
    adm = e.sup.admit_next()
    assert adm.task_id == "d"
    with pytest.raises(LedgerRefused, match="CWD_OUTSIDE_WORKSPACE"):
        e.sup.run_attempt(adm, cwd=str(tmp_path), resolved_executable=sys.executable, extra_argv=[FAKE, "--scenario", "ok_read"])


# D6: unprovable fingerprints never compare equal --------------------------------------------------------------------
def test_d6_oversized_directory_cannot_prove_absence_of_effect(tmp_path, monkeypatch):
    d = tmp_path / "big"; d.mkdir()
    for i in range(6):
        (d / f"f{i}").write_text("x")
    monkeypatch.setattr(postconditions, "MAX_FINGERPRINT_ENTRIES", 3)
    e = mk(tmp_path)
    e.task("t", effects=[{"op_class": "local_write", "operation": "w", "paths": [str(d)]}],
           postconditions=[{"kind": "file_exists", "spec": {"path": str(d / "never")}}])
    e.run(e.sup.admit_next(), "error_claim")
    assert e.state("t") == "NEEDS_USER"                    # untouched directory, but URI could not PROVE that


# D7: argv bypass-flag refusal covers the FINAL argv and substrings ---------------------------------------------------
@pytest.mark.parametrize("extra", [["--dangerously-skip-permissions"], ["-c", 'sandbox_mode="danger-full-access"'], ["--yolo=true"]])
def test_d7_forbidden_flags_in_final_argv_are_refused_and_nothing_spawns(tmp_path, extra):
    e = mk(tmp_path)
    e.task("t")
    adm = e.sup.admit_next()
    r = e.sup.run_attempt(adm, cwd=str(tmp_path), resolved_executable=sys.executable, extra_argv=[FAKE, "--scenario", "ok_read", *extra])
    assert r.end_reason == "spawn_failed"
    assert e.L.q1("SELECT pid FROM attempt WHERE attempt_id=?", (adm.attempt_id,))[0] is None


# D8: executor-supplied session ids cannot inject argv on resume ------------------------------------------------------
def test_d8_hostile_session_id_is_never_stored_or_used_for_resume(tmp_path):
    e = Env(tmp_path)
    e.setup_pools(slot=3)
    e.register(claims={"slot": 1}, spec=replace(GENERIC_NDJSON, resume_argv=("--resume", "{session}")))
    e.task("t")
    e.run(e.sup.admit_next(), "evil_session")
    assert e.L.q1("SELECT session_id FROM attempt")[0] is None
    d = e.L.q1("SELECT action FROM recovery_decision")
    assert d["action"] == "RETRY_FRESH"
    adm2 = e.sup.admit_next()
    spec = GENERIC_NDJSON
    with pytest.raises(ExecutorSpecError):
        replace(spec, resume_argv=("--resume", "{session}")).build_argv(session="--yolo", resolved_executable="x")


# D9: unbounded line without newline must not exhaust memory or become authoritative ------------------------------
def test_d9_oversize_line_is_fragmented_incomplete_and_bounded():
    sp = LineSplitter(max_line_bytes=1024)
    out = []
    for _ in range(100):
        out += sp.feed(b"A" * 700)
    assert len(sp._tail) <= 1024 + 700
    assert out and all(complete is False for _, complete in out)
    tail_end = sp.feed(b'{"type":"done","ok":true}\n')
    assert all(complete is False for _, complete in tail_end), "remainder of an oversize line must not parse as a fresh complete line"
    nxt = sp.feed(b'{"type":"done","ok":true}\n')
    assert nxt == [(b'{"type":"done","ok":true}\n', True)]


# D10: lease heartbeat must not fsync every poll -------------------------------------------------------------------------
def test_d10_lease_renewal_is_throttled(tmp_path, monkeypatch):
    e = mk(tmp_path)
    e.task("t")
    calls = []
    real = e.sup.admitter.renew
    monkeypatch.setattr(e.sup.admitter, "renew", lambda aid: (calls.append(time.monotonic()), real(aid))[1])
    e.run(e.sup.admit_next(), "sleep", sleep=2.5, timeout_s=2.5)
    assert len(calls) <= 4, len(calls)


# D11: expired same-epoch leases of dead run-loops are reaped via recovery ----------------------------------------------
def test_d11_reap_expired_leases_reconciles_abandoned_attempts_and_frees_capacity(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk, pools={"slot": 1})
    e.task("t1"); e.task("t2")
    a = e.sup.admit_next()                                 # admitted, nobody runs it (run-loop died)
    assert e.sup.admit_next() is None
    clk.advance(61)
    assert e.sup.reap_expired_leases() == [a.attempt_id]
    assert e.state("t1") == "RETRY_SAFE"
    assert e.sup.admit_next() is not None                  # capacity came back, with proof
    # a live attempt (known to this supervisor) is never reaped by deadline alone
    clk.advance(1000)
    assert e.sup.reap_expired_leases(skip_active={e.L.q1("SELECT MAX(attempt_id) FROM attempt")[0]}) == []


# D12: escalation inside the unresolved group must not reset the 'new evidence' watermark --------------------------------
def test_d12_escalation_keeps_evidence_watermark(tmp_path):
    e = mk(tmp_path)
    e.task("t", effects=[{"op_class": "external", "operation": "pay", "context": {"reconciler": "r", "lookup": "k"}}],
           postconditions=[{"kind": "external_object", "spec": {"reconciler": "r", "key": "k"}}])
    e.sup.reconcilers["r"] = lambda k, c: ("UNKNOWN", "x")
    e.run(e.sup.admit_next(), "error_claim")
    before = e.L.task("t")["enter_evidence_hwm"]
    assert e.state("t") == "UNCERTAIN"
    e.L.transition("t", "NEEDS_USER", "ESCALATED")
    assert e.L.task("t")["enter_evidence_hwm"] == before


# coverage: supervisor death kills grandchildren too ---------------------------------------------------------------------
def test_executor_grandchildren_die_when_supervisor_dies(tmp_path):
    from phase2a.test_crash import child, cfg_for
    pidfile = tmp_path / "gc.pid"
    cfg, _ = cfg_for(tmp_path, scenario="grandchild", sleep=300, pidfile=str(pidfile))
    cfg["effects"] = [{"op_class": "read", "operation": "x"}]
    cfg["postconditions"] = [{"kind": "terminal_success"}]
    r = child(cfg, crash_at="mid_stream")
    assert r.returncode == 137
    deadline = time.time() + 10
    while time.time() < deadline and not pidfile.exists():
        time.sleep(0.1)
    if pidfile.exists():
        gc = int(pidfile.read_text())
        deadline = time.time() + 10
        while time.time() < deadline and winproc.process_create_time(gc) is not None:
            time.sleep(0.1)
        assert winproc.process_create_time(gc) is None


# D15: run_attempt twice on the same admission must not duplicate durable intents ------------------------------------
def test_d15_run_attempt_twice_is_refused_before_touching_the_ledger(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    adm = e.sup.admit_next()
    e.run(adm, "ok_read")
    n = e.L.q1("SELECT COUNT(*) FROM effect_intent")[0]
    with pytest.raises(LedgerRefused, match="ATTEMPT_ALREADY_STARTED"):
        e.run(adm, "ok_read")
    assert e.L.q1("SELECT COUNT(*) FROM effect_intent")[0] == n


# D16: job names carry an unguessable nonce so another local process cannot squat a name recovery will terminate -----
def test_d16_job_name_is_unguessable_and_squatter_job_is_not_terminated(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    adm = e.sup.admit_next()
    e.run(adm, "ok_read")
    name = e.L.q1("SELECT job_name FROM attempt WHERE attempt_id=?", (adm.attempt_id,))[0]
    guessable = winproc.job_name_for(e.L.ledger_id(), adm.attempt_id)
    assert name != guessable and name.startswith(guessable + "-") and len(name) > len(guessable) + 8
    # a squatter holding the GUESSABLE name is untouched by recovery (recovery only ever uses the recorded nonce name)
    sq = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(30)"])
    cp = winproc.spawn_contained([sys.executable, "-c", "import time;time.sleep(30)"], guessable)
    try:
        before = winproc.job_state(guessable)
        assert before[0] and before[1] >= 1
        e.task("u")
        a2 = e.sup.admit_next()
        e.run(a2, "ok_read")
        after = winproc.job_state(guessable)
        assert after[0] and after[1] >= before[1]      # squatter's processes were not terminated
    finally:
        cp.kill(); cp.close(); sq.kill()
