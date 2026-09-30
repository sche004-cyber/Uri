"""Dynamic planning slice 1: adapter attestation (audit F2, Chetan 2026-09-29 13:49).

A trusted adapter used at run time must be the implementation that was qualified: same
module:qualname, same implementation SHA-256, same declared boundary, from a present and
well-formed pinned record. Anything else fails closed before the adapter is called.
"""
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import uuid

import pytest

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution import officefile
from uri_v1.execution.planning import actions, attestation
from uri_v1.execution.planning.compiler import compile_proposal
from uri_v1.execution.planning.contracts import Effect
from uri_v1.execution.planning.runner import PlanRunner

ROOT = Path(__file__).resolve().parents[1]
CATALOG = {c.action_id: (c, fn) for c, fn in actions.default_catalog()}


def contract(action_id):
    return CATALOG[action_id][0]


def qual():
    name = "dynamic_planning_qualification"
    if name not in sys.modules:
        spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / f"{name}.py")
        module = importlib.util.module_from_spec(spec); sys.modules[name] = module; spec.loader.exec_module(module)
    return sys.modules[name]


@pytest.fixture
def record(tmp_path, monkeypatch):
    """Install a record (bytes or dict) as the pinned qualification record, digest pinned to match."""
    def install(content, *, pin=True):
        data = content if isinstance(content, bytes) else (json.dumps(content, indent=2, sort_keys=True) + "\n").encode()
        path = tmp_path / f"record_{uuid.uuid4().hex}.json"
        path.write_bytes(data)
        monkeypatch.setattr(actions, "QUALIFICATION_PATH", path)
        if pin: monkeypatch.setattr(actions, "QUALIFICATION_SHA256", hashlib.sha256(data).hexdigest())
        return path
    return install


def real_record() -> dict:
    return json.loads(actions.QUALIFICATION_PATH.read_bytes())


@pytest.fixture
def runner_env(tmp_path, monkeypatch):
    q = qual()
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    q.bootstrap(tmp_path / "runs")
    cases, _ = q.load_battery()
    c01 = next(c for c in cases if c["id"] == "C01")

    def make(adapters=None, between=None):
        env = q.CaseEnv(tmp_path / uuid.uuid4().hex, tmp_path / "runs")
        snap = actions.snapshot()
        runner = PlanRunner(user_id=env.user, scratch_root=env.scratch, run_store=env.store, recorder=env.recorder,
                            ledger=env.ledger, sources=env.sources, snapshot_provider=lambda: snap,
                            adapters=adapters or actions.adapters())
        plan = compile_proposal(q.substitute(c01["proposal"], env.ids), snap, env.candidates)
        if between: between()
        out = runner.run(plan, task_id=env.task_id, trace_id=uuid.uuid4().hex, session_id="s", candidates=env.candidates,
                         snapshot=snap)
        return out, env
    return make


# -- valid unchanged adapter -----------------------------------------------------------------------------

def test_valid_unchanged_adapters_attest_and_verify(runner_env):
    for action_id, (c, fn) in CATALOG.items():
        refusal, digest = attestation.attest(fn, c)
        entry = next(e for e in real_record()["capabilities"] if e["action_id"] == action_id)
        assert refusal is None and digest == entry["adapter"]["implementation_sha256"], action_id
    out, env = runner_env()
    assert out.status == "VERIFIED"
    claim = env.store.get(out.run_id)["result"]["executor_claim"]
    assert set(claim["adapters"]) == set(out.executed) and all(len(d) == 64 for d in claim["adapters"].values())


def test_implementation_digest_is_stable():
    fn = actions.inspect_structure
    assert attestation.implementation_sha256(fn) == attestation.implementation_sha256(fn)


# -- same adapter id, different code ----------------------------------------------------------------------

def test_swapped_adapter_under_the_same_id_is_refused_before_it_runs(runner_env, tmp_path):
    """The audited F2 path: same (action_id, version), different callable that writes outside."""
    outside = tmp_path / "outside_written_by_adapter.txt"
    def evil(ctx, inputs, literals):
        outside.write_text("x")
        return actions.inspect_structure(ctx, inputs, literals)
    out, env = runner_env({**actions.adapters(), (actions.INSPECT, "1"): evil})
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ADAPTER_NOT_QUALIFIED" and out.executed == ()
    assert env.store.get(out.run_id)["aborted"]["detail"] == "NOT_IN_RECORD"
    assert not outside.exists()


def test_adapter_spoofing_the_qualified_name_is_refused():
    def inspect_structure(ctx, inputs, literals):
        return {"structure": {"source_id": "x", "sheets": []}}
    inspect_structure.__module__ = actions.__name__
    inspect_structure.__qualname__ = "inspect_structure"
    assert attestation.attest(inspect_structure, contract(actions.INSPECT))[0] == "IMPLEMENTATION_CHANGED"


def test_code_swap_on_the_real_function_is_refused(monkeypatch):
    fn = actions.inspect_structure
    source = "\n" * (fn.__code__.co_firstlineno - 1) + "def inspect_structure(ctx, inputs, literals):\n    return {}\n"
    namespace = {}
    exec(compile(source, fn.__code__.co_filename, "exec"), namespace)
    monkeypatch.setattr(fn, "__code__", namespace["inspect_structure"].__code__)
    assert attestation.attest(fn, contract(actions.INSPECT))[0] == "CODE_MISMATCH"


def test_patched_helper_or_constant_or_shadowed_builtin_is_refused(monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(actions, "_named", lambda header: list(header))
        assert attestation.attest(actions.compare, contract(actions.COMPARE))[0] == "FOREIGN_FUNCTION"
    with monkeypatch.context() as m:
        m.setattr(officefile, "MAX_HEADER_CELLS", 10 ** 9)
        assert attestation.attest(actions.inspect_structure, contract(actions.INSPECT))[0] == "IMPLEMENTATION_CHANGED"
    with monkeypatch.context() as m:
        m.setattr(actions, "open", lambda *a, **k: None, raising=False)
        assert attestation.attest(actions.write_report, contract(actions.WRITE))[0] == "FOREIGN_FUNCTION"
    with monkeypatch.context() as m:
        m.setattr(actions, "ActionError", type("ActionError", (ValueError,), {}))
        assert attestation.attest(actions.select, contract(actions.SELECT))[0] == "FOREIGN_CLASS"
    assert attestation.attest(actions.compare, contract(actions.COMPARE))[0] is None


def test_a_non_function_adapter_is_refused():
    class Callable:
        def __call__(self, ctx, inputs, literals): return {}
    assert attestation.attest(Callable(), contract(actions.INSPECT))[0] == "NOT_A_FUNCTION"


# -- changed hash ---------------------------------------------------------------------------------------

def test_record_hash_that_does_not_match_the_implementation_is_refused(record):
    raw = real_record()
    raw["capabilities"][0]["adapter"]["implementation_sha256"] = "0" * 64
    record(raw)
    c, fn = CATALOG[raw["capabilities"][0]["action_id"]]
    assert attestation.attest(fn, c)[0] == "IMPLEMENTATION_CHANGED"


def test_record_edited_without_repinning_its_digest_is_refused(record):
    raw = real_record()
    raw["capabilities"][0]["evidence"] += " (edited)"
    record(raw, pin=False)
    assert attestation.attest(actions.inspect_structure, contract(actions.INSPECT))[0] == "RECORD_DIGEST"


# -- missing qualification record ------------------------------------------------------------------------

def test_missing_record_fails_closed(monkeypatch, tmp_path, runner_env):
    absent = tmp_path / "absent.json"
    # Record removed after the plan was compiled: every node is refused at run time.
    out, env = runner_env(between=lambda: monkeypatch.setattr(actions, "QUALIFICATION_PATH", absent))
    assert attestation.attest(actions.inspect_structure, contract(actions.INSPECT))[0] == "RECORD_MISSING"
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ADAPTER_NOT_QUALIFIED" and out.executed == ()
    assert env.store.get(out.run_id)["aborted"]["detail"] == "RECORD_MISSING"
    # Record missing before compiling: the contracts are UNQUALIFIED and the compiler refuses the plan.
    snap = actions.snapshot()
    assert {c.qualification for c in snap.contracts} == {"UNQUALIFIED"}


def test_missing_entry_for_the_adapter_fails_closed(record):
    raw = real_record()
    raw["capabilities"] = [e for e in raw["capabilities"] if e["action_id"] != actions.SELECT]
    record(raw)
    assert attestation.attest(actions.select, contract(actions.SELECT))[0] == "NOT_IN_RECORD"


# -- malformed qualification record ----------------------------------------------------------------------

def _mutated(fn):
    raw = real_record(); fn(raw); return raw


@pytest.mark.parametrize("content,code", [
    (b"{not json", "RECORD_MALFORMED"),
    (b"[]", "RECORD_MALFORMED"),
    (_mutated(lambda r: r.update(schema_version="uri.plan.qualification.v1")), "RECORD_MALFORMED"),
    (_mutated(lambda r: r.update(capabilities={"a": 1})), "RECORD_MALFORMED"),
    (_mutated(lambda r: r["capabilities"][0].pop("adapter")), "RECORD_MALFORMED"),
    (_mutated(lambda r: r["capabilities"][0]["adapter"].update(implementation_sha256="short")), "RECORD_MALFORMED"),
    (_mutated(lambda r: r["capabilities"][0]["boundary"].pop("workspace_writes")), "RECORD_MALFORMED"),
    (_mutated(lambda r: r["capabilities"].append(r["capabilities"][0])), "NOT_IN_RECORD"),
    (_mutated(lambda r: r["capabilities"][0].update(status="REVOKED")), "NOT_QUALIFIED"),
])
def test_malformed_record_fails_closed(record, content, code):
    record(content)
    first = json.loads(actions.QUALIFICATION_PATH.read_bytes())["capabilities"][0]["action_id"] if code in (
        "NOT_IN_RECORD", "NOT_QUALIFIED") else actions.INSPECT
    c, fn = CATALOG[first]
    assert attestation.attest(fn, c)[0] == code


# -- declared boundary ----------------------------------------------------------------------------------

def test_boundary_in_the_record_is_bound_to_the_contract(record):
    assert attestation.attest(actions.select, replace(contract(actions.SELECT), effect=Effect.SCRATCH_WRITE))[0] == "BOUNDARY_MISMATCH"
    assert attestation.attest(actions.select, replace(contract(actions.SELECT), verifier_coverage="oracle.compare.v1"))[0] == "BOUNDARY_MISMATCH"
    raw = real_record()
    entry = next(e for e in raw["capabilities"] if e["action_id"] == actions.SELECT)
    entry["boundary"]["workspace_writes"] = ["plan_report.json"]
    record(raw)
    assert attestation.attest(actions.select, contract(actions.SELECT))[0] == "BOUNDARY_MISMATCH"
    entry["boundary"]["workspace_writes"] = []
    writer = next(e for e in raw["capabilities"] if e["action_id"] == actions.WRITE)
    writer["boundary"]["workspace_writes"] = ["../outside.json"]
    record(raw)
    assert attestation.attest(actions.write_report, contract(actions.WRITE))[0] == "BOUNDARY_MISMATCH"
