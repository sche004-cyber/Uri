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
from scripts.dev_workflow.milestones.store import EventStore, StoreError, read_segment

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
    m1.resolve_conflict("MM-A", "kept h2 objective")
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
    assert e.value.code == "LATER_NEGATIVE_REVIEW"


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
    m.record_decision("Use JSONL", "Ledger is JSONL", "2026-10-21", "OWNER-PROMPT", "prompt", ident="DEC-091")
    with pytest.raises(ValidationError) as e:
        m.record_decision("Other", "x", "2026-10-21", "OWNER-PROMPT", "prompt", ident="DEC-091")
    assert e.value.code == "EXISTS"
    m.record_decision("Use SQLite", "Ledger is SQLite", "2026-10-22", "OWNER-PROMPT", "prompt",
                      supersedes="DEC-091", reasoning="scale")
    m.correct_decision("DEC-091", "date was 2026-10-21 UTC", "AGENT-RECORD", "review R1")
    p = m.projection()
    old, new_ = p["decisions"]["DEC-091"], p["decisions"]["DEC-092"]
    assert old["decision"] == "Ledger is JSONL" and old["status"] == "SUPERSEDED"
    assert old["superseded_by"][0]["by"] == "DEC-092" and new_["supersedes"][0]["id"] == "DEC-091"
    assert old["corrections"][0]["correction"].startswith("date")


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
    assert e.value.code == "LATER_NEGATIVE_REVIEW"
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


@pytest.mark.parametrize("text", ["pwd=D:/uri-dev/worktree1", "api_key: env-var-NAME1", "API_KEY=$OPENAI_API_KEY",
                                  "token: TAVILY_API_KEY", "password: required", "see https://example.com/a:b"])
def test_r1_09_no_false_positive_on_paths_and_env_names(text):
    assert model.find_secret(text) is None, text


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
    def half(items, actor, session=None, ts=None):
        evs = real(items, actor, session, ts)
        path = m.store.segment_path
        lines = path.read_bytes().split(b"\n")[:-1]
        path.write_bytes(b"\n".join(lines[:-1]) + b"\n" + lines[-1][:20])  # second event torn
        raise OSError("ENOSPC simulated")
    monkeypatch.setattr(m.store, "append_many", half)
    with pytest.raises(OSError):
        m.record_decision("New", "new", "2026-10-22", "AGENT-RECORD", "s", supersedes="DEC-001")
    monkeypatch.undo()
    m.store.recover("impl:a")
    p = m.projection()
    assert set(p["decisions"]) == {"DEC-001"} and p["decisions"]["DEC-001"]["status"] == "ACTIVE"
    assert any("incomplete batch" in w for w in p["integrity_warnings"])
    m.record_decision("New", "new", "2026-10-22", "AGENT-RECORD", "s", supersedes="DEC-001")  # retry works
    p = m.projection()
    assert p["decisions"]["DEC-001"]["status"] == "SUPERSEDED" and p["decisions"]["DEC-002"]["decision"] == "new"
