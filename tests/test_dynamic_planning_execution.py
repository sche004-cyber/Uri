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


def _run(env, runner, plan):
    return runner.run(plan, task_id=env.task_id, trace_id=uuid.uuid4().hex, session_id="session", candidates=env.candidates)


def test_output_ceiling_fires(ctx):
    env, runner, plan = _runner_env(ctx, limits=Limits(max_output_bytes=40))
    out = _run(env, runner, plan)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "OUTPUT_TOO_LARGE" and out.executed == ("ia",)


def select_undeclared_shape(c, i, l):
    return {"selection": {"anything": True}}


def select_extra_port(c, i, l):
    return {"selection": i["structure"], "bonus": 1}


@pytest.mark.parametrize("buggy", [select_undeclared_shape, select_extra_port])
def test_adapter_returning_an_undeclared_shape_issues_nothing(ctx, buggy):
    # A buggy but *qualified* select adapter (qualified only by a throwaway record): output typing still stops it.
    q, _, _, tmp = ctx
    with q.tamper_record(tmp / uuid.uuid4().hex, {actions.SELECT: buggy}):
        adapters = dict(actions.adapters()); adapters[(actions.SELECT, "1")] = buggy
        env, runner, plan = _runner_env(ctx, adapters)
        out = _run(env, runner, plan)
    assert out.status == "NOT_ATTEMPTED" and out.reason == "OUTPUT_TYPE_INVALID" and out.executed[-1] == "sa"


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
    with pytest.raises(ValueError, match="COMPILED_PLAN_REQUIRED"):
        runner.run(plan.to_dict(), task_id=env.task_id, trace_id="t", session_id="s", candidates=env.candidates)
