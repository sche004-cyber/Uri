"""M39 repair round 2: regression tests for the R1 re-audit's residual findings
(R1-A..R1-D, see docs/plans/M39_IMPLEMENTATION_REPORT.md "Repair round 2" and
audits/M39_REPAIR1_REAUDIT_REPORT.md), turned from observation-only probes
(/mnt/project-files/audits/m39_reaudit/test_m39_r1_reaudit_probes.py) into
asserting regression tests, so a future change cannot silently reopen them.
"""
from __future__ import annotations

import sys
import unicodedata
from pathlib import Path

import pytest

from uri_v1.execution.harness.adapters import ClaudeCodeAdapter
from uri_v1.office import request as req
from uri_v1.office.flow import _is_consent
from tests.m39_office_support import answer_asks, request_names, OfficeEnv, SALES, make_workbook, script as script_text

ROOT = Path(__file__).resolve().parents[1]
EVIL = ROOT / "fixtures" / "m39_office" / "evil_claude_office.py"


def start(env, raw):
    parsed = req.parse(raw)
    assert parsed.ok, parsed
    turn_id, trace_id = env.turn()
    step = env.session.start(raw, session_id="session-r2", turn_id=turn_id, trace_id=trace_id, parsed=parsed)
    # Repair round 3 (R2-1): on the frozen M36 line a request naming both
    # files is confirmed one file per turn; answer those per-file questions
    # with the names the request used. Pinned in test_m39_repair3_regressions.
    return answer_asks(env, step, request_names(raw, parsed), session_id="session-r2")


def confirm(env, task_id, raw="yes, run it"):
    turn_id, trace_id = env.turn()
    return env.session.confirm_escalation(task_id, raw, session_id="session-r2", turn_id=turn_id, trace_id=trace_id)


def approve(env, task_id, raw="approve", **kw):
    turn_id, trace_id = env.turn()
    return env.session.approve_writeback(task_id, raw, session_id="session-r2", turn_id=turn_id, trace_id=trace_id, **kw)


def evil_env(tmp, monkeypatch, scenario):
    """A real HarnessRunner/ClaudeCodeAdapter pointed at the adversarial fake
    Claude Code above, never the network or real credentials (test-only)."""
    env = OfficeEnv(tmp, monkeypatch, with_harness=True)
    home = tmp / "home"; home.mkdir(exist_ok=True)
    env.session.adapter = ClaudeCodeAdapter((sys.executable, str(EVIL)), home=home)
    monkeypatch.setenv("URI_PROBE_SCENARIO", scenario)
    return env


# -- R1-A (residual of M39-4): pause() could re-arm ANY run_id as "offered" -----------------------

def test_r1_a_pause_refuses_a_run_id_this_session_never_offered(tmp_path, monkeypatch):
    """Any caller (not just the CLI) used to be able to feed pause() a
    run_id it invented -- a forged id, or one from a completely different
    run -- and have it accepted as the run offered for write-back approval.
    pause() must only ever re-affirm the run this exact session already
    offered via _offer_writeback."""
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    step = start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step

    forged = "0" * 32
    turn_id, trace_id = env.turn()
    paused = env.session.pause(step.task_id, "pause", run_id=forged, session_id="s", turn_id=turn_id, trace_id=trace_id)
    assert paused.kind == "ERROR"
    assert paused.reason == "RUN_ID_NOT_OFFERED"

    result = approve(env, step.task_id, run_id=forged, relpaths=step.relpaths)
    assert result.kind == "ERROR"
    assert result.reason == "RUN_ID_NOT_OFFERED"

    # The legitimately offered run is still approvable afterwards.
    ok = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
    assert ok.kind == "COMPLETED", ok


def test_r1_a_pause_refuses_another_tasks_run_id(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    env.write("other.py", script_text(column="amount"))
    a = start(env, "make report.py work with sales.xlsx")
    b = start(env, "make other.py work with sales.xlsx")
    assert a.kind == b.kind == "AWAITING_APPROVAL"

    turn_id, trace_id = env.turn()
    paused = env.session.pause(b.task_id, "pause", run_id=a.run_id, session_id="s", turn_id=turn_id, trace_id=trace_id)
    assert paused.kind == "ERROR"
    assert paused.reason == "RUN_ID_NOT_OFFERED"

    # b's own offered run must still be the one write-back would use.
    result = approve(env, b.task_id, relpaths=a.relpaths)
    assert result.kind == "WRITEBACK_REFUSED"
    assert result.reason == "NOTHING_TO_WRITE_BACK"  # a's relpaths, not b's


def test_r1_a_flagged_run_via_pause_after_restore_cannot_write_back(tmp_path, monkeypatch):
    """Real harness path (not a hand-written run-store record): the fake
    Claude Code writes a fixed script that, when the M37 verifier
    re-executes the candidate, also appends to the real original workbook.
    URI's own post-verification re-check (uri_v1/execution/harness/runner.py)
    correctly flags this run (ORIGINAL_MODIFIED_DURING_VERIFICATION) and
    HarnessOutcome.verified is False -- so confirm_escalation never offers
    this run for write-back at all, and (per the R1-A fix above) pause()
    cannot be used afterwards to re-arm it, restore or no restore."""
    env = evil_env(tmp_path, monkeypatch, "touch_original")
    make_workbook(env.root / "sales.xlsx", SALES)
    original_workbook = (env.root / "sales.xlsx").read_bytes()
    original_script = script_text(column="Amt")
    env.write("report.py", original_script)
    monkeypatch.setenv("URI_PROBE_ORIGINAL", str(env.root / "sales.xlsx"))

    step = start(env, "make report.py work with sales.xlsx")
    result = confirm(env, step.task_id, "yes")
    assert result.kind == "HARNESS_FAILED", result
    # Repair round 3 (re-audit R2-5): on the frozen M38 line (bd7c450) the
    # runner appends a superseding FAILED verification when
    # ORIGINAL_MODIFIED_DURING_VERIFICATION fires, so the run is FAILED, not
    # VERIFIED-with-a-flag as on the old base. That closes the old
    # "M38-owned gap" at the store level; the offer guard below stays as
    # defence in depth.
    assert result.verification_status == "FAILED"
    assert "ORIGINAL_MODIFIED_DURING_VERIFICATION" in result.safety_flags

    direct = approve(env, step.task_id, run_id=result.run_id, relpaths=("report.py",))
    assert direct.kind == "ERROR"
    assert direct.reason == "NO_PENDING_RUN"

    (env.root / "sales.xlsx").write_bytes(original_workbook)  # simulate a revert/restore
    turn_id, trace_id = env.turn()
    paused = env.session.pause(step.task_id, "pause", run_id=result.run_id, session_id="s",
                               turn_id=turn_id, trace_id=trace_id)
    assert paused.kind == "ERROR"
    assert paused.reason == "RUN_ID_NOT_OFFERED"

    after_pause = approve(env, step.task_id, run_id=result.run_id, relpaths=("report.py",))
    assert after_pause.kind == "ERROR"
    assert after_pause.reason == "NO_PENDING_RUN"
    assert (env.root / "report.py").read_text() == original_script, "flagged run must never be written back"


# -- R1-B (residual of M39-3): smart quotes, backticks, unquoted space names -----------------------

@pytest.mark.parametrize("text", [
    'make "my report.py" work with sales.xlsx',
    "make “my report.py” work with sales.xlsx",   # smart double quotes (Word/macOS)
    "make ‘my report.py’ work with sales.xlsx",   # smart single quotes
    "make `my report.py` work with sales.xlsx",             # markdown backticks
])
def test_r1_b_quote_variants_bind_the_full_space_containing_name(tmp_path, monkeypatch, text):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    env.write("my report.py", script_text(column="amount"))
    step = start(env, text)
    assert step.kind == "AWAITING_APPROVAL", step
    assert step.relpaths == ("my report.py",), step


def test_r1_b_unquoted_space_name_is_ambiguous_not_silently_wrong(tmp_path, monkeypatch):
    """Without quotes, "my report.py" cannot be told apart from "my" (a
    possessive) plus the distinct file "report.py" -- refusing (asking for
    clarification/quoting) is required; silently binding "report.py" is the
    original M39-3 wrong-file bind."""
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    env.write("my report.py", script_text(column="amount"))
    parsed = req.parse("make my report.py work with sales.xlsx")
    assert parsed.ok is False
    assert parsed.reason == "ROLE_AMBIGUOUS"


def test_r1_b_smart_quote_end_to_end_never_writes_the_plain_file(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    before_plain = script_text(column="amount")
    env.write("report.py", before_plain)
    env.write("my report.py", script_text(column="Amount"))   # distinguishable contents
    step = start(env, "make “my report.py” work with sales.xlsx")
    if step.kind == "AWAITING_APPROVAL":
        approve(env, step.task_id, relpaths=step.relpaths)
    assert (env.root / "report.py").read_text() == before_plain, "the plain report.py must never be touched"


# -- R1-C (residual of M39-2): non-English words, emoji and full-width punctuation ------------------

@pytest.mark.parametrize("text", [
    "ok 等一下",       # "ok wait a moment" (Chinese)
    "ok не надо",  # "ok not necessary" (Russian)
    "yes 不要",            # "yes don't" (Chinese)
    "ok ❌",                   # cross mark emoji
    "yes ✋",                  # raised hand emoji
    "okay \U0001F6D1",              # stop sign emoji
    "ok, run it？",            # full-width question mark
    "okay‽",                  # interrobang
    "¿yes",                   # inverted question mark
    "yes 2",
])
def test_r1_c_non_ascii_and_symbolic_replies_are_not_consent(text):
    assert _is_consent(text) is False


def test_r1_c_non_ascii_decline_never_starts_the_harness(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="Amt"))  # abbreviation forces escalation
    step = start(env, "make report.py work with sales.xlsx")
    assert step.kind == "ESCALATION_PROPOSAL", step
    result = confirm(env, step.task_id, "ok ❌ 不要")
    assert result.kind == "ESCALATION_DECLINED", result


# -- R1-D (new regression): sentence-final punctuation must not be refused -------------------------

@pytest.mark.parametrize("text,expected_script,expected_workbook", [
    ("make report.py work with sales.xlsx.", "report.py", "sales.xlsx"),
    ("Please fix report.py. It should work with sales.xlsx", "report.py", "sales.xlsx"),
    ("make report.py work with sales.xlsx...", "report.py", "sales.xlsx"),
    ("make ./report.py work with sales.xlsx", "report.py", "sales.xlsx"),
])
def test_r1_d_sentence_final_punctuation_still_parses(text, expected_script, expected_workbook):
    parsed = req.parse(text)
    assert parsed.ok, parsed
    assert text[parsed.spans["script"][0]:parsed.spans["script"][1]] == expected_script
    assert text[parsed.spans["workbook"][0]:parsed.spans["workbook"][1]] == expected_workbook


@pytest.mark.parametrize("text", [
    "make report.py.bak work with sales.xlsx",
    "make data.xlsx.py work with sales.xlsx",
])
def test_r1_d_fix_does_not_reopen_m39_3_longer_token_refusal(text):
    """The R1-D fix (trailing '.' is punctuation, not continuation) must not
    reopen M39-3's refusal of a match that is really only part of a longer
    filename token."""
    parsed = req.parse(text)
    assert parsed.ok is False
    assert parsed.reason == "ROLE_AMBIGUOUS"
