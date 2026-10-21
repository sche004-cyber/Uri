"""Lifecycle V3.1 task ledger: acceptance criteria AC-1..AC-12 of docs/dev_workflow/LIFECYCLE_V3_1_PLAN_AND_ACCEPTANCE.md."""
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import time
from pathlib import Path

import pytest

from scripts.dev_workflow import task_ledger as tl
from scripts.dev_workflow.lifecycle import State, sha256, write_json

ROOT = Path(__file__).resolve().parents[2]
DEV = "claude:impl-session"
REV = "subagent:reviewer-1"


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "repo"
    r.mkdir()
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "core.autocrlf", "false")
    (r / "a.txt").write_bytes(b"one\n")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "c1")
    return r


def _commit(repo, name, data):
    (repo / name).write_bytes(data)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def lp(tmp_path):
    return tmp_path / "ledger" / "ledger.sqlite3"


@pytest.fixture
def lg(lp):
    x = tl.Ledger(lp)
    yield x
    x.close()


def cli(lp, *args):
    return subprocess.run([sys.executable, "-m", "scripts.dev_workflow.task_ledger", "--ledger", str(lp), *args],
                          capture_output=True, text=True, cwd=ROOT)


def py(code):
    return subprocess.Popen([sys.executable, "-c", textwrap.dedent(code)], cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, text=True)


def review_file(tmp_path, commit, verdict="ACCEPT", findings=(), prior=(), name="review.txt"):
    f = tmp_path / name
    body = {"candidate": commit, "baseline": "x", "verdict": verdict, "findings": list(findings),
            "prior_findings": list(prior)}
    f.write_text("review notes\nAUDIT_RESULT_BEGIN\n" + json.dumps(body) + "\nAUDIT_RESULT_END\n", encoding="utf-8")
    return f


def ready_for_review(lg, repo, tid):
    lg.transition(tid, "IN_PROGRESS", DEV)
    head = _commit(repo, "b.txt", b"feature\n")
    lg.set_head(tid, DEV, head)
    lg.record_test(tid, DEV, head, True, "unit 5 passed")
    lg.transition(tid, "IN_REVIEW", DEV)
    return head


# ------------------------------------------------------------------ AC-1 identity

def test_ac1_identity_survives_restart(lp, repo):
    lg = tl.Ledger(lp)
    tid = lg.create("t", "objective X", DEV, worktree=str(repo), milestone_ref="LIFECYCLE-V3-1")
    lg.close()
    r = cli(lp, "show", tid)
    assert r.returncode == 0, r.stderr
    s = json.loads(r.stdout)
    assert s["task_id"] == tid and s["milestone_ref"] == "LIFECYCLE-V3-1" and s["status"] == "OPEN"
    assert tl.Ledger(lp).verify() == []


def test_ac1_ids_unique_under_concurrent_creation(lp):
    tl.Ledger(lp).close()
    procs = [py(f"""
        from scripts.dev_workflow.task_ledger import Ledger
        lg = Ledger(r"{lp}")
        for i in range(15):
            print(lg.create("p{n}-%d" % i, "o", "claude:p{n}"))
        """) for n in range(6)]
    ids = []
    for p in procs:
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err
        ids += out.split()
    assert len(ids) == 90 and len(set(ids)) == 90
    assert tl.Ledger(lp).verify() == []


# ------------------------------------------------------------------ AC-2 context continuity, AC-10 handoff

def _rich_task(lg, repo):
    tid = lg.create("ctx", "Deliver persistent task ids", DEV, worktree=str(repo))
    lg.add_context(tid, DEV, "constraint", "no new dependencies")
    lg.add_context(tid, DEV, "decision", "use SQLite WAL", key="storage")
    lg.add_context(tid, DEV, "todo", "write migration", key="mig")
    lg.add_context(tid, DEV, "todo", "write docs", key="docs")
    lg.add_context(tid, DEV, "done", "docs written", key="docs")
    lg.add_context(tid, DEV, "next_action", "run the V3 import against D:/uri-dev/lifecycle")
    lg.add_context(tid, DEV, "evidence", "bench shows 0.4 ms per append")
    head = ready_for_review(lg, repo, tid)
    lg.add_finding(tid, REV, "F-1", "HIGH", "redaction misses bearer tokens")
    return tid, head


def test_ac2_context_survives_session_replacement(lp, repo):
    lg = tl.Ledger(lp)
    tid, head = _rich_task(lg, repo)
    mine = lg.packet(tid, use_cache=False)
    lg.close()
    r = cli(lp, "context", tid)
    assert r.returncode == 0, r.stderr
    other = json.loads(r.stdout)
    for k in ("items", "open_findings", "task"):
        assert other[k] == mine[k]
    texts = " | ".join(i["text"] for i in other["items"])
    for must in ("Deliver persistent task ids", "no new dependencies", "use SQLite WAL", "write migration",
                 "run the V3 import", "PASS @", head[:12]):
        assert must in texts
    assert "write docs" not in texts                     # a todo marked done is not 'remaining'
    assert other["open_findings"][0]["finding_id"] == "F-1"
    assert other["task"]["last_verified_commit"] == head


def test_ac10_handoff_from_ledger_only(lp, repo):
    lg = tl.Ledger(lp)
    tid, head = _rich_task(lg, repo)
    lg.close()
    r = cli(lp, "handoff", tid)
    assert r.returncode == 0, r.stderr
    h = json.loads(r.stdout)
    assert h["task_id"] == tid and h["status"] == "IN_REVIEW"
    assert h["last_verified_commit"] == {"commit": head, "exists": True, "on_branch": True}
    assert h["next_executable_action"].startswith("run the V3 import")
    assert [f["id"] for f in h["blocking_findings"]] == ["F-1"]
    assert h["remaining"] == ["write migration"] and "docs written" in h["completed"]
    md = (lp.parent / "handoffs" / f"{tid}.md").read_text(encoding="utf-8")
    assert tid in md and "run the V3 import" in md and "F-1" in md


# ------------------------------------------------------------------ AC-3 interruption

def test_ac3_interrupted_step_never_completes_and_resumes(lp, repo):
    lg = tl.Ledger(lp)
    tid = lg.create("crash", "o", DEV, worktree=str(repo))
    lg.transition(tid, "IN_PROGRESS", DEV)
    lg.close()
    p = py(f"""
        import os
        from scripts.dev_workflow.task_ledger import Ledger
        lg = Ledger(r"{lp}")
        lg.claim("{tid}", "{DEV}", ttl_s=0.3)
        print(lg.step_start("{tid}", "{DEV}", "edit files"), flush=True)
        os._exit(9)                                  # process dies mid-step
        """)
    out, err = p.communicate(timeout=60)
    assert p.returncode == 9 and out.strip() == "S1", err
    lg = tl.Ledger(lp)
    assert lg.recover() == []                         # claim still live: never interrupt a running session
    time.sleep(0.4)
    rec = lg.recover()
    assert rec and rec[0]["action"] == "INTERRUPTED" and rec[0]["steps"] == ["S1"]
    t = lg.get(tid)
    assert t["status"] == "INTERRUPTED" and t["resume_to"] == "IN_PROGRESS"
    with pytest.raises(tl.Refused):
        lg.step_end(tid, DEV, "S1", True)
    with pytest.raises(tl.Refused):
        lg.accept(tid, DEV)
    assert lg.recover() == []                         # idempotent
    lg.resume(tid, DEV, "checked worktree")
    assert lg.get(tid)["status"] == "IN_PROGRESS"
    h = lg.handoff(tid, write=False)
    assert h["interrupted_steps"] == ["S1 edit files"] and h["completed"] == []
    assert lg.verify() == []


def test_ac3_fencing_old_claim_cannot_close_step(lg, repo):
    tid = lg.create("fence", "o", DEV, worktree=str(repo))
    lg.transition(tid, "IN_PROGRESS", DEV)
    lg.claim(tid, DEV, ttl_s=0.2)
    sid = lg.step_start(tid, DEV, "work")
    time.sleep(0.3)
    lg.claim(tid, DEV, ttl_s=60)                      # lapsed claim re-taken -> new fencing token
    with pytest.raises(tl.Refused, match="token"):
        lg.step_end(tid, DEV, sid, True)


def test_ac3_worktree_drift_recorded(lg, repo):
    tid = lg.create("drift", "o", DEV, worktree=str(repo))
    _commit(repo, "x.txt", b"unexpected\n")
    (repo / "dirty.txt").write_bytes(b"d")
    rec = lg.recover()
    d = [r for r in rec if r["action"] == "WORKTREE_DRIFT"][0]
    assert d["actual_head"] != d["expected_head"] and "dirty.txt" in d["uncommitted"]
    assert lg.recover() == []                         # same drift is not re-recorded
    assert lg.handoff(tid, write=False)["worktree_drift"]


# ------------------------------------------------------------------ AC-4 concurrency

def test_ac4_concurrent_writers_keep_chains_intact(lp):
    lg = tl.Ledger(lp)
    shared = lg.create("shared", "o", DEV)
    lg.close()
    procs = [py(f"""
        from scripts.dev_workflow.task_ledger import Ledger
        lg = Ledger(r"{lp}")
        own = lg.create("own{n}", "o", "claude:w{n}")
        for i in range(30):
            lg.add_context("{shared}", "claude:w{n}", "note", "w{n} item %d" % i)
            lg.add_context(own, "claude:w{n}", "note", "own %d" % i)
        """) for n in range(6)]
    for p in procs:
        _, err = p.communicate(timeout=180)
        assert p.returncode == 0, err
    lg = tl.Ledger(lp)
    assert lg.verify() == []
    assert lg.get(shared)["version"] == 1 + 1 + 6 * 30     # CREATED + objective + notes
    seqs = [e["seq"] for e in lg.history(shared)]
    assert seqs == list(range(1, len(seqs) + 1))


def test_ac4_lease_contention_one_holder_no_deadlock(lp):
    tl.Ledger(lp).close()
    procs = [py(f"""
        import sys
        from scripts.dev_workflow.task_ledger import Ledger, Refused
        lg = Ledger(r"{lp}")
        res = ["worktree:A", "branch:B"] if {n} % 2 else ["branch:B", "worktree:A"]
        try:
            lg.acquire(None, "claude:c{n}", res, ttl_s=60)
            print("WON")
        except Refused as e:
            print("LOST")
        """) for n in range(8)]
    outs = []
    t0 = time.time()
    for p in procs:
        out, err = p.communicate(timeout=120)
        assert p.returncode == 0, err
        outs.append(out.strip())
    assert outs.count("WON") == 1 and outs.count("LOST") == 7
    assert time.time() - t0 < 100
    holders = {x["holder"] for x in tl.Ledger(lp).leases()}
    assert len(holders) == 1


def test_ac4_killed_writer_leaves_no_partial_record(lp):
    lg = tl.Ledger(lp)
    tid = lg.create("k", "o", DEV)
    v = lg.get(tid)["version"]
    lg.close()
    p = py(f"""
        import os
        from scripts.dev_workflow.task_ledger import Ledger
        lg = Ledger(r"{lp}")
        lg.db.execute("BEGIN IMMEDIATE")
        lg._append("{tid}", "PARTIAL", "{DEV}", {{"x": 1}})
        os._exit(9)                                   # dies before COMMIT
        """)
    p.communicate(timeout=60)
    lg = tl.Ledger(lp)
    assert lg.get(tid)["version"] == v and lg.verify() == []
    assert all(e["kind"] != "PARTIAL" for e in lg.history(tid))


def test_ac4_gpu_lease_belongs_to_gpu_lease_module(lg):
    with pytest.raises(tl.Refused, match="gpu_lease"):
        lg.acquire(None, DEV, ["gpu:0"])


def test_ac4_optimistic_version(lg):
    tid = lg.create("v", "o", DEV)
    with pytest.raises(tl.Refused, match="version"):
        lg.transition(tid, "IN_PROGRESS", DEV, expected_version=1)
    lg.transition(tid, "IN_PROGRESS", DEV, expected_version=lg.get(tid)["version"])


# ------------------------------------------------------------------ AC-5 cache invalidation

def test_ac5_cache_and_invalidation(lg, repo):
    tid = lg.create("cache", "o", DEV, worktree=str(repo))
    lg.add_context(tid, DEV, "evidence", "a.txt says one", path="a.txt")
    assert lg.packet(tid)["cache"] == "MISS"
    assert lg.packet(tid)["cache"] == "HIT"
    (repo / "a.txt").write_bytes(b"two\n")              # bound file changed
    p = lg.packet(tid)
    assert p["cache"] == "MISS" and p["stale"] and all("a.txt says" not in i["text"] for i in p["items"])
    (repo / "a.txt").write_bytes(b"one\n")
    assert lg.packet(tid)["stale"] == []
    lg.add_context(tid, DEV, "note", "new event")      # new event -> new version
    assert lg.packet(tid)["cache"] == "MISS"
    lg.packet(tid)
    _commit(repo, "c.txt", b"c")                       # new HEAD
    assert lg.packet(tid)["cache"] == "MISS"
    lg.add_context(tid, DEV, "evidence", "short-lived", ttl_s=0.2)
    assert any("short-lived" in i["text"] for i in lg.packet(tid)["items"])
    time.sleep(0.3)
    p = lg.packet(tid)
    assert p["cache"] == "MISS" and not any("short-lived" in i["text"] for i in p["items"])


def test_ac5_missing_commit_is_stale(lg, repo):
    tid = lg.create("gc", "o", DEV, worktree=str(repo))
    tmp = _commit(repo, "t.txt", b"temp\n")
    lg.add_context(tid, DEV, "evidence", "built at temp commit", commit=tmp)
    _git(repo, "reset", "-q", "--hard", "HEAD~1")
    _git(repo, "reflog", "expire", "--expire=now", "--all")
    _git(repo, "gc", "-q", "--prune=now")
    p = lg.packet(tid)
    assert any("no longer exists" in s["why"] for s in p["stale"])


def test_ac5_dedup_compression_supersession(lg):
    tid = lg.create("d", "o", DEV)
    a = lg.add_context(tid, DEV, "evidence", "same text")
    b = lg.add_context(tid, DEV, "evidence", "same text")
    assert b["deduplicated"] and a["id"] == b["id"]
    lg.add_context(tid, DEV, "decision", "old choice", key="k")
    lg.add_context(tid, DEV, "decision", "new choice", key="k")
    lg.add_context(tid, DEV, "evidence", "L" * 5000)
    p = lg.packet(tid, item_chars=100)
    texts = [i["text"] for i in p["items"]]
    assert "new choice" in texts and "old choice" not in texts
    long = [t for t in texts if t.startswith("LLLL")][0]
    assert len(long) < 200 and "context-get" in long
    sha = long.split("context-get ")[1].rstrip("]")
    assert lg.context_get(tid, sha)["text"] == "L" * 5000
    small = lg.packet(tid, budget=20)
    assert small["omitted"] > 0 and small["chars"] <= 20


def test_ac5_query_ranks_evidence(lg):
    tid = lg.create("q", "o", DEV)
    for i in range(10):
        lg.add_context(tid, DEV, "evidence", f"item {i} about topic{i}")
    p = lg.packet(tid, query="topic3", budget=60)
    ev = [i["text"] for i in p["items"] if i["kind"] == "evidence"]
    assert ev[0] == "item 3 about topic3"


# ------------------------------------------------------------------ AC-6 sensitive data

SECRETS = ["sk-ant-api03-" + "A" * 40, "ghp_" + "b" * 36, "AKIA" + "C" * 16, "hunter2-super-secret-pw",
           "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVmNHl0w5N_XgL0n3I9PlFUP0THsR8U"]


def test_ac6_secrets_never_reach_records(lp, repo, tmp_path):
    lg = tl.Ledger(lp)
    tid = lg.create(f"task with {SECRETS[0]}", f"objective token={SECRETS[1]}", DEV, worktree=str(repo))
    lg.add_context(tid, DEV, "evidence", f"aws {SECRETS[2]} and password: {SECRETS[3]}")
    lg.add_context(tid, DEV, "note", f"Authorization: Bearer {SECRETS[4]}")
    lg.add_context(tid, DEV, "note", "-----BEGIN RSA PRIVATE KEY-----\nMIIabc\n-----END RSA PRIVATE KEY-----")
    lg.add_context(tid, DEV, "note", "clone https://user:pa55word@example.invalid/x.git")
    head = ready_for_review(lg, repo, tid)
    rf = review_file(tmp_path, head, "ACCEPT WITH FINDINGS",
                     [{"id": "R1-01", "severity": "LOW", "title": f"leaked {SECRETS[1]}"}])
    lg.record_review(tid, REV, head, str(rf))
    lg.handoff(tid)
    (repo / ".env").write_bytes(b"API_KEY=x\n")
    with pytest.raises(tl.Refused, match="secret"):
        lg.add_context(tid, DEV, "evidence", "env", path=".env")
    lg.close()
    blob = b"".join(f.read_bytes() for f in lp.parent.rglob("*") if f.is_file())
    for s in SECRETS + ["MIIabc", "pa55word"]:
        assert s.encode() not in blob, s
    assert b"[REDACTED:" in blob


# ------------------------------------------------------------------ AC-8 independent subagent acceptance

def test_ac8_subagent_accept_on_exact_head(lg, repo, tmp_path):
    tid = lg.create("acc", "o", DEV, worktree=str(repo))
    head = ready_for_review(lg, repo, tid)
    r = lg.record_review(tid, REV, head, str(review_file(tmp_path, head)), mechanism="fresh read-only subagent")
    assert r["verdict"] == "ACCEPT" and r["independent"]
    ev = lg.accept(tid, DEV)
    assert ev["data"]["reviewer"] == REV and lg.get(tid)["accepted_commit"] == head
    new = _commit(repo, "after.txt", b"more\n")
    lg.set_head(tid, DEV, new)                         # new code -> acceptance invalidated
    t = lg.get(tid)
    assert t["status"] == "IN_REVIEW" and t["accepted_commit"] is None
    with pytest.raises(tl.Refused, match="no review of the exact head"):
        lg.accept(tid, DEV)


def test_ac8_refusals(lg, repo, tmp_path):
    tid = lg.create("ref", "o", DEV, worktree=str(repo))
    head = ready_for_review(lg, repo, tid)
    # implementer reviewing own work
    lg.set_head(tid, "codex:impl2", head)
    r = lg.record_review(tid, "codex:impl2", head, str(review_file(tmp_path, head, name="own.txt")))
    assert r["verdict"] == "ACCEPT" and not r["independent"]
    with pytest.raises(tl.Refused, match="not independent"):
        lg.accept(tid, DEV)
    # wrong commit named in the result
    r = lg.record_review(tid, REV, head, str(review_file(tmp_path, "0" * 40, name="wrong.txt")))
    assert r["verdict"] is None and "names candidate" in r["problem"]
    # non-reviewer actor kinds
    with pytest.raises(tl.Refused):
        lg.record_review(tid, "antigravity:ag", head, str(review_file(tmp_path, head, name="ag.txt")))
    # REJECT -> REPAIR with blocking finding; fix + re-review
    r = lg.record_review(tid, REV, head, str(review_file(tmp_path, head, "REJECT",
                         [{"id": "R2-01", "severity": "HIGH", "title": "bug"}], name="rej.txt")))
    assert r["verdict"] == "REJECT" and lg.get(tid)["status"] == "REPAIR"
    fix = _commit(repo, "fix.txt", b"fix\n")
    lg.set_head(tid, DEV, fix)
    lg.transition(tid, "IN_REVIEW", DEV)
    r = lg.record_review(tid, REV, fix, str(review_file(tmp_path, fix, "ACCEPT", name="ok.txt")))
    with pytest.raises(tl.Refused, match="open blocking"):
        lg.accept(tid, DEV)                            # reviewer did not confirm R2-01, developer did not close it
    lg.record_review(tid, "subagent:reviewer-2", fix, str(review_file(
        tmp_path, fix, "ACCEPT", prior=[{"id": "R2-01", "status": "FIXED"}], name="ok2.txt")))
    lg.accept(tid, DEV)
    assert lg.get(tid)["status"] == "ACCEPTED"
    with pytest.raises(tl.Refused):
        lg.transition(tid, "ACCEPTED", DEV)
    assert lg.verify() == []


def test_ac8_integrated_needs_ancestry_and_receipt(lg, repo, tmp_path):
    tid = lg.create("int", "o", DEV, worktree=str(repo))
    head = ready_for_review(lg, repo, tid)
    lg.record_review(tid, REV, head, str(review_file(tmp_path, head)))
    lg.accept(tid, DEV)
    receipt = tmp_path / "RECEIPT.md"
    receipt.write_text("integrated other", encoding="utf-8")
    with pytest.raises(tl.Refused, match="receipt"):
        lg.mark_integrated(tid, DEV, "main", str(receipt))
    receipt.write_text(f"integrated {head}", encoding="utf-8")
    with pytest.raises(tl.Refused, match="ancestor"):
        lg.mark_integrated(tid, DEV, "HEAD~1", str(receipt))
    lg.mark_integrated(tid, DEV, "main", str(receipt))
    assert lg.get(tid)["status"] == "INTEGRATED"


# ------------------------------------------------------------------ AC-7 Lifecycle V3 reviews and migration

def _v3_run(root, name, candidate, rounds):
    """A V3 run written with the real V3 State/event code: rounds = [(independent, imported, tamper)]."""
    sd = root / name / "state"
    st = State({"state_dir": str(sd), "milestone": name})
    st.d["candidate"] = candidate
    st.event("PLAN", baseline="b" * 40)
    for i, (indep, imported, tamper) in enumerate(rounds, 1):
        rec = {"round": i, "candidate": candidate, "independent": indep, "effective_verdict": "ACCEPT",
               "status": "COMPLETED_WITH_RESULT"}
        h = write_json(sd / "rounds" / f"R{i}" / "round.json", rec)
        st.event("REVIEW_RECORDED", round=i, candidate=candidate, independent=indep, imported=imported,
                 status="COMPLETED_WITH_RESULT", verdict="ACCEPT", round_sha256=h, stdout_sha256="",
                 worker={"provider": "codex_cli"})
        if tamper:
            (sd / "rounds" / f"R{i}" / "round.json").write_text("{}", encoding="utf-8")
    st.d["stage"] = "VERIFIED"
    st.save()
    return sd


def test_ac7_v3_import_verified_and_unchanged(lg, repo, tmp_path):
    head = _git(repo, "rev-parse", "HEAD")
    root = tmp_path / "lifecycle"
    _v3_run(root, "DEMO-MS-r1", head, [(False, True, False), (True, False, True)])
    _v3_run(root, "DEMO-MS-r2", head, [(True, False, False)])
    rep = lg.import_v3(str(root))
    assert rep["source_unchanged"] and rep["source_files"] > 0
    assert len(rep["tasks"]) == 1                       # revisions share one persistent task identity
    tid = next(iter(rep["tasks"]))
    provs = sorted(r["provenance"] for run in rep["runs"] for r in run["reviews"])
    assert provs == ["DRIVER_VERIFIED", "V3_UNVERIFIED", "V3_UNVERIFIED"]
    again = lg.import_v3(str(root))                      # idempotent
    assert all(run["reviews"] == [] for run in again["runs"]) and again["source_unchanged"]
    # a DRIVER_VERIFIED V3 review accepts the task on its exact commit
    lg.db.execute("UPDATE tasks SET worktree=? WHERE task_id=?", (str(repo), tid))
    lg.transition(tid, "IN_PROGRESS", DEV)
    lg.set_head(tid, DEV, head)
    lg.transition(tid, "IN_REVIEW", DEV)
    assert lg.accept(tid, DEV)["data"]["provenance"] == "DRIVER_VERIFIED"
    assert lg.verify() == []


def test_ac7_broken_v3_chain_imports_nothing(lg, tmp_path):
    root = tmp_path / "lc"
    sd = _v3_run(root, "BROKEN", "c" * 40, [(True, False, False)])
    lines = (sd / "events.jsonl").read_text(encoding="utf-8").splitlines()
    ev = json.loads(lines[1])
    ev["data"]["independent"] = True
    ev["data"]["verdict"] = "ACCEPT"
    ev["ts"] = "2000-01-01T00:00:00Z"
    lines[1] = json.dumps(ev, sort_keys=True)
    (sd / "events.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8")
    rep = lg.import_v3(str(root))
    assert rep["runs"][0]["reviews"][0]["error"].startswith("V3 chain broken")


# ------------------------------------------------------------------ AC-11 development pause

def test_ac11_pause_policy(lg, repo):
    tid = lg.create("p", "o", DEV, worktree=str(repo))
    lg.transition(tid, "IN_PROGRESS", DEV)
    lg.claim(tid, DEV)
    lg.step_start(tid, DEV, "half done")
    assert lg.set_availability("codex:cx", "codex", False, "weekly quota") == []
    paused = lg.set_availability(DEV, "claude", False, "quota exhausted")
    assert paused == [tid] and lg.development_paused()
    t = lg.get(tid)
    assert t["status"] == "PAUSED" and t["resume_to"] == "IN_PROGRESS"
    for actor in ("antigravity:ag", "subagent:s1"):
        with pytest.raises(tl.Refused):
            lg.resume(tid, actor)
        with pytest.raises(tl.Refused):
            lg.transition(tid, "IN_REVIEW", actor)
        with pytest.raises(tl.Refused):
            lg.set_availability(actor, "claude", True)
    with pytest.raises(tl.Refused, match="DEVELOPMENT_PAUSED"):
        lg.create("new", "o", DEV)
    lg.add_context(tid, "antigravity:ag", "evidence", "preserved log path")   # evidence preservation allowed
    with pytest.raises(tl.Refused, match="unavailable"):
        lg.resume(tid, DEV)
    with pytest.raises(tl.Refused):
        lg.set_availability("codex:cx", "claude", True)   # one developer cannot vouch for the other
    lg.set_availability(DEV, "claude", True, "quota reset")
    lg.resume(tid, DEV, "back")
    assert lg.get(tid)["status"] == "IN_PROGRESS"
    assert lg.handoff(tid, write=False)["interrupted_steps"] == ["S1 half done"]


# ------------------------------------------------------------------ Milestone Manager contract, recovery hygiene

def test_mm_summary_contract_and_integrity_exit(lp, repo):
    lg = tl.Ledger(lp)
    tid = lg.create("mm", "o", DEV, milestone_ref="LIFECYCLE-V3-1", worktree=str(repo))
    lg.create("other", "o", DEV, milestone_ref="MILESTONE-MANAGER")
    lg.close()
    r = cli(lp, "summary", "--milestone", "LIFECYCLE-V3-1", "--json")
    assert r.returncode == 0, r.stderr
    rows = json.loads(r.stdout)
    schema = json.loads((ROOT / "docs/dev_workflow/contracts/task_ledger_contract.json").read_text(encoding="utf-8"))
    assert len(rows) == 1 and rows[0]["task_id"] == tid
    for k in schema["required"]:
        assert k in rows[0]
    db = sqlite3.connect(str(lp))
    db.execute("UPDATE events SET data='{}' WHERE task_id=? AND seq=1", (tid,))
    db.commit()
    db.close()
    r = cli(lp, "summary", "--milestone", "LIFECYCLE-V3-1", "--json")
    assert r.returncode == 4 and "LEDGER_INTEGRITY_FAILED" in r.stderr and r.stdout == ""


def test_stray_partial_handoff_cleaned(lp, repo):
    lg = tl.Ledger(lp)
    tid = lg.create("h", "o", DEV)
    lg.handoff(tid)
    lg.close()
    stray = lp.parent / "handoffs" / f"{tid}.json.999.tmp"
    stray.write_bytes(b'{"half')
    tl.Ledger(lp).close()
    assert not stray.exists()
    assert json.loads((lp.parent / "handoffs" / f"{tid}.json").read_text(encoding="utf-8"))["task_id"] == tid


def test_actor_and_transition_rules(lg):
    tid = lg.create("r", "o", DEV)
    with pytest.raises(tl.Refused):
        lg.transition(tid, "IN_PROGRESS", "nobody")
    with pytest.raises(tl.Refused):
        lg.transition(tid, "IN_REVIEW", DEV)            # OPEN -> IN_REVIEW not allowed
    with pytest.raises(tl.Refused):
        lg.step_start(tid, DEV, "x")                     # not active
    lg.transition(tid, "IN_PROGRESS", DEV)
    with pytest.raises(tl.Refused, match="claim"):
        lg.step_start(tid, DEV, "x")                     # steps need a live claim
    lg.block(tid, DEV, "needs owner", "owner decision")
    lg.unblock(tid, "owner:chetan", "decided")
    assert lg.get(tid)["status"] == "IN_PROGRESS"


# ------------------------------------------------------------------ AC-12 performance smoke

def test_ac12_bench_runs_without_gpu():
    b = tl.bench(60)
    assert b["gpu"] == "none used" and b["packet_cache"] == ["MISS", "HIT"]
    assert b["ledger_append_ms_per_event"] > 0 and b["v3_append_ms_per_event"] > 0
