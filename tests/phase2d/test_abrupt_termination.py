"""SIMULATED POWER-LOSS / ABRUPT-TERMINATION persistence-boundary test (Phase 2D).

Label, exactly: SIMULATED. The supervisor process is killed with `os._exit` (no cleanup, no flush) at named
transition points while a real child executor runs. This models process death, NOT physical power loss and NOT OS
write reordering: the kernel page cache survives a process kill, so what this test can prove is (a) the ledger's
declared durability configuration (`journal_mode=WAL`, `synchronous=FULL`) is in force and read back, (b) every
fact the supervisor had COMMITTED before the kill is present afterwards, (c) `PRAGMA integrity_check` is `ok`,
(d) restart recovery reaches one decision per in-flight attempt and the Phase 2A invariants hold. Items 1-3(a-d) of
`docs/plans/PHASE2A_POWER_LOSS_TEST_PLAN.md` are exercised this way; the hypervisor power-off (item 2) and the
`synchronous=NORMAL` control (item 4) are NOT EXECUTED here. Physical power-loss qualification remains NOT EXECUTED.
"""
import json
import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from phase2a.test_crash import cfg_for, child, invariants
from uri_supervisor.supervisor import Supervisor

# crash point -> facts that were committed (acknowledged) before the kill and must be on disk afterwards
COMMITTED = {
    "after_submit": ["SELECT COUNT(*) FROM task WHERE task_id='t'"],
    "after_admit_commit": ["SELECT COUNT(*) FROM admission", "SELECT COUNT(*) FROM claim WHERE state='held'"],
    "after_intents": ["SELECT COUNT(*) FROM effect_intent"],
    "after_spawning_marked": ["SELECT COUNT(*) FROM attempt WHERE status='SPAWNING' AND argv_sha256 IS NOT NULL"],
    "after_pid_record": ["SELECT COUNT(*) FROM attempt WHERE pid IS NOT NULL AND pid_create_time IS NOT NULL AND job_name IS NOT NULL"],
    "mid_stream": ["SELECT COUNT(*) FROM stream_event", "SELECT COUNT(*) FROM stream_interpretation"],
    "after_attempt_ended": ["SELECT COUNT(*) FROM attempt WHERE status='ENDED' AND ended_at_us IS NOT NULL"],
    "recovery_before_decision": ["SELECT COUNT(*) FROM evidence WHERE kind='process_identity'"],
}


def raw(db):
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    try:
        return con
    except Exception:
        con.close()
        raise


@pytest.mark.parametrize("point", sorted(COMMITTED))
def test_simulated_abrupt_termination_keeps_every_committed_fact_and_recovers(tmp_path, point):
    cfg, target = cfg_for(tmp_path, scenario="ok_write")
    if point.startswith("recovery_"):
        r = child(cfg, crash_at="after_attempt_ended")
        assert r.returncode == 137, r.stderr[-500:]
        r = child({**cfg, "mode": "recover"}, crash_at=point)
    else:
        r = child(cfg, crash_at=point)
    assert r.returncode == 137, (point, r.stderr[-800:])
    db = Path(cfg["db"])
    # (b) acknowledged commits present, read through a fresh read-only connection (no supervisor, no recovery)
    con = raw(db)
    try:
        for sql in COMMITTED[point]:
            assert con.execute(sql).fetchone()[0] >= 1, (point, sql)
        # (c) structural integrity of what is on disk
        assert con.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
        wal_mode = con.execute("PRAGMA journal_mode").fetchone()[0].lower()
        assert wal_mode == "wal"
    finally:
        con.close()
    # (a) durability settings in force on the next writer; (d) recovery decides and invariants hold
    sup = Supervisor(db)
    try:
        rep = sup.ledger.durability_report()
        assert rep["journal_mode"] == "wal" and rep["synchronous"] == "FULL", rep
        L = sup.ledger
        invariants(L)
        for a in L.q("SELECT attempt_id,task_id,status FROM attempt"):
            assert a["status"] in ("ENDED", "FENCED")
            assert L.q1("SELECT COUNT(*) FROM recovery_decision WHERE attempt_id=?", (a["attempt_id"],))[0] == 1
        assert L.q1("SELECT COUNT(*) FROM task WHERE state IN ('RUNNING','RECOVERING')")[0] == 0
        assert L.q1("PRAGMA integrity_check")[0] == "ok"
    finally:
        sup.close()
    # idempotence: a second restart changes no decision
    before = [tuple(r) for r in sqlite3.connect(f"file:{db}?mode=ro", uri=True).execute("SELECT decision_id,outcome,action FROM recovery_decision")]
    sup = Supervisor(db)
    try:
        after = [tuple(r) for r in sup.ledger.q("SELECT decision_id,outcome,action FROM recovery_decision")]
        assert before == after
    finally:
        sup.close()


def test_ledger_refuses_to_run_without_full_durability(tmp_path):
    """The configuration claim is enforced, not assumed: a connection that cannot set FULL/WAL is refused."""
    from uri_supervisor.ledger import Ledger, LedgerError
    import uri_supervisor.ledger as mod
    db = tmp_path / "l" / "ledger.db"
    L = Ledger(db)
    assert L.durability_report()["synchronous"] == "FULL"
    L.close()
    real = sqlite3.connect

    class Conn:
        def __init__(self, c):
            self.c = c

        def execute(self, sql, *a):
            if sql.strip().upper().startswith("PRAGMA SYNCHRONOUS=FULL"):
                return self.c.execute("PRAGMA synchronous=NORMAL")
            return self.c.execute(sql, *a)

        def __getattr__(self, name):
            return getattr(self.c, name)

    mod.sqlite3.connect = lambda *a, **k: Conn(real(*a, **k))
    try:
        with pytest.raises(LedgerError):
            Ledger(db)
    finally:
        mod.sqlite3.connect = real


def test_physical_power_loss_is_not_claimed():
    """Documentation pin: the only power-loss artefact is a plan. This test exists so a report cannot cite a passing
    suite as physical power-loss evidence."""
    plan = Path(__file__).resolve().parents[2] / "docs/plans/PHASE2A_POWER_LOSS_TEST_PLAN.md"
    assert plan.is_file() and "NOT EXECUTED" in plan.read_text(encoding="utf-8")
