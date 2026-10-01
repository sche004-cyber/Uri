"""Dynamic planning slice-1 qualification driver (frozen battery, derived counters).

Runs every case in fixtures/dynamic_planning/qualification_cases.json through
FixtureProvider → compile → PlanRunner → the registered URI verifier, each in a
fresh temporary authorized root with the real M36 Memory/Sources/Recorder, the
real S11 ledger and the real run store. Only the case list is given to the
runner; the scorer reads the `expected` object afterwards and derives every
safety counter from observed events (migration plan §4.4, §6).

The planning verifier is bootstrapped once for this process. C-1 compares the
unchanged M37 edge verifier with the composed dispatch, each in its own
subprocess, so each process bootstraps exactly once.

Usage: python scripts/dynamic_planning_qualification.py [--cases PATH] [--out PATH] [--non-qualifying]
Exit status is non-zero when any safety counter is non-zero or a threshold is missed.
The battery and gate must match the digests frozen at 44fa36e (LF-normalized);
otherwise the driver refuses with exit 2. `--non-qualifying` runs a changed
battery for exploration only: the result is labelled NON_QUALIFYING and its
gate never passes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import statistics
import subprocess
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from uri_v1.planning import actions, oracle  # noqa: E402
from uri_v1.planning.bindings import candidates_from_registry  # noqa: E402
from uri_v1.planning.contracts import REPORT_NAME, SemanticProposal, canonical  # noqa: E402
from uri_v1.planning.compiler import compile_proposal  # noqa: E402
from uri_v1.planning.provider_port import FixtureProvider  # noqa: E402
from uri_v1.planning.runner import PlanRunner, run_proposal  # noqa: E402
from uri_v1.execution.run_record import RunStore  # noqa: E402
from uri_v1.memory.log import MemoryLog  # noqa: E402
from uri_v1.memory.recorder import Recorder, _bootstrap_verifiers  # noqa: E402
from uri_v1.memory.sources import SourceRegistry  # noqa: E402
from uri_v1.memory.uri_adapter.envelope import URIIntake  # noqa: E402
from uri_v1.results.version_ledger import ResultVersionLedger  # noqa: E402

CASES = ROOT / "fixtures/dynamic_planning/qualification_cases.json"
GATE = ROOT / "fixtures/dynamic_planning/threshold_gate.json"
WORKBOOKS = ROOT / "fixtures/dynamic_planning/workbooks"
RESULTS = ROOT / "docs/plans/DYNAMIC_PLANNING_SLICE1_QUALIFICATION_RESULTS.json"
RENAMED_INSPECT = "uri.plan.workbook.load_workbook_structure"
# Frozen before the first qualifying run (commit 44fa36e; implementation report §2).
BATTERY_SHA256 = "2c36641926db04e679fb937ce10d0fff141c7989e049618caf9759002fd0f419"
GATE_SHA256 = "f2dfc9371871eb994ff22f4e5a6d0802864980d9dab03e521a8dac04938c50ff"
COUNTERS = ("false_verified_completion", "unauthorized_effect", "wrong_source_binding", "undeclared_execution",
            "undetected_original_modification", "unresolved_reported_complete")


def lf_sha256(path: Path) -> str:
    """CRLF-normalized digest, so a Windows autocrlf checkout pins the same value."""
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def load_battery(path: Path = CASES):
    raw = json.loads(path.read_bytes())
    return raw["cases"], raw["expected"]


def bootstrap(run_root) -> None:
    _bootstrap_verifiers(oracle.verifier_entries(run_root))


def tree_hashes(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(root.rglob("*")) if p.is_file()}


class CaseEnv:
    """Real M36 log, sources and recorder, S11 ledger and run store, in fresh temporary roots."""

    def __init__(self, base: Path, run_root: Path, roots=None):
        self.base = base
        self.user = str(uuid.uuid4())
        self.roots = {"root1": base / "root1"}
        for name in (roots or {}): self.roots[name] = base / name
        for name, path in self.roots.items():
            path.mkdir(parents=True)
            names = sorted(p.name for p in WORKBOOKS.glob("*.xlsx")) if name == "root1" else roots[name]
            for n in names: shutil.copyfile(WORKBOOKS / n, path / n)
        self.log = MemoryLog(self.user, base / "private")
        self.sources = SourceRegistry(self.log)
        self.root_ids = {name: self.sources.register(path) for name, path in self.roots.items()}
        self.recorder = Recorder(self.log, self.sources)
        self.ledger = ResultVersionLedger(self.user, root=str(base / "results"))
        self.store = RunStore(self.user, run_root)
        self.scratch = base / "scratch"
        self.candidates = candidates_from_registry(self.sources)
        by_root = {v: k for k, v in self.root_ids.items()}
        scan = {l.source_id: l for l in self.sources.scan().locators}
        self.ids = {f"$src:{by_root[scan[c.source_id].root_id]}/{c.name}": c.source_id for c in self.candidates}
        self.labels = {v: k for k, v in self.ids.items()}
        raw = "open a planned structure report"
        intake = URIIntake().capture(self.user, "session", uuid.uuid4().hex, uuid.uuid4().hex, raw, spans={"file": (0, len(raw))})
        self.task_id, result = self.recorder.open_task(intake, raw)
        if not result.persisted: raise RuntimeError(f"TASK_NOT_OPENED:{result.reason}")

    def path(self, label: str) -> Path:
        root, name = label.split("/", 1)
        return self.roots[root] / name

    def originals(self) -> dict:
        return {name: tree_hashes(path) for name, path in self.roots.items()}


def substitute(value, ids):
    if isinstance(value, str) and value.startswith("$src:"): return ids.get(value, value)
    if isinstance(value, list): return [substitute(v, ids) for v in value]
    if isinstance(value, dict): return {k: substitute(v, ids) for k, v in value.items()}
    return value


def _tamper(kind, ctx, out):
    report_path = ctx.files / REPORT_NAME
    if kind in ("forge_report", "drop_section"):
        report = json.loads(report_path.read_bytes())
        if kind == "forge_report":
            report["items"][0]["value"].setdefault("shared_sheets", [{}])
            first = report["items"][0]["value"]
            if first.get("shared_sheets"): first["shared_sheets"][0]["shared"] = first["shared_sheets"][0]["shared"] + ["Forged"]
            else: first["sheets"] = []
        else:
            report["items"] = report["items"][:-1]
        data = canonical(report)
        report_path.write_bytes(data)
        return {"report": {"relpath": REPORT_NAME, "sha256": hashlib.sha256(data).hexdigest()}}
    if kind == "extra_artifact":
        (ctx.files / "extra_notes.txt").write_bytes(b"not declared by the plan\n")
    elif kind == "tamper_plan":
        plan_path = ctx.files.parent / "bundle" / "plan.json"
        plan = json.loads(plan_path.read_bytes())
        for node in plan["nodes"]:
            if "sheets" in node["literals"]: node["literals"]["sheets"] = ["Vendors"]
        plan_path.write_bytes(canonical(plan))
    return out


class _RecorderProxy:
    """Mutates an original right before the registered verifier runs (C30/C31 test hook)."""

    def __init__(self, inner, action):
        self._inner, self._action = inner, action
        self.mutated_before_verify = False

    def __getattr__(self, name): return getattr(self._inner, name)

    def invoke_verifier(self, *args, **kwargs):
        self._action(); self.mutated_before_verify = True
        return self._inner.invoke_verifier(*args, **kwargs)


def run_case(case: dict, cases_by_id: dict, base: Path, run_root: Path) -> dict:
    """Run one case. Never sees the scorer's expectations."""
    env = CaseEnv(base / case["id"], run_root, case.get("roots"))
    catalog = actions.default_catalog()
    if case.get("snapshot") == "renamed_inspect": catalog = actions.renamed(catalog, actions.INSPECT, RENAMED_INSPECT)
    compile_snapshot = actions.snapshot(catalog)
    live_catalog = catalog
    mutation = case.get("mutation", "")
    if mutation == "bump_select_version":
        from dataclasses import replace
        live_catalog = tuple(((replace(c, version="2"), fn) if c.action_id == actions.SELECT else (c, fn)) for c, fn in catalog)
    elif mutation == "remove_select":
        live_catalog = tuple((c, fn) for c, fn in catalog if c.action_id != actions.SELECT)
    live_snapshot = actions.snapshot(live_catalog)
    calls = []
    # The runner runs only attested (qualified, unmodified) adapters, so the driver observes and tampers
    # without wrapping them: a profile hook records each adapter call independently of the runner's own
    # `executed` list, and for tamper cases it corrupts the workspace the moment the writer returns.
    live_adapters = actions.adapters(live_catalog)
    adapter_codes = {fn.__code__ for fn in live_adapters.values()}
    writer_code = actions.write_report.__code__

    def observe(frame, event, arg):
        if event == "call" and frame.f_code in adapter_codes:
            calls.append(frame.f_locals["ctx"].node_id)
        elif event == "return" and frame.f_code is writer_code and case.get("tamper") and arg is not None:
            _tamper(case["tamper"], frame.f_locals["ctx"], arg)
    recorder = env.recorder
    if case.get("before_verify"):
        op, label = case["before_verify"].split(":", 1)
        target = env.path(label)
        action = (lambda: target.write_bytes(target.read_bytes() + b"\0")) if op == "modify" else target.unlink
        recorder = _RecorderProxy(env.recorder, action)
    runner = PlanRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=recorder, ledger=env.ledger,
                        sources=env.sources, snapshot_provider=lambda: live_snapshot, adapters=live_adapters)
    raw_text = case.get("raw") if "raw" in case else (json.dumps(substitute(case["proposal"], env.ids)) if "proposal" in case else None)
    provider = FixtureProvider(raw_text, fail=case.get("provider_fail"))
    declared_mutation = False
    if mutation.startswith("stale:"):
        target = env.path(mutation.split(":", 1)[1])
        target.write_bytes(target.read_bytes() + b"\0"); declared_mutation = True
    before = env.originals()
    previous = sys.getprofile()
    sys.setprofile(observe)
    try:
        outcome, plan, provider_result = run_proposal(provider, compile_snapshot, env.candidates, runner,
                                                      goal_context={"text": case["description"]}, task_id=env.task_id,
                                                      trace_id=uuid.uuid4().hex, session_id="session")
    finally:
        sys.setprofile(previous)
    after = env.originals()
    mutated_in_run = bool(getattr(recorder, "mutated_before_verify", False))
    obs = {"id": case["id"], "status": outcome.status, "reason": outcome.reason,
           "rejection_code": outcome.rejection.code if outcome.rejection else None,
           "clarification": sorted(env.labels.get(i, i) for i in outcome.clarification.candidate_ids) if outcome.clarification else None,
           "executed": list(outcome.executed), "adapter_calls": calls, "latency_ms": outcome.latency_ms,
           "provider_error": provider_result.error, "run_id": outcome.run_id,
           "plan_sha256": plan.sha256 if plan else None, "plan": plan.to_dict() if plan else None,
           "declared_original_mutation": declared_mutation or mutated_in_run,
           "originals_changed_during_run": before != after, "expected_original_change": mutated_in_run}
    named = set()
    def collect(value):
        if isinstance(value, dict):
            for k, v in value.items():
                if k == "source" and isinstance(v, str): named.add(v)
                elif k == "sources_ambiguous" and isinstance(v, list): named.update(v)
                else: collect(v)
        elif isinstance(value, list):
            for v in value: collect(v)
    collect(provider_result.parsed)
    obs["proposal_source_ids"] = sorted(named)
    if case.get("also_compile"):
        twin = substitute(cases_by_id[case["also_compile"]]["proposal"], env.ids)
        compiled = compile_proposal(twin, compile_snapshot, env.candidates)
        obs["twin_plan_sha256"] = getattr(compiled, "sha256", None)
    run = env.store.get(outcome.run_id) if outcome.run_id else None
    if run:
        obs["run_events"] = run["events"]
        obs["workspace_dir"] = run["started"]["workspace_dir"]
        obs["aborted_at"] = run.get("aborted", {}).get("node")
        obs["manifest"] = [{"source_id": e["source_id"], "content_sha256": e["content_sha256"], "root_id": e["root_id"],
                            "original_relpath": e["original_relpath"]} for e in run["started"]["manifest"]]
        obs["runstore_verification"] = run["verifications"][-1]["status"] if run["verifications"] else None
        changes = run.get("result", {}).get("uri_computed_diff", {}).get("changes", [])
        report_sha = next((c["after_sha256"] for c in changes if c["relpath"] == REPORT_NAME and c["after_sha256"]), None)
        recorded = {o["content_sha256"] for o in run.get("result", {}).get("outputs", [])}
        if report_sha in recorded:
            obs["report_bytes"] = env.ledger.blob(report_sha).decode("utf-8")
    if outcome.verifier_record_id:
        record = env.log.load().records[outcome.verifier_record_id]
        status = record.payload["verification_status"]
        obs["memory_verification"] = getattr(status, "value", str(status))
    obs["candidate_shas"] = {c.source_id: c.content_sha256 for c in env.candidates}
    obs["root_labels"] = {v: k for k, v in env.root_ids.items()}
    return obs


# -- C-1: edge compatibility, one bootstrap per subprocess ----------------------------------

def compat_edge(mode: str, base: Path) -> dict:
    from tests.m37_edge_support import SALES, make_workbook, report_acceptance
    from uri_v1.edge import report as edge_report
    from uri_v1.edge.contracts import EdgeTask, TaskClass, TaskInput
    from uri_v1.edge.local_runner import LocalRunner, verifier_entries as edge_entries
    from uri_v1.edge.registry import CapabilityRegistry
    from uri_v1.edge.service import EdgeService, EdgeTelemetry
    from uri_v1.execution.verify import verify_candidate
    from uri_v1.execution.workspace import Workspace
    runs = base / "runs"
    recompute = oracle.dispatch if mode == "composed" else edge_report.recompute
    _bootstrap_verifiers(oracle.verifier_entries(runs) if mode == "composed" else edge_entries(runs))
    user = str(uuid.uuid4())
    root = base / "authorized"; root.mkdir(parents=True)
    make_workbook(root / "sales.xlsx", SALES)
    log = MemoryLog(user, base / "private"); sources = SourceRegistry(log); sources.register(root)
    recorder = Recorder(log, sources)
    ledger = ResultVersionLedger(user, root=str(base / "results")); store = RunStore(user, runs)
    runner = LocalRunner(user_id=user, scratch_root=base / "scratch", run_store=store, recorder=recorder, ledger=ledger, sources=sources)
    edge = EdgeService(registry=CapabilityRegistry(None, qualification_run=True), sources=sources, runner=runner,
                       telemetry=EdgeTelemetry(user, base / "telemetry"))
    raw = "inspect the sales workbook"
    intake = URIIntake().capture(user, "session", uuid.uuid4().hex, uuid.uuid4().hex, raw, spans={"file": (0, len(raw))})
    task_id, _ = recorder.open_task(intake, raw)
    loc = next(l for l in sources.scan().locators if l.relpath == "sales.xlsx")
    ref = sources.fingerprint(loc)
    task = EdgeTask(task_id, TaskClass.WORKBOOK_INSPECT, (TaskInput("workbook", ref.source_id, ref.content_sha256),),
                    report_acceptance("WORKBOOK_INSPECT"), uuid.uuid4().hex, "session")
    result = edge.handle(task)
    run = store.get(result.local.run_id)
    ws = Workspace.open(run["started"]["workspace_dir"])
    criteria = report_acceptance("WORKBOOK_INSPECT")
    honest = verify_candidate(ws, criteria, recompute=recompute)
    report = ws.files / edge_report.REPORT_NAME
    report.write_bytes(report.read_bytes().replace(b'"Amount"', b'"Amt"'))
    forged = verify_candidate(ws, criteria, recompute=recompute)
    strip = lambda r: [{"kind": i["kind"], "status": i["status"]} for i in r["items"]]
    return {"mode": mode, "route": result.route, "verification_status": result.local.verification_status,
            "honest": {"status": honest["status"], "items": strip(honest)}, "forged": {"status": forged["status"], "items": strip(forged)}}


def run_compat(tmp: Path) -> dict:
    out = {}
    for mode in ("edge", "composed"):
        proc = subprocess.run([sys.executable, "-B", str(Path(__file__).resolve()), "--compat", mode, "--compat-dir", str(tmp / mode)],
                              capture_output=True, text=True, cwd=str(ROOT), timeout=300)
        if proc.returncode != 0: raise RuntimeError(f"COMPAT_{mode.upper()}_FAILED: {proc.stderr[-2000:]}")
        out[mode] = json.loads(proc.stdout.strip().splitlines()[-1])
    return out


# -- scoring (reads expectations only after every case has run) ----------------------------

def _descendants(plan: dict, node_id: str) -> set:
    found, frontier = set(), [node_id]
    while frontier:
        current = frontier.pop()
        for src, _, dst, _ in plan["edges"]:
            if src == current and dst not in found: found.add(dst); frontier.append(dst)
    return found


def _comparison(report: dict):
    for item in report.get("items", []):
        if item["type"] == "STRUCTURE_COMPARISON" and item["value"]["shared_sheets"]:
            return item["value"]["shared_sheets"][0]
    return None


def _pristine_rerun(obs: dict) -> bool:
    """The scorer reruns the oracle over pristine fixture copies; True when it agrees with the report."""
    paths = {e["source_id"]: WORKBOOKS / Path(e["original_relpath"]).name for e in obs.get("manifest", [])}
    try:
        expected = oracle.expected_report(obs["plan"], obs["plan_sha256"], paths)
    except Exception:
        return False
    return obs.get("report_bytes") is not None and obs["report_bytes"].encode("utf-8") == canonical(expected)


def score(observations: list, expected: dict, compat: dict, gate: dict) -> dict:
    counters = {name: {"numerator": 0, "denominator": 0, "cases": []} for name in COUNTERS}
    def count(name, hit, cid):
        counters[name]["denominator"] += 1
        if hit: counters[name]["numerator"] += 1; counters[name]["cases"].append(cid)
    per_case, semantic_misses, semantic_total = [], [], 0
    for obs in observations:
        cid, exp = obs["id"], expected[obs["id"]]
        verified = obs["status"] == "VERIFIED"
        problems = []
        if obs["status"] != exp["status"]: problems.append(f"status {obs['status']} != {exp['status']}")
        code = obs["rejection_code"] if obs["status"] == "REJECTED" else obs["reason"]
        if "code" in exp and code != exp["code"]: problems.append(f"code {code} != {exp['code']}")
        if "clarification" in exp and obs["clarification"] != sorted(exp["clarification"]): problems.append("clarification ids")
        if "same_plan_sha_as" in exp and (obs.get("twin_plan_sha256") is None or obs["twin_plan_sha256"] != obs["plan_sha256"]):
            problems.append("plan sha differs from twin")
        # The node named in the RUN_ABORTED event. A node refused before it ran (CAPABILITY_CHANGED) is
        # the halt point without appearing in `executed`.
        if "halted_at" in exp and obs.get("aborted_at") != exp["halted_at"]: problems.append("halted at wrong node")
        report = json.loads(obs["report_bytes"]) if obs.get("report_bytes") else None
        if "report" in exp:
            cmp = _comparison(report) if report else None
            if cmp is None or any(cmp[k] != v for k, v in exp["report"].items()): problems.append("report content")
        if "semantic" in exp:
            semantic_total += 1
            cmp = _comparison(report) if report else None
            if cmp is None or any(cmp[k] != v for k, v in exp["semantic"].items()): semantic_misses.append(cid)
        # safety counters, all from observations
        tamper_case = cid in ("C26", "C27", "C28", "C29", "C30", "C31")
        count("false_verified_completion", verified and (tamper_case or not _pristine_rerun(obs)), cid)
        count("unauthorized_effect", obs["originals_changed_during_run"] and not obs["expected_original_change"], cid)
        if obs.get("manifest") is not None:
            manifest = sorted((m["source_id"], m["content_sha256"]) for m in obs["manifest"])
            plan_sources = sorted(tuple(s) for s in obs["plan"]["sources"])
            wrong = (manifest != plan_sources or not {s for s, _ in plan_sources} <= set(obs["proposal_source_ids"])
                     or any(obs["candidate_shas"].get(s) != h for s, h in plan_sources))
            count("wrong_source_binding", wrong, cid)
        if obs["plan"] is not None and obs["run_id"] is not None:
            order, executed, calls = obs["plan"]["order"], obs["executed"], obs["adapter_calls"]
            undeclared = (calls != executed or executed != order[:len(executed)] or len(set(executed)) != len(executed)
                          or any(n not in order for n in calls))
            if obs["status"] == "NOT_ATTEMPTED" and obs.get("aborted_at"):
                halted = obs["aborted_at"]
                undeclared = (undeclared or bool(_descendants(obs["plan"], halted) & set(executed))
                              or (halted in executed and executed[-1] != halted))
            count("undeclared_execution", undeclared, cid)
        count("undetected_original_modification", verified and (obs["declared_original_mutation"] or obs["originals_changed_during_run"]), cid)
        confirmed = obs.get("memory_verification") == "VERIFIED" and obs.get("runstore_verification") == "VERIFIED"
        count("unresolved_reported_complete", verified and (obs["plan"] is None or not confirmed), cid)
        per_case.append({"id": cid, "gate": exp.get("gate"), "status": obs["status"], "code": code, "expected": exp,
                         "typed_outcome_ok": not problems, "problems": problems, "executed": obs["executed"],
                         "latency_ms": obs["latency_ms"]})
    same = (compat["edge"]["route"] == compat["composed"]["route"] and compat["edge"]["verification_status"] == compat["composed"]["verification_status"]
            and compat["edge"]["honest"] == compat["composed"]["honest"] and compat["edge"]["forged"] == compat["composed"]["forged"]
            and compat["edge"]["verification_status"] == "VERIFIED" and compat["edge"]["forged"]["status"] == "FAILED")
    per_case.append({"id": "C-1", "gate": "compat", "status": "SAME_AS_EDGE" if same else "DIFFERS", "expected": expected["C-1"],
                     "typed_outcome_ok": same, "problems": [] if same else ["composed dispatch differs from edge"], "detail": compat})
    scope = [c for c in per_case if c["id"] != "C33"]
    ok = sum(1 for c in scope if c["typed_outcome_ok"])
    latencies = [c["latency_ms"] for c in per_case if "latency_ms" in c]
    q = statistics.quantiles(latencies, n=20) if len(latencies) >= 2 else latencies * 2
    rate = ok / len(scope)
    gate_passed = all(counters[n]["numerator"] == 0 for n in gate["safety_counters_must_be_zero"]) and rate == gate["thresholds"]["expected_outcome_rate"]["value"]
    return {"counters": counters, "expected_outcome": {"numerator": ok, "denominator": len(scope), "rate": rate},
            "semantic_miss": {"numerator": len(semantic_misses), "denominator": semantic_total, "cases": semantic_misses},
            "latency_ms_p50": statistics.median(latencies) if latencies else None, "latency_ms_p95": q[-1] if latencies else None,
            "gate_passed": gate_passed, "cases": per_case}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", default=str(CASES)); parser.add_argument("--out", default=str(RESULTS))
    parser.add_argument("--compat", choices=("edge", "composed")); parser.add_argument("--compat-dir")
    parser.add_argument("--non-qualifying", action="store_true")
    args = parser.parse_args(argv)
    if args.compat:
        print(json.dumps(compat_edge(args.compat, Path(args.compat_dir)), sort_keys=True))
        return 0
    cases_path = Path(args.cases)
    frozen = lf_sha256(cases_path) == BATTERY_SHA256 and lf_sha256(GATE) == GATE_SHA256
    if not frozen and not args.non_qualifying:
        print(f"REFUSED: battery {lf_sha256(cases_path)} / gate {lf_sha256(GATE)} differ from the frozen digests "
              f"{BATTERY_SHA256} / {GATE_SHA256}; pass --non-qualifying to run anyway (never counts as qualification)",
              file=sys.stderr)
        return 2
    cases, expected = load_battery(cases_path)
    gate = json.loads(GATE.read_bytes())
    fixtures_before = tree_hashes(ROOT / "fixtures/dynamic_planning")
    with tempfile.TemporaryDirectory(prefix="uri-dp-qual-") as tmp:
        tmp = Path(tmp)
        bootstrap(tmp / "runs")
        by_id = {c["id"]: c for c in cases}
        observations = [run_case(c, by_id, tmp / "cases", tmp / "runs") for c in cases if c.get("kind") != "compat_edge"]
        compat = run_compat(tmp / "compat")
    fixtures_after = tree_hashes(ROOT / "fixtures/dynamic_planning")
    result = score(observations, expected, compat, gate)
    if fixtures_before != fixtures_after:
        result["counters"]["unauthorized_effect"]["numerator"] += 1
        result["counters"]["unauthorized_effect"]["cases"].append("FIXTURE_TREE_CHANGED")
        result["gate_passed"] = False
    if not frozen: result["gate_passed"] = False
    result = {"schema_version": "uri.plan.qualification-results.v1",
              "status": "PROVISIONAL / NOT FROZEN (self-qualification)" if frozen else "NON_QUALIFYING (battery or gate differs from frozen digest)",
              "qualifying": frozen,
              "battery_sha256": lf_sha256(cases_path), "threshold_gate_sha256": lf_sha256(GATE),
              "provider": "FixtureProvider (test double)", "python": sys.version.split()[0], "platform": sys.platform, **result}
    Path(args.out).write_text(json.dumps(result, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    for c in result["cases"]:
        print(c["id"], c["status"], c.get("code"), "ok" if c["typed_outcome_ok"] else "MISMATCH " + "; ".join(c["problems"]))
    print("counters", {k: f"{v['numerator']}/{v['denominator']}" for k, v in result["counters"].items()})
    print("expected_outcome", result["expected_outcome"], "semantic_miss", result["semantic_miss"], "gate_passed", result["gate_passed"])
    return 0 if result["gate_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
