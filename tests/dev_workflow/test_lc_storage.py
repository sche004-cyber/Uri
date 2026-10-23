"""LIFECYCLE-V3.1-STORAGE acceptance tests (docs/dev_workflow/LIFECYCLE_V3_1_STORAGE_PLAN_AND_ACCEPTANCE.md §3).

TS-* supervised test runs (scripts/dev_workflow/testrun.py), DM-* development memory (devmemory.py), HK-*
housekeeping and evidence archives (housekeeping.py). Everything runs in tmp_path sandboxes; nothing touches the
real ledger, runs directory or repository."""
import hashlib
import json
import os
import sqlite3
import subprocess
import sys
import textwrap
import time
import zipfile
from pathlib import Path

import pytest

from scripts.dev_workflow import devmemory as dm
from scripts.dev_workflow import housekeeping as hk
from scripts.dev_workflow import task_ledger as tl
from scripts.dev_workflow import testrun as tr

ROOT = Path(__file__).resolve().parents[2]
DEV = "claude:lc-storage-test"
CANON = "refs/remotes/uri-repo/integration/git-sync-20261008"
PY = sys.executable


def _git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


def _init(r: Path) -> Path:
    r.mkdir(parents=True)
    _git(r, "init", "-q", "-b", "main")
    _git(r, "config", "user.email", "t@example.invalid")
    _git(r, "config", "user.name", "t")
    _git(r, "config", "core.autocrlf", "false")
    (r / "a.txt").write_bytes(b"one\n")
    _git(r, "add", ".")
    _git(r, "commit", "-q", "-m", "c1")
    return r


def _commit(repo, name, data):
    p = Path(repo) / name
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    _git(repo, "add", ".")
    _git(repo, "commit", "-q", "-m", name)
    return _git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    return _init(tmp_path / "repo")


@pytest.fixture
def runs(tmp_path):
    return tmp_path / "runs"


def cli(module, *args, env=None, timeout=120):
    e = {**os.environ, **(env or {})}
    return subprocess.run([PY, "-m", f"scripts.dev_workflow.{module}", *args], capture_output=True, text=True,
                          cwd=ROOT, env=e, timeout=timeout)


def pyc(code: str) -> list[str]:
    return [PY, "-c", textwrap.dedent(code)]


# =========================================================================== TS: supervised test runs

def test_ts1_exit_status_is_the_completion_signal(runs, repo):
    ok = tr.start(pyc("print('ok')"), name="ok", timeout_s=60, cwd=str(repo), root=runs)
    bad = tr.start(pyc("import sys; print('x'); sys.exit(3)"), name="bad", timeout_s=60, cwd=str(repo), root=runs)
    crash = tr.start(pyc("raise RuntimeError('boom')"), name="crash", timeout_s=60, cwd=str(repo), root=runs)
    assert (ok["state"], ok["exit_code"]) == ("COMPLETED", 0)
    assert (bad["state"], bad["exit_code"]) == ("FAILED", 3)
    assert crash["state"] == "FAILED" and crash["exit_code"] != 0
    for rec in (ok, bad, crash):
        stored = json.loads((runs / rec["id"] / "run.json").read_text(encoding="utf-8"))
        assert stored["final"] is True and stored["state"] == rec["state"]
        assert hashlib.sha256(Path(stored["log"]).read_bytes()).hexdigest() == stored["log_sha256"]
    assert "RuntimeError: boom" in Path(crash["log"]).read_text(encoding="utf-8")
    assert tr.exit_code_for(bad) == 3


def test_ts1_launch_failure_is_failed_not_running(runs, repo):
    rec = tr.start(["definitely-not-a-command-xyz"], name="nolaunch", timeout_s=30, cwd=str(repo), root=runs)
    assert rec["state"] == "FAILED" and rec["final"] and rec["launch_error"]
    assert tr.exit_code_for(rec) == 127


def test_r2_04_test_command_secrets_are_redacted_but_identity_uses_raw_args(runs, repo, capsys):
    key = "sk-" + "A" * 24
    argv = pyc("pass") + ["password=hunter2", key, "--token", "separated-secret"]
    rec = tr.start(argv, name="secret", timeout_s=30, cwd=str(repo), root=runs)
    stored = (runs / rec["id"] / "run.json").read_text(encoding="utf-8")
    shown = json.dumps(rec) + json.dumps(tr.status(runs, rec["id"])) + json.dumps(tr.all_runs(runs))
    assert all(secret not in stored + shown for secret in ("hunter2", key, "separated-secret"))
    assert "[REDACTED:" in stored and "[REDACTED:" in shown
    assert tr.reuse_key(argv, tr.tree_state(repo)) != tr.reuse_key(
        pyc("pass") + ["password=othersecret", key], tr.tree_state(repo))
    tr.main(["--runs", str(runs), "status", rec["id"]])
    printed = capsys.readouterr().out
    assert all(secret not in printed for secret in ("hunter2", key, "separated-secret"))


def test_r3_02_separated_secret_flags_stay_out_of_records_and_cli(runs, repo, capsys):
    argv = pyc("pass") + ["--api_key", "hunter2", "--client-secret", "othersecret",
                           "--access-token", "thirdsecret"]
    tr.main(["--runs", str(runs), "start", "--name", "redacted", "--timeout", "30",
             "--cwd", str(repo), "--", *argv])
    start_output = capsys.readouterr().out
    rec = next(iter(tr.all_runs(runs)))
    stored = (runs / rec["id"] / "run.json").read_text(encoding="utf-8")
    tr.main(["--runs", str(runs), "status", rec["id"]])
    tr.main(["--runs", str(runs), "list"])
    output = start_output + capsys.readouterr().out + stored + json.dumps(rec)
    assert all(s not in output for s in ("hunter2", "othersecret", "thirdsecret"))
    assert output.count("[REDACTED:") >= 3


def test_r3_03_rewritten_then_restored_source_cannot_be_reused(runs, repo):
    source = repo / "a.txt"
    code = ("import os; from pathlib import Path; "
            f"p=Path({str(source)!r}); p.write_bytes(b'changed'); "
            "p.write_bytes(b'one\\n'); "
            "os.utime(p, ns=(2_000_000_000_000_000_000, 2_000_000_000_000_000_000))")
    argv = pyc(code)
    first = tr.start(argv, name="transient", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert first["state"] == "COMPLETED" and not first.get("reuse_key")
    assert tr.tree_state(repo)["dirty"] is False
    second = tr.start(argv, name="transient", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert second["state"] == "COMPLETED" and second["id"] != first["id"]


def test_r3_03_legacy_run_without_final_source_evidence_is_not_reused(runs, repo):
    argv = pyc("print('ok')")
    first = tr.start(argv, name="legacy", timeout_s=30, cwd=str(repo), root=runs)
    path = runs / first["id"] / "run.json"
    stored = json.loads(path.read_text(encoding="utf-8"))
    stored.pop("source_stable", None)
    path.write_text(json.dumps(stored), encoding="utf-8")
    second = tr.start(argv, name="legacy", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert second["state"] == "COMPLETED" and second["id"] != first["id"]


@pytest.mark.parametrize("assigned", [False, True])
def test_r3_04_uncontained_windows_run_is_never_certified(runs, repo, monkeypatch, assigned):
    from scripts.dev_workflow import containment

    def uncontained_spawn(argv, **kw):
        proc = subprocess.Popen(argv, **kw)
        if assigned:
            proc._uri_job = object()
        return proc

    monkeypatch.setattr(containment, "WINDOWS", True)
    monkeypatch.setattr(containment, "spawn", uncontained_spawn)
    monkeypatch.setattr(containment, "kill_tree", lambda proc: proc.kill() if proc.poll() is None else None)
    monkeypatch.setattr(containment, "finish", lambda proc: {"contained": False, "reason": "no job object"})
    rec = tr.start(pyc("print('ran')"), name="uncontained", timeout_s=30, cwd=str(repo), root=runs)
    saved = json.loads((runs / rec["id"] / "run.json").read_text(encoding="utf-8"))
    assert rec["state"] == saved["state"] == "CONTAINMENT_FAILED"
    assert rec["final"] and rec["contained"]["contained"] is False and tr.exit_code_for(rec) == 126


def test_ts2_timeout_kills_the_whole_tree(runs, repo, tmp_path):
    pidf = tmp_path / "grandchild.pid"
    code = f"""
        import subprocess, sys, time
        g = subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(120)'])
        open(r'{pidf}', 'w').write(str(g.pid))
        time.sleep(120)
    """
    t0 = time.monotonic()
    rec = tr.start(pyc(code), name="slow", timeout_s=3, cwd=str(repo), root=runs)
    assert rec["state"] == "TIMED_OUT" and time.monotonic() - t0 < 60
    assert tr.exit_code_for(rec) == 124
    gpid = int(pidf.read_text())
    time.sleep(0.5)
    assert tr._proc_ctime(gpid) is None, "grandchild survived the timeout kill"


def test_ts3_stall_detected_and_killed(runs, repo):
    rec = tr.start(pyc("import time; print('started', flush=True); time.sleep(120)"), name="stall", timeout_s=90,
                   stall_s=2, kill_on_stall=True, cwd=str(repo), root=runs, heartbeat_s=0.5)
    assert rec["state"] == "STALLED_KILLED" and rec["duration_s"] < 60
    assert tr.exit_code_for(rec) == 125


def test_ts3_status_reports_stalled_while_alive(runs, repo):
    p = subprocess.Popen([PY, "-m", "scripts.dev_workflow.testrun", "--runs", str(runs), "start", "--name", "quiet",
                          "--timeout", "60", "--stall", "1", "--cwd", str(repo), "--lock", "none", "--",
                          *pyc("import time; time.sleep(20)")], cwd=ROOT, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE)
    try:
        st = {}
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            st = tr.status(runs, "quiet")
            if st["state"] == "STALLED":
                break
            time.sleep(0.5)
        assert st["state"] == "STALLED", st
    finally:
        p.kill()
        p.wait()


def test_ts4_missing_marker_when_supervisor_dies(runs, repo):
    p = subprocess.Popen([PY, "-m", "scripts.dev_workflow.testrun", "--runs", str(runs), "start", "--name", "orphan",
                          "--timeout", "120", "--cwd", str(repo), "--lock", "none", "--",
                          *pyc("import time; time.sleep(60)")], cwd=ROOT)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and tr.status(runs, "orphan")["state"] != "RUNNING":
            time.sleep(0.2)
        assert tr.status(runs, "orphan")["state"] == "RUNNING"
    finally:
        p.kill()            # the supervisor dies without writing its final record
        p.wait()
    st = tr.status(runs, "orphan")
    assert st["state"] == "MISSING_MARKER", st
    w = tr.wait(runs, st["id"], timeout_s=5)
    assert w["state"] == "MISSING_MARKER"


def test_ts4_reused_pid_is_not_alive(runs):
    me = os.getpid()
    assert tr._alive(me, tr._proc_ctime(me))
    assert not tr._alive(me, tr._proc_ctime(me) - 1000.0)     # same pid, different creation time


def test_ts5_wait_is_bound_to_run_id_not_log_text(runs, repo):
    t0 = time.monotonic()
    assert tr.wait(runs, "no-such-run", timeout_s=30)["state"] == "NOT_FOUND"
    assert time.monotonic() - t0 < 5
    # Watcher-incident regression: the command's log never contains any 'rc=' marker; wait still completes.
    done = tr.start(pyc("print('no marker here')"), name="nomarker", timeout_s=30, cwd=str(repo), root=runs)
    w = tr.wait(runs, done["id"], timeout_s=30)
    assert w["state"] == "COMPLETED" and "rc=" not in Path(done["log"]).read_text(encoding="utf-8")
    p = subprocess.Popen([PY, "-m", "scripts.dev_workflow.testrun", "--runs", str(runs), "start", "--name",
                          "long", "--timeout", "60", "--cwd", str(repo), "--lock", "none", "--",
                          *pyc("import time; time.sleep(30)")], cwd=ROOT)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and tr.status(runs, "long")["state"] != "RUNNING":
            time.sleep(0.2)
        t0 = time.monotonic()
        w = tr.wait(runs, tr.status(runs, "long")["id"], timeout_s=1.5, poll_s=0.2)
        assert w["state"] == "WAIT_TIMEOUT" and w["run_state"] == "RUNNING"
        assert time.monotonic() - t0 < 10
    finally:
        p.kill()
        p.wait()
    with pytest.raises(tr.RunError):
        tr.wait(runs, "long", timeout_s=0)


def test_r1_08_wait_never_resolves_a_run_name(runs, repo):
    first = tr.start(pyc("print('first')"), name="repeat", timeout_s=30, cwd=str(repo), root=runs)
    second = tr.start(pyc("print('second')"), name="repeat", timeout_s=30, cwd=str(repo), root=runs)
    assert first["id"] != second["id"]
    assert tr.wait(runs, first["id"], 5)["id"] == first["id"]
    assert tr.wait(runs, "repeat", 5)["state"] == "NOT_FOUND"


def test_ts6_duplicate_run_refused_and_lock_released_after_kill(runs, repo):
    args = ["--runs", str(runs), "start", "--name", "dup", "--timeout", "60", "--cwd", str(repo), "--"]
    cmd = pyc("import time; time.sleep(30)")
    p = subprocess.Popen([PY, "-m", "scripts.dev_workflow.testrun", *args, *cmd], cwd=ROOT)
    try:
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and tr.status(runs, "dup")["state"] != "RUNNING":
            time.sleep(0.2)
        first = tr.status(runs, "dup")["id"]
        second = cli("testrun", *args, *cmd)
        assert second.returncode == tr.EXIT["DUPLICATE_RUN"], second.stdout + second.stderr
        out = json.loads(second.stdout)
        assert out["state"] == "DUPLICATE_RUN" and out["active_runs"] == [first]
    finally:
        p.kill()            # holder dies: the OS releases the lock
        p.wait()
    third = tr.start(pyc("print(1)"), name="dup", timeout_s=30, cwd=str(repo), root=runs)
    assert third["state"] == "COMPLETED"
    # same command, different lock class: a class lock serialises different commands too
    assert tr.lock_name("phase1", ["a"], repo) == tr.lock_name("phase1", ["b"], repo)
    assert tr.lock_name("auto", ["a"], repo) != tr.lock_name("auto", ["b"], repo)


def test_ts7_reuse_only_for_identical_clean_tree(runs, repo):
    marker = repo.parent / "executions.txt"
    cmd = pyc(f"open(r'{marker}', 'a').write('x'); print('ran')")
    first = tr.start(cmd, name="r", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert first["state"] == "COMPLETED"
    second = tr.start(cmd, name="r", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert second["state"] == "REUSED" and second["reused_from"] == first["id"] and second["exit_code"] == 0
    assert marker.read_text() == "x"                                   # not executed again
    (repo / "untracked.txt").write_text("dirty")                       # dirty tree: never reused
    assert tr.start(cmd, name="r", timeout_s=30, cwd=str(repo), root=runs, reuse=True)["state"] == "COMPLETED"
    (repo / "untracked.txt").unlink()
    _commit(repo, "b.txt", b"two\n")                                   # new tree id: not reused
    third = tr.start(cmd, name="r", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert third["state"] == "COMPLETED"
    other = pyc(f"open(r'{marker}', 'a').write('y')")                  # different argv: not reused
    assert tr.start(other, name="r", timeout_s=30, cwd=str(repo), root=runs, reuse=True)["state"] == "COMPLETED"
    Path(third["log"]).write_text("tampered")                          # log no longer matches: not reused
    assert tr.start(cmd, name="r", timeout_s=30, cwd=str(repo), root=runs, reuse=True)["state"] == "COMPLETED"
    failing = pyc("import sys; sys.exit(2)")                           # a failure is reused as a failure
    tr.start(failing, name="f", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    again = tr.start(failing, name="f", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert again["state"] == "REUSED" and again["reused_state"] == "FAILED" and tr.exit_code_for(again) == 2


def test_r1_04_reuse_is_bound_to_repository_and_complete_environment(runs, repo, tmp_path, monkeypatch):
    other = _init(tmp_path / "other")
    assert tr.tree_state(repo)["tree"] == tr.tree_state(other)["tree"]
    marker = tmp_path / "executions.txt"
    cmd = pyc(f"open(r'{marker}', 'a').write('x')")
    first = tr.start(cmd, name="isolate", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    second = tr.start(cmd, name="isolate", timeout_s=30, cwd=str(other), root=runs, reuse=True)
    assert second["state"] == "COMPLETED" and second["id"] != first["id"]
    monkeypatch.setenv("URI_TEST_REUSE_CONTEXT", "different")
    third = tr.start(cmd, name="isolate", timeout_s=30, cwd=str(repo), root=runs, reuse=True)
    assert third["state"] == "COMPLETED" and marker.read_text() == "xxx"
    assert "different" not in (runs / third["id"] / "run.json").read_text()


def test_ts8_environmental_failure_labelled_exit_unchanged(runs, repo):
    rec = tr.start(pyc("import jsonschema_not_installed_xyz"), name="env", timeout_s=30, cwd=str(repo), root=runs)
    assert rec["state"] == "FAILED" and rec["exit_code"] == 1
    assert "ENV_MISSING_MODULE:jsonschema_not_installed_xyz" in rec["env_failures"]
    rec2 = tr.start(pyc("print('OSError: [Errno 28] No space left on device'); raise SystemExit(1)"), name="disk",
                    timeout_s=30, cwd=str(repo), root=runs)
    assert rec2["env_failures"] == ["ENV_DISK_FULL"]
    ok = tr.start(pyc("print(\"No module named 'x'\")"), name="ok", timeout_s=30, cwd=str(repo), root=runs)
    assert ok["state"] == "COMPLETED" and ok["env_failures"] == []


def test_ts9_result_recorded_in_ledger_only_for_clean_tree(runs, repo, tmp_path):
    lp = tmp_path / "ledger.sqlite3"
    lg = tl.Ledger(lp)
    tid = lg.create("t", "o", DEV, worktree=str(repo), branch="main")
    lg.transition(tid, "IN_PROGRESS", DEV)
    lg.close()
    rec = tr.start(pyc("print('5 passed')"), name="unit", timeout_s=30, cwd=str(repo), root=runs, task=tid,
                   actor=DEV, ledger=str(lp))
    assert rec["ledger"] == {"recorded": True, "task": tid}
    (repo / "dirty.txt").write_text("x")
    rec2 = tr.start(pyc("print(1)"), name="unit", timeout_s=30, cwd=str(repo), root=runs, task=tid, actor=DEV,
                    ledger=str(lp))
    assert rec2["ledger"]["recorded"] is False
    lg = tl.Ledger(lp)
    try:
        tests = lg.db.execute("SELECT text, commit_sha FROM context WHERE task_id=? AND kind='test'",
                              (tid,)).fetchall()
        assert len(tests) == 1 and tests[0]["commit_sha"] == _git(repo, "rev-parse", "HEAD")
        assert not lg.verify(tid)
    finally:
        lg.close()


def test_ts_select_is_advisory(repo):
    _commit(repo, "pkg/mod.py", b"X = 1\n")
    base = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "tests/test_mod.py", b"from pkg.mod import X\n")
    _commit(repo, "tests/test_other.py", b"import json\n")
    head0 = _git(repo, "rev-parse", "HEAD")
    _commit(repo, "pkg/mod.py", b"X = 2\n")
    _commit(repo, "README.md", b"doc\n")
    sel = tr.select_tests(repo, head0)
    assert sel["selected"] == ["tests/test_mod.py"] and sel["unmapped_changes"] == ["README.md"]
    assert "advisory" in sel["rule"]
    assert "tests/test_mod.py" in tr.select_tests(repo, base)["selected"]


# =========================================================================== DM: development memory

@pytest.fixture
def mem(tmp_path, repo):
    """A ledger with an active and an integrated task, a decisions register, a receipt and an index config."""
    lp = tmp_path / "ledger.sqlite3"
    _git(repo, "update-ref", CANON, "HEAD")
    lg = tl.Ledger(lp)
    active = lg.create("Storage milestone work", "make cleanup safe", DEV, milestone_ref="M-STORAGE",
                       worktree=str(repo), branch="main")
    lg.transition(active, "IN_PROGRESS", DEV)
    lg.add_context(active, DEV, "next_action", "run the housekeeping dry run on the sandbox")
    lg.add_context(active, DEV, "lesson", "background waits must match the producer's exact output file")
    lg.add_context(active, DEV, "failed_approach", "grep for rc= in a guessed log path never terminates")
    lg.add_context(active, DEV, "environment", "dwm.exe holds 1.7 GB of VRAM; GPU profile P3 does not fit")
    lg.add_context(active, DEV, "decision", "use the task ledger as the source of truth", path="a.txt")
    lg.add_context(active, DEV, "note", "password=hunter2 must never reach the index")
    with pytest.raises(tl.Refused):     # the ledger itself refuses secret-bearing paths at write time
        lg.add_context(active, DEV, "evidence", "token at secrets/.env", path=".env")
    lg.add_finding(active, DEV, "F-1", "HIGH", "journal recovery missing", True)
    lg.close()
    dec = tmp_path / "decisions.md"
    hdr = "| ID | Date | Title | Decision text | Reasoning (recorded) | Alternatives / rejected | Later corrections / " \
          "supersession | Scope & limits | Approval requirement | Related milestones | Applicability | Source(s) | " \
          "Evidence class |"
    rows = [
        "| DEC-001 | 2026-09-05 | Interaction loop | Brain composes replies; URI supplies context | split | - | - | all"
        " | - | all | ACTIVE | MEM x | MEMORY-ONLY |",
        "| DEC-003 | 2026-09-10 | AO-3 cycle | Claude plans, Gemma implements | - | - | renamed | dev | - | - | "
        "SUPERSEDED by DEC-004 | MEM y | REPO-RECORD (+MEM) |",
        "| DEC-041 | 2026-10-15 | Lifecycle reviewer | Codex is the primary independent auditor | quota | - | - | "
        "dev | - | LC | ACTIVE | CAN AGENTS.md | REPO-RECORD |",
        "| DEC-042 | 2026-10-15 | Duplicate row | Codex is the primary independent auditor | quota | - | - | "
        "dev | - | LC | ACTIVE | CAN AGENTS.md | REPO-RECORD |",
    ]
    opens = ["| OPEN-14 | Frozen exception for GRF-P0-1 | protected path | P0 closure |",
             "| OPEN-19 | **DONE 2026-10-22.** canonical push | permission | addendum G |"]
    dec.write_text("# decisions\n\n" + hdr + "\n|---|\n" + "\n".join(rows) + "\n\n## 3\n\n| Ref | Q | C | W |\n|---|\n"
                   + "\n".join(opens) + "\n", encoding="utf-8")
    rroot = tmp_path / "lifecycle"
    (rroot / "RUN-A" / "state").mkdir(parents=True)
    (rroot / "RUN-A" / "state" / "receipt.json").write_text(json.dumps(
        {"milestone": "RUN-A", "stage": "COMPLETE", "candidate": _git(repo, "rev-parse", "HEAD"), "baseline": "x",
         "rounds": 2, "evidence_ok_for_candidate": True, "integration": {"status": "INTEGRATED"},
         "written_at": "2026-10-22T00:00:00Z"}), encoding="utf-8")
    ix = dm.Index(tmp_path / "devmemory.sqlite3")
    cfg = {"ledger": str(lp), "decisions": [str(dec)], "receipts_roots": [str(rroot)], "repo": str(repo),
           "canonical_ref": CANON, "archive_indexes": []}
    yield {"ix": ix, "cfg": cfg, "lp": lp, "active": active, "dec": dec, "repo": repo, "rroot": rroot,
           "tmp": tmp_path}
    ix.close()


def test_dm1_refresh_with_provenance_and_incremental(mem):
    ix = mem["ix"]
    r1 = dm.refresh(ix, mem["cfg"])
    assert all(v.startswith("rebuilt") for v in r1["sources"].values()), r1
    rows = {r["ref"]: dict(r) for r in ix.db.execute("SELECT * FROM items")}
    assert any(r["source"] == "ledger" and r["confidence"] == "VERIFIED" for r in rows.values())
    dec1 = next(r for k, r in rows.items() if k.startswith("DEC-001@"))
    assert dec1["confidence"] == "REPORTED" and dec1["source"].startswith("decisions:")
    assert next(r for k, r in rows.items() if k.startswith("DEC-041@"))["confidence"] == "RECORDED"
    rec = next(r for r in rows.values() if r["kind"] == "receipt")
    assert rec["confidence"] == "VERIFIED" and rec["integrated"] == 1
    r2 = dm.refresh(ix)
    assert set(r2["sources"].values()) == {"unchanged"}


def test_r2_03_refresh_does_not_create_a_missing_source_ledger(tmp_path, repo):
    missing = tmp_path / "absent" / "ledger.sqlite3"
    ix = dm.Index(tmp_path / "index.sqlite3")
    try:
        report = dm.refresh(ix, {"ledger": str(missing), "repo": str(repo), "decisions": [],
                                 "receipts_roots": [], "archive_indexes": []})
        assert report["sources"]["ledger"].startswith("ERROR ")
        assert not missing.exists() and not missing.parent.exists()
    finally:
        ix.close()


def test_r2_03_refresh_does_not_migrate_an_existing_ledger(mem):
    lp = mem["lp"]
    with sqlite3.connect(lp) as db:
        db.execute("DELETE FROM events WHERE kind='SEAL'")
    before = lp.read_bytes()
    dm.refresh(mem["ix"], mem["cfg"])
    assert lp.read_bytes() == before
    with sqlite3.connect(lp) as db:
        assert db.execute("SELECT count(*) FROM events WHERE kind='SEAL'").fetchone()[0] == 0


def test_dm2_brief_budget_and_content(mem):
    ix = mem["ix"]
    dm.refresh(ix, mem["cfg"])
    b = dm.brief(ix, budget_tokens=1200)
    assert b["tokens"] <= 1200
    t = b["text"]
    assert mem["active"] in t and "run the housekeeping dry run" in t
    assert "OPEN-14" in t and "OPEN-19" not in t                         # closed open-decision row is cold
    assert "producer's exact output file" in t and "dwm.exe" in t
    assert "DEC-003" not in t                                           # superseded / warm items not in the brief
    small = dm.brief(ix, budget_tokens=60)
    assert small["tokens"] <= 60 and small["omitted"] > 0
    assert "omitted" in small["text"]
    assert dm.brief(ix, budget_tokens=1)["tokens"] <= 1


def test_dm4_open_question_citing_integrated_commit_is_flagged(mem):
    ix, repo = mem["ix"], mem["repo"]
    head = _git(repo, "rev-parse", "HEAD")
    with mem["dec"].open("a", encoding="utf-8") as f:
        f.write(f"| OPEN-21 | Integrate follow-up `{head[:8]}` | x | y |\n")
    dm.refresh(ix, mem["cfg"])
    t = dm.brief(ix, 2000)["text"]
    line21 = next(x for x in t.splitlines() if x.startswith("- OPEN-21"))
    line14 = next(x for x in t.splitlines() if x.startswith("- OPEN-14"))
    assert "possibly resolved" in line21 and "possibly resolved" not in line14
    assert t.index("- OPEN-14") < t.index("- OPEN-21")                  # flagged items are listed last


def test_dm_cli_output_is_utf8(mem):
    mem["dec"].write_text(mem["dec"].read_text(encoding="utf-8").replace("P0 closure", "P0 closure §N"),
                          encoding="utf-8")
    dm.refresh(mem["ix"], mem["cfg"])
    r = subprocess.run([PY, "-m", "scripts.dev_workflow.devmemory", "--index", str(mem["ix"].path), "brief",
                        "--no-refresh"], capture_output=True, cwd=ROOT)
    assert r.returncode == 0 and "§N".encode("utf-8") in r.stdout


def test_dm3_recall_precision(mem):
    ix = mem["ix"]
    lg = tl.Ledger(mem["lp"])
    try:
        facts = {
            "vram": "Brain profile P2 needs 14 GiB VRAM and cannot run beside dwm with the frozen profile",
            "tamper": "git info refs digest caused false TAMPER blocks; fixed by git-control v2",
            "jsonschema": "PH1-GATE-1 Phase 1 suite uncollectable because jsonschema is undeclared",
            "playwright": "assist render tests need node playwright which is absent on this host",
            "quota": "Codex weekly quota ran out twice; fallback only after NO_INDEPENDENT_REVIEWER",
        }
        for i in range(15):
            lg.add_context(mem["active"], DEV, "note", f"routine progress note number {i} about unrelated chores")
        for k, v in facts.items():
            lg.add_context(mem["active"], DEV, "lesson", v)
    finally:
        lg.close()
    dm.refresh(ix, mem["cfg"])
    assert ix.db.execute("SELECT COUNT(*) n FROM items").fetchone()["n"] >= 20
    queries = {"vram": "VRAM dwm profile", "tamper": "false TAMPER digest", "jsonschema": "jsonschema Phase 1",
               "playwright": "playwright assist tests", "quota": "Codex quota fallback"}
    for k, q in queries.items():
        hits = dm.recall(ix, q)["hits"]
        assert hits and hits[0]["text"].startswith(facts[k][:30]), (q, hits[:2])
        assert hits[0]["source"] == "ledger" and hits[0]["confidence"] == "VERIFIED" and hits[0]["ref"]


def test_dm4_invalidation(mem):
    ix, repo = mem["ix"], mem["repo"]
    dm.refresh(ix, mem["cfg"])

    def ledger_decision(**kw):
        return [h for h in dm.recall(ix, "source of truth", kind="decision", **kw)["hits"] if h["source"] == "ledger"]
    assert ledger_decision()
    (repo / "a.txt").write_bytes(b"changed in the task worktree\n")         # the decision row recorded a.txt's blob
    dm.refresh(ix)
    assert not ledger_decision()
    stale = ledger_decision(include_stale=True)
    assert stale and "a.txt changed" in stale[0]["stale"]
    sup = ix.db.execute("SELECT tier, stale FROM items WHERE ref LIKE 'DEC-003@%'").fetchone()
    assert sup["tier"] == "cold" and sup["stale"] == 1
    # canonical moves: re-evaluated (fingerprint includes the canonical tip)
    _git(repo, "checkout", "--", "a.txt")
    new = _commit(repo, "c.txt", b"x\n")
    _git(repo, "update-ref", CANON, new)
    r = dm.refresh(ix)
    assert r["canonical"] == new and r["sources"]["ledger"].startswith("rebuilt")


def test_dm4_missing_commit_is_stale(mem):
    ix = mem["ix"]
    dm.refresh(ix, mem["cfg"])
    rec = mem["rroot"] / "RUN-B"
    rec.mkdir()
    (rec / "receipt.json").write_text(json.dumps({"milestone": "RUN-B", "stage": "BLOCKED", "candidate": "f" * 40,
                                                  "evidence_ok_for_candidate": False}), encoding="utf-8")
    dm.refresh(ix)
    row = ix.db.execute("SELECT stale, stale_why, confidence FROM items WHERE ref LIKE '%RUN-B%'").fetchone()
    assert row["stale"] == 1 and "does not exist" in row["stale_why"] and row["confidence"] == "RECORDED"


def test_dm5_secrets_never_indexed(mem):
    ix = mem["ix"]
    dm.refresh(ix, mem["cfg"])
    blob = "\n".join(r["text"] + r["title"] for r in ix.db.execute("SELECT text, title FROM items"))
    assert "hunter2" not in blob
    assert not ix.db.execute("SELECT 1 FROM items WHERE path LIKE '%.env%'").fetchall()
    assert "hunter2" not in dm.brief(ix, 4000)["text"]
    assert all("hunter2" not in json.dumps(h) for h in dm.recall(ix, "password hunter2")["hits"])


def test_r1_05_decision_titles_and_all_index_fields_are_redacted(mem):
    ix = mem["ix"]
    dec = mem["dec"]
    dec.write_text(dec.read_text(encoding="utf-8").replace("Interaction loop", "password=hunter2 Interaction loop"),
                   encoding="utf-8")
    dm.refresh(ix, mem["cfg"])
    ix.replace_source("password=hunter2", "fp", [{"ref": "password=hunter2", "kind": "lesson",
        "tier": "warm", "title": "password=hunter2", "text": "safe", "path": "password=hunter2",
        "confidence": "RECORDED", "flags": {"next": "password=hunter2"}}], 0)
    rows = [dict(r) for r in ix.db.execute("SELECT * FROM items")]
    fts = [tuple(r) for r in ix.db.execute("SELECT title, text FROM fts")]
    assert "hunter2" not in json.dumps([rows, fts])
    hits = dm.recall(ix, "Interaction")["hits"]
    assert hits and "hunter2" not in json.dumps(hits)
    assert ix.path.read_bytes().find(b"hunter2") == -1


def test_dm6_deduplication(mem):
    ix = mem["ix"]
    dm.refresh(ix, mem["cfg"])
    s = dm.stats(ix)
    assert s["deduplicated_refs"] == 0      # DEC-041/042 have different titles in the text, so both are kept
    lg = tl.Ledger(mem["lp"])
    try:
        t2 = lg.create("second task", "o", DEV)
        lg.add_context(t2, DEV, "lesson", "background waits must match the producer's exact output file")
    finally:
        lg.close()
    dm.refresh(ix)
    rows = ix.db.execute("SELECT also_refs FROM items WHERE text LIKE 'background waits must match%'").fetchall()
    assert len(rows) == 1 and len(json.loads(rows[0]["also_refs"])) == 1
    assert dm.stats(ix)["deduplicated_refs"] == 1


def test_dm7_remember_writes_ledger_not_index(mem):
    ix = mem["ix"]
    dm.refresh(ix, mem["cfg"])
    dm.remember(mem["active"], "procedure", "start sessions with devmemory brief then task_ledger handoff", DEV,
                ledger=str(mem["lp"]))
    lg = tl.Ledger(mem["lp"])
    try:
        assert not lg.verify(mem["active"])
        assert lg.db.execute("SELECT 1 FROM context WHERE kind='procedure'").fetchone()
    finally:
        lg.close()
    dm.refresh(ix)
    assert dm.recall(ix, "start sessions devmemory brief")["hits"][0]["kind"] == "procedure"
    with pytest.raises(dm.MemoryError_):
        dm.remember(mem["active"], "note", "x", DEV, ledger=str(mem["lp"]))
    with pytest.raises(tl.LedgerError):
        dm.remember("TASK-none", "lesson", "x", DEV, ledger=str(mem["lp"]))


def test_dm8_rebuild_reproduces_index(mem):
    ix = mem["ix"]
    dm.refresh(ix, mem["cfg"])
    before = sorted((r["id"], r["tier"], r["stale"]) for r in ix.db.execute("SELECT id, tier, stale FROM items"))
    path = ix.path
    ix.close()
    r = cli("devmemory", "--index", str(path), "rebuild")
    assert r.returncode == 0, r.stderr
    ix2 = dm.Index(path)
    try:
        after = sorted((r["id"], r["tier"], r["stale"]) for r in ix2.db.execute("SELECT id, tier, stale FROM items"))
        assert after == before and ix2.meta("derived") is True
    finally:
        ix2.close()
    mem["ix"] = dm.Index(path)


# =========================================================================== HK: housekeeping

@pytest.fixture
def sandbox(tmp_path):
    """Repository with canonical + remote refs and one worktree of every class."""
    repo = _init(tmp_path / "main")
    base = _git(repo, "rev-parse", "HEAD")
    _git(repo, "update-ref", CANON, base)
    wt = tmp_path / "wt"
    wt.mkdir()

    def add(name, *extra):
        _git(repo, "worktree", "add", "-q", *extra)
        return wt / name

    disposable = add("disposable", "--detach", str(wt / "disposable"), base)
    dirty = add("dirty", "--detach", str(wt / "dirty"), base)
    (dirty / "work.txt").write_bytes(b"uncommitted work\n")
    evidence = add("evidence", "--detach", str(wt / "evidence"), base)
    (evidence / "out").mkdir()
    locked = add("locked", "--detach", str(wt / "locked"), base)
    _git(repo, "worktree", "lock", str(locked))
    cited = add("cited", "--detach", str(wt / "cited"), base)
    unmerged = add("unmerged", "-b", "feature/unmerged", str(wt / "unmerged"), base)
    _commit(unmerged, "f.txt", b"feature\n")
    gone = add("gone", "--detach", str(wt / "gone"), base)
    _git(repo, "branch", "merged/old", base)
    _git(repo, "branch", "preserve/keep", base)
    side = _commit(repo, "side.txt", b"s\n")
    _git(repo, "branch", "local/only", side)
    _git(repo, "reset", "-q", "--hard", base)
    records = tmp_path / "records"
    records.mkdir()
    (records / "decisions.md").write_text(f"evidence kept in `{cited.as_posix()}` for review\n", encoding="utf-8")
    roots = tmp_path / "devroot"
    (roots / "lifecycle-RUN" / "state").mkdir(parents=True)
    (roots / "lifecycle-RUN" / "state" / "receipt.json").write_text("{}")
    (roots / "tmpstuff" / "__pycache__").mkdir(parents=True)
    (roots / "tmpstuff" / "__pycache__" / "x.pyc").write_bytes(b"\0" * 100)
    (roots / "tmpstuff" / "notes.txt").write_text("scratch")
    import shutil
    shutil.rmtree(gone)
    (evidence / "out" / "receipt.json").write_text("{}")     # untracked evidence file
    return {"repo": repo, "base": base, "wt": wt, "records": records, "roots": roots, "tmp": tmp_path,
            "paths": {n: wt / n for n in ("disposable", "dirty", "evidence", "locked", "cited", "unmerged",
                                           "gone")}}


def _plan(sb, **kw):
    return hk.inventory(sb["repo"], canonical_ref=CANON, roots=[sb["roots"]], records=[sb["records"]],
                        min_age_hours=kw.pop("min_age_hours", 0), **kw)


def _by_path(plan):
    return {Path(it["path"]).name if it["kind"] != "branch" else it["path"]: it for it in plan["items"]}


def _digest(repo: Path, extra: list[Path]) -> str:
    h = hashlib.sha256()
    h.update(_git(repo, "for-each-ref", "--format=%(refname) %(objectname)").encode())
    h.update(_git(repo, "worktree", "list", "--porcelain").encode())
    for root in extra:
        for p in sorted(root.rglob("*")):
            if ".git" in p.parts and p.name == "index":
                continue
            h.update(str(p).encode())
            if p.is_file():
                h.update(p.read_bytes())
    return h.hexdigest()


def test_hk1_inventory_is_read_only(sandbox):
    before = _digest(sandbox["repo"], [sandbox["wt"], sandbox["roots"]])
    _plan(sandbox)
    assert _digest(sandbox["repo"], [sandbox["wt"], sandbox["roots"]]) == before


def test_r1_03_inventory_never_creates_default_ledger(sandbox, monkeypatch):
    missing = sandbox["tmp"] / "no-ledger" / "task.sqlite3"
    monkeypatch.setenv("URI_TASK_LEDGER", str(missing))
    _plan(sandbox)
    assert not missing.exists() and not missing.parent.exists()


def test_r1_03_existing_ledger_is_opened_without_schema_writes(sandbox):
    lp = sandbox["tmp"] / "old-ledger.sqlite3"
    with sqlite3.connect(lp) as db:
        db.executescript(tl.DDL)
    db.close()
    before = lp.read_bytes()
    _plan(sandbox, ledger=str(lp))
    assert lp.read_bytes() == before


def test_hk2_classification(sandbox):
    items = _by_path(_plan(sandbox))
    assert items["main"]["cls"] == "PROTECTED"
    assert items["locked"]["cls"] == "PROTECTED"
    assert items["unmerged"]["cls"] == "PROTECTED" and any("feature/unmerged" in r for r in items["unmerged"]["reasons"])
    assert items["dirty"]["cls"] == "DIRTY"
    assert items["evidence"]["cls"] == "EVIDENCE" and items["evidence"]["evidence"] == ["out/receipt.json"]
    assert items["cited"]["cls"] == "REFERENCED"
    assert items["disposable"]["cls"] == "DISPOSABLE"
    assert items["gone"]["cls"] == "PRUNABLE"
    assert items["lifecycle-RUN"]["cls"] == "ESSENTIAL_EVIDENCE"
    assert items["tmpstuff"]["cls"] == "AMBIGUOUS"
    assert items["__pycache__"]["cls"] == "CACHE"
    assert items["wt"]["cls"] == "PROTECTED" if "wt" in items else True
    assert items["refs/heads/merged/old"]["cls"] == "OBSOLETE_BRANCH"
    assert "refs/heads/preserve/keep" not in items and "refs/heads/local/only" not in items
    assert "refs/heads/feature/unmerged" not in items
    # recent worktree is not disposable
    assert _by_path(_plan(sandbox, min_age_hours=24))["disposable"]["cls"] == "AMBIGUOUS"


def test_hk2_dir_holding_worktrees_is_protected(sandbox):
    sb = sandbox
    holder = sb["roots"] / "live-run"
    holder.mkdir()
    _git(sb["repo"], "worktree", "add", "-q", "--detach", str(holder / "runtime"), sb["base"])
    items = _by_path(_plan(sb))
    assert items["live-run"]["cls"] == "PROTECTED" and items["live-run"]["nested_worktrees"] == 1
    assert items["runtime"]["kind"] == "worktree"


def test_r2_01_inventory_excludes_cache_beneath_registered_worktree(sandbox):
    sb = sandbox
    holder = sb["roots"] / "live-run"
    cache = holder / "__pycache__"
    cache.mkdir(parents=True)
    (cache / "x.pyc").write_bytes(b"cache")
    _git(sb["repo"], "worktree", "add", "-q", "--detach", str(holder / "runtime"), sb["base"])
    plan = _plan(sb)
    assert _by_path(plan)["live-run"]["cls"] == "PROTECTED"
    assert not any(it["kind"] == "cache" and it["path"] == str(cache) for it in plan["items"])


def test_r3_01_cache_evidence_is_never_automatic(sandbox):
    sb = sandbox
    cache = sb["roots"] / "tmpstuff" / "__pycache__"
    evidence = cache / "nested" / "receipt.json"
    evidence.parent.mkdir()
    evidence.write_text("evidence", encoding="utf-8")
    plan = _plan(sb)
    item = next(it for it in plan["items"] if it["path"] == str(cache))
    assert item["cls"] == "ESSENTIAL_EVIDENCE"
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    result = hk.apply(pf, journal_dir=sb["tmp"] / "j")
    row = next(x for x in result["results"] if x.get("path") == str(cache))
    assert row["outcome"] == "NOT_SELECTED" and evidence.read_text(encoding="utf-8") == "evidence"


def test_r3_01_record_cited_cache_is_never_automatic(sandbox):
    sb = sandbox
    cache = sb["roots"] / "tmpstuff" / "__pycache__"
    with (sb["records"] / "decisions.md").open("a", encoding="utf-8") as record:
        record.write(f"\nEvidence at `{(cache / 'x.pyc').as_posix()}`\n")
    plan = _plan(sb)
    item = next(it for it in plan["items"] if it["path"] == str(cache))
    assert item["cls"] in hk.NEVER and item["cited"]


def test_r3_01_cache_recheck_rejects_new_parent_evidence(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    parent = sb["roots"] / "tmpstuff"
    cache = parent / "__pycache__"
    receipt = parent / "receipt.json"
    receipt.write_text("keep", encoding="utf-8")
    result = hk.apply(pf, journal_dir=sb["tmp"] / "j")
    row = next(x for x in result["results"] if x.get("path") == str(cache))
    assert row["outcome"] == "SKIPPED_CHANGED"
    assert cache.is_dir() and receipt.read_text(encoding="utf-8") == "keep"


@pytest.mark.parametrize("protection", ["worktree", "task"])
def test_r2_01_apply_refuses_cache_when_parent_becomes_protected(sandbox, protection):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    parent = sb["roots"] / "tmpstuff"
    cache = parent / "__pycache__"
    ledger = None
    if protection == "worktree":
        _git(sb["repo"], "worktree", "add", "-q", "--detach", str(parent / "runtime"), sb["base"])
    else:
        ledger = sb["tmp"] / "ledger.sqlite3"
        lg = tl.Ledger(ledger)
        lg.create("active", "work", DEV, worktree=str(parent / "runtime"))
        lg.close()
    result = hk.apply(pf, journal_dir=sb["tmp"] / "j", ledger=str(ledger) if ledger else None)
    row = next(x for x in result["results"] if x.get("path") == str(cache))
    assert row["outcome"] == "SKIPPED_CHANGED" and cache.is_dir()


def test_r2_01_cache_parent_protection_after_first_recheck_blocks_removal(sandbox, monkeypatch):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    parent = sb["roots"] / "tmpstuff"
    cache = parent / "__pycache__"
    cache_id = next(it["id"] for it in plan["items"] if it["path"] == str(cache))
    original = hk.Chain.append
    changed = False

    def protect_after_intent(self, kind, data):
        nonlocal changed
        result = original(self, kind, data)
        if kind == "INTENT" and data.get("item") == cache_id and not changed:
            changed = True
            _git(sb["repo"], "worktree", "add", "-q", "--detach", str(parent / "runtime"), sb["base"])
        return result

    monkeypatch.setattr(hk.Chain, "append", protect_after_intent)
    result = hk.apply(pf, journal_dir=sb["tmp"] / "j")
    row = next(x for x in result["results"] if x.get("path") == str(cache))
    assert changed and row["outcome"] == "FAILED" and "SOURCE_CHANGED" in row["error"]
    assert cache.is_dir()


def test_hk2_active_ledger_task_protects_worktree(sandbox):
    lp = sandbox["tmp"] / "ledger.sqlite3"
    lg = tl.Ledger(lp)
    lg.create("t", "o", DEV, worktree=str(sandbox["paths"]["disposable"]))
    lg.close()
    items = _by_path(_plan(sandbox, ledger=str(lp)))
    assert items["disposable"]["cls"] == "PROTECTED"


def _driver_state(state: Path, stage: str):
    state.mkdir(parents=True, exist_ok=True)
    (state / "state.json").write_text(json.dumps({"stage": stage}), encoding="utf-8")
    (state / "events.jsonl").write_text("", encoding="utf-8")


def test_hk2_driver_work_trees_of_unfinished_runs_are_protected(sandbox):
    sb = sandbox
    base = sb["base"]
    running = sb["tmp"] / "lifecycle" / "RUN-X" / "state"
    done = sb["tmp"] / "lifecycle" / "RUN-Y" / "state"
    _driver_state(running, "REVIEWING")
    _driver_state(done, "COMPLETE")
    for st in (running, done):
        _git(sb["repo"], "worktree", "add", "-q", "--detach", str(st / ".work" / "qualify"), base)
        _git(sb["repo"], "worktree", "add", "-q", "--detach", str(st / ".work" / "audit_R1"), base)
        import shutil
        shutil.rmtree(st / ".work" / "audit_R1")                 # driver removed the dir, registration remains
    items = {it["path"]: it for it in _plan(sb)["items"] if it["kind"] == "worktree"}
    assert items[str(running / ".work" / "qualify")]["cls"] == "PROTECTED"
    assert items[str(running / ".work" / "audit_R1")]["cls"] == "PROTECTED"
    assert items[str(done / ".work" / "qualify")]["cls"] == "DISPOSABLE"
    assert items[str(done / ".work" / "audit_R1")]["cls"] == "PRUNABLE"


def test_hk3_prune_is_per_item_never_global(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    other = sb["wt"] / "late"                                   # becomes prunable after the plan was made
    _git(sb["repo"], "worktree", "add", "-q", "--detach", str(other), sb["base"])
    import shutil
    shutil.rmtree(other)
    hk.apply(pf, journal_dir=sb["tmp"] / "j")
    listed = _git(sb["repo"], "worktree", "list", "--porcelain")
    assert other.as_posix() in listed.replace("\\", "/")          # not in the plan: still registered
    assert sb["paths"]["gone"].as_posix() not in listed.replace("\\", "/")


def test_hk3_apply_scope_refusals_and_archive_restore(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    items = _by_path(plan)
    jd, ar = sb["tmp"] / "journal", sb["tmp"] / "archive"
    r = hk.apply(pf, journal_dir=jd, archive_root=ar,
                 approve=[items["dirty"]["id"], items["locked"]["id"], items["lifecycle-RUN"]["id"]])
    out = {Path(x["path"]).name if x["kind"] != "branch" else x["path"]: x for x in r["results"] if "item" in x}
    assert out["disposable"]["outcome"] == "DONE" and not sb["paths"]["disposable"].exists()
    assert out["gone"]["outcome"] == "DONE"
    assert out["__pycache__"]["outcome"] == "DONE" and (sb["roots"] / "tmpstuff" / "notes.txt").exists()
    assert out["locked"]["outcome"] == "REFUSED" and sb["paths"]["locked"].exists()
    assert out["lifecycle-RUN"]["outcome"] == "REFUSED" and (sb["roots"] / "lifecycle-RUN").exists()
    assert out["evidence"]["outcome"] == "NOT_SELECTED" and sb["paths"]["evidence"].exists()
    assert out["cited"]["outcome"] == "NOT_SELECTED" and out["tmpstuff"]["outcome"] == "NOT_SELECTED"
    assert out["refs/heads/merged/old"]["outcome"] == "NOT_SELECTED"
    assert out["dirty"]["outcome"] == "DONE" and out["dirty"]["archive"] and not sb["paths"]["dirty"].exists()
    assert out["unmerged"]["outcome"] == "NOT_SELECTED" and sb["paths"]["unmerged"].exists()
    # the approved dirty tree's uncommitted file comes back byte-identical
    back = sb["tmp"] / "restored"
    hk.restore(out["dirty"]["archive"], ar, back)
    assert (back / "work.txt").read_bytes() == b"uncommitted work\n"
    assert r["journal_ok"] and Path(r["receipt"]).is_file() and Path(r["receipt"]).with_suffix(".md").is_file()


def test_hk4_changed_item_is_skipped(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    (sb["paths"]["disposable"] / "new.txt").write_text("arrived after the plan")
    r = hk.apply(pf, journal_dir=sb["tmp"] / "j", archive_root=sb["tmp"] / "a")
    row = next(x for x in r["results"] if x.get("path") == str(sb["paths"]["disposable"]))
    assert row["outcome"] == "SKIPPED_CHANGED" and sb["paths"]["disposable"].exists()


def test_r1_02_cache_and_dirty_bytes_bind_the_plan(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    dirty = sb["paths"]["dirty"]
    (dirty / "work.txt").write_bytes(b"changed same count\n")
    cache = sb["roots"] / "tmpstuff" / "__pycache__"
    next(cache.iterdir()).write_bytes(b"new cache bytes")
    r = hk.apply(pf, journal_dir=sb["tmp"] / "j", archive_root=sb["tmp"] / "ar",
                 approve=[_by_path(plan)["dirty"]["id"]])
    rows = {x["path"]: x for x in r["results"] if "item" in x}
    assert rows[str(dirty)]["outcome"] == "SKIPPED_CHANGED" and dirty.exists()
    assert rows[str(cache)]["outcome"] == "SKIPPED_CHANGED" and cache.exists()


def test_r1_02_change_after_archive_refuses_removal(sandbox, monkeypatch):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    dirty = sb["paths"]["dirty"]
    original = hk.archive

    def changed_after_archive(*args, **kwargs):
        result = original(*args, **kwargs)
        (dirty / "work.txt").write_bytes(b"changed after archive\n")
        return result

    monkeypatch.setattr(hk, "archive", changed_after_archive)
    r = hk.apply(pf, journal_dir=sb["tmp"] / "j", archive_root=sb["tmp"] / "ar",
                 approve=[_by_path(plan)["dirty"]["id"]])
    row = next(x for x in r["results"] if x.get("path") == str(dirty))
    assert row["outcome"] == "FAILED" and "SOURCE_CHANGED" in row["error"] and dirty.exists()


def test_r2_02_same_tree_head_advance_after_first_recheck_blocks_removal(sandbox, monkeypatch):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    target = sb["paths"]["disposable"]
    target_id = _by_path(plan)["disposable"]["id"]
    original = hk.Chain.append
    moved = False

    def advance_after_intent(self, kind, data):
        nonlocal moved
        result = original(self, kind, data)
        if kind == "INTENT" and data.get("item") == target_id and not moved:
            moved = True
            _git(target, "commit", "-q", "--allow-empty", "-m", "same tree, new head")
        return result

    monkeypatch.setattr(hk.Chain, "append", advance_after_intent)
    result = hk.apply(pf, journal_dir=sb["tmp"] / "j")
    row = next(x for x in result["results"] if x.get("path") == str(target))
    assert moved and row["outcome"] == "FAILED" and "SOURCE_CHANGED" in row["error"]
    assert target.is_dir() and _git(target, "rev-parse", "HEAD") != sb["base"]


def test_r1_01_approved_worktree_with_omitted_link_is_retained(sandbox):
    sb = sandbox
    dirty = sb["paths"]["dirty"]
    outside = sb["tmp"] / "outside"
    outside.mkdir()
    (outside / "keep.txt").write_text("keep")
    link = dirty / "link"
    if os.name == "nt":
        subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(outside)], check=True, capture_output=True)
    else:
        link.symlink_to(outside, target_is_directory=True)
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    r = hk.apply(pf, journal_dir=sb["tmp"] / "j", archive_root=sb["tmp"] / "ar",
                 approve=[_by_path(plan)["dirty"]["id"]])
    row = next(x for x in r["results"] if x.get("path") == str(dirty))
    assert row["outcome"] == "FAILED" and "LINKS_PRESENT" in row["error"]
    assert dirty.exists() and hk.is_link(link) and (outside / "keep.txt").exists()


def test_hk5_idempotent_apply(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    jd = sb["tmp"] / "j"
    r1 = hk.apply(pf, journal_dir=jd, classes=["OBSOLETE_BRANCH"])
    r2 = hk.apply(pf, journal_dir=jd, classes=["OBSOLETE_BRANCH"])
    done1 = {x["item"] for x in r1["results"] if x.get("outcome") == "DONE"}
    assert done1 and {x["item"] for x in r2["results"] if x.get("outcome") == "ALREADY_DONE"} == done1
    assert not any(x.get("outcome") == "DONE" for x in r2["results"])
    intents = [e for e in hk.Chain(jd / "journal.jsonl").read() if e["kind"] == "INTENT"]
    assert len(intents) == len(done1)
    assert not hk.Chain(jd / "journal.jsonl").verify()
    assert cli("housekeeping", "verify-chain", str(jd / "journal.jsonl")).returncode == 0


def test_hk6_recover_after_crash(sandbox):
    sb = sandbox
    jd = sb["tmp"] / "j"
    j = hk.Chain(jd / "journal.jsonl")
    j.append("INTENT", {"plan_id": "p1", "item": "wt:aaa", "action": "worktree-remove",
                        "path": str(sb["paths"]["disposable"]), "fingerprint": "f"})
    _git(sb["repo"], "worktree", "remove", str(sb["paths"]["disposable"]))     # the action ran, the DONE did not
    j.append("INTENT", {"plan_id": "p1", "item": "wt:bbb", "action": "worktree-remove",
                        "path": str(sb["paths"]["cited"]), "fingerprint": "f"})  # crashed before acting
    r = hk.recover(jd, sb["repo"])
    res = {x["item"]: x["result"] for x in r["recovered"]}
    assert res == {"wt:aaa": "RECOVERED_DONE", "wt:bbb": "RECOVERED_NOT_DONE"}
    assert hk.recover(jd, sb["repo"])["recovered"] == []                      # resolved once
    assert sb["paths"]["cited"].exists() and not j.verify()


def test_r1_07_recovery_and_reapply_keep_verified_archive_pointer(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    it = _by_path(plan)["dirty"]
    ar, jd = sb["tmp"] / "archive", sb["tmp"] / "journal"
    a = hk.archive(it["path"], ar)
    assert hk.verify_archive(a["archive_id"], ar)["ok"]
    j = hk.Chain(jd / "journal.jsonl")
    base = {"plan_id": plan["plan_id"], "item": it["id"], "action": "archive-then-remove",
            "path": it["path"], "restore": it["restore"]}
    j.append("INTENT", base)
    j.append("ARCHIVE_READY", {**base, "archive": a["archive_id"]})
    _git(sb["repo"], "worktree", "remove", "--force", it["path"])
    recovered = hk.recover(jd, sb["repo"])["recovered"]
    assert recovered[0]["result"] == "RECOVERED_DONE"
    assert recovered[0]["archive"] == a["archive_id"] and recovered[0]["restore"] == it["restore"]
    again = hk.apply(pf, journal_dir=jd, archive_root=ar, approve=[it["id"]])
    row = next(x for x in again["results"] if x.get("item") == it["id"])
    assert row["outcome"] == "ALREADY_DONE" and row["archive"] == a["archive_id"]


def test_hk6_tampered_journal_blocks_apply(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    jd = sb["tmp"] / "j"
    hk.Chain(jd / "journal.jsonl").append("INTENT", {"plan_id": "x", "item": "y", "action": "z", "path": "p"})
    text = (jd / "journal.jsonl").read_text(encoding="utf-8").replace('"z"', '"w"')
    (jd / "journal.jsonl").write_text(text, encoding="utf-8")
    with pytest.raises(hk.HKError) as e:
        hk.apply(pf, journal_dir=jd)
    assert e.value.code == "CHAIN_BROKEN" and sb["paths"]["disposable"].exists()


def test_hk7_archive_verification_and_safe_restore(tmp_path):
    src = tmp_path / "evidence"
    (src / "sub").mkdir(parents=True)
    (src / "receipt.json").write_text('{"ok": true}')
    (src / "sub" / "log.txt").write_bytes(os.urandom(5000))
    ar = tmp_path / "archive"
    a = hk.archive(src, ar, label="ev")
    assert hk.verify_archive(a["archive_id"], ar)["ok"] and src.exists()           # source kept
    back = tmp_path / "back"
    hk.restore(a["archive_id"], ar, back)
    assert (back / "sub" / "log.txt").read_bytes() == (src / "sub" / "log.txt").read_bytes()
    with pytest.raises(hk.HKError) as e:
        hk.restore(a["archive_id"], ar, back)                                          # not empty
    assert e.value.code == "TARGET_NOT_EMPTY"
    # tamper a member: verification fails
    bad = tmp_path / "bad.zip"
    with zipfile.ZipFile(a["zip"]) as zin, zipfile.ZipFile(bad, "w") as zout:
        for n in zin.namelist():
            data = zin.read(n)
            zout.writestr(n, b"tampered" if n == "data/receipt.json" else data)
    errs = hk._verify_zip(bad)
    assert any("sha256 mismatch" in e for e in errs)
    # a zip-slip member is refused
    slip = tmp_path / "slip.zip"
    with zipfile.ZipFile(slip, "w") as z:
        z.writestr("data/../evil.txt", b"x")
        z.writestr("manifest.json", json.dumps({"files": [{"path": "../evil.txt", "sha256": hashlib.sha256(b"x")
                                                           .hexdigest(), "size": 1}]}))
    assert any("unsafe" in e for e in hk._verify_zip(slip))
    assert not hk.Chain(ar / "archive_index.jsonl").verify()


@pytest.mark.windows_only
def test_hk7_archive_never_follows_junctions(tmp_path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "a.txt").write_text("a")
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "big.bin").write_bytes(b"x" * 1000)
    subprocess.run(["cmd", "/c", "mklink", "/J", str(src / "link"), str(outside)], check=True, capture_output=True)
    a = hk.archive(src, tmp_path / "ar")
    with zipfile.ZipFile(a["zip"]) as z:
        man = json.loads(z.read("manifest.json"))
    assert [f["path"] for f in man["files"]] == ["a.txt"] and man["links_not_followed"] == ["link"]
    with pytest.raises(hk.HKError):
        hk._rmtree(src / "link")
    assert (outside / "big.bin").exists()


def test_hk8_restore_commands_work(sandbox):
    sb = sandbox
    plan = _plan(sb)
    pf = sb["tmp"] / "plan.json"
    pf.write_text(json.dumps(plan), encoding="utf-8")
    r = hk.apply(pf, journal_dir=sb["tmp"] / "j", classes=["OBSOLETE_BRANCH"])
    rows = {x["path"]: x for x in r["results"] if x.get("outcome") == "DONE"}
    wt_row = rows[str(sb["paths"]["disposable"])]
    br_row = rows["refs/heads/merged/old"]
    for row in (wt_row, br_row):
        cmd = row["restore"].split()
        subprocess.run(cmd, check=True, capture_output=True)
    assert (sb["paths"]["disposable"] / "a.txt").read_bytes() == b"one\n"
    assert _git(sb["repo"], "rev-parse", "merged/old") == sb["base"]
