"""M39 repair round 3: regressions for the re-audit of 7bcbbee on the frozen
M36-M38 line (audits/m39_reaudit2, report M39_REPAIR2_REAUDIT_REPORT.md).

- R2-2 (High): approved write-back completes through frozen M36's runtime
  VERIFIED_COMPLETE path, never a synthesized user turn; any failure after the
  originals were written is a typed refusal carrying and recording `written`.
- R2-1 (High): a two-filename request cannot bind in one turn on the frozen
  line, so M39 asks for each file instead of dead-ending (per-file answers:
  the User's chosen design, 2026-09-29).
- R2-3 (Medium): unquoted names with an unsafe prefix or path never bind the
  bare name.
- R2-4 (Medium): the benchmark scores what write-back actually returns and
  exits non-zero when its dry-run gate fails.
- R2-5 (Low): stale M39 expectations re-pointed at the frozen line (covered in
  test_m39_repair2_regressions.py and test_m39_boundaries.py).
"""
from __future__ import annotations

import io
from pathlib import Path

import pytest

from uri_v1.memory.contracts import Provenance as P, RecordKind as K
from uri_v1.office import request as req
from uri_v1.office import writeback as wb_module
from uri_v1.office.__main__ import run_repl
from uri_v1.office.view import render
from tests.m39_office_support import OfficeEnv, SALES, answer_asks, make_workbook, request_names, script as script_text

ROOT = Path(__file__).resolve().parents[1]
SID = "session-r3"


def raw_start(env, raw):
    parsed = req.parse(raw)
    assert parsed.ok, parsed
    turn_id, trace_id = env.turn()
    return env.session.start(raw, session_id=SID, turn_id=turn_id, trace_id=trace_id, parsed=parsed)


def answer(env, step, role, text):
    turn_id, trace_id = env.turn()
    return env.session.answer(step.task_id, text, session_id=SID, turn_id=turn_id, trace_id=trace_id,
                              round_id=step.roles[role].contract_id)


def confirmed_start(env, raw):
    parsed = req.parse(raw)
    return answer_asks(env, raw_start(env, raw), request_names(raw, parsed), session_id=SID)


def approve(env, step, raw="approve"):
    turn_id, trace_id = env.turn()
    return env.session.approve_writeback(step.task_id, raw, run_id=step.run_id, relpaths=step.relpaths,
                                         session_id=SID, turn_id=turn_id, trace_id=trace_id)


def local_fixable(env):
    make_workbook(env.root / "sales.xlsx", SALES)
    original = script_text(column="amount")  # case-only mismatch Edge fixes locally
    env.write("report.py", original)
    return original


def task_head(env, task_id):
    return env.log.load().task(task_id)



# -- R2-2: governed completion, and honest failure after a write ---------------------------------

def test_r2_2_writeback_completes_through_runtime_verified_complete(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step
    done = approve(env, step)
    assert done.kind == "COMPLETED", done
    assert '"Amount"' in (env.root / "report.py").read_text()

    head = task_head(env, step.task_id)
    assert head.payload["status"] == "COMPLETED"
    # Runtime completion, not a user declaration: URI_RECORDED provenance...
    assert head.provenance == P.URI_RECORDED
    # ...linked to the run's own VERIFIED verdict, whose inputs cover the
    # task's (pre-write) references, as frozen M36 requires.
    verdict = env.log.load().records[head.payload["last_outcome_record_id"]]
    assert verdict.provenance == P.VERIFIER_RESULT
    assert str(verdict.payload["verification_status"]) == "VERIFIED"
    assert verdict.payload["attempt_id"] == step.run_id
    # The write-back's own independent verdict is named in the checkpoint text.
    assert "write-back applied and verified" in head.payload["next_step"]["text"]
    # No record anywhere carries words the user never typed.
    for record in env.log.load().records.values():
        assert "write-back complete" not in str(record.payload.get("raw_text", ""))


def test_r2_2_writeback_module_no_longer_synthesizes_user_turns():
    text = (ROOT / "uri_v1" / "office" / "writeback.py").read_text(encoding="utf-8")
    assert "URIIntake" not in text
    assert '"write-back complete"' not in text
    assert '_runtime_observation(approval_intake, "VERIFIED_COMPLETE")' in text


def test_r2_2_failure_after_write_is_refused_and_recorded_failed(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    original = local_fixable(env)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step

    def boom(*a, **kw):
        raise ValueError("SIMULATED_POST_WRITE_FAILURE")
    monkeypatch.setattr(env.recorder, "invoke_verifier", boom)

    refused = approve(env, step)  # must not raise
    assert refused.kind == "WRITEBACK_REFUSED", refused
    assert "SIMULATED_POST_WRITE_FAILURE" in refused.reason
    assert [w["relpath"] for w in refused.written] == ["report.py"]
    assert (env.root / "report.py").read_text() != original  # the write really happened...
    assert refused.partial_record == "FAILED"                  # ...and Memory says so
    head = task_head(env, step.task_id)
    assert head.payload["status"] == "FAILED"
    assert "report.py" in head.payload["next_step"]["text"]
    assert head.provenance == P.URI_RECORDED
    rendered = render(refused)
    assert "already written" in rendered and "FAILED in Memory" in rendered


def test_r2_2_failure_after_write_when_memory_also_refuses_is_still_a_typed_refusal(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step

    def boom(*a, **kw):
        raise ValueError("SIMULATED_MEMORY_FAILURE")
    monkeypatch.setattr(env.recorder, "invoke_verifier", boom)
    monkeypatch.setattr(env.recorder, "task_state", boom)

    refused = approve(env, step)
    assert refused.kind == "WRITEBACK_REFUSED", refused
    assert [w["relpath"] for w in refused.written] == ["report.py"]
    assert refused.partial_record.startswith("NOT_RECORDED")
    assert "could not record" in render(refused)


def test_r2_2_completion_refused_by_memory_is_recorded_not_raised(tmp_path, monkeypatch):
    """The exact audit scenario (E1): M36 refuses the completing transition
    after the write. Simulated by making the runtime completion fail."""
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    real = wb_module._runtime_observation

    def refuse_complete(intake, action):
        if action == "VERIFIED_COMPLETE":
            raise ValueError("EXPLICIT_USER_TRANSITION_REQUIRED")
        return real(intake, action)
    monkeypatch.setattr(wb_module, "_runtime_observation", refuse_complete)

    refused = approve(env, step)
    assert refused.kind == "WRITEBACK_REFUSED"
    assert refused.written and refused.partial_record == "FAILED"
    assert task_head(env, step.task_id).payload["status"] == "FAILED"


# -- R2-1: two-filename requests ask per file instead of dead-ending --------------------------------

def test_r2_1_two_filename_request_asks_for_each_file(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = raw_start(env, "make report.py work with sales.xlsx")
    assert step.kind == "CLARIFY", step
    for role in ("script", "workbook"):
        rb = step.roles[role]
        assert rb.ask and rb.contract_id and rb.state == "PENDING" and rb.bound is None
        assert rb.reason == "NON_AFFIRMATIVE_CONTEXT"
    assert task_head(env, step.task_id).payload["references"] == ()
    rendered = render(step)
    assert "which file is the script" in rendered and "which file is the workbook" in rendered

    step = answer(env, step, "script", "report.py")
    assert step.kind == "CLARIFY" and step.roles["script"].state == "CONFIRMED"
    assert step.roles["script"].bound.source.relpath == "report.py"
    step = answer(env, step, "workbook", "sales.xlsx")
    assert step.kind == "AWAITING_APPROVAL", step
    assert approve(env, step).kind == "COMPLETED"


@pytest.mark.parametrize("reply,reason", [
    ("yes", "ANSWER_NOT_A_FILE_NAME"),
    ("sales.xlsx", "ANSWER_NOT_A_FILE_NAME"),              # wrong type for the script role
    ("report.py, not old_report.py", "EXPRESSION_GROUNDING_UNESTABLISHED"),  # negated: M36 refuses to ground it
    ("report.py and sales.xlsx", "ANSWER_NOT_A_FILE_NAME"),
])
def test_r2_1_bad_answer_is_asked_again_never_guessed(tmp_path, monkeypatch, reply, reason):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = raw_start(env, "make report.py work with sales.xlsx")
    again = answer(env, step, "script", reply)
    assert again.kind == "CLARIFY"
    rb = again.roles["script"]
    assert rb.ask and rb.state == "PENDING" and rb.bound is None and rb.reason == reason
    assert rb.contract_id != step.roles["script"].contract_id


@pytest.mark.parametrize("reply", ["../report.py", "2024 report.py", r"C:\old\report.py", "use report.py"])
def test_r2_1_answer_with_prefix_or_path_never_binds_the_bare_name(tmp_path, monkeypatch, reply):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = raw_start(env, "make report.py work with sales.xlsx")
    after = answer(env, step, "script", reply)
    assert after.kind == "CLARIFY"
    assert after.roles["script"].state != "CONFIRMED"
    assert after.roles["script"].bound is None


def test_r2_1_answer_with_a_name_collision_opens_a_memory_round(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    (env.root / "old").mkdir()
    make_workbook(env.root / "old" / "sales.xlsx", SALES)
    step = confirmed_start(env, "make report.py work with sales.xlsx")
    assert step.kind == "CLARIFY"
    wb = step.roles["workbook"]
    assert wb.state == "PENDING" and wb.contract_id and not wb.ask and wb.bound is None


def test_r2_1_one_filename_plus_phrase_still_binds_without_asking(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    step = raw_start(env, "make report.py work with the spreadsheet")
    assert not any(rb.ask for rb in step.roles.values())


def test_r2_1_repl_answers_per_file_questions_and_completes(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    buf = io.StringIO()
    run_repl(env.session, env.user, in_stream=io.StringIO(
        "make report.py work with sales.xlsx\nreport.py\nsales.xlsx\napprove\n"), out=buf)
    out = buf.getvalue()
    assert "which file is the script" in out
    assert "[AWAITING_APPROVAL]" in out
    assert "[COMPLETED]" in out


def test_r2_1_repl_new_request_while_a_question_is_pending_starts_fresh(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    buf = io.StringIO()
    run_repl(env.session, env.user, in_stream=io.StringIO(
        "make report.py work with sales.xlsx\nmake report.py work with the spreadsheet\n"), out=buf)
    assert len([r for r in env.session.status()]) == 2


# -- R2-3: unquoted prefixes and paths never bind the bare name --------------------------------------

@pytest.mark.parametrize("text,role", [
    ("make 2024 report.py work with sales.xlsx", "script"),
    ("make report.py work with Q1 sales.xlsx", "workbook"),
    ("make 报告 report.py work with sales.xlsx", "script"),
    ("make report.py work with 2024-Q1 sales.xlsx", "workbook"),
    (r"make C:\old\report.py work with sales.xlsx", "script"),
    (r"make ..\report.py work with sales.xlsx", "script"),
    ("make ../report.py work with sales.xlsx", "script"),
    ("make report.py work with sales.xlsx~", "workbook"),
])
def test_r2_3_unsafe_prefix_or_path_is_ambiguous(text, role):
    parsed = req.parse(text)
    assert not parsed.ok
    assert (parsed.reason, parsed.role) == (req.REASON_ROLE_AMBIGUOUS, role)


@pytest.mark.parametrize("text", [
    "make report.py work with sales.xlsx",
    "make ./report.py work with sales.xlsx.",
    "Please fix report.py. It should work with sales.xlsx",
    "make report.py work with sales.xlsx...",
    "before anything else, make report.py work with sales.xlsx",
    "make report.py work with (sales.xlsx)",
    "make sub/report.py work with sales.xlsx",
    'make report.py work with "Q1 sales.xlsx"',
])
def test_r2_3_plain_and_quoted_names_still_parse(text):
    assert req.parse(text).ok, text


def test_r2_3_q1_workbook_end_to_end_never_binds_the_other_file(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    make_workbook(env.root / "sales.xlsx", SALES)
    make_workbook(env.root / "Q1 sales.xlsx", SALES)
    env.write("report.py", script_text(column="amount", workbook="Q1 sales.xlsx"))
    assert not req.parse("make report.py work with Q1 sales.xlsx").ok
    step = confirmed_start(env, 'make report.py work with "Q1 sales.xlsx"')
    assert step.kind in ("AWAITING_APPROVAL", "NOTHING_TO_WRITE", "ESCALATION_PROPOSAL"), step
    by_id = {l.source_id: l.relpath for l in env.sources.scan().locators}
    bound = {by_id[r["source_id"]] for r in task_head(env, step.task_id).payload["references"]}
    assert bound == {"report.py", "Q1 sales.xlsx"}


# -- R2-4: the benchmark scores returned files and fails loudly ---------------------------------------

def _bench():
    import importlib.util
    spec = importlib.util.spec_from_file_location("m39_office_benchmark", ROOT / "scripts" / "m39_office_benchmark.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_r2_4_benchmark_confirms_in_envelope_tasks_by_running_the_returned_script():
    results = _bench().run(dry_run=True, out_path=None)
    summary = results["summary"]
    assert summary["dry_run_gate"] == "PASS", summary["dry_run_gate_failures"]
    assert summary["hard_gates"] == {"oracle_false_verified": 0, "originals_modified_without_approval": 0,
                                     "wrong_file_binding_acted_on": 0}
    for name in ("task_01", "task_02", "task_03", "task_04"):
        b = results["tasks"][name]["arm_b"]
        assert b["completed"] and b["oracle_match"] is True and b["memory_status"] == "COMPLETED", (name, b)
        assert b["oracle_value"] is not None
    # no_success tasks are never counted as confirmed successes.
    for name in ("task_11", "task_12"):
        b = results["tasks"][name]["arm_b"]
        assert b["oracle_match"] is None and not b["completed"] and b["correct"], (name, b)


def test_r2_4_benchmark_exits_non_zero_when_the_gate_fails(monkeypatch, capsys):
    bench = _bench()
    real = bench._run_arm_b_dry

    def broken(task_dir, scratch):
        result = real(task_dir, scratch)
        if task_dir.name == "task_01":
            result.update(completed=False, correct=False, oracle_match=None, route="CLARIFY")
        return result
    monkeypatch.setattr(bench, "_run_arm_b_dry", broken)
    assert bench.main(["--dry-run"]) == 1
    assert "task_01" in capsys.readouterr().err


def test_r2_3_session_start_with_a_refused_parse_is_typed_not_a_crash(tmp_path, monkeypatch):
    env = OfficeEnv(tmp_path, monkeypatch, with_harness=False)
    local_fixable(env)
    parsed = req.parse("make report.py work with Q1 sales.xlsx")
    turn_id, trace_id = env.turn()
    step = env.session.start("make report.py work with Q1 sales.xlsx", session_id=SID, turn_id=turn_id,
                             trace_id=trace_id, parsed=parsed)
    assert (step.kind, step.reason, step.role) == ("UNSUPPORTED", req.REASON_ROLE_AMBIGUOUS, "workbook")
    assert env.session.status() == ()
