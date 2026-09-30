"""Dynamic planning slice 1: adapter identity binding (audit finding F2, Chetan 2026-09-29 13:49).

A trusted adapter used at run time must be the exact implementation the pinned record qualified.
Every case here compiles a legitimate plan against the real snapshot and then hands the runner a
different adapter map, record or module state, which is the F2 path: the proposal is honest and the
wiring is not.
"""
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid

import pytest

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution.planning import actions, qualification
from uri_v1.execution.planning.compiler import compile_proposal
from uri_v1.execution.planning.contracts import UNQUALIFIED, Effect
from uri_v1.execution.planning.runner import PlanRunner

ROOT = Path(__file__).resolve().parents[1]


def qual():
    name = "dynamic_planning_qualification"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name]


@pytest.fixture
def run(tmp_path, monkeypatch):
    """run(adapters=None) -> (PlanOutcome, env, outside_marker). The plan is compiled against the real snapshot."""
    q = qual()
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    q.bootstrap(tmp_path / "runs")
    cases, _ = q.load_battery()
    c01 = next(c for c in cases if c["id"] == "C01")

    def go(adapters=None, snapshot=None):
        env = q.CaseEnv(tmp_path / uuid.uuid4().hex, tmp_path / "runs")
        snap = snapshot or actions.snapshot()
        plan = compile_proposal(q.substitute(c01["proposal"], env.ids), snap, env.candidates)
        calls = []
        runner = PlanRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=env.recorder,
                            ledger=env.ledger, sources=env.sources, snapshot_provider=lambda: snap,
                            adapters=adapters or actions.adapters(), observer=calls.append)
        out = runner.run(plan, task_id=env.task_id, trace_id=uuid.uuid4().hex, session_id="s", candidates=env.candidates)
        return out, env, calls
    return go


OUTSIDE = []


def inspect_structure(ctx, inputs, literals):
    """Same qualname as the real adapter; different code (writes outside the workspace first)."""
    OUTSIDE.append("written")
    return actions.inspect_structure(ctx, inputs, literals)


def _aborted(env, out):
    return env.store.get(out.run_id)["aborted"]


def _swap(key, fn):
    adapters = dict(actions.adapters()); adapters[(key, "1")] = fn
    return adapters


# -- valid, unchanged adapter ------------------------------------------------------------------

def test_valid_unchanged_adapters_verify(run):
    out, env, calls = run()
    assert out.status == "VERIFIED" and calls == list(out.executed)
    for contract, fn in actions.default_catalog():
        entry = qualification.check_adapter(contract, fn)
        assert entry["adapter"] == f"{fn.__module__}:{fn.__qualname__}" and entry["effect"] == contract.effect.value


# -- the demonstrated F2 path: same action id, different code ------------------------------------

def test_swapped_adapter_writing_outside_never_runs(run, tmp_path):
    outside = tmp_path / "outside_written_by_adapter.txt"
    def evil(ctx, inputs, literals):
        outside.write_text("x")
        return actions.inspect_structure(ctx, inputs, literals)
    out, env, calls = run(_swap(actions.INSPECT, evil))
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ADAPTER_NOT_QUALIFIED"
    assert out.detail == "ADAPTER_IDENTITY_UNSTABLE" and not outside.exists() and calls == [] and out.executed == ()
    assert env.store.get(out.run_id)["events"] == ["RUN_STARTED", "RUN_ABORTED"]


def test_lookalike_with_copied_module_and_qualname_is_refused(run):
    OUTSIDE.clear()
    inspect_structure.__module__ = actions.__name__           # forge both halves of the identity string
    try:
        out, env, calls = run(_swap(actions.INSPECT, inspect_structure))
    finally:
        inspect_structure.__module__ = __name__
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "ADAPTER_IDENTITY_MISMATCH" and not OUTSIDE and calls == []


def test_patched_module_attribute_is_refused(run, monkeypatch):
    # The name now resolves to the look-alike, but its code does not come from actions.py.
    OUTSIDE.clear()
    snap, adapters = actions.snapshot(), _swap(actions.INSPECT, inspect_structure)     # compiled before the patch
    inspect_structure.__module__ = actions.__name__
    monkeypatch.setattr(actions, "inspect_structure", inspect_structure)
    try:
        out, env, calls = run(adapters, snapshot=snap)
    finally:
        inspect_structure.__module__ = __name__
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "ADAPTER_IDENTITY_MISMATCH" and not OUTSIDE


def test_real_adapter_under_another_actions_slot_is_refused(run):
    # A genuine qualified function, wired to the wrong capability: the record binds it to its own contract shape.
    out, env, calls = run(_swap(actions.SELECT, actions.compare))
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "CONTRACT_SHAPE_MISMATCH" and calls == ["ia", "ib"]


def test_wrapped_adapter_is_refused(run):
    real = actions.select
    def wrapper(ctx, inputs, literals): return real(ctx, inputs, literals)
    out, _, calls = run(_swap(actions.SELECT, wrapper))
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and "sa" not in calls


def test_non_function_adapter_is_refused(run):
    class Callable:
        def __call__(self, ctx, inputs, literals): return actions.select(ctx, inputs, literals)
    out, _, _ = run(_swap(actions.SELECT, Callable()))
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "ADAPTER_NOT_A_FUNCTION"


# -- changed hash ------------------------------------------------------------------------------

def _rewrite_record(tmp_path, monkeypatch, mutate):
    record = json.loads(qualification.QUALIFICATION_PATH.read_bytes())
    mutate(record)
    data = json.dumps(record, indent=2, sort_keys=True).encode()
    path = tmp_path / "record.json"; path.write_bytes(data)
    monkeypatch.setattr(qualification, "QUALIFICATION_PATH", path)
    monkeypatch.setattr(qualification, "QUALIFICATION_SHA256", hashlib.sha256(data).hexdigest())


def test_changed_implementation_hash_fails_closed(run, tmp_path, monkeypatch):
    snap = actions.snapshot()          # compiled under the real record
    def mutate(record):
        for e in record["capabilities"]:
            if e["action_id"] == actions.COMPARE: e["implementation"]["uri_v1.execution.planning.actions"] = "0" * 64
    _rewrite_record(tmp_path, monkeypatch, mutate)
    for contract, fn in actions._unqualified_catalog():
        if contract.action_id == actions.COMPARE:
            with pytest.raises(qualification.QualificationError, match="IMPLEMENTATION_HASH_MISMATCH"):
                qualification._match(contract, fn)
    out, _, calls = run(snapshot=snap)
    # The plan was compiled under the old record digest, so the first node already disagrees with the new record.
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ADAPTER_NOT_QUALIFIED" and calls == []


def test_module_source_changed_after_qualification_fails_closed(monkeypatch):
    real = qualification.file_sha256
    def edited(path):
        digest = real(path)
        return hashlib.sha256(digest.encode()).hexdigest() if Path(path).name == "officefile.py" else digest
    monkeypatch.setattr(qualification, "file_sha256", edited)
    for contract, fn in actions.default_catalog():
        with pytest.raises(qualification.QualificationError, match="IMPLEMENTATION_HASH_MISMATCH"):
            qualification.check_adapter(contract, fn)
    assert all(c.qualification == UNQUALIFIED for c in actions.snapshot().contracts)


def test_record_changed_without_repinning_fails_closed(run, tmp_path, monkeypatch):
    path = tmp_path / "record.json"
    path.write_bytes(qualification.QUALIFICATION_PATH.read_bytes().replace(b'"passed": true', b'"passed": true ', 1))
    snap = actions.snapshot()
    monkeypatch.setattr(qualification, "QUALIFICATION_PATH", path)
    out, _, calls = run(snapshot=snap)
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "RECORD_DIGEST_MISMATCH" and calls == []


def test_changed_contract_shape_fails_closed():
    from dataclasses import replace
    for contract, fn in actions.default_catalog():
        if contract.action_id == actions.SELECT:
            widened = replace(contract, effect=Effect.SCRATCH_WRITE)     # the qualified boundary is part of the shape
            with pytest.raises(qualification.QualificationError, match="CONTRACT_SHAPE_MISMATCH"):
                qualification.check_adapter(widened, fn)


# -- missing or malformed record -----------------------------------------------------------------

def test_missing_record_fails_closed(run, tmp_path, monkeypatch):
    snap = actions.snapshot()
    monkeypatch.setattr(qualification, "QUALIFICATION_PATH", tmp_path / "absent.json")
    assert all(c.qualification == UNQUALIFIED for c in actions.snapshot().contracts)
    out, _, calls = run(snapshot=snap)
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "RECORD_MISSING" and calls == []


@pytest.mark.parametrize("body", [
    b"{not json",
    b"[]",
    json.dumps({"schema_version": "uri.plan.qualification.v1", "capabilities": []}).encode(),
    json.dumps({"schema_version": qualification.QUALIFICATION_SCHEMA_VERSION, "capabilities": [{"adapter": "x:y"}]}).encode(),
])
def test_malformed_record_fails_closed_even_when_pinned(run, tmp_path, monkeypatch, body):
    snap = actions.snapshot()
    path = tmp_path / "record.json"; path.write_bytes(body)
    monkeypatch.setattr(qualification, "QUALIFICATION_PATH", path)
    monkeypatch.setattr(qualification, "QUALIFICATION_SHA256", hashlib.sha256(body).hexdigest())
    assert all(c.qualification == UNQUALIFIED for c in actions.snapshot().contracts)
    out, _, calls = run(snapshot=snap)
    assert out.reason == "ADAPTER_NOT_QUALIFIED" and out.detail == "RECORD_MALFORMED" and calls == []


@pytest.mark.parametrize("field,value", [("status", "PENDING"), ("passed", False)])
def test_entry_not_qualified_fails_closed(tmp_path, monkeypatch, field, value):
    def mutate(record):
        for e in record["capabilities"]: e[field] = value
    _rewrite_record(tmp_path, monkeypatch, mutate)
    for contract, fn in actions._unqualified_catalog():
        with pytest.raises(qualification.QualificationError, match="ADAPTER_NOT_QUALIFIED"):
            qualification._match(contract, fn)


# -- the record itself -----------------------------------------------------------------------------

def test_pinned_record_binds_every_action_to_identity_implementation_and_shape():
    sha, record = qualification.load_record()
    assert sha == qualification.QUALIFICATION_SHA256
    by_action = {e["action_id"]: e for e in record["capabilities"]}
    for contract, fn in actions._unqualified_catalog():
        e = by_action[contract.action_id]
        assert e["adapter"] == f"uri_v1.execution.planning.actions:{fn.__name__}"
        assert e["contract_shape_sha256"] == qualification.contract_shape(contract)
        assert e["effect"] == contract.effect.value
        assert set(e["implementation"]) == set(actions.IMPLEMENTATION_MODULES)
    # actions.py is hashed by the record, so the record's own pin must not live there.
    assert qualification.QUALIFICATION_SHA256 not in (ROOT / "uri_v1/execution/planning/actions.py").read_text()
