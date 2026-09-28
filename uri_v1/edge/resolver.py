"""Local-first resolution: LOCAL / ESCALATE / CLARIFY (LF-1, VG-1 G1/G2).

Pure with respect to URI state: it reads hash-bound originals and the M36
`MemoryContextPackage` (E-5: consumed as-is, no Memory contract change) and
writes nothing. It never calls a model in M37.
"""
from __future__ import annotations

import hashlib
import tempfile
from pathlib import Path

from uri_v1.execution.officefile import WorkbookReadError, read_workbook_structure
from .compat import diagnose
from .contracts import DecisionKind as D, EdgeDecision, EdgeTask, EscalationRequest, Reason as R, TaskClass as T
from .scriptinfo import inspect_script

_DEGRADED = {"CONFLICT": R.MEMORY_CONFLICT, "PENDING_CORRECTION": R.MEMORY_PENDING_CORRECTION,
             "QUARANTINED_RECORDS": R.MEMORY_QUARANTINED}

# Per-class minimum acceptance (F-3): a caller-supplied AcceptanceCriteria that omits the
# check that actually exercises the class's own qualified capability must never let a
# local completion be reported VERIFIED — it would only prove something unrelated passed.
_MIN_ACCEPTANCE = {
    T.SCRIPT_WORKBOOK_REPAIR: lambda kinds, items: "script_exit_zero" in kinds,
    T.WORKBOOK_INSPECT: lambda kinds, items: any(i["kind"] == "report_recomputes" and i.get("task_class") == T.WORKBOOK_INSPECT.value for i in items),
    T.SCRIPT_WORKBOOK_DIAGNOSE: lambda kinds, items: any(i["kind"] == "report_recomputes" and i.get("task_class") == T.SCRIPT_WORKBOOK_DIAGNOSE.value for i in items),
}


def _meets_minimum_acceptance(task_class, acceptance) -> bool:
    check = _MIN_ACCEPTANCE.get(task_class)
    if check is None: return True
    items = list(acceptance.items)
    return check({i["kind"] for i in items}, items)


def read_bound(sources, source_id, content_sha256):
    """Return (bytes, filename) for a live, hash-matching original, else None."""
    scan = sources.scan()
    locator = sources.locate(source_id, scan)
    ref = sources.fingerprint(locator) if locator else None
    if ref is None or ref.content_sha256 != content_sha256: return None
    data = (Path(sources.roots()[ref.root_id]) / ref.relpath).read_bytes()
    if hashlib.sha256(data).hexdigest() != content_sha256: return None
    return data, ref.relpath.split("/")[-1]


def structure_of(data: bytes):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "w.xlsx"; p.write_bytes(data)
        return read_workbook_structure(p)


def _memory_gate(task: EdgeTask, package):
    if package is None: return None
    try:
        ctx = package.to_dict()
    except AttributeError:
        return R.INVALID_CONTEXT
    if not isinstance(ctx, dict) or ctx.get("schema_version") != "m36.context.v1": return R.INVALID_CONTEXT
    if ctx.get("degraded") in _DEGRADED: return _DEGRADED[ctx["degraded"]]
    # The package must belong to this task: a clean package built for another task_id
    # would otherwise silently bypass a real CONFLICT/correction on this one (F-6).
    if ctx.get("task") and ctx["task"].get("task_id") != task.task_id: return R.INVALID_CONTEXT
    wanted = {(i.source_id, i.content_sha256) for i in task.inputs}
    ids = {i.source_id for i in task.inputs}
    # Only stale *references* gate the task; stale historical outcomes are expected
    # after a file changes and say nothing about the current input.
    for item in ctx.get("stale", []):
        if "binding_authority" in item and item.get("source_id") in ids: return R.STALE_INPUT
    if ctx.get("task"):
        current = {r["source_id"]: r["content_sha256"] for r in ctx.get("references", [])}
        for source_id, sha in wanted:
            if source_id in current and current[source_id] != sha: return R.STALE_INPUT
            # The task's current binding moved away from this file after a user correction.
            if source_id not in current and ctx.get("corrections"): return R.CORRECTED_REFERENCE
    return None


def local_findings(task: EdgeTask, sources):
    """Deterministic, read-only inspection of the bound originals."""
    wb = read_bound(sources, task.input("workbook").source_id, task.input("workbook").content_sha256)
    if wb is None: return None, R.STALE_INPUT
    try:
        structure = structure_of(wb[0])
    except WorkbookReadError as exc:
        return {"workbook_error": str(exc)}, R.UNREADABLE_INPUT
    findings = {"workbook": dict(structure.to_dict(), name=wb[1])}
    if task.task_class is T.WORKBOOK_INSPECT: return findings, None
    sc = read_bound(sources, task.input("script").source_id, task.input("script").content_sha256)
    if sc is None: return None, R.STALE_INPUT
    findings["script_name"] = sc[1]
    findings["diagnosis"] = diagnose(inspect_script(sc[0]), structure, wb[1])
    return findings, None


def _escalate_reason(diag) -> R:
    if not diag["script"]["parse_ok"]: return R.OUTSIDE_LOCAL_ENVELOPE
    if diag["script"]["dynamic"]: return R.DYNAMIC_ACCESS
    if diag["path_mismatch"]: return R.WORKBOOK_PATH_MISMATCH
    problems = diag["missing_sheets"] + diag["missing_columns"]
    if any(p["status"] == "AMBIGUOUS" for p in problems): return R.AMBIGUOUS_REMAP
    return R.NO_REMAP


def escalation(task: EdgeTask, findings: dict, unresolved) -> EscalationRequest:
    return EscalationRequest(task.task_id, task.task_class, task.inputs, task.acceptance.to_dict(), task.acceptance.sha256,
                             findings or {}, tuple(unresolved), task.trace_id)


def resolve(task: EdgeTask, package, registry, sources) -> EdgeDecision:
    gate = _memory_gate(task, package)
    if gate is not None: return EdgeDecision(D.CLARIFY, gate, task.task_id)
    for i in task.inputs:
        if not sources.verify_source(i.source_id, i.content_sha256): return EdgeDecision(D.CLARIFY, R.STALE_INPUT, task.task_id)
    findings, problem = local_findings(task, sources)
    if problem is R.STALE_INPUT: return EdgeDecision(D.CLARIFY, R.STALE_INPUT, task.task_id)
    eligible = registry.eligible(task.task_class)
    if problem is R.UNREADABLE_INPUT:
        return EdgeDecision(D.ESCALATE, problem, task.task_id, findings=findings,
                            escalation=escalation(task, findings, ("workbook structure unreadable locally",)))
    if not eligible:
        return EdgeDecision(D.ESCALATE, R.NO_QUALIFIED_CAPABILITY, task.task_id, findings=findings,
                            escalation=escalation(task, findings, (f"no qualified local capability for {task.task_class.value}",)))
    if not _meets_minimum_acceptance(task.task_class, task.acceptance):
        return EdgeDecision(D.ESCALATE, R.ACCEPTANCE_BELOW_MINIMUM, task.task_id, findings=findings,
                            escalation=escalation(task, findings, (f"acceptance criteria omit the required check for {task.task_class.value}",)))
    cap = eligible[0].capability_id
    if task.task_class is not T.SCRIPT_WORKBOOK_REPAIR:
        return EdgeDecision(D.LOCAL, R.QUALIFIED_LOCAL, task.task_id, cap, findings)
    diag = findings["diagnosis"]
    if diag["status"] == "COMPATIBLE": return EdgeDecision(D.LOCAL, R.ALREADY_COMPATIBLE, task.task_id, cap, findings)
    if diag["status"] == "REMAPPABLE": return EdgeDecision(D.LOCAL, R.QUALIFIED_LOCAL, task.task_id, cap, findings)
    reason = _escalate_reason(diag)
    unresolved = [f"{p['literal']!r}: {p['status'].lower()} match in workbook" for p in diag["missing_sheets"] + diag["missing_columns"] if p["status"] != "UNIQUE"]
    unresolved += [f"script uses a workbook path {p!r} that is not the bound workbook" for p in diag["path_mismatch"]]
    unresolved += [f"script has {d.lower().replace('_', ' ')}" for d in diag["script"]["dynamic"]]
    return EdgeDecision(D.ESCALATE, reason, task.task_id, findings=findings,
                        escalation=escalation(task, findings, unresolved or ("script could not be analysed locally",)))
