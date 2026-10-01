"""Adapter attestation: the callable that runs is the implementation that was qualified (audit F2).

The pinned qualification record (`actions.QUALIFICATION_PATH`, digest `actions.QUALIFICATION_SHA256`)
names, for each qualified capability, its adapter by `module` and `qualname`, the SHA-256 of its
implementation, and its declared boundary (mechanism, effect, verifier coverage, workspace writes).

Before every node the runner calls `attest(adapter, contract)`. It returns `(None, digest)` when:

1. the record is present, matches its pinned digest and parses as the current schema;
2. one QUALIFIED entry names this callable's `module:qualname`;
3. the implementation digest recomputed now equals the entry's `implementation_sha256`;
4. every function in that implementation is running the code compiled from its source on disk
   (so a `__code__` swap, a patched helper or a function defined elsewhere is refused);
5. the entry's boundary equals the contract's mechanism, effect and verifier coverage.

Anything else returns `(refusal_code, None)` and the node does not run (fail closed). Matching is by
implementation, not by action name, so a renamed action over the same handler still attests.

Implementation digest: SHA-256 of the canonical JSON list of `[module, qualname, source, globals]`
for the adapter and every function it reaches through global names that resolve to Python
functions in `uri_v1.*` modules, sorted, with sources LF-normalized. `globals` fingerprints every
other global name the function uses: a module by name, a class by its defining module and qualname
(it must still be that module's attribute), a builtin by name, and a plain value (number, string,
container, compiled pattern) by its repr. A global that resolves to a Python function outside
`uri_v1.*` (for example a helper or a shadowed builtin replaced at run time) is refused. The code of
standard-library modules and builtins is not hashed (see the implementation report's limitations).
A uri_v1 module used as a global is refused (FOREIGN_MODULE), so uri_v1 code is reached only by
direct import and is always in the closure. Default argument values join the function's part when
present. Classes: every member of a uri_v1 class must be a function (attested as above), class or
dataclass machinery of the expected type, or a plain value; anything else is refused (FOREIGN_MEMBER).
Any other in-process modification of URI's already-running code or state is outside attestation.
"""
from __future__ import annotations

import ast
import builtins
import dataclasses
import hashlib
import inspect
import json
import linecache
import re
import sys
import textwrap
import types

from . import actions
from .contracts import REPORT_NAME, canonical

_OWN_PREFIX = "uri_v1."
_MAX_FUNCTIONS = 128


class AttestationError(ValueError):
    pass


def _source(fn) -> str:
    try: linecache.checkcache(fn.__code__.co_filename if isinstance(fn, types.FunctionType) else inspect.getsourcefile(fn))
    except TypeError: raise AttestationError("SOURCE_UNAVAILABLE")
    try:
        return inspect.getsource(fn).replace("\r\n", "\n")
    except (OSError, TypeError) as exc:
        raise AttestationError("SOURCE_UNAVAILABLE") from exc


def _names(code) -> set:
    names = set(code.co_names)
    for const in code.co_consts:
        if isinstance(const, types.CodeType): names |= _names(const)
    return names


_VALUES = (int, float, str, bytes, bool, type(None), tuple, frozenset, list, dict, re.Pattern)
_DATACLASS_DEFAULTS = {"init": True, "repr": True, "eq": True, "order": False, "unsafe_hash": False, "frozen": False}


def _own(ref) -> bool:
    return isinstance(ref, types.FunctionType) and (ref.__module__ or "").startswith(_OWN_PREFIX)


def _own_class(ref) -> bool:
    return isinstance(ref, type) and (ref.__module__ or "").startswith(_OWN_PREFIX)


def _lookup(owner, qualname):
    """Resolve a module-level qualname through class dictionaries (not attribute lookup)."""
    obj = owner
    for part in qualname.split("."):
        obj = vars(obj).get(part) if isinstance(obj, type) else getattr(obj, part, None)
        if obj is None: return None
    return obj


def _check_home(f) -> None:
    """A function must be its own module's function, with that module's globals and the real builtins
    (audit F2R-1): a function object rebuilt from genuine code with private globals is refused."""
    owner = sys.modules.get(f.__module__ or "")
    found = _lookup(owner, f.__qualname__) if owner is not None else None
    held = (found, getattr(found, "__func__", None), getattr(found, "fget", None), getattr(found, "fset", None),
            getattr(found, "fdel", None))
    if (owner is None or f.__globals__ is not vars(owner) or f.__builtins__ is not vars(builtins)
            or not any(h is f for h in held)):
        raise AttestationError("NOT_MODULE_FUNCTION")


def _fingerprint(ref):
    """How a global that is neither a uri_v1 function nor a uri_v1 class enters the digest; raises for
    anything that must not run."""
    if isinstance(ref, types.FunctionType): raise AttestationError("FOREIGN_FUNCTION")
    if isinstance(ref, types.ModuleType):
        # a uri_v1 module global would reach uri_v1 code the closure does not hash (re-audit R3-3)
        if sys.modules.get(ref.__name__) is not ref or (ref.__name__ + ".").startswith(_OWN_PREFIX):
            raise AttestationError("FOREIGN_MODULE")
        return ["module", ref.__name__]
    if isinstance(ref, type):
        owner = sys.modules.get(ref.__module__)
        if _lookup(owner, ref.__qualname__) is not ref if owner is not None else True: raise AttestationError("FOREIGN_CLASS")
        return ["class", ref.__module__, ref.__qualname__]
    if isinstance(ref, types.BuiltinFunctionType):
        owner = sys.modules.get(getattr(ref, "__module__", None) or "builtins")
        if owner is None or getattr(owner, ref.__name__, None) is not ref: raise AttestationError("FOREIGN_BUILTIN")
        return ["builtin", owner.__name__, ref.__qualname__]
    if isinstance(ref, _VALUES): return ["value", repr(ref)]
    raise AttestationError("FOREIGN_OBJECT")          # audit F2R-5: never fingerprint by type alone


def _globals(fn) -> list:
    out = []
    for name in sorted(_names(fn.__code__)):
        if name not in fn.__globals__: continue          # an attribute name, or a real builtin
        ref = fn.__globals__[name]
        if not _own(ref) and not _own_class(ref): out.append([name] + _fingerprint(ref))
    return out


def _functions_of(value):
    if isinstance(value, (staticmethod, classmethod)): value = value.__func__
    if isinstance(value, property): return [f for f in (value.fget, value.fset, value.fdel) if f is not None]
    return [value] if isinstance(value, types.FunctionType) else []


def _dataclass_spec(cls, source: str):
    """Field names, literal defaults and decorator arguments, read from the class source (no execution)."""
    try: node = ast.parse(textwrap.dedent(source)).body[0]
    except (SyntaxError, IndexError): raise AttestationError("GENERATED_MISMATCH")
    if not isinstance(node, ast.ClassDef) or node.name != cls.__name__: raise AttestationError("GENERATED_MISMATCH")
    if len(node.decorator_list) != 1: raise AttestationError("GENERATED_MISMATCH")
    deco = node.decorator_list[0]
    target = deco.func if isinstance(deco, ast.Call) else deco
    name = target.id if isinstance(target, ast.Name) else target.attr if isinstance(target, ast.Attribute) else None
    if name != "dataclass" or (isinstance(deco, ast.Call) and deco.args): raise AttestationError("GENERATED_MISMATCH")
    kwargs = {}
    if isinstance(deco, ast.Call):
        try: kwargs = {k.arg: ast.literal_eval(k.value) for k in deco.keywords}
        except ValueError: raise AttestationError("GENERATED_MISMATCH")
        if not set(kwargs) <= set(_DATACLASS_DEFAULTS): raise AttestationError("GENERATED_MISMATCH")
    names, defaults = [], {}
    for stmt in node.body:
        if isinstance(stmt, ast.AnnAssign) and isinstance(stmt.target, ast.Name):
            names.append(stmt.target.id)
            if stmt.value is not None:
                try: defaults[stmt.target.id] = ast.literal_eval(stmt.value)
                except ValueError: raise AttestationError("GENERATED_MISMATCH")
    return names, defaults, kwargs


def _same_generated(live, fresh, cls, fresh_cls, depth=0) -> bool:
    if depth > 4 or not isinstance(live, types.FunctionType) or not isinstance(fresh, types.FunctionType): return False
    if (live.__code__ != fresh.__code__ or live.__globals__ is not fresh.__globals__ or live.__builtins__ is not vars(builtins)
            or repr(live.__defaults__) != repr(fresh.__defaults__) or live.__kwdefaults__ != fresh.__kwdefaults__):
        return False
    a, b = live.__closure__ or (), fresh.__closure__ or ()
    if len(a) != len(b): return False
    for ca, cb in zip(a, b):
        x, y = ca.cell_contents, cb.cell_contents
        if isinstance(x, types.FunctionType) or isinstance(y, types.FunctionType):
            if not _same_generated(x, y, cls, fresh_cls, depth + 1): return False
        elif not (x is y or (x is cls and y is fresh_cls) or (type(x) is type(y) and repr(x) == repr(y))):
            return False
    return True


def _check_generated(cls, generated: dict, source: str) -> None:
    """Methods a dataclass generated at import (no source file) must equal the ones dataclasses generates
    now from the fields and arguments written in the class source (audit F2R-3)."""
    if not dataclasses.is_dataclass(cls): raise AttestationError("GENERATED_MISMATCH")
    names, defaults, kwargs = _dataclass_spec(cls, source)
    fields = dataclasses.fields(cls)
    params = {k: getattr(cls.__dataclass_params__, k) for k in _DATACLASS_DEFAULTS}
    if ([f.name for f in fields] != names or params != {**_DATACLASS_DEFAULTS, **kwargs}
            or any(f.default_factory is not dataclasses.MISSING for f in fields)
            or any(f.default != defaults.get(f.name, dataclasses.MISSING) for f in fields)):
        raise AttestationError("GENERATED_MISMATCH")
    namespace = {"__annotations__": {n: cls.__annotations__.get(n) for n in names}, "__module__": cls.__module__,
                 "__qualname__": cls.__qualname__, **defaults}
    fresh = dataclasses.dataclass(**kwargs)(type(cls.__name__, cls.__bases__, namespace))
    expected = {n for n, v in vars(fresh).items() if _functions_of(v)}
    if set(generated) != expected or not all(_same_generated(fn, vars(fresh)[n], cls, fresh) for n, fn in generated.items()):
        raise AttestationError("GENERATED_MISMATCH")


_MACHINERY = {"__module__": str, "__doc__": (str, type(None)), "__annotations__": dict, "__match_args__": tuple,
              "__dataclass_params__": object, "__dataclass_fields__": dict, "__hash__": type(None),
              "__dict__": types.GetSetDescriptorType, "__weakref__": types.GetSetDescriptorType}


def _plain_member(name, value) -> bool:
    """A non-function class member is allowed only as class or dataclass machinery of the expected type,
    or as a plain value (re-audit R3-1: a descriptor or hook object must not escape attestation)."""
    if name in _MACHINERY:
        return isinstance(value, _MACHINERY[name]) and (name != "__dataclass_params__" or type(value).__module__ == "dataclasses")
    return isinstance(value, _VALUES)


def _class_members(cls) -> list:
    """Source-defined methods of a uri_v1 class (attested like functions); generated ones are checked here."""
    owner = sys.modules.get(cls.__module__)
    if owner is None or _lookup(owner, cls.__qualname__) is not cls or type(cls) is not type:
        raise AttestationError("FOREIGN_CLASS")
    for base in cls.__bases__:
        if not _own_class(base) and base.__module__ != "builtins": raise AttestationError("FOREIGN_CLASS")
    source, own_file = _source(cls), getattr(owner, "__file__", None)
    methods, generated = [], {}
    for name, value in vars(cls).items():
        if not _functions_of(value) and not _plain_member(name, value): raise AttestationError("FOREIGN_MEMBER")
        for fn in _functions_of(value):
            if fn.__code__.co_filename == own_file and fn.__module__ == cls.__module__: methods.append(fn)
            else: generated[name] = fn
    if generated: _check_generated(cls, generated, source)
    return methods


def _closure(fn) -> list:
    """The adapter and every uri_v1 function or class it reaches by global name, in a stable order."""
    seen, stack = {}, [fn]
    while stack:
        f = stack.pop()
        is_class = _own_class(f)
        if not is_class and not isinstance(f, types.FunctionType): raise AttestationError("NOT_A_FUNCTION")
        key = ("class" if is_class else "function", f.__module__ or "", f.__qualname__)
        if key in seen:
            if seen[key] is not f: raise AttestationError("AMBIGUOUS_FUNCTION")
            continue
        seen[key] = f
        if len(seen) > _MAX_FUNCTIONS: raise AttestationError("IMPLEMENTATION_TOO_LARGE")
        if is_class:
            stack.extend(_class_members(f))
            stack.extend(b for b in f.__bases__ if _own_class(b))
            continue
        _check_home(f)
        for name in _names(f.__code__):
            ref = f.__globals__.get(name)
            if _own(ref) or _own_class(ref): stack.append(ref)
    return [seen[k] for k in sorted(seen)]


_COMPILED: dict = {}


def _walk(code):
    yield code
    for const in code.co_consts:
        if isinstance(const, types.CodeType): yield from _walk(const)


def _runs_its_source(fn) -> bool:
    """True when the live code object equals the code compiled from its module file on disk.

    The whole file is compiled (not the function alone), because CPython compiles a function
    differently out of its module context. Compiled modules are cached by file digest."""
    code = fn.__code__
    try:
        with open(code.co_filename, "rb") as handle: data = handle.read()
    except OSError:
        return False
    key = (code.co_filename, hashlib.sha256(data).hexdigest())
    if key not in _COMPILED:
        try: _COMPILED[key] = compile(data, code.co_filename, "exec", dont_inherit=True)
        except (SyntaxError, ValueError): return False
    return any(c.co_qualname == code.co_qualname and c.co_firstlineno == code.co_firstlineno and c == code
               for c in _walk(_COMPILED[key]))


def implementation_sha256(fn) -> str:
    """Digest of the adapter's implementation. Raises AttestationError if it cannot be established."""
    parts = []
    for f in _closure(fn):
        source = _source(f)
        if isinstance(f, type):
            parts.append([f.__module__, f.__qualname__, "class", source, [f"{b.__module__}.{b.__qualname__}" for b in f.__bases__]])
            continue
        if not _runs_its_source(f): raise AttestationError("CODE_MISMATCH")
        part = [f.__module__, f.__qualname__, source, _globals(f)]
        if f.__defaults__ is not None or f.__kwdefaults__ is not None:      # re-audit R3-2; absent keeps old digests
            part.append([[_fingerprint(d) for d in f.__defaults__ or ()],
                         sorted([k] + _fingerprint(v) for k, v in (f.__kwdefaults__ or {}).items())])
        parts.append(part)
    return hashlib.sha256(canonical(parts)).hexdigest()


def _record():
    try:
        data = actions.QUALIFICATION_PATH.read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        raise AttestationError("RECORD_MISSING")
    if hashlib.sha256(data).hexdigest() != actions.QUALIFICATION_SHA256: raise AttestationError("RECORD_DIGEST")
    try:
        raw = json.loads(data)
    except ValueError:
        raise AttestationError("RECORD_MALFORMED")
    if not isinstance(raw, dict) or raw.get("schema_version") != actions.QUALIFICATION_SCHEMA_VERSION or not isinstance(raw.get("capabilities"), list):
        raise AttestationError("RECORD_MALFORMED")
    return raw["capabilities"]


def _entry_ok(e) -> bool:
    adapter, boundary = e.get("adapter"), e.get("boundary")
    return (isinstance(adapter, dict) and set(adapter) == {"module", "qualname", "implementation_sha256"}
            and all(isinstance(v, str) and v for v in adapter.values()) and len(adapter["implementation_sha256"]) == 64
            and isinstance(boundary, dict) and set(boundary) == {"effect", "verifier_coverage", "workspace_writes"}
            and isinstance(boundary["workspace_writes"], list))


def attest(adapter, contract) -> tuple:
    """(None, implementation_sha256) when `adapter` is the qualified implementation for `contract`,
    else (refusal_code, None)."""
    refusal = _refusal(adapter, contract)
    return (None, refusal[1]) if refusal[0] is None else (refusal[0], None)


def _refusal(adapter, contract) -> tuple:
    try:
        entries = _record()
        if not all(isinstance(e, dict) and _entry_ok(e) for e in entries): return "RECORD_MALFORMED", None
        if not isinstance(adapter, types.FunctionType): return "NOT_A_FUNCTION", None
        named = [e for e in entries
                 if (e["adapter"]["module"], e["adapter"]["qualname"]) == (adapter.__module__, adapter.__qualname__)]
        if len(named) != 1: return "NOT_IN_RECORD", None
        entry = named[0]
        if entry.get("status") != "QUALIFIED" or entry.get("passed") is not True: return "NOT_QUALIFIED", None
        digest = implementation_sha256(adapter)
        if digest != entry["adapter"]["implementation_sha256"]: return "IMPLEMENTATION_CHANGED", None
        boundary = entry["boundary"]
        writes = boundary["workspace_writes"]
        if (entry.get("mechanism") != contract.mechanism.value or boundary["effect"] != contract.effect.value
                or boundary["verifier_coverage"] != contract.verifier_coverage
                or (boundary["effect"] == "READ_ONLY") != (writes == []) or any(w != REPORT_NAME for w in writes)):
            return "BOUNDARY_MISMATCH", None
        return None, digest
    except AttestationError as exc:
        return str(exc), None
    except (RecursionError, AttributeError, TypeError, KeyError, ValueError):
        return "ATTESTATION_ERROR", None
