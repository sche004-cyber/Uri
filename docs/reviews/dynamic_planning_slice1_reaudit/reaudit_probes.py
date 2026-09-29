"""Re-audit probes for dynamic planning slice 1 repair 458cbda.

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

TMP = Path(tempfile.mkdtemp(prefix="dp-reaudit-"))
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



def probe(pid, desc, fn, ok):
    try:
        obs = fn()
        verdict = ok(obs)
    except BaseException as exc:  # noqa: BLE001 - we want to see escapes of any kind
        obs, verdict = f"UNCAUGHT {type(exc).__name__}: {str(exc)[:120]}", "ESCAPED"
    record(pid, desc, obs if isinstance(obs, str) else repr(obs), verdict)


def compiled(e, proposal):
    return compile_proposal(proposal, actions.snapshot(), e.candidates)


def direct(e, plan, r=None, **kw):
    kw.setdefault("snapshot", actions.snapshot())
    return (r or make_runner(e)).run(plan, task_id=e.task_id, trace_id=uuid.uuid4().hex, session_id="s", candidates=e.candidates, **kw)


def summ(e, out):
    return f"status={out.status} reason={out.reason} rej={getattr(out.rejection, 'detail', None)} executed={out.executed} events={events(e, out.run_id)}"


# R1 F1 repair: driver digest pin
def r1():
    copy = TMP / "cases_changed.json"
    raw = json.loads((ROOT / "fixtures/dynamic_planning/qualification_cases.json").read_bytes())
    for c in raw["cases"]:
        if c["id"] == "C01": c["description"] += " (changed by re-auditor)"
    copy.write_text(json.dumps(raw))
    out = TMP / "r1_out.json"
    p = subprocess.run([sys.executable, "-B", "scripts/dynamic_planning_qualification.py", "--cases", str(copy), "--out", str(out)],
                       cwd=ROOT, capture_output=True, text=True, timeout=900)
    a = f"refuse: exit={p.returncode} out_written={out.exists()} stderr={p.stderr.strip()[:60]}"
    p2 = subprocess.run([sys.executable, "-B", "scripts/dynamic_planning_qualification.py", "--cases", str(copy), "--out", str(out), "--non-qualifying"],
                        cwd=ROOT, capture_output=True, text=True, timeout=900)
    r = json.loads(out.read_text())
    b = f"non-qualifying: exit={p2.returncode} status={r['status']} qualifying={r['qualifying']} gate_passed={r['gate_passed']}"
    crlf = TMP / "cases_crlf.json"
    crlf.write_bytes((ROOT / "fixtures/dynamic_planning/qualification_cases.json").read_bytes().replace(b"\n", b"\r\n"))
    out3 = TMP / "r1_crlf.json"
    p3 = subprocess.run([sys.executable, "-B", "scripts/dynamic_planning_qualification.py", "--cases", str(crlf), "--out", str(out3)],
                        cwd=ROOT, capture_output=True, text=True, timeout=900)
    r3 = json.loads(out3.read_text()) if out3.exists() else {}
    c = f"crlf copy of frozen battery: exit={p3.returncode} qualifying={r3.get('qualifying')} gate={r3.get('gate_passed')}"
    return (p.returncode, out.exists(), p2.returncode, r["qualifying"], r["gate_passed"], p3.returncode, r3.get("qualifying"), f"{a}; {b}; {c}")


probe("R1", "driver: changed battery refused; --non-qualifying labelled and gate forced false; CRLF copy of frozen battery",
      r1, lambda o: "HOLDS" if o[0] == 2 and not o[1] and o[2] != 0 and o[3] is False and o[4] is False and o[5] == 0 and o[6] is True else "DEFECT")


# R2 liveness of plan re-derivation: legit proposals written in other valid forms still verify
def r2(variant):
    def fn():
        e = env(f"r2_{variant}")
        p = c01(e)
        if variant == "reversed_nodes": p["nodes"] = list(reversed(p["nodes"]))
        if variant == "bare_items_ref": p["nodes"][5]["inputs"]["items"] = {"from": "cmp.comparison"}
        if variant == "key_order": p = {k: p[k] for k in reversed(list(p))}; p["nodes"] = [{k: n[k] for k in reversed(list(n))} for n in p["nodes"]]
        if variant == "dup_items": p["nodes"][5]["inputs"]["items"] = {"from": ["cmp.comparison", "cmp.comparison"]}
        if variant == "whitespace_raw":
            raw = json.dumps(p, indent=7)
            return summ(e, go(e, p, raw=raw)[0])
        return summ(e, go(e, p)[0])
    return fn


for v in ("reversed_nodes", "bare_items_ref", "key_order", "dup_items", "whitespace_raw"):
    probe(f"R2-{v}", f"valid C01 proposal written as {v} through run_proposal", r2(v), lambda o: "HOLDS" if o.startswith("status=VERIFIED") else "REGRESSION")


# R3 raw proposal binding
def r3(kind):
    def fn():
        e = env(f"r3_{kind}")
        p = c01(e)
        plan = compiled(e, p)
        other = c01(e); other["nodes"][2]["literals"]["sheets"] = ["Customers"]
        raw = {"other": json.dumps(other), "garbage": "{not json", "same_reformatted": json.dumps(p, indent=2),
               "huge": " " * 300_000 + json.dumps(p)}[kind]
        return summ(e, direct(e, plan, raw_proposal=raw))
    return fn


probe("R3-other", "compiled C01 run with raw_proposal of a different proposal", r3("other"), lambda o: "HOLDS" if "PROPOSAL_DIFFERS" in o and "REJECTED" in o else "DEFECT")
probe("R3-garbage", "compiled C01 run with unparseable raw_proposal", r3("garbage"), lambda o: "HOLDS" if "REJECTED" in o else "DEFECT")
probe("R3-same", "compiled C01 run with the same proposal reformatted", r3("same_reformatted"), lambda o: "HOLDS" if o.startswith("status=VERIFIED") else "REGRESSION")
probe("R3-huge", "compiled C01 run with the same proposal padded past the raw cap", r3("huge"), lambda o: "OBSERVATION")


# R4 snapshot argument
def r4(kind):
    def fn():
        e = env(f"r4_{kind}")
        plan = compiled(e, c01(e))
        if kind == "none": return summ(e, direct(e, plan, snapshot=None))
        if kind == "missing_kw": return summ(e, make_runner(e).run(plan, task_id=e.task_id, trace_id="t", session_id="s", candidates=e.candidates))

        class Other:
            sha256 = "0" * 64
            def get(self, *a): return actions.snapshot().get(*a)
        return summ(e, direct(e, plan, snapshot=Other()))
    return fn


for k in ("none", "missing_kw", "wrong_sha"):
    probe(f"R4-{k}", f"runner snapshot argument {k}", r4(k), lambda o: "HOLDS" if o.startswith("status=REJECTED") and "events=None" in o else "DEFECT")


# R5 plan tampering the compiler would not produce
def r5(kind):
    def fn():
        e = env(f"r5_{kind}")
        plan = compiled(e, c01(e))
        import dataclasses
        if kind == "order_swapped":
            forged = dataclasses.replace(plan, order=tuple(reversed(plan.order)))
        elif kind == "proposal_sha":
            forged = dataclasses.replace(plan, proposal_sha256="f" * 64)
        elif kind == "literal_changed":
            nodes = tuple(dataclasses.replace(n, literals=(("sheets", ("Customers",)),)) if n.node_id == "sa" else n for n in plan.nodes)
            forged = dataclasses.replace(plan, nodes=nodes)
        elif kind == "source_hash":
            forged = dataclasses.replace(plan, sources=tuple((s, "0" * 64) for s, _ in plan.sources))
        elif kind == "qual_sha":
            nodes = tuple(dataclasses.replace(n, qualification_sha="0" * 64) if n.node_id == "ia" else n for n in plan.nodes)
            forged = dataclasses.replace(plan, nodes=nodes)
        elif kind == "candidates_shrunk":
            return summ(e, (make_runner(e)).run(plan, task_id=e.task_id, trace_id="t", session_id="s", candidates=e.candidates[:1],
                                                 snapshot=actions.snapshot()))
        return summ(e, direct(e, forged))
    return fn


for k in ("order_swapped", "proposal_sha", "literal_changed", "source_hash", "qual_sha", "candidates_shrunk"):
    probe(f"R5-{k}", f"hand-altered CompiledPlan: {k}", r5(k), lambda o: "HOLDS" if o.startswith("status=REJECTED") and "events=None" in o else "DEFECT")


# R6 failure-path closure beyond the prior probes
class Boom(Exception):
    pass


def wrap_adapter(target_action, behaviour):
    base = actions.adapters()
    out = dict(base)
    for key, fn in base.items():
        if key[0] == target_action:
            out[key] = behaviour(fn)
    return out


def r6(kind):
    def fn():
        e = env(f"r6_{kind}")
        plan = compiled(e, c01(e))
        if kind == "writer_raises_before_write":
            ad = wrap_adapter(plan.node("w").action_id, lambda f: (lambda ctx, i, l: (_ for _ in ()).throw(Boom("x"))))
            return summ(e, direct(e, plan, make_runner(e, adapters=ad)))
        if kind in ("systemexit", "keyboardinterrupt"):
            exc = SystemExit if kind == "systemexit" else KeyboardInterrupt
            ad = wrap_adapter(plan.node("ia").action_id, lambda f: (lambda ctx, i, l: (_ for _ in ()).throw(exc())))
            r = make_runner(e, adapters=ad)
            try:
                return summ(e, direct(e, plan, r))
            except BaseException as x:  # noqa: BLE001
                runs = [e.store.get(p.name) for p in RUN_ROOT.glob("*") if p.is_dir()]
                return f"ESCAPED {type(x).__name__}; open runs in store: {sum(1 for rr in runs if rr and rr['events'] and rr['events'][-1] == 'RUN_STARTED')}"
        if kind == "snapshot_provider_raises":
            r = make_runner(e)
            calls = {"n": 0}
            snap = actions.snapshot()
            def sp():
                calls["n"] += 1
                if calls["n"] == 3: raise Boom("provider")
                return snap
            r.snapshot_provider = sp
            return summ(e, direct(e, plan, r))
        if kind in ("store_fails_on_abort", "store_fails_on_start"):
            r = make_runner(e)
            real = e.store.append
            def app(run_id, ev, data):
                if (ev == "RUN_ABORTED" and kind == "store_fails_on_abort") or (ev == "RUN_STARTED" and kind == "store_fails_on_start"):
                    raise OSError("disk")
                return real(run_id, ev, data)
            r.store = type("S", (), {"append": staticmethod(app), "get": staticmethod(e.store.get)})()
            ad = wrap_adapter(plan.node("ia").action_id, lambda f: (lambda ctx, i, l: (_ for _ in ()).throw(Boom("x"))))
            r.adapters = ad
            return summ(e, direct(e, plan, r))
        if kind == "log_load_fails_after_verdict":
            class LogProxy:
                def __init__(s, log): s._log = log
                def load(s): raise Boom("log")
                def __getattr__(s, n): return getattr(s._log, n)
            class RecProxy:
                def __init__(s, rec): s._rec = rec; s.log = LogProxy(rec.log)
                def __getattr__(s, n): return getattr(s._rec, n)
            out = direct(e, plan, make_runner(e, recorder=RecProxy(e.recorder)))
            recs = e.log.load().records
            verdicts = [str(r.payload.get("verification_status")) for r in recs.values() if isinstance(r.payload, dict) and "verification_status" in r.payload]
            return summ(e, out) + f" m36_log_verdicts={verdicts}"
    return fn


probe("R6-writer", "writer adapter raises before writing anything", r6("writer_raises_before_write"),
      lambda o: "OBSERVATION" if "RUN_ABORTED" in o and "VERIFIED" not in o.split()[0].replace("NOT_VERIFIED", "") else "DEFECT")
probe("R6-sysexit", "adapter raises SystemExit (trusted code)", r6("systemexit"), lambda o: "OBSERVATION")
probe("R6-kbint", "adapter raises KeyboardInterrupt (trusted code)", r6("keyboardinterrupt"), lambda o: "OBSERVATION")
probe("R6-snapprov", "live snapshot provider raises mid-run", r6("snapshot_provider_raises"),
      lambda o: "HOLDS" if "RUN_ABORTED" in o and "RUNNER_ERROR" in o else "DEFECT")
probe("R6-store-abort", "run store refuses RUN_ABORTED after an adapter failure", r6("store_fails_on_abort"),
      lambda o: "HOLDS" if "RUN_NOT_CLOSED" in o and not o.startswith("status=VERIFIED") else "DEFECT")
probe("R6-store-start", "run store refuses RUN_STARTED", r6("store_fails_on_start"),
      lambda o: "HOLDS" if o.startswith("status=NOT_ATTEMPTED") and "RUN_RECORD_ERROR" in o else "DEFECT")
probe("R6-logload", "M36 log load fails after the verifier persisted its verdict", r6("log_load_fails_after_verdict"), lambda o: "OBSERVATION")


# R7 provider port
def r7(kind):
    def fn():
        e = env(f"r7_{kind}")
        class P:
            provider_id = "p"; model_id = "m"; config_sha256 = ""
            def propose(self, *a):
                if kind == "raises": raise Boom("net")
                return None
        return summ(e, run_proposal(P(), actions.snapshot(), e.candidates, make_runner(e), goal_context={}, task_id=e.task_id,
                                    trace_id="t", session_id="s")[0])
    return fn


probe("R7-raises", "provider.propose raises", r7("raises"), lambda o: "HOLDS" if "PROVIDER_UNAVAILABLE" in o else "DEFECT")
probe("R7-none", "provider.propose returns None (not a ProviderResult)", r7("none"), lambda o: "OBSERVATION")


# R8 parse_raw boundaries
def r8():
    from uri_v1.execution.planning.provider_port import MAX_RAW_BYTES
    e = env("r8")
    body = json.dumps(c01(e))
    under = body + " " * (MAX_RAW_BYTES - len(body))
    over = under + " "
    astral = json.dumps({"x": "\U0001F600" * (MAX_RAW_BYTES // 4)})
    deep16 = "[" * 15 + "]" * 15
    return (parse_raw(under) is not None, parse_raw(over) is None, parse_raw(astral) is None,
            parse_raw('{"a":' + deep16 + "}") is not None, parse_raw('{"a":' + "[" * 16 + "]" * 16 + "}") is None)


probe("R8", "parse_raw: at cap accepted, cap+1 refused, 4-byte chars counted as bytes, depth 16 ok / 17 refused", r8,
      lambda o: "HOLDS" if all(o) else "CHECK")


print(json.dumps(RESULTS, indent=1), file=open(TMP / "results.json", "w"))
print("RESULTS_JSON", TMP / "results.json")
