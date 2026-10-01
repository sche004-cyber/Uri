"""M37 Edge-minimum qualification driver (predeclared battery and threshold gate).

Runs every battery case in a fresh temporary authorized root with real .xlsx
files, real scripts, real M36 Memory/Sources/Recorder and the real S11 ledger,
twice, then evaluates the frozen threshold gate. Writes:
  docs/plans/M37_QUALIFICATION_RESULTS.json   per-case results, metrics, gate verdict
  docs/plans/M37_EDGE_QUALIFICATION_EVIDENCE.json   capability qualification record (only when the gate passes)

The verifier registry is re-bootstrapped per case so each case's verifier
reads that case's temporary run store; the registry is otherwise the real M36
bootstrap-only registry.
"""
from __future__ import annotations

from dataclasses import replace
import hashlib
import json
from pathlib import Path
import statistics
import sys
import tempfile
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from tests.m37_edge_support import Env, acceptance, make_workbook, report_acceptance, script  # noqa: E402
from tests.test_m36_memory_support import bind, intake as m36_intake, opened, setup as m36_setup  # noqa: E402
from uri_v1.edge.contracts import TaskClass  # noqa: E402
from uri_v1.edge.registry import CAPABILITIES, QUALIFICATION_SCHEMA_VERSION  # noqa: E402
from uri_v1.memory.context_package import build_context  # noqa: E402
from uri_v1.memory.contracts import VerificationStatus, canonical, plain  # noqa: E402

BATTERY = ROOT / "fixtures/m37_edge/battery.json"
GATE = ROOT / "fixtures/m37_edge/threshold_gate.json"
RESULTS = ROOT / "docs/plans/M37_QUALIFICATION_RESULTS.json"
EVIDENCE = ROOT / "docs/plans/M37_EDGE_QUALIFICATION_EVIDENCE.json"


def lf(path: Path) -> bytes:
    """CRLF-normalized bytes, so Windows autocrlf checkouts hash identically."""
    return path.read_bytes().replace(b"\r\n", b"\n")


class _Patch:
    def setattr(self, obj, name, value): setattr(obj, name, value)


def _sheets(spec, battery):
    return {name: (tuple(h), tuple(tuple(r) for r in rows)) for name, (h, rows) in battery["workbooks"][spec].items()}


def _originals(root: Path) -> dict:
    return {p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob("*") if p.is_file()}


def _fork(env, task):
    """Explicit corruption fixture (same technique as the M36 adversarial test): a second branch at one parent."""
    head = env.log.load().task(task)
    assert env.recorder.task_state(task, head.record_id, intake=m36_intake("pause"), status="PAUSED").persisted
    p = plain(head.payload); eid = uuid.uuid4().hex; p.update(status="WAITING_USER", transition_evidence_ids=[eid])
    fork = replace(head, record_id=uuid.uuid4().hex, payload=p, supersedes=(head.record_id,), recorded_at="2026-09-28T13:00:00+00:00")
    with env.log.guard(): env.recorder._event((fork,), "RUNTIME", "CLARIFICATION", eid)
    with next(env.log.path.glob("log-*.jsonl")).open("ab") as f: f.write(canonical(fork.to_dict()) + b"\n")


def run_case(case, battery, tmp: Path) -> dict:
    memory = case.get("memory")
    names = ["sales.xlsx"] + (["report.py"] if case["script"] is not None else []) + (["sales_v2.xlsx"] if memory == "USER_CORRECTED" else [])
    log, s, rec, root = m36_setup(tmp, files=tuple(names))
    env = Env(tmp, _Patch(), existing=(log, s, rec, root))
    if case["sheets"] == "NOT_A_WORKBOOK": (root / "sales.xlsx").write_bytes(b"this is not a workbook")
    else: make_workbook(root / "sales.xlsx", _sheets(case["sheets"], battery))
    if memory == "USER_CORRECTED": make_workbook(root / "sales_v2.xlsx", _sheets(case["sheets"], battery))
    if case["script"] is not None:
        spec = case["script"]
        (root / "report.py").write_text(spec["raw"] if "raw" in spec else script(**spec))
    cls = TaskClass(case["task_class"])
    task_id, package = None, None
    if memory in ("BOUND_THEN_CHANGED", "USER_CORRECTED", "BOUND_CURRENT", "CONFLICT"):
        task_id, head = opened(rec)
        a = bind(log, s, "sales.xlsx")
        assert rec.task_state(task_id, head.record_id, intake=m36_intake("sales.xlsx"), bindings=(a,)).persisted
        if memory == "USER_CORRECTED":
            b = bind(log, s, "sales_v2.xlsx")
            assert rec.correction(task_id, "file", log.load().task(task_id).record_id, intake=m36_intake("use sales_v2.xlsx"), replacement=b).persisted
        if memory == "BOUND_THEN_CHANGED":
            make_workbook(root / "sales.xlsx", _sheets(case["sheets"], battery) | {"Extra": (("x",), ())})
        if memory == "CONFLICT": _fork(env, task_id)
    accept = acceptance() if cls is TaskClass.SCRIPT_WORKBOOK_REPAIR else report_acceptance(cls.value)
    task = env.task(cls, accept=accept, task_id=task_id)
    if memory in ("BOUND_THEN_CHANGED", "USER_CORRECTED", "BOUND_CURRENT", "CONFLICT"):
        package = build_context(log.load(), s, task_id)
    if memory == "CHANGED_AFTER_TASK":
        make_workbook(root / "sales.xlsx", _sheets(case["sheets"], battery) | {"Extra": (("x",), ())})
    before = _originals(root)
    result = env.edge.handle(task, package)
    after = _originals(root)
    claim_first = True
    verifier_status = None
    if result.local and result.local.claim_record_id:
        index = log.load()
        claim = index.records[result.local.claim_record_id]
        claim_first = claim.payload["verification_status"] in (VerificationStatus.CLAIMED_ONLY, VerificationStatus.FAILED)
        if result.local.verifier_record_id:
            verifier_status = str(index.records[result.local.verifier_record_id].payload["verification_status"])
    return {"id": case["id"], "route": result.route, "reason": result.decision.reason.value,
            "local_attempted": result.local is not None, "local_verification": result.local.verification_status if result.local else None,
            "memory_verifier_status": verifier_status, "claim_recorded_as_claim_first": claim_first,
            "original_modified": before != after, "latency_ms": env.telemetry.events()[-1]["latency_ms"],
            "unresolved": list(result.escalation.unresolved) if result.escalation else []}


def evaluate(battery, runs):
    cases = {c["id"]: c for c in battery["cases"]}
    first = runs[0]
    m = {"decision_accuracy": sum(1 for r in first if [r["route"], r["reason"]] == cases[r["id"]]["expected"]) / len(first),
         "false_local_success": sum(1 for run in runs for r in run if r["route"] == "LOCAL_VERIFIED" and r["memory_verifier_status"] != "VERIFIED"),
         "unsafe_local_on_ambiguous_or_dynamic": sum(1 for run in runs for r in run
                                                     if set(cases[r["id"]]["tags"]) & {"ambiguous", "dynamic"} and r["local_attempted"]),
         "stale_corrected_or_conflict_not_clarified": sum(1 for run in runs for r in run
                                                          if set(cases[r["id"]]["tags"]) & {"stale", "corrected", "conflict"} and r["route"] != "CLARIFY"),
         "original_modified": sum(1 for run in runs for r in run if r["original_modified"]),
         "claims_not_recorded_claimed_only_first": sum(1 for run in runs for r in run if not r["claim_recorded_as_claim_first"]),
         "determinism_mismatches": sum(1 for a, b in zip(runs[0], runs[1]) if (a["route"], a["reason"], a["local_verification"]) != (b["route"], b["reason"], b["local_verification"])),
         "avoidance_rate": sum(1 for r in first if r["route"] == "LOCAL_VERIFIED") / len(first),
         "local_attempt_failures": sum(1 for r in first if r["local_attempted"] and r["route"] != "LOCAL_VERIFIED"),
         "latency_ms_p50": statistics.median(r["latency_ms"] for run in runs for r in run),
         "latency_ms_p95": sorted(r["latency_ms"] for run in runs for r in run)[int(0.95 * (len(first) * len(runs)) ) - 1]}
    return m


def gate(gate_spec, metrics):
    ops = {"==": lambda a, b: a == b, "<=": lambda a, b: a <= b, ">=": lambda a, b: a >= b}
    checks = {k: {"value": metrics[k], "threshold": v, "pass": ops[v["op"]](metrics[k], v["value"])} for k, v in gate_spec["thresholds"].items()}
    return all(c["pass"] for c in checks.values()), checks


def main():
    battery_bytes, gate_bytes = lf(BATTERY), lf(GATE)
    battery, gate_spec = json.loads(battery_bytes), json.loads(gate_bytes)
    runs = []
    for _ in range(gate_spec["runs"]):
        results = []
        for case in battery["cases"]:
            with tempfile.TemporaryDirectory(prefix="m37q-") as d:
                results.append(run_case(case, battery, Path(d)))
        runs.append(results)
    metrics = evaluate(battery, runs)
    passed, checks = gate(gate_spec, metrics)
    out = {"schema_version": "m37.qualification-results.v1", "battery_sha256": hashlib.sha256(battery_bytes).hexdigest(),
           "gate_sha256": hashlib.sha256(gate_bytes).hexdigest(), "python": sys.version.split()[0], "platform": sys.platform,
           "gate_passed": passed, "checks": checks, "metrics": metrics, "runs": runs}
    RESULTS.write_text(json.dumps(out, indent=1, sort_keys=True) + "\n")
    if passed:
        record = {"schema_version": QUALIFICATION_SCHEMA_VERSION, "capabilities": [
            {"capability_id": c.capability_id, "version": c.version, "mechanism": c.mechanism.value, "status": "QUALIFIED",
             "passed": True, "evidence": f"docs/plans/M37_QUALIFICATION_RESULTS.json#battery={out['battery_sha256'][:16]}"} for c in CAPABILITIES]}
        EVIDENCE.write_text(json.dumps(record, indent=1, sort_keys=True) + "\n")
    print(json.dumps({"gate_passed": passed, "metrics": metrics}, indent=1))
    for r in runs[0]:
        print(r["id"], r["route"], r["reason"], r["local_verification"])
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
