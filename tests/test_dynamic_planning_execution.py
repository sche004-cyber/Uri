"""Dynamic planning slice 1, gate G4: bounded execution and authority."""
import importlib.util
import json
from pathlib import Path
import sys
import uuid

import pytest

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution.planning import actions
from uri_v1.execution.planning.compiler import compile_proposal
from uri_v1.execution.planning.contracts import Limits
from uri_v1.execution.planning.runner import PlanRunner

ROOT = Path(__file__).resolve().parents[1]


def qual():
    name = "dynamic_planning_qualification"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name]


@pytest.fixture
def ctx(tmp_path, monkeypatch):
    q = qual()
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    q.bootstrap(tmp_path / "runs")
    cases, _ = q.load_battery()
    by_id = {c["id"]: c for c in cases}
    run = lambda case_id, **over: q.run_case(dict(by_id[case_id], **over), by_id, tmp_path / "cases", tmp_path / "runs")
    return q, by_id, run, tmp_path


@pytest.mark.parametrize("case_id", ["C01", "C03", "C04"])
def test_compiled_plans_run_and_verify(ctx, case_id):
    obs = ctx[2](case_id)
    assert obs["status"] == "VERIFIED", obs
    assert obs["memory_verification"] == "VERIFIED" and obs["runstore_verification"] == "VERIFIED"
    assert obs["executed"] == obs["adapter_calls"] == obs["plan"]["order"]
    assert obs["run_events"] == ["RUN_STARTED", "RUN_RESULT", "VERIFICATION"]
    assert not obs["originals_changed_during_run"]


def test_happy_path_report_content(ctx):
    report = json.loads(ctx[2]("C01")["report_bytes"])
    (item,) = report["items"]
    assert item["type"] == "STRUCTURE_COMPARISON"
    assert item["value"]["shared_sheets"] == [{"name": "Orders", "shared": ["Id", "Date", "Amount"], "only_left": [],
                                                "only_right": ["Region"]}]


@pytest.mark.parametrize("case_id", ["C22", "C23"])
def test_capability_changed_between_compile_and_run_stops_descendants(ctx, case_id):
    obs = ctx[2](case_id)
    assert obs["status"] == "NOT_ATTEMPTED" and obs["reason"] == "CAPABILITY_CHANGED"
    assert obs["adapter_calls"] == ["ia", "ib"] and obs["executed"] == ["ia", "ib"]
    assert obs["run_events"] == ["RUN_STARTED", "RUN_ABORTED"]


def test_header_ceiling_stops_the_run(ctx):
    obs = ctx[2]("C24")
    assert obs["status"] == "NOT_ATTEMPTED" and obs["reason"] == "XLSX_HEADER_TOO_WIDE" and obs["adapter_calls"] == ["ia"]


def test_proposal_cannot_add_approval_or_effect(ctx):
    obs = ctx[2]("C25")
    assert obs["status"] == "REJECTED" and obs["rejection_code"] == "PROPOSAL_INVALID" and obs["run_id"] is None


def _runner_env(ctx, adapters=None, limits=Limits()):
    q, by_id, _, tmp = ctx
    env = q.CaseEnv(tmp / uuid.uuid4().hex, tmp / "runs")
    snap = actions.snapshot()
    runner = PlanRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=env.recorder, ledger=env.ledger,
                        sources=env.sources, snapshot_provider=lambda: snap, adapters=adapters or actions.adapters(), limits=limits)
    plan = compile_proposal(q.substitute(by_id["C01"]["proposal"], env.ids), snap, env.candidates)
    return env, runner, plan


def _run(env, runner, plan, snapshot=None):
    return runner.run(plan, task_id=env.task_id, trace_id=uuid.uuid4().hex, session_id="session", candidates=env.candidates,
                      snapshot=snapshot or actions.snapshot())


def test_output_ceiling_fires(ctx):
    env, runner, plan = _runner_env(ctx, limits=Limits(max_output_bytes=40))
    out = _run(env, runner, plan)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "OUTPUT_TOO_LARGE" and out.executed == ("ia",)


def test_adapter_returning_an_undeclared_shape_issues_nothing(ctx):
    adapters = dict(actions.adapters())
    adapters[(actions.SELECT, "1")] = lambda c, i, l: {"selection": {"anything": True}}
    env, runner, plan = _runner_env(ctx, adapters)
    out = _run(env, runner, plan)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "OUTPUT_TYPE_INVALID" and out.executed[-1] == "sa"
    adapters[(actions.SELECT, "1")] = lambda c, i, l: {"selection": i["structure"], "bonus": 1}
    env, runner, plan = _runner_env(ctx, adapters)
    assert _run(env, runner, plan).reason == "OUTPUT_TYPE_INVALID"


def test_missing_adapter_is_capability_changed(ctx):
    adapters = {k: v for k, v in actions.adapters().items() if k[0] != actions.COMPARE}
    env, runner, plan = _runner_env(ctx, adapters)
    out = _run(env, runner, plan)
    assert out.reason == "CAPABILITY_CHANGED" and "cmp" not in out.executed


def test_node_time_ceiling(ctx, monkeypatch):
    import time
    real = time.perf_counter
    ticks = iter(range(0, 10 ** 6, 20))
    monkeypatch.setattr(time, "perf_counter", lambda: float(next(ticks)))
    env, runner, plan = _runner_env(ctx, limits=Limits(node_seconds=5.0, run_seconds=10 ** 9))
    out = _run(env, runner, plan)
    monkeypatch.setattr(time, "perf_counter", real)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "NODE_TIME_EXCEEDED" and out.executed == ("ia",)


def test_plan_json_is_in_the_bundle_before_run_started(ctx):
    env, runner, plan = _runner_env(ctx)
    seen = {}
    real_append = env.store.append
    def append(run_id, event, data):
        if event == "RUN_STARTED":
            seen["plan"] = (Path(data["workspace_dir"]) / "bundle" / "plan.json").read_bytes()
        return real_append(run_id, event, data)
    env.store.append = append
    out = _run(env, runner, plan)
    assert out.status == "VERIFIED" and seen["plan"] == plan.canonical()
    started = env.store.get(out.run_id)["started"]
    assert started["executor"] == "LOCAL_EDGE" and started["capability_id"] == "uri.plan.compiled"
    assert started["plan_sha256"] == plan.sha256
    assert started["acceptance"]["items"][1]["task_class"] == "PLANNED_STRUCTURE_REPORT@" + plan.sha256


def test_runner_refuses_anything_but_a_compiled_plan(ctx):
    env, runner, plan = _runner_env(ctx)
    out = runner.run(plan.to_dict(), task_id=env.task_id, trace_id="t", session_id="s", candidates=env.candidates,
                     snapshot=actions.snapshot())
    assert out.status == "REJECTED" and out.reason == "PLAN_NOT_COMPILED" and out.run_id is None


# -- repair round after the independent audit of c5d47a0 (F3, N1, N3, N4) ---------------------------------

def _terminal(env, run_id):
    events = env.store.get(run_id)["events"]
    assert events[0] == "RUN_STARTED" and events[-1] in ("RUN_ABORTED", "VERIFICATION"), events
    return events


def _damaged(src, dst, mode):
    """Copy of `src` with the first worksheet damaged: bad CRC, encryption flag or unknown compression method."""
    import zipfile
    raw = bytearray(src.read_bytes())
    name = b"xl/worksheets/sheet1.xml"
    lh = raw.find(b"PK\x03\x04")
    while True:
        nlen, xlen = int.from_bytes(raw[lh + 26:lh + 28], "little"), int.from_bytes(raw[lh + 28:lh + 30], "little")
        if raw[lh + 30:lh + 30 + nlen] == name: break
        lh = raw.find(b"PK\x03\x04", lh + 4)
    assert zipfile.ZipFile(src).getinfo(name.decode()).compress_type == zipfile.ZIP_STORED
    cd = raw.find(b"PK\x01\x02")
    if mode == "bad_crc":
        raw[lh + 30 + nlen + xlen + 10] ^= 0x01
    while mode != "bad_crc" and cd != -1:
        n = int.from_bytes(raw[cd + 28:cd + 30], "little")
        if mode == "encrypted": raw[cd + 8] |= 0x01
        elif raw[cd + 46:cd + 46 + n] == name: raw[cd + 10:cd + 12] = (99).to_bytes(2, "little")
        cd = raw.find(b"PK\x01\x02", cd + 4)
    dst.write_bytes(bytes(raw))


@pytest.mark.parametrize("mode", ["bad_crc", "encrypted", "bad_method"])
def test_damaged_user_workbook_is_a_typed_abort_with_a_closed_record(ctx, mode):
    from uri_v1.execution.planning.bindings import candidates_from_registry
    q, by_id, _, tmp = ctx
    env = q.CaseEnv(tmp / uuid.uuid4().hex, tmp / "runs")
    _damaged(q.WORKBOOKS / "wb_a.xlsx", env.roots["root1"] / "damaged.xlsx", mode)
    env.candidates = candidates_from_registry(env.sources)
    name_to_id = {c.name: c.source_id for c in env.candidates}
    proposal = q.substitute(by_id["C01"]["proposal"], env.ids | {"$src:root1/wb_a.xlsx": name_to_id["damaged.xlsx"]})
    snap = actions.snapshot()
    plan = compile_proposal(proposal, snap, env.candidates)
    runner = PlanRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=env.recorder, ledger=env.ledger,
                        sources=env.sources, snapshot_provider=lambda: snap, adapters=actions.adapters())
    out = _run(env, runner, plan, snap)
    assert out.status == "NOT_ATTEMPTED" and out.run_id and out.status != "VERIFIED"
    assert out.reason in ("ACTION_FAILED", "XLSX_NOT_ZIP") or out.reason.startswith("XLSX_"), out.reason
    assert _terminal(env, out.run_id) == ["RUN_STARTED", "RUN_ABORTED"]
    assert env.store.get(out.run_id)["aborted"]["node"] == out.executed[-1]


def test_any_adapter_exception_is_a_typed_abort(ctx):
    adapters = dict(actions.adapters())
    def boom(c, i, l): raise NotImplementedError("unsupported")
    adapters[(actions.COMPARE, "1")] = boom
    env, runner, plan = _runner_env(ctx, adapters)
    out = _run(env, runner, plan)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ACTION_FAILED" and out.executed[-1] == "cmp"
    aborted = env.store.get(out.run_id)["aborted"]
    assert aborted["node"] == "cmp" and aborted["detail"] == "NotImplementedError"


class _FailingLedger:
    def __init__(self, inner, exc): self.inner, self.exc = inner, exc
    def __getattr__(self, name): return getattr(self.inner, name)
    def record_generated(self, *a, **k): raise self.exc


def test_ledger_error_during_recording_is_not_verified_with_a_closed_record(ctx):
    from uri_v1.results.version_ledger import ResultVersionError
    env, runner, plan = _runner_env(ctx)
    runner.ledger = _FailingLedger(env.ledger, ResultVersionError("blob integrity failure"))
    out = _run(env, runner, plan)
    assert out.status == "NOT_VERIFIED" and out.reason == "VERIFICATION_ERROR:ResultVersionError"
    assert _terminal(env, out.run_id) == ["RUN_STARTED", "RUN_ABORTED"]


def test_any_verifier_path_exception_is_not_verified(ctx, monkeypatch):
    from uri_v1.execution.planning import runner as runner_mod
    env, runner, plan = _runner_env(ctx)
    def boom(**kw): raise RuntimeError("verifier crash")
    monkeypatch.setattr(runner_mod, "record_and_verify", boom)
    out = _run(env, runner, plan)
    assert out.status == "NOT_VERIFIED" and out.reason == "VERIFICATION_ERROR:RuntimeError"
    assert _terminal(env, out.run_id)[-1] == "RUN_ABORTED"


def test_a_broken_run_store_still_returns_a_typed_outcome(ctx):
    env, runner, plan = _runner_env(ctx)
    real = env.store.append
    def append(run_id, event, data):
        if event != "RUN_STARTED": raise OSError("disk gone")
        return real(run_id, event, data)
    env.store.append = append
    adapters = dict(actions.adapters())
    def boom(c, i, l): raise RuntimeError("x")
    runner.adapters = adapters | {(actions.INSPECT, "1"): boom}
    out = _run(env, runner, plan)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ACTION_FAILED|RUN_NOT_CLOSED"


def test_run_that_executed_every_node_is_not_labelled_not_attempted(ctx):
    adapters = dict(actions.adapters())
    real_write = adapters[(actions.WRITE, "1")]
    def write_then_bad_shape(c, i, l):
        real_write(c, i, l)
        return {"report": {"relpath": "plan_report.json", "sha256": "not-a-sha"}}
    adapters[(actions.WRITE, "1")] = write_then_bad_shape
    env, runner, plan = _runner_env(ctx, adapters)
    out = _run(env, runner, plan)
    assert out.executed == plan.order and out.status == "NOT_VERIFIED" and out.reason == "OUTPUT_TYPE_INVALID"
    assert _terminal(env, out.run_id)[-1] == "RUN_ABORTED"


def _with_extra_node(plan, env):
    from uri_v1.execution.planning.contracts import CompiledPlan, PlanNode
    snap = actions.snapshot()
    ic = snap.get(actions.INSPECT, "1")
    extra_src = env.ids["$src:root1/wb_formula_err.xlsx"]
    sha = next(c.content_sha256 for c in env.candidates if c.source_id == extra_src)
    extra = PlanNode("zz", ic.action_id, ic.version, ic.qualification, ic.verifier_coverage, (("source", ("source", extra_src)),), ())
    return CompiledPlan(tuple(sorted(plan.nodes + (extra,), key=lambda n: n.node_id)), plan.edges,
                        tuple(sorted(plan.sources + ((extra_src, sha),))), plan.outputs, plan.order + ("zz",),
                        plan.proposal_sha256, plan.snapshot_sha256)


def test_runner_refuses_a_hand_built_plan_the_compiler_would_reject(ctx):
    from dataclasses import replace
    env, runner, plan = _runner_env(ctx)
    calls = []
    runner.adapters = {k: (lambda fn: lambda c, i, l: calls.append(c.node_id) or fn(c, i, l))(fn) for k, fn in runner.adapters.items()}
    forged = [_with_extra_node(plan, env),                                     # unused node the compiler rejects
              replace(plan, order=tuple(reversed(plan.order))),                # not a topological order
              replace(plan, nodes=tuple(replace(n, literals=(("sheets", ("Orders", "Returns")),)) if n.node_id == "sa" else n
                                        for n in plan.nodes)),                 # literal changed after compile
              replace(plan, snapshot_sha256="0" * 64)]                         # not the snapshot it claims
    for bad in forged:
        out = _run(env, runner, bad)
        assert out.status == "REJECTED" and out.reason == "PLAN_NOT_COMPILED" and out.run_id is None, out
    assert calls == []
    out = runner.run(plan, task_id=env.task_id, trace_id="t", session_id="s", candidates=env.candidates)   # no snapshot given
    assert out.status == "REJECTED" and out.rejection.detail == "SNAPSHOT_MISMATCH"
    out = runner.run(plan, task_id=env.task_id, trace_id="t", session_id="s", candidates=env.candidates,
                     snapshot=actions.snapshot(), raw_proposal='{"schema_version": "other"}')
    assert out.status == "REJECTED" and out.rejection.detail == "PROPOSAL_DIFFERS"
    assert _run(env, runner, plan).status == "VERIFIED"
