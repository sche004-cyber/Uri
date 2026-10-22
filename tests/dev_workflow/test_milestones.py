"""Milestone Manager tests (acceptance criteria F1-F18, N1, N3 in docs/milestone_manager/ACCEPTANCE_CRITERIA.md)."""
from __future__ import annotations

import ast
import datetime
import io
import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from scripts.dev_workflow.milestones import cli, importers, model, views
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.store import EventStore, StoreError, check_free_text, read_segment

ROOT = Path(__file__).resolve().parents[2]
C1 = "1" * 40
C2 = "2" * 40
UTC = datetime.timezone.utc


class Clock:
    def __init__(self):
        self.t = datetime.datetime(2026, 10, 21, 12, 0, tzinfo=UTC)

    def __call__(self):
        return self.t


def new(tmp_path, actor="impl:a", host="h1", **kw):
    home = tmp_path / "ledger"
    if not (home / "mm.json").exists():
        EventStore.init(home, host)
    return Manager(home, actor=actor, session="s1", **kw)


def _loss_first(fn):
    """Since review R13 a write that records a ledger loss is refused once (LEDGER_LOSS_RECORDED); the retry runs."""
    with pytest.raises(ValidationError) as e:
        fn()
    assert e.value.code == "LEDGER_LOSS_RECORDED"
    return fn()


def _resolve(m, entity, note):
    """Resolve every open conflict on ``entity`` by the ids `status`/`conflicts` show (review R14-01)."""
    ids = [r["id"] for r in views.conflict_rows(m.projection()) if r["entity"] == entity]
    return m.resolve_conflict(entity, note, ids)


def seg_bytes(mgr):
    return mgr.store.segment_path.read_bytes()


# ------------------------------------------------------------------ F1-F3 store integrity

def test_f1_append_only_prefix_preserved(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    m.update_milestone("MM-A", title="A2")
    m.set_status("MM-A", "IN_PROGRESS", "start")
    m.add_blocker("MM-A", "TECHNICAL", "r", "n")
    after = seg_bytes(m)
    assert after.startswith(before) and len(after) > len(before)


@pytest.mark.parametrize("attack", ["edit", "delete", "reorder", "insert"])
def test_f2_verify_detects_tampering(tmp_path, attack):
    m = new(tmp_path)
    for i in range(4):
        m.create_milestone(f"MM-{i}", f"t{i}")
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    if attack == "edit":
        lines[1] = lines[1].replace(b'"t1"', b'"tX"')
    elif attack == "delete":
        del lines[1]
    elif attack == "reorder":
        lines[1], lines[2] = lines[2], lines[1]
    else:
        lines.insert(2, lines[1])
    path.write_bytes(b"\n".join(lines) + b"\n")
    rep = m.store.verify()
    assert not rep["ok"] and rep["errors"]
    # and writes are refused on a broken chain
    with pytest.raises(StoreError):
        m.create_milestone("MM-Z", "z")


def test_f3_torn_tail_read_ignored_then_recovered(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.create_milestone("MM-B", "B")
    torn = b'{"v":1,"seg":"h1","seq":3,"ts":"2026'  # power loss mid-write
    with m.store.segment_path.open("ab") as f:
        f.write(torn)
    rep = m.store.verify()
    assert not rep["ok"] and rep["torn"] == [{"segment": "h1", "bytes": len(torn)}]
    p = m.projection()
    assert set(p["milestones"]) == {"MM-A", "MM-B"}
    with pytest.raises(StoreError) as e:
        m.create_milestone("MM-C", "C")
    assert e.value.code == "TORN_TAIL"
    res = m.store.recover("impl:a")
    assert res["recovered"] and res["bytes"] == len(torn)
    assert (m.store.home / res["quarantine"]).read_bytes().startswith(b'{"v":1')
    assert m.store.verify()["ok"]
    m.create_milestone("MM-C", "C")
    assert set(m.projection()["milestones"]) == {"MM-A", "MM-B", "MM-C"}
    assert m.projection()["recoveries"][0]["bytes"] == len(torn)


# ------------------------------------------------------------------ F4-F6 concurrency

WRITER = r"""
import sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones.service import Manager
m = Manager(sys.argv[2], actor="w" + sys.argv[3])
for i in range(int(sys.argv[4])):
    m.add_blocker("PROJECT", "OTHER", f"w{sys.argv[3]}-{i}", "n")
"""


def test_f4_parallel_processes_serialised(tmp_path):
    m = new(tmp_path)
    n_proc, n_ev = 4, 12
    procs = [subprocess.Popen([sys.executable, "-c", WRITER, str(ROOT), str(m.home), str(k), str(n_ev)])
             for k in range(n_proc)]
    assert all(p.wait(timeout=180) == 0 for p in procs)
    rep = m.store.verify()
    assert rep["ok"], rep
    assert rep["events"] == n_proc * n_ev
    p = m.rebuild()
    assert len(p["blockers"]) == n_proc * n_ev  # unique ids: BLK-1..BLK-48
    assert sorted(int(b.split("-")[1]) for b in p["blockers"]) == list(range(1, n_proc * n_ev + 1))


def test_f5_stale_expect_version_conflict(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    v = m.projection()["versions"]["MM-A"]
    m.update_milestone("MM-A", expect_version=v, objective="o1")
    size = len(seg_bytes(m))
    with pytest.raises(ValidationError) as e:
        m.update_milestone("MM-A", expect_version=v, objective="o2")
    assert e.value.code == "CONFLICT"
    assert len(seg_bytes(m)) == size


def test_f6_assignment_lease(tmp_path):
    clock = Clock()
    a = new(tmp_path, actor="agent:a", clock=clock)
    b = Manager(a.home, actor="agent:b", clock=clock)
    a.create_milestone("MM-A", "A")
    a.assign("MM-A", hours=1)
    with pytest.raises(ValidationError) as e:
        b.assign("MM-A")
    assert e.value.code == "ASSIGNED"
    with pytest.raises(ValidationError):
        b.release("MM-A", "steal")
    clock.t += datetime.timedelta(hours=2)
    with pytest.raises(ValidationError) as e:
        b.assign("MM-A")
    assert e.value.code == "EXPIRED_ASSIGNMENT"
    b.assign("MM-A", takeover=True)
    asg = b.projection()["milestones"]["MM-A"]["assignment"]
    assert asg["agent"] == "agent:b" and asg["takeover_of"] == "agent:a"


def test_cross_host_concurrent_update_is_a_conflict(tmp_path):
    """Two hosts edit the same milestone offline; after merging segments the fold flags a conflict (RED)."""
    m1 = new(tmp_path, actor="h1:agent")
    m1.create_milestone("MM-A", "A")
    # second host: copy the ledger, give it its own host id (as a git clone on another machine would)
    home2 = tmp_path / "ledger2"
    EventStore.init(home2, "h2")
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    m2 = Manager(home2, actor="h2:agent")
    m1.update_milestone("MM-A", objective="from h1")
    m2.update_milestone("MM-A", objective="from h2")
    # merge h2's segment into home 1
    (m1.home / "events" / "h2.jsonl").write_bytes((home2 / "events" / "h2.jsonl").read_bytes())
    p = m1.projection()
    assert m1.store.verify()["ok"]
    conflicts = views.open_conflicts(p, "MM-A")
    assert len(conflicts) == 1
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "RED"
    _resolve(m1, "MM-A", "kept h2 objective")
    p = m1.projection()
    assert not views.open_conflicts(p)


# ------------------------------------------------------------------ F7-F9 evidence guards

def _accept_ready(tmp_path, reviewer="subagent:r1", verdict="ACCEPT", blocking=0, result="COMPLETED_WITH_RESULT",
                  assurance="SUBAGENT", commit=C1):
    m = new(tmp_path, actor="impl:a")
    m.create_milestone("MM-A", "A")
    m.set_status("MM-A", "IN_PROGRESS", "start")
    m.update_milestone("MM-A", candidate_commit=C1)
    m.record_review("MM-A", commit, "subagent", reviewer, assurance, verdict, blocking, max(blocking, 2), result,
                    "review summary")
    return m


def test_f7_accepted_needs_independent_accept_on_exact_commit(tmp_path):
    _accept_ready(tmp_path).set_status("MM-A", "ACCEPTED", "independent accept")


@pytest.mark.parametrize("kw,code", [
    ({"reviewer": "impl:a"}, "NO_INDEPENDENT_ACCEPT"),                      # self review
    ({"commit": C2}, "NO_INDEPENDENT_ACCEPT"),                              # wrong commit
    ({"verdict": "REJECT", "blocking": 1}, "NO_INDEPENDENT_ACCEPT"),
    ({"result": "PENDING"}, "NO_INDEPENDENT_ACCEPT"),
    ({"result": "FAILED"}, "NO_INDEPENDENT_ACCEPT"),
    ({"result": "TIMED_OUT"}, "NO_INDEPENDENT_ACCEPT"),
    ({"assurance": "UNVERIFIED"}, "NO_INDEPENDENT_ACCEPT"),
])
def test_f7_accepted_refused_without_qualifying_review(tmp_path, kw, code):
    m = _accept_ready(tmp_path, **kw)
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == code


def test_f7_later_reject_outranks_earlier_accept(tmp_path):
    m = _accept_ready(tmp_path)
    m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "no")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "NEGATIVE_REVIEW"


def test_f7_positive_verdict_with_blocking_findings_refused(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    with pytest.raises(ValidationError):
        m.record_review("MM-A", C1, "subagent", "r", "SUBAGENT", "ACCEPT", 1, 1, "COMPLETED_WITH_RESULT", "x")


def test_f8_integrated_needs_owner_approval_and_integration_record(tmp_path):
    m = _accept_ready(tmp_path)
    m.set_status("MM-A", "ACCEPTED", "ok")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "INTEGRATED", "try")
    assert e.value.code == "NO_OWNER_INTEGRATION_APPROVAL"
    m.request_approval("MM-A", "INTEGRATION", "Integrate MM-A into canonical?")
    with pytest.raises(ValidationError):
        m.set_status("MM-A", "INTEGRATED", "try")
    m.resolve_approval("AP-1", "APPROVED", owner_words="Yes, integrate MM-A.", source="owner chat 2026-10-21")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "INTEGRATED", "try")
    assert e.value.code == "NO_INTEGRATION_RECORD"
    with pytest.raises(ValidationError):
        m.record_integration("MM-A", "canonical", C2)  # does not contain candidate (no repo given)
    m.record_integration("MM-A", "canonical", C1)
    m.set_status("MM-A", "INTEGRATED", "done")
    m.set_status("MM-A", "DONE", "closed")
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "GREEN"


def test_f8_integration_ancestry_checked_with_git(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    g = lambda *a: subprocess.run(["git", "-C", str(repo), *a], check=True, capture_output=True, text=True).stdout
    g("init", "-q")
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "a")
    a = g("rev-parse", "HEAD").strip()
    g("-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "--allow-empty", "-m", "b")
    b = g("rev-parse", "HEAD").strip()
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.update_milestone("MM-A", candidate_commit=b)
    with pytest.raises(ValidationError) as e:
        m.record_integration("MM-A", "main", a, repo=repo)
    assert e.value.code == "NOT_CONTAINED"
    m.update_milestone("MM-A", candidate_commit=a)
    m.record_integration("MM-A", "main", b, repo=repo)
    assert m.projection()["milestones"]["MM-A"]["integration"]["verified_by"].startswith("git merge-base")


def test_f9_owner_approval_needs_owner_words_and_source(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.request_approval("MM-A", "SCOPE", "Widen scope?")
    with pytest.raises(ValidationError):
        m.resolve_approval("AP-1", "APPROVED")
    with pytest.raises(ValidationError):
        m.resolve_approval("AP-1", "APPROVED", owner_words="yes")
    m.resolve_approval("AP-1", "DENIED", owner_words="No.", source="owner chat")
    a = m.projection()["approvals"]["AP-1"]
    assert a["status"] == "DENIED"
    assert a["resolution"]["assurance"] == "OWNER_RELAYED" and a["resolution"]["relayed_by"] == "impl:a"
    with pytest.raises(ValidationError):
        m.resolve_approval("AP-1", "APPROVED", owner_words="yes", source="x")


# ------------------------------------------------------------------ F10-F12

def test_f10_decisions_never_overwritten(tmp_path):
    m = new(tmp_path)
    m.record_decision("Use JSONL", "Ledger is JSONL", "2026-10-21", "OWNER-PROMPT", "prompt", ident="LDEC-091")
    with pytest.raises(ValidationError) as e:
        m.record_decision("Other", "x", "2026-10-21", "OWNER-PROMPT", "prompt", ident="LDEC-091")
    assert e.value.code == "EXISTS"
    m.record_decision("Use SQLite", "Ledger is SQLite", "2026-10-22", "OWNER-PROMPT", "prompt",
                      supersedes="LDEC-091", reasoning="scale")
    m.correct_decision("LDEC-091", "date was 2026-10-21 UTC", "AGENT-RECORD", "review R1")
    p = m.projection()
    old, new_ = p["decisions"]["LDEC-091"], p["decisions"]["LDEC-092"]
    assert old["decision"] == "Ledger is JSONL" and old["status"] == "SUPERSEDED"
    assert old["superseded_by"][0]["by"] == "LDEC-092" and new_["supersedes"][0]["id"] == "LDEC-091"
    assert old["corrections"][0]["correction"].startswith("date")
    with pytest.raises(ValidationError) as e:  # owner-register numbering is reserved until promotion (R2-07)
        m.record_decision("X", "x", "2026-10-21", "OWNER-PROMPT", "prompt", ident="DEC-200")
    assert e.value.code == "DEC_NAMESPACE"


def test_f11_dependencies_cycles_and_ready(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A", priority="P0")
    m.create_milestone("MM-B", "B", priority="P1", depends_on=["MM-A"])
    m.create_milestone("MM-C", "C", priority="P2", depends_on=["MM-B"])
    with pytest.raises(ValidationError) as e:
        m.add_dependency("MM-A", "MM-C")
    assert e.value.code == "CYCLE"
    with pytest.raises(ValidationError):
        m.add_dependency("MM-A", "MM-A")
    assert views.ready(m.projection()) == ["MM-A"]
    m.add_blocker("MM-A", "TECHNICAL", "x", "y")
    assert views.ready(m.projection()) == []


def test_f12_indicators_derived_with_text(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    p = m.projection()
    ind = views.indicator(p, p["milestones"]["MM-A"])
    assert (ind["color"], ind["word"], ind["phase"]) == ("WHITE", "NOT ACTIVE", "RESEARCH")
    m.set_status("MM-A", "IN_PROGRESS", "go")
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "BLUE"
    m.request_approval("MM-A", "SCOPE", "ok?")
    p = m.projection()
    ind = views.indicator(p, p["milestones"]["MM-A"])
    assert ind["color"] == "YELLOW" and "AP-1" in ind["issue"] and ind["next_action"]
    m.add_blocker("MM-A", "RESOURCE", "GPU busy", "lease")
    p = m.projection()
    ind = views.indicator(p, p["milestones"]["MM-A"])
    assert ind["color"] == "RED" and "GPU busy" in ind["issue"] and ind["more_issues"] == 1
    # status is never stored as a colour
    assert "color" not in json.dumps(p["milestones"]["MM-A"])
    tasks = {"available": True, "tasks": [{"task_id": "TASK-1", "status": "BLOCKED"}]}
    m.resolve_blocker("BLK-1", "lease granted")
    m.resolve_approval("AP-1", "WITHDRAWN", reason="not needed")
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"], tasks)["color"] == "RED"
    assert views.indicator(p, p["milestones"]["MM-A"], {"available": False, "integrity_failure": True,
                                                         "reason": "x"})["color"] == "RED"


# ------------------------------------------------------------------ F13 resume

def test_f13_resume_answers_seven_questions_bounded(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A", objective="Build the registry", acceptance_ref="docs/AC.md",
                       depends_on=[], next_action="write tests")
    m.create_milestone("MM-B", "B", depends_on=["MM-A"])
    m.set_status("MM-A", "IN_PROGRESS", "go")
    m.update_milestone("MM-A", candidate_commit=C1)
    m.add_evidence("MM-A", "test_run", "pytest tests/x", "COMPLETED_WITH_RESULT", "40 passed", sha256="a" * 64)
    m.record_review("MM-A", C1, "subagent", "subagent:r1", "SUBAGENT", "REJECT", 2, 3, "COMPLETED_WITH_RESULT",
                    "two HIGH findings")
    m.request_approval("MM-A", "INTEGRATION", "Integrate?")
    m.add_blocker("MM-A", "REVIEWER_UNAVAILABLE", "Codex quota", "wait until 2026-10-22")
    m.record_handoff("MM-A", "context ran out", done="store done", next_action="fix R1", files=["a.py"], commit=C1)
    tasks = {"available": True, "tasks": [{"task_id": "TASK-20261021-0000aaaa", "status": "IN_PROGRESS",
                                           "title": "views", "next_action": "finish"}]}
    text = views.resume_brief(m.projection(), "MM-A", tasks)
    for marker in ("1. REQUESTED: Build the registry", "2. COMPLETED", "3. EVIDENCE (1)", "4. REJECTED",
                   "two HIGH findings", "5. UNFINISHED", "Codex quota", "TASK-20261021-0000aaaa", "6. SAFE NEXT",
                   "7. OWNER APPROVAL NEEDED", "AP-1"):
        assert marker in text, marker
    for i in range(80):
        m.add_evidence("MM-A", "log", f"log{i}", "COMPLETED_WITH_RESULT", "x" * 300, sha256=f"{i:064x}")
    short = views.resume_brief(m.projection(), "MM-A", tasks, max_chars=1500)
    assert len(short) <= 1500 and "truncated" in short


# ------------------------------------------------------------------ F14 importers

DECISIONS_MD = """# decisions
| ID | Date | Title | Decision text | Reasoning (recorded) | Alternatives / rejected | Later corrections / supersession | Scope & limits | Approval requirement | Related milestones | Applicability | Source(s) | Evidence class |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| DEC-001 | 2026-09-05 | Loop | the loop | — | — | — | all | — | — | ACTIVE | CAN x | REPO-RECORD |
| DEC-002 | 2026-09-10 | Old | old way | — | — | superseded by DEC-003 | dev | — | — | SUPERSEDED by DEC-003 | MEM y | MEMORY-ONLY |
| DEC-003 | 2026-09-11 | New | new way | why | old way | — | dev | — | — | ACTIVE | CAN z | REPO-RECORD |

## 3. Open owner decisions
| Ref | Question | Context | Where |
|---|---|---|---|
| OPEN-01 | Integrate X? | ready | plan |
"""


def test_f14_import_decisions_provenance_idempotent_and_revision(tmp_path):
    src = tmp_path / "decisions.md"
    src.write_bytes(DECISIONS_MD.encode())
    m = new(tmp_path)
    r = importers.import_decisions(m, src, commit="8e1d6324")
    assert (r["recorded"], r["supersessions"], r["open_questions"]) == (3, 1, 1)
    p = m.projection()
    d2 = p["decisions"]["DEC-002"]
    assert d2["status"] == "SUPERSEDED" and d2["superseded_by"][0]["by"] == "DEC-003"
    assert d2["source"]["line"] == 5 and d2["source"]["commit"] == "8e1d6324" and len(d2["source"]["file_sha256"]) == 64
    assert p["approvals"]["AP-1"]["alias"] == "OPEN-01"
    before = len(seg_bytes(m))
    r2 = importers.import_decisions(m, src, commit="8e1d6324")
    assert r2["recorded"] == 0 and r2["unchanged"] == 3 and r2["open_questions"] == 0
    assert len(m.projection()["decisions"]) == 3
    assert len(seg_bytes(m)) > before  # only the IMPORT_RECORDED provenance event
    src.write_bytes(DECISIONS_MD.replace("the loop", "the loop (clarified)").encode())
    r3 = importers.import_decisions(m, src)
    assert r3["revised"] == 1
    d1 = m.projection()["decisions"]["DEC-001"]
    assert d1["decision"] == "the loop" and "clarified" in d1["source_revisions"][0]["raw"]


REGISTER_MD = """# register
## B. Capability inventory
| ID | Capability | Status |
|---|---|---|
| CAP-1 | Thing | GREEN |
| CAP-2 | Other | **BLUE** |
## C. Milestone roadmap and dependencies
| ID | Milestone | Depends on | State 2026-10-21 |
|---|---|---|---|
| P0 | Audit | — | BLUE (this audit) |
## J. Known defects
| ID | Severity | Area | Defect | Location | Next action |
|---|---|---|---|---|---|
| CRASH-1 / DEMOTE-P1 | open | runtime | crash | — | owner |
"""


def test_f14_import_register(tmp_path):
    src = tmp_path / "developmental.md"
    src.write_bytes(REGISTER_MD.encode())
    m = new(tmp_path)
    r = importers.import_register(m, src)
    assert r["recorded"] == 4
    recs = m.projection()["records"]
    assert recs["REG-B-CAP-1"]["color"] == "GREEN" and recs["REG-B-CAP-2"]["color"] == "BLUE"
    assert recs["REG-C-P0"]["record_type"] == "roadmap"
    assert "REG-J-CRASH-1_DEMOTE-P1" in recs
    assert importers.import_register(m, src)["unchanged"] == 4


def test_f14_real_p0_registers_if_present(tmp_path):
    dec = Path("D:/uri-dev/uri-p0-audit/decisions.md")
    reg = Path("D:/uri-dev/uri-p0-audit/developmental.md")
    if not (dec.is_file() and reg.is_file()):
        pytest.skip("P0 audit worktree not present on this host")
    m = new(tmp_path)
    r = importers.import_decisions(m, dec)
    assert r["recorded"] >= 90 and not r["skipped_secret"]
    assert importers.import_register(m, reg)["recorded"] > 50
    assert m.store.verify()["ok"]


# ------------------------------------------------------------------ F15 lifecycle

def _lifecycle_state_dir(tmp_path, blocker_kind="OWNER_AUTHORIZATION"):
    from scripts.dev_workflow.lifecycle import State  # the real driver's event writer
    sd = tmp_path / "lc_state"
    st = State({"state_dir": str(sd), "milestone": "DEVTEST-MM"})
    st.d["candidate"] = C1
    st.event("PLAN", baseline=C2, candidate=C1)
    st.event("REVIEW_RECORDED", round=1, candidate=C1, verdict="ACCEPT", independent=True, outcome="ACCEPT",
             provider="codex_cli", status="COMPLETED_WITH_RESULT")
    st.d["stage"] = "BLOCKED"
    st.d["blocker"] = {"kind": blocker_kind, "reason": "awaiting owner", "needs": "authorized: true", "at": "x",
                       "stage": "VERIFIED"}
    st.event("STAGE", stage="BLOCKED", frm="VERIFIED", reason="x")
    return sd


def test_f15_lifecycle_snapshot_from_real_driver_chain(tmp_path):
    sd = _lifecycle_state_dir(tmp_path)
    before = {p.name: p.read_bytes() for p in sd.iterdir()}
    snap = importers.read_lifecycle_snapshot(sd)
    assert snap["chain_ok"], snap["errors"]
    assert snap["stage"] == "BLOCKED" and snap["blocker"]["kind"] == "OWNER_AUTHORIZATION"
    assert snap["latest_review"]["verdict"] == "ACCEPT" and snap["candidate"] == C1
    assert {p.name: p.read_bytes() for p in sd.iterdir()} == before  # read-only
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    with pytest.raises(ValidationError):
        m.sync_lifecycle("MM-A", sd)
    m.link_lifecycle("MM-A", sd)
    m.sync_lifecycle("MM-A", sd)
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "YELLOW"
    # tamper with the lifecycle chain -> RED
    ev = sd / "events.jsonl"
    ev.write_bytes(ev.read_bytes().replace(b"codex_cli", b"claude_cli"))
    assert not importers.read_lifecycle_snapshot(sd)["chain_ok"]
    m.sync_lifecycle("MM-A", sd)
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "RED"


def test_f15_real_lifecycle_dir_if_present():
    sd = Path("D:/uri-dev/lifecycle/LIFECYCLE-REVIEWER-TIERS-r11/state")
    if not (sd / "state.json").is_file():
        pytest.skip("historical lifecycle run not present on this host")
    snap = importers.read_lifecycle_snapshot(sd)
    assert snap["chain_ok"], snap["errors"]
    assert snap["events"] >= 1 and snap["candidate"]


# ------------------------------------------------------------------ F16-F18

@pytest.mark.parametrize("secret", [
    "key sk-ant-abcdefghijklmnopqrstuvwxyz0123",
    "ghp_" + "a" * 36,
    "AKIA" + "ABCDEFGHIJKLMNOP",
    "-----BEGIN RSA PRIVATE KEY-----",
    "password = hunter2abc9",
    "Authorization: Bearer abcdefghijklmnopqrstuvwxyz012345",
])
def test_f16_secrets_refused(tmp_path, secret):
    m = new(tmp_path)
    size = len(seg_bytes(m)) if m.store.segment_path.exists() else 0
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-A", "A", objective=f"note: {secret}")
    assert e.value.code == "SECRET"
    assert (len(seg_bytes(m)) if m.store.segment_path.exists() else 0) == size


@pytest.mark.parametrize("text", ["the api-token file inherits the folder ACL", "token comparison not constant-time",
                                  "password reset flow", "D10 random key-store secret every start"])
def test_f16_no_false_positive_on_prose(tmp_path, text):
    assert model.find_secret(text) is None


def test_f17_projection_always_derived_from_verified_log(tmp_path):
    """Amended F17 (after R1-02/06/08): no projection cache exists; a stray cache file is never read."""
    m = new(tmp_path)
    for i in range(30):
        m.create_milestone(f"MM-{i}", f"t{i}")
    cache = m.home / "cache" / "projection.json"
    cache.parent.mkdir(exist_ok=True)
    cache.write_text(json.dumps({"state": {"milestones": {"FORGED": {}}}}), encoding="utf-8")
    p = m.projection()
    assert "FORGED" not in p["milestones"] and len(p["milestones"]) == 30 and p["events"] == 30


def test_f18_status_json_schema(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A", priority="P0")
    out = io.StringIO()
    rc = cli.run(["--home", str(m.home), "status", "--json", "--no-tasks"], out=out)
    assert rc == 0
    st = json.loads(out.getvalue())
    assert st["schema"] == "uri-mm-status/1"
    ms = st["milestones"][0]
    assert set(ms) >= {"id", "title", "priority", "phase", "status", "indicator", "depends_on", "ready",
                       "open_approvals", "open_blockers", "assignment", "candidate_commit", "integration", "lifecycle"}
    assert set(ms["indicator"]) == {"color", "word", "tone", "issue", "next_action"}


def test_cli_roundtrip_and_exit_codes(tmp_path):
    home = tmp_path / "h"
    run = lambda *a: cli.run(["--home", str(home), "--actor", "cli:a", *a], out=io.StringIO())
    assert run("init", "--host-id", "cli") == 0
    assert run("milestone-add", "MM-A", "--title", "A", "--priority", "P0") == 0
    assert run("status-set", "MM-A", "ACCEPTED", "--reason", "x") == 1  # refused
    assert cli.run(["--home", str(home), "milestone-add", "MM-B", "--title", "B"], out=io.StringIO()) == 1  # no actor
    assert run("verify") == 0
    out = io.StringIO()
    cli.run(["--home", str(home), "--no-emoji", "status", "--no-tasks"], out=out)
    assert "NOT ACTIVE" in out.getvalue() and "\u26AA" not in out.getvalue()
    out = io.StringIO()
    cli.run(["--home", str(home), "status", "--a2ui", "--no-tasks"], out=out)
    assert json.loads(out.getvalue())["surface_id"] == "dev.milestones"


def test_task_ledger_absent_is_reported_not_fatal(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    t = m.task_summaries("MM-A")
    if not (ROOT / "scripts" / "dev_workflow" / "task_ledger.py").is_file():
        assert t["available"] is False and "not installed" in t["reason"]
    assert "RESUME MM-A" in views.resume_brief(m.projection(), "MM-A", t)


def test_git_autocommit(tmp_path):
    home = tmp_path / "ledger"
    home.mkdir()
    subprocess.run(["git", "-C", str(home), "init", "-q"], check=True)
    EventStore.init(home, "h1", autocommit=True)
    m = Manager(home, actor="a")
    m.create_milestone("MM-A", "A")
    log = subprocess.run(["git", "-C", str(home), "log", "--oneline"], capture_output=True, text=True).stdout
    assert "MILESTONE_CREATED" in log
    assert m.store.verify()["git"] == {"tracked": True, "uncommitted": []}


# ------------------------------------------------------------------ N1, N3

def test_n1_stdlib_only():
    pkg = ROOT / "scripts" / "dev_workflow" / "milestones"
    allowed_internal = ("scripts.dev_workflow.milestones",)
    stdlib = set(sys.stdlib_module_names)
    for f in pkg.glob("*.py"):
        tree = ast.parse(f.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                assert n.split(".")[0] in stdlib or n.startswith(allowed_internal) or n == "__future__", (f.name, n)


def test_n3_performance_10k_events(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    # bulk-write 10,000 evidence events through the real append path under one lock
    with m.store.locked():
        for i in range(10_000):
            m.store.append("EVIDENCE_ADDED", {"id": f"EV-{i:016x}", "subject": "MM-A", "kind": "log", "ref": f"r{i}",
                                              "sha256": None, "commit": None, "result_class": "COMPLETED_WITH_RESULT",
                                              "summary": "perf"}, actor="perf")
    t0 = time.perf_counter()
    p = m.rebuild()
    t_rebuild = time.perf_counter() - t0
    t0 = time.perf_counter()
    views.status_json(m.projection())
    t_status = time.perf_counter() - t0
    size = m.store.segment_path.stat().st_size
    record = {"events": p["events"], "rebuild_s": round(t_rebuild, 3), "status_s": round(t_status, 3),
              "bytes": size}
    print("N3", json.dumps(record))
    assert p["events"] == 10_001
    assert t_rebuild < 3.0 and t_status < 1.0 and size < 10 * 1024 * 1024


# ------------------------------------------------------------------ R1 regression tests (review R1 on 2ae7a79f)

def test_r1_01_candidate_locked_after_accept_and_integration_bound_to_candidate(tmp_path):
    m = _accept_ready(tmp_path)
    m.set_status("MM-A", "ACCEPTED", "ok")
    with pytest.raises(ValidationError) as e:
        m.update_milestone("MM-A", candidate_commit=C2)
    assert e.value.code == "CANDIDATE_LOCKED"
    # demote, change candidate: the old ACCEPT no longer counts
    m.set_status("MM-A", "IN_PROGRESS", "new candidate")
    m.update_milestone("MM-A", candidate_commit=C2)
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "NO_INDEPENDENT_ACCEPT"


def test_r1_01_integration_record_must_match_current_candidate(tmp_path):
    m = _accept_ready(tmp_path)
    m.record_integration("MM-A", "canonical", C1)
    m.set_status("MM-A", "ACCEPTED", "ok")
    m.request_approval("MM-A", "INTEGRATION", "integrate?")
    m.resolve_approval("AP-1", "APPROVED", owner_words="yes", source="chat")
    # forge: integration record for another candidate (fold-level edit is impossible via API; use the guard path)
    p = m.projection()
    mm = dict(p["milestones"]["MM-A"])
    mm["integration"] = {**mm["integration"], "candidate_commit": C2}
    with pytest.raises(ValidationError) as e:
        m.guard_status(p, mm, "INTEGRATED")
    assert e.value.code == "NO_INTEGRATION_RECORD"


def test_r1_02_guard_does_not_trust_cache_and_fold_flags_unbacked_basis(tmp_path):
    m = _accept_ready(tmp_path, verdict="REJECT", blocking=1)
    cache = m.home / "cache" / "projection.json"
    cache.parent.mkdir(exist_ok=True)
    cache.write_text('{"schema": "uri-mm-projection/1", "segments": {}, "state": {}}', encoding="utf-8")
    with pytest.raises(ValidationError):
        m.set_status("MM-A", "ACCEPTED", "try")
    # an ACCEPTED event whose basis names no real review (e.g. written by an old or forged writer) is flagged RED
    with m.store.locked():
        m.store.append("MILESTONE_STATUS_SET", {"id": "MM-A", "status": "ACCEPTED", "reason": "x",
                                                "basis": {"reviews": ["RV-99"]}}, actor="forger")
    p = m.projection()
    assert any(c["type"] == "BASIS_INVALID" for c in views.open_conflicts(p, "MM-A"))
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "RED"


def test_r1_03_later_reject_blocks_done_and_integrated_and_shows_red(tmp_path):
    m = _accept_ready(tmp_path)
    m.set_status("MM-A", "ACCEPTED", "ok")
    m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "REJECT", 2, 2, "COMPLETED_WITH_RESULT", "no")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "DONE", "close")
    assert e.value.code == "NEGATIVE_REVIEW"
    p = m.projection()
    ind = views.indicator(p, p["milestones"]["MM-A"])
    assert ind["color"] == "RED" and "REJECT" in ind["issue"]


def test_r1_04_tampered_events_not_folded_and_reported(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.set_status("MM-A", "IN_PROGRESS", "go")
    path = m.store.segment_path
    path.write_bytes(path.read_bytes().replace(b'"status":"IN_PROGRESS"', b'"status":"ACCEPTED"'))
    p = m.projection()
    assert p["integrity_errors"]
    assert p["milestones"]["MM-A"]["status"] == "PLANNED"  # the edited event is not trusted
    out = io.StringIO()
    rc = cli.run(["--home", str(m.home), "--no-emoji", "status", "--no-tasks"], out=out)
    assert rc == 3 and "LEDGER INTEGRITY FAILURE" in out.getvalue()
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "resume", "MM-A", "--no-tasks"], out=out) == 3
    assert "LEDGER INTEGRITY FAILURE" in out.getvalue()


def _two_hosts(tmp_path):
    m1 = new(tmp_path, actor="h1:agent")
    home2 = tmp_path / "ledger2"
    EventStore.init(home2, "h2")
    m2 = Manager(home2, actor="h2:agent")
    return m1, m2, home2


def _merge(m1, home2):
    (m1.home / "events" / "h2.jsonl").write_bytes((home2 / "events" / "h2.jsonl").read_bytes())


def test_r1_05_same_ids_on_two_hosts_never_overwrite(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    for m in (m1, m2):
        m.create_milestone("MM-A", "A")
    m1.record_decision("Keep X", "keep", "2026-10-21", "AGENT-RECORD", "h1")
    m2.record_decision("Drop X", "drop", "2026-10-21", "AGENT-RECORD", "h2")
    m1.update_milestone("MM-A", candidate_commit=C1)
    m1.record_review("MM-A", C1, "subagent", "r1", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "h1 reject")
    m2.update_milestone("MM-A", candidate_commit=C1)
    m2.record_review("MM-A", C1, "subagent", "r2", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "h2 accept")
    _merge(m1, home2)
    p = m1.projection()
    decisions = {d["decision"] for d in p["decisions"].values()}
    assert decisions == {"keep", "drop"}
    verdicts = sorted(r["verdict"] for r in p["reviews"].values())
    assert verdicts == ["ACCEPT", "REJECT"]
    assert any(c["type"] == "DUPLICATE_ID" for c in views.open_conflicts(p))
    with pytest.raises(ValidationError) as e:
        m1.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "CONFLICT_OPEN"


def test_r1_06_tamper_in_other_hosts_segment_blocks_writes(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m2.create_milestone("MM-B", "Bee")
    _merge(m1, home2)
    m1.create_milestone("MM-A", "A")
    seg = m1.home / "events" / "h2.jsonl"
    seg.write_bytes(seg.read_bytes().replace(b'"Bee"', b'"Bxx"'))
    with pytest.raises(StoreError) as e:
        m1.create_milestone("MM-C", "C")
    assert e.value.code == "CHAIN_BROKEN"
    assert not m1.store.verify()["ok"]


def test_r1_07_deleting_newest_events_detected(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.record_decision("D", "d", "2026-10-21", "AGENT-RECORD", "s")
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(b"\n".join(lines[:-1]) + b"\n")
    rep = m.store.verify()
    assert not rep["ok"] and any("deleted" in x for x in rep["errors"])
    with pytest.raises(StoreError):
        m.create_milestone("MM-B", "B")


def test_r1_08_events_arriving_during_a_write_are_folded(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-A", "A")
    m2.create_milestone("MM-B", "B")
    _merge(m1, home2)  # arrives "outside the lock" (e.g. git pull)
    m1.create_milestone("MM-C", "C")
    assert set(m1.projection()["milestones"]) == {"MM-A", "MM-B", "MM-C"}


@pytest.mark.parametrize("secret", [
    "key sk_" + "live_" + "4eC39HqLyjWDarjtT1zdp7dcAbCdEf",
    "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U",
    "password = hunter",
    "token=" + "9f86d081884c7d659a2feaa0c55ad015",
    "hf_" + "AbCdEfGhIjKlMnOpQrStUvWxYz012345",
    "https://user:pa55word@example.com/repo",
    "client_secret: abcd1234efgh",
])
def test_r1_09_more_secret_forms_refused(secret):
    assert model.find_secret(secret), secret


@pytest.mark.parametrize("text", ["worktree=D:/uri-dev/worktree1", "api_key: env:VAR_NAME1", "API_KEY=$OPENAI_API_KEY",
                                  "token: TAVILY_API_KEY", "password: required", "see https://example.com/a:b"])
def test_r1_09_no_false_positive_on_paths_and_env_names(text):
    assert model.find_secret(text) is None, text


def test_r6_01_pwd_path_assignment_is_a_credential():
    assert model.find_secret("pwd=D:/uri-dev/worktree1") == "credential assignment"


def test_r1_10_secret_row_skipped_without_refusing_import(tmp_path):
    src = tmp_path / "decisions.md"
    bad = "| DEC-004 | 2026-09-12 | Bad | x | — | — | Superseded by DEC-003 after password: hunter2abc9 | " \
          "s | — | — | SUPERSEDED | CAN | REPO-RECORD |\n"
    src.write_bytes((DECISIONS_MD.split("\n## 3.")[0] + bad).encode())
    m = new(tmp_path)
    r = importers.import_decisions(m, src)
    assert r["skipped_secret"] == ["DEC-004"] and r["recorded"] == 3
    assert "DEC-004" not in m.projection()["decisions"]


def test_r1_11_partial_supersession_statuses():
    assert importers.source_status("SUPERSEDED in part (no paid licences)") == "PARTIALLY_SUPERSEDED"
    assert importers.source_status("SUPERSEDED for later phases by per-phase rules") == "PARTIALLY_SUPERSEDED"
    assert importers.source_status("SUPERSEDED (run-scoped)") == "PARTIALLY_SUPERSEDED"
    assert importers.source_status("SUPERSEDED (history)") == "SUPERSEDED"
    assert importers.source_status("SUPERSEDED by DEC-004") == "SUPERSEDED"
    assert importers.source_status("PARTLY SUPERSEDED (x)") == "PARTIALLY_SUPERSEDED"


def test_r1_11_real_decisions_partial_links_if_present(tmp_path):
    dec = Path("D:/uri-dev/uri-p0-audit/decisions.md")
    if not dec.is_file():
        pytest.skip("P0 audit worktree not present on this host")
    m = new(tmp_path)
    importers.import_decisions(m, dec)
    d = m.projection()["decisions"]
    assert d["DEC-053"]["status"] == "PARTIALLY_SUPERSEDED"
    assert d["DEC-062"]["status"] == "PARTIALLY_SUPERSEDED"
    assert d["DEC-003"]["status"] == "SUPERSEDED"
    assert all(s["partial"] for s in d["DEC-012"]["superseded_by"] if s["by"] == "DEC-066")


def test_r1_12_cli_errors_are_json_with_exit_2(tmp_path):
    home = tmp_path / "h"
    run = lambda *a: cli.run(["--home", str(home), "--actor", "a", *a], out=io.StringIO())
    run("init", "--host-id", "h")
    run("milestone-add", "MM-A", "--title", "A")
    assert run("import-decisions", str(tmp_path / "missing.md")) == 2
    assert run("evidence-add", "MM-A", "--kind", "log", "--ref", "x", "--result", "COMPLETED_WITH_RESULT",
               "--summary", "s", "--file", str(tmp_path / "nope.log")) == 2
    sd = tmp_path / "lc"
    sd.mkdir()
    (sd / "state.json").write_text('{"stage": "BLOCKED", "history": [{}]}', encoding="utf-8")
    (sd / "events.jsonl").write_text('[1,2]\n{"seq": 1}\n', encoding="utf-8")
    snap = importers.read_lifecycle_snapshot(sd)
    assert snap["chain_ok"] is False and snap["errors"]
    run("link-lifecycle", "MM-A", str(sd))
    assert run("sync-lifecycle", "MM-A", str(sd)) == 0


def test_r1_14_reviewer_identity_case_insensitive(tmp_path):
    m = _accept_ready(tmp_path, reviewer="IMPL:A ")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "self")
    assert e.value.code == "NO_INDEPENDENT_ACCEPT"


def test_r1_15_multi_event_command_is_atomic(tmp_path, monkeypatch):
    m = new(tmp_path)
    m.record_decision("Old", "old", "2026-10-21", "AGENT-RECORD", "s")
    # crash after the first line of a two-event batch: simulate by writing only the first event of the batch
    real = m.store.append_many
    def half(items, actor, session=None, ts=None, floor=""):
        evs = real(items, actor, session, ts, floor)
        path = m.store.segment_path
        lines = path.read_bytes().split(b"\n")[:-1]
        path.write_bytes(b"\n".join(lines[:-1]) + b"\n" + lines[-1][:20])  # second event torn
        raise OSError("ENOSPC simulated")
    monkeypatch.setattr(m.store, "append_many", half)
    with pytest.raises(OSError):
        m.record_decision("New", "new", "2026-10-22", "AGENT-RECORD", "s", supersedes="LDEC-001")
    monkeypatch.undo()
    m.store.recover("impl:a")
    p = m.projection()
    assert set(p["decisions"]) == {"LDEC-001"} and p["decisions"]["LDEC-001"]["status"] == "ACTIVE"
    assert any("incomplete batch" in w for w in p["integrity_warnings"])
    m.record_decision("New", "new", "2026-10-22", "AGENT-RECORD", "s", supersedes="LDEC-001")  # retry works
    p = m.projection()
    assert p["decisions"]["LDEC-001"]["status"] == "SUPERSEDED" and p["decisions"]["LDEC-002"]["decision"] == "new"


# ------------------------------------------------------------------ R2 regression tests (review R2 on 4a54ebe1)

def test_r2_01_resolve_binds_to_its_own_record_across_hosts(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    for m in (m1, m2):
        m.create_milestone("MM-X", "X")
        m.create_milestone("MM-Y", "Y")
    m1.request_approval("MM-Y", "SCOPE", "Y scope?")
    m1.add_blocker("MM-Y", "TECHNICAL", "y broken", "fix")
    m2.request_approval("MM-X", "SCOPE", "X scope?")
    m2.resolve_approval("AP-1", "APPROVED", owner_words="yes, X", source="chat")
    m2.add_blocker("MM-X", "TECHNICAL", "x broken", "fix")
    m2.resolve_blocker("BLK-1", "fixed x")
    _merge(m1, home2)
    p = m1.projection()
    ap = {a["subject"]: a["status"] for a in p["approvals"].values()}
    bl = {b["subject"]: b["status"] for b in p["blockers"].values()}
    assert ap == {"MM-Y": "REQUESTED", "MM-X": "APPROVED"}
    assert bl == {"MM-Y": "OPEN", "MM-X": "RESOLVED"}
    assert views.open_conflicts(p, "MM-Y") and views.open_conflicts(p, "MM-X")  # both subjects flagged


def test_r2_02_anchor_refresh_failure_is_a_warning_not_a_failed_write(tmp_path, monkeypatch):
    m = new(tmp_path)
    def boom(segs):
        raise PermissionError("anchors open by a reader")
    monkeypatch.setattr(m.store, "write_anchors", boom)
    written = m.create_milestone("MM-A", "A")
    assert written and m.last_warnings and "succeeded" in m.last_warnings[0]
    monkeypatch.undo()
    assert "MM-A" in m.projection()["milestones"]


@pytest.mark.windows_only
def test_r2_02_atomic_replace_retries_while_a_reader_holds_the_file(tmp_path):
    import threading
    from scripts.dev_workflow.milestones.store import atomic_write_bytes
    target = tmp_path / "a.json"
    target.write_bytes(b"old")
    f = target.open("rb")
    threading.Timer(0.3, f.close).start()
    atomic_write_bytes(target, b"new")
    assert target.read_bytes() == b"new"


def test_r2_03_missing_or_corrupt_anchors_are_integrity_errors(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.create_milestone("MM-B", "B")
    m.store.anchors_path.unlink()
    rep = m.store.verify()
    assert not rep["ok"] and any("anchors" in x for x in rep["errors"])
    with pytest.raises(StoreError):
        m.create_milestone("MM-C", "C")
    m.store.anchors_path.write_text("{corrupt", encoding="utf-8")
    assert not m.store.verify()["ok"]
    with pytest.raises(StoreError) as e:  # an unknown history cannot be re-based silently (R3-01)
        m.store.reanchor("impl:a", "anchors file lost")
    assert e.value.code == "LOSS_NOT_ACKNOWLEDGED"
    m.store.reanchor("impl:a", "anchors file lost; checked segment against git history", acknowledge_loss=True)
    assert m.store.verify()["ok"]
    m.create_milestone("MM-C", "C")
    kinds = [e["kind"] for s in m.store.read_all() for e in s.events]
    assert "ANCHORS_RESET" in kinds


def test_r2_04_clone_needs_its_own_host_id_and_local_files_are_untracked(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    assert "local/" in (m.home / ".gitignore").read_text(encoding="utf-8")
    clone = tmp_path / "clone"
    (clone / "events").mkdir(parents=True)
    (clone / "mm.json").write_bytes((m.home / "mm.json").read_bytes())
    (clone / "events" / "h1.jsonl").write_bytes(m.store.segment_path.read_bytes())
    with pytest.raises(StoreError) as e:
        Manager(clone, actor="b")
    assert e.value.code == "NO_HOST_ID"
    with pytest.raises(StoreError) as e:
        EventStore.init_host(clone, "h1")
    assert e.value.code == "HOST_ID_TAKEN"
    EventStore.init_host(clone, "h2")
    m2 = Manager(clone, actor="b")
    assert m2.store.verify()["ok"]
    m2.create_milestone("MM-B", "B")
    assert (clone / "events" / "h2.jsonl").is_file()
    assert not (clone / "anchors.json").exists() and (clone / "local" / "anchors.json").is_file()


def test_r2_05_resolve_only_the_conflicts_the_resolver_saw(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    home3 = tmp_path / "ledger3"
    EventStore.init(home3, "h3")
    m3 = Manager(home3, actor="h3:agent")
    m1.create_milestone("MM-A", "A")
    seg1 = m1.store.segment_path.read_bytes()
    for home in (home2, home3):
        (home / "events" / "h1.jsonl").write_bytes(seg1)
    m3.update_milestone("MM-A", next_action="h3: do NOT ship")      # earlier timestamp, merged later
    m1.update_milestone("MM-A", next_action="h1")
    m2.update_milestone("MM-A", next_action="h2")
    _merge(m1, home2)
    _resolve(m1, "MM-A", "saw h2 only")
    (m1.home / "events" / "h3.jsonl").write_bytes((home3 / "events" / "h3.jsonl").read_bytes())
    p = m1.projection()
    assert [c for c in views.open_conflicts(p, "MM-A")]  # h3's conflict stays open


def test_r2_06_clock_step_back_keeps_segment_order(tmp_path):
    clock = Clock()
    m = new(tmp_path, clock=clock)
    m.create_milestone("MM-A", "A")
    with m.store.locked():  # simulate a later write stamped earlier by a stepped-back clock
        ev = m.store.append("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": "later"}}, actor="x",
                            base={"MM-A": 1}, ts="2000-01-01T00:00:00.000000Z")
    assert ev["ts"] >= m.store.read_all()[0].events[0]["ts"]  # clamped, never earlier than the previous event
    assert m.projection()["milestones"]["MM-A"]["objective"] == "later"
    # a foreign segment whose timestamps go backwards is still folded in its own order
    from scripts.dev_workflow.milestones.store import read_segment
    s = read_segment(m.store.segment_path)
    evs = [dict(e) for e in s.events]
    evs[1]["ts"] = "1999-01-01T00:00:00.000000Z"
    class S:
        valid_events = evs
    order = [e["seq"] for e in model.ordered([S()])]
    assert order == [1, 2]


def test_r2_07_import_never_revises_an_unrelated_ledger_decision(tmp_path):
    src = tmp_path / "decisions.md"
    src.write_bytes(DECISIONS_MD.encode())
    m = new(tmp_path)
    importers.import_decisions(m, src)
    m.store.config["dec_namespace"] = "DEC"  # simulate a promoted ledger that numbers DEC- itself
    m.record_decision("Ledger-native", "native", "2026-10-22", "AGENT-RECORD", "s", ident="DEC-004")
    src.write_bytes((DECISIONS_MD.split("\n## 3.")[0] + "| DEC-004 | 2026-10-23 | P0 later | other | — | — | — | "
                     "s | — | — | ACTIVE | CAN | REPO-RECORD |\n").encode())
    r = importers.import_decisions(m, src)
    assert r["collisions"] == ["DEC-004"] and r["revised"] == 0
    d = m.projection()["decisions"]["DEC-004"]
    assert d["decision"] == "native" and not d["source_revisions"]


def test_r2_08_integration_approval_bound_to_candidate(tmp_path):
    m = _accept_ready(tmp_path)
    m.set_status("MM-A", "ACCEPTED", "ok")
    m.request_approval("MM-A", "INTEGRATION", "integrate C1?")
    m.resolve_approval("AP-1", "APPROVED", owner_words="yes integrate C1", source="chat")
    assert m.projection()["approvals"]["AP-1"]["commit"] == C1
    m.set_status("MM-A", "IN_PROGRESS", "new candidate")
    m.update_milestone("MM-A", candidate_commit=C2)
    m.record_review("MM-A", C2, "subagent", "subagent:r9", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m.set_status("MM-A", "ACCEPTED", "ok")
    m.record_integration("MM-A", "canonical", C2)
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "INTEGRATED", "try with the old approval")
    assert e.value.code == "NO_OWNER_INTEGRATION_APPROVAL"


def test_r2_09_unclear_or_partial_rows_never_record_full_supersession(tmp_path):
    src = tmp_path / "decisions.md"
    row = "| DEC-004 | 2026-09-12 | Q | quota | — | — | Its premise is superseded by DEC-003 | s | — | — | " \
          "UNCLEAR (partly superseded) | CAN | REPO-RECORD |\n"
    src.write_bytes((DECISIONS_MD.split("\n## 3.")[0] + row).encode())
    m = new(tmp_path)
    importers.import_decisions(m, src)
    d = m.projection()["decisions"]["DEC-004"]
    assert d["status"] == "UNCLEAR" and all(s["partial"] for s in d["superseded_by"])
    real = Path("D:/uri-dev/uri-p0-audit/decisions.md")
    if real.is_file():
        m2 = Manager(m.home, actor="x")
        h = tmp_path / "real"
        EventStore.init(h, "r")
        mr = Manager(h, actor="x")
        importers.import_decisions(mr, real)
        d30 = mr.projection()["decisions"]["DEC-030"]
        assert d30["superseded_by"] and all(s["partial"] for s in d30["superseded_by"])


def test_r2_12_log_reports_integrity(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.create_milestone("MM-B", "Bee")
    path = m.store.segment_path
    path.write_bytes(path.read_bytes().replace(b'"Bee"', b'"Bxx"'))
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "log"], out=out) == 3
    assert "integrity_errors" in out.getvalue()


@pytest.mark.parametrize("text", ["token: 65536 context", "token=4096 budget", "access_token: expired",
                                  "secret: rotated"])
def test_r2_13_numbers_and_state_words_are_not_secrets(text):
    assert model.find_secret(text) is None


def test_r2_14_recover_acknowledges_incomplete_batches(tmp_path):
    m = new(tmp_path)
    m.record_decision("Old", "old", "2026-10-21", "AGENT-RECORD", "s")
    with m.store.locked():
        evs = m.store.append_many([("BLOCKER_ADDED", {"id": "BLK-1", "subject": "PROJECT", "kind": "OTHER",
                                                      "reason": "r", "needs": "n"}, {}),
                                   ("BLOCKER_ADDED", {"id": "BLK-2", "subject": "PROJECT", "kind": "OTHER",
                                                      "reason": "r", "needs": "n"}, {})], actor="x")
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(b"\n".join(lines[:-1]) + b"\n" + lines[-1][:10])
    m.store.recover("impl:a")
    assert any("incomplete batch" in w for w in m.projection()["integrity_warnings"])
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=out) == 0
    assert json.loads(out.getvalue())["abandoned_batches"]
    p = m.projection()
    assert not p["integrity_warnings"] and not p["blockers"]


# ------------------------------------------------------------------ R3 regression tests (review R3 on 5bce5bdf)

def test_r3_01_reanchor_cannot_hide_a_detected_loss(tmp_path):
    m = _accept_ready(tmp_path, verdict="REJECT", blocking=1)
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(b"\n".join(lines[:-1]) + b"\n")  # delete the REJECT review
    assert not m.store.verify()["ok"]
    with pytest.raises(StoreError) as e:
        m.store.reanchor("impl:a", "routine")
    assert e.value.code == "LOSS_NOT_ACKNOWLEDGED"
    info = m.store.reanchor("impl:a", "deleted review confirmed in git", acknowledge_loss=True)
    assert info["lost"] == {"h1": {"anchored": len(lines), "now": len(lines) - 1}}
    m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "CONFLICT_OPEN"
    p = m.projection()
    ind = views.indicator(p, p["milestones"]["MM-A"])
    assert ind["color"] == "RED" and "integrity loss" in ind["issue"]


def test_r3_01_emptied_anchors_with_own_events_is_an_error(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.create_milestone("MM-B", "B")
    m.store.anchors_path.write_text("{}", encoding="utf-8")
    rep = m.store.verify()
    assert not rep["ok"] and any("no anchor entry" in x for x in rep["errors"])


def test_r3_02_supersede_links_bind_to_the_right_duplicate(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.record_decision("Base", "base", "2026-10-21", "AGENT-RECORD", "s")          # LDEC-001 on h1
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    m1.record_decision("A-side", "a", "2026-10-21", "AGENT-RECORD", "s")           # LDEC-002 on h1
    m2.record_decision("B-side", "b", "2026-10-21", "AGENT-RECORD", "s", supersedes="LDEC-001")  # LDEC-002 on h2
    _merge(m1, home2)
    d = m1.projection()["decisions"]
    b_key = next(k for k, v in d.items() if v["decision"] == "b")
    a_key = next(k for k, v in d.items() if v["decision"] == "a")
    assert [s["by"] for s in d["LDEC-001"]["superseded_by"]] == [b_key]
    assert d[b_key]["supersedes"] == [{"id": "LDEC-001", "partial": False}]
    assert d[a_key]["supersedes"] == []


def test_r3_03_reimport_through_another_path_is_unchanged(tmp_path, monkeypatch):
    src = tmp_path / "decisions.md"
    src.write_bytes(DECISIONS_MD.encode())
    other = tmp_path / "clone" / "decisions.md"
    other.parent.mkdir()
    other.write_bytes(DECISIONS_MD.encode())
    m = new(tmp_path)
    assert importers.import_decisions(m, src)["recorded"] == 3
    monkeypatch.chdir(tmp_path)
    r = importers.import_decisions(m, Path("decisions.md"))
    assert r["collisions"] == [] and r["unchanged"] == 3
    r = importers.import_decisions(m, other)
    assert r["collisions"] == [] and r["unchanged"] == 3


def test_r3_04_a_clock_behind_still_orders_after_what_it_saw(tmp_path, monkeypatch):
    import datetime as dt
    from scripts.dev_workflow.milestones import store as store_mod, service as service_mod
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-A", "A")
    m1.request_approval("MM-A", "SCOPE", "ok?")
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    behind = lambda: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    monkeypatch.setattr(store_mod, "utc_now", behind)
    monkeypatch.setattr(service_mod, "store_now", behind)
    m2.resolve_approval("AP-1", "APPROVED", owner_words="yes", source="chat")
    assert any("behind" in w for w in m2.last_warnings)
    monkeypatch.undo()
    _merge(m1, home2)
    for m in (m1, m2):
        p = m.projection()
        assert p["approvals"]["AP-1"]["status"] == "APPROVED" and not views.open_conflicts(p)


def test_r3_05_transient_sharing_violation_is_not_missing_anchors(tmp_path, monkeypatch):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    real = Path.read_text
    calls = {"n": 0}
    def flaky(self, *a, **k):
        if self.name == "anchors.json" and calls["n"] < 3:
            calls["n"] += 1
            raise PermissionError("sharing violation")
        return real(self, *a, **k)
    monkeypatch.setattr(Path, "read_text", flaky)
    assert m.store.read_anchors() and calls["n"] == 3
    calls["n"] = 0
    assert not m.projection()["integrity_errors"]


def test_r3_06_abandonment_applies_whatever_the_order():
    ab = {"v": 1, "seg": "h1", "seq": 1, "ts": "2026-10-21T10:00:00.000000Z", "actor": "a", "session": None,
          "kind": "BATCH_ABANDONED", "data": {"batches": ["b1"], "reason": "crash"}, "base": {}, "prev": "0" * 64,
          "hash": "x1"}
    half = {"v": 1, "seg": "h2", "seq": 1, "ts": "2026-10-21T11:00:00.000000Z", "actor": "a", "session": None,
            "kind": "BLOCKER_ADDED", "data": {"id": "BLK-1", "subject": "PROJECT", "kind": "OTHER", "reason": "r",
                                              "needs": "n"},
            "base": {}, "prev": "0" * 64, "hash": "x2", "batch": {"id": "b1", "n": 2, "i": 0}}
    p = model.fold([ab, half])
    assert not p["blockers"] and "b1" in p["abandoned_ids"]  # stays unapplied; never silently applied or lost


def test_r3_07_long_numeric_credentials_refused():
    assert model.find_secret("api_key: 123456789012345678901234567890")
    assert model.find_secret("password: 12345678")
    assert model.find_secret("token: 123456789012")
    assert model.find_secret("token: 65536 context") is None


# ------------------------------------------------------------------ R4 regression tests (review R4 on c992b5ae)

def _truncate_last(m):
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(b"\n".join(lines[:-1]) + b"\n")


@pytest.mark.parametrize("edit", ["remove_own", "empty", "zero_own"])
def test_r4_01_reanchor_needs_acknowledgement_when_anchors_cannot_vouch(tmp_path, edit):
    m = _accept_ready(tmp_path, verdict="REJECT", blocking=1)
    anchors = json.loads(m.store.anchors_path.read_text(encoding="utf-8"))
    if edit == "remove_own":
        anchors.pop("h1")
    elif edit == "empty":
        anchors = {}
    else:
        anchors["h1"] = {"count": 0, "head": "0" * 64}
    m.store.anchors_path.write_text(json.dumps(anchors), encoding="utf-8")
    _truncate_last(m)  # the REJECT review disappears
    p = m.projection()
    assert p["integrity_errors"] or p["integrity_warnings"]  # never silently clean
    with pytest.raises(StoreError) as e:
        m.store.reanchor("impl:a", "routine")
    assert e.value.code == "LOSS_NOT_ACKNOWLEDGED"
    m.store.reanchor("impl:a", "checked git", acknowledge_loss=True)
    m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "CONFLICT_OPEN"


def test_r4_02_lagging_host_that_sorts_first_still_orders_after(tmp_path, monkeypatch):
    import datetime as dt
    from scripts.dev_workflow.milestones import store as store_mod, service as service_mod
    mb = new(tmp_path, actor="b:agent", host="b")
    home_a = tmp_path / "ledger_a"
    EventStore.init(home_a, "a")
    ma = Manager(home_a, actor="a:agent")
    mb.create_milestone("MM-A", "A")
    mb.request_approval("MM-A", "SCOPE", "ok?")
    (home_a / "events" / "b.jsonl").write_bytes(mb.store.segment_path.read_bytes())
    behind = lambda: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    monkeypatch.setattr(store_mod, "utc_now", behind)
    monkeypatch.setattr(service_mod, "store_now", behind)
    ma.resolve_approval("AP-1", "APPROVED", owner_words="yes", source="chat")
    assert any("segment b" in w for w in ma.last_warnings)
    monkeypatch.undo()
    (mb.home / "events" / "a.jsonl").write_bytes((home_a / "events" / "a.jsonl").read_bytes())
    for m in (ma, mb):
        p = m.projection()
        assert p["approvals"]["AP-1"]["status"] == "APPROVED" and not views.open_conflicts(p)


def test_r4_02_future_stamped_segment_is_named_in_warnings(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m2.create_milestone("MM-F", "F")
    with m2.store.locked():
        m2.store.append("MILESTONE_UPDATED", {"id": "MM-F", "fields": {"objective": "x"}}, actor="h2",
                        base={"MM-F": 1}, ts="2099-01-01T00:00:00.000000Z")
    _merge(m1, home2)
    assert any("segment h2" in w and "ahead" in w for w in m1.projection()["integrity_warnings"])


def test_r4_03_recover_never_abandons_another_hosts_batch(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m2.record_decision("Base", "base", "2026-10-21", "AGENT-RECORD", "s")
    m2.record_decision("New", "new", "2026-10-21", "AGENT-RECORD", "s", supersedes="LDEC-001")  # 2-event batch
    seg2 = (home2 / "events" / "h2.jsonl").read_bytes()
    partial = b"\n".join(seg2.split(b"\n")[:-2]) + b"\n"  # incomplete sync: last line missing
    (m1.home / "events" / "h2.jsonl").write_bytes(partial)
    m1.create_milestone("MM-A", "A")
    out = io.StringIO()
    assert cli.run(["--home", str(m1.home), "--actor", "h1:agent", "recover"], out=out) == 0
    assert json.loads(out.getvalue())["abandoned_batches"] == []
    _merge(m1, home2)  # full sync
    d = m1.projection()["decisions"]
    assert d["LDEC-001"]["status"] == "SUPERSEDED" and d["LDEC-002"]["decision"] == "new"


def test_r4_03_an_abandoned_batch_that_completes_is_applied_and_flagged():
    mk = lambda seq, i, ts: {"v": 1, "seg": "h2", "seq": seq, "ts": ts, "actor": "a", "session": None,
                             "kind": "BLOCKER_ADDED", "data": {"id": f"BLK-{seq}", "subject": "PROJECT",
                                                              "kind": "OTHER", "reason": "r", "needs": "n"},
                             "base": {}, "prev": "0" * 64, "hash": f"h{seq}", "batch": {"id": "b1", "n": 2, "i": i}}
    ab = {"v": 1, "seg": "h1", "seq": 1, "ts": "2026-10-21T10:00:00.000000Z", "actor": "a", "session": None,
          "kind": "BATCH_ABANDONED", "data": {"batches": ["b1"], "reason": "crash"}, "base": {}, "prev": "0" * 64,
          "hash": "x1"}
    p = model.fold([ab, mk(1, 0, "2026-10-21T11:00:00.000000Z"), mk(2, 1, "2026-10-21T11:00:00.000000Z")])
    assert len(p["blockers"]) == 2
    assert any(c["type"] == "ABANDONED_BATCH_COMPLETED" for c in p["conflicts"])


def test_r4_04_register_identity_is_the_document_not_the_file_name(tmp_path):
    src = tmp_path / "decisions.md"
    src.write_bytes(DECISIONS_MD.encode())
    m = new(tmp_path)
    importers.import_decisions(m, src)
    other = tmp_path / "other" / "decisions.md"
    other.parent.mkdir()
    other.write_bytes(DECISIONS_MD.replace("# decisions", "# Another project's decisions")
                      .replace("the loop", "unrelated").encode())
    r = importers.import_decisions(m, other)
    assert r["collisions"] == ["DEC-001", "DEC-002", "DEC-003"] and r["revised"] == 0
    renamed = tmp_path / "decisions_2026-10-21.md"
    renamed.write_bytes(DECISIONS_MD.encode())
    r = importers.import_decisions(m, renamed)
    assert r["collisions"] == [] and r["unchanged"] == 3


def test_r4_05_first_write_without_anchor_refresh_does_not_block_the_next(tmp_path, monkeypatch):
    m = new(tmp_path)
    real = m.store.write_anchors
    def boom(segs):
        raise PermissionError("busy")
    monkeypatch.setattr(m.store, "write_anchors", boom)
    m.create_milestone("MM-A", "A")
    p = m.projection()
    assert not p["integrity_errors"] and any("not anchored yet" in w for w in p["integrity_warnings"])
    monkeypatch.setattr(m.store, "write_anchors", real)
    _loss_first(lambda: m.create_milestone("MM-B", "B"))
    p = m.projection()
    assert not p["integrity_errors"] and not p["integrity_warnings"] and "MM-B" in p["milestones"]
    # adopting the unanchored own segment is recorded and must be reviewed (R5-04)
    assert any(c["type"] == "ANCHOR_LOSS" and c["kind"] == "ANCHORS_ADOPTED" for c in views.open_conflicts(p))


def test_r4_06_status_scales_with_many_conflicts():
    p = model.empty_projection()
    for i in range(500):
        p["milestones"][f"MM-{i}"] = {"id": f"MM-{i}", "title": "t", "priority": "P1", "phase": "RESEARCH",
                                      "status": "IN_PROGRESS", "depends_on": [], "lifecycle": [], "assignment": None,
                                      "implementers": [], "status_history": []}
    ref = {"seg": "h", "seq": 1, "hash": "x", "ts": "t", "actor": "a"}
    for i in range(5000):
        p["conflicts"].append({"type": "VERSION", "entity": f"MM-{i % 500}", "subject": f"MM-{i % 500}",
                               "event": ref, "kind": "K", "resolved": False})
    t0 = time.perf_counter()
    views.status_json(p)
    views.status_lines(p)
    assert time.perf_counter() - t0 < 1.0


# ------------------------------------------------------------------ R5 regression tests (review R5 on 7c8e0a29)

def test_r5_01_recover_cannot_rebase_unvouched_anchors(tmp_path):
    m = _accept_ready(tmp_path, verdict="REJECT", blocking=1)
    m.store.anchors_path.unlink()
    _truncate_last(m)
    with m.store.segment_path.open("ab") as f:
        f.write(b'{"v')
    with pytest.raises(StoreError) as e:
        m.store.recover("impl:a")
    assert e.value.code == "LOSS_NOT_ACKNOWLEDGED"
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=out) == 2
    m.store.recover("impl:a", acknowledge_loss=True)
    m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "CONFLICT_OPEN"


REGISTER_OTHER = REGISTER_MD.replace("# register", "# Some other project's register").replace("Thing", "Unrelated")


def test_r5_02_register_rows_of_another_register_collide(tmp_path):
    src = tmp_path / "developmental.md"
    src.write_bytes(REGISTER_MD.encode())
    m = new(tmp_path)
    importers.import_register(m, src)
    other = tmp_path / "other.md"
    other.write_bytes(REGISTER_OTHER.encode())
    r = importers.import_register(m, other)
    assert "REG-B-CAP-1" in r["collisions"] and r["revised"] == 0
    assert m.projection()["records"]["REG-B-CAP-1"]["fields"]["capability"] == "Thing"
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "a", "import-register", str(other)], out=out) == 1


def test_r5_03_record_revision_keeps_the_original(tmp_path):
    src = tmp_path / "developmental.md"
    src.write_bytes(REGISTER_MD.encode())
    m = new(tmp_path)
    importers.import_register(m, src)
    src.write_bytes(REGISTER_MD.replace("Thing", "Thing v2").encode())
    importers.import_register(m, src)
    r = m.projection()["records"]["REG-B-CAP-1"]
    assert r["original"]["fields"]["capability"] == "Thing"
    assert r["revisions"][0]["previous"]["fields"]["capability"] == "Thing"
    assert r["fields"]["capability"] == "Thing v2"


def test_r5_04_write_over_unanchored_truncation_is_recorded_and_blocks(tmp_path):
    m = _accept_ready(tmp_path, verdict="REJECT", blocking=1)
    _truncate_last(m)
    anchors = json.loads(m.store.anchors_path.read_text(encoding="utf-8"))
    anchors["h1"] = {"count": 0, "head": "0" * 64}
    m.store.anchors_path.write_text(json.dumps(anchors), encoding="utf-8")
    _loss_first(lambda: m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "ACCEPT", 0, 0,
                                        "COMPLETED_WITH_RESULT", "ok"))
    with pytest.raises(ValidationError) as e:
        m.set_status("MM-A", "ACCEPTED", "try")
    assert e.value.code == "CONFLICT_OPEN"
    kinds = [e["kind"] for s in m.store.read_all() for e in s.events]
    assert "ANCHORS_ADOPTED" in kinds


def test_r5_05_reanchor_and_recover_are_lamport_floored(tmp_path, monkeypatch):
    import datetime as dt
    from scripts.dev_workflow.milestones import store as store_mod
    m1, m2, home2 = _two_hosts(tmp_path)
    m2.create_milestone("MM-B", "B")
    _merge(m1, home2)
    m1.create_milestone("MM-A", "A")
    newest = max(e["ts"] for s in m1.store.read_all() for e in s.events)
    behind = lambda: (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    monkeypatch.setattr(store_mod, "utc_now", behind)
    m1.store.reanchor("impl:a", "test")
    with m1.store.segment_path.open("ab") as f:
        f.write(b'{"v')
    m1.store.recover("impl:a")
    evs = [e for e in m1.store.read_all() if e.name == "h1"][0].events
    assert all(e["ts"] > newest for e in evs if e["kind"] in ("ANCHORS_RESET", "STORE_RECOVERED"))


def test_r5_06_future_warning_names_the_earliest_future_segment(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m2.create_milestone("MM-F", "F")
    with m2.store.locked():
        m2.store.append("MILESTONE_UPDATED", {"id": "MM-F", "fields": {"objective": "x"}}, actor="h2",
                        base={"MM-F": 1}, ts="2099-01-01T00:00:00.000000Z")
    _merge(m1, home2)
    m1.create_milestone("MM-A", "A")  # pinned after h2's future event
    w = [x for x in m1.projection()["integrity_warnings"] if "ahead" in x]
    assert len(w) == 1 and "segment h2" in w[0] and "segment h1" not in w[0]


def test_r5_07_conflict_index_tracks_in_place_resolution(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-A", "A")
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    m1.update_milestone("MM-A", objective="1")
    m2.update_milestone("MM-A", objective="2")
    _merge(m1, home2)
    p = m1.projection()
    c = views.open_conflicts(p, "MM-A")
    assert c
    model.apply(p, {"v": 1, "seg": "h1", "seq": 99, "ts": "2099-01-01T00:00:00.000000Z", "actor": "x",
                    "session": None, "kind": "CONFLICT_RESOLVED",
                    "data": {"entity": "MM-A", "note": "n", "conflicts": [x["event"]["hash"] for x in c]},
                    "base": {}, "prev": "0" * 64, "hash": "zz"})
    assert views.open_conflicts(p, "MM-A") == []


def test_r5_08_malformed_anchor_entry_is_an_integrity_error(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_text(json.dumps({"h1": {"count": "1", "head": "0" * 64}}), encoding="utf-8")
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "status", "--no-tasks"], out=out) == 3
    assert cli.run(["--home", str(m.home), "verify"], out=io.StringIO()) == 3


def test_r5_09_bom_prefixed_register_imports(tmp_path):
    src = tmp_path / "decisions.md"
    src.write_bytes(b"\xef\xbb\xbf" + DECISIONS_MD.encode())
    m = new(tmp_path)
    assert importers.import_decisions(m, src)["recorded"] == 3
    plain = tmp_path / "plain.md"
    plain.write_bytes(DECISIONS_MD.encode())
    r = importers.import_decisions(m, plain)
    assert r["collisions"] == [] and r["unchanged"] == 3


# ------------------------------------------------------------------ R6 regression tests (review R6 on 3ba9af68)

def _first_batch_power_loss(tmp_path, torn_len):
    src = tmp_path / "developmental.md"
    src.write_bytes(REGISTER_MD.encode())
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()  # as `init` left them: own count 0
    importers.import_register(m, src)  # first command: one multi-event batch
    m.store.anchors_path.write_bytes(init_anchors)  # power lost before the anchor refresh
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(lines[0] + b"\n" + lines[1][:torn_len])  # 1 complete line + part of the 2nd
    return m, src


@pytest.mark.parametrize("torn_len", [20, 60, 65, 120, 400])
def test_r6_01_power_loss_in_a_hosts_first_multi_event_command_recovers(tmp_path, torn_len):
    """Never refused (R6-01), never silent (R7-01, R8-01/02): one ANCHOR_LOSS to review, any cut position."""
    m, src = _first_batch_power_loss(tmp_path, torn_len)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=out) == 0, out.getvalue()
    res = json.loads(out.getvalue())
    assert res["recovered"] and res["abandoned_batches"]
    p = m.projection()
    assert not p["integrity_errors"] and not p["records"]
    assert [c["type"] for c in views.open_conflicts(p)] == ["ANCHOR_LOSS"]
    _resolve(m, "LEDGER", "power loss during the first import; quarantined bytes checked")
    importers.import_register(m, src)  # the retry works
    p = m.projection()
    assert len(p["records"]) == 4 and not views.open_conflicts(p)


def test_r7_01_short_torn_tail_is_recovered_but_recorded_for_review(tmp_path):
    m, _ = _first_batch_power_loss(tmp_path, 20)  # too short to prove anything
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=out) == 0, out.getvalue()
    p = m.projection()
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))


def test_r7_01_truncated_applied_batch_is_never_hidden(tmp_path):
    src = tmp_path / "developmental.md"
    src.write_bytes(REGISTER_MD.encode())
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    importers.import_register(m, src)  # complete and applied
    m.store.anchors_path.write_bytes(init_anchors)  # its anchor refresh had failed
    assert m.projection()["records"]
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(lines[0] + b"\n" + b'{"x')  # later: complete lines cut, junk appended
    m.store.recover("impl:a")
    p = m.projection()
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))  # visible, needs review


def test_r8_02_truncation_of_an_applied_batch_past_the_batch_id_is_never_hidden(tmp_path):
    src = tmp_path / "developmental.md"
    src.write_bytes(REGISTER_MD.encode())
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    importers.import_register(m, src)  # complete and applied
    m.store.anchors_path.write_bytes(init_anchors)  # its anchor refresh had failed
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(lines[0] + b"\n" + lines[1][:200])  # genuine bytes, cut deep inside line 2
    m.store.recover("impl:a")
    p = m.projection()
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))


def test_r6_02_init_host_refuses_uncommitted_segment_changes_and_records_itself(tmp_path):
    home = tmp_path / "ledger"
    home.mkdir()
    subprocess.run(["git", "-C", str(home), "init", "-q"], check=True)
    subprocess.run(["git", "-C", str(home), "config", "user.email", "t@t"], check=True)
    subprocess.run(["git", "-C", str(home), "config", "user.name", "t"], check=True)
    EventStore.init(home, "h1", autocommit=True)
    m = Manager(home, actor="a")
    m.create_milestone("MM-A", "A")
    m.create_milestone("MM-B", "B")
    _truncate_last(m)
    import shutil
    shutil.rmtree(home / "local")  # e.g. `git clean -xdf`
    with pytest.raises(StoreError) as e:
        EventStore.init_host(home, "h2")
    assert e.value.code == "UNCOMMITTED_SEGMENTS"
    assert not (home / "local" / "host.json").exists()
    clone = tmp_path / "clone"
    (clone / "events").mkdir(parents=True)
    (clone / "mm.json").write_bytes((home / "mm.json").read_bytes())
    subprocess.run(["git", "-C", str(home), "checkout", "--", "events"], check=True)
    (clone / "events" / "h1.jsonl").write_bytes((home / "events" / "h1.jsonl").read_bytes())
    st = EventStore.init_host(clone, "h3")
    kinds = [e["kind"] for s in st.read_all() for e in s.events]
    assert "HOST_REGISTERED" in kinds and st.verify()["ok"]


def test_r6_03_acknowledged_recover_rebases_and_keeps_the_loss_visible(tmp_path):
    m = new(tmp_path)
    for i in range(4):
        m.create_milestone(f"MM-{i}", "x")
    path = m.store.segment_path
    lines = path.read_bytes().split(b"\n")[:-1]
    path.write_bytes(b"\n".join(lines[:-2]) + b"\n" + b'{"v')  # 2 events lost + torn tail
    with pytest.raises(StoreError):
        m.store.recover("impl:a")
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "recover", "--acknowledge-loss"], out=out) == 0
    assert "quarantine" in out.getvalue()
    p = m.projection()
    assert not p["integrity_errors"]
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))


def test_r6_04_adopting_write_reports_it(tmp_path, monkeypatch):
    m = new(tmp_path)
    monkeypatch.setattr(m.store, "write_anchors", lambda segs: (_ for _ in ()).throw(PermissionError("x")))
    m.create_milestone("MM-A", "A")
    monkeypatch.undo()
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-B", "B")
    assert e.value.code == "LEDGER_LOSS_RECORDED" and "ANCHORS_ADOPTED" in str(e.value)
    assert any("ANCHORS_ADOPTED" in w for w in m.last_warnings)
    out = io.StringIO()  # the CLI shows the warnings with the refusal
    m.store.anchors_path.write_text(json.dumps({"h1": {"count": 0, "head": "0" * 64}}), encoding="utf-8")
    assert cli.run(["--home", str(m.home), "--actor", "a", "milestone-add", "MM-C", "--title", "C"], out=out) == 1
    assert "warnings" in json.loads(out.getvalue())


# ------------------------------------------------------------------ R7 regression tests (review R7 on 5b2a1427)

def test_r7_02_count0_warning_text_is_clean(tmp_path):
    m = new(tmp_path)
    m.store.anchors_path.write_bytes(m.store.anchors_path.read_bytes())
    real = m.store.write_anchors
    m.store.write_anchors = lambda segs: (_ for _ in ()).throw(PermissionError("x"))
    m.create_milestone("MM-A", "A")
    m.store.write_anchors = real
    w = m.projection()["integrity_warnings"][0]
    assert w.count("anchors it") == 1


def test_r7_03_init_host_failure_leaves_no_half_registration(tmp_path, monkeypatch):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = tmp_path / "clone"
    (clone / "events").mkdir(parents=True)
    (clone / "mm.json").write_bytes((m.home / "mm.json").read_bytes())
    (clone / "events" / "h1.jsonl").write_bytes(m.store.segment_path.read_bytes())
    from scripts.dev_workflow.milestones import store as store_mod
    real = store_mod.EventStore.append_many
    def boom(self, *a, **k):
        raise StoreError("LOCK_TIMEOUT", "busy")
    monkeypatch.setattr(store_mod.EventStore, "append_many", boom)
    with pytest.raises(StoreError):
        EventStore.init_host(clone, "h2")
    assert not (clone / "local" / "host.json").exists()
    monkeypatch.setattr(store_mod.EventStore, "append_many", real)
    st = EventStore.init_host(clone, "h2")  # the retry works
    assert st.verify()["ok"]


# ------------------------------------------------------------------ R8 regression tests (review R8 on ddc4e63b)

def _clone_of(m, tmp_path, name="clone"):
    clone = tmp_path / name
    (clone / "events").mkdir(parents=True)
    (clone / "mm.json").write_bytes((m.home / "mm.json").read_bytes())
    for seg in (m.home / "events").glob("*.jsonl"):
        (clone / "events" / seg.name).write_bytes(seg.read_bytes())
    return clone


def test_r8_03_init_host_never_takes_over_a_registered_segment(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    c2 = _clone_of(m, tmp_path, "c2")
    EventStore.init_host(c2, "pc2")  # registered, nothing else written yet
    c3 = tmp_path / "c3"
    (c3 / "events").mkdir(parents=True)
    (c3 / "mm.json").write_bytes((c2 / "mm.json").read_bytes())
    for seg in (c2 / "events").glob("*.jsonl"):
        (c3 / "events" / seg.name).write_bytes(seg.read_bytes())
    with pytest.raises(StoreError) as e:
        EventStore.init_host(c3, "pc2")
    assert e.value.code == "HOST_ID_TAKEN"


def test_r8_04_failed_init_host_in_git_can_be_retried(tmp_path, monkeypatch):
    home = tmp_path / "ledger"
    home.mkdir()
    for args in (("init", "-q"), ("config", "user.email", "t@t"), ("config", "user.name", "t")):
        subprocess.run(["git", "-C", str(home), *args], check=True)
    EventStore.init(home, "h1", autocommit=True)
    Manager(home, actor="a").create_milestone("MM-A", "A")
    clone = tmp_path / "clone"
    subprocess.run(["git", "clone", "-q", str(home), str(clone)], check=True)
    from scripts.dev_workflow.milestones import store as store_mod
    real = store_mod.EventStore.write_anchors
    monkeypatch.setattr(store_mod.EventStore, "write_anchors",
                        lambda self, segs: (_ for _ in ()).throw(OSError("disk")))
    with pytest.raises(OSError):
        EventStore.init_host(clone, "pc4")
    monkeypatch.setattr(store_mod.EventStore, "write_anchors", real)
    assert not (clone / "events" / "pc4.jsonl").exists()
    st = EventStore.init_host(clone, "pc4")
    assert st.verify()["ok"]


def test_r8_05_failed_init_host_restores_existing_anchors(tmp_path, monkeypatch):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = _clone_of(m, tmp_path)
    (clone / "local").mkdir()
    old = b'{"h9": {"count": 0, "head": "' + b"0" * 64 + b'"}}'
    (clone / "local" / "anchors.json").write_bytes(old)
    from scripts.dev_workflow.milestones import store as store_mod
    monkeypatch.setattr(store_mod.EventStore, "append_many",
                        lambda self, *a, **k: (_ for _ in ()).throw(StoreError("LOCK_TIMEOUT", "busy")))
    with pytest.raises(StoreError):
        EventStore.init_host(clone, "h2")
    assert (clone / "local" / "anchors.json").read_bytes() == old
    assert not (clone / "local" / "host.json").exists()


# ------------------------------------------------------------------ R9 regression tests (review R9 on 2fe3615f)

@pytest.mark.parametrize("first", ["single", "batch"])
@pytest.mark.parametrize("cut", [1, 30, 120])
def test_r9_01_cut_inside_the_first_line_is_recorded(tmp_path, first, cut):
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    if first == "single":
        m.create_milestone("MM-A", "A")
    else:
        src = tmp_path / "developmental.md"
        src.write_bytes(REGISTER_MD.encode())
        importers.import_register(m, src)
    m.store.anchors_path.write_bytes(init_anchors)  # first anchor refresh failed (or power lost before it)
    path = m.store.segment_path
    path.write_bytes(path.read_bytes()[:cut])  # cut inside line 0: no complete event remains
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "recover"], out=io.StringIO()) == 0
    p = m.projection()
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))


HOLD_LOCK = r"""
import sys, time
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones.store import os_lock
from pathlib import Path
with os_lock(Path(sys.argv[2])):
    Path(sys.argv[3]).write_text("held")
    time.sleep(0.8)
    if len(sys.argv) > 4:  # another registration of the same id completes while the lock is held
        Path(sys.argv[4]).write_bytes(b"")
    time.sleep(1.2)
"""


def test_r9_02_init_host_checks_under_the_ledger_lock(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = _clone_of(m, tmp_path)
    flag = tmp_path / "held.flag"
    proc = subprocess.Popen([sys.executable, "-c", HOLD_LOCK, str(ROOT), str(clone / ".lock"), str(flag),
                             str(clone / "events" / "h2.jsonl")])
    try:
        for _ in range(200):
            if flag.exists():
                break
            time.sleep(0.02)
        assert flag.exists()
        with pytest.raises(StoreError) as e:  # sees the segment created while it waited: never races it
            EventStore.init_host(clone, "h2")
        assert e.value.code == "HOST_ID_TAKEN"
        assert (clone / "events" / "h2.jsonl").exists()  # the other registration's file is untouched
    finally:
        proc.wait(timeout=30)


KILL_IN_INIT_HOST = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import store
real = store.EventStore.write_anchors
calls = {"n": 0}
def dying(self, segs):
    calls["n"] += 1
    if calls["n"] == 1:   # after HOST_REGISTERED was appended, before the refresh
        os._exit(9)
    return real(self, segs)
store.EventStore.write_anchors = dying
store.EventStore.init_host(sys.argv[2], "h2")
"""


def test_r9_03_kill_during_init_host_leaves_the_documented_count0_state(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = _clone_of(m, tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL_IN_INIT_HOST, str(ROOT), str(clone)])
    assert r.returncode == 9
    m2 = Manager(clone, actor="b")
    p = m2.projection()
    assert not p["integrity_errors"] and any("not anchored yet" in w for w in p["integrity_warnings"])
    _loss_first(lambda: m2.create_milestone("MM-B", "B"))  # next write adopts and records it (architecture §7)
    p = m2.projection()
    assert not p["integrity_errors"]
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))


# ------------------------------------------------------------------ R10 regression tests (review R10 on 1838e2df)

KILL_BEFORE_HOST_FILE = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import store
def dying(home, host_id):
    os._exit(9)
store.EventStore._write_local = staticmethod(dying)
store.EventStore.init_host(sys.argv[2], "h2")
"""


def test_r10_01_kill_before_the_host_file_leaves_an_unregistered_home(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = _clone_of(m, tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL_BEFORE_HOST_FILE, str(ROOT), str(clone)])
    assert r.returncode == 9
    with pytest.raises(StoreError) as e:  # not an integrity failure: simply not registered yet
        Manager(clone, actor="b")
    assert e.value.code == "NO_HOST_ID"
    st = EventStore.init_host(clone, "h2")  # retry registers normally
    assert st.verify()["ok"] and not views.open_conflicts(Manager(clone, actor="b").projection())


def test_r10_01_anchors_exist_before_the_machine_is_registered(tmp_path, monkeypatch):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = _clone_of(m, tmp_path)
    from scripts.dev_workflow.milestones import store as store_mod
    real = store_mod.EventStore._write_local
    seen = {}
    def spy(home, host_id):
        seen["anchors"] = (Path(home) / "local" / "anchors.json").is_file()
        return real(home, host_id)
    monkeypatch.setattr(store_mod.EventStore, "_write_local", staticmethod(spy))
    EventStore.init_host(clone, "h2")
    assert seen["anchors"] is True


@pytest.mark.parametrize("damage", ["truncate", "corrupt"])
def test_r10_02_init_host_mismatch_has_a_working_acknowledged_path(tmp_path, damage):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    m.create_milestone("MM-B", "B")
    if damage == "truncate":
        _truncate_last(m)
    else:
        m.store.anchors_path.write_text("{corrupt", encoding="utf-8")
    (m.home / "local" / "host.json").unlink()  # local identity lost, earlier anchors kept
    with pytest.raises(StoreError) as e:
        EventStore.init_host(m.home, "h2")
    assert e.value.code == "ANCHOR_MISMATCH" and "init-host" in str(e.value)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "init-host", "--host-id", "h2", "--acknowledge-loss"], out=out) == 0
    p = Manager(m.home, actor="x").projection()
    assert not p["integrity_errors"]
    assert any(c["type"] == "ANCHOR_LOSS" and c["kind"] == "HOST_REGISTERED" for c in views.open_conflicts(p))


# ------------------------------------------------------------------ R11 regression tests (review R11 on 5bb005f6)

KILL_ACK_INIT_HOST = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import store
point = sys.argv[3]
if point == "K1":
    store.EventStore._write_local = staticmethod(lambda home, host_id: os._exit(9))
else:
    store.EventStore.append_many = lambda self, *a, **k: os._exit(9)
store.EventStore.init_host(sys.argv[2], "hc", acknowledge_loss=True)
"""


def _lost_host_identity(tmp_path):
    m = new(tmp_path)
    for i in range(3):
        m.create_milestone(f"MM-{i}", "x")
    _truncate_last(m)
    (m.home / "local" / "host.json").unlink()
    return m.home


@pytest.mark.parametrize("point", ["K1", "K2"])
def test_r11_01_interrupted_acknowledged_registration_keeps_the_loss(tmp_path, point):
    home = _lost_host_identity(tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL_ACK_INIT_HOST, str(ROOT), str(home), point])
    assert r.returncode == 9
    if point == "K1":  # not registered: a retry must still see and record the loss
        with pytest.raises(StoreError) as e:
            EventStore.init_host(home, "hc")
        assert e.value.code == "ANCHOR_MISMATCH"
        EventStore.init_host(home, "hc", acknowledge_loss=True)
    else:  # registered without its event: the next write records it
        m = Manager(home, actor="x")
        assert any("pending" in w for w in m.projection()["integrity_warnings"])
        _loss_first(lambda: m.create_milestone("MM-N", "n"))
    p = Manager(home, actor="x").projection()
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(p))
    assert not (home / "local" / "pending_loss.json").exists()


def test_r11_02_init_host_works_without_git(tmp_path, monkeypatch):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    clone = _clone_of(m, tmp_path)
    from scripts.dev_workflow.milestones import store as store_mod
    real = store_mod.subprocess.run
    def no_git(cmd, *a, **k):
        if cmd and cmd[0] == "git":
            raise FileNotFoundError("git not installed")
        return real(cmd, *a, **k)
    monkeypatch.setattr(store_mod.subprocess, "run", no_git)
    st = EventStore.init_host(clone, "h2")
    assert st.verify()["ok"]


def test_r11_03_writer_refuses_when_the_host_registration_changed(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    (m.home / "local" / "host.json").write_text('{"host_id": "other"}', encoding="utf-8")
    with pytest.raises(StoreError) as e:
        m.create_milestone("MM-B", "B")
    assert e.value.code == "NO_HOST_ID"


def test_r11_04_status_shows_the_recorded_problem(tmp_path):
    home = _lost_host_identity(tmp_path)
    EventStore.init_host(home, "hc", acknowledge_loss=True)
    p = Manager(home, actor="x").projection()
    p["milestones"]["MM-0"]["status"] = "IN_PROGRESS"
    issue = views.indicator(p, p["milestones"]["MM-0"])["issue"]
    assert "HOST_REGISTERED" in issue and "anchored" in issue


def test_r11_05_unreadable_host_file_can_be_replaced_by_init_host(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    (m.home / "local" / "host.json").write_text("", encoding="utf-8")
    with pytest.raises(StoreError) as e:
        Manager(m.home, actor="x")
    assert e.value.code == "NO_HOST_ID" and "unreadable" in str(e.value)
    st = EventStore.init_host(m.home, "h2")
    assert st.verify()["ok"]


# ------------------------------------------------------------------ R12 regression tests (review R12 on 61b01ac4)

KILL_INIT_HOST_AT = r"""
import os, sys
sys.path.insert(0, sys.argv[1])
from scripts.dev_workflow.milestones import store
point, ack = sys.argv[3], sys.argv[4] == "1"
if point == "K2":        # registered, before the HOST_REGISTERED append
    store.EventStore.append_many = lambda self, *a, **k: os._exit(9)
elif point == "K3m":     # after the append, before the pending-loss marker is removed
    store.unlink_retry = lambda path: os._exit(9)
else:                    # K3: after the append, before the anchor refresh
    store.EventStore.write_anchors = lambda self, segs: os._exit(9)
store.EventStore.init_host(sys.argv[2], "hc", acknowledge_loss=ack)
"""


def _accept_ready_then_lose_identity(tmp_path, with_loss=True):
    m = new(tmp_path, actor="impl:a")
    m.create_milestone("MM-A", "A")
    m.set_status("MM-A", "IN_PROGRESS", "go")
    m.update_milestone("MM-A", candidate_commit=C1)
    m.record_review("MM-A", C1, "subagent", "subagent:r1", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m.create_milestone("MM-X", "x")
    if with_loss:
        _truncate_last(m)
    (m.home / "local" / "host.json").unlink()
    return m.home


@pytest.mark.parametrize("point,with_loss", [("K2", True), ("K3", False)])
def test_r12_01_loss_recorded_by_a_write_blocks_that_same_positive_status(tmp_path, point, with_loss):
    home = _accept_ready_then_lose_identity(tmp_path, with_loss)
    r = subprocess.run([sys.executable, "-c", KILL_INIT_HOST_AT, str(ROOT), str(home), point,
                        "1" if with_loss else "0"])
    assert r.returncode == 9
    m = Manager(home, actor="impl:a")
    with pytest.raises(ValidationError) as e:  # the loss is recorded first; the command is not executed
        m.set_status("MM-A", "ACCEPTED", "try right after the interruption")
    assert e.value.code == "LEDGER_LOSS_RECORDED"
    assert m.projection()["milestones"]["MM-A"]["status"] == "IN_PROGRESS"
    with pytest.raises(ValidationError) as e:  # and it blocks the retry until reviewed
        m.set_status("MM-A", "ACCEPTED", "retry")
    assert e.value.code == "CONFLICT_OPEN"
    kinds = [e["kind"] for s in m.store.read_all() for e in s.events]
    assert ("LOSS_RECORDED" in kinds) if with_loss else ("ANCHORS_ADOPTED" in kinds)


def test_r12_02_marker_removal_failure_is_a_warning_and_never_records_twice(tmp_path, monkeypatch):
    home = _accept_ready_then_lose_identity(tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL_INIT_HOST_AT, str(ROOT), str(home), "K2", "1"])
    assert r.returncode == 9
    from scripts.dev_workflow.milestones import service as service_mod
    monkeypatch.setattr(service_mod, "unlink_retry", lambda path: (_ for _ in ()).throw(PermissionError("busy")))
    m = Manager(home, actor="x")
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-N", "n")
    assert e.value.code == "LEDGER_LOSS_RECORDED"
    assert any("marker not removed" in w for w in m.last_warnings)
    monkeypatch.undo()
    m.create_milestone("MM-M", "m")
    kinds = [e["kind"] for s in m.store.read_all() for e in s.events]
    assert kinds.count("LOSS_RECORDED") == 1


def test_r12_03_marker_left_after_a_recorded_registration_is_not_recorded_again(tmp_path):
    home = _accept_ready_then_lose_identity(tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL_INIT_HOST_AT, str(ROOT), str(home), "K3m", "1"])
    assert r.returncode == 9
    assert (home / "local" / "pending_loss.json").exists()
    m = Manager(home, actor="x")
    _loss_first(lambda: m.create_milestone("MM-N", "n"))  # (the unrefreshed own anchor is adopted first)
    kinds = [e["kind"] for s in m.store.read_all() for e in s.events]
    assert kinds.count("LOSS_RECORDED") == 0 and "HOST_REGISTERED" in kinds
    assert not (home / "local" / "pending_loss.json").exists()


# ------------------------------------------------------------------ R13 regression tests (review R13 on 3da86259)

def test_r13_01_resolve_conflict_cannot_close_a_loss_it_just_recorded(tmp_path):
    home = _accept_ready_then_lose_identity(tmp_path)
    r = subprocess.run([sys.executable, "-c", KILL_INIT_HOST_AT, str(ROOT), str(home), "K2", "1"])
    assert r.returncode == 9
    m = Manager(home, actor="x")
    assert not views.open_conflicts(m.projection())
    with pytest.raises(ValidationError) as e:
        m.resolve_conflict("LEDGER", "reviewed", ["deadbeef0000"])  # nothing was open when the user typed this
    assert e.value.code == "LEDGER_LOSS_RECORDED"
    assert any(c["type"] == "ANCHOR_LOSS" for c in views.open_conflicts(m.projection()))
    _resolve(m, "LEDGER", "now reviewed")  # an explicit second resolution, naming what was shown, closes it
    assert not views.open_conflicts(m.projection())


@pytest.mark.parametrize("case", ["pending", "adopt"])
def test_r13_02_recover_with_a_pending_loss_reports_cleanly(tmp_path, case):
    if case == "pending":
        home = _accept_ready_then_lose_identity(tmp_path)
        r = subprocess.run([sys.executable, "-c", KILL_INIT_HOST_AT, str(ROOT), str(home), "K2", "1"])
        assert r.returncode == 9
        m = Manager(home, actor="x")
    else:
        m = new(tmp_path)
        init_anchors = m.store.anchors_path.read_bytes()
        m.create_milestone("MM-A", "A")
        m.store.anchors_path.write_bytes(init_anchors)
        home = m.home
    out = io.StringIO()
    rc = cli.run(["--home", str(home), "--actor", "x", "recover"], out=out)
    res = json.loads(out.getvalue())
    assert rc in (0, 2) and "KeyError" not in out.getvalue()
    assert "LEDGER_LOSS_RECORDED" in res.get("abandon_error", "") or rc == 0
    out = io.StringIO()
    assert cli.run(["--home", str(home), "--actor", "x", "recover"], out=out) == 0  # re-run is clean


def test_r13_03_stale_update_after_a_recorded_loss_writes_only_the_loss(tmp_path):
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_bytes(init_anchors)
    before = len(m.store.read_all()[0].events)
    with pytest.raises(ValidationError) as e:
        m.update_milestone("MM-A", expect_version=99, objective="x")
    assert e.value.code == "LEDGER_LOSS_RECORDED"
    evs = m.store.read_all()[0].events
    assert [x["kind"] for x in evs[before:]] == ["ANCHORS_ADOPTED"]
    with pytest.raises(ValidationError) as e:
        m.update_milestone("MM-A", expect_version=99, objective="x")
    assert e.value.code == "CONFLICT"
    assert len(m.store.read_all()[0].events) == before + 1  # the refused update wrote nothing (F5)


# ------------------------------------------------------------------ R14 regression tests (review R14 on b59c1f2a)

def _interrupted_loss_recording(tmp_path, monkeypatch):
    """A write records ANCHORS_ADOPTED and is interrupted (Ctrl-C) before it can refuse and tell its user."""
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_bytes(init_anchors)
    def interrupted(label):
        raise KeyboardInterrupt()
    monkeypatch.setattr(m.store, "autocommit", interrupted)
    with pytest.raises(KeyboardInterrupt):
        m.create_milestone("MM-B", "B")
    monkeypatch.undo()
    return m


def test_r14_01_unseen_loss_cannot_be_resolved_by_entity_name(tmp_path, monkeypatch):
    m = _interrupted_loss_recording(tmp_path, monkeypatch)
    assert views.open_conflicts(m.projection(), "LEDGER")  # recorded, but its user was never told
    for ids in ([], ["deadbeef0000"]):
        with pytest.raises(ValidationError) as e:
            m.resolve_conflict("LEDGER", "routine", ids)
        assert e.value.code in ("NO_CONFLICT_ID", "UNKNOWN_CONFLICT_ID")
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "a", "resolve-conflict", "LEDGER", "--note", "x"], out=out) == 1
    out = io.StringIO()
    cli.run(["--home", str(m.home), "conflicts"], out=out)
    shown = [r["id"] for r in json.loads(out.getvalue())]
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "a", "resolve-conflict", "LEDGER", "--note", "reviewed",
                    *[a for i in shown for a in ("--id", i)]], out=out) == 0
    assert not views.open_conflicts(m.projection())


def test_r14_01_status_points_to_the_conflicts_listing(tmp_path, monkeypatch):
    """(Changed after R19-01: status no longer prints a ready-to-run id; `conflicts` shows every conflict and id.)"""
    m = _interrupted_loss_recording(tmp_path, monkeypatch)
    out = io.StringIO()
    cli.run(["--home", str(m.home), "--no-emoji", "status", "--no-tasks"], out=out)
    assert "conflicts --entity LEDGER" in out.getvalue() and "--id " not in out.getvalue().replace("--id <id>", "")
    out = io.StringIO()
    cli.run(["--home", str(m.home), "conflicts", "--entity", "LEDGER"], out=out)
    assert json.loads(out.getvalue())[0]["id"] == views.conflict_rows(m.projection())[0]["id"]


def test_r14_02_refusal_reports_autocommit_errors(tmp_path, monkeypatch):
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_bytes(init_anchors)
    from scripts.dev_workflow.milestones import store as store_mod
    monkeypatch.setattr(store_mod.EventStore, "autocommit", lambda self, label: {"committed": False,
                                                                                  "error": "git: disk full"})
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "a", "milestone-add", "MM-B", "--title", "B"], out=out) == 1
    res = json.loads(out.getvalue())
    assert res["refused"] == "LEDGER_LOSS_RECORDED" and res["autocommit_error"] == "git: disk full"


# ------------------------------------------------------------------ R15 regression tests (review R15 on 255b9079)

def test_r15_01_conflicts_raised_by_one_event_are_resolved_by_its_id_and_accept_follows(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-X", "x")
    m2.create_milestone("MM-X", "x")  # the same id created on two hosts
    m2.record_decision("B", "b", "2026-10-22", "AGENT-RECORD", "s", ident="LDEC-900")
    m1.record_decision("A", "a", "2026-10-22", "AGENT-RECORD", "s", ident="LDEC-900")
    _merge(m1, home2)
    p = m1.projection()
    rows = [r for r in views.conflict_rows(p) if r["entity"] == "MM-X"]
    assert len(rows) >= 2 and len({r["id"] for r in rows}) < len(rows)  # several conflicts, one event id
    with pytest.raises(ValidationError) as e:
        m1.resolve_conflict("MM-X", "x", [])
    assert rows[0]["id"] not in str(e.value)  # since R20-01 the refusal points to `conflicts` instead of listing ids
    _resolve(m1, "MM-X", "duplicate creation reviewed")
    _resolve(m1, "LDEC-900", "duplicate decision reviewed")
    assert not views.open_conflicts(m1.projection(), "MM-X") and not views.open_conflicts(m1.projection(), "LDEC-900")
    m1.set_status("MM-X", "IN_PROGRESS", "go")
    m1.update_milestone("MM-X", candidate_commit=C1)
    m1.record_review("MM-X", C1, "subagent", "subagent:r1", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m1.set_status("MM-X", "ACCEPTED", "independent accept")


def test_r15_02_loss_refusal_names_the_ids_to_resolve(tmp_path):
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_bytes(init_anchors)
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-B", "B")
    cid = views.conflict_rows(m.projection())[0]["id"]
    assert f"--id {cid}" in str(e.value)


# ------------------------------------------------------------------ R16 regression tests (review R16 on f07da5d0)

def test_r16_01_a_conflict_raised_after_a_later_sync_is_not_closed_by_an_earlier_resolution(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-X", "x")
    m1.create_milestone("MM-Y", "y")
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    m2.update_milestone("MM-X", objective="edited on h2")                              # B1
    m2.update_milestone("MM-Y", candidate_commit=C2)
    m2.record_review("MM-Y", C2, "subagent", "subagent:q", "SUBAGENT", "REJECT", 1, 1,
                     "COMPLETED_WITH_RESULT", "no")                                     # RV-1 on h2
    m1.update_milestone("MM-X", candidate_commit=C1)
    m1.set_status("MM-X", "IN_PROGRESS", "go")
    m1.record_review("MM-X", C1, "subagent", "subagent:r", "SUBAGENT", "ACCEPT", 0, 0,
                     "COMPLETED_WITH_RESULT", "ok")                                     # RV-1 on h1
    m1.set_status("MM-X", "ACCEPTED", "accepted")                                      # H
    seg2 = (home2 / "events" / "h2.jsonl").read_bytes().split(b"\n")[:-1]
    (m1.home / "events" / "h2.jsonl").write_bytes(seg2[0] + b"\n")                    # sync 1: only B1
    _resolve(m1, "MM-X", "concurrent objective edit reviewed")
    assert not views.open_conflicts(m1.projection(), "MM-X")
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")          # sync 2: the rest
    p = m1.projection()
    assert any(c["type"] == "BASIS_INVALID" for c in views.open_conflicts(p, "MM-X"))
    assert any(r["type"] == "BASIS_INVALID" for r in views.conflict_rows(p, "MM-X"))  # displayed, then resolvable


@pytest.mark.parametrize("ident", ["RV-1", "AP-2", "BLK-3", "HO-1", "EV-1", "DEC-001", "LDEC-001", "REG-B-X",
                                   "PROJECT", "LEDGER"])
def test_r16_02_milestone_ids_cannot_take_generated_or_reserved_names(tmp_path, ident):
    m = new(tmp_path)
    with pytest.raises(ValidationError) as e:
        m.create_milestone(ident, "x")
    assert e.value.code == "RESERVED_ID"


# ------------------------------------------------------------------ R17 regression tests (review R17 on 4f462be7)

def _r17_scenario(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-X", "x")
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    m2.update_milestone("MM-X", next_action="harmless")                       # U1
    m2.record_implementer("MM-X", "rev:y")                                     # U2: the reviewer becomes implementer
    m1.update_milestone("MM-X", candidate_commit=C1)
    m1.set_status("MM-X", "IN_PROGRESS", "go")
    m1.record_review("MM-X", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m1.set_status("MM-X", "ACCEPTED", "accepted")                              # H
    seg2 = (home2 / "events" / "h2.jsonl").read_bytes().split(b"\n")[:-1]
    return m1, seg2


def test_r17_01_a_resolved_conflict_whose_content_grows_is_open_again(tmp_path):
    m1, seg2 = _r17_scenario(tmp_path)
    (m1.home / "events" / "h2.jsonl").write_bytes(seg2[0] + b"\n")            # sync U1 only
    _resolve(m1, "MM-X", "next_action edit is harmless")
    assert not views.open_conflicts(m1.projection(), "MM-X")
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")   # sync U2
    p = m1.projection()
    types = {c["type"] for c in views.open_conflicts(p, "MM-X")}
    assert "VERSION" in types                       # the shown VERSION conflict changed: open again
    assert "BASIS_INVALID" in types                 # and the ACCEPTED basis is no longer independent
    assert views.indicator(p, p["milestones"]["MM-X"])["color"] == "RED"


# ------------------------------------------------------------------ R18 regression tests (review R18 on c455dee2)

def test_r18_01_an_id_read_before_a_sync_is_stale(tmp_path):
    m1, seg2 = _r17_scenario(tmp_path)
    (m1.home / "events" / "h2.jsonl").write_bytes(seg2[0] + b"\n")            # sync U1
    shown = [r["id"] for r in views.conflict_rows(m1.projection()) if r["entity"] == "MM-X"]
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")   # sync U2 lands before the resolve
    with pytest.raises(ValidationError) as e:
        m1.resolve_conflict("MM-X", "harmless", shown)
    assert e.value.code in ("STALE_CONFLICT_ID", "UNKNOWN_CONFLICT_ID")
    p = m1.projection()
    assert any(c["type"] == "BASIS_INVALID" for c in views.open_conflicts(p, "MM-X"))
    with pytest.raises(ValidationError) as e:  # the bare event part is not enough either
        m1.resolve_conflict("MM-X", "harmless", [s.split(".")[0] for s in shown])
    assert e.value.code == "UNKNOWN_CONFLICT_ID"


def test_r18_02_fold_with_many_resolved_conflicts_is_fast(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    n = 1000
    with m.store.locked():
        for i in range(n):  # n concurrent-looking updates, each raising one VERSION conflict
            m.store.append("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": str(i)}}, actor="x",
                           base={"MM-A": 0})
    p = m.projection()
    rows = [c for c in views.open_conflicts(p, "MM-A")]
    with m.store.locked():
        for c in rows:
            m.store.append("CONFLICT_RESOLVED", {"entity": "MM-A", "note": "n", "conflicts": [c["event"]["hash"]],
                                                 "seen": [[c["event"]["hash"], c["type"],
                                                           model.conflict_fingerprint(c)]]}, actor="x")
        m.store.write_anchors(m.store.read_all())
    t0 = time.perf_counter()
    p = m.projection()
    views.status_json(p)
    assert time.perf_counter() - t0 < 1.5
    assert not views.open_conflicts(p)


def test_r18_03_adding_a_detail_key_does_not_reopen_resolved_conflicts(tmp_path, monkeypatch):
    m1, m2, home2 = _two_hosts(tmp_path)
    m1.create_milestone("MM-A", "A")
    (home2 / "events" / "h1.jsonl").write_bytes(m1.store.segment_path.read_bytes())
    m1.update_milestone("MM-A", objective="1")
    m2.update_milestone("MM-A", objective="2")
    _merge(m1, home2)
    _resolve(m1, "MM-A", "reviewed")
    monkeypatch.setattr(model, "CONFLICT_DETAIL_KEYS", model.CONFLICT_DETAIL_KEYS + ("note_added_later",))
    assert not views.open_conflicts(m1.projection())


# ------------------------------------------------------------------ R19 regression tests (review R19 on dc22ece1)

def test_r19_01_status_never_hands_out_an_id_that_covers_unshown_conflicts(tmp_path):
    m1, seg2 = _r17_scenario(tmp_path)
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")   # full sync
    out = io.StringIO()
    cli.run(["--home", str(m1.home), "--no-emoji", "status", "--no-tasks"], out=out)
    text = out.getvalue()
    assert "conflicts --entity MM-X" in text and "BASIS_INVALID" in text       # every type is named in status
    for r in views.conflict_rows(m1.projection()):
        assert r["id"] not in text                                             # no ready-to-run id in status
    out = io.StringIO()
    cli.run(["--home", str(m1.home), "conflicts", "--entity", "MM-X"], out=out)
    assert {"VERSION", "BASIS_INVALID"} <= {r["type"] for r in json.loads(out.getvalue())}


# ------------------------------------------------------------------ R20 regression tests (review R20 on e008d3ff)

def test_r20_01_no_id_refusal_prints_no_ids(tmp_path):
    m1, seg2 = _r17_scenario(tmp_path)
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")
    with pytest.raises(ValidationError) as e:
        m1.resolve_conflict("MM-X", "x", [])
    assert e.value.code == "NO_CONFLICT_ID" and "conflicts --entity MM-X" in str(e.value)
    for r in views.conflict_rows(m1.projection()):
        assert r["id"] not in str(e.value) and r["id"].split(".")[0] not in str(e.value)


def test_r20_01_loss_refusal_shows_the_loss_detail(tmp_path):
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_bytes(init_anchors)
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-B", "B")
    assert "not anchored yet" in str(e.value)


def test_r20_02_filtered_listing_contains_the_whole_group_behind_each_id(tmp_path):
    m1, m2, home2 = _two_hosts(tmp_path)
    for m in (m1, m2):
        m.create_milestone("MM-1", "1")
        m.create_milestone("MM-2", "2")
    m2.update_milestone("MM-2", candidate_commit=C2)
    m2.record_review("MM-2", C2, "subagent", "r:b", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "no")
    m1.update_milestone("MM-1", candidate_commit=C1)
    m1.record_review("MM-1", C1, "subagent", "r:a", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    _merge(m1, home2)
    p = m1.projection()
    for target in ("MM-1", "MM-2"):
        rows = views.conflict_rows(p, target)
        for r in rows:  # every conflict carrying a listed id is in the listing
            same = [x for x in views.conflict_rows(p) if x["id"] == r["id"] and x["entity"] == r["entity"]]
            assert all(x in rows for x in same)


# ------------------------------------------------------------------ R21 regression tests (review R21 on 8745a8d0)

ID_TOKEN = __import__("re").compile(r"\b[0-9a-f]{12}\.[0-9a-f]{6}\b")


def test_r21_01_stale_refusal_prints_no_id(tmp_path):
    m1, seg2 = _r17_scenario(tmp_path)
    (m1.home / "events" / "h2.jsonl").write_bytes(seg2[0] + b"\n")
    shown = [r["id"] for r in views.conflict_rows(m1.projection()) if r["entity"] == "MM-X"]
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")
    with pytest.raises(ValidationError) as e:
        m1.resolve_conflict("MM-X", "x", shown[:1])
    assert e.value.code == "STALE_CONFLICT_ID"
    assert ID_TOKEN.findall(str(e.value)) == [shown[0]]  # only the id the user typed, never a new one


def test_r21_01_no_refusal_or_warning_hands_out_ids(tmp_path):
    """Only `conflicts` (and the loss refusal for the losses it just recorded) may print ids."""
    m1, seg2 = _r17_scenario(tmp_path)
    (m1.home / "events" / "h2.jsonl").write_bytes(b"\n".join(seg2) + b"\n")
    for ids in ([], ["0123456789ab.abcdef"], ["0123"]):
        with pytest.raises(ValidationError) as e:
            m1.resolve_conflict("MM-X", "x", ids)
        assert not [i for i in ID_TOKEN.findall(str(e.value)) if i not in ids]
    with pytest.raises(ValidationError) as e:
        m1.set_status("MM-X", "DONE", "x")
    assert not ID_TOKEN.findall(str(e.value))


def test_r21_02_conflicts_listing_shows_adoption_and_unknown_history(tmp_path):
    m = new(tmp_path)
    init_anchors = m.store.anchors_path.read_bytes()
    m.create_milestone("MM-A", "A")
    m.store.anchors_path.write_bytes(init_anchors)
    with pytest.raises(ValidationError):
        m.create_milestone("MM-B", "B")
    rows = views.conflict_rows(m.projection(), "LEDGER")
    assert rows and rows[0]["detail"].get("adopted")
    m.store.anchors_path.unlink()
    m.store.reanchor("impl:a", "anchors lost", acknowledge_loss=True)
    rows = [r for r in views.conflict_rows(m.projection(), "LEDGER") if r["recorded_by"] == "ANCHORS_RESET"]
    assert rows and rows[0]["detail"].get("unknown_previous") and rows[0]["detail"].get("anchor_problems")


# ------------------------------------------------------------------ R22 regression tests (review R22 on aa70a5ba)

AWS_KEY = "AKIA" + "ABCDEFGHIJKLMNOP"
GH_TOKEN = "ghp_" + "c" * 36


@pytest.mark.parametrize("kw", [{"reason": "rotated key " + AWS_KEY}, {"actor": GH_TOKEN},
                                {"session": "xoxb-" + "1234567890abc"}])
def test_r22_01_reanchor_refuses_secrets_before_writing(tmp_path, kw):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    args = {"actor": "impl:a", "reason": "rebase", "session": None, **kw}
    with pytest.raises(StoreError) as e:
        m.store.reanchor(args["actor"], args["reason"], args["session"], acknowledge_loss=True)
    assert e.value.code == "SECRET"
    assert seg_bytes(m) == before


@pytest.mark.parametrize("argv", [["--actor", AWS_KEY, "recover"],
                                  ["--actor", "impl:a", "--session", "xoxb-1234567890abc", "recover"],
                                  ["--actor", "impl:a", "recover", "--reason", "key " + GH_TOKEN]])
def test_r22_01_recover_refuses_secrets_before_writing(tmp_path, argv):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    with m.store.segment_path.open("ab") as f:
        f.write(b'{"torn":')
    before = seg_bytes(m)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), *argv], out=out) != 0
    assert seg_bytes(m) == before and "SECRET" in out.getvalue()
    with pytest.raises(StoreError) as e:
        m.store.recover(AWS_KEY)
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def _r22_hosts(tmp_path):
    a = new(tmp_path, actor="impl:a")
    a.create_milestone("MM-1", "x")
    a.update_milestone("MM-1", candidate_commit=C1)
    clone = _clone_of(a, tmp_path, "b")
    EventStore.init_host(clone, "hb")
    return a, Manager(clone, actor="impl:b"), clone


def _r22_accept(a, integrate=False):
    a.record_review("MM-1", C1, "subagent", "rev:y", "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    a.set_status("MM-1", "ACCEPTED", "go")
    if integrate:
        a.request_approval("MM-1", "INTEGRATION", "merge?")
        a.resolve_approval("AP-1", "APPROVED", "yes", "chat")
        a.record_integration("MM-1", "master", C1)
        a.set_status("MM-1", "INTEGRATED", "merged")


@pytest.mark.parametrize("order", ["update_first", "accept_first", "integrated"])
def test_r22_02_concurrent_candidate_change_never_leaves_a_positive_status(tmp_path, order):
    a, b, clone = _r22_hosts(tmp_path)
    if order == "update_first":
        b.update_milestone("MM-1", candidate_commit=C2)
        _r22_accept(a)
    else:
        _r22_accept(a, integrate=order == "integrated")
        b.update_milestone("MM-1", candidate_commit=C2)
    (a.home / "events" / "hb.jsonl").write_bytes((clone / "events" / "hb.jsonl").read_bytes())
    p = a.projection()
    changed = [r for r in views.conflict_rows(p, "MM-1") if r["type"] == "CANDIDATE_CHANGED"]
    assert changed and changed[0]["detail"]["bound"] == C1 and changed[0]["detail"]["candidate"] == C2
    _resolve(a, "MM-1", "seen")
    p = a.projection()
    m = p["milestones"]["MM-1"]
    assert m["candidate_commit"] == C2 and not views.open_conflicts(p, "MM-1")
    ind = views.indicator(p, m)
    assert ind["color"] == "RED" and "rests on" in ind["issue"]
    out = io.StringIO()
    cli.run(["--home", str(a.home), "status", "--json", "--no-tasks"], out=out)
    row = [x for x in json.loads(out.getvalue())["milestones"] if x["id"] == "MM-1"][0]
    assert row["indicator"]["color"] == "RED"
    a.update_milestone("MM-1", candidate_commit=C1)  # the lock lets the candidate return to the bound commit
    p = a.projection()
    assert views.indicator(p, p["milestones"]["MM-1"])["color"] != "RED"


def test_r22_02_single_host_flow_binds_without_conflict(tmp_path):
    m = _accept_ready(tmp_path)
    m.set_status("MM-A", "ACCEPTED", "ok")
    p = m.projection()
    assert p["milestones"]["MM-A"]["bound_commit"] == C1
    assert not [c for c in p["conflicts"] if c["type"] == "CANDIDATE_CHANGED"]
    with pytest.raises(ValidationError) as e:
        m.update_milestone("MM-A", candidate_commit=C2)
    assert e.value.code == "CANDIDATE_LOCKED"
    m.set_status("MM-A", "IN_PROGRESS", "repair")
    m.update_milestone("MM-A", candidate_commit=C2)
    p = m.projection()
    assert p["milestones"]["MM-A"]["bound_commit"] is None
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] != "RED"


@pytest.mark.parametrize("status", ["ACCEPTED", "INTEGRATED", "DONE"])
@pytest.mark.parametrize("membership", ["recorded", "assigned", "handoff"])
def test_d1_01_positive_status_rechecks_reviewer_independence(tmp_path, status, membership):
    m = _accept_ready(tmp_path, reviewer="rev:y")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    if status == "INTEGRATED":
        m.request_approval("MM-A", "INTEGRATION", "integrate?")
        m.resolve_approval("AP-1", "APPROVED", "yes", "chat")
        m.record_integration("MM-A", "master", C1)
        m.set_status("MM-A", "INTEGRATED", "integrated")
    elif status == "DONE":
        m.set_status("MM-A", "DONE", "done")

    reviewer = Manager(m.home, actor=" REV:Y ", session="s2")
    if membership == "recorded":
        m.record_implementer("MM-A", " REV:Y ")
    elif membership == "assigned":
        reviewer.assign("MM-A")
    else:
        reviewer.record_handoff("MM-A", "implementation handoff")

    p = m.projection()
    milestone = p["milestones"]["MM-A"]
    assert milestone["status"] == status
    assert any(c["type"] == "BASIS_INVALID" for c in views.open_conflicts(p, "MM-A"))
    ind = views.indicator(p, milestone)
    assert ind["color"] == "RED"
    assert views.status_json(p)["milestones"][0]["indicator"]["color"] == "RED"

    # Acknowledging the conflict alone cannot make the stale status look valid.
    _resolve(m, "MM-A", "reviewer became an implementer")
    p = m.projection()
    ind = views.indicator(p, p["milestones"]["MM-A"])
    assert ind["color"] == "RED" and "independent" in ind["issue"]

    # A separate qualifying review on the same candidate restores the claim.
    m.record_review("MM-A", C1, "subagent", "rev:z", "SUBAGENT", "ACCEPT", 0, 0,
                    "COMPLETED_WITH_RESULT", "independent review")
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] != "RED"


def test_d1_01_invalid_positive_status_does_not_satisfy_dependency(tmp_path):
    m = _accept_ready(tmp_path, reviewer="rev:y")
    m.create_milestone("MM-B", "dependent")
    m.add_dependency("MM-B", "MM-A")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    assert "MM-B" in views.ready(m.projection())
    m.record_implementer("MM-A", "rev:y")
    assert "MM-B" not in views.ready(m.projection())


def test_r2_02_negative_review_invalidates_ready_dependency(tmp_path):
    m = _accept_ready(tmp_path)
    m.create_milestone("MM-B", "dependent")
    m.add_dependency("MM-B", "MM-A")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    assert "MM-B" in views.ready(m.projection())
    m.record_review("MM-A", C1, "subagent", "subagent:r2", "SUBAGENT", "REJECT", 1, 1,
                    "COMPLETED_WITH_RESULT", "blocking finding")
    p = m.projection()
    assert views.indicator(p, p["milestones"]["MM-A"])["color"] == "RED"
    assert "MM-A" in views.unmet_dependencies(p, p["milestones"]["MM-B"])
    assert "MM-B" not in views.ready(p)


@pytest.mark.parametrize("field,secret", [("actor", "password=12345678"),
                                           ("session", "token=123456789012"),
                                           ("data", "api_key: 12345678901234567890")])
def test_d1_02_direct_store_append_refuses_secrets_without_writing(tmp_path, field, secret):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"objective": secret if field == "data" else "safe"}}
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor=secret if field == "actor" else "impl:a",
                       session=secret if field == "session" else "s1")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_d1_02_direct_store_batch_refuses_secret_in_later_item_atomically(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    items = [("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": "safe"}}, {}),
             ("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": "password=12345678"}}, {})]
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append_many(items, actor="impl:a", session="s1")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("field", ["base_key", "base_value", "kind", "ts"])
def test_r2_01_direct_store_append_refuses_secret_metadata_without_writing(tmp_path, field):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    secret = "password=12345678"
    base = {secret: 0} if field == "base_key" else {"safe": secret} if field == "base_value" else {}
    kind = secret if field == "kind" else "MILESTONE_UPDATED"
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append(kind, {"id": "MM-A", "fields": {"objective": "safe"}}, actor="impl:a",
                       base=base, ts=secret if field == "ts" else None)
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("field", ["base_key", "base_value", "kind", "floor"])
def test_r2_01_direct_store_batch_refuses_secret_metadata_atomically(tmp_path, field):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    secret = "password=12345678"
    later_base = {secret: 0} if field == "base_key" else {"safe": secret} if field == "base_value" else {}
    later_kind = secret if field == "kind" else "MILESTONE_UPDATED"
    data = {"id": "MM-A", "fields": {"objective": "safe"}}
    items = [("MILESTONE_UPDATED", data, {}), (later_kind, data, later_base)]
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append_many(items, actor="impl:a", floor=secret if field == "floor" else "")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_r22_03_autocommit_commits_only_ledger_paths(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "-C", str(repo), "init", "-q"], check=True)
    (repo / "wip.txt").write_text("unrelated work\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "wip.txt"], check=True)
    home = repo / "ledger"
    EventStore.init(home, "h1", autocommit=True)
    Manager(home, actor="impl:a").create_milestone("MM-A", "A")
    files = subprocess.run(["git", "-C", str(repo), "log", "--name-only", "--format="], capture_output=True,
                           text=True).stdout.split()
    assert "ledger/events/h1.jsonl" in files and "wip.txt" not in files
    staged = subprocess.run(["git", "-C", str(repo), "diff", "--cached", "--name-only"], capture_output=True,
                            text=True).stdout.split()
    assert staged == ["wip.txt"]


@pytest.mark.parametrize("limit", [0, 10, 59, 60])
def test_r22_04_resume_bound_holds_for_small_limits(tmp_path, limit):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A", objective="o" * 3000)
    text = views.resume_brief(m.projection(), "MM-A", {"available": False, "reason": "x"}, max_chars=limit)
    assert len(text) <= views.MIN_RESUME_CHARS and "truncated" in text


def test_r22_05_resolve_help_names_only_conflicts():
    assert "`status`/`conflicts`" not in (ROOT / "scripts" / "dev_workflow" / "milestones" / "cli.py").read_text(
        encoding="utf-8")


@pytest.mark.parametrize("data", [
    {"details": {"access_token": "abc123def456ghi789jkl012mno345"}},
    {"details": [{"credentials": {"access_token": "abc123def456ghi789jkl012mno345"}}]},
    {"details": {"api_key": 123456789012345678901234567890}},
])
def test_r3_01_direct_store_append_refuses_nested_credential_value(tmp_path, data):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("credential", [
    {"api_key": {"value": "abcd1234xyz9876"}},
    {"access_token": [{"details": {"value": "abc123def456ghi789"}}]},
])
def test_r4_01_direct_store_append_refuses_credential_container_without_writing(tmp_path, credential):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"details": credential}}
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("credential", [
    {"api_key": {"value": "abcd1234xyz9876"}},
    {"access_token": ["abc123def456ghi789"]},
])
def test_r4_01_direct_store_batch_refuses_later_credential_container_atomically(tmp_path, credential):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    items = [("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": "safe"}}, {}),
             ("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"details": credential}}, {})]
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append_many(items, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_r4_01_find_secret_keeps_credential_context_through_containers():
    assert model.find_secret({"api_key": {"value": "abcd1234xyz9876"}}) == "credential assignment"
    assert model.find_secret({"access_token": [{"details": ["abc123def456ghi789"]}]}) == "credential assignment"
    for value in ("expired", "<redacted>", "$OPENAI_API_KEY"):
        assert model.find_secret({"api_key": {"value": [value]}}) is None
    assert model.find_secret({"api_key": {"value": ["D:/uri-dev/worktree1"]}}) == "credential assignment"


@pytest.mark.parametrize("value", [
    {"credentials": {"password": {"value": "s3cret/abc123"}}},
    {"credentials": {"access_token": [{"value": "abc123/def456ghi789"}]}},
    {"password": {"value": r"s3cret\abc123"}},
    "password=s3cret/abc123",
])
def test_r5_01_find_secret_refuses_slash_credential(value):
    assert model.find_secret(value) == "credential assignment"


@pytest.mark.parametrize("credential", [
    {"credentials": {"password": {"value": "s3cret/abc123"}}},
    {"credentials": {"access_token": [{"value": "abc123/def456ghi789"}]}},
    {"password": {"value": r"s3cret\abc123"}},
])
def test_r5_01_direct_store_append_refuses_nested_slash_credential(tmp_path, credential):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"details": credential}}
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_r5_01_direct_store_batch_refuses_later_slash_credential_atomically(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    items = [("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": "safe"}}, {}),
             ("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"credentials": {"token": "abc123/def456"}}}, {})]
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append_many(items, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("credential", [
    {"password": {"value": "/s3cret99"}},
    {"access_token": [{"value": "/abc123def456"}]},
    {"pwd": {"value": "/secretword"}},
])
def test_r6_01_slash_prefixed_nested_credentials_are_secrets(credential):
    assert model.find_secret(credential) == "credential assignment"
    assert model.find_secret({"worktree": "/uri-dev/worktree1", "details": credential}) == "credential assignment"


def test_r6_01_public_service_refuses_slash_prefixed_password(tmp_path):
    m = new(tmp_path)
    before = seg_bytes(m) if m.store.segment_path.exists() else b""
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-A", "A", objective="password=/s3cret99")
    assert e.value.code == "SECRET"
    assert (seg_bytes(m) if m.store.segment_path.exists() else b"") == before


@pytest.mark.parametrize("credential", [
    {"password": {"value": "/s3cret99"}},
    {"access_token": [{"value": "/abc123def456"}]},
    {"pwd": {"value": "/secretword"}},
])
def test_r6_01_service_write_refuses_nested_credential_without_writing(tmp_path, credential):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"details": credential}}
    with pytest.raises(ValidationError) as e:
        m._write(lambda p: [("MILESTONE_UPDATED", data, {"MM-A": p["versions"]["MM-A"]})])
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("credential", [
    {"password": {"value": "/s3cret99"}},
    {"access_token": [{"value": "/abc123def456"}]},
    {"pwd": {"value": "/secretword"}},
])
def test_r6_01_direct_store_append_refuses_nested_credential_without_writing(tmp_path, credential):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"details": credential}}
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_r6_01_actual_path_fields_remain_allowed(tmp_path):
    path = "/uri-dev/worktree1"
    assert model.find_secret({"worktree": path}) is None
    assert model.find_secret(f"worktree={path}") is None
    m = new(tmp_path)
    m.create_milestone("MM-A", "A", worktree=path)
    assert m.projection()["milestones"]["MM-A"]["worktree"] == path


@pytest.mark.parametrize("password", ["abc,defghi9", "abc, defghi9"])
def test_r7_01_direct_store_refuses_comma_in_nested_password_without_writing(tmp_path, password):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"details": {"metadata": {"password": password}}}}
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_r7_01_inline_comma_password_is_secret():
    assert model.find_secret("password=abc,defghi9") == "credential assignment"


def test_r3_02_ready_requires_dependency_status_bound_to_candidate(tmp_path):
    m = _accept_ready(tmp_path)
    m.create_milestone("MM-B", "dependent")
    m.add_dependency("MM-B", "MM-A")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    p = m.projection()
    a = p["milestones"]["MM-A"]
    assert a["bound_commit"] == C1
    p["reviews"]["RV-2"] = {**next(iter(p["reviews"].values())), "id": "RV-2", "commit": C2}
    a["candidate_commit"] = C2
    assert model.independent_accept_reviews(p, a)
    assert "MM-A" in views.unmet_dependencies(p, p["milestones"]["MM-B"])
    assert "MM-B" not in views.ready(p)


def test_r3_02_ready_rejects_dependency_with_open_conflict(tmp_path):
    m = _accept_ready(tmp_path)
    m.create_milestone("MM-B", "dependent")
    m.add_dependency("MM-B", "MM-A")
    m.set_status("MM-A", "ACCEPTED", "accepted")
    p = m.projection()
    p["conflicts"].append({"type": "VERSION", "entity": "MM-A", "subject": "MM-A", "resolved": False,
                           "event": {"hash": "f" * 64}})
    assert views.open_conflicts(p, "MM-A")
    assert "MM-A" in views.unmet_dependencies(p, p["milestones"]["MM-B"])
    assert "MM-B" not in views.ready(p)


# ------------------------------------------------------------------ driver review MILESTONE-MANAGER-d1, rounds 4-8:
# one bypass per round in the credential-value exemptions; repaired once as a class (default deny).

@pytest.mark.parametrize("value", [
    "$uperS3cret!", "$ecret-abc123", "s3cret/abc123", "/s3cret123", "abc,def123", "env-hunter22", "{s3cret123}",
    "%s3cret123", "<s3cret123", "HUNTER22", "D:/uri-dev/worktree1", "pa55 word",
])
@pytest.mark.parametrize("shape", ["dict", "nested", "text"])
def test_d1_default_deny_credential_values(value, shape):
    data = {"dict": {"password": value}, "nested": {"auth": {"password": {"value": [value]}}},
            "text": f"password={value}" if " " not in value else None}[shape]
    if data is None:
        return
    assert model.find_secret(data) == "credential assignment", (shape, value)


@pytest.mark.parametrize("value", ["${DB_PASSWORD}", "%API_KEY%", "env:OPENAI_KEY", "$OPENAI_API_KEY",
                                   "TAVILY_API_KEY", "<redacted>", "********", "expired", "none"])
def test_d1_default_deny_keeps_exact_references(value):
    assert model.find_secret({"api_key": {"value": [value]}}) is None, value
    assert model.find_secret(f"api_key: {value}") is None, value


def test_d1_default_deny_refused_by_service_and_store(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-0", "0")
    before = seg_bytes(m)
    with pytest.raises(ValidationError) as e:
        m.create_milestone("MM-A", "A", objective="password=$uperS3cret!")
    assert e.value.code == "SECRET" and seg_bytes(m) == before
    with pytest.raises(StoreError) as e:
        m.store.reanchor("impl:a", "password: $uperS3cret!", acknowledge_loss=True)
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("value", ["abc", "123", "pw"])
def test_d2_01_short_password_is_secret_in_nested_and_inline_values(value):
    assert model.find_secret({"password": {"value": value}}) == "credential assignment"
    assert model.find_secret(f"password={value}") == "credential assignment"


def test_d2_01_direct_store_refuses_short_password_without_writing(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    data = {"id": "MM-A", "fields": {"details": {"password": {"value": "abc"}}}}
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", data, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


@pytest.mark.parametrize("value", ["${PASSWORD} hunter2", '"${PASSWORD} hunter2"', "${PASSWORD} 'hunter2'",
                                   "%PASSWORD% hunter2", "env:DB_PASSWORD hunter2"])
def test_d2_02_reference_followed_by_password_is_secret(value):
    assert model.find_secret(f"password: {value}") == "credential assignment"


def test_d2_02_service_and_direct_store_refuse_reference_followed_by_password(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    value = "password: ${PASSWORD} hunter2"
    with pytest.raises(ValidationError) as e:
        m.update_milestone("MM-A", objective=value)
    assert e.value.code == "SECRET" and seg_bytes(m) == before
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": value}}, actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


# ------------------------------------------------------------------ fallback review of f76c2e17 (FB-01..FB-05):
# credential keys recognised by their words; quoted keys; leaf dict keys under a credential key; NFKC.

FB_SECRETS = [
    "DB_PASSWORD=hunter2bypass1", "github_token=abcdefbypass3", "myPassword=bypass4", "passwordValue: hunter22",
    '{"password": "hunter2bypass2"}', "{'password': 'hunter2'}", '"password"="hunter2"', 'config {"api_key":"abc123def"}',
    "password=HUNTER_TWO", "secret=1234567", "password\uff1dhunter22", "pass\u200bword=hunter22",
    "password: env:DB_PASSWORD hunter2", 'note: x, client-secret: "s3cr3tvalue"',
    {"db_password": "hunter22"}, {"clientSecret": "abc123"}, {"password": {"BYPASS_b2y": None}},
    {"password": {"BYPASS_b2y": True}}, {"auth": {"apiKey": ["abc123def"]}},
]
FB_CLEAN = [
    "max_tokens=4096", "token_count=12", "token: 128k context", "token: 32768 tokens", "password_policy: strong",
    "api_key: ${KEY}, model: x", "worktree=D:/uri-dev/x", "api_key: TAVILY_API_KEY", "API_KEY=$OPENAI_API_KEY",
    "the token expired", "D:/secrets/readme", {"api_key": {"value": ["<redacted>"]}}, {"token_count": 5},
]


@pytest.mark.parametrize("value", FB_SECRETS)
def test_fb_credential_keys_by_words_are_refused(value):
    assert model.find_secret(value), value


@pytest.mark.parametrize("value", FB_CLEAN)
def test_fb_descriptive_keys_and_references_pass(value):
    assert model.find_secret(value) is None, value


@pytest.mark.parametrize("argv", [["milestone-update", "MM-A", "--objective", "DB_PASSWORD=hunter2bypass1"],
                                  ["milestone-update", "MM-A", "--next-action", '{"password": "hunter2bypass2"}']])
def test_fb_cli_refuses_without_writing(tmp_path, argv):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", *argv], out=out) != 0
    assert seg_bytes(m) == before and "SECRET" in out.getvalue()


def test_fb_direct_store_refuses_leaf_key_and_prefixed_key(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    for data in ({"id": "X", "password": {"BYPASS_b2y": None}}, {"id": "X", "db_password": "hunter22"}):
        with pytest.raises(StoreError) as e:
            m.store.append_many([("HANDOFF_RECORDED", data, {})], actor="impl:a")
        assert e.value.code == "SECRET"
    assert seg_bytes(m) == before


# ------------------------------------------------------------------ fallback review of de0354ef (FB2-01..FB2-06)
# within the bounded F16 contract (owner decision 2026-10-22, ACCEPTANCE_CRITERIA.md amendment log).

FB2_SECRETS = [
    "mysql -u root --password=hunter2", "run --api-key=abc123def456", "gh auth --token=abcdef123456",
    "tool -password=hunter2", "--client-secret=Zx9kq2abc", "mysql --password hunter2", "--pwd hunter2",
    "**password**: hunter2", "`password`: hunter2", "password:\n  hunter2", "password: |\n  hunter2",
    "| password | hunter2 |", '{"db password": "hunter2"}', '{"password ": "hunter2"}',
    "token=TOKEN_8F3A9C2B7D1E6F", "api_key=API_KEY_9F8E7D6C5B4A3F2E", "password=SUPER_SECRET_99",
    "password=$ADMIN_PASSWORD_2024", {"api_key": "PROD_API_KEY_7Q2W9E4R"}, "password= TOKEN_ABC_ZZZ91",
    "password_reset=NewPass2024!", "admin_password_rotated: Spring2026!", "password_used=Hunter2!",
    "password_hint: hunter2", "password_file=hunter2", "DB_PASSWORD_FILE=hunter2", "secret_path=Xk9vQ2",
    "client_secret_expiry=Zx9!kq2", "api_key_size=abc123def456ghi", {"api_key_type": "q8W3eR5tY7"},
    "Authorization: Basic dXNlcjpodW50ZXIy", "passcode=482913", "session_key=abc123def", "token: 482913",
    {"token": 4829131}, "password: none;hunter2", "password=none|hunter2", "password=xXx.X",
    {"password": {"hunter2": "x"}}, {"password": {"hunter2": "none"}},
]
FB2_CLEAN = [
    "token: 65536", "-ot token_embd.weight=CPU", "password_file=D:/vault/pw.txt", "token_limit: 4096",
    "api_key_type: bearer", "token_expiry=2026-10-22", "| Field | Value |", "| Token | Value | Why |",
    "password: ****", '"monthly_token_ceiling": 100000',
]


@pytest.mark.parametrize("value", FB2_SECRETS)
def test_fb2_contract_notations_are_refused(value):
    assert model.find_secret(value), value


@pytest.mark.parametrize("value", FB2_CLEAN)
def test_fb2_descriptive_shapes_and_context_sizes_pass(value):
    assert model.find_secret(value) is None, value


@pytest.mark.parametrize("argv", [["handoff", "MM-A", "--summary", "mysql --password=hunter2"],
                                  ["milestone-update", "MM-A", "--next-action", "**password**: hunter2"],
                                  ["milestone-update", "MM-A", "--next-action", "password_reset=NewPass2024!"]])
def test_fb2_cli_refuses_without_writing(tmp_path, argv):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", *argv], out=out) != 0
    assert seg_bytes(m) == before and "SECRET" in out.getvalue()


# ------------------------------------------------------------------ fallback review of 4aa3d40b (FB3-01..FB3-06)

FB3_SECRETS = [
    "API key: 9f8e7d6c5b4a3f2e1d0c", "Secret key: 9f8e7d6c5b4a3f2e", "Private key: abcdef123456",
    "Access key = abc123def456", "Session key: abc123def", "- **API key:** 9f8e7d6c5b4a", "| DB password | hunter2 |",
    "| API key | 9f8e7d6c |", '| "password" | hunter2 |', "| password | correct horse battery staple |",
    "__password__: hunter2", "_password_: hunter2", "~~password~~: hunter2", "password: |\n  none\n  hunter2",
    "password: >-\n  ${PASS}\n  hunter2", "PGPASSWORD=hunter2", "accesstoken=abc123", "authtoken: abc123",
    "adminpassword=hunter2", {"PGPASSWORD": "hunter2"},
]
FB3_CLEAN = ["api_key: env:VAR_NAME1", "| Gmail credential scoping | owner |", "the API key is set", "tokens: 4096",
             "tokenizer: bpe", "key: decision", "password: |\n  ${PASS}\nnext: x"]


@pytest.mark.parametrize("value", FB3_SECRETS)
def test_fb3_multiword_markdown_table_and_block_keys_are_refused(value):
    assert model.find_secret(value), value


@pytest.mark.parametrize("value", FB3_CLEAN)
def test_fb3_prose_tables_and_references_pass(value):
    assert model.find_secret(value) is None, value


@pytest.mark.parametrize("argv", [["handoff", "MM-A", "--summary", "API key: 9f8e7d6c5b4a3f2e1d0c"],
                                  ["milestone-update", "MM-A", "--next-action", "| DB password | hunter2 |"],
                                  ["milestone-update", "MM-A", "--next-action", "__password__: hunter2"],
                                  ["handoff", "MM-A", "--summary", "password: |\n  none\n  hunter2"]])
def test_fb3_cli_refuses_without_writing(tmp_path, argv):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", *argv], out=out) != 0
    assert seg_bytes(m) == before and "SECRET" in out.getvalue()


@pytest.mark.parametrize("ident", ["PASSWORD-RESET", "TOKEN-REFRESH", "SECRET-STORE", "OAUTH-TOKEN", "API-KEY-ROTATION"])
def test_fb3_05_credential_words_in_milestone_ids_stay_writable(tmp_path, ident):
    m = new(tmp_path)
    m.create_milestone(ident, "t")
    m.update_milestone(ident, next_action="continue")
    m.set_status(ident, "IN_PROGRESS", "start")
    assert m.projection()["milestones"][ident]["status"] == "IN_PROGRESS"


# ------------------------------------------------------------------ fallback review of 1483a4ea (FB4-01..FB4-06)

FB4_SECRETS = [
    "_password = 'hunter2'", "__password = 'hunter2'", "_DB_PASSWORD=hunter2", "export _TOKEN=abc123def",
    "_api_key: abc123def", "1password: hunter2", "___password___: hunter2", "os.environ['DB_PASSWORD'] = 'hunter2'",
    "cfg['password'] = 'hunter2'", 'cfg["api_key"]="abc123def"', {"Authorization": "Basic dXNlcjpodW50ZXIy"},
    '{"Authorization": "Basic dXNlcjpodW50ZXIy"}', "| Authorization | Basic dXNlcjpodW50ZXIy |",
    "**Authorization**: Basic dXNlcjpodW50ZXIy", "AUTHKEY=abc123", "passwords: hunter2",
]
FB4_CLEAN = ["PASSWORD-RESET: done", "- PASSWORD-RESET: ACCEPTED", "| PASSWORD-RESET | ACCEPTED |",
             "OAUTH-TOKEN: implemented refresh flow", "Blocked: TOKEN-REFRESH: waiting on owner", "password:\n  - required",
             "authorization: owner approved"]


@pytest.mark.parametrize("value", FB4_SECRETS)
def test_fb4_prefixed_subscripted_and_basic_forms_are_refused(value):
    assert model.find_secret(value), value


@pytest.mark.parametrize("value", FB4_CLEAN)
def test_fb4_milestone_ids_and_list_markup_pass(value):
    assert model.find_secret(value) is None, value


@pytest.mark.parametrize("base", [{"password": "hunter2xyz"}, {"api_key": "abc123def456"},
                                  {"db_password": "Tr0ub4dor&3"}, {"MM-A": 0, "token": "abc123def456"}])
def test_fb4_01_store_base_pairs_stay_checked(tmp_path, base):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    with m.store.locked(), pytest.raises(StoreError) as e:
        m.store.append_many([("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"objective": "x"}}, base)],
                            actor="impl:a")
    assert e.value.code == "SECRET" and seg_bytes(m) == before


def test_fb4_cli_refuses_subscripted_key_without_writing(tmp_path):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    out = io.StringIO()
    assert cli.run(["--home", str(m.home), "--actor", "impl:a", "milestone-update", "MM-A", "--objective",
                    "os.environ['DB_PASSWORD'] = 'hunter2'"], out=out) != 0
    assert seg_bytes(m) == before and "SECRET" in out.getvalue()


@pytest.mark.parametrize("value", [
    '--password "required hunter2"',
    '-pwd "%DB_PASSWORD% hunter2"',
    '--api-key "<redacted> abc123xyz"',
    "--password 'required hunter2'",
])
def test_d6_01_quoted_flag_value_refuses_secret_after_allowed_prefix(value):
    assert model.find_secret(value) == "credential assignment"


def test_d6_01_store_preflight_refuses_quoted_flag_value():
    with pytest.raises(StoreError) as e:
        check_free_text(data={"title": '--password "required hunter2"'})
    assert e.value.code == "SECRET"


@pytest.mark.parametrize("value", [
    '--password "required hunter2"',
    '-pwd "%DB_PASSWORD% hunter2"',
    '--api-key "<redacted> abc123xyz"',
    "--password 'required hunter2'",
])
def test_d6_01_store_refuses_quoted_flag_value_without_writing(tmp_path, value):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    with pytest.raises(StoreError) as e:
        m.store.append_many([("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"title": value}}, {})],
                            actor="impl:a")
    assert e.value.code == "SECRET"
    assert seg_bytes(m) == before


@pytest.mark.parametrize("value", [
    '{"password":{"value":"hunter2"}}',
    "{'password': {'value': 'hunter2'}}",
    'config {"credentials":{"password":{"value":"hunter2"}}}',
])
def test_d6_02_inline_nested_credential_is_secret_in_free_text(value):
    assert model.find_secret(value) == "credential assignment"
    with pytest.raises(StoreError) as e:
        check_free_text(data={"title": value})
    assert e.value.code == "SECRET"


@pytest.mark.parametrize("value", [
    '{"password":{"value":"hunter2"}}',
    "{'password': {'value': 'hunter2'}}",
])
def test_d6_02_batch_refuses_inline_nested_credential_before_append(tmp_path, value):
    m = new(tmp_path)
    m.create_milestone("MM-A", "A")
    before = seg_bytes(m)
    items = [("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"title": "safe"}}, {}),
             ("MILESTONE_UPDATED", {"id": "MM-A", "fields": {"title": value}}, {})]
    with pytest.raises(StoreError) as e:
        m.store.append_many(items, actor="impl:a")
    assert e.value.code == "SECRET"
    assert seg_bytes(m) == before


@pytest.mark.parametrize("value", [
    '{"password":{"value":["<redacted>"]}}',
    "{'api_key': {'value': ['${API_KEY}']}}",
])
def test_d6_02_inline_nested_credential_references_remain_writable(value):
    assert model.find_secret(value) is None
    check_free_text(data={"title": value})
