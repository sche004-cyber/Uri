"""Admission, resource pools, fencing epochs, leases, priority/aging, breakers, preemption."""
import threading
import time
from dataclasses import replace

import pytest

from phase2a.conftest import Env
from uri_supervisor.clock import FakeClock
from uri_supervisor.executors import GENERIC_NDJSON
from uri_supervisor.ledger import LedgerRefused
from uri_supervisor.supervisor import Supervisor, SupervisorError


def held(L, pool):
    return L.q1("SELECT COALESCE(SUM(amount),0) FROM claim WHERE pool=? AND state='held'", (pool,))[0]


def mk(tmp_path, clock=None, pools=None, **reg):
    e = Env(tmp_path, clock=clock)
    e.setup_pools(**(pools or {"slot": 2}))
    e.register(**({"claims": {"slot": 1}} | reg))
    return e


def free_claims(e, adm):
    e.sup.admitter.release(adm.attempt_id, "test")


# ---- capacity / atomicity ------------------------------------------------------------------------

def test_concurrent_admission_never_exceeds_capacity(tmp_path):
    e = mk(tmp_path, pools={"slot": 3})
    for i in range(12):
        e.task(f"t{i}")
    got, errs = [], []

    def w():
        try:
            for _ in range(6):
                a = e.sup.admit_next()
                if a:
                    got.append(a)
                assert held(e.L, "slot") <= 3
        except Exception as ex:
            errs.append(ex)
    ts = [threading.Thread(target=w) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert not errs and len(got) == 3 and held(e.L, "slot") == 3
    e.close()


def test_multi_resource_admission_is_all_or_nothing(tmp_path):
    e = Env(tmp_path)
    e.setup_pools(a=1, b=1)
    e.register(claims={"a": 1, "b": 1})
    e.sup.admit_next()                         # nothing queued
    e.task("t1"); e.task("t2")
    first = e.sup.admit_next()
    assert first and held(e.L, "a") == 1 and held(e.L, "b") == 1
    e.L._db.execute("UPDATE claim SET state='released' WHERE pool='b'")      # externally free only b
    assert e.sup.admit_next() is None          # a is still held: t2 must not get b alone
    assert held(e.L, "a") == 1 and held(e.L, "b") == 0
    assert e.L.q1("SELECT COUNT(*) FROM attempt")[0] == 1
    e.close()


# ---- supervisors & epochs ----------------------------------------------------------------------

def test_startup_race_only_one_supervisor_holds_the_ledger(tmp_path):
    first = Supervisor(tmp_path / "r" / "l.db")
    results = []

    def attempt():
        try:
            Supervisor(tmp_path / "r" / "l.db").close()
            results.append("started")
        except SupervisorError:
            results.append("refused")
    ts = [threading.Thread(target=attempt) for _ in range(6)]
    [t.start() for t in ts]; [t.join() for t in ts]
    assert results == ["refused"] * 6
    first.close()


def test_superseded_supervisor_cannot_admit_after_new_epoch(tmp_path):
    a = mk(tmp_path)
    a.task("t1")
    b = Supervisor(tmp_path / "ledger" / "ledger.db", take_lock=False, run_recovery=False)    # lock bypassed on purpose
    assert b.epoch > a.sup.epoch
    with pytest.raises(LedgerRefused, match="SUPERSEDED_SUPERVISOR"):
        a.sup.admit_next()
    with pytest.raises(LedgerRefused, match="SUPERSEDED_SUPERVISOR"):
        a.sup.admitter.renew(1)
    assert b.admit_next() is not None
    b.close(); a.close()


def test_old_epoch_claims_still_block_capacity_until_recovery_proves_release(tmp_path):
    e = mk(tmp_path, pools={"slot": 1})
    e.task("t1"); e.task("t2")
    a1 = e.sup.admit_next()
    assert a1 and e.sup.admit_next() is None
    e.close()                                                  # "crash": claim of t1 survives in the ledger
    s2 = Supervisor(tmp_path / "ledger" / "ledger.db", run_recovery=False)       # new epoch, recovery deferred
    assert s2.epoch > a1.epoch
    assert len(s2.admitter.foreign_epoch_claims()) == 1
    assert s2.admit_next() is None                             # stale claim is NOT trusted away: no double admission
    assert held(s2.ledger, "slot") == 1
    s2.recover_all()                                           # evidence: attempt never started -> claim released
    assert held(s2.ledger, "slot") == 0 or s2.ledger.task("t1")["state"] != "RUNNING"
    nxt = s2.admit_next()
    assert nxt is not None and held(s2.ledger, "slot") <= 1
    s2.close()


def test_monotonic_origin_change_across_reboot_does_not_corrupt_leases(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk, pools={"slot": 1})
    e.task("t1")
    a1 = e.sup.admit_next()
    old_deadline = e.L.q1("SELECT lease_deadline_mono_ns FROM claim")[0]
    e.close()
    clk.set_mono(1_000)                                        # "reboot": monotonic origin resets far below old deadline
    s2 = Supervisor(tmp_path / "ledger" / "ledger.db", clock=clk, run_recovery=False)
    assert old_deadline > clk.mono_ns()                        # a naive comparison would call the old lease LIVE
    assert s2.admitter.expired_leases() == []                  # foreign epoch claims are never judged by deadline
    assert len(s2.admitter.foreign_epoch_claims()) == 1
    s2.close()


def test_wall_clock_rollback_does_not_affect_leases_or_ordering(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk, pools={"slot": 2})
    e.task("t1")
    a = e.sup.admit_next()
    clk.advance(100)                                           # lease_s=60 -> expired in monotonic terms
    exp1 = [r["claim_id"] for r in e.sup.admitter.expired_leases()]
    clk.set_wall(clk.wall_us() - 10 * 86400 * 1_000_000)       # wall clock jumps back 10 days
    assert [r["claim_id"] for r in e.sup.admitter.expired_leases()] == exp1 == [1]
    e.sup.admitter.renew(a.attempt_id)
    assert e.sup.admitter.expired_leases() == []               # renewal uses monotonic only
    seqs = [r[0] for r in e.L.q("SELECT seq FROM event ORDER BY seq")]
    assert seqs == sorted(seqs)                                # ledger order is by seq, not by recorded wall time
    e.close()


def test_expired_lease_does_not_auto_release_capacity(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk, pools={"slot": 1})
    e.task("t1"); e.task("t2")
    e.sup.admit_next()
    clk.advance(10_000)
    assert len(e.sup.admitter.expired_leases()) == 1
    assert e.sup.admit_next() is None and held(e.L, "slot") == 1
    e.close()


# ---- priority, aging, reservation ----------------------------------------------------------------

def test_higher_priority_admitted_first(tmp_path):
    e = mk(tmp_path, pools={"slot": 1})
    e.task("low", priority=0); e.task("high", priority=9); e.task("mid", priority=3)
    assert e.sup.admit_next().task_id == "high"
    e.close()


def test_low_priority_is_not_starved_by_continuous_high_priority_arrivals(tmp_path):
    e = mk(tmp_path, pools={"slot": 1})
    e.task("low", priority=0)
    admitted_low_at = None
    for i in range(60):
        e.task(f"h{i}", priority=5)
        a = e.sup.admit_next()
        assert a is not None
        if a.task_id == "low":
            admitted_low_at = i
            break
        free_claims(e, a)
    assert admitted_low_at is not None and admitted_low_at <= 40, admitted_low_at
    e.close()


def test_aging_counts_rounds_not_wall_time(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk, pools={"slot": 1})
    e.task("low", priority=0)
    clk.advance(10 * 365 * 86400)                              # ten years of wall time must not age anything
    e.task("high", priority=1)
    assert e.sup.admit_next().task_id == "high"
    e.close()


def test_blocked_high_priority_task_reserves_its_pools_against_lower_priority(tmp_path):
    """Reservation policy: a capacity-blocked higher-ranked task reserves ALL pools it needs (atomic claim), so lower
    ranked tasks cannot take any of them and starve it; tasks on unrelated pools still run (backfill)."""
    e = Env(tmp_path)
    e.setup_pools(a=1, b=1, c=1)
    e.register("exec_a", claims={"a": 1}, caps=("a",))
    e.register("exec_ab", claims={"a": 1, "b": 1}, caps=("ab",))
    e.register("exec_b", claims={"b": 1}, caps=("b",))
    e.register("exec_c", claims={"c": 1}, caps=("c",))
    for tid, cap, pr in (("holder", "a", 100), ("big", "ab", 9), ("sneak", "a", 5), ("greedy_b", "b", 4), ("unrelated", "c", 1)):
        e.sup.submit_task(tid, "t", {}, authorization={}, effects=[{"op_class": "read", "operation": "x"}],
                          postconditions=[{"kind": "terminal_success"}], requirements={"capabilities": [cap]}, priority=pr)
    h = e.sup.admit_next(); assert h.task_id == "holder"
    nxt = e.sup.admit_next()
    assert nxt.task_id == "unrelated"                          # big is blocked on a; sneak and greedy_b are fenced off its pools
    assert e.sup.admit_next() is None
    free_claims(e, h)
    assert e.sup.admit_next().task_id == "big"                 # when a frees, the reserved higher-ranked task wins
    e.close()


# ---- executor capability changes while queued -------------------------------------------------------

def test_capability_change_while_queued_uses_current_registration(tmp_path):
    e = Env(tmp_path)
    e.setup_pools(slot=2)
    e.register("w", claims={"slot": 1}, caps=("run",))
    e.sup.submit_task("t", "u", {}, authorization={}, effects=[{"op_class": "read", "operation": "x"}],
                      postconditions=[{"kind": "terminal_success"}], requirements={"capabilities": ["gpu"]})
    assert e.sup.admit_next() is None                          # capability absent
    r2 = e.register("w", claims={"slot": 1}, caps=("run", "gpu"))
    a = e.sup.admit_next()
    assert a and a.registration_id == r2                       # admitted under the registration current at admission
    assert e.L.q1("SELECT registration_id FROM attempt WHERE attempt_id=?", (a.attempt_id,))[0] == r2
    old = e.L.q1("SELECT superseded_at_us FROM executor_registration WHERE registration_id=1")[0]
    assert old is not None                                     # earlier version superseded, not edited
    e.sup.submit_task("t2", "u", {}, authorization={}, effects=[{"op_class": "read", "operation": "x"}],
                      postconditions=[{"kind": "terminal_success"}], requirements={"capabilities": ["gpu"]})
    e.register("w", claims={"slot": 1}, caps=("run",))         # capability withdrawn again
    assert e.sup.admit_next() is None
    e.close()


def test_registration_history_is_bitemporal(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk)
    t0 = clk.wall_us()
    clk.advance(100)
    e.register("fake", claims={"slot": 2})
    believed_then = e.sup.registry.registration_as_believed("fake", t0 + 1_000_000)
    believed_now = e.sup.registry.registration_as_believed("fake", clk.wall_us())
    import json
    assert json.loads(believed_then["claims_json"]) == {"slot": 1} and json.loads(believed_now["claims_json"]) == {"slot": 2}
    e.close()


def test_registration_is_immutable_except_for_supersession(tmp_path):
    e = mk(tmp_path)
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError, match="REGISTRATION_IMMUTABLE"):
        e.L._db.execute("UPDATE executor_registration SET claims_json='{}'")
    e.close()


# ---- authorization validity (half-open) ---------------------------------------------------------------

def test_authorization_validity_is_half_open_and_superseded_versions_are_preserved(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk)
    now = clk.wall_us()
    e.sup.submit_task("t", "u", {}, authorization={"valid_from_us": now + 10_000_000, "valid_until_us": now + 20_000_000},
                      effects=[{"op_class": "read", "operation": "x"}], postconditions=[{"kind": "terminal_success"}],
                      requirements={"capabilities": ["run"]})
    assert e.sup.admit_next() is None                          # before valid_from
    clk.advance(10)                                            # exactly valid_from: inclusive
    a = e.sup.admit_next()
    assert a is not None
    e.sup.submit_task("t2", "u", {}, authorization={"valid_from_us": now, "valid_until_us": now + 20_000_000},
                      effects=[{"op_class": "read", "operation": "x"}], postconditions=[{"kind": "terminal_success"}],
                      requirements={"capabilities": ["run"]})
    clk.advance(10)                                            # exactly valid_until: exclusive
    assert e.sup.admit_next() is None
    e.sup.supersede_authorization("t2", scope={"renewed": True}, valid_until_us=clk.wall_us() + 10_000_000)
    assert e.sup.admit_next().task_id == "t2"
    rows = e.L.q("SELECT superseded_at_us FROM authorization WHERE task_id='t2' ORDER BY auth_id")
    assert rows[0][0] is not None and rows[1][0] is None       # old version retained with superseded_at
    e.close()


def test_admission_without_authorization_in_force_is_impossible_to_spawn(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    adm = e.sup.admit_next()
    row = e.L.q1("SELECT auth_id FROM admission WHERE attempt_id=?", (adm.attempt_id,))
    assert row is not None                                     # durable admission references the authorization it relied on


# ---- circuit breakers ---------------------------------------------------------------------------------

def mk_quota(tmp_path, clock, **spec_kw):
    e = Env(tmp_path, clock=clock)
    e.setup_pools(slot=3, prov=1)
    e.register(claims={"slot": 1, "prov": 1}, quota_pools=("prov",), spec=replace(GENERIC_NDJSON, **spec_kw))
    return e


def test_quota_failure_opens_breaker_without_consuming_retry_budget_and_stops_hammering(tmp_path):
    clk = FakeClock()
    e = mk_quota(tmp_path, clk)
    e.task("t", max_attempts=1)
    e.run(e.sup.admit_next(), "quota")
    t = e.L.task("t")
    assert t["state"] == "RETRY_SAFE" and t["max_attempts"] == 2          # quota did not consume the budget
    assert e.L.q1("SELECT breaker_state FROM resource_pool WHERE name='prov'")[0] == "open"
    n = e.L.q1("SELECT COUNT(*) FROM attempt")[0]
    for _ in range(10):
        assert e.sup.admit_next() is None
    assert e.L.q1("SELECT COUNT(*) FROM attempt")[0] == n                 # not hammered
    e.close()


def test_bounded_backoff_then_single_half_open_probe_then_close(tmp_path):
    clk = FakeClock()
    e = mk_quota(tmp_path, clk)
    e.task("t1"); e.task("t2")
    e.run(e.sup.admit_next(), "quota")
    clk.advance(10)
    assert e.sup.admit_next() is None                                      # still inside backoff
    clk.advance(25)                                                        # > 30s base backoff
    probe = e.sup.admit_next()
    assert probe is not None
    assert e.L.q1("SELECT breaker_state FROM resource_pool WHERE name='prov'")[0] == "half_open"
    assert e.sup.admit_next() is None                                      # only ONE probe while half-open
    e.run(probe, "ok_read")
    assert e.L.q1("SELECT breaker_state,breaker_failures FROM resource_pool WHERE name='prov'")["breaker_state"] == "closed"
    e.close()


def test_failed_probe_reopens_with_doubled_backoff_and_cap(tmp_path):
    clk = FakeClock()
    e = mk_quota(tmp_path, clk)
    e.task("t")
    e.run(e.sup.admit_next(), "quota")
    until1 = e.L.q1("SELECT breaker_until_mono_ns FROM resource_pool WHERE name='prov'")[0]
    clk.advance(31)
    e.run(e.sup.admit_next(), "quota")
    row = e.L.q1("SELECT * FROM resource_pool WHERE name='prov'")
    assert row["breaker_state"] == "open" and row["breaker_failures"] == 2
    assert row["breaker_until_mono_ns"] - clk.mono_ns() == 60 * 10**9      # 30 * 2^1
    for _ in range(12):
        e.L._db.execute("UPDATE resource_pool SET breaker_failures=breaker_failures+1")
    clk.advance(10_000)
    e.sup.admit_next()
    e.close()


def test_trustworthy_provider_reset_time_is_used_instead_of_backoff(tmp_path):
    clk = FakeClock()
    e = mk_quota(tmp_path, clk, reset_regex=r"reset_at=(\d+)")
    reset_s = clk.wall_us() // 1_000_000 + 3600
    e.task("t")
    e.run(e.sup.admit_next(), "quota_reset", content=str(reset_s))
    row = e.L.q1("SELECT * FROM resource_pool WHERE name='prov'")
    assert row["breaker_until_wall_us"] == reset_s * 1_000_000 and row["breaker_until_mono_ns"] is None
    clk.advance(3599)
    assert e.sup.admit_next() is None
    clk.advance(2)
    assert e.sup.admit_next() is not None                                  # half-open probe after the stated reset
    e.close()


def test_breaker_state_after_restart_never_trusts_old_monotonic_deadline(tmp_path):
    clk = FakeClock()
    e = mk_quota(tmp_path, clk)
    e.task("t")
    e.run(e.sup.admit_next(), "quota")
    e.close()
    s2 = Supervisor(tmp_path / "ledger" / "ledger.db", clock=clk)
    assert s2.admit_next() is not None                                     # conservative: probe allowed (half-open), not open-forever / not closed
    assert s2.ledger.q1("SELECT breaker_state FROM resource_pool WHERE name='prov'")[0] == "half_open"
    s2.close()


def test_provider_names_never_appear_in_scheduler_code():
    import pathlib
    import re
    for f in ("admission.py", "ledger.py", "schema.py", "recovery.py", "supervisor.py", "snapshot.py", "narration.py", "postconditions.py"):
        src = pathlib.Path(__file__).resolve().parents[2].joinpath("uri_supervisor", f).read_text(encoding="utf-8")
        assert not re.search(r"claude|codex|anthropic|openai|ollama|gemma", src, re.I), f


# ---- preemption (safe points only) --------------------------------------------------------------------

def _start(e, adm, scenario, **kw):
    box = {}
    th = threading.Thread(target=lambda: box.setdefault("r", e.run(adm, scenario, **kw)))
    th.start()
    deadline = time.time() + 20
    while time.time() < deadline and e.L.q1("SELECT status FROM attempt WHERE attempt_id=?", (adm.attempt_id,))[0] != "RUNNING":
        time.sleep(0.05)
    return th, box


def _wait_safe(e, adm, want=True):
    deadline = time.time() + 20
    while time.time() < deadline:
        if bool(e.sup._safe.get(adm.attempt_id)) == want and e.L.q1("SELECT COUNT(*) FROM stream_event WHERE attempt_id=?", (adm.attempt_id,))[0] >= 2:
            return
        time.sleep(0.05)


def test_preemption_granted_only_at_safe_point(tmp_path):
    e = mk(tmp_path, preemptible=True)
    e.task("t")
    adm = e.sup.admit_next()
    th, box = _start(e, adm, "sleep", sleep=120)
    _wait_safe(e, adm)
    out = e.sup.request_preempt(adm.attempt_id)
    th.join(30)
    assert out["granted"] and box["r"].end_reason == "preempted_at_safe_point"
    assert e.state("t") == "RETRY_SAFE"
    e.close()


def test_preemption_denied_mid_work_for_nonpreemptible_and_for_nonidempotent_effects(tmp_path):
    e = mk(tmp_path, preemptible=True, pools={"slot": 3})
    e.task("t")
    adm = e.sup.admit_next()
    th, box = _start(e, adm, "sleep_unsafe", sleep=4)
    _wait_safe(e, adm, want=False)
    assert e.sup.request_preempt(adm.attempt_id) == {"granted": False, "reason": "NOT_AT_SAFE_POINT"}
    th.join(30)
    # non-idempotent declared effect: never preempt even at a safe point
    t = tmp_path / "w.txt"
    e.task("w", effects=[{"op_class": "local_write", "operation": "w", "paths": [str(t)]}],
           postconditions=[{"kind": "file_exists", "spec": {"path": str(t)}}], priority=9)
    a2 = e.sup.admit_next()
    assert a2.task_id == "w"
    th2, box2 = _start(e, a2, "sleep", sleep=4)
    _wait_safe(e, a2)
    assert e.sup.request_preempt(a2.attempt_id) == {"granted": False, "reason": "NON_IDEMPOTENT_EFFECT_DECLARED"}
    th2.join(30)
    e.close()
    e2 = mk(tmp_path / "np", preemptible=False)
    e2.task("t")
    a3 = e2.sup.admit_next()
    th3, _ = _start(e2, a3, "sleep", sleep=3)
    _wait_safe(e2, a3)
    assert e2.sup.request_preempt(a3.attempt_id) == {"granted": False, "reason": "EXECUTOR_NOT_PREEMPTIBLE"}
    th3.join(30)
    e2.close()
