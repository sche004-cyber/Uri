"""WORKER-LEVEL INTEGRATION: the real Scheduler + the real accepted uri_supervisor (contained spawn, raw stream,
postcondition reconciliation, quota breaker) + a SYNTHETIC Claude stand-in process (tests/scheduler/helpers/fake_claude.py).
No model is called. Every attempt is recorded with mode FIXTURE.
"""
import json
import os
import threading
import time
from pathlib import Path

import pytest

from uri_scheduler.engine import Scheduler
from uri_scheduler.harness import ClaudeHarness

FAKE = Path(__file__).parent / "helpers" / "fake_claude.py"
pytestmark = pytest.mark.skipif(os.name != "nt", reason="the accepted supervisor spawns only on Windows")


def make(tmp_path, scenario, timeout_s=60, inactivity_s=30):
    os.environ["URI_FAKE_SCENARIO"] = scenario
    h = ClaudeHarness(tmp_path / "state", mode="fixture", fixture_script=FAKE, timeout_s=timeout_s, inactivity_s=inactivity_s)
    s = Scheduler(tmp_path / "state", harness=h).start()
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1",
                  params={"festival": {"key": "diwali", "name": "Diwali (Deepavali)", "date": "2026-11-08"}},
                  schedule={"kind": "once", "at": "2026-01-01T00:00"}, policy={"max_attempts": 2})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    return s, h


@pytest.fixture(autouse=True)
def _env():
    old = os.environ.get("URI_FAKE_SCENARIO")
    yield
    if old is None:
        os.environ.pop("URI_FAKE_SCENARIO", None)
    else:
        os.environ["URI_FAKE_SCENARIO"] = old


def test_honest_run_through_supervisor(tmp_path):
    s, h = make(tmp_path, "honest")
    try:
        r = s.tick()[0]
        assert r["result"] == "AWAITING_REVIEW"
        att = s.store.q1("SELECT * FROM attempt")
        rec = json.loads(att["receipt_json"])
        assert att["mode"] == "FIXTURE" and rec["harness"]["supervisor_state"] == "COMPLETE"
        assert rec["harness"]["mode"] == "FIXTURE" and rec["gate"]["executor_id"] == "claude_fixture"
        L = h.sup.ledger
        auth = L.q1("SELECT valid_until_us FROM authorization WHERE task_id=? AND superseded_at_us IS NULL", (att["supervisor_task_id"],))
        assert auth[0] is not None and auth[0] <= L.now_us()        # authority closed after the run
    finally:
        s.close()


def test_quota_opens_breaker_and_defers(tmp_path):
    s, h = make(tmp_path, "quota")
    try:
        r = s.tick()[0]
        assert r["result"] == "QUOTA_DEFERRED"
        occ = s.occurrence(r["occ_id"])
        assert occ["retry_at_us"] > s.now() and occ["attempts"] == 0
        assert h.breaker_reset_us() is not None
        att = s.store.q1("SELECT outcome, reason FROM attempt")
        assert tuple(att) == ("QUOTA", "PROVIDER_QUOTA_EXHAUSTED")
    finally:
        s.close()


def test_false_success_claim_is_not_success(tmp_path):
    s, h = make(tmp_path, "false_claim")
    try:
        r = s.tick()[0]
        assert r["result"] == "SCHEDULED" and r["reason"].startswith("RETRY:SUPERVISOR_FAILED")
        assert s.store.q1("SELECT COUNT(*) FROM artifact")[0] == 0
    finally:
        s.close()


def test_invalid_scene_is_rejected_by_uri(tmp_path):
    s, h = make(tmp_path, "invalid")
    try:
        r = s.tick()[0]
        assert r["reason"].startswith("RETRY:OUTPUT_INVALID:SCENE_NOT_JSON")
    finally:
        s.close()


def test_cancel_while_running_kills_executor(tmp_path):
    s, h = make(tmp_path, "hang", timeout_s=120, inactivity_s=120)
    try:
        out = {}
        t = threading.Thread(target=lambda: out.setdefault("r", s.tick()))
        t.start()
        occ_id = None
        for _ in range(100):
            row = s.store.q1("SELECT occ_id FROM occurrence WHERE state='RUNNING'")
            if row and h._running:
                occ_id = row[0]
                break
            time.sleep(0.1)
        assert occ_id is not None
        s.cancel_occurrence(occ_id, "owner")
        t.join(60)
        assert not t.is_alive()
        assert out["r"][0]["result"] == "CANCELLED"
    finally:
        s.close()


def test_crashing_executor_retries_then_fails(tmp_path):
    s, h = make(tmp_path, "crash")
    try:
        r = s.tick()[0]
        assert r["result"] == "SCHEDULED"
        with s.store.tx() as db:
            db.execute("UPDATE occurrence SET retry_at_us=0")
        r = s.tick()[0]
        assert r["result"] == "FAILED"
        assert s.store.q1("SELECT COUNT(*) FROM attempt")[0] == 2
        tids = [x[0] for x in s.store.q("SELECT supervisor_task_id FROM attempt")]
        assert len(set(tids)) == 2
    finally:
        s.close()


def test_r6_harness_cancel_before_spawn_never_spawns(tmp_path):
    s, h = make(tmp_path, "honest")
    try:
        from uri_scheduler.harness import ClaudeHarness as CH
        key = "job:1:1"
        tid = CH.task_id_for(key)
        h.cancel(tid)                                 # recorded before submission
        ws = tmp_path / "ws"
        ws.mkdir()
        out = h.run(attempt_key=key, principal="owner", workspace=ws, instructions=b"x", gate=h.gate())
        assert out.status == "cancelled" and h.sup.ledger.task(tid) is None
    finally:
        s.close()
