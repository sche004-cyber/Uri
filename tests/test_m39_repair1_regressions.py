"""M39 repair round 1: regression tests for the audit's High findings
(M39-1..M39-4) and the CLI/logic defects (M39-3, M39-7, M39-8, M39-9), turned
from observation-only probes (see docs/plans/M39_INTERNAL_AUDIT_REPORT.md and
/mnt/project-files/audits/m39_audit/test_m39_audit_probes.py) into asserting
regression tests, so a future change cannot silently reopen them.
"""
from __future__ import annotations

import io

import pytest

import uri_v1.memory.recorder as memory_recorder
import uri_v1.office.bootstrap as office_bootstrap
from uri_v1.office import request as req
from uri_v1.office.__main__ import run_repl
from uri_v1.office.acceptance_builder import build_acceptance
from uri_v1.office.bootstrap import UnsafeHarnessRefused, build_session
from uri_v1.office.flow import _is_consent
from tests.m39_office_support import answer_asks, request_names, OfficeEnv, SALES, make_workbook, script as script_text


def _fresh_verifier_registry(monkeypatch):
    """`build_session` freezes a process-global verifier registry once; other
    tests in this run may have already done so (via `OfficeEnv`, which resets
    it per-test through monkeypatch). Reset both of that mechanism's flags so
    a direct `build_session` call here is not order-dependent on what ran
    before it in the same process."""
    monkeypatch.setattr(memory_recorder, "_VERIFIERS", memory_recorder.MappingProxyType({}))
    monkeypatch.setattr(office_bootstrap, "_VERIFIERS_FROZEN", False)


def start(env, raw):
    parsed = req.parse(raw)
    assert parsed.ok, parsed
    turn_id, trace_id = env.turn()
    step = env.session.start(raw, session_id="session-r1", turn_id=turn_id, trace_id=trace_id, parsed=parsed)
    # Repair round 3 (R2-1): on the frozen M36 line a request naming both
    # files is confirmed one file per turn; answer those per-file questions
    # with the names the request used. Pinned in test_m39_repair3_regressions.
    return answer_asks(env, step, request_names(raw, parsed), session_id="session-r1")


def confirm(env, task_id, raw="yes, run it"):
    turn_id, trace_id = env.turn()
    return env.session.confirm_escalation(task_id, raw, session_id="session-r1", turn_id=turn_id, trace_id=trace_id)


def approve(env, task_id, raw="approve", **kw):
    turn_id, trace_id = env.turn()
    return env.session.approve_writeback(task_id, raw, session_id="session-r1", turn_id=turn_id, trace_id=trace_id, **kw)


# -- M39-1: a write-back refusal never claims "nothing written" when something was ----------------

def test_m39_1_stale_reference_refuses_before_any_write(tmp_path, monkeypatch):
    """A reference the task depends on (the workbook) going stale between
    verification and approval must refuse *before* any os.replace happens --
    not write the script and only then discover the workbook is stale."""
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    step = start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step
    original_bytes = (env.root / "report.py").read_bytes()

    (env.root / "sales.xlsx").write_bytes((env.root / "sales.xlsx").read_bytes() + b"\x00")

    refused = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
    assert refused.kind == "WRITEBACK_REFUSED", refused
    assert refused.reason == "WRITEBACK_SOURCE_NOT_CURRENT"
    assert refused.written == (), "refusal must not claim a clean 'nothing written' while lying"
    assert (env.root / "report.py").read_bytes() == original_bytes, "script must be untouched"


# -- M39-2: consent must be an exact affirmative reply, never a word-bag match ---------------------

@pytest.mark.parametrize("text,expected", [
    ("yes, run it", True),
    ("yes", True),
    ("approve", True),
    ("go ahead", True),
    ("do it", True),
    ("how long will it run?", False),
    ("ok wait, what exactly would you send?", False),
    ("go back, I want to rename the file first", False),
    ("make report.py run with sales.xlsx", False),  # a brand new request, not consent
    ("is it safe? yes or no", False),
    ("no", False),
    ("nope, not now", False),
])
def test_m39_2_consent_is_not_a_word_bag(text, expected):
    assert _is_consent(text) is expected


def test_m39_2_question_never_starts_harness(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="Amt"))  # abbreviation forces escalation
    step = start(env, "make report.py work with sales.xlsx")
    assert step.kind == "ESCALATION_PROPOSAL", step
    result = confirm(env, step.task_id, "how long will it run?")
    assert result.kind == "ESCALATION_DECLINED", result
    # M39-7: declining must clear the pending proposal so the session is not stuck.
    assert step.task_id not in env.session._escalation


def test_m39_2_consent_is_recorded_in_memory(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="Amt"))
    step = start(env, "make report.py work with sales.xlsx")
    before = set(env.log.load().records)
    confirm(env, step.task_id, "yes, run it")
    after = set(env.log.load().records)
    assert after - before, "consenting to escalation must add at least one durable Memory record"


# -- M39-3: filename parsing never silently binds part of a longer token ---------------------------

def test_m39_3_quoted_space_filename_binds_the_full_name(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    env.write("my report.py", script_text(column="amount"))
    step = start(env, 'make "my report.py" work with sales.xlsx')
    assert step.kind in ("AWAITING_APPROVAL", "NOTHING_TO_WRITE", "ESCALATION_PROPOSAL", "CLARIFY_MEMORY"), step
    # The bound script must be "my report.py", never the distinct "report.py".
    scan = env.sources.scan()
    my_report = next(l for l in scan.locators if l.relpath == "my report.py")
    report = next(l for l in scan.locators if l.relpath == "report.py")
    task_head = env.log.load().task(step.task_id)
    bound_source_id = next(r["source_id"] for r in task_head.payload["references"] if r["ref_key"] == "script")
    assert bound_source_id == my_report.source_id
    assert bound_source_id != report.source_id


@pytest.mark.parametrize("text", [
    "make report.py.bak work with sales.xlsx",
    "make data.xlsx.py work with sales.xlsx",
])
def test_m39_3_substring_of_longer_token_is_refused(text):
    parsed = req.parse(text)
    assert not parsed.ok
    assert parsed.reason == req.REASON_ROLE_AMBIGUOUS


# -- M39-4: approve_writeback trusts only the run_id it itself offered -----------------------------

def test_m39_4_approve_refuses_a_run_id_it_did_not_offer(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    step = start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step

    forged = "0" * 32
    result = approve(env, step.task_id, run_id=forged, relpaths=step.relpaths)
    assert result.kind == "ERROR"
    assert result.reason == "RUN_ID_NOT_OFFERED"
    # The legitimately offered run must still be approvable afterwards.
    ok = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
    assert ok.kind == "COMPLETED", ok


def test_m39_4_approve_refuses_a_run_with_safety_flags(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    original = script_text(column="amount")
    env.write("report.py", original)
    step = start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step

    # Simulate a run URI itself would flag (e.g. ORIGINAL_MODIFIED_DURING_VERIFICATION)
    # by appending a further RUN_RESULT with a safety flag onto the same run.
    run = env.store.get(step.run_id)
    flagged_result = dict(run["result"])
    flagged_result["uri_observations"] = dict(flagged_result["uri_observations"], safety_flags=["ORIGINAL_MODIFIED_DURING_VERIFICATION"])
    env.store.append(step.run_id, "RUN_RESULT", flagged_result)

    refused = approve(env, step.task_id, run_id=step.run_id, relpaths=step.relpaths)
    assert refused.kind == "WRITEBACK_REFUSED", refused
    assert refused.reason == "WRITEBACK_REFUSES_FLAGGED_RUN"
    assert (env.root / "report.py").read_bytes() == original.encode() or (env.root / "report.py").read_text() == original


# -- M39-7: the REPL's own approve path must actually complete -------------------------------------

def test_m39_7_repl_approve_completes_writeback(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount"))
    buf = io.StringIO()
    run_repl(env.session, env.user, in_stream=io.StringIO(
        "make report.py work with sales.xlsx\nreport.py\nsales.xlsx\napprove\n"), out=buf)
    # (repair round 3, R2-1: the two lines after the request answer the
    # per-file questions the frozen M36 line requires.)
    assert "[COMPLETED]" in buf.getvalue()
    assert "Written and task complete." in buf.getvalue()


def test_m39_7_repl_recovers_after_declined_escalation(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=True)
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text(column="Amt"))  # forces escalation
    buf = io.StringIO()
    run_repl(env.session, env.user, in_stream=io.StringIO(
        "make report.py work with sales.xlsx\nreport.py\nsales.xlsx\nno, don't run anything\nstatus\n"), out=buf)
    rendered = buf.getvalue()
    assert "[ESCALATION_DECLINED]" in rendered
    # After a decline, the session must not still be stuck offering the same
    # escalation forever -- confirm the internal state was actually cleared.
    assert not env.session._escalation


# -- M39-8: the not-yet-safe harness substrate needs an explicit ack, and never runs with a spend key

_USER = "00000000-0000-0000-0000-0000000000f1"


def test_m39_8_real_harness_wiring_refused_without_ack(tmp_path):
    (tmp_path / "docs").mkdir()
    with pytest.raises(UnsafeHarnessRefused):
        build_session(_USER, tmp_path / "data", authorized_root=tmp_path / "docs", with_harness=True)


def test_m39_8_real_harness_wiring_refused_with_api_key_set(tmp_path, monkeypatch):
    (tmp_path / "docs").mkdir()
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    with pytest.raises(UnsafeHarnessRefused):
        build_session(_USER, tmp_path / "data", authorized_root=tmp_path / "docs",
                     with_harness=True, acknowledge_unsafe_harness=True)


def test_m39_8_no_harness_by_default_is_unaffected(tmp_path, monkeypatch):
    _fresh_verifier_registry(monkeypatch)
    (tmp_path / "docs").mkdir()
    session = build_session(_USER, tmp_path / "data", authorized_root=tmp_path / "docs")
    assert session.adapter is None
    assert session.harness_runner is None


# -- M39-9: header detection follows source order, not ast.walk's breadth-first order ---------------

def test_m39_9_header_detection_follows_source_order_not_bfs():
    script = (
        'from openpyxl import Workbook\n'
        'out = Workbook(); o = out.active; o.title = "Summary"\n'
        'if True:\n'
        '    o.append(["Region", "Total"])\n'
        'o.append(["ALL", "n/a"])\n'
        'out.save("summary.xlsx")\n'
    ).encode()
    built = build_acceptance(script, "report.py")
    columns = [i for i in built.criteria.items if i["kind"] == "workbook_has_columns"]
    assert columns, built.criteria.items
    assert columns[0]["columns"] == ["Region", "Total"], columns
