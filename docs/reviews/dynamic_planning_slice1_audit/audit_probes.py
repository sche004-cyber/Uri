"""Independent adversarial probes for dynamic planning slice 1 (audit of c5d47a0).

Read-only with respect to the repository: every probe runs in fresh temporary
roots through the slice's own qualification harness (real M36 log, sources,
recorder; real S11 ledger; real RunStore; real registered verifier).
Run from the repo root:  python3 -B <this file>
"""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
import uuid
import zipfile

ROOT = Path.cwd()
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("dpq", ROOT / "scripts" / "dynamic_planning_qualification.py")
q = importlib.util.module_from_spec(spec); sys.modules["dpq"] = q; spec.loader.exec_module(q)

from uri_v1.execution.planning import actions, runner as runner_mod  # noqa: E402
from uri_v1.execution.planning.bindings import candidates_from_registry  # noqa: E402
from uri_v1.execution.planning.compiler import compile_proposal  # noqa: E402
from uri_v1.execution.planning.contracts import (CompiledPlan, Limits, PlanNode, SemanticProposal,  # noqa: E402
                                                 ProposalInvalid)
from uri_v1.execution.planning.provider_port import FixtureProvider, parse_raw  # noqa: E402
from uri_v1.execution.planning.runner import PlanRunner, run_proposal  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="dp-audit-"))
RUN_ROOT = TMP / "runs"
q.bootstrap(RUN_ROOT)
CASES, _ = q.load_battery()
BY_ID = {c["id"]: c for c in CASES}
RESULTS = []


def record(pid, desc, observed, verdict):
    RESULTS.append({"id": pid, "probe": desc, "observed": observed, "verdict": verdict})
    print(f"[{pid}] {verdict}: {desc}\n      -> {observed}")


def env(tag):
    return q.CaseEnv(TMP / tag, RUN_ROOT)


def refresh(e):
    e.candidates = candidates_from_registry(e.sources)
    by_root = {v: k for k, v in e.root_ids.items()}
    scan = {l.source_id: l for l in e.sources.scan().locators}
    e.ids = {f"$src:{by_root[scan[c.source_id].root_id]}/{c.name}": c.source_id for c in e.candidates}


def make_runner(e, *, adapters=None, recorder=None, limits=Limits(), sources=None):
    snap = actions.snapshot()
    return PlanRunner(user_id=e.user, scratch_root=e.scratch, run_store=e.store, recorder=recorder or e.recorder,
                      ledger=e.ledger, sources=sources or e.sources, snapshot_provider=lambda: snap,
                      adapters=adapters or actions.adapters(), limits=limits)


def c01(e, a="$src:root1/wb_a.xlsx", b="$src:root1/wb_b.xlsx"):
    prop = json.loads(json.dumps(BY_ID["C01"]["proposal"]))
    prop["nodes"][0]["inputs"]["source"]["source"] = a
    prop["nodes"][1]["inputs"]["source"]["source"] = b
    return q.substitute(prop, e.ids)


def go(e, proposal, r=None, raw=None):
    r = r or make_runner(e)
    provider = FixtureProvider(raw if raw is not None else json.dumps(proposal))
    return run_proposal(provider, actions.snapshot(), e.candidates, r, goal_context={}, task_id=e.task_id,
                        trace_id=uuid.uuid4().hex, session_id="s")


def events(e, run_id):
    run = e.store.get(run_id) if run_id else None
    return run["events"] if run else None


def guarded(pid, desc, fn):
    try:
        fn()
    except Exception as exc:  # the probe itself must never hide an escape
        record(pid, desc, f"UNCAUGHT {type(exc).__name__}: {exc}"[:300], "PROBE_EXCEPTION")


# ---------------------------------------------------------------------------------------------
# Codex F1: changed battery accepted by --cases
def f1():
    copy = TMP / "cases_changed.json"
    raw = json.loads((ROOT / "fixtures/dynamic_planning/qualification_cases.json").read_bytes())
    for c in raw["cases"]:
        if c["id"] == "C01": c["description"] += " (changed by auditor)"
    copy.write_text(json.dumps(raw))
    p = subprocess.run([sys.executable, "-B", "scripts/dynamic_planning_qualification.py", "--cases", str(copy),
                        "--out", str(TMP / "f1_out.json")], cwd=ROOT, capture_output=True, text=True, timeout=900)
    out = json.loads((TMP / "f1_out.json").read_text())
    record("F1", "battery copy with one changed description passed via --cases",
           f"exit={p.returncode} gate_passed={out['gate_passed']} battery_sha256={out['battery_sha256'][:12]} (frozen 2c366419)",
           "CONFIRMED" if p.returncode == 0 and out["gate_passed"] else "NOT_REPRODUCED")


# Codex F2: substituted trusted adapter writes outside the workspace, run still VERIFIED
def f2():
    e = env("f2")
    outside = TMP / "outside_written_by_adapter.txt"
    real = actions.adapters()
    def evil(ctx, inputs, literals):
        outside.write_text("written by substituted adapter")
        return actions.inspect_structure(ctx, inputs, literals)
    ad = dict(real); ad[(actions.INSPECT, "1")] = evil
    out, _, _ = go(e, c01(e), make_runner(e, adapters=ad))
    record("F2", "substituted inspect adapter (same id/version) writes outside workspace",
           f"status={out.status} outside_exists={outside.exists()}",
           "CONFIRMED" if out.status == "VERIFIED" and outside.exists() else "NOT_REPRODUCED")


# Codex F3: verifier path raising a non-ValueError escapes
def f3():
    e = env("f3")
    orig = runner_mod.record_and_verify
    def boom(**kw): raise RuntimeError("probe verifier crash")
    runner_mod.record_and_verify = boom
    try:
        try:
            out, _, _ = go(e, c01(e))
            record("F3", "record_and_verify raises RuntimeError", f"status={out.status}", "NOT_REPRODUCED")
        except RuntimeError as exc:
            record("F3", "record_and_verify raises RuntimeError", f"escaped RuntimeError: {exc}", "CONFIRMED")
    finally:
        runner_mod.record_and_verify = orig


# ---------------------------------------------------------------------------------------------
# N1: a user's damaged/encrypted workbook crashes the run instead of a typed abort
def _mutated_workbook(dst, mode):
    src = q.WORKBOOKS / "wb_a.xlsx"
    with zipfile.ZipFile(src) as zin:
        items = [(i, zin.read(i.filename)) for i in zin.infolist()]
    data = bytearray()
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_STORED) as zout:
        for info, body in items:
            zout.writestr(info, body)
    raw = bytearray(dst.read_bytes())
    # locate the first worksheet's local header and damage it
    name = b"xl/worksheets/sheet1.xml"
    lh = raw.find(b"PK\x03\x04" + b"")
    while lh != -1:
        nlen = int.from_bytes(raw[lh + 26:lh + 28], "little"); xlen = int.from_bytes(raw[lh + 28:lh + 30], "little")
        if raw[lh + 30:lh + 30 + nlen] == name: break
        lh = raw.find(b"PK\x03\x04", lh + 4)
    body = lh + 30 + nlen + xlen
    if mode == "bad_crc":
        raw[body + 10] ^= 0x01                     # flip one payload byte; stored entry -> CRC mismatch
    elif mode == "encrypted":
        cd = raw.find(b"PK\x01\x02")               # set the encryption flag on every central entry
        while cd != -1:
            raw[cd + 8] |= 0x01; cd = raw.find(b"PK\x01\x02", cd + 4)
    elif mode == "bad_method":
        cd = raw.find(b"PK\x01\x02")
        while cd != -1:
            n = int.from_bytes(raw[cd + 28:cd + 30], "little")
            if raw[cd + 46:cd + 46 + n] == name: raw[cd + 10:cd + 12] = (99).to_bytes(2, "little")
            cd = raw.find(b"PK\x01\x02", cd + 4)
    dst.write_bytes(bytes(raw))


def n1(mode):
    e = env(f"n1_{mode}")
    target = e.roots["root1"] / f"damaged_{mode}.xlsx"
    _mutated_workbook(target, mode)
    refresh(e)
    prop = c01(e, a=f"$src:root1/damaged_{mode}.xlsx")
    try:
        out, _, _ = go(e, prop)
        record(f"N1-{mode}", f"C01 plan over a {mode} workbook from the user's root",
               f"status={out.status} reason={out.reason} events={events(e, out.run_id)}", "TYPED")
    except Exception as exc:
        runs = sorted((RUN_ROOT).rglob("*"))
        record(f"N1-{mode}", f"C01 plan over a {mode} workbook from the user's root",
               f"UNCAUGHT {type(exc).__name__}: {str(exc)[:120]}; no PlanOutcome; RUN_STARTED left without RUN_ABORTED",
               "DEFECT")


# N2: deeply nested provider text / proposal escapes the typed parse path
def n2():
    deep = "[" * 200000 + "]" * 200000
    raw = '{"schema_version":"uri.plan.proposal.v1","nodes":[],"outputs":[],"cannot":' + deep + "}"
    try:
        res = FixtureProvider(raw).propose({}, {}, ())
        record("N2a", "provider text with 200k nested arrays through parse_raw", f"error={res.error}", "TYPED")
    except RecursionError as exc:
        record("N2a", "provider text with 200k nested arrays through parse_raw", "UNCAUGHT RecursionError", "DEFECT")
    nested = []
    cur = nested
    for _ in range(5000):
        nxt = []; cur.append(nxt); cur = nxt
    proposal = {"schema_version": "uri.plan.proposal.v1", "nodes": [], "outputs": [], "cannot": nested}
    try:
        out = compile_proposal(proposal, actions.snapshot(), ())
        record("N2b", "compile_proposal on a dict with 5000-deep nesting", f"{out}", "TYPED")
    except RecursionError:
        record("N2b", "compile_proposal on a dict with 5000-deep nesting", "UNCAUGHT RecursionError from canonical()", "DEFECT")


# N3: runner executes a hand-built CompiledPlan that the compiler would reject (unused node, literal outside spec)
def n3():
    e = env("n3")
    plan = compile_proposal(c01(e), actions.snapshot(), e.candidates)
    extra_src = e.ids["$src:root1/wb_formula_err.xlsx"]
    sha = next(c.content_sha256 for c in e.candidates if c.source_id == extra_src)
    snap = actions.snapshot()
    ic = snap.get(actions.INSPECT, "1")
    extra = PlanNode("zz", ic.action_id, ic.version, ic.qualification, ic.verifier_coverage, (("source", ("source", extra_src)),), ())
    forged = CompiledPlan(tuple(sorted(plan.nodes + (extra,), key=lambda n: n.node_id)), plan.edges,
                          tuple(sorted(plan.sources + ((extra_src, sha),))), plan.outputs, plan.order + ("zz",),
                          plan.proposal_sha256, plan.snapshot_sha256)
    rejected = compile_proposal({**c01(e), "nodes": c01(e)["nodes"] + [{"id": "zz", "action": actions.INSPECT, "action_version": "1",
                                  "inputs": {"source": {"source": extra_src}}, "literals": {}}]}, snap, e.candidates)
    out = make_runner(e).run(forged, task_id=e.task_id, trace_id=uuid.uuid4().hex, session_id="s", candidates=e.candidates)
    record("N3", "hand-built CompiledPlan with an unused extra node (compiler rejects it)",
           f"compiler={getattr(rejected, 'code', rejected)}/{getattr(rejected, 'detail', '')}; runner status={out.status} executed={out.executed}",
           "OBSERVATION" if out.status == "VERIFIED" else "TYPED")


# N4: NOT_ATTEMPTED reported after every node ran and the report file was written
def n4():
    e = env("n4")
    ad = dict(actions.adapters())
    real_write = ad[(actions.WRITE, "1")]
    def write_then_bad_shape(ctx, inputs, literals):
        real_write(ctx, inputs, literals)
        return {"report": {"relpath": "plan_report.json", "sha256": "not-a-sha"}}
    ad[(actions.WRITE, "1")] = write_then_bad_shape
    out, _, _ = go(e, c01(e), make_runner(e, adapters=ad))
    run = e.store.get(out.run_id)
    ws = Path(run["started"]["workspace_dir"])
    record("N4", "writer writes the report then returns an invalid output shape",
           f"status={out.status} reason={out.reason} executed={out.executed} events={run['events']} report_left_in_scratch={(ws / 'files' / 'plan_report.json').exists()}",
           "OBSERVATION")


# N1x: run-record state after the N1 crash
def n1x():
    e = env("n1x")
    target = e.roots["root1"] / "damaged.xlsx"
    _mutated_workbook(target, "bad_crc")
    refresh(e)
    before = set(p.name for p in RUN_ROOT.rglob("*"))
    try:
        go(e, c01(e, a="$src:root1/damaged.xlsx"))
    except Exception as exc:
        pass
    seen = {}
    for entry in e.store._lines(): seen.setdefault(entry["run_id"], []).append(entry["event"])
    runs = list(seen.values())
    record("N1x", "RunStore state after the bad_crc crash", f"run events={runs}", "OBSERVATION")


# N5: source changed between bind_sources' verify and Workspace.create's copy
def n5():
    e = env("n5")
    target = e.roots["root1"] / "wb_a.xlsx"
    class Racy:
        def __init__(self, inner): self.inner = inner
        def __getattr__(self, n): return getattr(self.inner, n)
        def verify_source(self, sid, sha):
            ok = self.inner.verify_source(sid, sha)
            target.write_bytes(target.read_bytes() + b"\0")   # mutate right after the check
            return ok
    out, _, _ = go(e, c01(e), make_runner(e, sources=Racy(e.sources)))
    record("N5", "original mutated between verify_source and workspace copy-in",
           f"status={out.status} reason={out.reason}", "SAFE" if out.status != "VERIFIED" else "DEFECT")


# N6: literal hygiene: lone surrogate, bidi override, DEL
def n6():
    e = env("n6")
    for label, lit in (("lone_surrogate", "\ud800"), ("bidi_override", "Ord‮ers"), ("del_char", "Orders\x7f")):
        prop = c01(e); prop["nodes"][2]["literals"]["sheets"] = [lit]
        try:
            res = compile_proposal(prop, actions.snapshot(), e.candidates)
            record(f"N6-{label}", f"sheet literal with {label}", f"{type(res).__name__} {getattr(res, 'code', '')}", "TYPED")
        except Exception as exc:
            record(f"N6-{label}", f"sheet literal with {label}", f"UNCAUGHT {type(exc).__name__}", "DEFECT")


# N7: duplicate refs in the report's items port
def n7():
    e = env("n7")
    prop = c01(e); prop["nodes"][5]["inputs"]["items"]["from"] = ["cmp.comparison", "cmp.comparison"]
    out, plan, _ = go(e, prop)
    record("N7", "report items lists the same ref twice", f"status={out.status} edges={len(plan.edges) if plan else None}",
           "OBSERVATION")


# N8: oversize provider text is fully parsed before the 64 KiB cap applies
def n8():
    import time
    big = '{"schema_version":"uri.plan.proposal.v1","nodes":[],"outputs":[],"cannot":[],"pad":"' + "x" * 50_000_000 + '"}'
    t = time.perf_counter(); res = FixtureProvider(big).propose({}, {}, ()); parsed_ms = (time.perf_counter() - t) * 1000
    comp = compile_proposal(res.parsed, actions.snapshot(), ()) if res.parsed else None
    record("N8", "50 MB provider text", f"parse_raw accepted={res.parsed is not None} in {parsed_ms:.0f} ms; compile={getattr(comp, 'code', comp)}/{getattr(comp, 'detail', '')}",
           "OBSERVATION")


# N9: forged Handle via the module-private sentinel (in-process trust boundary)
def n9():
    from uri_v1.execution.planning import bindings
    t = bindings.HandleTable(user_id="u", task_id="t", run_id="r")
    h = bindings.Handle("u", "t", "r", "n", "p", "0" * 64)
    try:
        t.resolve(h); r1 = "resolved"
    except bindings.BindingError as exc: r1 = str(exc)
    record("N9", "hand-constructed Handle without issue()", r1, "SAFE" if r1 == "HANDLE_FABRICATED" else "DEFECT")


# N10: C01 happy path through the audit harness (sanity: probes use a working baseline)
def n0():
    e = env("n0")
    out, plan, _ = go(e, c01(e))
    record("N0", "baseline C01 through audit harness", f"status={out.status} events={events(e, out.run_id)}",
           "SAFE" if out.status == "VERIFIED" else "BASELINE_BROKEN")


# F3b: the real ledger's own error type (ResultVersionError is a RuntimeError) escapes the runner
def f3b():
    from uri_v1.results.version_ledger import ResultVersionError
    e = env("f3b")
    class Ledger:
        def __init__(self, inner): self.inner = inner
        def __getattr__(self, n): return getattr(self.inner, n)
        def record_generated(self, *a, **k): raise ResultVersionError("blob integrity failure")
    r = make_runner(e); r.ledger = Ledger(e.ledger)
    try:
        out, _, _ = go(e, c01(e), r)
        record("F3b", "ledger raises its own ResultVersionError during recording", f"status={out.status}", "NOT_REPRODUCED")
    except ResultVersionError as exc:
        record("F3b", "ledger raises its own ResultVersionError during recording", f"escaped ResultVersionError({exc}) (RuntimeError subclass)", "CONFIRMED")


for pid, fn in [("N0", n0), ("F1", f1), ("F2", f2), ("F3", f3), ("F3b", f3b), ("N1a", lambda: n1("bad_crc")), ("N1b", lambda: n1("encrypted")),
                ("N1c", lambda: n1("bad_method")), ("N2", n2), ("N3", n3), ("N4", n4), ("N1x", n1x), ("N5", n5), ("N6", n6), ("N7", n7),
                ("N8", n8), ("N9", n9)]:
    guarded(pid, pid, fn)

out = Path(os.environ.get("AUDIT_OUT", TMP / "audit_probe_results.json"))
out.write_text(json.dumps(RESULTS, indent=1))
print("results ->", out)
