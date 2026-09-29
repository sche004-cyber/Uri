"""Q-O2: end-to-end scenarios D1-D12 (M39 plan §5.2). Offline, deterministic,
fake harness (tests/m38_harness_support.py-style adapter, no real API calls),
run twice per scenario checking identical outcomes.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.office import request as req
from uri_v1.office.flow import OfficeSession
from tests.m39_office_support import OfficeEnv, SALES, fake_adapter, make_workbook, script as script_text

GATE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "m39_office" / "threshold_gate.json"


def start(env, raw):
    parsed = req.parse(raw)
    assert parsed.ok, parsed
    turn_id, trace_id = env.turn()
    return env.session.start(raw, session_id="session-d", turn_id=turn_id, trace_id=trace_id, parsed=parsed)


def answer(env, task_id, round_id, raw):
    turn_id, trace_id = env.turn()
    return env.session.answer(task_id, raw, session_id="session-d", turn_id=turn_id, trace_id=trace_id, round_id=round_id)


def confirm(env, task_id, raw="yes, run it"):
    turn_id, trace_id = env.turn()
    return env.session.confirm_escalation(task_id, raw, session_id="session-d", turn_id=turn_id, trace_id=trace_id)


def approve(env, task_id, raw="approve", **kw):
    turn_id, trace_id = env.turn()
    return env.session.approve_writeback(task_id, raw, session_id="session-d", turn_id=turn_id, trace_id=trace_id, **kw)


def test_gate_file_lists_all_scenarios():
    gate = json.loads(GATE_PATH.read_bytes())
    assert set(gate["q_o2"]["scenarios"]) == {f"D{i}" for i in range(1, 13)}


# -- D1: local remap (case/separator), approve, write-back verified -----------------------------

def test_d1_local_remap_write_back(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d1-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales.xlsx", SALES)
        original_script = script_text(column="amount")  # case-only mismatch: "amount" vs "Amount"
        env.write("report.py", original_script)
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "AWAITING_APPROVAL", step
        assert step.relpaths == ("report.py",)
        done = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
        assert done.kind == "COMPLETED", done
        assert (env.root / "report.py").read_text() != original_script
        assert '"Amount"' in (env.root / "report.py").read_text()


# -- D2: escalate, consent, honest fake fix, verified, approve, written -------------------------

def test_d2_escalate_honest_fix_write_back(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d2-{run}", monkeypatch, with_harness=True)
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text(column="Amt"))  # abbreviation: no unique local remap
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "ESCALATION_PROPOSAL", step
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        monkeypatch.setenv("URI_FAKE_FIND", '"Amt"')
        monkeypatch.setenv("URI_FAKE_REPLACE", '"Amount"')
        awaiting = confirm(env, step.task_id)
        assert awaiting.kind == "AWAITING_APPROVAL", awaiting
        done = approve(env, step.task_id, run_id=awaiting.run_id, relpaths=awaiting.relpaths)
        assert done.kind == "COMPLETED", done
        assert '"Amount"' in (env.root / "report.py").read_text()


# -- D3: harness claims success, changes nothing useful -> FAILED, nothing written ----------------

def test_d3_false_claim_rejected(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d3-{run}", monkeypatch, with_harness=True)
        make_workbook(env.root / "sales.xlsx", SALES)
        original = script_text(column="Amt")
        env.write("report.py", original)
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "ESCALATION_PROPOSAL", step
        monkeypatch.setenv("URI_FAKE_SCENARIO", "false_claim")
        result = confirm(env, step.task_id)
        assert result.kind == "HARNESS_FAILED", result
        assert result.verification_status != "VERIFIED"
        assert (env.root / "report.py").read_text() == original


# -- D4: harness empties the script's logic but exits 0 -> FAILED on output structure -------------

def test_d4_emptied_script_fails_output_structure(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d4-{run}", monkeypatch, with_harness=True)
        make_workbook(env.root / "sales.xlsx", SALES)
        original = script_text(column="Amt")
        env.write("report.py", original)
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "ESCALATION_PROPOSAL", step
        monkeypatch.setenv("URI_FAKE_SCENARIO", "empty_script")
        result = confirm(env, step.task_id)
        assert result.kind == "HARNESS_FAILED", result
        assert result.verification_status == "FAILED"
        assert (env.root / "report.py").read_text() == original


# -- D5: two plausible workbooks -> clarification; user picks; flow continues --------------------

def test_d5_ambiguous_workbook_clarification(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d5-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales_2024.xlsx", SALES)
        make_workbook(env.root / "sales_2025.xlsx", SALES)
        env.write("report.py", script_text(workbook="sales_2024.xlsx"))
        step = start(env, "make report.py work with the spreadsheet")
        assert step.kind == "CLARIFY", step
        assert step.roles["script"].state == "CONFIRMED"
        wb = step.roles["workbook"]
        assert wb.state == "PENDING" and wb.contract_id
        resolved = answer(env, step.task_id, wb.contract_id, "sales_2024.xlsx")
        assert resolved.kind in ("AWAITING_APPROVAL", "NOTHING_TO_WRITE", "ESCALATION_PROPOSAL"), resolved


# -- D6: original edited between verification and approval -> refused, nothing written -----------

def test_d6_original_changed_since_verification(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d6-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text(column="amount"))
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "AWAITING_APPROVAL", step
        (env.root / "report.py").write_text("# edited by someone else\n" + script_text(column="amount"))
        refused = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
        assert refused.kind == "WRITEBACK_REFUSED", refused
        # M39-1 repair: writeback.py now checks every current task reference
        # is still live *before* opening the workspace at all (so a stale
        # reference can never be discovered only after a write already
        # happened -- see uri_v1/office/writeback.py). That pre-check now
        # catches this case earlier than `Workspace.write_back`'s own
        # per-relpath check would, with a more general reason.
        assert refused.reason == "WRITEBACK_SOURCE_NOT_CURRENT"
        assert refused.written == ()


# -- D7: "don't apply it" -> no write-back --------------------------------------------------------

def test_d7_declined_approval_not_negated_word_alone(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d7-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales.xlsx", SALES)
        original = script_text(column="amount")
        env.write("report.py", original)
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "AWAITING_APPROVAL", step
        refused = approve(env, step.task_id, raw="don't apply it", run_id=step.run_id, relpaths=step.relpaths)
        assert refused.kind == "WRITEBACK_REFUSED", refused
        assert (env.root / "report.py").read_text() == original


# -- D8: user declines escalation -> no harness process started ----------------------------------

def test_d8_declines_escalation(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d8-{run}", monkeypatch, with_harness=True)
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text(column="Amt"))
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "ESCALATION_PROPOSAL", step
        result = confirm(env, step.task_id, raw="no, don't run anything")
        assert result.kind == "ESCALATION_DECLINED", result
        # M39-7 repair: a decline must clear the pending escalation, or every
        # later line (including a brand new request) keeps being routed to
        # confirm_escalation and declined again (the REPL "stuck after
        # decline" bug). The task itself is untouched (still open, with
        # URI's local findings) -- only the *pending proposal* is gone.
        assert step.task_id not in env.session._escalation


# -- D9: harness not installed -> typed message, nothing started ---------------------------------

def test_d9_harness_unavailable(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d9-{run}", monkeypatch, with_harness=True)
        env.session.adapter = ClaudeCodeAdapter("uri-m39-nonexistent-binary-xyz")
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text(column="Amt"))
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "ESCALATION_PROPOSAL", step
        result = confirm(env, step.task_id)
        assert result.kind == "HARNESS_UNAVAILABLE", result


# -- D10: pause after verification; new process; status -> resume -> approve; written once --------

def test_d10_pause_resume_new_process(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d10-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text(column="amount"))
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "AWAITING_APPROVAL", step
        turn_id, trace_id = env.turn()
        paused = env.session.pause(step.task_id, "pause", run_id=step.run_id, session_id="session-d",
                                   turn_id=turn_id, trace_id=trace_id)
        assert paused.kind == "PAUSED", paused

        # A new process: a fresh OfficeSession over the same durable stores.
        new_session = OfficeSession(log=env.log, sources=env.sources, recorder=env.recorder, retriever=env.retriever,
                                    edge=env.edge, scratch_root=env.scratch, user_id=env.user, run_store=env.store)
        rows = new_session.status()
        row = next(r for r in rows if r["task_id"] == step.task_id)
        assert row["status"] == "PAUSED"
        turn_id, trace_id = env.turn()
        resumed = new_session.resume(step.task_id, "resume", session_id="session-d", turn_id=turn_id, trace_id=trace_id)
        assert resumed.kind == "AWAITING_APPROVAL", resumed
        turn_id, trace_id = env.turn()
        done = new_session.approve_writeback(step.task_id, "approve", run_id=resumed.run_id, relpaths=resumed.relpaths,
                                             session_id="session-d", turn_id=turn_id, trace_id=trace_id)
        assert done.kind == "COMPLETED", done
        assert len(done.written) == 1


# -- D11: second request on the same files after D1's write-back -> new task, no STALE_INPUT ------

def test_d11_followup_request_after_writeback(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d11-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text(column="amount"))
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "AWAITING_APPROVAL", step
        done = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
        assert done.kind == "COMPLETED", done

        second = start(env, "make report.py work with sales.xlsx")
        assert second.task_id != step.task_id
        assert second.kind != "ERROR", second
        assert second.reason != "STALE_INPUT"
        assert second.kind == "NOTHING_TO_WRITE", second  # already compatible now


# -- D12: script already works -> ALREADY_COMPATIBLE; nothing to write ---------------------------

def test_d12_already_compatible(tmp_path, monkeypatch):
    for run in range(2):
        env = OfficeEnv(tmp_path / f"d12-{run}", monkeypatch, with_harness=False)
        make_workbook(env.root / "sales.xlsx", SALES)
        env.write("report.py", script_text())  # column="Amount" matches exactly
        step = start(env, "make report.py work with sales.xlsx")
        assert step.kind == "NOTHING_TO_WRITE", step
