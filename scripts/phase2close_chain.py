"""Phase 2 closure regression chain (2026-10-08). Runs every gate SEQUENTIALLY (the Phase 1 full suite rewrites part of
the source pin, so nothing runs concurrently) and writes one evidence directory. It never cuts a candidate itself; it
prints a summary and exits non-zero when any gate's outcome is not the expected one, so a candidate is only cut from a
green chain (lesson of review round 3: suite counts alone are not enough).

Gates, in order:
  1. phase2        python -I scripts/phase2d_regression.py phase2          (all Phase 2 suites, incl. tests/phase2ops)
  2. authority     ... authority                                           (Phase 1 authority suites; baseline 134)
  3. phase1-full   ... phase1-full                                         (baseline 2675 passed / 12 skipped / 11 failed)
                   Operational qualification (review round 1, OQ-R1-4): run with OLLAMA_BASE_URL pointed at an unreachable
                   port so a local Ollama service outside the tree cannot turn opt-in live tests on (the baseline ran with
                   no Ollama listening). Review round 2 (OQ-R2-1): PASS only when, per test, nothing regressed: the SAME
                   failure IDs; the SAME total; every skip (location + reason, URLs normalised) is one the baseline also
                   had, never more of one kind; and every baseline skip that disappeared is matched by a named PASSED test
                   of the same file (a live test that hard-codes 127.0.0.1:11434 passes while Ollama runs on this PC).
     2b. phase1-scope  no file the Phase 1 suite collects or imports changed since the accepted closure candidate -f:
                   every path that differs from -f (or is new / modified vs HEAD) lies in Phase 2-only scope, and nothing
                   outside that scope imports the Phase 2 packages or scripts.
  4. residue       removes ONLY the two zero-byte files the Phase 1 full suite plants at the tree root
  5. flutter       flutter test (whole uri_ui/test)
  6. bridge xN     scripts/phase2ops_validate_ui_bridge.py, N runs, + every CLIENT_REFUSAL line of each server log
  7. native        scripts/phase2ops_native_execution.py --provider codex_cli --model gpt-6-sol   (REAL Codex; optional)
  8. native-worker scripts/phase2oq_native_worker.py (operational qualification, EXE-1): REAL server + worker processes
                   with the NATIVE codex.exe (pinned launch chain, client-profile CODEX_HOME, Windows sandbox) against
                   the scripted local endpoint: the not-logged-in profile fails closed (W), no sandbox mode / the npm
                   launcher invalidate the record (W2, W3), and the worker-environment lifecycle reaches a verified
                   receipt and a mid-run cancel with no surviving process (L, auth gate substituted, not PA-10)

Usage: .venv/Scripts/python.exe -I scripts/phase2close_chain.py <evidence_dir> [--bridge-runs 10] [--no-native] [--only g1,g2]
"""
import argparse
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RESIDUE = ("STALE_BOOTSTRAP_EXECUTED", "STALE_LAZY_EXECUTED")


def run(cmd, log, cwd=ROOT, env=None, timeout=7200):
    t0 = time.time()
    with open(log, "wb") as fh:
        fh.write((" ".join(map(str, cmd)) + "\n").encode())
        fh.flush()
        try:
            r = subprocess.run(cmd, cwd=str(cwd), stdout=fh, stderr=subprocess.STDOUT, stdin=subprocess.DEVNULL,
                               env=env, timeout=timeout)
            code = r.returncode
        except subprocess.TimeoutExpired:
            code = "TIMED_OUT"
        fh.write(f"\nEXIT={code} DURATION_S={round(time.time() - t0, 1)}\n".encode())
    return code


def pytest_counts(log):
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    tail = [l for l in text.splitlines() if re.search(r"\d+ (passed|failed)", l)]
    line = tail[-1] if tail else ""
    get = lambda k: int(m.group(1)) if (m := re.search(r"(\d+) " + k, line)) else 0
    return {"passed": get("passed"), "failed": get("failed"), "skipped": get("skipped"), "errors": get("error"), "line": line.strip()}


def failed_ids(log):
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    return sorted(set(m.strip() for m in re.findall(r"^FAILED (.+?)(?: - .*)?\r?$", text, re.M)))


SKIP_RE = re.compile(r"^SKIPPED \[(\d+)\] (\S+?):(\d+): (.*)$", re.M)


def skip_multiset(log):
    """{(file, line, reason with URLs/OS error detail normalised): count} from a `-rs` summary."""
    out = {}
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    for n, loc, line, reason in SKIP_RE.findall(text):
        reason = re.sub(r"https?://\S+", "<URL>", reason)
        reason = re.sub(r"<URL>:? <urlopen error.*$", "<URL>", reason).strip()
        key = (loc.replace("\\", "/").split("/")[-1], line, reason)
        out[key] = out.get(key, 0) + int(n)
    return out


def passed_ids(log):
    text = Path(log).read_text(encoding="utf-8", errors="replace")
    return sorted(set(m.strip() for m in re.findall(r"^PASSED (.+?)\r?$", text, re.M)))


BASELINE_TOTAL = 2675 + 12 + 11


COLLECTION_BASELINE = ROOT.parent / "evidence" / "phase2oq" / "phase1_collection_baseline.txt"


def phase1_collection(log_path):
    """Test IDs the Phase 1 full scope collects (same ignores as the run), written to `log_path`. Sorted list."""
    run([PY, "-I", "scripts/phase2d_regression.py", "phase1-full", "--", "--collect-only"], log_path, timeout=1800,
        env={**os.environ, "OLLAMA_BASE_URL": "http://127.0.0.1:9"})
    text = Path(log_path).read_text(encoding="utf-8", errors="replace")
    return sorted(set(l.strip() for l in text.splitlines() if "::" in l and not l.startswith(("RUN", "ERROR", "FAILED"))))


def phase1_equivalence(log, baseline_log, counts, collected=None, baseline_collection=None):
    """OQ-R2-1: per-test non-regression of a Phase 1 full run against the baseline log. Returns (ok, details).
    `collected` / `baseline_collection` (test IDs): when given they must be identical, so a missing test can never be
    offset by a new one; every passed and failed ID must belong to the collection."""
    now, base = failed_ids(log), failed_ids(baseline_log)
    total = counts["passed"] + counts["skipped"] + counts["failed"] + counts["errors"]
    s_now, s_base = skip_multiset(log), skip_multiset(baseline_log)
    extra = {"|".join(k): v - s_base.get(k, 0) for k, v in s_now.items() if v > s_base.get(k, 0)}
    gone = {k: n - s_now.get(k, 0) for k, n in s_base.items() if n > s_now.get(k, 0)}
    passes = passed_ids(log)
    unmatched = {"|".join(k): n for k, n in gone.items()
                 if k[0] == "unittest.py" or sum(1 for pid in passes if pid.split("::")[0].split("/")[-1] == k[0]) < n}
    details = {"failed_ids": now, "SAME_FAILURE_SET": now == base, "total": total, "baseline_total": BASELINE_TOTAL,
               "skips_not_in_baseline": extra, "baseline_skips_gone": {"|".join(k): n for k, n in gone.items()},
               "gone_skips_without_named_pass": unmatched, "passed_ids_recorded": len(passes)}
    ok = (now == base and counts["errors"] == 0 and total == BASELINE_TOTAL and not extra and not unmatched
          and len(passes) == counts["passed"])
    if collected is not None or baseline_collection is not None:
        coll, bcoll = set(collected or ()), set(baseline_collection or ())
        missing, added = sorted(bcoll - coll), sorted(coll - bcoll)
        stray = sorted(t for t in passes + now if t not in coll)
        details.update(collection_size=len(coll), baseline_collection_size=len(bcoll), collection_missing=missing[:20],
                       collection_added=added[:20], results_outside_collection=stray[:20])
        ok = ok and not missing and not added and not stray and len(coll) == BASELINE_TOTAL
    return ok, details


PHASE2_SCOPE = ("tests/phase2", "uri_supervisor/", "uri_supervisor_bridge/", "uri_ui/", "docs/", "scripts/phase2",
                "scripts/run_uri_supervised_worker.py", "scripts/run_uri_phase2_server.py", "evidence/", "work/")
# Working-system integration (owner decision WS-D3): EXACT new paths, enumerated and matched by equality, never as a
# prefix (Codex WS rounds 1-2, F5). Phase 1 never imports them; the importer check below still enforces that.
WS_EXACT = frozenset((
    "OI_MATERIALIZATION_RECEIPT.json",
    "model_lab/integration/local_brain.json",
    "model_lab/integration/local_brain.py",
    "model_lab/integration/prove_integration.py",
    "model_lab/lab/cases.py",
    "model_lab/lab/client.py",
    "model_lab/lab/decision.py",
    "model_lab/lab/hard.py",
    "model_lab/lab/longctx.py",
    "model_lab/lab/paired.py",
    "model_lab/lab/prompts.py",
    "model_lab/lab/runtime.py",
    "model_lab/lab/vision.py",
    "scripts/oi_materialize_test_runtime.py",
    "scripts/run_uri_integrated_server.py",
    "scripts/run_uri_integrated_worker.py",
    "scripts/ws_brain_host.py",
    "scripts/ws_frozen_check.py",
    "scripts/ws_provision.py",
    "scripts/ws_server_identity.py",
    "tests/oi/__init__.py",
    "tests/oi/conftest.py",
    "tests/oi/fake_llama.py",
    "tests/oi/test_oi_answer_planner_ledger.py",
    "tests/oi/test_oi_audit_r1_regressions.py",
    "tests/oi/test_oi_audit_r2_regressions.py",
    "tests/oi/test_oi_audit_r3_regressions.py",
    "tests/oi/test_oi_audit_r5_regressions.py",
    "tests/oi/test_oi_brain_client.py",
    "tests/oi/test_oi_core_live.py",
    "tests/oi/test_oi_core_provider.py",
    "tests/oi/test_oi_orchestrator.py",
    "tests/oi/test_oi_policy_triage.py",
    "tests/oi/test_oi_runtime_v1.py",
    "tests/oi/test_oi_server.py",
    "tests/ws/__init__.py",
    "tests/ws/test_ws_cloud_and_composition.py",
    "tests/ws/test_ws_hardening.py",
    "tests/ws/test_ws_worker_bridge.py",
    "tests/ws/test_ws_worker_live.py",
    "uri_operational_intelligence/__init__.py",
    "uri_operational_intelligence/answer.py",
    "uri_operational_intelligence/bench/__init__.py",
    "uri_operational_intelligence/bench/no_mtp_compare.py",
    "uri_operational_intelligence/bench/reasoning.py",
    "uri_operational_intelligence/bench/suite_p.py",
    "uri_operational_intelligence/bench/tasks.py",
    "uri_operational_intelligence/brain_catalog.py",
    "uri_operational_intelligence/brain_client.py",
    "uri_operational_intelligence/brain_health.py",
    "uri_operational_intelligence/cloud_policy.py",
    "uri_operational_intelligence/core_provider.py",
    "uri_operational_intelligence/events.py",
    "uri_operational_intelligence/gpu_lease.py",
    "uri_operational_intelligence/harness_choice.py",
    "uri_operational_intelligence/host.py",
    "uri_operational_intelligence/integrated_composition.py",
    "uri_operational_intelligence/orchestrator.py",
    "uri_operational_intelligence/perf_monitor.py",
    "uri_operational_intelligence/planner.py",
    "uri_operational_intelligence/reasoning_policy.py",
    "uri_operational_intelligence/runtime_v1.py",
    "uri_operational_intelligence/server.py",
    "uri_operational_intelligence/task_ledger.py",
    "uri_operational_intelligence/triage.py",
    "uri_operational_intelligence/worker_bridge.py",
    "work/oi/.gitignore",
    # URI Scheduler (docs/scheduler/SCHEDULER_ARCHITECTURE.md): EXACT new paths, same WS-D3 rule.
    "scripts/scheduler_live_test.py",
    "scripts/scheduler_task_ctl.ps1",
    "tests/scheduler/fixtures/diwali_scene.json",
    "tests/scheduler/helpers/fake_claude.py",
    "tests/scheduler/test_engine.py",
    "tests/scheduler/test_renderer_gif.py",
    "tests/scheduler/test_service_process.py",
    "tests/scheduler/test_supervised.py",
    "tests/scheduler/test_task_ctl.py",
    "tests/scheduler/test_timespec_calendar.py",
    "uri_scheduler/__init__.py",
    "uri_scheduler/calendar_store.py",
    "uri_scheduler/data/in_festivals.json",
    "uri_scheduler/engine.py",
    "uri_scheduler/gif_task.py",
    "uri_scheduler/harness.py",
    "uri_scheduler/renderer.py",
    "uri_scheduler/service.py",
    "uri_scheduler/store.py",
    "uri_scheduler/timespec.py",
    # URI A2UI (docs/a2ui/A2UI_ARCHITECTURE.md): EXACT new paths, same WS-D3 rule.
    "scripts/a2ui_live_check.py",
    "tests/a2ui/fixtures/contract_cases.json",
    "tests/a2ui/fixtures/surfaces.json",
    "tests/a2ui/make_fixtures.py",
    "tests/a2ui/make_surface_fixtures.py",
    "tests/a2ui/test_contract.py",
    "tests/a2ui/test_schedule_intent.py",
    "tests/a2ui/test_scheduler_a2ui.py",
    "uri_a2ui/__init__.py",
    "uri_a2ui/actions.py",
    "uri_a2ui/catalog.py",
    "uri_a2ui/surface.py",
    "uri_a2ui/validate.py",
    "uri_operational_intelligence/schedule_intent.py",
    "uri_scheduler/a2ui_host.py"))



FROZEN_PHASE1 = Path(r"C:\Users\cheta\.codex\worktrees\uri-phase1-integration\uri-agent\work\c1\checkpoints\final-closure-20261005-phase1.zip")


def phase1_scope_check(root, closure_zip, frozen_zip=FROZEN_PHASE1):
    """OQ-R2-1: prove the Phase 1 suite's inputs equal those of the accepted closure candidate. Every path that differs
    from -f, is new, or is modified vs HEAD must be either Phase 2-only scope or a frozen Phase 1 checkpoint file whose
    bytes equal the checkpoint. Read-only git."""
    import hashlib
    import zipfile
    git = lambda *a: subprocess.run(["git", "-C", str(root), *a], capture_output=True, text=True).stdout.splitlines()
    manifest = json.loads(zipfile.ZipFile(closure_zip).read("MANIFEST.json"))
    changed = []
    for rel, digest in manifest.items():
        if rel.startswith("evidence/"):
            continue
        f = root / rel
        if not f.is_file() or hashlib.sha256(f.read_bytes()).hexdigest() != digest:
            changed.append(rel)
    new = [r for r in git("ls-files", "-o", "--exclude-standard") if r not in manifest]
    modified = [r for r in git("diff", "--name-only", "HEAD") if r not in manifest]
    frozen = zipfile.ZipFile(frozen_zip)
    frozen_names = set(frozen.namelist())
    outside, frozen_ok = [], 0
    runner_ok = None
    for r in sorted(set(changed + new + modified)):
        if r in ("scripts/phase2d_regression.py", "scripts/phase2d_pytest.ini"):
            # OQ-R3-2: the Phase 1 runner and its ini select the Phase 1 suite; they are Phase 1 inputs. The ini must
            # equal -f; the runner must build exactly the -f runner's phase1-full argv plus the tests/phase2oq ignore.
            if r.endswith(".ini"):
                runner_ok = False
                outside.append(r)
                continue
            now_argv = runner_argv((root / r).read_text(encoding="utf-8"))
            f_argv = runner_argv(zipfile.ZipFile(closure_zip).read(r).decode("utf-8"))
            runner_ok = now_argv == f_argv + [OQ_EXTRA_IGNORE]
            if not runner_ok:
                outside.append(r)
            continue
        if r.startswith(PHASE2_SCOPE) or r in WS_EXACT:
            continue
        if r in frozen_names and (root / r).is_file() and (root / r).read_bytes() == frozen.read(r):
            frozen_ok += 1
            continue
        outside.append(r)
    importers = []
    for r in git("ls-files", "-co", "--exclude-standard"):
        if r.endswith(".py") and not r.startswith(PHASE2_SCOPE) and r not in WS_EXACT:
            try:
                text = (root / r).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if re.search(r"^\s*(from|import)\s+(uri_supervisor|uri_supervisor_bridge|uri_operational_intelligence)\b", text, re.M):
                importers.append(r)
    return {"changed_vs_closure": sorted(changed), "new_untracked": len(new), "modified_vs_head_outside_closure": sorted(modified),
            "frozen_phase1_byte_identical": frozen_ok, "outside_phase2_scope": outside,
            "runner_argv_equals_accepted_plus_phase2oq_ignore": runner_ok,
            "phase1_scope_importers_of_phase2": importers}


# ---- Review round 3 (OQ-R3-1, OQ-R3-2): per-test OUTCOME identity against a baseline made with the ACCEPTED runner ----
CLOSURE_ZIP = ROOT.parent / "evidence" / "phase2close-candidate-20261008-f.zip"
OUTCOME_BASELINE = ROOT.parent / "evidence" / "phase2oq" / "phase1_outcome_baseline.json"
OQ_EXTRA_IGNORE = "--ignore=tests/phase2oq"
# Review round 6 (OQ-R6-2): the outcome baseline is pinned by digest IN this reviewed script. Changing the baseline files
# (XML, JSON map or log, even jointly) fails the gate; a new baseline needs a new, reviewed digest here.
BASELINE_PINS = {
    "phase1_outcome_baseline.json": "a9c180877cbf19a8901f8d74c3e1da84480778544894a888a1773554977a6a4a",
    "outcome_baseline/phase1_baseline.xml": "6c5c04dc057f382d5db0588446558232462f9e4150036343306d50dd94177043",
    "outcome_baseline/phase1_baseline.log": "6e3f13e5e29f385c2e930a12e1a2428d10fed35874a28b16d288c9642e94f022",
}
# Review round 6 (OQ-R6-1): pytest exits 1 when tests failed and the session completed (the 11 accepted failures);
# 2 interrupted, 3 internal error, 4 usage error, 5 nothing collected, or a timeout are never acceptable.
PHASE1_EXPECTED_EXIT = 1


def baseline_pins_hold(base_dir=None):
    import hashlib
    d = Path(base_dir) if base_dir else ROOT.parent / "evidence" / "phase2oq"
    got = {rel: (hashlib.sha256((d / rel).read_bytes()).hexdigest() if (d / rel).is_file() else None) for rel in BASELINE_PINS}
    return got == BASELINE_PINS, got   # tests/phase2oq did not exist in -f; ignoring it == its absence there


def runner_argv(runner_source, extra=()):
    """The exact pytest argv a phase2d_regression.py SOURCE builds for `phase1-full`, captured by running its own
    main() with subprocess.run intercepted (nothing is executed). ROOT resolves to this tree."""
    import types
    mod = types.ModuleType("captured_runner")
    mod.__file__ = str(ROOT / "scripts" / "phase2d_regression.py")
    exec(compile(runner_source, mod.__file__, "exec"), mod.__dict__)
    captured = {}

    class _Done(Exception):
        pass

    def fake_run(cmd, *a, **k):
        captured["cmd"] = list(cmd)
        raise _Done()
    mod.subprocess = types.SimpleNamespace(run=fake_run)
    saved = sys.argv
    sys.argv = ["phase2d_regression.py", "phase1-full", *(["--", *extra] if extra else [])]
    try:
        mod.main()
    except _Done:
        pass
    finally:
        sys.argv = saved
    return captured["cmd"]


def accepted_runner_source():
    import zipfile
    return zipfile.ZipFile(CLOSURE_ZIP).read("scripts/phase2d_regression.py").decode("utf-8")


def junit_records(xml_path):
    """[(test id, outcome)] for EVERY testcase of a pytest JUnit XML (duplicates kept); id = classname::name."""
    import xml.etree.ElementTree as ET
    out = []
    for case in ET.parse(xml_path).getroot().iter("testcase"):
        kinds = {c.tag for c in case}
        out.append((case.get("classname", "") + "::" + case.get("name", ""),
                    "error" if "error" in kinds else "failed" if "failure" in kinds else "skipped" if "skipped" in kinds
                    else "passed"))
    return out


def junit_outcomes(xml_path):
    """{test id: outcome}; a duplicated id is recorded as `conflict` (review round 4, OQ-R4-1: never collapsed)."""
    out = {}
    for tid, outcome in junit_records(xml_path):
        out[tid] = "conflict" if tid in out else outcome
    return out


def junit_integrity(xml_path, counts):
    """OQ-R4-1: the per-test identity is only meaningful when the JUnit ids are injective and complete: every testcase
    key unique, and the raw testcase count equal to pytest's own summary total (passed + failed + skipped + errors)."""
    recs = junit_records(xml_path)
    seen, dup = set(), []
    for tid, _ in recs:
        if tid in seen:
            dup.append(tid)
        seen.add(tid)
    total = counts["passed"] + counts["failed"] + counts["skipped"] + counts["errors"]
    # Review round 5 (OQ-R5-1): every outcome category must agree, not only the total.
    xml_counts = {k: sum(1 for _, o in recs if o == k) for k in ("passed", "failed", "skipped", "error")}
    summary = {"passed": counts["passed"], "failed": counts["failed"], "skipped": counts["skipped"], "error": counts["errors"]}
    return {"testcases": len(recs), "unique_ids": len(seen), "duplicate_ids": sorted(set(dup))[:20], "summary_total": total,
            "xml_outcome_counts": xml_counts, "summary_outcome_counts": summary,
            "ok": not dup and len(recs) == total and total > 0 and xml_counts == summary}


def outcome_identity(now, base):
    """OQ-R3-1: every test ID must exist in both and have the SAME outcome. Returns (ok, details)."""
    missing = sorted(set(base) - set(now))
    added = sorted(set(now) - set(base))
    changed = sorted((t, base[t], now[t]) for t in set(base) & set(now) if base[t] != now[t])
    counts = {k: sum(1 for v in now.values() if v == k) for k in ("passed", "failed", "skipped", "error", "conflict")}
    return (not missing and not added and not changed and counts["conflict"] == 0), {
        "ids": len(now), "baseline_ids": len(base), "missing": missing[:20], "added": added[:20],
        "outcome_changed": changed[:20], "outcome_counts": counts}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("evidence")
    ap.add_argument("--bridge-runs", type=int, default=10)
    ap.add_argument("--no-native", action="store_true")
    ap.add_argument("--only", default="")
    ap.add_argument("--make-phase1-outcome-baseline", action="store_true",
                    help="(OQ-R3) run the Phase 1 suite with the ACCEPTED -f runner bytes and write per-test outcomes; refused "
                         "unless the scope check passes and the run matches the accepted log's anchors")
    ap.add_argument("--make-phase1-collection-baseline", action="store_true",
                    help="write the Phase 1 collection baseline; refused unless the phase1-scope check passes and the "
                         "collection size equals the independent baseline total")
    ap.add_argument("--baseline-full-log", default=str(ROOT.parent / "evidence" / "phase2ops_r6" / "phase1_full.log"))
    a = ap.parse_args()
    ev = Path(a.evidence)
    ev.mkdir(parents=True, exist_ok=True)
    if a.make_phase1_outcome_baseline:
        import hashlib
        scope = phase1_scope_check(ROOT, CLOSURE_ZIP)
        if scope["outside_phase2_scope"] or scope["phase1_scope_importers_of_phase2"] or OUTCOME_BASELINE.exists():
            raise SystemExit("REFUSED: scope check failed or baseline exists: " + json.dumps(scope)[:2000])
        src = accepted_runner_source()
        xml = ev / "phase1_baseline.xml"
        cmd = runner_argv(src) + [OQ_EXTRA_IGNORE, "-rfEsp", "--junitxml", str(xml)]
        code = run(cmd, ev / "phase1_baseline.log", timeout=14400, env={**os.environ, "OLLAMA_BASE_URL": "http://127.0.0.1:9"})
        outcomes = junit_outcomes(xml)
        log = ev / "phase1_baseline.log"
        integ = junit_integrity(xml, pytest_counts(log))
        if not integ["ok"]:
            raise SystemExit("REFUSED: JUnit ids are not injective/complete: " + json.dumps(integ))
        # Anchors against the ACCEPTED run's own log (round-7 / closure baseline): failure IDs identical, total identical,
        # skips identical except keys whose tests now pass by name (a live test reaching the local Ollama).
        s_now, s_base = skip_multiset(log), skip_multiset(a.baseline_full_log)
        passes = passed_ids(log)
        anchor = {"exit": code, "failed_same": failed_ids(log) == failed_ids(a.baseline_full_log),
                  "total": len(outcomes), "skips_not_in_accepted": {"|".join(k): v for k, v in s_now.items() if v > s_base.get(k, 0)},
                  "accepted_skips_now_passing": {"|".join(k): n - s_now.get(k, 0) for k, n in s_base.items() if n > s_now.get(k, 0)}}
        anchor["accepted_skips_now_passing_named"] = all(
            k.split("|")[0] != "unittest.py" and sum(1 for pid in passes if pid.split("::")[0].split("/")[-1] == k.split("|")[0]) >= n
            for k, n in anchor["accepted_skips_now_passing"].items())
        if not (anchor["failed_same"] and anchor["total"] == BASELINE_TOTAL and not anchor["skips_not_in_accepted"]
                and anchor["accepted_skips_now_passing_named"]):
            raise SystemExit("REFUSED: the accepted-runner run does not match the accepted log's anchors: " + json.dumps(anchor))
        OUTCOME_BASELINE.write_text(json.dumps({
            "schema": "uri.phase2oq.phase1_outcome_baseline.v1", "made": time.strftime("%Y-%m-%dT%H:%M:%S"),
            "runner": "scripts/phase2d_regression.py from " + str(CLOSURE_ZIP),
            "runner_sha256": hashlib.sha256(src.encode("utf-8")).hexdigest(), "argv": cmd, "extra_ignore_disclosed": OQ_EXTRA_IGNORE,
            "ollama_base_url": "http://127.0.0.1:9", "scope_check": {k: scope[k] for k in ("frozen_phase1_byte_identical",
            "outside_phase2_scope", "phase1_scope_importers_of_phase2", "runner_argv_equals_accepted_plus_phase2oq_ignore")},
            "anchors": anchor, "outcomes": outcomes}, indent=1, sort_keys=True), encoding="utf-8")
        print(json.dumps({"written": str(OUTCOME_BASELINE), "ids": len(outcomes), "anchors": anchor}))
        return 0
    if a.make_phase1_collection_baseline:
        scope = phase1_scope_check(ROOT, ROOT.parent / "evidence" / "phase2close-candidate-20261008-f.zip")
        if scope["outside_phase2_scope"] or scope["phase1_scope_importers_of_phase2"]:
            raise SystemExit("REFUSED: Phase 1 inputs differ from the accepted closure candidate: " + json.dumps(scope))
        coll = phase1_collection(ev / "phase1_collection_baseline.log")
        if len(coll) != BASELINE_TOTAL or COLLECTION_BASELINE.exists():
            raise SystemExit(f"REFUSED: collection size {len(coll)} != {BASELINE_TOTAL} or baseline file exists")
        COLLECTION_BASELINE.write_text("\n".join(coll) + "\n", encoding="utf-8")
        print(json.dumps({"written": str(COLLECTION_BASELINE), "tests": len(coll), "scope": {k: scope[k] for k in
                          ("frozen_phase1_byte_identical", "outside_phase2_scope", "phase1_scope_importers_of_phase2")}}))
        return 0
    only = set(filter(None, a.only.split(",")))
    want = lambda g: not only or g in only
    summary = {"started": time.strftime("%Y-%m-%dT%H:%M:%S"), "gates": {}}
    ok = True

    def record(name, result, passed):
        nonlocal ok
        summary["gates"][name] = {**result, "PASS": bool(passed)}
        ok = ok and bool(passed)
        print(name, json.dumps(summary["gates"][name])[:400], flush=True)
        (ev / "chain_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")

    reg = [PY, "-I", "scripts/phase2d_regression.py"]
    if want("phase2"):
        code = run(reg + ["phase2"], ev / "phase2_all.log")
        c = pytest_counts(ev / "phase2_all.log")
        record("phase2", {"exit": code, **c}, code == 0 and c["failed"] == 0 and c["errors"] == 0 and c["passed"] > 0)
    if want("authority"):
        code = run(reg + ["authority"], ev / "phase1_authority.log")
        c = pytest_counts(ev / "phase1_authority.log")
        record("authority", {"exit": code, **c}, code == 0 and c["passed"] == 134 and c["failed"] == 0)
    if want("phase1-full"):
        env = {**os.environ, "OLLAMA_BASE_URL": "http://127.0.0.1:9"}
        log = ev / "phase1_full.log"
        xml = ev / "phase1_full.xml"
        code = run(reg + ["phase1-full", "--", "-rfEsp", "--junitxml", str(xml)], log, timeout=14400, env=env)
        c = pytest_counts(log)
        same_fail = failed_ids(log) == failed_ids(a.baseline_full_log)
        details = {"failed_ids": failed_ids(log), "SAME_FAILURE_SET_AS_ACCEPTED_LOG": same_fail}
        if OUTCOME_BASELINE.is_file() and xml.is_file():
            base = json.loads(OUTCOME_BASELINE.read_text(encoding="utf-8"))
            ok_ids, idd = outcome_identity(junit_outcomes(xml), base["outcomes"])
            integ = junit_integrity(xml, c)
            bdir = ROOT.parent / "evidence" / "phase2oq" / "outcome_baseline"
            binteg = junit_integrity(bdir / "phase1_baseline.xml", pytest_counts(bdir / "phase1_baseline.log"))
            # Review round 5 (OQ-R5-2): the stored baseline map must still be exactly what its own baseline XML records.
            baseline_bound = junit_outcomes(bdir / "phase1_baseline.xml") == base["outcomes"]
            ok_ids = (ok_ids and integ["ok"] and binteg["ok"] and binteg["testcases"] == len(base["outcomes"])
                      and baseline_bound)
            details["baseline_json_equals_baseline_xml"] = baseline_bound
            pins_ok, pins = baseline_pins_hold()
            ok_ids = ok_ids and pins_ok
            details["baseline_pins_hold"] = pins_ok
            details.update(idd, outcome_baseline=str(OUTCOME_BASELINE), outcome_baseline_runner_sha256=base.get("runner_sha256"),
                           junit_integrity=integ, baseline_junit_integrity=binteg)
        else:
            ok_ids = False
            details["outcome_baseline"] = "MISSING"
        record("phase1-full", {"exit": code, **c, **details, "baseline_log": a.baseline_full_log,
                               "ollama_base_url": env["OLLAMA_BASE_URL"], "expected_exit": PHASE1_EXPECTED_EXIT},
               ok_ids and same_fail and c["errors"] == 0 and code == PHASE1_EXPECTED_EXIT)
    if want("phase1-scope"):
        closure = ROOT.parent / "evidence" / "phase2close-candidate-20261008-f.zip"
        res = phase1_scope_check(ROOT, closure)
        record("phase1-scope", res, not res["outside_phase2_scope"] and not res["phase1_scope_importers_of_phase2"])
    if want("residue"):
        removed = []
        for name in RESIDUE:
            p = ROOT / name
            if p.is_file() and p.stat().st_size == 0:
                p.unlink()
                removed.append(name)
        record("residue", {"removed": removed}, all(not (ROOT / n).exists() for n in RESIDUE))
    if want("flutter"):
        flutter = Path.home() / "flutter/bin/flutter.bat"
        code = run([str(flutter), "test"], ev / "flutter_all.log", cwd=ROOT / "uri_ui")
        text = (ev / "flutter_all.log").read_text(encoding="utf-8", errors="replace")
        m = re.findall(r"\+(\d+)(?: ~(\d+))?(?: -(\d+))?: (All tests passed!|Some tests failed\.)", text)
        last = m[-1] if m else ("0", "0", "0", "")
        res = {"exit": code, "passed": int(last[0]), "skipped": int(last[1] or 0), "failed": int(last[2] or 0), "verdict": last[3]}
        record("flutter", res, code == 0 and res["verdict"] == "All tests passed!")
    if want("bridge"):
        results, refusals = [], []
        for i in range(1, a.bridge_runs + 1):
            code = run([PY, "-I", "scripts/phase2ops_validate_ui_bridge.py", "--log", str(ev / f"ui_bridge_live_{i}.json")],
                       ev / f"ui_bridge_stdout_{i}.txt", timeout=1800)
            data = {}
            try:
                data = json.loads((ev / f"ui_bridge_live_{i}.json").read_text(encoding="utf-8"))
                slog = Path(data["base"]) / "server" / "state" / "logs" / "phase2-server.log"
                cand = [slog] + list(Path(data["base"]).rglob("phase2-server.log"))
                for logp in cand:
                    if logp.is_file():
                        refusals += [f"run{i} " + l for l in logp.read_text(encoding="utf-8", errors="replace").splitlines()
                                     if l.startswith("CLIENT_REFUSAL")]
                        break
            except Exception as exc:  # noqa: BLE001
                data = {"error": type(exc).__name__}
            results.append({"run": i, "exit": code, "flutter_exit": data.get("exit")})
        (ev / "refusals.txt").write_text("\n".join(refusals) + ("\n" if refusals else ""), encoding="utf-8")
        passed = sum(1 for r in results if r["exit"] == 0 and r["flutter_exit"] == 0)
        record("bridge", {"runs": len(results), "passed": passed, "refusal_lines": len(refusals), "results": results},
               passed == len(results))
    if want("native") and not a.no_native:
        nat = ev / "native"
        nat.mkdir(exist_ok=True)
        code = run([PY, "-I", "scripts/phase2ops_native_execution.py", "--provider", "codex_cli", "--model", "gpt-6-sol",
                    "--evidence", str(nat)], ev / "native_codex_stdout.txt", timeout=3600)
        # The native script prints a one-line summary (`{"tag": ..., "runs": [{name, state, reason, code,
        # pid_after_cancel}]}`) before `REPORT <path>`; the report JSON keeps the raw per-run material instead.
        runs = {}
        try:
            lines = (ev / "native_codex_stdout.txt").read_text(encoding="utf-8", errors="replace").splitlines()
            summ = json.loads([l for l in lines if l.startswith('{"tag"')][-1])
            runs = {r.get("name"): {k: r.get(k) for k in ("state", "reason", "code", "pid_after_cancel")} for r in summ.get("runs") or []}
            runs["_qualification"] = summ.get("qualification")
            runs["_report"] = [l[7:] for l in lines if l.startswith("REPORT ")][-1:]
        except Exception as exc:  # noqa: BLE001
            runs = {"error": type(exc).__name__}
        good = (runs.get("lifecycle", {}).get("state") == "completed" and runs.get("lifecycle", {}).get("code") == "SETTLED_VERIFIED"
                and runs.get("mid_run_cancel", {}).get("state") == "uncertain"
                and runs.get("mid_run_cancel", {}).get("reason") == "CANCELLED_AFTER_DISPATCH"
                and runs.get("mid_run_cancel", {}).get("pid_after_cancel") == "DEAD")
        record("native", {"exit": code, "runs": runs}, code == 0 and good)
    if want("native-worker"):
        nw = ev / "native_worker"
        code = run([PY, "-I", "scripts/phase2oq_native_worker.py", "--evidence", str(nw)], ev / "native_worker_stdout.txt", timeout=3600)
        try:
            lines = (ev / "native_worker_stdout.txt").read_text(encoding="utf-8", errors="replace").splitlines()
            summ = json.loads([l for l in lines if l.startswith('{"tag"')][-1])
        except Exception as exc:  # noqa: BLE001
            summ = {"error": type(exc).__name__}
        lc = summ.get("L") or {}
        row = (summ.get("W_codex_row") or [{}])[0]
        good = (summ.get("probe") == "OK" and summ.get("logged_in") is False and row.get("status") == "QUALIFIED"
                and (summ.get("W_harness") or {}).get("usable") is False
                and summ.get("W_begin") == {"result": "REFUSED", "code": "HARNESS_NOT_USABLE"}
                and summ.get("W2") == [["INVALIDATED", "CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED"]]
                and summ.get("W3") == [["INVALIDATED", "LAUNCH_CHAIN_RESOLUTION_CHANGED"]]
                and (lc.get("lifecycle") or {}).get("state") == "completed"
                and (lc.get("lifecycle") or {}).get("code") == "SETTLED_VERIFIED"
                and (lc.get("mid_run_cancel") or {}).get("state") == "uncertain"
                and (lc.get("mid_run_cancel") or {}).get("reason") == "CANCELLED_AFTER_DISPATCH"
                and (lc.get("mid_run_cancel") or {}).get("pid_after") == "DEAD"
                and (lc.get("mid_run_cancel") or {}).get("survivors") == 0)
        record("native-worker", {"exit": code, "summary": summ}, code == 0 and good)
    summary["finished"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    summary["ALL_PASS"] = ok
    (ev / "chain_summary.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    print("ALL_PASS" if ok else "CHAIN_FAILED", flush=True)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
