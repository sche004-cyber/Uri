"""Q-O1: request + binding battery (M39 plan §5.1). >= 60 deterministic cases,
run twice, checking: wrong_binding_acted_on = 0, invented_source = 0, expected
outcome (BOUND / CLARIFY / UNSUPPORTED) = 100%, identical across runs.
"""
from __future__ import annotations

import json
from pathlib import Path
import uuid

import pytest

from uri_v1.memory.uri_adapter.envelope import URIIntake
from uri_v1.office import request as req
from uri_v1.office.binding import answer_ask, answer_filename_span, bind_all, with_asks
from uri_v1.reference_clarification.binding import BindingService
from tests.m39_office_support import OfficeEnv, make_workbook, script as script_text, SALES

GATE_PATH = Path(__file__).resolve().parents[1] / "fixtures" / "m39_office" / "threshold_gate.json"
INTAKE = URIIntake()


def _classify(env, raw):
    """BOUND: both roles bound from the request turn itself. ASK_THEN_BOUND /
    ASK_THEN_CLARIFY (repair round 3, R2-1): frozen M36 refused exact-name
    certainty in the two-filename turn, M39 asked for each file separately,
    and the answer turn (just the name the request used) then bound, or
    opened a clarification. CLARIFY: a clarification with no per-file ask."""
    parsed = req.parse(raw)
    if not parsed.ok:
        return "UNSUPPORTED", parsed
    service = BindingService()
    intake = INTAKE.capture(env.user, "session-q1", uuid.uuid4().hex, uuid.uuid4().hex, raw, spans=parsed.spans)
    bindings = with_asks(bind_all(env.retriever, env.sources, service, intake, task_id=None))
    if all(rb.state == "CONFIRMED" for rb in bindings.values()):
        return "BOUND", bindings
    if not any(rb.ask for rb in bindings.values()):
        return "CLARIFY", bindings
    for role, rb in list(bindings.items()):
        if not rb.ask:
            continue
        a, b = parsed.spans[role]
        answer = raw[a:b]
        span = answer_filename_span(answer, role)
        assert span is not None, (role, answer)
        answer_intake = INTAKE.capture(env.user, "session-q1", uuid.uuid4().hex, uuid.uuid4().hex, answer,
                                       spans={role: span})
        bindings[role] = answer_ask(env.retriever, env.sources, service, rb, answer_intake)
    if all(rb.state == "CONFIRMED" for rb in bindings.values()):
        return "ASK_THEN_BOUND", bindings
    return "ASK_THEN_CLARIFY", bindings


def _known_source_ids(env):
    return {l.source_id for l in env.sources.scan().locators}


# -- fixture setups (functions of env -> None) ------------------------------------------------

def _basic(env):
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text())


def _same_stem(env):
    make_workbook(env.root / "report.xlsx", SALES)
    env.write("report.py", script_text(workbook="report.xlsx"))


def _collision(env):
    make_workbook(env.root / "sales.xlsx", SALES)
    (env.root / "old").mkdir(parents=True, exist_ok=True)
    make_workbook(env.root / "old" / "sales.xlsx", SALES)
    env.write("report.py", script_text())


def _negation_setup(env):
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("new_report.py", script_text())
    env.write("old_report.py", script_text())


def _ambiguous_py_setup(env):
    make_workbook(env.root / "sales.xlsx", SALES)
    env.write("report.py", script_text())
    env.write("backup_report.py", script_text())


def _moved_setup(env):
    make_workbook(env.root / "sales.xlsx", SALES)
    # report.py deliberately absent (moved/deleted)


# -- generated cases -----------------------------------------------------------------------------

_BOUND_FILENAME = [
    "make report.py work with sales.xlsx",
    "make report.py work with the sales.xlsx",
    "please make report.py work with sales.xlsx",
    "can you make report.py work with sales.xlsx",
    "get report.py to work with sales.xlsx",
    "fix report.py to run with sales.xlsx",
    "fix report.py so it runs with sales.xlsx",
    "have report.py work with sales.xlsx",
    "make sales.xlsx work with report.py",
    "before anything else, make report.py work with sales.xlsx",
    "make report.py run with sales.xlsx",
    "get report.py running with sales.xlsx",
    "URI, make report.py work with sales.xlsx",
    "could you get report.py to work with sales.xlsx",
]

_CLARIFY_PHRASE = [
    "make this script work with this spreadsheet",
    "make this script work with the workbook",
    "get this script to work with this workbook",
    "fix the script to run with the spreadsheet",
    "make my script work with my spreadsheet",
    "have this script work with the sheet",
    "make this script run with the workbook",
    "please make this script work with this workbook",
    "can you get this script to run with this spreadsheet",
    "make the script work with the spreadsheet",
]

_SAME_STEM = [
    "make report.py work with report.xlsx",
    "get report.py to work with report.xlsx",
    "fix report.py to run with report.xlsx",
    "make report.py run with report.xlsx",
]

_TYPOS_UNSUPPORTED = [
    "mak this script work with this spreadsheet",
    "make this scritp work with this spreadsheet",
    "make this script wrk with this spreadsheet",
    "make this script work wth this spreadsheet",
    "make this scrpt work with the workbook",
    "makee report.py work with sales.xlsx",
]

_UNSUPPORTED_INTENT = [
    "summarize this spreadsheet",
    "what does this script do",
    "open report.py",
    "delete sales.xlsx",
    "email me the workbook",
    "clean up this script",
    "review the spreadsheet with me",
    "tell me about this script and this spreadsheet",
]

_COLLISION_CLARIFY = [
    "make report.py work with sales.xlsx",
    "get report.py to work with sales.xlsx",
    "fix report.py to run with sales.xlsx",
    "make report.py run with sales.xlsx",
    "please make report.py work with sales.xlsx",
]

_NEGATION_CLARIFY = [
    "make this script work with sales.xlsx, don't use the old version",
    "get this script to work with sales.xlsx, not the old one",
    "fix this script to run with sales.xlsx, don't touch anything else",
    "make this script work with sales.xlsx, never mind the backup",
]

_AMBIGUOUS_ROLE_UNSUPPORTED = [
    "make report.py or backup_report.py work with sales.xlsx",
    "make report.py and backup_report.py work with sales.xlsx",
    "get report.py or backup_report.py to work with sales.xlsx",
    "fix report.py or backup_report.py to run with sales.xlsx",
]

_MOVED_CLARIFY = [
    "make report.py work with sales.xlsx",
    "get report.py to work with sales.xlsx",
    "fix report.py to run with sales.xlsx",
    "have report.py work with sales.xlsx",
    "make report.py run with sales.xlsx",
]

# Repair round 3 (re-audit R2-1): on the frozen M36 line a request that names
# both files cannot bind either one in its own turn (frozen
# `affirmative_around`: each role's context holds the other file name), so
# every two-filename case is asked per file first. The labels below were
# "BOUND" / "CLARIFY" on the pre-freeze base. Per-file answers is the User's
# chosen design (2026-09-29; implementation report §11), so these labels are
# the intended behaviour.
CASES = (
    [(r, _basic, "ASK_THEN_BOUND") for r in _BOUND_FILENAME]
    # Sole-candidate deictic phrases ("this script") are HEURISTIC, not
    # CERTAINTY authority (uri_v1/reference_clarification/authority.py
    # classify_authority): even with one matching file, they open a
    # CONFIRM_ONE clarification round rather than binding outright.
    + [(r, _basic, "CLARIFY") for r in _CLARIFY_PHRASE]
    + [(r, _same_stem, "ASK_THEN_BOUND") for r in _SAME_STEM]
    + [(r, _basic, "UNSUPPORTED") for r in _TYPOS_UNSUPPORTED]
    + [(r, _basic, "UNSUPPORTED") for r in _UNSUPPORTED_INTENT]
    + [(r, _collision, "ASK_THEN_CLARIFY") for r in _COLLISION_CLARIFY]
    + [(r, _negation_setup, "CLARIFY") for r in _NEGATION_CLARIFY]
    + [(r, _ambiguous_py_setup, "UNSUPPORTED") for r in _AMBIGUOUS_ROLE_UNSUPPORTED]
    + [(r, _moved_setup, "ASK_THEN_CLARIFY") for r in _MOVED_CLARIFY]
)

assert len(CASES) >= 60, f"Q-O1 requires >= 60 cases, have {len(CASES)}"


def test_gate_file_matches_declared_battery_size():
    gate = json.loads(GATE_PATH.read_bytes())
    assert gate["q_o1"]["min_cases"] <= len(CASES)


@pytest.mark.parametrize("raw,setup,expected", CASES, ids=[f"{i:03d}-{e}" for i, (_, _, e) in enumerate(CASES)])
def test_q_o1_request_and_binding(raw, setup, expected, tmp_path, monkeypatch):
    outcomes = []
    for run in range(2):
        env = OfficeEnv(tmp_path / f"run{run}", monkeypatch, with_harness=False)
        setup(env)
        known = _known_source_ids(env)
        outcome, detail = _classify(env, raw)
        outcomes.append(outcome)
        assert outcome == expected, f"{raw!r}: expected {expected}, got {outcome} ({detail})"
        if outcome == "ASK_THEN_CLARIFY":
            # The per-file answer led to a real Memory clarification round
            # (two files share the name, or none matches) -- never a guess
            # and never a dead end.
            assert any(rb.contract_id and not rb.ask for rb in detail.values()), detail
        if outcome in ("BOUND", "ASK_THEN_BOUND"):
            for rb in detail.values():
                assert rb.bound is not None
                # invented_source: every bound source_id must be a real, scanned source.
                assert rb.bound.source.source_id in known
            # wrong_binding_acted_on: script role must bind a .py, workbook role a spreadsheet.
            assert detail["script"].bound.source.relpath.endswith(".py")
            assert detail["workbook"].bound.source.relpath.split(".")[-1] in ("xlsx", "xlsm")
    assert outcomes[0] == outcomes[1], f"{raw!r}: non-deterministic across runs: {outcomes}"
