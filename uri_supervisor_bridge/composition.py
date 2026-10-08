"""Phase 2D composition: the explicit, file-backed reasoning policy for the paired server and the client-side
composition that pairs it (persisted qualification -> Phase 1 registry + supervisor bindings -> bridge).

Server side. The frozen default composition lists exactly one row, the deterministic no-Brain source
(`uri_core.app.paired_server.default_composition`). Phase 2D does not change that file. Instead a Phase 2 server
profile reads an explicit policy file in the SERVER's own state root (`<state_root>/control/phase2_reasoning_policy.json`)
and lists its rows in addition to the deterministic one. A row is a (kind, provider, model) triple the owner chose to
offer; it is still only an *offer*: the client registry, the bridge and the ticket chain decide whether anything runs.
No row is ever inferred from an installed binary, a model advertisement or a client's claim.

Client side. `compose_client` (qualification.py) turns persisted, re-validated evidence into the Phase 1
`HarnessRegistry` qualification plus pinned `ExecutorBinding`s; `build_bridge` wires them into one `SupervisorBridge`.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from uri_core.core.paired_reasoning import ReasoningSelectionPolicy

from .bridge import SupervisorBridge
from .qualification import ClientComposition, compose_client

POLICY_SCHEMA = "uri.phase2d.reasoning_policy.v1"
DETERMINISTIC_ROW = ("server_local_model", "uri-deterministic", None)
# The only kind Phase 2 adds rows for. Cloud-model and server-local-model rows stay owner decisions outside Phase 2.
ALLOWED_KINDS = ("client_external_harness",)
QUALIFIED_CAPABILITIES = ("remember_fact", "external_harness_task")
_PROVIDER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")


class PolicyError(ValueError):
    pass


def policy_path(state_root) -> Path:
    return Path(state_root).resolve() / "control" / "phase2_reasoning_policy.json"


def load_policy_rows(path) -> frozenset:
    """Deterministic row + every valid row in the file. A malformed file is refused as a whole (fail closed: no
    harness rows), never partially accepted."""
    rows = {DETERMINISTIC_ROW}
    p = Path(path)
    if not p.is_file():
        return frozenset(rows)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise PolicyError("POLICY_UNREADABLE") from None
    if not isinstance(data, dict) or data.get("schema") != POLICY_SCHEMA or not isinstance(data.get("rows"), list):
        raise PolicyError("POLICY_SCHEMA")
    for row in data["rows"]:
        if not isinstance(row, dict) or set(row) != {"kind", "provider", "model"}:
            raise PolicyError("POLICY_ROW_SHAPE")
        kind, provider, model = row["kind"], row["provider"], row["model"]
        if kind not in ALLOWED_KINDS:
            raise PolicyError("POLICY_KIND_NOT_ALLOWED")
        if not isinstance(provider, str) or not _PROVIDER.fullmatch(provider):
            raise PolicyError("POLICY_PROVIDER_INVALID")
        if model is not None and (not isinstance(model, str) or not _MODEL.fullmatch(model)):
            raise PolicyError("POLICY_MODEL_INVALID")
        rows.add((kind, provider, model))
    return frozenset(rows)


def write_policy(path, rows) -> Path:
    """Owner-side helper: write an explicit policy file. `rows` are (kind, provider, model) triples."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    rows = sorted({tuple(r) for r in rows} - {DETERMINISTIC_ROW}, key=str)   # the deterministic row is implied, never listed
    body = {"schema": POLICY_SCHEMA, "rows": [{"kind": k, "provider": pr, "model": m} for k, pr, m in rows]}
    load_policy_rows_from_data(body)
    p.write_text(json.dumps(body, indent=1, sort_keys=True), encoding="utf-8")
    return p


def load_policy_rows_from_data(data):
    import tempfile
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8") as f:
        json.dump(data, f)
        name = f.name
    try:
        return load_policy_rows(name)
    finally:
        Path(name).unlink(missing_ok=True)


def phase2_server_composition(policy_file) -> dict:
    """`create_app(runtime, composition=...)` input for the Phase 2 server profile."""
    rows = load_policy_rows(policy_file)
    return {"policy": ReasoningSelectionPolicy(rows), "qualified": QUALIFIED_CAPABILITIES}


def build_bridge(client_root, composition: ClientComposition, **bridge_kwargs) -> SupervisorBridge:
    return SupervisorBridge(client_root, registry=composition.registry, executors=composition.executors, **bridge_kwargs)


def compose_and_build(client_root, *, trust, allow_fixture=False, auth_probe=None, environ=None, **bridge_kwargs):
    comp = compose_client(client_root, trust=trust, allow_fixture=allow_fixture, auth_probe=auth_probe, environ=environ)
    return comp, build_bridge(client_root, comp, **bridge_kwargs)
