"""Q-O3 live smoke (M39 plan R0 §5.3), opt-in only.

Skipped unless URI_M39_LIVE_SMOKE=1. When enabled it runs scenario D2 once
against the REAL Claude Code CLI on a generated fixture in a temporary folder
(never the User's own files):
abbreviated column -> ESCALATION_PROPOSAL -> "yes" -> real harness run ->
URI verification -> approve only if VERIFIED.

Spend policy (2026-09-28): subscription-authenticated Claude Code only. The
test refuses to start if ANTHROPIC_API_KEY is set or the adapter probe does not
report auth_mode "subscription". The flow's own per-run limit is
max_budget_usd=1.0 (Claude Code's notional figure under a subscription).

Pass: the reply agrees with URI's own verifier record, and no original changes
without approval. A harness that fails to fix the task is a valid, honestly
reported result (plan §5.3). Optional env: URI_M39_CLAUDE (path to the claude
executable, default "claude" on PATH), URI_M39_LIVE_SMOKE_OUT (write a JSON
evidence record there).
"""
from __future__ import annotations

import json
import os
import shutil
from pathlib import Path

import pytest

from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.office import request as req
from uri_v1.office.view import render
from tests.m39_office_support import answer_asks, request_names, OfficeEnv, SALES, make_workbook, script as script_text

pytestmark = pytest.mark.skipif(os.environ.get("URI_M39_LIVE_SMOKE") != "1",
                                reason="live Claude Code smoke is opt-in: set URI_M39_LIVE_SMOKE=1")

REQUEST = "make report.py work with sales.xlsx"


def _turn(env):
    return env.turn()


def test_q_o3_live_smoke_d2(tmp_path, monkeypatch):
    if os.environ.get("ANTHROPIC_API_KEY"):
        pytest.fail("REFUSED: ANTHROPIC_API_KEY is set; this run must use the subscription login")
    executable = os.environ.get("URI_M39_CLAUDE") or shutil.which("claude") or "claude"

    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    env.session.adapter = ClaudeCodeAdapter(executable, home=Path.home())
    probe = env.session.adapter.probe()
    if not probe.get("installed"):
        pytest.fail(f"Claude Code not found at {executable!r}")
    if probe.get("auth_mode") != "subscription":
        pytest.fail(f"REFUSED: auth_mode is {probe.get('auth_mode')!r}, not 'subscription'")

    make_workbook(env.root / "sales.xlsx", SALES)
    original_script = script_text(column="Amt")  # abbreviation: Edge cannot remap locally
    env.write("report.py", original_script)
    original_workbook = (env.root / "sales.xlsx").read_bytes()

    parsed = req.parse(REQUEST)
    turn_id, trace_id = _turn(env)
    step = env.session.start(REQUEST, session_id="live-smoke", turn_id=turn_id, trace_id=trace_id, parsed=parsed)
    step = answer_asks(env, step, request_names(REQUEST, parsed), session_id="live-smoke")
    assert step.kind == "ESCALATION_PROPOSAL", step
    proposal = render(step)
    assert "Harness: Claude Code." in proposal

    turn_id, trace_id = _turn(env)
    result = env.session.confirm_escalation(step.task_id, "yes", session_id="live-smoke",
                                            turn_id=turn_id, trace_id=trace_id)
    reply = render(result)
    record = {"probe": {"version": probe.get("version"), "auth_mode": probe.get("auth_mode")},
              "proposal": proposal, "result_kind": result.kind, "reply": reply,
              "run_id": result.run_id, "safety_flags": list(result.safety_flags)}

    assert result.kind in ("AWAITING_APPROVAL", "NOTHING_TO_WRITE", "HARNESS_FAILED"), result
    run = env.store.get(result.run_id) if result.run_id else None
    verifications = (run or {}).get("verifications") or []
    record["verifier_status"] = verifications[-1]["status"] if verifications else None
    # Nothing reached the originals before any approval.
    unchanged_before_approval = ((env.root / "report.py").read_text() == original_script
                                 and (env.root / "sales.xlsx").read_bytes() == original_workbook)
    record["originals_unchanged_before_approval"] = unchanged_before_approval

    if result.kind == "AWAITING_APPROVAL":
        # The run-store statuses frozen M37 write-back accepts (workspace.py).
        assert record["verifier_status"] in ("VERIFIED", "STRUCTURALLY_VERIFIED")
        assert unchanged_before_approval
        turn_id, trace_id = _turn(env)
        done = env.session.approve_writeback(result.task_id, "approve", run_id=result.run_id, relpaths=result.relpaths,
                                             session_id="live-smoke", turn_id=turn_id, trace_id=trace_id)
        record["approval_kind"] = done.kind
        assert done.kind == "COMPLETED", done
    elif result.kind == "HARNESS_FAILED":
        # An honest failure is a valid smoke result; the reply must match the
        # verifier and must not hide a changed original.
        assert record["verifier_status"] not in ("VERIFIED", "STRUCTURALLY_VERIFIED") or result.safety_flags
        if not unchanged_before_approval:
            assert "were changed during" in reply

    out = os.environ.get("URI_M39_LIVE_SMOKE_OUT")
    if out:
        Path(out).write_text(json.dumps(record, indent=2), encoding="utf-8")
