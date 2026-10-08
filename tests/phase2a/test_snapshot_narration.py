"""Manager snapshot (bounded, deterministic, freshness-aware) and evidence-grounded narration (no event, no claim)."""
import json
import sys

import pytest

from phase2a.conftest import Env
from uri_supervisor.clock import FakeClock
from uri_supervisor.narration import Claim, filter_proposed_claims, format_claim, narrate, render, verify_claim
from uri_supervisor.snapshot import STABLE_SHA256, ObservationBoard, build_snapshot, render_prompt


def mk(tmp_path, clock=None, **kw):
    e = Env(tmp_path, clock=clock or FakeClock())
    e.setup_pools(slot=50)
    e.register(claims={"slot": 1}, **kw)
    return e


# ---- snapshot ---------------------------------------------------------------------------------------

def test_snapshot_is_deterministic_and_versioned_by_ledger_watermark(tmp_path):
    e = mk(tmp_path)
    b = ObservationBoard(e.clock)
    s1, s2 = build_snapshot(e.L, b), build_snapshot(e.L, b)
    assert s1 == s2
    e.task("t")
    s3 = build_snapshot(e.L, b)
    assert s3["volatile"]["version"] > s1["volatile"]["version"] and s3["volatile"]["counts"]["queued"] == 1
    e.close()


def test_snapshot_lists_are_bounded_and_disclose_omitted_counts(tmp_path):
    e = mk(tmp_path)
    for i in range(25):
        e.task(f"t{i}")
        a = e.sup.admit_next()
        e.L._db.execute("UPDATE attempt SET status='SPAWNING' WHERE attempt_id=?", (a.attempt_id,)) if False else None
    snap = build_snapshot(e.L, ObservationBoard(e.clock), max_items=10)
    v = snap["volatile"]
    assert len(v["running"]) == 10 and v["omitted"]["running"] == 15 and v["counts"]["running"] == 25
    e.close()


def test_every_snapshot_item_cites_existing_ledger_events_of_its_task(tmp_path):
    e = mk(tmp_path)
    t = tmp_path / "ne.txt"
    import hashlib
    e.task("n", effects=[{"op_class": "local_write", "operation": "w", "paths": [str(t)]}],
           postconditions=[{"kind": "file_hash", "spec": {"path": str(t), "sha256": hashlib.sha256(b"FULL").hexdigest()}}])
    e.run(e.sup.admit_next(), "partial_write_then_die", path=str(t))
    v = build_snapshot(e.L, ObservationBoard(e.clock))["volatile"]
    assert v["counts"]["needs_user"] == 1 and v["attention"][0]["state"] == "NEEDS_USER"
    for item in v["attention"] + v["running"]:
        for eid in item["event_ids"]:
            row = e.L.q1("SELECT task_id FROM event WHERE seq=?", (eid,))
            assert row is not None and row["task_id"] == item["task_id"]
    e.close()


def test_conditions_unknown_when_never_observed_or_stale_and_true_false_when_fresh(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk)
    b = ObservationBoard(clk)
    b.require("executor_reachable", ttl_s=30)
    b.require("disk_ok", ttl_s=30)
    cond = lambda: {c["type"]: c for c in build_snapshot(e.L, b)["volatile"]["conditions"]}
    assert cond()["executor_reachable"]["status"] == "Unknown" and cond()["executor_reachable"]["reason"] == "NEVER_OBSERVED"
    b.observe("executor_reachable", True)
    b.observe("disk_ok", False, detail="98% full")
    c = cond()
    assert c["executor_reachable"]["status"] == "True" and c["disk_ok"]["status"] == "False"
    clk.advance(31)
    c = cond()
    assert c["executor_reachable"]["status"] == "Unknown" and c["executor_reachable"]["reason"] == "STALE_OBSERVATION"
    assert c["disk_ok"]["status"] == "Unknown"                   # a stale False is not reported as False either
    clk.set_mono(1)                                              # monotonic origin change: negative age is untrusted
    assert cond()["executor_reachable"]["status"] == "Unknown"
    e.close()


def test_restart_makes_all_observations_unknown(tmp_path):
    clk = FakeClock()
    e = mk(tmp_path, clock=clk)
    b = ObservationBoard(clk); b.require("x", 60); b.observe("x", True)
    assert {c["type"]: c["status"] for c in build_snapshot(e.L, b)["volatile"]["conditions"]}["x"] == "True"
    b2 = ObservationBoard(clk); b2.require("x", 60)               # new process => new board
    assert {c["type"]: c["status"] for c in build_snapshot(e.L, b2)["volatile"]["conditions"]}["x"] == "Unknown"
    e.close()


def test_stable_prefix_is_byte_identical_across_snapshots_and_volatile_data_never_leaks_into_it(tmp_path):
    e = mk(tmp_path)
    b = ObservationBoard(e.clock)
    p1 = render_prompt(build_snapshot(e.L, b))
    for i in range(3):
        e.task(f"t{i}"); e.sup.admit_next()
    p2 = render_prompt(build_snapshot(e.L, b))
    cut = lambda p: p.split("\n--- VOLATILE ---\n")[0]
    assert cut(p1) == cut(p2) and p1 != p2
    stable = cut(p2)
    for forbidden in ("version", "generated_at", "counts", "running", "t0"):
        assert f'"{forbidden}"' not in stable and forbidden not in ("t0",) or "t0" not in stable
    import hashlib
    assert hashlib.sha256(cut(p1).encode()).hexdigest() == STABLE_SHA256
    e.close()


def test_pool_capacity_condition_is_derived_from_ledger(tmp_path):
    e = mk(tmp_path)
    c = {x["type"]: x for x in build_snapshot(e.L, ObservationBoard(e.clock))["volatile"]["conditions"]}
    assert c["pool_capacity_respected"]["status"] == "True" and c["breaker_open:slot"]["status"] == "False"
    e.close()


# ---- narration ----------------------------------------------------------------------------------------

def done_task(e, tmp_path, tid="t"):
    t = tmp_path / f"{tid}.txt"
    e.task(tid, effects=[{"op_class": "local_write", "operation": "w", "target": str(t), "paths": [str(t)]}],
           postconditions=[{"kind": "file_exists", "spec": {"path": str(t)}},
                           {"kind": "command_passes", "spec": {"argv": [sys.executable, "-c", "print('3 passed, 3 total')"],
                                                               "summary_regex": r"(?P<passed>\d+) passed, (?P<total>\d+) total"}}])
    e.run(e.sup.admit_next(), "ok_write", path=str(t))
    return t


def test_tests_ran_sentence_comes_from_uri_verified_evidence(tmp_path):
    e = mk(tmp_path)
    done_task(e, tmp_path)
    lines = [format_claim(c) for c in narrate(e.L, "t")]
    assert "[URI verified] Ran tests: 3/3 passed." in lines
    assert "[URI verified] Task complete: every required postcondition was verified by URI." in lines
    e.close()


def test_every_emitted_claim_re_verifies_and_cites_existing_rows(tmp_path):
    e = mk(tmp_path)
    done_task(e, tmp_path)
    for c in narrate(e.L, "t"):
        assert c.citations
        status, _ = verify_claim(e.L, "t", c)
        assert status == "ok"
    e.close()


def test_tampered_claims_are_dropped_or_downgraded(tmp_path):
    e = mk(tmp_path)
    done_task(e, tmp_path)
    good = next(c for c in narrate(e.L, "t") if c.template_id == "tests_ran")
    ev = good.citations[0]
    bad = [
        Claim("tests_ran", {"passed": 3, "total": 3}, render("tests_ran", {"passed": 3, "total": 3}), "uri_verified", []),                # no event
        Claim("tests_ran", {"passed": 3, "total": 3}, render("tests_ran", {"passed": 3, "total": 3}), "uri_verified", [("evidence", 99999)]),  # corrupt citation
        Claim("tests_ran", {"passed": 3, "total": 3}, render("tests_ran", {"passed": 3, "total": 3}), "uri_verified", [("evidence_x", 1)]),
        Claim("tests_ran", {"passed": 9, "total": 9}, render("tests_ran", {"passed": 9, "total": 9}), "uri_verified", [ev]),                # fabricated numbers
        Claim("tests_ran", {"passed": 3, "total": 3}, "Ran tests: 3/3 passed!!", "uri_verified", [ev]),                                       # altered text
        Claim("made_up", {}, "x", "uri_verified", [ev]),                                                                                       # unknown template
        Claim("tests_ran", {"passed": 3, "total": 3}, render("tests_ran", {"passed": 3, "total": 3}), "uri_verified", [("event", 1)]),         # unsupportive citation
    ]
    kept, dropped = filter_proposed_claims(e.L, "t", bad)
    assert kept == [] and len(dropped) == len(bad)
    e.close()


def test_claim_citing_another_tasks_evidence_is_dropped(tmp_path):
    e = mk(tmp_path)
    done_task(e, tmp_path, "t")
    done_task(e, tmp_path, "u")
    other = next(c for c in narrate(e.L, "u") if c.template_id == "tests_ran")
    forged = Claim("tests_ran", other.fields, other.text, "uri_verified", other.citations)
    assert verify_claim(e.L, "t", forged)[0] == "dropped"
    e.close()


def test_level_inflation_is_downgraded(tmp_path):
    e = mk(tmp_path)
    env_t = tmp_path / "x.txt"
    e.task("t")
    e.run(e.sup.admit_next(), "ok_read")                              # read task completes via terminal_success
    e.task("v")
    e.run(e.sup.admit_next(), "text_success_but_failed_command")
    claims = narrate(e.L, "v")
    failed = next(c for c in claims if c.template_id == "command_failed")
    assert failed.level == "executor_says"
    inflated = Claim(failed.template_id, failed.fields, failed.text, "uri_verified", failed.citations)
    status, res = verify_claim(e.L, "v", inflated)
    assert status == "downgraded" and res.level == "executor_says"
    e.close()


def test_missing_terminal_event_yields_no_completion_claim(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    e.run(e.sup.admit_next(), "no_terminal_nothing")
    claims = narrate(e.L, "t")
    assert not any(c.template_id in ("executor_claims_complete", "state_complete") for c in claims)
    fake = Claim("executor_claims_complete", {}, render("executor_claims_complete", {}), "executor_says",
                 [("evidence", e.L.q1("SELECT evidence_id FROM evidence WHERE kind='agent_message'")[0])])
    assert verify_claim(e.L, "t", fake)[0] == "dropped"
    e.close()


def test_unverified_success_claim_is_labelled_as_executor_says_and_state_is_not_complete(tmp_path):
    e = mk(tmp_path)
    t = tmp_path / "gone.txt"
    e.task("t", effects=[{"op_class": "local_write", "operation": "w", "paths": [str(t)]}],
           postconditions=[{"kind": "file_exists", "spec": {"path": str(t)}}])
    e.run(e.sup.admit_next(), "claims_success_no_effect")
    lines = [format_claim(c) for c in narrate(e.L, "t")]
    assert "[executor says] Executor reports completion; URI has not verified it." in lines
    assert any(l.startswith("[URI state] Attempt ended without proof of completion") for l in lines)
    assert not any(l.startswith("[URI verified]") and "complete" in l.lower() for l in lines)
    e.close()


def test_needs_user_narration_states_why_waiting(tmp_path):
    e = mk(tmp_path)
    e.task("t", effects=[{"op_class": "external", "operation": "pay"}],
           postconditions=[{"kind": "external_object", "spec": {"reconciler": "none", "key": "k"}}])
    e.run(e.sup.admit_next(), "error_claim")
    lines = [format_claim(c) for c in narrate(e.L, "t")]
    assert any("Waiting for user decision because the effect cannot be confirmed" in l for l in lines)
    e.close()


def test_state_claim_is_dropped_once_state_changes(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    state_claim = next(c for c in narrate(e.L, "t") if c.template_id == "state_queued")
    e.sup.admit_next()
    assert verify_claim(e.L, "t", state_claim)[0] == "dropped"          # stale narration cannot be replayed as current
    e.close()


def test_executor_free_text_is_quoted_never_parsed_for_facts(tmp_path):
    e = mk(tmp_path)
    e.task("t")
    e.run(e.sup.admit_next(), "text_success_but_failed_command")
    claims = narrate(e.L, "t")
    msg = next(c for c in claims if c.template_id == "executor_message")
    assert msg.level == "executor_says" and "(unverified)" in msg.text
    assert not any(c.template_id in ("tests_ran", "state_complete") for c in claims)
    e.close()
