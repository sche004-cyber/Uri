"""Binds each qualified action adapter to its implementation (closes audit finding F2).

The pinned capability record (`fixtures/dynamic_planning/capability_qualification.json`, SHA-256
pinned here) names, per qualified capability:

- `adapter`: the adapter's stable identity, `<module>:<qualname>`;
- `implementation`: the LF-normalized SHA-256 of the adapter's module and of every module it
  relies on (for the slice-1 actions: `actions`, `contracts`, `officefile`);
- `contract_shape_sha256`: the digest of the capability contract it was qualified under, minus
  its display name and the qualification field. The shape carries the version, mechanism, ports,
  literals, verifier coverage and the declared effect (READ_ONLY or SCRATCH_WRITE), so the
  qualified workspace boundary is bound in the same record.

`check_adapter` runs before every node. It fails closed with a typed code unless the adapter is
a plain function, its identity is in the record under the same contract shape, the name resolves
to this exact object, its code comes from that module's file, and every bound module still hashes
to the recorded value. A missing, altered or malformed record fails the same way.

Scope: this proves which code is about to run. It does not contain what that code does. An
adapter's effects outside the run workspace need OS-level containment (retained limitation).
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import sys
import types

from .contracts import UNQUALIFIED, canonical

QUALIFICATION_SCHEMA_VERSION = "uri.plan.qualification.v2"
QUALIFICATION_PATH = Path(__file__).resolve().parents[3] / "fixtures" / "dynamic_planning" / "capability_qualification.json"
QUALIFICATION_SHA256 = "b0dcf1ec54d7eb256038dd53d4efdaac874cdbc4622fb8167f8e504a4e190a7a"

_SHA = re.compile(r"^[0-9a-f]{64}$")
_IDENTITY = re.compile(r"^[A-Za-z_][A-Za-z0-9_.]*:[A-Za-z_][A-Za-z0-9_.]*$")
_ENTRY_KEYS = {"action_id", "version", "mechanism", "effect", "adapter", "contract_shape_sha256", "implementation",
               "status", "passed", "evidence"}


class QualificationError(ValueError):
    """Typed failure; the reason code is the message."""


def file_sha256(path) -> str:
    """LF-normalized, so a Windows autocrlf checkout pins the same value."""
    return hashlib.sha256(Path(path).read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def contract_shape(contract) -> str:
    """Digest of what a contract lets a node do. The display name and the qualification are not part of it."""
    shape = contract.to_dict()
    shape.pop("action_id"); shape.pop("qualification")
    return hashlib.sha256(canonical(shape)).hexdigest()


def adapter_identity(adapter) -> str:
    if type(adapter) is not types.FunctionType: raise QualificationError("ADAPTER_NOT_A_FUNCTION")
    identity = f"{adapter.__module__}:{adapter.__qualname__}"
    if not _IDENTITY.fullmatch(identity): raise QualificationError("ADAPTER_IDENTITY_UNSTABLE")   # lambdas, closures
    return identity


def _module_file(name):
    module = sys.modules.get(name)
    path = getattr(module, "__file__", None)
    if not path or not str(path).endswith(".py"): raise QualificationError("IMPLEMENTATION_UNAVAILABLE")
    return Path(path).resolve()


def implementation_digests(module_names) -> dict:
    try:
        return {name: file_sha256(_module_file(name)) for name in module_names}
    except OSError:
        raise QualificationError("IMPLEMENTATION_UNAVAILABLE")


def _valid_entry(e) -> bool:
    return (isinstance(e, dict) and set(e) == _ENTRY_KEYS and all(isinstance(e[k], str) for k in _ENTRY_KEYS - {"implementation", "passed"})
            and _IDENTITY.fullmatch(e["adapter"]) is not None and _SHA.fullmatch(e["contract_shape_sha256"]) is not None
            and isinstance(e["implementation"], dict) and bool(e["implementation"])
            and all(isinstance(k, str) and isinstance(v, str) and _SHA.fullmatch(v) for k, v in e["implementation"].items())
            and e["adapter"].split(":")[0] in e["implementation"] and type(e["passed"]) is bool)


def load_record(path=None, pinned=None):
    """(sha256, record) of the pinned record, or QualificationError. Defaults are read at call time."""
    path = QUALIFICATION_PATH if path is None else path
    pinned = QUALIFICATION_SHA256 if pinned is None else pinned
    try:
        data = Path(path).read_bytes().replace(b"\r\n", b"\n")
    except OSError:
        raise QualificationError("RECORD_MISSING")
    sha = hashlib.sha256(data).hexdigest()
    if sha != pinned: raise QualificationError("RECORD_DIGEST_MISMATCH")
    try:
        raw = json.loads(data)
    except ValueError:
        raise QualificationError("RECORD_MALFORMED")
    if (not isinstance(raw, dict) or raw.get("schema_version") != QUALIFICATION_SCHEMA_VERSION
            or not isinstance(raw.get("capabilities"), list) or not all(_valid_entry(e) for e in raw["capabilities"])):
        raise QualificationError("RECORD_MALFORMED")
    return sha, raw


def _resolve(identity):
    module_name, qualname = identity.split(":")
    obj = sys.modules.get(module_name)
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
    return obj


def _match(contract, adapter):
    """(record sha, entry) for this exact adapter under this exact contract shape, or QualificationError."""
    sha, record = load_record()
    identity = adapter_identity(adapter)
    entries = [e for e in record["capabilities"] if e["adapter"] == identity]
    if not entries: raise QualificationError("ADAPTER_NOT_IN_RECORD")
    shape = contract_shape(contract)
    entry = next((e for e in entries if e["contract_shape_sha256"] == shape), None)
    if entry is None: raise QualificationError("CONTRACT_SHAPE_MISMATCH")
    if entry["status"] != "QUALIFIED" or entry["passed"] is not True: raise QualificationError("ADAPTER_NOT_QUALIFIED")
    # The name must resolve to this very object, and its code must come from that module's file:
    # a look-alike with a copied __module__/__qualname__, or a patched module attribute, fails here.
    if _resolve(identity) is not adapter: raise QualificationError("ADAPTER_IDENTITY_MISMATCH")
    if Path(adapter.__code__.co_filename).resolve() != _module_file(adapter.__module__):
        raise QualificationError("ADAPTER_IDENTITY_MISMATCH")
    if implementation_digests(entry["implementation"]) != entry["implementation"]:
        raise QualificationError("IMPLEMENTATION_HASH_MISMATCH")
    return sha, entry


def qualification_for(contract, adapter) -> str:
    """The record's digest if it qualifies this adapter for this contract shape, else UNQUALIFIED (fail closed)."""
    try:
        return _match(contract, adapter)[0]
    except QualificationError:
        return UNQUALIFIED


def check_adapter(contract, adapter) -> dict:
    """Runtime gate: raises QualificationError unless the contract was qualified by the current pinned record
    and the adapter is the exact implementation that record qualifies."""
    sha, entry = _match(contract, adapter)
    if contract.qualification != sha: raise QualificationError("QUALIFICATION_MISMATCH")
    return entry


def record_entry(contract, adapter, modules, *, evidence, status="QUALIFIED", passed=True) -> dict:
    """One record entry for `adapter` under `contract`, hashing the modules it relies on. Used to (re)generate
    the record after requalification, and by tests to build throwaway records."""
    identity = adapter_identity(adapter)
    names = sorted(set(modules) | {adapter.__module__})
    return {"action_id": contract.action_id, "version": contract.version, "mechanism": contract.mechanism.value,
            "effect": contract.effect.value, "adapter": identity, "contract_shape_sha256": contract_shape(contract),
            "implementation": implementation_digests(names), "status": status, "passed": passed, "evidence": evidence}


def record_bytes(entries, **extra) -> bytes:
    body = {"schema_version": QUALIFICATION_SCHEMA_VERSION, "capabilities": list(entries), **extra}
    return (json.dumps(body, indent=2, sort_keys=True) + "\n").encode("utf-8")
