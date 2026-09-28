"""M36 second-repair re-audit probes (410d1b8). Same-provider internal audit, 2026-09-28.
Each test asserts the SAFE expected behaviour; a failure is a finding.
Run from the repo root: python -m pytest <this file> --rootdir=. -q"""
import pytest
from uri_v1.memory.contracts import negated
from uri_v1.memory.context_package import build_context
from uri_v1.turn.rar_clarification_contract import BindingState
from tests.test_m36_memory_support import setup, retrieval, opened, intake
from tests.test_m36_memory_grounding import registered
from tests.test_m36_memory_verifier import bootstrap, claimed

# ---- Q1: negation forms that bind CONFIRMED end to end (apostrophes / unicode) ----
GLYPH_FORMS = [
    "don‛t use budget.xlsx",   # single high-reversed-9 quotation mark
    "don′t use budget.xlsx",   # prime
    "donʹt use budget.xlsx",   # modifier letter prime
    "donˈt use budget.xlsx",   # modifier letter vertical line
    "don t use budget.xlsx",        # apostrophe dropped to a space
    "don­t use budget.xlsx",   # soft hyphen
    "ＮＯＴ budget.xlsx",          # fullwidth NOT
    "n​ot budget.xlsx",        # zero-width space inside "not"
]
# Contractions the repair says are covered as "the full n't family"
CONTRACTION_FORMS = [
    "shan't use budget.xlsx", "mightn't use budget.xlsx", "oughtn't use budget.xlsx",
    "daren't use budget.xlsx",
]
# Everyday English negation/exclusion phrasings
PHRASE_FORMS = [
    "leave budget.xlsx out",         # split form of the listed phrase "leave out"
    "disregard budget.xlsx",
    "rule out budget.xlsx",
    "keep budget.xlsx out of this",
    "steer clear of budget.xlsx",
    "hold off on budget.xlsx",
    "w/o budget.xlsx",
    "sans budget.xlsx",
    "budget.xlsx is the wrong file",
    "budget.xlsx is off limits",
    "deselect budget.xlsx",
]
# Ambiguous: the file may legitimately be the target of the action, so these are
# recorded, not asserted (not counted as defects).
AMBIGUOUS_FORMS = ["forget budget.xlsx", "remove budget.xlsx", "ditch budget.xlsx"]

@pytest.mark.parametrize("raw", AMBIGUOUS_FORMS)
def test_q1_ambiguous_record(raw, tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    a = raw.index("budget.xlsx")
    result = retrieval(log, sources, raw, proposal="budget.xlsx", span=(a, a + 11))
    state, service, p = registered(sources, result)
    print("ambiguous:", raw, state)

@pytest.mark.parametrize("raw", GLYPH_FORMS + CONTRACTION_FORMS + PHRASE_FORMS)
@pytest.mark.parametrize("tight", [False, True])
def test_q1_negation_never_confirms(raw, tight, tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    a = raw.index("budget.xlsx"); span = (a, a + len("budget.xlsx")) if tight else None
    result = retrieval(log, sources, raw, proposal="budget.xlsx", span=span)
    state, service, p = registered(sources, result)
    assert state != BindingState.CONFIRMED, (raw, p.grounding)

def test_q1_explicit_id_negated(tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    sid = next(l.source_id for l in sources.scan().locators if l.relpath == "budget.xlsx")
    for raw in (f"don′t use {sid}", f"shan't use {sid}", f"disregard {sid}", f"leave {sid} out"):
        a = raw.index(sid)
        result = retrieval(log, sources, raw, proposal=sid, span=(a, a + len(sid)))
        state, service, p = registered(sources, result)
        assert state != BindingState.CONFIRMED, raw

# Double negatives and mixed cues must fail closed (clarify), never confirm.
@pytest.mark.parametrize("raw", ["don't not use budget.xlsx", "do not NOT use budget.xlsx",
                                 "it's not that I don't want budget.xlsx", "never not budget.xlsx"])
def test_q1_double_negative_fails_closed(raw, tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    a = raw.index("budget.xlsx")
    result = retrieval(log, sources, raw, proposal="budget.xlsx", span=(a, a + 11))
    state, service, p = registered(sources, result)
    assert state != BindingState.CONFIRMED, raw

# Controls: plain positive still confirms (proves probes are not trivially passing).
@pytest.mark.parametrize("raw", ["update budget.xlsx", "open budget.xlsx please", "summarize budget.xlsx"])
def test_q1_control_positive_confirms(raw, tmp_path):
    log, sources, rec, root = setup(tmp_path, ("budget.xlsx", "report.docx"))
    a = raw.index("budget.xlsx")
    result = retrieval(log, sources, raw, proposal="budget.xlsx", span=(a, a + 11))
    state, service, p = registered(sources, result)
    assert state == BindingState.CONFIRMED

# Usability record (not a safety failure): positives now forced to clarification.
@pytest.mark.parametrize("raw", ["drop budget.xlsx into the report", "stop by budget.xlsx",
                                 "update budget.xlsx but keep the format"])
def test_q1_usability_false_negation_record(raw):
    print("negated():", raw, negated(raw))

# ---- Q2: negated status transitions persisted as USER assertions ----
NEG_STATUS = [
    ("don t cancel this", "ABANDONED"),
    ("don′t cancel this", "ABANDONED"),
    ("shan't cancel this", "ABANDONED"),
    ("mightn't be done", "COMPLETED"),
    ("don‛t pause", "PAUSED"),
    ("oughtn't be marked failed", "FAILED"),
]
@pytest.mark.parametrize("text,status", NEG_STATUS)
def test_q2_negated_status_rejected(text, status, tmp_path):
    log, sources, rec, root = setup(tmp_path)
    task, head = opened(rec)
    try:
        persisted = rec.task_state(task, head.record_id, intake=intake(text), status=status).persisted
    except ValueError:
        persisted = False
    assert not persisted, text
    assert log.load().task(task).payload["status"] == "OPEN"

# ---- Q3: A-1 whole-task forget vs FAILED verdict ----
def _failed(tmp_path):
    bootstrap(); log, s, rec, root = setup(tmp_path)
    (root / "budget.xlsx").write_bytes(b"FAIL")
    task, head = opened(rec); src = s.fingerprint(s.scan().locators[0])
    return log, s, rec, root, task, src

def test_q3_block_holds_and_log_unchanged(tmp_path):
    log, s, rec, root, task, src = _failed(tmp_path)
    v = rec.invoke_verifier(claimed(rec, task, src).record_ids[0], "uri.verifier.m36_fixture", trace_id="a"*32, session_id="session")
    assert v.persisted
    before = {p.name: p.read_bytes() for p in log.path.glob("log-*.jsonl")}
    opening = log.load().openings[task]
    for targets in ((opening,), (opening, opening), (opening, claimed(rec, task, src).record_ids[0])):
        before = {p.name: p.read_bytes() for p in log.path.glob("log-*.jsonl")}
        r = rec.forget(targets, intake=intake("forget the task"))
        assert not r.persisted and r.reason == "INVALID_HIDE_TARGET", targets
        assert before == {p.name: p.read_bytes() for p in log.path.glob("log-*.jsonl")}
    idx = log.load()
    assert idx.task(task) is not None and opening not in idx.hidden

def test_q3_block_single_target_reason(tmp_path):
    log, s, rec, root, task, src = _failed(tmp_path)
    v = rec.invoke_verifier(claimed(rec, task, src).record_ids[0], "uri.verifier.m36_fixture", trace_id="a"*32, session_id="session")
    assert v.persisted
    r = rec.forget((log.load().openings[task],), intake=intake("forget the task"))
    assert not r.persisted

def test_q3_forget_before_verdict_then_failed_verdict_is_still_visible(tmp_path):
    """Ordering bypass: forget the task while its claim is still unverified, then the
    verifier records FAILED. The FAILED verdict must not end up hidden."""
    log, s, rec, root, task, src = _failed(tmp_path)
    claim = claimed(rec, task, src).record_ids[0]
    hid = rec.forget((log.load().openings[task],), intake=intake("forget the task"))
    try:
        v = rec.invoke_verifier(claim, "uri.verifier.m36_fixture", trace_id="a"*32, session_id="session")
        verdict_persisted = v.persisted
    except ValueError:
        verdict_persisted = False
    idx = log.load()
    failed_hidden = verdict_persisted and idx.task(task) is None
    pkg = build_context(idx, s, task).to_dict()
    print("forget persisted:", hid.persisted, "verdict persisted:", verdict_persisted,
          "task visible:", idx.task(task) is not None, "outcomes:", len(pkg["recent_outcomes"]))
    assert not failed_hidden, "FAILED verdict persisted against a forgotten task and is unreachable via build_context"

def test_q3_forget_before_claim_then_claim_and_failed_verdict(tmp_path):
    """Same bypass with the whole claim+verify cycle after forget (e.g. a background harness run)."""
    log, s, rec, root, task, src = _failed(tmp_path)
    hid = rec.forget((log.load().openings[task],), intake=intake("forget the task"))
    assert hid.persisted
    try:
        c = claimed(rec, task, src)
        v = rec.invoke_verifier(c.record_ids[0], "uri.verifier.m36_fixture", trace_id="a"*32, session_id="session") if c.persisted else None
        verdict_persisted = bool(v and v.persisted)
    except ValueError:
        verdict_persisted = False
    idx = log.load()
    assert not (verdict_persisted and idx.task(task) is None), "FAILED verdict recorded on a hidden task"
