"""Durable task / step state for multi-step requests, with restart recovery.

One JSON file per task (atomic write: temp file + fsync + replace). The ledger records what URI has PROPOSED and
what Core has REPORTED; it never authorizes anything. Recovery rules (applied by `recover()` after a restart):

  * a step whose Core turn may have dispatched (Core state ticket_issued / executing / execution_uncertain) becomes
    UNCERTAIN and is never retried automatically (no duplicate execution after an uncertain failure);
  * a step that was waiting for approval returns to PENDING: Core keeps pending approvals in memory only and fails
    closed after a restart, so the user starts that step again (Core's intent ledger still blocks re-execution of
    an already verified or possibly executed intent);
  * a task paused for provider quota stays paused with its checkpoint; only an explicit user choice resumes it.
"""
from __future__ import annotations

import json
import os
import threading
import time
import uuid
from pathlib import Path

TASK_STATES = {"PROPOSED", "AWAITING_PLAN_APPROVAL", "RUNNING", "WAITING_APPROVAL", "WAITING_USER_CHOICE",
               "PAUSED_PROVIDER_QUOTA", "COMPLETED", "FAILED", "CANCELLED", "NEEDS_ATTENTION"}
STEP_STATES = {"PENDING", "IN_CORE", "WAITING_CONFIRMATION", "WAITING_APPROVAL", "EXECUTING", "VERIFIED", "ANSWERED",
               "FAILED", "UNCERTAIN", "REFUSED", "SKIPPED", "CANCELLED", "WAITING_USER_CHOICE"}
STEP_TERMINAL = {"VERIFIED", "ANSWERED", "FAILED", "UNCERTAIN", "REFUSED", "SKIPPED", "CANCELLED"}
# Core states after which an effect may exist.
CORE_MAY_HAVE_RUN = {"ticket_issued", "executing", "execution_uncertain"}

_STEP_TRANSITIONS = {
    "PENDING": {"IN_CORE", "ANSWERED", "SKIPPED", "CANCELLED", "WAITING_USER_CHOICE", "REFUSED", "FAILED"},
    "WAITING_USER_CHOICE": {"PENDING", "IN_CORE", "CANCELLED", "SKIPPED"},
    "IN_CORE": {"WAITING_CONFIRMATION", "WAITING_APPROVAL", "EXECUTING", "VERIFIED", "FAILED", "UNCERTAIN",
                "REFUSED", "ANSWERED", "PENDING", "CANCELLED", "WAITING_USER_CHOICE"},
    "WAITING_CONFIRMATION": {"IN_CORE", "WAITING_CONFIRMATION", "WAITING_APPROVAL", "REFUSED", "CANCELLED", "PENDING",
                             "FAILED", "VERIFIED", "UNCERTAIN", "ANSWERED"},
    "WAITING_APPROVAL": {"EXECUTING", "VERIFIED", "CANCELLED", "FAILED", "UNCERTAIN", "PENDING", "REFUSED",
                         "WAITING_USER_CHOICE"},
    "EXECUTING": {"VERIFIED", "FAILED", "UNCERTAIN", "WAITING_USER_CHOICE"},
}


class LedgerError(ValueError):
    pass


def _atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class TaskLedger:
    def __init__(self, root):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _path(self, task_id):
        uuid.UUID(task_id)          # task ids are UUIDs: no path traversal through ids
        return self.root / (task_id + ".json")

    def create(self, *, session_id, request_text, plan=None, state="PROPOSED") -> dict:
        task = {"task_id": str(uuid.uuid4()), "session_id": session_id, "request_text": request_text,
                "created_at": time.time(), "updated_at": time.time(), "state": state, "plan": plan,
                "steps": [], "provider_choices": [], "checkpoint": None, "events": []}
        if plan:
            task["steps"] = [{"step_id": s["id"], "description": s["description"], "kind": s["kind"],
                              "capability": s.get("capability"), "source_span": s.get("source_span"),
                              "depends_on": list(s.get("depends_on") or []), "state": "PENDING",
                              "core": None, "attempts": 0} for s in plan["steps"]]
        self._event(task, "created", state=state)
        with self._lock:
            _atomic_json(self._path(task["task_id"]), task)
        return task

    def get(self, task_id) -> dict:
        p = self._path(task_id)
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except FileNotFoundError:
            raise LedgerError("TASK_NOT_FOUND") from None
        except ValueError:
            raise LedgerError("TASK_UNREADABLE") from None

    def list(self):
        return sorted(p.stem for p in self.root.glob("*.json"))

    @staticmethod
    def _event(task, kind, **data):
        task["events"].append({"t": time.time(), "kind": kind, **data})
        del task["events"][:-200]

    def update(self, task_id, fn):
        with self._lock:
            task = self.get(task_id)
            fn(task)
            task["updated_at"] = time.time()
            _atomic_json(self._path(task_id), task)
            return task

    def set_state(self, task_id, state, **data):
        if state not in TASK_STATES:
            raise LedgerError("UNKNOWN_TASK_STATE")

        def fn(task):
            if task["state"] in {"COMPLETED", "CANCELLED"} and state != task["state"]:
                raise LedgerError("TASK_CLOSED")
            task["state"] = state
            task.update({k: v for k, v in data.items() if k in ("checkpoint",)})
            self._event(task, "task_state", state=state, **{k: v for k, v in data.items() if k != "checkpoint"})
        return self.update(task_id, fn)

    def step(self, task, step_id):
        for s in task["steps"]:
            if s["step_id"] == step_id:
                return s
        raise LedgerError("STEP_NOT_FOUND")

    def set_step(self, task_id, step_id, state, *, core=None, note=None):
        if state not in STEP_STATES:
            raise LedgerError("UNKNOWN_STEP_STATE")

        def fn(task):
            s = self.step(task, step_id)
            if s["state"] in STEP_TERMINAL:
                raise LedgerError("STEP_TERMINAL")
            if state != s["state"] and state not in _STEP_TRANSITIONS.get(s["state"], set()):
                raise LedgerError("STEP_TRANSITION_%s_TO_%s" % (s["state"], state))
            if state == "IN_CORE" and s["state"] in ("PENDING", "WAITING_USER_CHOICE"):
                s["attempts"] += 1
            s["state"] = state
            if core is not None:
                s["core"] = core
            self._event(task, "step_state", step=step_id, state=state, note=note)
            if all(x["state"] in STEP_TERMINAL for x in task["steps"]) and task["steps"]:
                bad = [x for x in task["steps"] if x["state"] in ("FAILED", "UNCERTAIN", "REFUSED")]
                task["state"] = "NEEDS_ATTENTION" if bad else "COMPLETED"
                self._event(task, "task_state", state=task["state"])
        return self.update(task_id, fn)

    def ready_steps(self, task):
        done = {s["step_id"] for s in task["steps"] if s["state"] in ("VERIFIED", "ANSWERED", "SKIPPED")}
        return [s for s in task["steps"] if s["state"] == "PENDING" and set(s["depends_on"]) <= done]

    def blocked_steps(self, task):
        """Pending steps whose dependency ended without success: never run on top of a failure or uncertainty."""
        bad = {s["step_id"] for s in task["steps"] if s["state"] in ("FAILED", "UNCERTAIN", "REFUSED", "CANCELLED")}
        return [s for s in task["steps"] if s["state"] == "PENDING" and set(s["depends_on"]) & bad]

    def record_provider_choice(self, task_id, provider, by="user"):
        def fn(task):
            task["provider_choices"].append({"t": time.time(), "provider": provider, "by": by})
            self._event(task, "provider_choice", provider=provider, by=by)
        return self.update(task_id, fn)

    def recover(self) -> list:
        """Apply the restart rules to every non-closed task. Returns a summary (for the UI and evidence)."""
        out = []
        for tid in self.list():
            try:
                task = self.get(tid)
            except LedgerError as exc:
                out.append({"task_id": tid, "error": str(exc)})
                continue
            if task["state"] in {"COMPLETED", "CANCELLED", "FAILED"}:
                continue
            changes = []

            def fn(t):
                for s in t["steps"]:
                    core_state = (s.get("core") or {}).get("state")
                    if s["state"] == "EXECUTING" or (s["state"] in ("IN_CORE", "WAITING_APPROVAL")
                                                     and core_state in CORE_MAY_HAVE_RUN):
                        s["state"] = "UNCERTAIN"
                        changes.append((s["step_id"], "UNCERTAIN"))
                    elif s["state"] in ("IN_CORE", "WAITING_APPROVAL", "WAITING_CONFIRMATION"):
                        s["state"] = "PENDING"
                        changes.append((s["step_id"], "PENDING"))
                if any(c[1] == "UNCERTAIN" for c in changes):
                    t["state"] = "NEEDS_ATTENTION"
                elif t["state"] in ("RUNNING", "WAITING_APPROVAL"):
                    t["state"] = "WAITING_USER_CHOICE" if changes else t["state"]
                self._event(t, "recovered", changes=changes)
            self.update(tid, fn)
            out.append({"task_id": tid, "changes": changes})
        return out
