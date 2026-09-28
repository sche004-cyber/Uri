"""Regression tests for the M36 repair round 4 findings (re-audit of c179e42):
P-1 phrasal exclusions built only from allowed words, and P-2 non-declaration
status transitions. Promoted from the re-audit thread's 22 probes
(audits/m36_reaudit2/test_reaudit3_probes.py)."""
import pytest
from uri_v1.turn.rar_clarification_contract import BindingState
from tests.test_m36_memory_support import setup, retrieval, opened, intake
from tests.test_m36_memory_grounding import registered
from tests.test_m36_memory_verifier import bootstrap, claimed


# P-1: phrasal verbs built only from allowlisted words that mean "drop / be done
# with this file" must never bind CONFIRMED.
PHRASAL_EXCLUSIONS = [
    "let go of budget.xlsx", "give up on budget.xlsx", "give budget.xlsx up", "let budget.xlsx go",
    "I'm through with budget.xlsx", "that's it for budget.xlsx", "we're over budget.xlsx",
]


@pytest.mark.parametrize("raw", PHRASAL_EXCLUSIONS)
@pytest.mark.parametrize("tight", [False, True])
def test_repair4_phrasal_exclusion_never_confirms(raw, tight, tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    a = raw.index("budget.xlsx")
    span = (a, a + 11) if tight else None
    result = retrieval(log, sources, raw, proposal="budget.xlsx", span=span)
    state, service, p = registered(sources, result)
    assert state != BindingState.CONFIRMED, raw


# P-2: non-declarations must never persist as USER status transitions.
NON_DECLARATIONS = [
    ("done for now", "COMPLETED"),                 # a pause, not a completion
    ("done for a moment", "COMPLETED"),
    ("can you complete the task", "COMPLETED"),     # a request for work, no '?'
    ("please complete this task", "COMPLETED"),
    ("I can pause it for a bit then resume", "PAUSED"),
    # Focused re-check fix: bare "complete" outside "mark as"/"it's" framing is a
    # request, not a declaration, whether or not it carries a lead request word.
    ("just complete it", "COMPLETED"),
    ("complete the task", "COMPLETED"),
    ("go ahead and complete the task", "COMPLETED"),
    ("let's complete this task", "COMPLETED"),
]


@pytest.mark.parametrize("text,status", NON_DECLARATIONS)
def test_repair4_non_declaration_not_transition(text, status, tmp_path):
    log, sources, rec, root = setup(tmp_path)
    task, head = opened(rec)
    try:
        persisted = rec.task_state(task, head.record_id, intake=intake(text), status=status).persisted
    except ValueError:
        persisted = False
    assert not persisted, text
    assert log.load().task(task).payload["status"] == "OPEN"


# Ordering fix (verified holding under this repair too): forget the claim alone,
# then the task, then invoke the verifier -- must not land a FAILED verdict hidden.
def test_repair4_forget_claim_then_task_then_verify(tmp_path):
    bootstrap(); log, s, rec, root = setup(tmp_path)
    (root / "budget.xlsx").write_bytes(b"FAIL")
    task, head = opened(rec); src = s.fingerprint(s.scan().locators[0])
    claim = claimed(rec, task, src).record_ids[0]
    assert rec.forget((log.load().openings[task],), intake=intake("forget the task")).persisted is False
    assert rec.forget((claim,), intake=intake("forget that claim")).persisted
    hid = rec.forget((log.load().openings[task],), intake=intake("forget the task")).persisted
    try:
        v = rec.invoke_verifier(claim, "uri.verifier.m36_fixture", trace_id="a"*32, session_id="session").persisted
    except ValueError:
        v = False
    idx = log.load()
    assert not (v and idx.task(task) is None)


def test_repair4_verify_hidden_claim_while_task_visible_surfaces_failed(tmp_path):
    from uri_v1.memory.context_package import build_context
    bootstrap(); log, s, rec, root = setup(tmp_path)
    (root / "budget.xlsx").write_bytes(b"FAIL")
    task, head = opened(rec); src = s.fingerprint(s.scan().locators[0])
    claim = claimed(rec, task, src).record_ids[0]
    assert rec.forget((claim,), intake=intake("forget that claim")).persisted
    v = rec.invoke_verifier(claim, "uri.verifier.m36_fixture", trace_id="a"*32, session_id="session")
    pkg = build_context(log.load(), s, task).to_dict()
    if v.persisted:
        assert any(o["verification_status"] == "FAILED" for o in pkg["recent_outcomes"])
        assert rec.forget((log.load().openings[task],), intake=intake("forget the task")).persisted is False


def test_repair4_hidden_task_rejects_new_writes(tmp_path):
    log, s, rec, root = setup(tmp_path)
    task, head = opened(rec)
    assert rec.forget((log.load().openings[task],), intake=intake("forget the task")).persisted
    src = s.fingerprint(s.scan().locators[0])
    with pytest.raises(ValueError, match="TASK_HIDDEN"):
        r = claimed(rec, task, src)
        assert not r.persisted; raise ValueError(r.reason)


# Controls: the repair round 3 positive examples must still confirm / persist,
# proving the round 4 tightening did not overreach.
AFFIRMATIVE_CONTROLS = [
    "update budget.xlsx", "please open budget.xlsx", "can you summarize budget.xlsx for me", "let's review budget.xlsx",
    "I'd like to check budget.xlsx", "open the budget.xlsx file please", "use budget.xlsx", '"budget.xlsx"',
    "Update budget.xlsx now!", "could you fix budget.xlsx?", "I'll edit budget.xlsx", "ok, open budget.xlsx again",
]


@pytest.mark.parametrize("raw", AFFIRMATIVE_CONTROLS)
def test_repair4_plain_affirmative_requests_still_confirm(raw, tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    a = raw.index("budget.xlsx")
    result = retrieval(log, sources, raw, proposal="budget.xlsx", span=(a, a + 11))
    state, service, p = registered(sources, result)
    assert state == BindingState.CONFIRMED, raw


STATUS_DECLARATION_CONTROLS = [
    ("done", "COMPLETED"), ("it's done", "COMPLETED"), ("we are done now", "COMPLETED"),
    ("mark this task as complete", "COMPLETED"), ("please cancel this task", "ABANDONED"),
    ("pause for a moment", "PAUSED"), ("ok, the task failed", "FAILED"), ("can you cancel this task", "ABANDONED"),
    # "complete" declares completion only in "mark as"/"it's"/"is" framing.
    ("it's complete", "COMPLETED"), ("the task is complete", "COMPLETED"), ("mark as complete", "COMPLETED"),
]


@pytest.mark.parametrize("text,status", STATUS_DECLARATION_CONTROLS)
def test_repair4_plain_status_declarations_still_accepted(text, status, tmp_path):
    log, sources, rec, root = setup(tmp_path)
    task, head = opened(rec)
    assert rec.task_state(task, head.record_id, intake=intake(text), status=status).persisted, text
    assert log.load().task(task).payload["status"] == status
