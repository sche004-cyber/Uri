"""Recovery / reconciliation semantics with a real contained subprocess executor."""
import hashlib
import json
import subprocess
import sys
import time

import pytest

from uri_supervisor import recovery, winproc
from uri_supervisor.narration import format_claim, narrate
from uri_supervisor.supervisor import Supervisor
from phase2a.conftest import Env


def dec(env, tid):
    return env.L.q1("SELECT * FROM recovery_decision WHERE task_id=? ORDER BY decision_id DESC LIMIT 1", (tid,))


def write_task(env, tid, target, **kw):
    env.task(tid, effects=[{"op_class": "local_write", "operation": "write", "target": str(target), "paths": [str(target)]}],
             postconditions=[{"kind": "file_exists", "spec": {"path": str(target)}}], **kw)


def test_missing_terminal_event_but_postcondition_proves_effect(env, tmp_path):
    t = tmp_path / "o.txt"
    write_task(env, "t", t)
    r = env.run(env.sup.admit_next(), "no_terminal_after_write", path=str(t))
    assert r.end_reason == "exited_without_terminal_event" and r.exit_code == 0
    assert env.state("t") == "COMPLETE"
    assert dec(env, "t")["reason_code"] == "POSTCONDITIONS_VERIFIED_WITHOUT_TERMINAL_EVENT"


def test_exit_zero_without_terminal_and_no_effect_is_interruption_not_success(env, tmp_path):
    t = tmp_path / "never.txt"
    write_task(env, "t", t)
    r = env.run(env.sup.admit_next(), "no_terminal_nothing")
    assert r.exit_code == 0 and env.state("t") == "RETRY_SAFE"
    d = dec(env, "t")
    assert d["reason_code"] == "EXECUTOR_INTERRUPTED_NO_TERMINAL_EVENT_RETRY_SAFE" and d["action"] == "RETRY_FRESH"


def test_read_task_with_no_terminal_event_is_not_complete(env):
    env.task("t")
    env.run(env.sup.admit_next(), "no_terminal_nothing")
    assert env.state("t") == "RETRY_SAFE"


def test_terminal_event_then_process_hang_is_killed_and_completion_is_verified(env, tmp_path):
    t = tmp_path / "h.txt"
    write_task(env, "t", t)
    t0 = time.monotonic()
    r = env.run(env.sup.admit_next(), "terminal_hang", path=str(t), terminal_grace_s=1)
    assert r.end_reason == "terminal_then_hang_killed" and time.monotonic() - t0 < 20
    assert env.state("t") == "COMPLETE"


def test_truncated_final_event_is_preserved_raw_and_never_authoritative(env, tmp_path):
    t = tmp_path / "tr.txt"
    env.task("t", effects=[{"op_class": "read", "operation": "r"}], postconditions=[{"kind": "terminal_success"}])
    adm = env.sup.admit_next()
    r = env.run(adm, "truncated_terminal", path=str(t))
    assert env.state("t") == "RETRY_SAFE"
    tail = env.L.q1("SELECT * FROM stream_event WHERE attempt_id=? AND complete=0", (adm.attempt_id,))
    assert tail is not None and bytes(tail["raw"]).startswith(b'{"type":"done"')
    assert env.L.q1("SELECT COUNT(*) FROM evidence WHERE kind='terminal_success_claim'")[0] == 0
    assert env.L.q1("SELECT COUNT(*) FROM evidence WHERE kind='truncated_tail_ignored'")[0] == 1


def test_executor_claims_success_but_effect_absent_is_unverified_and_retry_safe(env, tmp_path):
    t = tmp_path / "absent.txt"
    write_task(env, "t", t)
    env.run(env.sup.admit_next(), "claims_success_no_effect")
    assert env.state("t") == "RETRY_SAFE" and dec(env, "t")["reason_code"] == "EXECUTOR_CLAIMED_SUCCESS_NOT_VERIFIED_RETRY_SAFE"
    claims = [format_claim(c) for c in narrate(env.L, "t")]
    assert any("Executor reports completion; URI has not verified it." in c for c in claims)
    assert not any("[URI verified] Task complete" in c for c in claims)


def test_nonidempotent_partial_write_needs_user_and_is_never_auto_retried(env, tmp_path):
    t = tmp_path / "part.txt"
    full = hashlib.sha256(b"FULL").hexdigest()
    env.task("t", effects=[{"op_class": "local_write", "operation": "w", "target": str(t), "paths": [str(t)]}],
             postconditions=[{"kind": "file_hash", "spec": {"path": str(t), "sha256": full}}])
    env.run(env.sup.admit_next(), "partial_write_then_die", path=str(t))
    assert env.state("t") == "NEEDS_USER" and dec(env, "t")["reason_code"] == "LOCAL_WRITE_STATE_CHANGED_UNPROVEN"
    for _ in range(5):
        assert env.sup.admit_next() is None          # never re-admitted
    assert env.L.q1("SELECT COUNT(*) FROM uncertainty WHERE task_id='t' AND resolved_at_us IS NULL")[0] == 1


def test_recovery_twice_yields_same_authoritative_outcome(env, tmp_path):
    t = tmp_path / "x.txt"
    write_task(env, "t", t)
    adm = env.sup.admit_next()
    env.run(adm, "no_terminal_after_write", path=str(t))
    first = dec(env, "t")
    again = recovery.reconcile(env.sup, "t", adm.attempt_id, "restart")
    assert again["decision_id"] == first["decision_id"] and env.state("t") == "COMPLETE"
    assert env.L.q1("SELECT COUNT(*) FROM recovery_decision")[0] == 1
    # and a full restart-recovery pass is a no-op
    assert env.sup.recover_all() == []


def test_idempotent_write_retry_reuses_original_key_and_params(env, tmp_path):
    t = tmp_path / "idem.txt"
    env.task("t", effects=[{"op_class": "idem_write", "operation": "put", "params": {"v": 7}, "idempotency_key": "KEY-1", "target": str(t)}],
             postconditions=[{"kind": "file_exists", "spec": {"path": str(t)}}], max_attempts=3)
    a1 = env.sup.admit_next()
    env.run(a1, "error_claim")
    assert env.state("t") == "RETRY_SAFE" and dec(env, "t")["action"] == "RETRY_SAME_KEY"
    a2 = env.sup.admit_next()
    env.run(a2, "ok_write", path=str(t))
    rows = env.L.q("SELECT idempotency_key,params_hash,retry_of FROM effect_intent ORDER BY intent_id")
    assert len(rows) == 2 and rows[0]["idempotency_key"] == rows[1]["idempotency_key"] == "KEY-1"
    assert rows[0]["params_hash"] == rows[1]["params_hash"] and rows[1]["retry_of"] is not None
    assert env.state("t") == "COMPLETE"


def test_retry_budget_exhaustion_fails_instead_of_looping(env):
    env.task("t", max_attempts=2)
    for _ in range(2):
        a = env.sup.admit_next()
        env.run(a, "error_claim")
    assert env.state("t") == "FAILED" and dec(env, "t")["reason_code"] == "RETRY_BUDGET_EXHAUSTED"


def test_external_effect_without_key_is_never_auto_retried(env):
    env.task("t", effects=[{"op_class": "external", "operation": "send_mail", "params": {"to": "a"}}],
             postconditions=[{"kind": "external_object", "spec": {"reconciler": "mail", "key": "m1"}}])
    env.run(env.sup.admit_next(), "error_claim")
    assert env.state("t") == "NEEDS_USER" and dec(env, "t")["reason_code"] == "EXTERNAL_EFFECT_UNCONFIRMED"
    for _ in range(5):
        assert env.sup.admit_next() is None


def test_external_effect_applied_but_unverified_completion_is_never_repeated(env):
    env.sup.reconcilers["mail"] = lambda key, ctx: ("FOUND", "in outbox") if True else None
    env.task("t", effects=[{"op_class": "external", "operation": "send_mail", "context": {"reconciler": "mail", "lookup": "m1"},
                            "idempotency_key": "K"}],
             postconditions=[{"kind": "file_exists", "spec": {"path": "C:/definitely/not/there"}}])   # postcondition cannot be proven
    env.run(env.sup.admit_next(), "error_claim")
    assert env.state("t") == "UNCERTAIN" and dec(env, "t")["reason_code"] == "EXTERNAL_EFFECT_APPLIED_UNVERIFIED_COMPLETION"
    assert env.sup.admit_next() is None


def test_external_keyed_effect_may_retry_with_same_key(env):
    env.sup.reconcilers["mail"] = lambda key, ctx: ("NOT_FOUND", "not in outbox")
    env.task("t", effects=[{"op_class": "external", "operation": "send_mail", "idempotency_key": "K9", "context": {"reconciler": "mail", "lookup": "m"}}],
             postconditions=[{"kind": "external_object", "spec": {"reconciler": "mail", "key": "m"}}])
    env.run(env.sup.admit_next(), "error_claim")
    assert env.state("t") == "RETRY_SAFE" and dec(env, "t")["action"] == "RETRY_SAME_KEY"


def test_new_evidence_moves_uncertain_task_to_complete_and_requires_it(env):
    state = {"v": "UNKNOWN"}
    env.sup.reconcilers["svc"] = lambda key, ctx: (state["v"], "probe")
    env.task("t", effects=[{"op_class": "external", "operation": "create", "context": {"reconciler": "svc", "lookup": "obj"}}],
             postconditions=[{"kind": "external_object", "spec": {"reconciler": "svc", "key": "obj"}}])
    env.run(env.sup.admit_next(), "error_claim")
    assert env.state("t") in ("UNCERTAIN", "NEEDS_USER")
    assert env.sup.reexamine("t")["changed"] is False and env.state("t") in ("UNCERTAIN", "NEEDS_USER")   # still unknown
    state["v"] = "FOUND"
    assert env.sup.reexamine("t") == {"changed": True, "to": "COMPLETE"}
    row = env.L.task("t")
    assert row["basis_kind"] == "evidence" and row["state"] == "COMPLETE"


def test_user_decision_is_recorded_and_required_for_unproven_exit(env, tmp_path):
    t = tmp_path / "ud.txt"
    full = hashlib.sha256(b"FULL").hexdigest()
    env.task("t", effects=[{"op_class": "local_write", "operation": "w", "target": str(t), "paths": [str(t)]}],
             postconditions=[{"kind": "file_hash", "spec": {"path": str(t), "sha256": full}}])
    env.run(env.sup.admit_next(), "partial_write_then_die", path=str(t))
    assert env.state("t") == "NEEDS_USER"
    did = env.sup.record_user_decision("t", "retry", "alice", "I checked, safe to redo")
    row = env.L.task("t")
    assert row["state"] == "RETRY_SAFE" and row["basis_kind"] == "user_decision" and row["basis_ref"] == did
    assert env.L.q1("SELECT COUNT(*) FROM uncertainty WHERE resolved_at_us IS NOT NULL")[0] == 1
    with pytest.raises(Exception):
        env.sup.record_user_decision("t", "abandon", "alice")      # nothing unresolved any more


def test_pid_reuse_never_signals_unrelated_process(tmp_path):
    """A recorded (pid, create_time) whose live PID has a DIFFERENT creation time is a different process."""
    e = Env(tmp_path)
    e.setup_pools(slot=2); e.register(claims={"slot": 1})
    sleeper = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    try:
        e.task("t")
        a = e.sup.admit_next()
        L = e.L
        e.sup.declare_intents(a)
        real_ct = winproc.process_create_time(sleeper.pid)
        L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (a.attempt_id,))
        L._db.execute("UPDATE attempt SET pid=?, pid_create_time=?, job_name=?, status='RUNNING' WHERE attempt_id=?",
                      (sleeper.pid, real_ct + 10_000_000, "Local\\uri-sup-nonexistent-1", a.attempt_id))
        e.close()                                              # supervisor "crashes" here
        e2 = Env(tmp_path)                                     # restart: recover_all
        assert sleeper.poll() is None, "recovery killed an unrelated process"
        ev = e2.L.q1("SELECT payload FROM evidence WHERE kind='process_identity'")
        assert json.loads(ev[0])["identity"] == "PID_REUSED"
        assert e2.state("t") == "RETRY_SAFE"
        e2.close()
    finally:
        sleeper.kill()


def test_matching_identity_outside_job_is_terminated_by_identity(tmp_path):
    e = Env(tmp_path)
    e.setup_pools(slot=2); e.register(claims={"slot": 1})
    sleeper = subprocess.Popen([sys.executable, "-c", "import time;time.sleep(60)"])
    try:
        e.task("t")
        a = e.sup.admit_next(); L = e.L
        e.sup.declare_intents(a)
        ct = winproc.process_create_time(sleeper.pid)
        L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (a.attempt_id,))
        L._db.execute("UPDATE attempt SET pid=?, pid_create_time=?, job_name=?, status='RUNNING' WHERE attempt_id=?",
                      (sleeper.pid, ct, "Local\\uri-sup-nonexistent-2", a.attempt_id))
        e.close()
        e2 = Env(tmp_path)
        assert sleeper.wait(timeout=10) is not None            # it was ours (identity matched) and is now gone
        assert e2.state("t") == "RETRY_SAFE"
        e2.close()
    finally:
        sleeper.kill()


def test_unverifiable_process_blocks_decision_as_uncertain_and_keeps_claims(tmp_path, monkeypatch):
    e = Env(tmp_path)
    e.setup_pools(slot=2); e.register(claims={"slot": 1})
    e.task("t")
    a = e.sup.admit_next()
    e.sup.declare_intents(a)
    e.L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (a.attempt_id,))
    e.L._db.execute("UPDATE attempt SET pid=4, pid_create_time=1, job_name='Local\\\\x', status='RUNNING' WHERE attempt_id=?", (a.attempt_id,))
    e.close()
    monkeypatch.setattr(winproc, "identity_state", lambda pid, ct: "UNKNOWN")
    e2 = Env(tmp_path)
    assert e2.state("t") == "UNCERTAIN" and dec(e2, "t")["reason_code"] == "PROCESS_NOT_CONFIRMED_DEAD"
    assert e2.L.q1("SELECT COUNT(*) FROM claim WHERE state='held'")[0] == 1          # capacity stays consumed
    e2.close()


def test_stale_attempt_stream_lines_are_quarantined_not_authoritative(env, tmp_path):
    env.task("t")
    adm = env.sup.admit_next()
    reg = env.L.q1("SELECT * FROM executor_registration WHERE registration_id=?", (adm.registration_id,))
    from uri_supervisor.executors import ExecutorSpec
    spec = ExecutorSpec.from_json(json.loads(reg["spec_json"]))
    env.L._db.execute("UPDATE attempt SET status='FENCED' WHERE attempt_id=?", (adm.attempt_id,))
    counters, state = {"stdout": 0, "stderr": 0}, {"terminal": None, "terminal_at": None, "events": 0}
    env.sup._record_lines(adm, spec, "stdout", [(b'{"type":"done","ok":true,"summary":"late"}\n', True)], counters, state)
    row = env.L.q1("SELECT * FROM stream_event WHERE attempt_id=?", (adm.attempt_id,))
    assert row["fence_current"] == 0 and bytes(row["raw"]).startswith(b'{"type":"done"')
    assert env.L.q1("SELECT COUNT(*) FROM evidence WHERE attempt_id=?", (adm.attempt_id,))[0] == 0


def test_spawn_failure_never_ran_and_is_retry_safe(env):
    env.task("t")
    adm = env.sup.admit_next()
    r = env.sup.run_attempt(adm, cwd=str(env.tmp), resolved_executable="C:/no/such/exe.exe", extra_argv=[])
    assert r.end_reason == "spawn_failed" and env.state("t") == "RETRY_SAFE"
    assert env.L.q1("SELECT COUNT(*) FROM claim WHERE state='held'")[0] == 0     # proven never started -> claims released


def test_timeout_kills_whole_tree_including_grandchild(env, tmp_path):
    env.task("t")
    pidfile = tmp_path / "gc.pid"
    r = env.run(env.sup.admit_next(), "grandchild", pidfile=str(pidfile), sleep=60, timeout_s=3, inactivity_s=60)
    assert r.end_reason == "timeout_killed"
    gc = int(pidfile.read_text())
    deadline = time.time() + 5
    while time.time() < deadline and winproc.process_create_time(gc) is not None:
        time.sleep(0.1)
    assert winproc.process_create_time(gc) is None, "grandchild survived executor kill (breakaway)"


def test_free_text_success_cannot_override_failed_structured_command(env):
    env.task("t")
    env.run(env.sup.admit_next(), "text_success_but_failed_command")
    assert env.state("t") == "RETRY_SAFE"
    lines = [format_claim(c) for c in narrate(env.L, "t")]
    assert any("`pytest -q` exited with code 1" in l for l in lines)
    assert any("(unverified)" in l and "[executor says]" in l for l in lines)
    assert not any(l.startswith("[URI verified]") and "success" in l.lower() for l in lines)
    assert not any("Task complete" in l for l in lines)


def test_unicode_and_spaces_in_paths(env, tmp_path):
    d = tmp_path / "папка с пробелами" / "日本語"
    d.mkdir(parents=True)
    t = d / "résumé ✓.txt"
    write_task(env, "t", t)
    env.run(env.sup.admit_next(), "unicode_write", path=str(t), content="héllo ✓")
    assert env.state("t") == "COMPLETE"
    texts = [format_claim(c) for c in narrate(env.L, "t")]
    assert any("готово ✓ 日本語" in x for x in texts)
