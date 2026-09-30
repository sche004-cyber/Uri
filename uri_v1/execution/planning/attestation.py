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
"""
from __future__ import annotations

import hashlib
import inspect
import json
import linecache
import re
import sys
import types

from . import actions
from .contracts import REPORT_NAME, canonical

_OWN_PREFIX = "uri_v1."
_MAX_FUNCTIONS = 128


class AttestationError(ValueError):
    pass


def _source(fn) -> str:
    linecache.checkcache(fn.__code__.co_filename)
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


def _own(ref) -> bool:
    return isinstance(ref, types.FunctionType) and (ref.__module__ or "").startswith(_OWN_PREFIX)


def _fingerprint(ref):
    """How a non-uri_v1-function global enters the digest; raises for anything that must not run."""
    if isinstance(ref, types.FunctionType): raise AttestationError("FOREIGN_FUNCTION")
    if isinstance(ref, types.ModuleType): return ["module", ref.__name__]
    if isinstance(ref, type):
        owner = sys.modules.get(ref.__module__)
        if getattr(owner, ref.__qualname__, None) is not ref: raise AttestationError("FOREIGN_CLASS")
        return ["class", ref.__module__, ref.__qualname__]
    if isinstance(ref, types.BuiltinFunctionType): return ["builtin", getattr(ref, "__module__", None), ref.__qualname__]
    if isinstance(ref, _VALUES): return ["value", repr(ref)]
    return ["object", type(ref).__module__, type(ref).__qualname__]


def _globals(fn) -> list:
    out = []
    for name in sorted(_names(fn.__code__)):
        if name not in fn.__globals__: continue          # an attribute name, or a real builtin
        ref = fn.__globals__[name]
        if not _own(ref): out.append([name] + _fingerprint(ref))
    return out


def _closure(fn) -> list:
    """The adapter and every uri_v1 function it reaches by global name, in a stable order."""
    seen, stack = {}, [fn]
    while stack:
        f = stack.pop()
        if not isinstance(f, types.FunctionType): raise AttestationError("NOT_A_FUNCTION")
        key = (f.__module__ or "", f.__qualname__)
        if key in seen:
            if seen[key] is not f: raise AttestationError("AMBIGUOUS_FUNCTION")
            continue
        seen[key] = f
        if len(seen) > _MAX_FUNCTIONS: raise AttestationError("IMPLEMENTATION_TOO_LARGE")
        for name in _names(f.__code__):
            ref = f.__globals__.get(name)
            if _own(ref): stack.append(ref)
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
        if not _runs_its_source(f): raise AttestationError("CODE_MISMATCH")
        parts.append([f.__module__, f.__qualname__, source, _globals(f)])
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
