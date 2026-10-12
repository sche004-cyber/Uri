"""Ledger: durability config, append-only, mechanical invariants, busy writers, disk-full, crash around tx boundaries."""
import json
import os
import sqlite3
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from uri_supervisor.ledger import Ledger, LedgerBusy, LedgerRefused, LedgerWriteFailed

ROOT = Path(__file__).resolve().parents[2]


def refused(fn, code):
    with pytest.raises(LedgerRefused) as ei:
        fn()
    assert code in str(ei.value), str(ei.value)


def test_durability_pragmas_are_wal_full(env):
    rep = env.L.durability_report()
    assert rep["journal_mode"] == "wal" and rep["synchronous"] == "FULL" and rep["foreign_keys"]


def test_every_new_connection_is_full(tmp_path):
    a = Ledger(tmp_path / "a.db")
    a.close()
    b = Ledger(tmp_path / "a.db")
    assert b.durability_report()["synchronous"] == "FULL"


def _populate(env, tmp_path):
    target = tmp_path / "pop.txt"
    env.task("pop", effects=[{"op_class": "local_write", "operation": "w", "target": str(target), "paths": [str(target)]}],
             postconditions=[{"kind": "file_exists", "spec": {"path": str(target)}}])
    a = env.sup.admit_next()
    env.run(a, "ok_write", path=str(target))
    assert env.state("pop") == "COMPLETE"
    L = env.L
    intent = L.q1("SELECT intent_id FROM effect_intent LIMIT 1")[0]
    L._db.execute("INSERT INTO user_decision(task_id,choice,principal,decided_at_us,recorded_at_us) VALUES ('pop','abandon','u',1,1)")
    L._db.execute("INSERT INTO effect_observation(intent_id,task_id,status,basis,observed_at_us,recorded_at_us,recorded_by) "
                  "VALUES (?,'pop','UNKNOWN','t',1,1,'supervisor')", (intent,))


@pytest.mark.parametrize("table", ["event", "admission", "effect_intent", "stream_event", "evidence", "postcondition",
                                   "postcondition_result", "completion_record", "recovery_decision", "user_decision",
                                   "effect_observation", "stream_interpretation", "scheduler_epoch"])
def test_append_only_tables_reject_update_and_delete(env, tmp_path, table):
    _populate(env, tmp_path)
    L = env.L
    row = L.q1(f"SELECT rowid FROM {table} LIMIT 1")
    assert row is not None, f"{table} unexpectedly empty after a full lifecycle"
    with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        L._db.execute(f"DELETE FROM {table} WHERE rowid=?", (row[0],))
    with pytest.raises(sqlite3.IntegrityError, match="APPEND_ONLY"):
        L._db.execute(f"UPDATE {table} SET rowid=rowid WHERE rowid=?", (row[0],))


def test_illegal_transitions_are_refused_by_the_database(env):
    env.task("t")
    L = env.L
    for bad in ("COMPLETE", "UNCERTAIN", "RETRY_SAFE", "RECOVERING"):
        with pytest.raises(sqlite3.IntegrityError):
            L._db.execute("UPDATE task SET state=? WHERE task_id='t'", (bad,))


def test_complete_requires_a_completion_record(env):
    env.task("t")
    a = env.sup.admit_next()
    with pytest.raises(sqlite3.IntegrityError, match="COMPLETE_REQUIRES_COMPLETION_RECORD"):
        env.L._db.execute("UPDATE task SET state='COMPLETE' WHERE task_id='t'")


def test_verified_completion_record_requires_passing_required_postconditions(env, tmp_path):
    env.task("t", effects=[{"op_class": "local_write", "operation": "w", "paths": [str(tmp_path / "nope")]}],
             postconditions=[{"kind": "file_exists", "spec": {"path": str(tmp_path / "nope")}}])
    with pytest.raises(sqlite3.IntegrityError, match="POSTCONDITION_NOT_PROVEN"):
        env.L._db.execute("INSERT INTO completion_record(task_id,kind,basis_json,recorded_at_us) VALUES ('t','verified','{}',1)")


def test_pass_result_requires_uri_verified_evidence(env):
    env.task("t", effects=[{"op_class": "local_write", "operation": "w"}], postconditions=[{"kind": "file_exists", "spec": {"path": "x"}}])
    L = env.L
    ev = L._db.execute("INSERT INTO evidence(task_id,source,kind,payload,occurred_at_us,recorded_at_us,recorded_by) "
                       "VALUES ('t','executor_report','claim','{}',1,1,'recovery')").lastrowid
    pc = L.q1("SELECT postcondition_id FROM postcondition WHERE task_id='t'")[0]
    with pytest.raises(sqlite3.IntegrityError, match="PASS_REQUIRES_VERIFIED_EVIDENCE"):
        L._db.execute("INSERT INTO postcondition_result(postcondition_id,task_id,status,evidence_id,checked_at_us) VALUES (?, 't','PASS',?,1)",
                      (pc, ev))


def test_terminal_success_postcondition_cannot_complete_a_task_with_effects(env):
    refused(lambda: env.task("t", effects=[{"op_class": "local_write", "operation": "w"}], postconditions=[{"kind": "terminal_success"}]),
            "TERMINAL_SUCCESS_ONLY_FOR_READ_TASKS")


def test_task_without_postcondition_or_effect_envelope_is_refused(env):
    refused(lambda: env.sup.submit_task("a", "u", {}, authorization={}, effects=[], postconditions=[{"kind": "file_exists"}]), "NO_EFFECT_ENVELOPE")
    refused(lambda: env.sup.submit_task("b", "u", {}, authorization={}, effects=[{"op_class": "read", "operation": "x"}],
                                        postconditions=[]), "NO_REQUIRED_POSTCONDITION")


def test_idempotent_write_requires_key(env):
    refused(lambda: env.task("t", effects=[{"op_class": "idem_write", "operation": "w"}]), "IDEMPOTENT_WRITE_REQUIRES_KEY")


def test_no_spawn_without_admission_or_intent(env):
    """Rules A and B at the database level, bypassing every Python guard."""
    env.task("t")
    L = env.L
    a = env.sup.admit_next()
    with pytest.raises(sqlite3.IntegrityError, match="NO_DURABLE_EFFECT_INTENT"):
        L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (a.attempt_id,))
    # fabricate an attempt that never went through admission
    L._db.execute("BEGIN")
    try:
        att = L._db.execute("INSERT INTO attempt(task_id,attempt_no,executor_id,registration_id,status,epoch,admitted_at_us) "
                            "VALUES ('t',9,'fake',1,'ADMITTED',1,1)").lastrowid
        L._db.execute("INSERT INTO effect_intent(task_id,attempt_id,op_class,operation,params_hash,declared_at_us,recorded_at_us) "
                      "VALUES ('t',?,'read','x','h',1,1)", (att,)) if False else None
        with pytest.raises(sqlite3.IntegrityError, match="NO_DURABLE_ADMISSION"):
            L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (att,))
    finally:
        L._db.execute("ROLLBACK")


def test_stale_fence_cannot_declare_intent_or_record_attempt_evidence(env):
    env.task("t")
    a = env.sup.admit_next()
    L = env.L
    L._db.execute("UPDATE attempt SET status='FENCED' WHERE attempt_id=?", (a.attempt_id,))
    with pytest.raises(sqlite3.IntegrityError, match="STALE_FENCE"):
        L._db.execute("INSERT INTO effect_intent(task_id,attempt_id,op_class,operation,params_hash,declared_at_us,recorded_at_us) "
                      "VALUES ('t',?,'read','x','h',1,1)", (a.attempt_id,))
    with pytest.raises(sqlite3.IntegrityError, match="STALE_FENCE"):
        L._db.execute("INSERT INTO evidence(task_id,attempt_id,source,kind,payload,occurred_at_us,recorded_at_us,recorded_by) "
                      "VALUES ('t',?,'executor_report','x','{}',1,1,'attempt')", (a.attempt_id,))


def test_superseded_attempt_cannot_write_after_newer_fence(env):
    env.task("t", max_attempts=5)
    a1 = env.sup.admit_next()
    r = env.run(a1, "error_claim")
    assert env.state("t") == "RETRY_SAFE"
    a2 = env.sup.admit_next()
    assert a2.attempt_id > a1.attempt_id
    with pytest.raises(sqlite3.IntegrityError, match="STALE_FENCE"):
        env.L._db.execute("INSERT INTO evidence(task_id,attempt_id,source,kind,payload,occurred_at_us,recorded_at_us,recorded_by) "
                          "VALUES ('t',?,'executor_report','terminal_success_claim','{}',1,1,'attempt')", (a1.attempt_id,))


def test_fencing_tokens_strictly_increase_and_never_reuse(env):
    ids = []
    env.sup.registry.set_capacity("slot", 10)
    for i in range(5):
        env.task(f"t{i}")
        ids.append(env.sup.admit_next().attempt_id)
    assert ids == sorted(set(ids))


def test_retry_must_reuse_key_and_params(env, tmp_path):
    env.task("t", effects=[{"op_class": "idem_write", "operation": "put", "params": {"v": 1}, "idempotency_key": "K1"}],
             postconditions=[{"kind": "file_exists", "spec": {"path": str(tmp_path / "zz")}}], max_attempts=4)
    a1 = env.sup.admit_next()
    env.sup.declare_intents(a1)
    first = env.L.q1("SELECT intent_id FROM effect_intent WHERE attempt_id=?", (a1.attempt_id,))[0]
    # simulate attempt end -> retry-safe, then second attempt
    env.L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (a1.attempt_id,))
    env.L._db.execute("UPDATE attempt SET status='ENDED' WHERE attempt_id=?", (a1.attempt_id,))
    from uri_supervisor import recovery
    recovery.reconcile(env.sup, "t", a1.attempt_id)
    assert env.state("t") == "RETRY_SAFE"
    d = env.L.q1("SELECT action FROM recovery_decision WHERE task_id='t'")
    assert d["action"] == "RETRY_SAME_KEY"
    a2 = env.sup.admit_next()
    with pytest.raises(sqlite3.IntegrityError, match="RETRY_PARAMS_MISMATCH"):
        env.L._db.execute("INSERT INTO effect_intent(task_id,attempt_id,op_class,operation,params_hash,idempotency_key,retry_of,declared_at_us,recorded_at_us) "
                          "VALUES ('t',?,'idem_write','put','DIFFERENT','K1',?,1,1)", (a2.attempt_id, first))
    with pytest.raises(sqlite3.IntegrityError, match="RETRY_PARAMS_MISMATCH"):
        env.L._db.execute("INSERT INTO effect_intent(task_id,attempt_id,op_class,operation,params_hash,idempotency_key,retry_of,declared_at_us,recorded_at_us) "
                          "VALUES ('t',?,'idem_write','put',?,'K2',?,1,1)", (a2.attempt_id, env.L.q1("SELECT params_hash FROM effect_intent WHERE intent_id=?", (first,))[0], first))
    env.sup.declare_intents(a2)       # the supervisor's own re-declaration satisfies the trigger
    assert env.L.q1("SELECT retry_of,idempotency_key FROM effect_intent WHERE attempt_id=?", (a2.attempt_id,))["retry_of"] == first


def test_pool_capacity_invariant_enforced_by_database(env):
    L = env.L
    L._db.execute("BEGIN")
    try:
        L._db.execute("INSERT INTO attempt(task_id,attempt_no,executor_id,registration_id,status,epoch,admitted_at_us) SELECT 'x',1,'f',1,'ADMITTED',1,1 WHERE 0")
    finally:
        L._db.execute("ROLLBACK")
    env.task("a"); env.task("b"); env.task("c")
    env.sup.admit_next(); env.sup.admit_next()
    assert env.sup.admit_next() is None          # slot capacity 2
    with pytest.raises(sqlite3.IntegrityError, match="POOL_CAPACITY_EXCEEDED"):
        L._db.execute("INSERT INTO claim(task_id,attempt_id,pool,amount,epoch,state,lease_ns,lease_deadline_mono_ns,acquired_at_us) "
                      "VALUES ('c',1,'slot',1,1,'held',1,1,1)")
    with pytest.raises(sqlite3.IntegrityError, match="CAPACITY_BELOW_HELD"):
        L._db.execute("UPDATE resource_pool SET capacity=1 WHERE name='slot'")


def test_claim_history_is_immutable(env):
    env.task("a")
    env.sup.admit_next()
    L = env.L
    with pytest.raises(sqlite3.IntegrityError):
        L._db.execute("DELETE FROM claim")
    with pytest.raises(sqlite3.IntegrityError, match="CLAIM_IMMUTABLE_FIELDS"):
        L._db.execute("UPDATE claim SET amount=99")


def test_uncertain_exit_requires_new_observed_evidence_or_user_decision(env, tmp_path):
    target = tmp_path / "t.txt"
    import hashlib
    full = hashlib.sha256(b"FULL").hexdigest()
    env.task("t", effects=[{"op_class": "local_write", "operation": "w", "paths": [str(target)]}],
             postconditions=[{"kind": "file_hash", "spec": {"path": str(target), "sha256": full}}])
    a = env.sup.admit_next()
    env.run(a, "partial_write_then_die", path=str(target))      # leaves "PART" behind: state changed, postcondition unproven
    assert env.state("t") == "NEEDS_USER"
    L = env.L
    for to in ("RETRY_SAFE", "FAILED", "COMPLETE"):
        with pytest.raises(sqlite3.IntegrityError):
            L._db.execute("UPDATE task SET state=? WHERE task_id='t'", (to,))
        with pytest.raises(sqlite3.IntegrityError, match="UNCERTAIN_EXIT|COMPLETE_REQUIRES"):
            L._db.execute("UPDATE task SET state=?, basis_kind='evidence', basis_ref=1 WHERE task_id='t'", (to,))   # OLD evidence id
    # executor-sourced evidence (a claim) is not new URI-observed evidence
    ev = L._db.execute("INSERT INTO evidence(task_id,source,kind,payload,occurred_at_us,recorded_at_us,recorded_by) "
                       "VALUES ('t','executor_report','x','{}',1,1,'recovery')").lastrowid
    with pytest.raises(sqlite3.IntegrityError, match="UNCERTAIN_EXIT"):
        L._db.execute("UPDATE task SET state='FAILED', basis_kind='evidence', basis_ref=? WHERE task_id='t'", (ev,))


def test_busy_writer_surfaces_typed_error_and_leaves_no_partial_state(tmp_path):
    p = tmp_path / "b.db"
    a = Ledger(p, busy_timeout_ms=200)
    b = Ledger(p, busy_timeout_ms=200)
    holder = threading.Event(); release = threading.Event()

    def hold():
        with a.tx():
            a.emit("hold")
            holder.set()
            release.wait(5)
    t = threading.Thread(target=hold); t.start(); holder.wait(5)
    try:
        before = b.q1("SELECT COUNT(*) FROM event")[0]
        with pytest.raises(LedgerBusy):
            with b.tx():
                b.emit("should-not-exist")
    finally:
        release.set(); t.join()
    kinds = [r[0] for r in b.q("SELECT kind FROM event")]
    assert "hold" in kinds and "should-not-exist" not in kinds and before == b.q1("SELECT COUNT(*) FROM event")[0] - 1


def test_many_concurrent_writers_all_commit_exactly_once(tmp_path):
    p = tmp_path / "c.db"
    Ledger(p).close()
    errors, n = [], 40

    def w(i):
        try:
            L = Ledger(p, busy_timeout_ms=15000)
            with L.tx():
                L.emit("w", payload={"i": i})
            L.close()
        except Exception as e:
            errors.append(e)
    ts = [threading.Thread(target=w, args=(i,)) for i in range(n)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errors
    L = Ledger(p)
    seen = sorted(json.loads(r[0])["i"] for r in L.q("SELECT payload FROM event WHERE kind='w'"))
    assert seen == list(range(n))


def test_disk_full_is_a_typed_failure_and_rolls_back(tmp_path):
    L = Ledger(tmp_path / "f.db")
    pages = L.q1("PRAGMA page_count")[0]
    L._db.execute(f"PRAGMA max_page_count={pages + 2}")       # SQLite's own disk-full simulation (SQLITE_FULL)
    with pytest.raises(LedgerWriteFailed):
        with L.tx():
            for i in range(5000):
                L.emit("filler", payload={"pad": "x" * 500, "i": i})
    L._db.execute("PRAGMA max_page_count=1073741823")
    assert L.q1("SELECT COUNT(*) FROM event WHERE kind='filler'")[0] == 0     # whole transaction rolled back


def test_disk_full_blocks_spawn_nothing_proceeds(env):
    """If the durable intent cannot be written, no process may be spawned."""
    env.task("t", effects=[{"op_class": "read", "operation": "x" * 40000}])
    a = env.sup.admit_next()
    L = env.L
    L._db.execute("PRAGMA max_page_count=%d" % L.q1("PRAGMA page_count")[0])    # freeze the database size
    with pytest.raises(LedgerWriteFailed):
        env.run(a, "ok_read")
    L._db.execute("PRAGMA max_page_count=1073741823")
    row = L.q1("SELECT pid,status FROM attempt WHERE attempt_id=?", (a.attempt_id,))
    assert row["pid"] is None and row["status"] == "ADMITTED"
    assert L.q1("SELECT COUNT(*) FROM effect_intent")[0] == 0 and L.q1("SELECT COUNT(*) FROM stream_event")[0] == 0


def test_committed_intent_survives_hard_process_exit(tmp_path):
    """A child commits an intent-bearing transaction then dies with os._exit (no cleanup). Reopen sees it."""
    code = ("import sys,os;sys.path.insert(0,%r);from uri_supervisor.ledger import Ledger;"
            "L=Ledger(%r);\nwith L.tx():\n L.emit('intent.committed',payload={'k':1})\n"
            "L._db.execute('BEGIN IMMEDIATE');L.emit('intent.uncommitted');os._exit(9)") % (str(ROOT), str(tmp_path / "d.db"))
    r = subprocess.run([sys.executable, "-c", code], capture_output=True)
    assert r.returncode == 9, r.stderr
    L = Ledger(tmp_path / "d.db")
    kinds = [x[0] for x in L.q("SELECT kind FROM event")]
    assert "intent.committed" in kinds and "intent.uncommitted" not in kinds


def test_replay_of_same_submit_is_idempotent_and_refused(env):
    env.task("t")
    with pytest.raises(LedgerRefused):
        env.task("t")                     # same task id cannot be admitted twice
    assert env.L.q1("SELECT COUNT(*) FROM task WHERE task_id='t'")[0] == 1


def test_ledger_unsupported_schema_version_fails_closed(tmp_path):
    p = tmp_path / "v.db"
    Ledger(p).close()
    c = sqlite3.connect(p); c.execute("PRAGMA user_version=99"); c.close()
    from uri_supervisor.ledger import LedgerError
    with pytest.raises(LedgerError, match="SCHEMA_VERSION_UNSUPPORTED"):
        Ledger(p)
