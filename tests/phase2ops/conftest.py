"""Phase 2 UI/operations fixtures: the Phase 2D REAL-server stack (real paired server, real client persistence/DPAPI,
real supervisor/ledger/job containment, persisted FIXTURE_ONLY qualification, SYNTHETIC fake harness) driven through
the execution lifecycle frames (`execution_begin` / `execution_status` / `execution_cancel` / `execution_list`)."""
from __future__ import annotations

import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for p in (str(ROOT), str(ROOT / "tests")):
    if p not in sys.path:
        sys.path.insert(0, p)

from phase2b.conftest import CLAUDE, CODEX, uid  # noqa: E402,F401
from phase2d.conftest import HARNESS_ROWS, ROOT, Stack, fixture_record, stack  # noqa: E402,F401
from uri_supervisor_bridge.execution import ACTIVE_STATES, TERMINAL_STATES  # noqa: E402,F401

TEXT = "use the harness to write a greeting into out.txt"


def begin(stack, turn, *, service=None, approval_digest=None, proposal_digest=None):
    """`execution_begin` exactly as a UI echoing the card it displayed would send it."""
    req, prop = turn["approval_request"], turn["execution_proposal"]
    cmd = {"command": "execution_begin", "turn_id": turn["turn_id"],
           "approval_digest": req["approval_digest"] if approval_digest is None else approval_digest,
           "proposal_digest": prop["proposal_digest"] if proposal_digest is None else proposal_digest}
    return (service or stack.service).handle("execution_begin", cmd)


def status(stack, eid, service=None):
    return (service or stack.service).handle("execution_status", {"command": "execution_status", "execution_id": eid})


def cancel(stack, eid, service=None):
    return (service or stack.service).handle("execution_cancel", {"command": "execution_cancel", "execution_id": eid})


def listing(stack, service=None):
    return (service or stack.service).handle("execution_list", {"command": "execution_list"})


def wait_for(stack, eid, predicate, timeout=30, service=None):
    deadline = time.monotonic() + timeout
    last = None
    while time.monotonic() < deadline:
        last = status(stack, eid, service)
        if predicate(last):
            return last
        time.sleep(0.05)
    raise AssertionError(f"timeout waiting for execution {eid}: state={last and last.get('state')} reason={last and last.get('reason')}")


def wait_terminal(stack, eid, timeout=40, service=None):
    return wait_for(stack, eid, lambda s: s["state"] in TERMINAL_STATES, timeout, service)


def wait_running(stack, eid, timeout=30, service=None):
    """Running AND the ledger shows a live attempt with a pid (the executor really exists)."""
    def live(s):
        att = ((s.get("ledger") or {}).get("attempts") or [])
        return s["state"] == "running" and any(a["status"] == "RUNNING" and a["pid"] for a in att)
    return wait_for(stack, eid, live, timeout, service)
