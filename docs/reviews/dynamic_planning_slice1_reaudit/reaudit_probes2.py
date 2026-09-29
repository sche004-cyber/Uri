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

import collections


def open_runs(e):
    last = collections.OrderedDict()
    for ent in e.store._lines(): last[ent["run_id"]] = ent["event"]
    return {k: v for k, v in last.items()}


for exc in (SystemExit, KeyboardInterrupt):
    e = env(f"x_{exc.__name__}")
    plan = compile_proposal(c01(e), actions.snapshot(), e.candidates)
    ad = dict(actions.adapters())
    for key in list(ad):
        if key[0] == plan.node("ia").action_id:
            ad[key] = lambda ctx, i, l, exc=exc: (_ for _ in ()).throw(exc())
    try:
        make_runner(e, adapters=ad).run(plan, task_id=e.task_id, trace_id="t", session_id="s", candidates=e.candidates, snapshot=actions.snapshot())
        esc = None
    except BaseException as x:  # noqa: BLE001
        esc = type(x).__name__
    record(f"R6b-{exc.__name__}", f"adapter raises {exc.__name__}: last event per run in the store", f"escaped={esc} runs={open_runs(e)}", "OBSERVATION")


class LogProxy:
    def __init__(s, log): s._log = log
    def load(s): raise RuntimeError("log")
    def __getattr__(s, n): return getattr(s._log, n)


class RecProxy:
    def __init__(s, rec): s._rec = rec; s.log = LogProxy(rec.log)
    def __getattr__(s, n): return getattr(s._rec, n)


e = env("logload")
plan = compile_proposal(c01(e), actions.snapshot(), e.candidates)
out = make_runner(e, recorder=RecProxy(e.recorder)).run(plan, task_id=e.task_id, trace_id=uuid.uuid4().hex, session_id="s", candidates=e.candidates,
                                                          snapshot=actions.snapshot())
run = e.store.get(out.run_id)
statuses = []
for rec in e.log.load().records.values():
    p = getattr(rec, "payload", {}) or {}
    statuses.append({k: p.get(k) for k in ("kind", "verification_status", "status") if isinstance(p, dict) and k in p})
record("R6b-logload", "M36 log load fails after the verifier persisted its verdict",
       f"outcome={out.status}/{out.reason} store_events={run['events']} store_verification={run['verifications']} "
       f"m36_verdicts={statuses} rec_types={sorted({type(r).__name__ for r in e.log.load().records.values()})}", "OBSERVATION")
