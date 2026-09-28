"""Edge minimum entry point with content-free avoidance telemetry (VG-1 G1)."""
from __future__ import annotations

from dataclasses import dataclass
import json
import os
from pathlib import Path
import time

from uri_v1.user_storage import locked_append, user_scoped_path
from .contracts import DecisionKind as D, EdgeTask
from .resolver import resolve

TELEMETRY_SCHEMA_VERSION = "m37.edge.telemetry.v1"


@dataclass(frozen=True)
class EdgeResult:
    route: str                  # LOCAL_VERIFIED | ESCALATE | CLARIFY
    decision: object
    local: object | None
    escalation: object | None


class EdgeTelemetry:
    def __init__(self, user_id, root):
        self.path = Path(user_scoped_path(user_id, os.path.join("edge", "telemetry.jsonl"), str(Path(root).resolve())))

    def record(self, event: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with locked_append(str(self.path)) as stream:
            stream.write(json.dumps(dict(event, schema_version=TELEMETRY_SCHEMA_VERSION), sort_keys=True).encode() + b"\n")

    def events(self) -> list:
        if not self.path.exists(): return []
        return [json.loads(x) for x in self.path.read_bytes().splitlines()]


class EdgeService:
    def __init__(self, *, registry, sources, runner, telemetry):
        self.registry, self.sources, self.runner, self.telemetry = registry, sources, runner, telemetry

    def handle(self, task: EdgeTask, package=None) -> EdgeResult:
        started = time.perf_counter()
        decision = resolve(task, package, self.registry, self.sources)
        local = None
        if decision.kind is D.LOCAL:
            local = self.runner.run(task, decision)
            route = "LOCAL_VERIFIED" if local.completed else "ESCALATE"
            esc = local.escalation
        else:
            route, esc = decision.kind.value, decision.escalation
        self.telemetry.record({"trace_id": task.trace_id, "task_class": task.task_class.value, "decision": decision.kind.value,
                               "reason": decision.reason.value, "capability_id": decision.capability_id, "route": route,
                               "verification_status": local.verification_status if local else None,
                               "escalation_avoided": route == "LOCAL_VERIFIED",
                               "qualification_run": bool(getattr(self.registry, "qualification_run", False)),
                               "latency_ms": round((time.perf_counter() - started) * 1000, 1)})
        return EdgeResult(route, decision, local, esc)
