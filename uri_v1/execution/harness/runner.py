"""HarnessRunner: escalation → copy-in workspace → capsule → harness → URI diff →
claim → URI verification → lineage. The harness never decides its own outcome.

Recorded dependencies: M37 workspace/acceptance/verifier/lineage (5460d64) and
M36 recorder/sources (405db1f); both PROVISIONAL.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import threading

from uri_v1.execution.acceptance import AcceptanceCriteria
from uri_v1.execution.lineage import record_and_verify
from uri_v1.execution.workspace import Workspace, WorkspaceInput, new_run_id
from .capsule import build_capsule
from .contracts import CapabilityGrant, ClaimedOutcome, HarnessError, Limits, PermissionProfile
from .process import supervise


@dataclass(frozen=True)
class HarnessOutcome:
    run_id: str
    verified: bool
    verification_status: str      # VERIFIED | PARTIALLY_VERIFIED | FAILED | UNVERIFIABLE | CLAIMED_ONLY | NOT_RECORDED
    claimed_outcome: str
    safety_flags: tuple
    claim_record_id: str | None
    verifier_record_id: str | None
    metrics: dict
    reason: str | None = None


class HarnessRunner:
    def __init__(self, *, user_id, scratch_root, run_store, recorder, ledger, sources):
        self.user_id, self.scratch_root, self.store = user_id, scratch_root, run_store
        self.recorder, self.ledger, self.sources = recorder, ledger, sources

    def run(self, escalation, adapter, *, session_id, posture: PermissionProfile | None = None,
            capabilities: CapabilityGrant | None = None, limits: Limits | None = None,
            cancel: threading.Event | None = None, run_id: str | None = None) -> HarnessOutcome:
        if AcceptanceCriteria.from_dict(escalation.acceptance).sha256 != escalation.acceptance_sha256:
            raise HarnessError("ACCEPTANCE_TAMPERED")
        probe = adapter.probe()
        if not probe.get("installed"): raise HarnessError("HARNESS_UNAVAILABLE")
        inventory = adapter.inventory()
        posture = posture or PermissionProfile()
        if posture.grants:
            # An elevation grant is scoped to one run (H-3/P3b): the caller must name
            # the run it was issued for, and it must be the run about to happen.
            if not run_id: raise HarnessError("RUN_ID_REQUIRED_FOR_ELEVATION")
            if not all(g.valid_for(run_id) for g in posture.grants): raise HarnessError("ELEVATION_GRANT_INVALID")
        run_id = run_id or new_run_id()
        ws = Workspace.create(user_id=self.user_id, scratch_root=self.scratch_root, sources=self.sources, run_id=run_id,
                              inputs=[WorkspaceInput(i.role, i.source_id, i.content_sha256) for i in escalation.inputs])
        capsule = build_capsule(escalation, ws, harness_type=adapter.harness_type, posture=posture, capabilities=capabilities, limits=limits)
        argv, env, prompt = adapter.invocation(capsule, ws.bundle, inventory)
        self.store.append(run_id, "RUN_STARTED", {
            "executor": "HARNESS", "task_id": escalation.task_id, "trace_id": escalation.trace_id,
            "workspace_dir": str(ws.base), "manifest": [e.__dict__ for e in ws.manifest], "manifest_sha256": ws.manifest_sha256,
            "acceptance": escalation.acceptance, "acceptance_sha256": escalation.acceptance_sha256,
            "capsule": capsule.to_dict(), "capsule_sha256": capsule.sha256,
            "adapter": {"type": adapter.harness_type.value, "version": probe.get("version"), "auth_mode": probe.get("auth_mode")},
            "inventory_sha256": inventory.sha256, "inventory_items": len(inventory.items),
            "argv_flags": [a for a in argv[1:] if a.startswith("-")]})
        ws.acquire(run_id)
        try:
            proc = supervise(argv, cwd=ws.files, env=env, stdin_bytes=prompt, timeout_s=capsule.limits.timeout_s,
                             inactivity_s=capsule.limits.inactivity_s, log_path=ws.bundle / "harness.log", cancel=cancel)
        finally:
            ws.release(run_id)
            mcp = Path(ws.bundle) / "mcp.json"
            if mcp.exists(): mcp.unlink()   # per-run capability config never outlives the run
        claims = adapter.parse(proc, capsule, probe.get("version"))
        flags = []
        if not proc.settled: flags.append("PROCESS_NOT_SETTLED")
        originals_changed = ws.originals_unchanged(self.sources)
        if originals_changed: flags.append("ORIGINAL_MODIFIED_DURING_RUN")
        diff = ws.diff()
        if diff["containment_violations"]: flags.append("CONTAINMENT_VIOLATION")
        claim = claims.to_claim()
        lineage = record_and_verify(recorder=self.recorder, ledger=self.ledger, store=self.store, workspace=ws, run_id=run_id,
                                    task_id=escalation.task_id, action_label=f"{adapter.harness_type.value.lower()} harness run",
                                    session_id=session_id, trace_id=escalation.trace_id,
                                    claimed_failed=claims.claimed_outcome is ClaimedOutcome.FAILED,
                                    exit_code=proc.exit_code if isinstance(proc.exit_code, int) and proc.exit_code >= 0 else None,
                                    executor_claim=claim,
                                    uri_observations={"safety_flags": flags, "originals_changed": originals_changed,
                                                      "process_settled": proc.settled})
        metrics = dict(claims.usage, capsule_instructions_bytes=len(prompt), input_files=len(ws.manifest),
                       changed_files=len(lineage.uri_computed_diff["changes"]), exit_code=proc.exit_code,
                       timed_out=proc.timed_out, inactivity_killed=proc.inactivity_killed)
        # Re-check the originals after verification too (H-2/M-1, probe P8): the run store
        # already reflects the pre-verification check, but verification can itself execute
        # harness-written code (M37 verifier, no sandbox), which can modify an original only
        # after the first check ran. A run is never called clean on the strength of a check
        # that predates code execution it did not see.
        if not originals_changed and ws.originals_unchanged(self.sources):
            flags.append("ORIGINAL_MODIFIED_DURING_VERIFICATION")
        verified = lineage.verification_status == "VERIFIED" and not flags
        return HarnessOutcome(run_id, verified, lineage.verification_status, claims.claimed_outcome.value, tuple(flags),
                              lineage.claim_record_id, lineage.verifier_record_id, metrics, lineage.reason)
