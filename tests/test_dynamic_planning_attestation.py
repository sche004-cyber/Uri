"""Dynamic planning slice 1: adapter attestation (audit F2, Chetan 2026-09-29 13:49).

A trusted adapter used at run time must be the implementation that was qualified: same
module:qualname, same implementation SHA-256, same declared boundary, from a present and
well-formed pinned record. Anything else fails closed before the adapter is called.
"""
import copy
from dataclasses import replace
import hashlib
import importlib.util
import json
from pathlib import Path
import builtins
import sys
import types
import uuid

import pytest

import uri_v1.memory.recorder as memory_recorder
from uri_v1.execution import officefile
from uri_v1.planning import actions, attestation
from uri_v1.planning.compiler import compile_proposal
from uri_v1.planning.contracts import Effect
from uri_v1.planning.runner import PlanRunner

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
    assert attestation.attest(inspect_structure, contract(actions.INSPECT))[0] == "NOT_MODULE_FUNCTION"


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


# -- re-audit of 74474a2 (F2R-1 .. F2R-5): the auditor's probes P1-P4 as regressions ----------------------

def _rebuilt(fn, globals_):
    """A function object built from the genuine code object but with its own globals."""
    clone = types.FunctionType(fn.__code__, globals_, fn.__name__, fn.__defaults__, fn.__closure__)
    clone.__module__, clone.__qualname__ = fn.__module__, fn.__qualname__
    return clone


def test_genuine_code_with_private_builtins_is_refused_before_it_runs(runner_env, tmp_path):
    """F2R-1 / probe P1: the real write_report code with a private __builtins__ whose open() also writes outside."""
    outside, real_open = tmp_path / "p1_outside.txt", builtins.open
    def leaky_open(*args, **kwargs):
        real_open(outside, "w").write("x")
        return real_open(*args, **kwargs)
    private = dict(vars(actions)); private["__builtins__"] = {**vars(builtins), "open": leaky_open}
    clone = _rebuilt(actions.write_report, private)
    assert attestation.attest(clone, contract(actions.WRITE))[0] == "NOT_MODULE_FUNCTION"
    out, env = runner_env({**actions.adapters(), (actions.WRITE, "1"): clone})
    assert out.status == "NOT_ATTEMPTED" and out.reason == "ADAPTER_NOT_QUALIFIED" and "w" not in out.executed
    assert env.store.get(out.run_id)["aborted"]["detail"] == "NOT_MODULE_FUNCTION" and not outside.exists()


def test_genuine_code_with_a_private_module_reference_is_refused(runner_env, tmp_path):
    """F2R-1 / probe P2: the real code with private globals whose hashlib is a fake module."""
    outside = tmp_path / "p2_outside.txt"
    fake = types.ModuleType("hashlib")
    def sha256(data): outside.write_text("x"); return hashlib.sha256(data)
    fake.sha256 = sha256
    clone = _rebuilt(actions.write_report, {**vars(actions), "hashlib": fake})
    out, env = runner_env({**actions.adapters(), (actions.WRITE, "1"): clone})
    assert out.status == "NOT_ATTEMPTED" and env.store.get(out.run_id)["aborted"]["detail"] == "NOT_MODULE_FUNCTION"
    assert not outside.exists()


def test_replaced_module_reference_in_the_real_module_is_refused(monkeypatch):
    """F2R-2 / probe P3: actions.hashlib replaced by a fake module named hashlib."""
    monkeypatch.setattr(actions, "hashlib", types.ModuleType("hashlib"))
    assert attestation.attest(actions.write_report, contract(actions.WRITE))[0] == "FOREIGN_MODULE"


def _unfrozen(params):
    """A copy of a dataclass's params with frozen dropped. Copied rather than constructed, because the
    constructor's arguments differ between Python versions (3.11 takes 6, 3.12+ takes 10)."""
    params = copy.copy(params)
    params.frozen = False
    return params


def test_patched_methods_of_uri_classes_are_refused(monkeypatch):
    """F2R-3 / probe P4: methods of uri_v1 classes the implementation uses are attested too."""
    real_init = officefile.SheetStructure.__init__
    def init(self, *args, **kwargs): real_init(self, *args, **kwargs)
    init.__qualname__ = "SheetStructure.__init__"
    cases = [
        (officefile.SheetStructure, "__init__", init),                                   # generated method replaced
        (officefile.WorkbookStructure, "sheet", lambda self, name: None),                # source method replaced
        (officefile.WorkbookStructure, "extra", lambda self: None),                      # method added
        (officefile.SheetStructure, "__dataclass_params__", _unfrozen(officefile.SheetStructure.__dataclass_params__)),  # frozen dropped
        (actions.ActionError, "__init__", lambda self, *a: None),                        # exception class
    ]
    for cls, name, value in cases:
        with monkeypatch.context() as m:
            m.setattr(cls, name, value, raising=False)
            target = actions.select if cls is actions.ActionError else actions.inspect_structure
            key = actions.SELECT if cls is actions.ActionError else actions.INSPECT
            assert attestation.attest(target, contract(key))[0] in ("GENERATED_MISMATCH", "IMPLEMENTATION_CHANGED"), name
    assert attestation.attest(actions.inspect_structure, contract(actions.INSPECT))[0] is None


def test_classes_and_their_methods_are_part_of_the_digest():
    closure = attestation._closure(actions.inspect_structure)
    names = {f.__qualname__ for f in closure}
    assert {"SheetStructure", "WorkbookStructure", "WorkbookStructure.sheet", "WorkbookReadError"} <= names


def test_unknown_object_globals_are_refused_not_typed(monkeypatch):
    """F2R-5: a global that is not a module, class, builtin or plain value is refused (not fingerprinted by type)."""
    monkeypatch.setattr(actions, "REPORT_NAME", Path("plan_report.json"))
    assert attestation.attest(actions.write_report, contract(actions.WRITE))[0] == "FOREIGN_OBJECT"


class _Hook:
    """A data descriptor that runs code whenever the adapter reads the attribute (re-audit R3-1 / Q1)."""
    def __init__(self, name, outside): self.name, self.outside = name, outside
    def __get__(self, inst, owner):
        if inst is None: return self
        self.outside.write_text("hook")
        return inst.__dict__[self.name]
    def __set__(self, inst, value): inst.__dict__[self.name] = value


def test_hook_object_on_a_uri_class_is_refused(runner_env, tmp_path, monkeypatch):
    """R3-1 / Q1: a non-function descriptor on a class the adapter reads must not attest or reach VERIFIED."""
    outside = tmp_path / "q1_outside.txt"
    monkeypatch.setattr(officefile.WorkbookStructure, "sheets", _Hook("sheets", outside), raising=False)
    assert attestation.attest(actions.inspect_structure, contract(actions.INSPECT))[0] == "FOREIGN_MEMBER"
    out, env = runner_env()
    assert out.status == "NOT_ATTEMPTED" and env.store.get(out.run_id)["aborted"]["detail"] == "FOREIGN_MEMBER"
    assert not outside.exists()


def test_callable_object_replacing_a_method_is_refused(monkeypatch):
    """R3-1 / Q2: a non-function object in place of a generated method is refused by rule, not by accident."""
    class Callable:
        def __get__(self, inst, owner): return lambda *a, **k: None
    monkeypatch.setattr(officefile.SheetStructure, "__init__", Callable())
    assert attestation.attest(actions.inspect_structure, contract(actions.INSPECT))[0] == "FOREIGN_MEMBER"


def test_injected_default_arguments_change_the_digest(monkeypatch):
    """R3-2 / Q5: default argument values are part of the implementation."""
    monkeypatch.setattr(actions.write_report, "__defaults__", (None,))
    assert attestation.attest(actions.write_report, contract(actions.WRITE))[0] == "IMPLEMENTATION_CHANGED"


def test_uri_module_as_a_global_is_refused(monkeypatch):
    """R3-3: uri_v1 code reached through a module global would not be hashed, so such a global is refused."""
    monkeypatch.setattr(actions, "hashlib", officefile)
    assert attestation.attest(actions.write_report, contract(actions.WRITE))[0] == "FOREIGN_MODULE"
