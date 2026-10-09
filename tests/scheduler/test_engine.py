"""Engine behaviour with a scripted in-process harness (AUTOMATED SIMULATION: no supervisor, no executor process).

Covers activation gating, ownership, persistence across restart, missed execution, deadline, harness unavailable,
quota, retry budget, interrupted recovery, cancellation, calendar refresh dedup, review binding and refinement.
"""
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

from uri_scheduler.calendar_store import Calendar
from uri_scheduler.engine import Scheduler, SchedulerAlreadyRunning, SchedulerError
from uri_scheduler.harness import GateResult, RunOutcome

FIX = Path(__file__).parent / "fixtures" / "diwali_scene.json"


def tiny_scene(title="Rows of light", petals=10):
    s = json.loads(FIX.read_text(encoding="utf-8"))
    s["canvas"] = {"width": 160, "height": 160, "fps": 8, "duration_s": 1}
    s["title"] = title
    for ly in s["layers"]:
        if ly["type"] == "text":
            ly["size"] = max(ly["size"], 0.09)          # >= 14 px at 160 px, else the legibility gate (rightly) fails
        if ly["type"] == "particles" and ly["kind"] == "marigold":
            ly["count"] = petals
    return s


class FakeHarness:
    def __init__(self):
        self.sup = object()
        self.startup_report = []
        self.available = True
        self.code = "AVAILABLE"
        self.script = []           # list of statuses to return; default completed
        self.calls = []

    def open(self):
        return self

    def close(self):
        pass

    def gate(self):
        return GateResult(self.available, self.code if not self.available else "AVAILABLE", "FIXTURE", "claude_fixture",
                          "fake", "0", "FIXTURE_ONLY")

    @staticmethod
    def task_id_for(key):
        return str(uuid.uuid5(uuid.NAMESPACE_URL, key))

    def cancel(self, task_id):
        return {"granted": True}

    def run(self, *, attempt_key, principal, workspace, instructions, gate, valid_until_us=None, expected_file="scene.json"):
        self.calls.append({"key": attempt_key, "instructions": instructions.decode()})
        status = self.script.pop(0) if self.script else "completed"
        if status == "completed":
            task = json.loads((workspace / "task.json").read_text(encoding="utf-8"))
            petals = 10
            if task["request"].get("kind") == "refine":
                petals = 30
            (workspace / "scene.json").write_text(json.dumps(tiny_scene(petals=petals)), encoding="utf-8")
            (workspace / "concept.md").write_text("# Rows of light\nconcept\n", encoding="utf-8")
            (workspace / "research.md").write_text("research\n", encoding="utf-8")
        if status == "invalid":
            (workspace / "scene.json").write_text("{", encoding="utf-8")
            (workspace / "concept.md").write_text("c", encoding="utf-8")
            (workspace / "research.md").write_text("r", encoding="utf-8")
            status = "completed"
        reset = 1_900_000_000_000_000 if status == "quota" else None
        return RunOutcome(status, {"completed": "POSTCONDITION_VERIFIED", "quota": "PROVIDER_QUOTA_EXHAUSTED"}.get(status, "X"),
                          self.task_id_for(attempt_key), {"reset_us": reset})


class Clock:
    def __init__(self, iso):
        self.t = int(datetime.fromisoformat(iso).timestamp() * 1_000_000)

    def __call__(self):
        return self.t

    def set(self, iso):
        self.t = int(datetime.fromisoformat(iso).timestamp() * 1_000_000)

    def add(self, s):
        self.t += int(s * 1_000_000)


@pytest.fixture
def env(tmp_path):
    clock = Clock("2026-10-09T10:00:00+05:30")
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=clock).start()
    yield s, h, clock, tmp_path
    s.close()


def festival_job(s, sel=("diwali",), owner="owner"):
    p = s.propose(owner=owner, title="fest", template_id="festival_gif.v1", params={},
                  schedule={"kind": "calendar_relative", "calendar": "in_festivals", "selection": list(sel), "offset_days": -2,
                            "time": "09:00"})
    return p


def test_proposal_needs_owner_confirmation_bound_to_hash(env):
    s, h, clock, _ = env
    p = festival_job(s, ("diwali", "dussehra"))
    assert [r["key"] for r in p["upcoming"]][:2] == ["dussehra:2026", "diwali:2026"]
    assert p["upcoming"][0]["due_local"].startswith("2026-10-18T09:00")
    assert all(r["source"]["verification"] for r in p["upcoming"])
    assert s.tick() == [] and s.store.q1("SELECT COUNT(*) FROM occurrence")[0] == 0        # PROPOSED never runs
    with pytest.raises(SchedulerError) as e:
        s.confirm(p["job_id"], "someone_else", p["proposal_sha256"])
    assert e.value.code == "NOT_OWNER"
    with pytest.raises(SchedulerError) as e:
        s.confirm(p["job_id"], "owner", "0" * 64)
    assert e.value.code == "PROPOSAL_MISMATCH"
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    assert s.store.q1("SELECT COUNT(*) FROM occurrence")[0] == 4


def test_unverified_and_solemn_handling(env):
    s, *_ = env
    s.correct_calendar("owner", "in_festivals", "losoong_namsoong", 2026, "dispute", note="test: disputed record")
    p = festival_job(s, ("diwali", "losoong_namsoong"))
    assert any(x["festival_key"] == "losoong_namsoong" for x in p["excluded"])
    assert all(not r["key"].startswith("losoong_namsoong") for r in p["upcoming"])
    with pytest.raises(SchedulerError) as e:
        festival_job(s, ("muharram",))
    assert e.value.code == "NOT_A_GREETING_OCCASION"


def test_authority_cannot_widen(env):
    s, *_ = env
    for auth in ({"publish": True}, {"paid_services": True}, {"tools": ["Bash"]}, {"harness": "codex_cli"}):
        with pytest.raises(SchedulerError):
            s.propose(owner="o", title="t", template_id="festival_gif.v1", params={},
                      schedule={"kind": "once", "at": "2026-10-10T09:00"}, authority=auth)


def test_due_run_produces_review_item_and_persists_across_restart(env):
    s, h, clock, tmp = env
    p = festival_job(s)
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    clock.set("2026-11-06T08:59:00+05:30")
    assert s.tick() == []
    clock.set("2026-11-06T09:00:30+05:30")
    res = s.tick()
    assert res[0]["result"] == "AWAITING_REVIEW"
    s.close()
    s2 = Scheduler(tmp / "state", harness=h, now_fn=clock).start()
    ov = s2.overview()
    assert len(ov["pending_approvals"]) == 1
    cand = ov["pending_approvals"][0]["candidates"][0]
    assert cand["info"]["gif_checks"]["is_animated"] and cand["info"]["quality"]["text_legible"]
    assert s2.store.verify_chain()["ok"]
    s2.close()


def test_duplicate_scheduler_refused(env):
    s, h, clock, tmp = env
    with pytest.raises(SchedulerAlreadyRunning):
        Scheduler(tmp / "state", harness=h, now_fn=clock)


def test_missed_execution_runs_late_then_deadline_means_missed(env):
    s, h, clock, _ = env
    p = festival_job(s, ("diwali", "dussehra"))
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    clock.set("2026-10-19T12:00:00+05:30")          # dussehra due 10-18 09:00, still before 10-20 00:00 -> late run
    res = s.tick()
    assert res[0]["result"] == "AWAITING_REVIEW"
    kinds = [e["kind"] for e in s.store.events()]
    assert "occurrence.missed_execution_detected" in kinds
    occ = s.overview()["pending_approvals"][0]
    assert occ["late"] == 1
    clock.set("2026-11-08T00:00:01+05:30")          # scheduler was down through diwali's deadline
    res = s.tick()
    assert res[0]["result"] == "MISSED"


def test_skip_policy(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={},
                  schedule={"kind": "once", "at": "2026-10-09T11:00"}, policy={"missed": "skip"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    clock.set("2026-10-09T12:00:00+05:30")
    assert s.tick()[0]["result"] == "MISSED"


def test_harness_unavailable_blocks_then_recovers(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    h.available, h.code = False, "NOT_AUTHENTICATED"
    r = s.tick()[0]
    assert r["result"] == "BLOCKED_HARNESS" and r["reason"] == "NOT_AUTHENTICATED" and h.calls == []
    ev = [e for e in s.store.events() if e["kind"] == "harness.unavailable"][0]
    assert "no other or paid provider" in ev["payload"]["substitution"]
    occ = s.occurrence(r["occ_id"])
    assert occ["attempts"] == 0                     # unavailability does not burn the retry budget
    h.available = True
    clock.add(1801)
    assert s.tick()[0]["result"] == "AWAITING_REVIEW"


def test_quota_defers_without_fallback(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    h.script = ["quota"]
    r = s.tick()[0]
    assert r["result"] == "QUOTA_DEFERRED"
    occ = s.occurrence(r["occ_id"])
    assert occ["retry_at_us"] == 1_900_000_000_000_000 and occ["attempts"] == 0
    assert s.tick() == []                            # nothing runs before the reset
    assert len(h.calls) == 1


def test_failure_retries_with_backoff_then_fails(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"},
                  policy={"max_attempts": 2})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    h.script = ["invalid", "failed"]
    assert s.tick()[0]["result"] == "SCHEDULED"
    assert s.tick() == []
    clock.add(301)
    r = s.tick()[0]
    assert r["result"] == "FAILED"
    s.retry_occurrence(r["occ_id"], "owner")
    assert s.tick()[0]["result"] == "AWAITING_REVIEW"


def test_uncertain_is_never_auto_retried(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    h.script = ["uncertain"]
    assert s.tick()[0]["result"] == "NEEDS_ATTENTION"
    clock.add(86400)
    assert s.tick() == []


def test_interrupted_run_is_requeued_with_context(env):
    s, h, clock, tmp = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    occ_id = s.store.q1("SELECT occ_id FROM occurrence")[0]
    with s.store.tx() as db:   # simulate a process that died after claiming and starting an attempt
        db.execute("UPDATE occurrence SET state='RUNNING', attempts=1 WHERE occ_id=?", (occ_id,))
        db.execute("INSERT INTO attempt(occ_id,kind,mode,harness,started_at_us,supervisor_task_id) VALUES (?,?,?,?,?,?)",
                   (occ_id, "generate", "FIXTURE", "claude_fixture", clock(), "dead-task"))
    s.close()
    s2 = Scheduler(tmp / "state", harness=h, now_fn=clock).start()
    assert s2.startup["interrupted"] == [{"occ_id": occ_id, "next": "SCHEDULED", "why": "INTERRUPTED_NEVER_STARTED"}]
    assert s2.store.q1("SELECT outcome FROM attempt WHERE supervisor_task_id='dead-task'")[0] == "INTERRUPTED"
    assert s2.tick()[0]["result"] == "AWAITING_REVIEW"
    s2.close()


def test_cancel_pause_resume_reschedule(env):
    s, h, clock, _ = env
    p = festival_job(s, ("diwali", "dussehra"))
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    s.pause(p["job_id"], "owner")
    clock.set("2026-10-18T09:05:00+05:30")
    assert s.tick() == []
    s.resume(p["job_id"], "owner")
    dus = s.store.q1("SELECT occ_id FROM occurrence WHERE occurrence_key='dussehra:2026'")[0]
    s.reschedule_occurrence(dus, "owner", "2026-10-18T15:00")
    assert s.tick() == []
    clock.set("2026-10-18T15:00:01+05:30")
    dw = s.store.q1("SELECT occ_id FROM occurrence WHERE occurrence_key='diwali:2026'")[0]
    s.cancel_occurrence(dw, "owner")
    assert [r["occ_id"] for r in s.tick()] == [dus]
    with pytest.raises(SchedulerError):
        s.cancel_occurrence(dus, "intruder")
    s.cancel_job(p["job_id"], "owner")
    assert s.job(p["job_id"])["state"] == "CANCELLED"


def test_calendar_refresh_moves_not_duplicates(env):
    s, h, clock, _ = env
    p = festival_job(s, ("diwali", "holi"))
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    n0 = s.store.q1("SELECT COUNT(*) FROM occurrence")[0]
    new = json.loads(json.dumps(s.calendar.raw("in_festivals")))
    new["version"] = "2026-10-09.2"
    for f in new["festivals"]:
        if f["festival_key"] == "diwali":
            f["occurrences"][0]["start"] = "2026-11-09"
        if f["festival_key"] == "holi":
            f["occurrences"] = [o for o in f["occurrences"] if o["year"] != 2027]
    r = s.refresh_calendar(new)
    assert r["reconcile"]["moved"] == 1 and r["reconcile"]["withdrawn"] == 1 and r["reconcile"]["inserted"] == 0
    assert s.store.q1("SELECT COUNT(*) FROM occurrence")[0] == n0
    row = s.store.q1("SELECT due_at_us, state, reason, occ_id FROM occurrence WHERE occurrence_key='diwali:2026'")
    assert datetime.fromtimestamp(row[0] / 1e6, tz=timezone.utc).isoformat() == "2026-11-07T03:30:00+00:00"
    s.refresh_calendar(new)                                         # idempotent
    assert s.store.q1("SELECT COUNT(*) FROM occurrence")[0] == n0
    # a moved date was never shown to the owner: it waits for confirmation (review round 1, F4)
    assert (row[1], row[2]) == ("AWAITING_CONFIRMATION", "DATE_CHANGED_SINCE_CONFIRMATION")
    clock.set("2026-11-07T09:30:00+05:30")
    assert all(x["occ_id"] != row[3] for x in s.tick())
    with pytest.raises(SchedulerError):
        s.confirm_occurrence(row[3], "intruder")
    s.confirm_occurrence(row[3], "owner")
    assert s.tick()[0]["result"] == "AWAITING_REVIEW"


def test_r1_dates_beyond_the_shown_preview_wait_for_confirmation(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="f", template_id="festival_gif.v1", params={}, preview_days=20,
                  schedule={"kind": "calendar_relative", "calendar": "in_festivals", "selection": ["diwali", "dussehra"],
                            "offset_days": -2})
    assert [r["key"] for r in p["upcoming"]] == ["dussehra:2026"]
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    st = {r["occurrence_key"]: r["state"] for r in s.store.q("SELECT occurrence_key, state FROM occurrence")}
    assert st["dussehra:2026"] == "SCHEDULED" and st["diwali:2026"] == "AWAITING_CONFIRMATION"
    assert st["diwali:2027"] == "AWAITING_CONFIRMATION"


def test_r1_bad_params_refused(env):
    s, *_ = env
    for params in ("x", {"festival": {"key": "../../evil", "name": "x"}}, {"festival": {"key": "ok", "name": "n" * 200}},
                   {"unknown": 1}, {"style": 5}):
        with pytest.raises(SchedulerError) as e:
            s.propose(owner="o", title="t", template_id="festival_gif.v1", params=params,
                      schedule={"kind": "once", "at": "2026-10-10T09:00"})
        assert e.value.code == "BAD_PARAMS"


def _boom(*a, **k):
    raise RuntimeError("boom")


def test_r1_execution_error_never_leaves_running(env, monkeypatch):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    import uri_scheduler.gif_task as G
    monkeypatch.setattr(G, "build_package", _boom)
    r = s.tick()[0]
    assert r["result"] == "SCHEDULED" and r["reason"] == "RETRY:EXECUTION_ERROR:RuntimeError"
    assert s.store.q1("SELECT COUNT(*) FROM occurrence WHERE state='RUNNING'")[0] == 0


def test_r1_cancelled_job_closes_reviews_and_refuses_decisions(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    s.tick()
    a = s.overview()["pending_approvals"][0]["candidates"][0]
    s.cancel_job(p["job_id"], "owner")
    assert s.occurrence(a["occ_id"])["state"] == "CANCELLED"
    with pytest.raises(SchedulerError) as e:
        s.review(a["artifact_id"], "owner", "approve", expected_sha256=a["sha256"])
    assert e.value.code == "JOB_CANCELLED"


def test_r1_claim_refused_when_job_cancelled_after_selection(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    occ_id = s.store.q1("SELECT occ_id FROM occurrence")[0]
    with s.store.tx() as db:      # the job is cancelled between selection and claim
        db.execute("UPDATE job SET state='CANCELLED'")
    assert s._dispatch(occ_id)["result"] == "NOT_CLAIMED" and h.calls == []


def test_r1_oversize_gif_is_not_a_candidate(tmp_path, monkeypatch):
    import uri_scheduler.gif_task as G
    import uri_scheduler.renderer as R
    real = R.render_gif
    monkeypatch.setattr(R, "render_gif", lambda scene, out, **k: real(scene, out, max_bytes=1000))
    res = G.render_and_validate({"scene": tiny_scene()}, tmp_path, "x")
    assert res["quality"]["within_size_budget"] is False and res["ok"] is False


def _interrupt(s, clock, sup_task):
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    occ_id = s.store.q1("SELECT occ_id FROM occurrence")[0]
    ws = s.state_dir / "work" / f"occ_{occ_id}" / "attempt_1"
    with s.store.tx() as db:
        db.execute("UPDATE occurrence SET state='RUNNING', attempts=1 WHERE occ_id=?", (occ_id,))
        db.execute("INSERT INTO attempt(occ_id,kind,mode,harness,started_at_us,supervisor_task_id,workspace) VALUES (?,?,?,?,?,?,?)",
                   (occ_id, "generate", "FIXTURE", "claude_fixture", clock(), sup_task, str(ws)))
    return occ_id, ws


@pytest.mark.parametrize("settle,expect", [
    ({"state": "COMPLETE", "spawned": True, "absence_proven": False}, "COLLECT_PENDING"),
    ({"state": "FAILED", "spawned": True, "absence_proven": False}, "NEEDS_ATTENTION"),
    ({"state": "FAILED", "spawned": True, "absence_proven": True}, "SCHEDULED"),
    ({"state": "FAILED", "spawned": False, "absence_proven": False}, "SCHEDULED"),
])
def test_r1_restart_reconciles_before_rerunning(tmp_path, settle, expect):
    clock = Clock("2026-10-09T10:00:00+05:30")
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=clock).start()
    occ_id, ws = _interrupt(s, clock, "t1")
    if settle["state"] == "COMPLETE":     # the harness finished its files before the scheduler died
        ws.mkdir(parents=True)
        (ws / "scene.json").write_text(json.dumps(tiny_scene()), encoding="utf-8")
        (ws / "concept.md").write_text("# c", encoding="utf-8")
        (ws / "research.md").write_text("r", encoding="utf-8")
    s.close()
    h.settlement = lambda tid: dict(settle, task_id=tid)
    s2 = Scheduler(tmp_path / "state", harness=h, now_fn=clock).start()
    assert s2.occurrence(occ_id)["state"] == expect
    if expect == "COLLECT_PENDING":
        r = s2.tick()
        assert r[0]["result"] == "AWAITING_REVIEW" and h.calls == []          # collected; harness NOT re-run
    if expect == "NEEDS_ATTENTION":
        assert s2.tick() == [] and h.calls == []
    s2.close()


def test_r1_artifact_recorded_before_crash_is_not_regenerated(env):
    s, h, clock, tmp = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    s.tick()
    occ_id = s.store.q1("SELECT occ_id FROM occurrence")[0]
    with s.store.tx() as db:      # crash window: artifact inserted, _finish never ran
        db.execute("UPDATE occurrence SET state='RUNNING'")
        db.execute("UPDATE attempt SET ended_at_us=NULL")
    s.close()
    s2 = Scheduler(tmp / "state", harness=h, now_fn=clock).start()
    assert s2.occurrence(occ_id)["state"] == "AWAITING_REVIEW" and len(h.calls) == 1
    s2.close()


def test_review_binding_refine_regenerate_reject(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={"festival": {"key": "diwali", "name": "Diwali"}},
                  schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    s.tick()
    a1 = s.overview()["pending_approvals"][0]["candidates"][0]
    with pytest.raises(SchedulerError) as e:
        s.review(a1["artifact_id"], "owner", "approve", expected_sha256="f" * 64)
    assert e.value.code == "ARTIFACT_VERSION_MISMATCH"
    with pytest.raises(SchedulerError) as e:
        s.review(a1["artifact_id"], "intruder", "approve", expected_sha256=a1["sha256"])
    assert e.value.code == "NOT_OWNER"
    s.review(a1["artifact_id"], "owner", "approve", expected_sha256=a1["sha256"])
    # refining an approved version invalidates that approval
    s.review(a1["artifact_id"], "owner", "refine", expected_sha256=a1["sha256"], instruction="More floral energy")
    assert "approval.invalidated" in [e["kind"] for e in s.store.events()]
    assert s.occurrence(a1["occ_id"])["state"] == "REVISION_QUEUED"
    assert "More floral energy" in [c for c in h.calls][-1]["instructions"] or True
    s.tick()
    assert "More floral energy" in h.calls[-1]["instructions"]
    a2 = s.overview()["pending_approvals"][0]["candidates"][0]
    assert a2["version"] == 2 and a2["parent_artifact_id"] == a1["artifact_id"] and a2["sha256"] != a1["sha256"]
    assert s.artifact(a1["artifact_id"])["status"] == "SUPERSEDED"
    # regenerate keeps the original candidate
    s.review(a2["artifact_id"], "owner", "regenerate", expected_sha256=a2["sha256"])
    s.tick()
    cands = s.overview()["pending_approvals"][0]["candidates"]
    assert {c["version"] for c in cands} == {2, 3}
    # tampering with the file on disk blocks approval
    Path(cands[0]["path"]).write_bytes(b"GIF89a tampered")
    with pytest.raises(SchedulerError) as e:
        s.review(cands[0]["artifact_id"], "owner", "approve", expected_sha256=cands[0]["sha256"])
    assert e.value.code == "ARTIFACT_CHANGED_ON_DISK"
    s.review(cands[1]["artifact_id"], "owner", "reject", expected_sha256=cands[1]["sha256"])
    assert s.occurrence(a1["occ_id"])["state"] == "AWAITING_REVIEW"     # one candidate still open
    ev = [e for e in s.store.events() if e["kind"].startswith("review.")]
    assert all(e["payload"]["published"] is False for e in ev)
    with pytest.raises(sqlite3_error()):
        s.store.db.execute("UPDATE review SET action='approve'")


def sqlite3_error():
    import sqlite3
    return sqlite3.IntegrityError


def test_event_chain_detects_tamper(env):
    s, h, clock, _ = env
    festival_job(s)
    assert s.store.verify_chain()["ok"]
    import sqlite3
    with pytest.raises(sqlite3.IntegrityError):
        s.store.db.execute("UPDATE event SET kind='x'")


def test_r2_crash_between_collection_claim_and_attempt_reopen_never_reruns(tmp_path):
    clock = Clock("2026-10-09T10:00:00+05:30")
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=clock).start()
    occ_id, ws = _interrupt(s, clock, "t1")
    ws.mkdir(parents=True)
    (ws / "scene.json").write_text(json.dumps(tiny_scene()), encoding="utf-8")
    (ws / "concept.md").write_text("# c", encoding="utf-8")
    (ws / "research.md").write_text("r", encoding="utf-8")
    with s.store.tx() as db:      # old crash window: occurrence claimed for collection, attempt already ended
        db.execute("UPDATE attempt SET ended_at_us=1, outcome='HARNESS_COMPLETE_RECOVERED'")
    s.close()
    h.settlement = lambda tid: {"task_id": tid, "state": "COMPLETE", "spawned": True, "absence_proven": False}
    s2 = Scheduler(tmp_path / "state", harness=h, now_fn=clock).start()
    assert s2.occurrence(occ_id)["state"] == "COLLECT_PENDING"
    assert s2.tick()[0]["result"] == "AWAITING_REVIEW" and h.calls == []
    s2.close()


def test_r2_render_failure_after_harness_retries_collection_only(env, monkeypatch):
    s, h, clock, _ = env
    h.settlement = lambda tid: {"task_id": tid, "state": "COMPLETE", "spawned": True, "absence_proven": False}
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    import uri_scheduler.gif_task as G
    real = G.render_and_validate
    calls = {"n": 0}

    def flaky(*a, **k):
        calls["n"] += 1
        if calls["n"] == 1:
            raise OSError("disk full")
        return real(*a, **k)
    monkeypatch.setattr(G, "render_and_validate", flaky)
    r = s.tick()[0]
    assert r["result"] == "COLLECT_PENDING" and r["reason"] == "COLLECT_RETRY:RENDER_FAILED" and len(h.calls) == 1
    assert s.tick() == []                     # waits for the backoff
    clock.add(301)
    r = s.tick()[0]
    assert r["result"] == "AWAITING_REVIEW" and len(h.calls) == 1      # collected again; harness NOT re-run


def test_r3_failure_after_artifact_insert_does_not_duplicate(env, monkeypatch):
    s, h, clock, _ = env
    h.settlement = lambda tid: {"task_id": tid, "state": "COMPLETE", "spawned": True, "absence_proven": False}
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    real = s._finish
    calls = {"n": 0}

    def flaky(occ, job, attempt_id, state, reason, receipt, outcome, **cols):
        calls["n"] += 1
        if calls["n"] == 1 and state == "AWAITING_REVIEW":
            raise OSError("disk hiccup after the artifact row was committed")
        return real(occ, job, attempt_id, state, reason, receipt, outcome, **cols)
    monkeypatch.setattr(s, "_finish", flaky)
    r = s.tick()[0]
    assert r["result"] == "AWAITING_REVIEW" and s.store.q1("SELECT COUNT(*) FROM artifact")[0] == 1
    assert len(h.calls) == 1 and s.store.q1("SELECT COUNT(*) FROM occurrence WHERE state='RUNNING'")[0] == 0


def test_r4_policy_is_fully_validated(env):
    s, *_ = env
    for pol in ({"retry_backoff_s": []}, {"max_attempts": float("inf")}, {"max_attempts": 0}, {"grace_s": "1"},
                {"retry_backoff_s": [1, -5]}, {"bogus": 1}, {"max_attempts": True}, {"execution_time": "25:99"}):
        with pytest.raises(SchedulerError) as e:
            s.propose(owner="o", title="t", template_id="festival_gif.v1", params={},
                      schedule={"kind": "once", "at": "2026-10-10T09:00"}, policy=pol)
        assert e.value.code == "BAD_POLICY", pol
    assert Scheduler._backoff_s({"retry_backoff_s": []}, 2) == 300      # stored malformed policy never raises


def test_r4_cancel_during_run_wins_over_completion(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    real_run = h.run

    def run_then_cancel(**kw):
        out = real_run(**kw)
        occ_id = s.store.q1("SELECT occ_id FROM occurrence")[0]
        s.cancel_occurrence(occ_id, "owner")        # owner cancels while the harness work is finishing
        return out
    h.run = run_then_cancel
    r = s.tick()[0]
    assert r["result"] == "CANCELLED"
    assert s.store.q1("SELECT COUNT(*) FROM artifact WHERE status='CANDIDATE'")[0] == 0
    assert s.overview()["pending_approvals"] == []


def test_r5_cancel_during_gate_is_not_overwritten_by_blocked(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    real_gate = h.gate

    def gate_while_owner_cancels():
        occ_id = s.store.q1("SELECT occ_id FROM occurrence")[0]
        s.cancel_occurrence(occ_id, "owner")
        h.available, h.code = False, "NOT_AUTHENTICATED"
        return real_gate()
    h.gate = gate_while_owner_cancels
    r = s.tick()[0]
    occ = s.occurrence(r["occ_id"])
    assert occ["state"] == "CANCELLED" and occ["retry_at_us"] is None
    clock.add(7200)
    assert s.tick() == [] and h.calls == []


def test_r6_cancel_during_available_gate_never_runs_harness(env):
    s, h, clock, _ = env
    p = s.propose(owner="owner", title="t", template_id="festival_gif.v1", params={}, schedule={"kind": "once", "at": "2026-10-09T10:00"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    real_gate = h.gate

    def gate_while_owner_cancels():
        s.cancel_occurrence(s.store.q1("SELECT occ_id FROM occurrence")[0], "owner")
        return real_gate()                      # gate says AVAILABLE
    h.gate = gate_while_owner_cancels
    r = s.tick()[0]
    assert r["result"] == "CANCELLED" and h.calls == []
    assert s.store.q1("SELECT COUNT(*) FROM attempt")[0] == 0


def test_owner_calendar_corrections_move_dispute_restore_and_survive_restart(env):
    s, h, clock, tmp = env
    p = festival_job(s, ("diwali", "dussehra"))
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])

    def occ(k):
        return tuple(s.store.q1("SELECT occ_id, state, reason FROM occurrence WHERE occurrence_key=?", (k,)))

    assert occ("diwali:2026")[1] == "SCHEDULED"
    with pytest.raises(SchedulerError) as e:
        s.correct_calendar("owner", "in_festivals", "diwali", 2026, "set_date", start="2027-11-09")
    assert e.value.code == "BAD_CORRECTION"
    with pytest.raises(SchedulerError):
        s.correct_calendar("", "in_festivals", "diwali", 2026, "dispute")
    # a corrected date moves the occurrence and waits for the owner's confirmation of the new date
    r = s.correct_calendar("owner", "in_festivals", "diwali", 2026, "set_date", start="2026-11-09", note="local practice")
    assert r["version"].endswith("+owner.1") and r["reconcile"]["moved"] == 1
    assert occ("diwali:2026")[1:] == ("AWAITING_CONFIRMATION", "DATE_CHANGED_SINCE_CONFIRMATION")
    rec = next(x for x in s.calendar.records("in_festivals") if x["festival_key"] == "diwali" and x["year"] == 2026)
    assert rec["source"]["id"] == "owner_correction" and rec["corrected_from"]["start"] == "2026-11-08"
    # disputed: withdrawn; accepted again: back only as a date to confirm, never straight to SCHEDULED
    s.correct_calendar("owner", "in_festivals", "dussehra", 2026, "dispute", note="unsure")
    assert occ("dussehra:2026")[1:] == ("CANCELLED", "CALENDAR_WITHDRAWN")
    r = s.correct_calendar("owner", "in_festivals", "dussehra", 2026, "accept", note="checked")
    assert r["reconcile"]["restored"] == 1
    assert occ("dussehra:2026")[1:] == ("AWAITING_CONFIRMATION", "RESTORED_BY_CALENDAR")
    clock.set("2026-10-18T09:30:00+05:30")
    assert all(x["occ_id"] != occ("dussehra:2026")[0] for x in s.tick())
    # append-only and audited
    with pytest.raises(Exception):
        s.store.db.execute("UPDATE calendar_correction SET note='x'")
    kinds = [ev["kind"] for ev in s.store.events(limit=1000)]
    assert kinds.count("calendar.corrected") == 3
    # restart: the corrections are re-applied on the shipped calendar; no duplicate occurrences
    n = s.store.q1("SELECT COUNT(*) FROM occurrence")[0]
    s.close()
    s2 = Scheduler(tmp / "state", harness=h, now_fn=clock).start()
    try:
        assert s2.calendar.version("in_festivals").endswith("+owner.3")
        s2.materialize()
        assert s2.store.q1("SELECT COUNT(*) FROM occurrence")[0] == n
        assert s2.store.q1("SELECT state FROM occurrence WHERE occurrence_key='diwali:2026'")[0] == "AWAITING_CONFIRMATION"
    finally:
        s2.close()


def test_r9_occurrence_changed_after_selection_is_never_claimed(env):
    """Codex round 9, C1-01: a correction (or refresh) between due-selection and claim must win."""
    s, h, clock, _ = env
    p = festival_job(s, ("dussehra",))
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    occ_id = s.store.q1("SELECT occ_id FROM occurrence WHERE occurrence_key='dussehra:2026'")[0]
    clock.set("2026-10-18T09:20:00+05:30")                      # due (09:00) and past the 600 s grace: late-run branch
    s.correct_calendar("owner", "in_festivals", "dussehra", 2026, "set_date", start="2026-10-21")
    assert s._dispatch(occ_id) == {"occ_id": occ_id, "result": "NOT_CLAIMED"}
    row = s.store.q1("SELECT state, reason FROM occurrence WHERE occ_id=?", (occ_id,))
    assert tuple(row) == ("AWAITING_CONFIRMATION", "DATE_CHANGED_SINCE_CONFIRMATION")   # the late branch did not reset it
    s.correct_calendar("owner", "in_festivals", "dussehra", 2026, "dispute")
    assert s._dispatch(occ_id)["result"] == "NOT_CLAIMED"
    assert s.store.q1("SELECT state FROM occurrence WHERE occ_id=?", (occ_id,))[0] == "CANCELLED"
    assert h.calls == []


def test_r9_obsolete_correction_never_blocks_later_ones(env):
    """Codex round 9, C1-02: a stored correction that no longer applies is skipped and reported, not fatal."""
    s, h, clock, tmp = env
    s.correct_calendar("owner", "in_festivals", "losar", 2026, "dispute", note="old")
    s.close()
    cal = Calendar.default()
    data = json.loads(json.dumps(cal.raw("in_festivals")))
    data["festivals"] = [f for f in data["festivals"] if f["festival_key"] != "losar"]       # a later shipped calendar
    cal.put(data)
    s2 = Scheduler(tmp / "state", harness=h, now_fn=clock, calendar=cal).start()
    try:
        assert s2.startup["calendar_corrections_not_applied"][0]["error"].startswith("UNKNOWN_FESTIVAL")
        r = s2.correct_calendar("owner", "in_festivals", "holi", 2027, "dispute", note="new")
        assert r["version"].endswith("+owner.1") and r["not_applied"][0]["correction_id"] == 1
        assert s2.store.q1("SELECT COUNT(*) FROM calendar_correction")[0] == 2               # history kept
    finally:
        s2.close()


def test_r10_reconciliation_and_pre_claim_are_serialized(env):
    """Codex round 10, R10-01: materialize/refresh take the engine mutex, and each pre-claim transition re-checks the row."""
    import threading
    s, h, clock, _ = env
    p = festival_job(s, ("dussehra",))
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    occ_id = s.store.q1("SELECT occ_id FROM occurrence WHERE occurrence_key='dussehra:2026'")[0]
    clock.set("2026-10-18T09:20:00+05:30")
    stale = s.occurrence(occ_id)                              # what a dispatch read before a concurrent change
    s.correct_calendar("owner", "in_festivals", "dussehra", 2026, "set_date", start="2026-10-21")
    real = s.occurrence
    s.occurrence = lambda oid: stale if oid == occ_id else real(oid)
    try:
        assert s._dispatch(occ_id)["result"] == "NOT_CLAIMED"     # the late-run transition saw the row had changed
    finally:
        s.occurrence = real
    assert s.store.q1("SELECT state FROM occurrence WHERE occ_id=?", (occ_id,))[0] == "AWAITING_CONFIRMATION"
    assert h.calls == []
    done = threading.Event()
    with s._mutex:
        t = threading.Thread(target=lambda: (s.materialize(), done.set()))
        t.start()
        assert not done.wait(0.3)                              # blocked while another holder has the mutex
    assert done.wait(10)
    t.join()
