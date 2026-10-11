"""uri-development-lifecycle driver (extends AO-4).

Plan -> Implement -> Test -> Independent Audit -> Repair -> Re-audit -> Qualify -> Integrate -> Receipt.

Deterministic parts live here: state, transitions (AO-4 ``VALID_TRANSITIONS``), evidence binding to exact commits,
independence checks, verdict recomputation, scope and protected-path enforcement, regression proof, baseline-aware
gates, integration policy, hash-chained receipts. Reasoning (implementing, reviewing) is done by separate worker
processes (``lifecycle_providers``).

    python -m scripts.dev_workflow.lifecycle run      <config.json>
    python -m scripts.dev_workflow.lifecycle status   <config.json> [--a2ui]
    python -m scripts.dev_workflow.lifecycle verify   <config.json>
    python -m scripts.dev_workflow.lifecycle unblock  <config.json> --note "<owner decision>"

Exit codes of ``run``: 0 COMPLETE or VERIFIED (integration policy none), 3 BLOCKED, 4 NOT_VERIFIED,
5 WAITING_FOR_MODEL, 2 usage/config error.

Boundary Guarantee: Development tooling only. Not part of the URI runtime.
"""
from __future__ import annotations

import argparse
import datetime
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import os
import signal
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.dev_workflow.lifecycle_providers import INDEPENDENT_PROVIDERS, run_worker
from scripts.dev_workflow.security_boundary import is_devtest_identifier
from scripts.dev_workflow.state_machine import VALID_TRANSITIONS, InvalidTransitionError, WorkflowState as S

SCHEMA = "uri-dev-lifecycle/1"
EXIT = {S.COMPLETE: 0, S.VERIFIED: 0, S.BLOCKED: 3, S.NOT_VERIFIED: 4, S.WAITING_FOR_MODEL: 5}
VERDICTS = ("ACCEPT", "ACCEPT WITH FINDINGS", "REJECT")
BLOCK_RE = re.compile(r"AUDIT_RESULT_BEGIN\s*(\{.*\})\s*AUDIT_RESULT_END", re.S)
REPAIR_RE = re.compile(r"REPAIR_RESULT_BEGIN\s*(\{.*\})\s*REPAIR_RESULT_END", re.S)
DEFAULTS = {
    "limits": {"max_rounds": 6, "max_repair_attempts": 3},
    "test_globs": ["tests/**", "**/test_*.py", "**/*_test.py", "**/test/**"],
    "permitted_paths": ["**"],
    "authorized_protected_changes": [],
    "allowed_flaky": [],
    "gates": [],
    "integration": {"mode": "none"},
    "commit_trailers": [],
    "review_focus": [],
}


class LifecycleError(Exception):
    pass


def now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b: bytes | str) -> str:
    return hashlib.sha256(b.encode() if isinstance(b, str) else b).hexdigest()


# Every git command the driver runs ignores repository hooks: a worker could plant one (DEV-LIFECYCLE-1 R1-03).
GIT = ["git", "-c", "core.hooksPath=/dev/null"]


def git(repo, *args, check=True) -> str:
    p = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True)
    if check and p.returncode:
        raise LifecycleError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def chash(obj) -> str:
    return sha256(json.dumps(obj, sort_keys=True))


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(obj, indent=1, sort_keys=True), encoding="utf-8")
    tmp.replace(path)


def match_any(path: str, globs) -> bool:
    return any(fnmatch.fnmatch(path, g) or (g.endswith("/") and path.startswith(g)) or path == g for g in globs)


# --------------------------------------------------------------------------- config

def load_config(path) -> dict:
    path = Path(path).resolve()
    cfg = json.loads(path.read_text(encoding="utf-8-sig"))
    for k, v in DEFAULTS.items():
        cfg.setdefault(k, json.loads(json.dumps(v)))
    for k, v in DEFAULTS["limits"].items():
        cfg["limits"].setdefault(k, v)
    missing = [k for k in ("milestone", "repo", "baseline", "candidate", "reviewer") if k not in cfg]
    if missing:
        raise LifecycleError(f"config missing {missing}")
    base = path.parent
    cfg["repo"] = str((base / cfg["repo"]).resolve())
    cfg["state_dir"] = str((Path(cfg["repo"]) / cfg.get("state_dir", f"docs/dev_workflow/lifecycle_runs/"
                                                                         f"{cfg['milestone']}")).resolve())
    cfg["work_dir"] = str(Path(cfg.get("work_dir") or (Path(cfg["state_dir"]) / ".work")).resolve())
    cand = cfg["candidate"]
    cand["worktree"] = str((base / cand["worktree"]).resolve())
    if cfg.get("protected_paths", "ws_frozen_check") == "ws_frozen_check":
        cfg["protected_paths"] = list(_ws_protected(cfg["repo"]))
    if cfg["reviewer"].get("counts_as_independent") and not is_devtest(cfg["milestone"]):
        raise LifecycleError("counts_as_independent is allowed only for DEVTEST milestones")
    if not is_devtest(cfg["milestone"]) and cfg["reviewer"].get("binary"):
        raise LifecycleError("a reviewer binary override is allowed only for DEVTEST milestones")
    cfg["_config_sha256"] = sha256(path.read_bytes())
    cfg["_config_path"] = str(path)
    return cfg


def is_devtest(milestone: str) -> bool:
    """Strict DEVTEST namespace for the lifecycle (AO-4's heuristic also matches any name containing _TEST)."""
    return is_devtest_identifier(milestone) and str(milestone).upper().startswith(("DEVTEST", "TOOLING_TEST"))


def _ws_protected(repo) -> tuple:
    f = Path(repo) / "scripts" / "ws_frozen_check.py"
    m = re.search(r"PROTECTED\s*=\s*\((.*?)\)\n", f.read_text(encoding="utf-8"), re.S) if f.is_file() else None
    return tuple(re.findall(r'"([^"]+)"', m.group(1))) if m else ()


# --------------------------------------------------------------------------- state + hash-chained events

class State:
    def __init__(self, cfg):
        self.cfg = cfg
        self.dir = Path(cfg["state_dir"])
        self.path = self.dir / "state.json"
        self.events_path = self.dir / "events.jsonl"
        if self.path.is_file():
            self.d = json.loads(self.path.read_text(encoding="utf-8"))
        else:
            self.d = {"schema": SCHEMA, "milestone": cfg["milestone"], "stage": None, "rounds": [], "repairs": [],
                      "gates": {}, "baseline_gates": {}, "attempts": {}, "blocker": None, "integration": None,
                      "candidate": None, "baseline": None, "history": []}

    @property
    def stage(self):
        return S(self.d["stage"]) if self.d["stage"] else None

    def event(self, kind: str, **data) -> dict:
        prev = "0" * 64
        if self.events_path.is_file():
            lines = self.events_path.read_text(encoding="utf-8").splitlines()
            if lines:
                prev = json.loads(lines[-1])["hash"]
        ev = {"seq": len(self.d["history"]) + 1, "ts": now(), "kind": kind, "data": data, "prev": prev}
        ev["hash"] = sha256(json.dumps({k: ev[k] for k in ("seq", "ts", "kind", "data", "prev")}, sort_keys=True))
        self.dir.mkdir(parents=True, exist_ok=True)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(ev, sort_keys=True) + "\n")
        self.d["history"].append({"seq": ev["seq"], "ts": ev["ts"], "kind": kind, "hash": ev["hash"]})
        self.save()
        return ev

    def to(self, new: S, reason: str = "") -> None:
        cur = self.stage
        if cur is not None and new != cur and new not in VALID_TRANSITIONS.get(cur, set()):
            raise InvalidTransitionError(f"{cur.value} -> {new.value} is not an AO-4 transition")
        self.d["stage"] = new.value
        self.event("STAGE", stage=new.value, frm=cur.value if cur else None, reason=reason)

    def block(self, kind: str, reason: str, needs: str) -> None:
        cur = self.stage
        self.d["resume_to"] = {S.VERIFYING: S.VERIFYING, S.VERIFIED: S.VERIFYING, S.FIXING: S.FIXING}.get(
            cur, S.AUDITING).value
        self.d["blocker"] = {"kind": kind, "reason": reason, "needs": needs, "at": now(), "stage": cur.value if cur else None}
        self.to(S.BLOCKED, f"{kind}: {reason}")

    def save(self) -> None:
        write_json(self.path, self.d)


# --------------------------------------------------------------------------- verdicts and independence

def parse_block(text: str, rx=BLOCK_RE) -> dict | None:
    m = None
    for m in rx.finditer(text or ""):
        pass
    if not m:
        return None
    try:
        obj = json.loads(m.group(1))
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def is_blocking(f: dict) -> bool:
    """HIGH or unknown severity: blocking. MEDIUM: blocking unless explicitly false. LOW: only if explicitly true."""
    sev = str(f.get("severity", "")).strip().upper()
    b = str(f.get("blocking")).strip().lower()
    if sev == "LOW":
        return b == "true"
    if sev == "MEDIUM":
        return b != "false"
    return True


def effective_verdict(result: dict) -> tuple[str, list]:
    """The driver's verdict, from findings alone; the reviewer's label can only make it stricter."""
    findings = [f for f in result.get("findings") or [] if isinstance(f, dict)]
    blocking = [f for f in findings if is_blocking(f)]
    label = str(result.get("verdict", "")).strip().upper()
    if blocking or label == "REJECT" or label not in VERDICTS:
        return "REJECT", blocking
    return ("ACCEPT WITH FINDINGS" if findings else "ACCEPT"), []


def is_independent(cfg, round_rec: dict, impl_sids=frozenset()) -> tuple[bool, str]:
    w = round_rec.get("worker") or {}
    if round_rec.get("integrity", {}).get("ok") is not True:
        return False, "audit checkout, implementation worktree, candidate refs or git hooks/config changed during review"
    if w.get("status") != "COMPLETED":
        return False, f"reviewer status {w.get('status')}"
    if w.get("provider") not in INDEPENDENT_PROVIDERS:
        if is_devtest(cfg["milestone"]) and cfg["reviewer"].get("counts_as_independent"):
            return True, "scripted reviewer accepted for DEVTEST only"
        return False, f"provider {w.get('provider')} is not an independent reviewer"
    if not w.get("binary_is_default") and not is_devtest(cfg["milestone"]):
        return False, f"reviewer executable {w.get('binary_realpath')} is not the installed CLI"
    sid = w.get("session_id")
    if not sid or sid == cfg.get("coordinator_session_id") or sid in impl_sids:
        return False, "reviewer session id missing or shared with coordinator/implementer"
    return True, "separate process, fresh session, clean checkout, integrity verified"


# --------------------------------------------------------------------------- git helpers

def git_control_digest(repo) -> str:
    """Hooks and config of the shared repository: a worker that plants a hook or rewrites config is caught."""
    common = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir"))
    parts = []
    for p in sorted((common / "hooks").glob("*")) if (common / "hooks").is_dir() else []:
        if p.is_file() and not p.name.endswith(".sample"):
            parts.append(f"{p.name}:{sha256(p.read_bytes())}")
    cfgf = common / "config"
    parts.append("config:" + (sha256(cfgf.read_bytes()) if cfgf.is_file() else "-"))
    return sha256("\n".join(parts))


def refs_digest(cfg) -> str:
    """Only the refs this milestone depends on (candidate branch, baseline ref, integration target). Other
    sessions legitimately move other branches (DEV-LIFECYCLE-1 coordinator finding C1)."""
    names = [f"refs/heads/{cfg['candidate']['branch']}", cfg["baseline"]["ref"]]
    pol = cfg.get("integration") or {}
    if pol.get("target_ref"):
        names.append(f"refs/heads/{pol['target_ref']}")
    vals = [f"{n}={git(cfg['repo'], 'rev-parse', '-q', '--verify', n, check=False)}" for n in names]
    return sha256("\n".join(vals))


def add_worktree(repo, path: Path, sha: str) -> Path:
    if path.exists():
        git(repo, "worktree", "remove", "--force", str(path), check=False)
        shutil.rmtree(path, ignore_errors=True)
    git(repo, "worktree", "prune")
    path.parent.mkdir(parents=True, exist_ok=True)
    git(repo, "worktree", "add", "--detach", str(path), sha)
    return path


def drop_worktree(repo, path: Path) -> None:
    git(repo, "worktree", "remove", "--force", str(path), check=False)
    shutil.rmtree(path, ignore_errors=True)


def changed_paths(repo, a: str, b: str) -> list[str]:
    return [p for p in git(repo, "diff", "--name-only", a, b).splitlines() if p]


def worktree_changes(wt) -> list[str]:
    out = subprocess.run(["git", "-C", str(wt), "status", "--porcelain", "-z", "--untracked-files=all"],
                         capture_output=True, text=True, check=True).stdout
    items, paths = out.split("\0"), set()
    i = 0
    while i < len(items):
        e = items[i]
        if len(e) > 3:
            paths.add(e[3:])
            if e[0] in "RC":  # rename/copy: the next item is the source path
                i += 1
                paths.add(items[i])
        i += 1
    return sorted(paths)


def protected_hits(cfg, paths) -> list[str]:
    prot = cfg["protected_paths"]
    hits = [p for p in paths if any(p == x or (x.endswith("/") and p.startswith(x)) for x in prot)]
    return [p for p in hits if not match_any(p, cfg["authorized_protected_changes"])]


# --------------------------------------------------------------------------- prompts

def _criteria_text(cfg) -> str:
    f = cfg.get("acceptance_criteria_file")
    if f:
        return f"Governing acceptance criteria: `{f}` in the checkout (read it in full)."
    return "Acceptance criteria:\n" + "\n".join(f"- {c}" for c in cfg.get("acceptance_criteria") or [])


def _env_notes(cfg) -> str:
    notes = cfg.get("environment_notes") or []
    return ("Environment notes:\n" + "\n".join(f"- {n}" for n in notes) + "\n\n") if notes else ""


def review_prompt(cfg, st: State, rnd: int, candidate: str) -> str:
    prior = [{"id": f["id"], "severity": f.get("severity"), "title": f.get("title"), "files": f.get("files")}
             for r in st.d["rounds"] for f in (r.get("result") or {}).get("findings") or []
             if f.get("severity") == "HIGH" or f.get("blocking")]
    repairs = [{"commit": r["commit"], "addresses": r["addresses"]} for r in st.d["repairs"] if r.get("commit")]
    focus = "\n".join(f"{i}. {x}" for i, x in enumerate(cfg["review_focus"], 1)) or "(whole diff)"
    return f"""You are the INDEPENDENT REVIEWER for URI milestone {cfg['milestone']}, round R{rnd}.
You did not write this code and you will not repair it. Your verdict is recorded verbatim.

Rules: read-only. Do not edit, create or delete files in this checkout; do not commit, push, change branches or
refs. Put throwaway probes under /tmp/uri_review_R{rnd}/. Running tests and adversarial probes is expected.

Baseline: {st.d['baseline']}
Candidate (this checkout, detached HEAD): {candidate}
Review range: `git diff {st.d['baseline']}..{candidate}` (fetch history if needed). Verify both SHAs yourself.
{_criteria_text(cfg)}
Protected paths (must not change without owner authorisation): {', '.join(cfg['protected_paths']) or '(none)'}
Review focus:
{focus}
Blocking findings from earlier rounds (verify each is fixed; state FIXED or NOT_FIXED): {json.dumps(prior)}
Repair commits since then: {json.dumps(repairs)}

Severity: HIGH = exploitable or criterion clearly unmet; MEDIUM = real defect on a realistic path (blocking: true
unless it is only a documented limitation); LOW = minor. Report only findings with a concrete reproduction or exact
code evidence. Set "owner_decision": true when the only fix needs a protected path, a new dependency, credentials
or an owner policy decision. Set "category": "documentation" for doc-only findings.
Verdict: REJECT if any HIGH or blocking finding.

{_env_notes(cfg)}Your final message must end with exactly one block of valid JSON:
AUDIT_RESULT_BEGIN
{{"candidate": "<sha you verified>", "baseline": "<sha>", "verdict": "ACCEPT | ACCEPT WITH FINDINGS | REJECT",
 "findings": [{{"id": "R{rnd}-01", "severity": "HIGH|MEDIUM|LOW", "blocking": true, "category": "code|security|test|documentation",
   "owner_decision": false, "title": "...", "files": ["path:line"], "evidence": "...", "suggested_fix": "..."}}],
 "prior_findings": [{{"id": "R1-01", "status": "FIXED|NOT_FIXED"}}],
 "tests_run": [{{"command": "...", "result": "...", "status": "COMPLETED_WITH_RESULT|FAILED|BLOCKED"}}],
 "unverified": ["..."]}}
AUDIT_RESULT_END
"""


def repair_prompt(cfg, st: State, findings: list, candidate: str) -> str:
    return f"""You are the IMPLEMENTER repairing URI milestone {cfg['milestone']} at commit {candidate}.
An independent reviewer reported the blocking findings below. Make the minimal, justified repair for each, in this
working tree only. For every code finding add or extend a regression test that FAILS on {candidate} and PASSES after
your change (it will be run both ways). Do not weaken, skip or delete existing tests. Do not touch protected paths:
{', '.join(cfg['protected_paths']) or '(none)'}. Stay inside the permitted paths: {', '.join(cfg['permitted_paths'])}.
Do not commit or push; the driver commits after checking your change. If a finding cannot be fixed within these
limits, do not work around it: report it as not repaired with the reason.

{_env_notes(cfg)}Findings (from the reviewer, verbatim):
{json.dumps(findings, indent=1)}

End your final message with:
REPAIR_RESULT_BEGIN
{{"repaired": ["<finding id>"], "not_repaired": [{{"id": "...", "reason": "..."}}],
 "regression_tests": ["path/to/test_file.py"], "notes": "..."}}
REPAIR_RESULT_END
"""


# --------------------------------------------------------------------------- gates

def _expand(cmd, cfg, wt) -> list[str]:
    py = cfg.get("python") or sys.executable
    return [c.replace("{python}", py).replace("{worktree}", str(wt)).replace("{repo}", cfg["repo"]) for c in cmd]


def _cause(msg: str) -> str:
    msg = (msg or "").strip().splitlines()[0] if (msg or "").strip() else ""
    m = re.match(r"^\s*(?:E\s+)?([A-Za-z_][\w.]*(?:Error|Exception|Exit|Interrupt|Failed|Failure))\b", msg)
    return m.group(1) if m else msg[:80]


def parse_junit(path: Path) -> dict:
    res = {"failures": {}, "passed": 0, "skipped": 0, "ids": [], "parsed": False}
    if not path.is_file():
        return res
    try:
        root = ET.parse(path).getroot()
    except ET.ParseError:
        return res
    res["parsed"] = True
    for tc in root.iter("testcase"):
        tid = f"{tc.get('classname', '')}::{tc.get('name', '')}"
        res["ids"].append(tid)
        bad = tc.find("failure") if tc.find("failure") is not None else tc.find("error")
        if bad is not None:
            res["failures"][tid] = _cause(bad.get("message") or bad.text or "")
        elif tc.find("skipped") is not None:
            res["skipped"] += 1
        else:
            res["passed"] += 1
    return res


def parse_flutter_machine(text: str) -> dict:
    names, res, errs = {}, {"failures": {}, "passed": 0, "skipped": 0, "ids": [], "parsed": False}, {}
    for line in text.splitlines():
        try:
            ev = json.loads(line)
        except ValueError:
            continue
        if not isinstance(ev, dict):
            continue
        t = ev.get("type")
        if t == "testStart":
            tst = ev.get("test") or {}
            src = tst.get("root_url") or tst.get("url") or ""
            i = src.rfind("/test/")  # file:///<any checkout>/uri_ui/test/x_test.dart -> test/x_test.dart
            names[tst.get("id")] = f"{src[i + 1:] if i >= 0 else src}::{tst.get('name')}"
        elif t == "error":
            errs.setdefault(ev.get("testID"), _cause(ev.get("error") or ""))
        elif t == "done":
            res["parsed"] = True
        elif t == "testDone":
            n = names.get(ev.get("testID"), str(ev.get("testID")))
            if not ev.get("hidden"):
                res["ids"].append(n)
            if ev.get("result") != "success":
                res["failures"][n] = errs.get(ev.get("testID"), ev.get("result"))
            elif ev.get("skipped"):
                res["skipped"] += 1
            elif not ev.get("hidden"):
                res["passed"] += 1
    return res


NOBYTECODE = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}


def run_cmd(cmd, cwd, timeout) -> tuple:
    """Run in its own process group; the whole group is killed afterwards (timeout or not)."""
    try:
        p = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                             env=NOBYTECODE, start_new_session=True)
    except OSError as e:
        return None, "", f"cannot start: {e}", "BLOCKED"
    state = "DONE"
    try:
        out, err = p.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        state = "TIMED_OUT"
        _killpg(p.pid)
        out, err = p.communicate()
    _killpg(p.pid)
    return (p.returncode if state == "DONE" else None), out, err, state


def _killpg(pid) -> None:
    try:
        os.killpg(pid, signal.SIGKILL)
    except OSError:
        pass


def run_gate(cfg, gate: dict, wt: Path, log_dir: Path) -> dict:
    kind = gate.get("kind", "command")
    log_dir.mkdir(parents=True, exist_ok=True)
    out = {"id": gate["id"], "kind": kind, "at": now(), "sha": git(wt, "rev-parse", "HEAD")}
    cmd = _expand(gate["cmd"], cfg, wt)
    junit = log_dir / f"{gate['id']}.junit.xml"
    if kind == "pytest":
        cmd += [f"--junitxml={junit}", "-p", "no:cacheprovider"]
    if kind == "flutter" and "--machine" not in cmd:
        cmd.append("--machine")
    if gate.get("gpu"):
        lease = [cfg.get("python") or sys.executable, "-m", "uri_operational_intelligence.gpu_lease"]
        rc, o, e, _ = run_cmd(lease + ["status"], wt, 120)
        if rc != 0:
            out.update(status="BLOCKED", detail="GPU lease unavailable: " + (e or o)[-300:])
            return out
        cmd = lease + ["run", "--purpose", f"lifecycle:{cfg['milestone']}:{gate['id']}",
                       "--wait", str(gate.get("lease_wait_s", 1800)), "--", *cmd]
    out["cmd"] = cmd
    if junit.exists():
        junit.unlink()
    rc, stdout, stderr, state = run_cmd(cmd, wt / gate.get("cwd", "."), gate.get("timeout_s", 3600))
    (log_dir / f"{gate['id']}.log").write_text(stdout + "\n--- stderr ---\n" + stderr, encoding="utf-8")
    if state != "DONE":
        out.update(status=state, detail=stderr[-300:])
        return out
    out["exit_code"] = rc
    run_id = f"{gate['id']}::__run__"
    if kind in ("pytest", "flutter"):
        out.update(parse_junit(junit) if kind == "pytest" else parse_flutter_machine(stdout))
        normal = (0, 1)
        # A crashed run, an unusable report or a failing exit with no recorded failure is itself a failure.
        if not out["parsed"]:
            out["failures"][run_id] = f"exit {rc}: no test report"
        elif rc not in normal or (rc != 0 and not out["failures"]):
            out["failures"][run_id] = f"exit {rc}"
    else:
        out.update({"failures": {run_id: f"exit {rc}"} if rc else {}, "passed": int(not rc), "skipped": 0,
                    "ids": [run_id], "parsed": True})
    out["status"] = "COMPLETED_WITH_RESULT"
    return out


def compare(cand: dict, base: dict | None, flaky) -> dict:
    cf, bf = cand.get("failures", {}), (base or {}).get("failures", {})
    new = sorted(t for t in cf if t not in bf and not match_any(t, flaky))
    changed = sorted(t for t in cf if t in bf and cf[t] != bf[t] and not match_any(t, flaky))
    cand_ids = set(cand.get("ids") or []) | set(cf)
    base_passed = set(base.get("ids") or []) - set(bf) if base else set()
    vanished = sorted(t for t in base_passed - cand_ids if not match_any(t, flaky))
    return {"new_failures": new, "changed_cause": changed, "vanished": vanished,
            "historical_failures": sorted(set(cf) & set(bf)), "fixed": sorted(set(bf) - set(cf)),
            "ok": not new and not changed and not vanished}


def _test_file(test_id: str, wt: Path) -> str:
    head = test_id.split("::")[0]
    for cand in (head, head.replace(".", "/") + ".py"):
        if (wt / cand).is_file():
            return cand
    return head


def qualify(cfg, st: State, sha: str, wt: Path | None = None) -> dict:
    """Run every gate on ``sha`` in a fresh detached worktree (never the implementation worktree, whose
    uncommitted or ignored files must not decide the result) and on the baseline (cached by SHA + command)."""
    own = wt is None
    wt = wt or add_worktree(cfg["repo"], Path(cfg["work_dir"]) / "qualify", sha)
    res = {"sha": sha, "at": now(), "gates": {}, "ok": True, "blocked": None}
    prot = protected_hits(cfg, changed_paths(cfg["repo"], st.d["baseline"], sha))
    res["protected_changed"] = prot
    if prot:
        res["ok"] = False
    log_root = Path(cfg["state_dir"]) / "gates" / sha[:12]
    base_wt = None
    try:
        for g in cfg["gates"]:
            r = run_gate(cfg, g, wt, log_root)
            entry = {"candidate": r}
            if r.get("status") != "COMPLETED_WITH_RESULT":
                entry["ok"] = False
                res["blocked"] = res["blocked"] or f"gate {g['id']}: {r.get('status')} {r.get('detail', '')}"
            else:
                key = chash([st.d["baseline"], g["cmd"], g.get("kind"), g.get("cwd", ".")])
                cached = st.d["baseline_gates"].get(g["id"])
                if not cached or cached.get("key") != key:
                    base_wt = base_wt or add_worktree(cfg["repo"], Path(cfg["work_dir"]) / "baseline", st.d["baseline"])
                    b = run_gate(cfg, g, base_wt, Path(cfg["state_dir"]) / "gates" / "baseline")
                    cached = {"key": key, "result": b}
                    st.d["baseline_gates"][g["id"]] = cached
                    st.event("BASELINE_GATE", gate=g["id"], key=key, status=b.get("status"), result_sha256=chash(cached))
                if cached["result"].get("status") != "COMPLETED_WITH_RESULT":
                    entry["ok"] = False
                    res["blocked"] = res["blocked"] or f"baseline gate {g['id']}: {cached['result'].get('status')}"
                else:
                    entry["comparison"] = compare(r, cached["result"], cfg["allowed_flaky"])
                    entry["ok"] = entry["comparison"]["ok"] or not g.get("required", True)
            res["gates"][g["id"]] = entry
            res["ok"] = res["ok"] and entry["ok"]
    finally:
        if base_wt:
            drop_worktree(cfg["repo"], base_wt)
        if own:
            drop_worktree(cfg["repo"], wt)
    if res["blocked"]:
        res["ok"] = False
    return res


# --------------------------------------------------------------------------- evidence guards

def accepted_review(cfg, st: State, sha: str) -> dict | None:
    for r in reversed(st.d["rounds"]):
        if r.get("candidate") == sha and r.get("independent") and r.get("effective_verdict") in VERDICTS[:2]:
            return r
    return None


def evidence_ok(cfg, st: State, sha: str) -> tuple[bool, list]:
    why = []
    if not accepted_review(cfg, st, sha):
        why.append("no independent ACCEPT on this exact commit")
    q = st.d["gates"].get(sha)
    if not q or not q.get("ok"):
        why.append("qualification gates not passed on this exact commit")
    if protected_hits(cfg, changed_paths(cfg["repo"], st.d["baseline"], sha)):
        why.append("protected paths changed without authorisation")
    errs = verify(cfg)
    if errs:
        why.append("receipt verification failed: " + "; ".join(errs[:5]))
    return not why, why


# --------------------------------------------------------------------------- stages

def do_review(cfg, st: State, sha: str) -> dict:
    rnd = len(st.d["rounds"]) + 1
    rdir = Path(cfg["state_dir"]) / "rounds" / f"R{rnd}"
    awt = add_worktree(cfg["repo"], Path(cfg["work_dir"]) / f"audit_R{rnd}", sha)
    cwt = Path(cfg["candidate"]["worktree"])

    def snap():
        return {"head": git(awt, "rev-parse", "HEAD"), "status": worktree_changes(awt), "refs": refs_digest(cfg),
                "git_control": git_control_digest(cfg["repo"]),
                "impl_head": git(cwt, "rev-parse", "HEAD"), "impl_status": worktree_changes(cwt)}
    before = snap()
    rec = {"round": rnd, "candidate": sha, "baseline": st.d["baseline"], "started_at": now(), "audit_worktree": str(awt)}
    st.d["rounds"].append(rec)
    st.event("REVIEW_STARTED", round=rnd, candidate=sha, provider=cfg["reviewer"].get("provider"))
    try:
        w = run_worker(cfg["reviewer"], "reviewer", review_prompt(cfg, st, rnd, sha), awt, rdir,
                       protected=cfg["protected_paths"], timeout_s=cfg["reviewer"].get("timeout_s", 5400))
        after = snap()
    finally:
        drop_worktree(cfg["repo"], awt)
    integrity = {"before": before, "after": after, "ok": before == after and before["head"] == sha and not after["status"]}
    w.pop("result_text", None)
    text = (rdir / "reviewer_result.txt").read_text(encoding="utf-8") if (rdir / "reviewer_result.txt").is_file() else ""
    result = parse_block(text)
    rec.update(worker=w, integrity=integrity, result=result, ended_at=now())
    ok, why = is_independent(cfg, rec, {(r.get("worker") or {}).get("session_id") for r in st.d["repairs"]})
    rec["independent"], rec["independence_basis"] = ok, why
    if result is None:
        rec["effective_verdict"], rec["status"] = None, "NO_RESULT"
    elif result.get("candidate") != sha:
        rec["effective_verdict"], rec["status"] = None, "WRONG_CANDIDATE"
    else:
        rec["effective_verdict"], blocking = effective_verdict(result)
        rec["blocking_ids"] = [f.get("id") for f in blocking]
        rec["status"] = "COMPLETED_WITH_RESULT" if ok else "NOT_INDEPENDENT"
    write_json(rdir / "round.json", rec)
    st.event("REVIEW_RECORDED", round=rnd, candidate=sha, status=rec["status"], verdict=rec["effective_verdict"],
             reviewer_label=(result or {}).get("verdict"), independent=ok, session_id=w.get("session_id"),
             stdout_sha256=w.get("stdout_sha256"), result_sha256=w.get("result_text_sha256"),
             round_sha256=sha256((rdir / "round.json").read_bytes()))
    return rec


def _fingerprint(f: dict) -> str:
    files = sorted({str(x).split(":")[0] for x in f.get("files") or []})
    words = re.findall(r"[a-z0-9]+", (f.get("title") or "").lower())[:5]
    return "|".join(files) + "#" + " ".join(words)


def count_attempts(cfg, st: State, rec: dict) -> list[str]:
    """Increment per-defect attempt counters; return ids that exceeded the limit."""
    over = []
    res = rec.get("result") or {}
    still = {p.get("id") for p in res.get("prior_findings") or [] if p.get("status") == "NOT_FIXED"}
    origin = {}
    for r in st.d["rounds"][:-1]:
        for f in (r.get("result") or {}).get("findings") or []:
            origin.setdefault(_fingerprint(f), f.get("id"))
    keys = set(still)
    for f in res.get("findings") or []:
        if f.get("severity") == "HIGH" or f.get("blocking"):
            keys.add(origin.get(_fingerprint(f), f.get("id")))
    for k in keys:
        st.d["attempts"][k] = st.d["attempts"].get(k, 0) + 1
        if st.d["attempts"][k] > cfg["limits"]["max_repair_attempts"]:
            over.append(k)
    return over


def _runner_for(cfg, test: str):
    for r in cfg.get("regression_runners") or []:
        if test.endswith(r["suffix"]):
            return r
    if test.endswith(".py") and cfg.get("regression_runner"):
        return {"suffix": ".py", "cmd": cfg["regression_runner"], "cwd": "."}
    return None


def regression_proof(cfg, pre_sha: str, post_sha: str, tests: list[str], log_dir: Path, *, need_fail_before=True,
                     must_fail=frozenset()) -> dict:
    """Run each regression test file on the committed repair and, copied, on the pre-repair commit - both in fresh
    worktrees. Every file must pass after. When a defect is repaired at least one must fail before (and every gate
    test named by a gate finding must). Coverage-only repairs add tests that already pass before."""
    runnable = [(t, _runner_for(cfg, t)) for t in tests]
    runnable = [(t, r) for t, r in runnable if r]
    if not runnable:
        return {"ok": False, "reason": "no runnable regression test (a test file with a configured runner is required)"}
    log_dir.mkdir(parents=True, exist_ok=True)
    per = {}
    pre = add_worktree(cfg["repo"], Path(cfg["work_dir"]) / "pre_repair", pre_sha)
    post = add_worktree(cfg["repo"], Path(cfg["work_dir"]) / "post_repair", post_sha)
    try:
        for t, _ in runnable:
            (pre / t).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(post / t, pre / t)
        for t, r in runnable:
            cwd = r.get("cwd", ".")
            rel = str(Path(t).relative_to(cwd)) if cwd != "." else t
            tmo = r.get("timeout_s", 1800)
            bc, bo, be, bs = run_cmd(_expand(r["cmd"], cfg, pre) + [rel], pre / cwd, tmo)
            ac, ao, ae, as_ = run_cmd(_expand(r["cmd"], cfg, post) + [rel], post / cwd, tmo)
            per[t] = {"before_exit": bc, "after_exit": ac, "before_state": bs, "after_state": as_}
            with (log_dir / "regression.log").open("a", encoding="utf-8") as f:
                f.write(f"=== {t} BEFORE ({pre_sha}) {bs}\n{bo[-6000:]}{be[-3000:]}\n=== {t} AFTER ({post_sha}) {as_}\n"
                        f"{ao[-6000:]}{ae[-3000:]}\n")
    finally:
        drop_worktree(cfg["repo"], pre)
        drop_worktree(cfg["repo"], post)
    reasons = [f"{t} does not pass after the repair ({r['after_state']}, exit {r['after_exit']})"
               for t, r in per.items() if r["after_exit"] != 0]
    reasons += [f"gate test {t} did not fail before the repair" for t in must_fail if per.get(t, {}).get("before_exit") == 0]
    if need_fail_before and not any(r["before_exit"] != 0 for r in per.values()):
        reasons.append("no regression test fails on the pre-repair commit")
    return {"ok": not reasons, "tests": per, "need_fail_before": need_fail_before, "reason": "; ".join(reasons)}


def _restore(wt: Path, sha: str) -> bool:
    """Put the implementation worktree back to ``sha`` exactly (index, files, branch tip)."""
    git(wt, "reset", "-q", "--hard", sha, check=False)
    git(wt, "clean", "-fdq", check=False)
    return git(wt, "rev-parse", "HEAD", check=False) == sha and not worktree_changes(wt)


def do_repair(cfg, st: State, sha: str, findings: list) -> dict:
    wt = Path(cfg["candidate"]["worktree"])
    n = len(st.d["repairs"]) + 1
    rdir = Path(cfg["state_dir"]) / "repairs" / f"P{n}"
    rec = {"repair": n, "pre": sha, "addresses": [f.get("id") for f in findings], "started_at": now()}
    st.d["repairs"].append(rec)

    def finish(status, **kw):
        rec.update(status=status, ended_at=now(), **kw)
        write_json(rdir / "repair.json", rec)
        st.event("REPAIR_COMMITTED" if status == "COMMITTED" else "REPAIR_REFUSED", repair=n, status=status,
                 commit=rec.get("commit"), reason=rec.get("reason"), addresses=rec["addresses"],
                 session_id=(rec.get("worker") or {}).get("session_id"),
                 repair_sha256=sha256((rdir / "repair.json").read_bytes()))
        return rec

    if git(wt, "rev-parse", "HEAD") != sha or worktree_changes(wt):
        return finish("REFUSED", reason="implementation worktree not clean or not at the candidate before repair")
    ctl0, refs0 = git_control_digest(cfg["repo"]), refs_digest(cfg)
    impl = cfg.get("implementer") or {}
    w = run_worker(impl, "implementer", repair_prompt(cfg, st, findings, sha), wt, rdir,
                   protected=cfg["protected_paths"], timeout_s=impl.get("timeout_s", 5400))
    w.pop("result_text", None)
    rec["worker"] = w
    rec["report"] = parse_block((rdir / "implementer_result.txt").read_text(encoding="utf-8")
                                if (rdir / "implementer_result.txt").is_file() else "", REPAIR_RE) or {}
    head = git(wt, "rev-parse", "HEAD")
    changed = worktree_changes(wt)
    rec["changed"] = changed
    reason = None
    if git_control_digest(cfg["repo"]) != ctl0:
        reason = "TAMPER: git hooks or config changed during the repair"
    elif refs_digest(cfg) != refs0 or head != sha:
        reason = "TAMPER: implementer moved HEAD or a milestone ref (commit/checkout is the driver's job)"
    elif w.get("status") != "COMPLETED":
        reason = f"implementer {w.get('status')}"
    elif not changed:
        reason = "no change made"
    elif protected_hits(cfg, changed):
        reason = "PROTECTED: " + ", ".join(protected_hits(cfg, changed))
    elif [p for p in changed if not match_any(p, cfg["permitted_paths"])]:
        reason = "OUT_OF_SCOPE: " + ", ".join(p for p in changed if not match_any(p, cfg["permitted_paths"]))
    if not reason:
        git(wt, "add", "-A", "--", *changed)
        msg = f"fix({cfg['milestone']}): repair {', '.join(map(str, rec['addresses']))} (lifecycle P{n})\n\n" + \
              "Findings from independent review; regression proof in lifecycle receipts.\n"
        if cfg["commit_trailers"]:
            msg += "\n" + "\n".join(cfg["commit_trailers"]) + "\n"
        git(wt, "commit", "-q", "--no-verify", "-m", msg)
        new = git(wt, "rev-parse", "HEAD")
        committed = changed_paths(cfg["repo"], sha, new)
        if set(committed) != set(changed) or protected_hits(cfg, committed) or \
                [p for p in committed if not match_any(p, cfg["permitted_paths"])]:
            reason = f"COMMIT_MISMATCH: committed {committed} != checked {changed}"
        else:
            tests = {p for p in committed if match_any(p, cfg["test_globs"])}
            # A gate finding names an existing test that fails on the candidate: it is its own regression test.
            gate_tests = {str(x).split(":")[0] for f in findings if str(f.get("id", "")).startswith("GATE-")
                          for x in f.get("files") or [] if (wt / str(x).split(":")[0]).is_file()}
            kinds = {f.get("category") or "code" for f in findings}
            defect = bool(kinds - {"documentation", "test"}) or bool(gate_tests)
            if kinds != {"documentation"}:
                proof = regression_proof(cfg, sha, new, sorted(tests | gate_tests), rdir, need_fail_before=defect,
                                         must_fail=gate_tests)
                rec["regression"] = proof
                if not proof["ok"]:
                    reason = "REGRESSION: " + proof["reason"]
            if not reason:
                rec["commit"] = new
                return finish("COMMITTED")
    restored = _restore(wt, sha)
    return finish("REFUSED", reason=reason, restored=restored)


def integrate(cfg, st: State, sha: str) -> None:
    pol = cfg["integration"]
    mode = pol.get("mode", "none")
    ok, why = evidence_ok(cfg, st, sha)
    if not ok:
        st.block("EVIDENCE", "; ".join(why), "re-run audit and gates")
        return
    if mode == "none":
        st.d["integration"] = {"mode": "none", "status": "NOT_INTEGRATED_BY_POLICY", "candidate": sha, "at": now()}
        st.event("INTEGRATION", **st.d["integration"])
        return
    remote, target = pol.get("remote", "origin"), pol["target_ref"]
    git(cfg["repo"], "fetch", "-q", remote, target, check=False)
    tip = (git(cfg["repo"], "ls-remote", remote, f"refs/heads/{target}").split("\t") or [""])[0]
    rec = {"mode": mode, "remote": remote, "target_ref": target, "target_tip_before": tip, "candidate": sha, "at": now()}
    if pol.get("expected_target_tip") and tip != pol["expected_target_tip"]:
        rec["status"] = "REFUSED_TARGET_MOVED"
    elif mode == "fast-forward" and subprocess.run(["git", "-C", cfg["repo"], "merge-base", "--is-ancestor", tip, sha]).returncode:
        rec["status"] = "REFUSED_NOT_FAST_FORWARD"
    if rec.get("status"):
        st.d["integration"] = rec
        st.event("INTEGRATION", **rec)
        st.block("INTEGRATION", rec["status"], "rebase/merge the candidate onto the current target and re-run")
        return
    command = f"git push {remote} {sha}:refs/heads/{target}"
    if not pol.get("authorized"):
        rec.update(status="AWAITING_OWNER_AUTHORIZATION", command=command)
        st.d["integration"] = rec
        st.event("INTEGRATION", **rec)
        st.block("OWNER_AUTHORIZATION", f"integration into {target} needs owner authorisation", command)
        return
    result_sha = sha
    if mode == "merge":
        iwt = add_worktree(cfg["repo"], Path(cfg["work_dir"]) / "integration", tip)
        try:
            m = subprocess.run(["git", "-C", str(iwt), "merge", "--no-ff", "-q", "-m",
                                f"integrate {cfg['milestone']} ({sha[:12]})", sha], capture_output=True, text=True)
            if m.returncode:
                rec.update(status="REFUSED_MERGE_CONFLICT", detail=m.stderr[-400:])
            else:
                result_sha = git(iwt, "rev-parse", "HEAD")
                q = qualify(cfg, st, result_sha, wt=iwt)
                rec["combined_gates"] = {k: v.get("comparison") for k, v in q["gates"].items()}
                if not q["ok"]:
                    rec["status"] = "REFUSED_COMBINED_GATES"
        finally:
            drop_worktree(cfg["repo"], iwt)
        if rec.get("status"):
            st.d["integration"] = rec
            st.event("INTEGRATION", **rec)
            st.block("INTEGRATION", rec["status"], "repair and re-run")
            return
        command = f"git push {remote} {result_sha}:refs/heads/{target}"
    p = subprocess.run(["git", "-C", cfg["repo"], "push", remote, f"{result_sha}:refs/heads/{target}"],
                       capture_output=True, text=True)
    after = git(cfg["repo"], "ls-remote", remote, f"refs/heads/{target}").split("\t")[0]
    rec.update(command=command, push_exit=p.returncode, push_stderr=p.stderr[-400:], target_tip_after=after,
               result_commit=result_sha)
    rec["status"] = "INTEGRATED" if p.returncode == 0 and after == result_sha else "PUSH_FAILED"
    st.d["integration"] = rec
    st.event("INTEGRATION", **{k: v for k, v in rec.items() if k != "combined_gates"})
    if rec["status"] == "INTEGRATED":
        st.to(S.COMPLETE, f"{target} -> {result_sha}")
    else:
        st.block("PERMISSION", "push to integration target failed", rec["push_stderr"] or "owner push permission")


# --------------------------------------------------------------------------- driver

def init(cfg, st: State) -> None:
    repo = cfg["repo"]
    b = cfg["baseline"]
    base = git(repo, "rev-parse", "--verify", b["ref"] + "^{commit}")
    if b.get("expect") and base != b["expect"]:
        raise LifecycleError(f"baseline {b['ref']} is {base}, expected {b['expect']}")
    wt = Path(cfg["candidate"]["worktree"])
    if not wt.exists():
        git(repo, "worktree", "add", "-b", cfg["candidate"]["branch"], str(wt), base)
    st.d.update(baseline=base, candidate=git(wt, "rev-parse", "HEAD"), started_at=now(),
                config_sha256=cfg["_config_sha256"], config_path=cfg["_config_path"])
    st.event("PLAN", baseline=base, candidate=st.d["candidate"], config_sha256=cfg["_config_sha256"],
             acceptance_criteria_file=cfg.get("acceptance_criteria_file"), protected=cfg["protected_paths"],
             permitted=cfg["permitted_paths"], gates=[g["id"] for g in cfg["gates"]],
             reviewer=cfg["reviewer"].get("provider"), integration=cfg["integration"].get("mode"))
    st.to(S.ACCEPTED, "plan recorded from config")


def run(cfg, max_steps: int = 50) -> S:
    st = State(cfg)
    if st.stage is None:
        init(cfg, st)
    errs = verify(cfg)
    if errs and st.stage == S.COMPLETE:  # terminal: record, never re-open silently
        st.event("TAMPER_DETECTED", errors=errs[:10])
        return st.stage
    if errs and st.stage != S.BLOCKED:
        st.block("TAMPER", "receipt verification failed: " + "; ".join(errs[:5]),
                 "owner: investigate; start a fresh state_dir (evidence cannot be trusted)")
    if st.d.get("config_sha256") != cfg["_config_sha256"]:
        st.event("CONFIG_CHANGED", frm=st.d.get("config_sha256"), to=cfg["_config_sha256"])
        st.d["config_sha256"] = cfg["_config_sha256"]
    wt = Path(cfg["candidate"]["worktree"])
    for _ in range(max_steps):
        stage = st.stage
        tip = git(wt, "rev-parse", "HEAD")
        if tip != st.d["candidate"]:
            st.event("CANDIDATE_MOVED", frm=st.d["candidate"], to=tip)
            st.d["candidate"] = tip
            if stage in (S.VERIFYING, S.VERIFIED):
                st.block("EVIDENCE", "candidate changed after audit", "re-audit")
                continue
        sha = st.d["candidate"]
        if stage == S.ACCEPTED:
            impl = cfg.get("implement")
            st.to(S.IMPLEMENTING, "implementation stage")
            if impl and not impl.get("done"):
                st.event("IMPLEMENT_EXTERNAL", note="initial implementation is produced in the candidate worktree "
                                                    "before `run`; the driver records it")
            continue
        if stage == S.IMPLEMENTING:
            if sha == st.d["baseline"]:
                st.block("NO_IMPLEMENTATION", "candidate equals baseline", "implement first")
                continue
            st.event("IMPLEMENTATION_RECORDED", candidate=sha, files=changed_paths(cfg["repo"], st.d["baseline"], sha))
            st.to(S.AUDITING, "implementation committed")
            continue
        if stage in (S.WAITING_FOR_MODEL, S.READY_TO_RESUME):
            if stage == S.WAITING_FOR_MODEL:
                st.to(S.READY_TO_RESUME, "retrying the reviewer")
            st.to(S(st.d.get("resume_to") or S.AUDITING.value), "resume")
            continue
        if stage == S.AUDITING:
            if len(st.d["rounds"]) >= cfg["limits"]["max_rounds"]:
                st.block("ROUND_LIMIT", f"{len(st.d['rounds'])} review rounds", "owner review of the open findings")
                continue
            rec = do_review(cfg, st, sha)
            stricter = rec["status"] == "NOT_INDEPENDENT" and rec["effective_verdict"] == "REJECT" and rec.get("blocking_ids")
            if stricter:  # a non-independent review may only make the outcome stricter
                st.event("NON_INDEPENDENT_REJECT_ROUTED", round=rec["round"], basis=rec["independence_basis"])
            if rec["status"] != "COMPLETED_WITH_RESULT" and not stricter:
                st.d["resume_to"] = S.AUDITING.value
                st.to(S.WAITING_FOR_MODEL, f"review R{rec['round']}: {rec['status']} ({rec['independence_basis']})")
                return st.stage
            if rec["effective_verdict"] == "REJECT":
                res = rec["result"]
                blocking = [f for f in res.get("findings") or [] if f.get("id") in rec["blocking_ids"]]
                extra = [f for f in res.get("findings") or [] if f.get("id") not in rec["blocking_ids"]
                         and f.get("severity") in cfg.get("repair_nonblocking_severities", [])]
                owner = [f for f in blocking if f.get("owner_decision")]
                if owner:
                    st.block("OWNER_DECISION", "; ".join(f"{f['id']}: {f.get('title')}" for f in owner),
                             "owner decision on the listed findings")
                    continue
                over = count_attempts(cfg, st, rec)
                if over:
                    st.block("RETRY_LIMIT", f"still failing after {cfg['limits']['max_repair_attempts']} repairs: "
                             + ", ".join(map(str, over)), "owner or a more capable implementer")
                    continue
                if not blocking:
                    st.block("NO_ACTIONABLE_FINDINGS", "REJECT without a blocking finding", "owner review of R"
                             + str(rec["round"]))
                    continue
                st.d["pending_findings"] = blocking + extra
                st.to(S.FIXING, f"R{rec['round']} REJECT: {len(blocking)} blocking, {len(extra)} non-blocking routed")
                continue
            st.to(S.VERIFYING, f"R{rec['round']} {rec['effective_verdict']}")
            continue
        if stage == S.FIXING:
            rep = do_repair(cfg, st, sha, st.d.get("pending_findings") or [])
            if rep["status"] == "COMMITTED":
                st.d["candidate"] = rep["commit"]
                st.d["pending_findings"] = []
                st.to(S.AUDITING, f"repair P{rep['repair']} {rep['commit'][:12]}")
                continue
            kind = "OWNER_DECISION" if rep["reason"].startswith(("PROTECTED", "OUT_OF_SCOPE")) else "REPAIR_FAILED"
            if rep["reason"].startswith("TAMPER") or not rep.get("restored", True):
                st.block("TAMPER", rep["reason"] + ("" if rep.get("restored", True) else "; worktree NOT restored"),
                         "owner: inspect the implementation worktree and git hooks/config")
                continue
            fails = sum(1 for r in st.d["repairs"] if r.get("status") == "REFUSED" and r.get("pre") == sha)
            if kind == "REPAIR_FAILED" and fails < cfg["limits"]["max_repair_attempts"]:
                st.event("REPAIR_RETRY", attempt=fails, reason=rep["reason"])
                continue
            st.block(kind, rep["reason"], "owner decision" if kind == "OWNER_DECISION" else "manual repair")
            continue
        if stage == S.VERIFYING:
            q = qualify(cfg, st, sha)
            st.d["gates"][sha] = q
            st.event("QUALIFICATION", sha=sha, ok=q["ok"], blocked=q["blocked"], protected=q["protected_changed"],
                     qual_sha256=chash(q),
                     gates={k: (v.get("comparison") or {}).get("new_failures") for k, v in q["gates"].items()})
            if q["blocked"]:
                st.block("RESOURCE", q["blocked"], "provide the resource and re-run")
                continue
            if q["protected_changed"]:
                st.block("OWNER_DECISION", "protected paths changed: " + ", ".join(q["protected_changed"]),
                         "owner authorisation (authorized_protected_changes) or revert")
                continue
            if not q["ok"]:
                findings = []
                for gid, e in q["gates"].items():
                    c = e.get("comparison") or {}
                    for t in (c.get("new_failures") or []) + (c.get("changed_cause") or []):
                        findings.append({"id": f"GATE-{gid}-{len(findings) + 1}", "severity": "HIGH", "blocking": True,
                                         "category": "test", "title": f"gate {gid}: new failure {t}",
                                         "files": [_test_file(t, wt)],
                                         "evidence": e["candidate"].get("failures", {}).get(t, "")})
                over = []
                for f in findings:
                    st.d["attempts"][f["title"]] = st.d["attempts"].get(f["title"], 0) + 1
                    if st.d["attempts"][f["title"]] > cfg["limits"]["max_repair_attempts"]:
                        over.append(f["title"])
                if over:
                    st.block("RETRY_LIMIT", "; ".join(over), "owner")
                    continue
                st.d["pending_findings"] = findings
                st.to(S.FIXING, f"{len(findings)} new gate failure(s)")
                continue
            ok, why = evidence_ok(cfg, st, sha)
            if not ok:
                st.block("EVIDENCE", "; ".join(why), "re-audit")
                continue
            st.to(S.VERIFIED, f"independent {accepted_review(cfg, st, sha)['effective_verdict']} + gates on {sha[:12]}")
            continue
        if stage == S.VERIFIED:
            ok, why = evidence_ok(cfg, st, sha)
            if not ok:
                st.block("EVIDENCE", "VERIFIED without evidence: " + "; ".join(why), "re-audit")
                continue
            integrate(cfg, st, sha)
            if st.stage == S.VERIFIED:
                write_receipt(cfg, st)
                return st.stage
            continue
        write_receipt(cfg, st)
        return st.stage
    st.block("STEP_LIMIT", f"driver exceeded {max_steps} steps", "inspect state")
    write_receipt(cfg, st)
    return st.stage


def import_review(cfg, result_file: Path, provider: str, session_id: str, source: str) -> S:
    """Record a review produced outside the driver (e.g. a separate cloud session) whose text was relayed.

    A relayed review can only make the outcome stricter: its findings are routed to repair, but it is never
    independent evidence for VERIFIED (the coordinator transcribed it).
    """
    st = State(cfg)
    if st.stage is None:
        init(cfg, st)
        st.to(S.IMPLEMENTING, "implementation exists")
        st.to(S.AUDITING, "external review imported")
    if st.stage != S.AUDITING:
        raise LifecycleError(f"import-review needs stage AUDITING, not {st.d['stage']}")
    text = Path(result_file).read_text(encoding="utf-8")
    result = parse_block(text)
    sha = st.d["candidate"]
    rnd = len(st.d["rounds"]) + 1
    rdir = Path(cfg["state_dir"]) / "rounds" / f"R{rnd}"
    rdir.mkdir(parents=True, exist_ok=True)
    (rdir / "reviewer_result.txt").write_text(text, encoding="utf-8")
    reviewed = (result or {}).get("candidate")
    same_tree = bool(reviewed) and git(cfg["repo"], "rev-parse", f"{reviewed}^{{tree}}", check=False) == \
        git(cfg["repo"], "rev-parse", f"{sha}^{{tree}}")
    rec = {"round": rnd, "candidate": sha, "baseline": st.d["baseline"], "imported": True, "source": source,
           "reviewed_commit": reviewed, "same_tree_as_candidate": same_tree, "result": result,
           "worker": {"provider": provider, "session_id": session_id, "status": "RELAYED",
                      "stdout_sha256": sha256(text)},
           "independent": False, "independence_basis": "relayed by the coordinator: may only tighten the outcome",
           "started_at": now(), "ended_at": now()}
    if result is None:
        rec.update(status="NO_RESULT", effective_verdict=None)
    else:
        rec["effective_verdict"], blocking = effective_verdict(result)
        rec["blocking_ids"] = [f.get("id") for f in blocking]
        rec["status"] = "IMPORTED"
    st.d["rounds"].append(rec)
    write_json(rdir / "round.json", rec)
    st.event("REVIEW_RECORDED", round=rnd, candidate=sha, status=rec["status"], verdict=rec["effective_verdict"],
             reviewer_label=(result or {}).get("verdict"), independent=False, session_id=session_id,
             stdout_sha256=sha256(text), result_sha256=sha256(text), imported=True, source=source,
             round_sha256=sha256((rdir / "round.json").read_bytes()))
    if rec.get("effective_verdict") == "REJECT":
        res = rec["result"]
        blocking = [f for f in res.get("findings") or [] if f.get("id") in rec["blocking_ids"]]
        extra = [f for f in res.get("findings") or [] if f.get("id") not in rec["blocking_ids"]
                 and f.get("severity") in cfg.get("repair_nonblocking_severities", [])]
        owner = [f for f in blocking if f.get("owner_decision")]
        if owner:
            st.block("OWNER_DECISION", "; ".join(f"{f['id']}: {f.get('title')}" for f in owner), "owner decision")
        elif blocking:
            count_attempts(cfg, st, rec)
            st.d["pending_findings"] = blocking + extra
            st.to(S.FIXING, f"imported R{rnd} REJECT: {len(blocking)} blocking, {len(extra)} non-blocking routed")
    return st.stage


def unblock(cfg, note: str) -> S:
    st = State(cfg)
    if st.stage != S.BLOCKED:
        raise LifecycleError(f"stage is {st.d['stage']}, not BLOCKED")
    st.event("OWNER_UNBLOCK", note=note, blocker=st.d["blocker"])
    st.d["blocker"] = None
    st.to(S.READY_TO_RESUME, "owner: " + note)
    return st.stage


def verify(cfg) -> list[str]:
    """Recompute the event chain and check state.json and every stored record against it.

    Tamper-evident, not tamper-proof: someone who can rewrite the whole state directory can rebuild a consistent
    chain. Anchor it by committing the receipts (the event head hash is in receipt.json)."""
    st = State(cfg)
    errs, prev = [], "0" * 64
    rows = st.events_path.read_text(encoding="utf-8").splitlines() if st.events_path.is_file() else []
    evs = []
    for line in rows:
        ev = json.loads(line)
        h = sha256(json.dumps({k: ev[k] for k in ("seq", "ts", "kind", "data", "prev")}, sort_keys=True))
        if ev["prev"] != prev or ev["hash"] != h:
            errs.append(f"event {ev['seq']} chain broken")
        prev = ev["hash"]
        evs.append(ev)
    if len(rows) != len(st.d["history"]) or any(a["hash"] != b["hash"] for a, b in zip(st.d["history"], evs)):
        errs.append("state history and event log differ")
    rounds = {r.get("round"): r for r in st.d["rounds"]}
    repairs = {r.get("repair"): r for r in st.d["repairs"]}
    seen_rounds, seen_repairs, quals, bases = set(), set(), {}, {}
    for ev in evs:
        d, k = ev["data"], ev["kind"]
        if k == "PLAN" and d.get("baseline") != st.d.get("baseline"):
            errs.append("baseline in state differs from the plan event")
        if k == "REVIEW_RECORDED":
            seen_rounds.add(d["round"])
            rdir = st.dir / "rounds" / f"R{d['round']}"
            f = rdir / "round.json"
            if not f.is_file() or sha256(f.read_bytes()) != d["round_sha256"]:
                errs.append(f"R{d['round']} round.json missing or changed after recording")
                continue
            raw = rdir / ("reviewer_result.txt" if d.get("imported") else "reviewer_stdout.txt")
            if raw.is_file() and sha256(raw.read_bytes()) != d["stdout_sha256"]:
                errs.append(f"R{d['round']} reviewer output changed after recording")
            rec = json.loads(f.read_text(encoding="utf-8"))
            if rec.get("effective_verdict") != d["verdict"]:
                errs.append(f"R{d['round']} verdict differs from the recorded event")
            mine = rounds.get(d["round"]) or {}
            for key in ("candidate", "effective_verdict", "independent", "status", "result"):
                if mine.get(key) != rec.get(key):
                    errs.append(f"R{d['round']} {key} in state.json differs from round.json")
        if k in ("REPAIR_COMMITTED", "REPAIR_REFUSED"):
            seen_repairs.add(d["repair"])
            f = st.dir / "repairs" / f"P{d['repair']}" / "repair.json"
            if not f.is_file() or sha256(f.read_bytes()) != d["repair_sha256"]:
                errs.append(f"P{d['repair']} repair.json missing or changed after recording")
                continue
            rec = json.loads(f.read_text(encoding="utf-8"))
            mine = repairs.get(d["repair"]) or {}
            for key in ("status", "commit", "pre"):
                if mine.get(key) != rec.get(key):
                    errs.append(f"P{d['repair']} {key} in state.json differs from repair.json")
        if k == "QUALIFICATION":
            quals[d["sha"]] = d.get("qual_sha256")
        if k == "BASELINE_GATE":
            bases[d["gate"]] = d.get("result_sha256")
    for n, r in rounds.items():
        if "status" in r and n not in seen_rounds:
            errs.append(f"R{n} in state.json has no recorded review event")
    for n, r in repairs.items():
        if "status" in r and n not in seen_repairs:
            errs.append(f"P{n} in state.json has no recorded repair event")
    for sha, q in st.d["gates"].items():
        if quals.get(sha) != chash(q):
            errs.append(f"gate results for {sha[:12]} differ from the qualification event")
    for gid, c in st.d["baseline_gates"].items():
        if bases.get(gid) != chash(c):
            errs.append(f"baseline gate {gid} differs from its recorded event")
    stages = [e["data"]["stage"] for e in evs if e["kind"] == "STAGE"]
    if (stages[-1] if stages else None) != st.d.get("stage"):
        errs.append("stage in state.json differs from the last stage event")
    return errs


# --------------------------------------------------------------------------- status and receipts

def status(cfg) -> dict:
    st = State(cfg)
    d = st.d
    last = d["rounds"][-1] if d["rounds"] else {}
    open_f = [] if not last else [f for f in (last.get("result") or {}).get("findings") or []]
    return {"schema": SCHEMA, "milestone": d["milestone"], "stage": d["stage"], "baseline": d["baseline"],
            "candidate": d["candidate"], "rounds": len(d["rounds"]),
            "reviewers": [{"round": r["round"], "provider": (r.get("worker") or {}).get("provider"),
                           "session_id": (r.get("worker") or {}).get("session_id"),
                           "models": (r.get("worker") or {}).get("models_used"), "candidate": r["candidate"],
                           "verdict": r.get("effective_verdict"), "reviewer_label": (r.get("result") or {}).get("verdict"),
                           "independent": r.get("independent"), "status": r.get("status")} for r in d["rounds"]],
            "repairs": [{"repair": r["repair"], "status": r.get("status"), "commit": r.get("commit"),
                         "addresses": r.get("addresses"), "reason": r.get("reason")} for r in d["repairs"]],
            "open_findings": [{"id": f.get("id"), "severity": f.get("severity"), "blocking": f.get("blocking"),
                               "title": f.get("title")} for f in open_f],
            "gates": {sha[:12]: {"ok": q.get("ok"), "blocked": q.get("blocked"),
                                 "new_failures": {k: (v.get("comparison") or {}).get("new_failures")
                                                  for k, v in q["gates"].items()}} for sha, q in d["gates"].items()},
            "integration": d.get("integration"), "blocker": d.get("blocker"), "events": len(d["history"]),
            "evidence_ok_for_candidate": evidence_ok(cfg, st, d["candidate"])[0] if d["candidate"] else False}


def status_surface(cfg):
    """Developer Console view as a validated A2UI surface (existing catalog; not wired into the UI)."""
    from uri_a2ui.surface import Surface
    s = status(cfg)
    comps = []

    def text(cid, v, variant="body"):
        comps.append({"id": cid, "component": "Text", "text": str(v)[:400].replace("://", ": //"), "variant": variant})
        return cid
    tone = {"COMPLETE": "success", "VERIFIED": "success", "BLOCKED": "danger", "NOT_VERIFIED": "danger"}
    kids = [text("t", f"Lifecycle {s['milestone']}", "title")]
    comps.append({"id": "stage", "component": "Badge", "text": s["stage"] or "-", "tone": tone.get(s["stage"], "neutral")})
    kids.append("stage")
    kids.append(text("c", f"baseline {str(s['baseline'])[:12]} · candidate {str(s['candidate'])[:12]} · "
                          f"{s['rounds']} review round(s)", "caption"))
    for r in s["reviewers"][-4:]:
        kids.append(text(f"r{r['round']}", f"R{r['round']} {r['provider']} {r['session_id']} -> {r['verdict']} "
                                           f"(independent: {r['independent']})", "caption"))
    for i, f in enumerate(s["open_findings"][:6]):
        kids.append(text(f"f{i}", f"{f['id']} {f['severity']} {f['title']}", "caption"))
    if s["blocker"]:
        kids.append(text("b", f"Blocked: {s['blocker']['kind']} — needs {s['blocker']['needs']}", "label"))
    comps.append({"id": "root", "component": "Column", "children": kids, "gap": "small"})
    comps.insert(0, comps.pop())
    return Surface(surface_id="dev.lifecycle." + re.sub(r"[^A-Za-z0-9_.-]", "_", s["milestone"])[:40],
                   kind="dev.lifecycle", components=comps, placement="workspace", title="Development lifecycle")


def write_receipt(cfg, st: State) -> Path:
    s = status(cfg)
    s["verify_errors"] = verify(cfg)
    s["config_sha256"] = st.d.get("config_sha256")
    s["written_at"] = now()
    write_json(st.dir / "receipt.json", s)
    L = [f"# Lifecycle receipt — {s['milestone']}", "",
         f"Stage: **{s['stage']}** · baseline `{s['baseline']}` · candidate `{s['candidate']}` · "
         f"events {s['events']} · chain {'OK' if not s['verify_errors'] else 'BROKEN: ' + '; '.join(s['verify_errors'])}",
         "", "## Review rounds", "", "| Round | Provider | Session | Candidate | Reviewer label | Effective | Independent | Status |",
         "|---|---|---|---|---|---|---|---|"]
    for r in s["reviewers"]:
        L.append(f"| R{r['round']} | {r['provider']} | `{r['session_id']}` | `{r['candidate'][:12]}` | {r['reviewer_label']} "
                 f"| {r['verdict']} | {r['independent']} | {r['status']} |")
    L += ["", "## Repairs", "", "| # | Status | Commit | Addresses | Reason |", "|---|---|---|---|---|"]
    for r in s["repairs"]:
        L.append(f"| P{r['repair']} | {r['status']} | `{r['commit'] or '-'}` | {', '.join(map(str, r['addresses'] or []))} "
                 f"| {r['reason'] or ''} |")
    L += ["", "## Qualification", ""]
    for sha, g in s["gates"].items():
        L.append(f"- `{sha}`: ok={g['ok']} blocked={g['blocked']} new failures={json.dumps(g['new_failures'])}")
    L += ["", "## Open findings (latest round)", ""] + [f"- {f['id']} {f['severity']} blocking={f['blocking']}: {f['title']}"
                                                        for f in s["open_findings"]]
    L += ["", "## Integration", "", f"```\n{json.dumps(s['integration'], indent=1)}\n```", "",
          "## Blocker", "", f"```\n{json.dumps(s['blocker'], indent=1)}\n```", ""]
    (st.dir / "RECEIPT.md").write_text("\n".join(L), encoding="utf-8")
    return st.dir / "receipt.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m scripts.dev_workflow.lifecycle")
    ap.add_argument("cmd", choices=["run", "status", "verify", "unblock", "receipt", "import-review"])
    ap.add_argument("config")
    ap.add_argument("--a2ui", action="store_true")
    ap.add_argument("--note", default="")
    ap.add_argument("--file")
    ap.add_argument("--provider", default="ccr_session")
    ap.add_argument("--session-id", default="")
    ap.add_argument("--source", default="")
    a = ap.parse_args(argv)
    try:
        cfg = load_config(a.config)
        if a.cmd == "run":
            stage = run(cfg)
            print(json.dumps(status(cfg), indent=1))
            return EXIT.get(stage, 1)
        if a.cmd == "status":
            print(json.dumps(status_surface(cfg).messages() if a.a2ui else status(cfg), indent=1))
            return 0
        if a.cmd == "verify":
            errs = verify(cfg)
            print(json.dumps({"ok": not errs, "errors": errs}, indent=1))
            return 0 if not errs else 1
        if a.cmd == "import-review":
            print(import_review(cfg, Path(a.file), a.provider, a.session_id, a.source).value)
            return 0
        if a.cmd == "receipt":
            print(write_receipt(cfg, State(cfg)))
            return 0
        if not a.note:
            raise LifecycleError("--note with the owner's decision is required")
        print(unblock(cfg, a.note).value)
        return 0
    except (LifecycleError, InvalidTransitionError) as e:
        print(json.dumps({"error": str(e)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
