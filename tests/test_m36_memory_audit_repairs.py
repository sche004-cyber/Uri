"""Regression tests for the M36 independent closing-audit findings F-1..F-6."""
from types import MappingProxyType
import pytest
import uri_v1.memory.recorder as module
from uri_v1.memory.recorder import _runtime_observation
from uri_v1.memory.contracts import RecordKind, negated
from uri_v1.memory.context_package import build_context
from uri_v1.memory.index import VerifierRegistryMismatch
from uri_v1.memory.log import MemoryLog
from uri_v1.memory.retrieval import Retriever
from uri_v1.memory.uri_adapter.envelope import MemoryAdapter
from uri_v1.turn.rar_clarification_contract import BindingState
from tests.test_m36_memory_support import setup,retrieval,opened,intake,bind,USER
from tests.test_m36_memory_grounding import registered
from tests.test_m36_memory_verifier import bootstrap,claimed,fixture_verifier


@pytest.mark.parametrize("raw,span",[
    ("don't use budget.xlsx",None),
    ("dont use budget.xlsx",None),
    ("never budget.xlsx",None),
    ("skip budget.xlsx",None),
    ("anything other than budget.xlsx",None),
    ("instead of budget.xlsx use the report",None),
    ("rather than budget.xlsx",None),
    ("not budget.xlsx",(4,15)),  # span cropped past the cue
    # Antigravity-audited M36 repair 70e6065 (a87e158), ported forward for coverage:
    ("I wouldn't use budget.xlsx",None),
    ("we haven't approved budget.xlsx",None),
    ("it wasn't budget.xlsx",None),
    ("don\u02bct use budget.xlsx",None),  # U+02BC modifier letter apostrophe
    ("don\u2018t use budget.xlsx",None),  # U+2018 left single quote
    ("don\uff07t use budget.xlsx",None),  # U+FF07 fullwidth apostrophe
    ("ignore budget.xlsx",None),
    ("leave out budget.xlsx",None),
    ("neither budget.xlsx nor notes.txt",None),
    ("anything besides budget.xlsx",None),
    ("aside from budget.xlsx use report.docx",None),
    ("except for budget.xlsx",None),
])
def test_f1_negation_anywhere_in_turn_never_confirms(raw,span,tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    result=retrieval(log,sources,raw,proposal="budget.xlsx",span=span)
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED
    assert p.degraded=="EXPRESSION_GROUNDING_UNESTABLISHED" and p.grounding.status=="NEGATED_REFERENCE"


@pytest.mark.parametrize("raw",["update budget.xlsx","budget.xlsx","open notes.md","update the budget.xlsx now"])
def test_f1_positive_literals_are_not_negations(raw):
    assert not negated(raw)


@pytest.mark.parametrize("raw",[
    "don‘t use budget.xlsx",   # left single quotation mark
    "donʼt use budget.xlsx",  # modifier letter apostrophe
    "don`t use budget.xlsx",       # backtick
    "don´t use budget.xlsx",  # acute accent
    "do n't use budget.xlsx",
    "DON'T use budget.xlsx",
    "anything but budget.xlsx",
    "ignore budget.xlsx",
    "leave out budget.xlsx",
    "neither budget.xlsx nor report.docx",
    "nothing from budget.xlsx",
    "none of budget.xlsx",
    "aside from budget.xlsx",
    "stop using budget.xlsx",
    "haven't touched budget.xlsx",
    "wouldn't use budget.xlsx",
    "mustn't use budget.xlsx",
    "please exclude budget.xlsx",
    "without budget.xlsx",
    "everything except budget.xlsx",
    "use report.docx instead of budget.xlsx",
])
def test_r1_r2_negation_forms_never_confirm(raw,tmp_path):
    """Re-audit R-1/R-2: apostrophe-glyph variants, the split "do n't" form,
    and everyday negation phrasings beyond the original 8-word cue set."""
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    a=raw.index("budget.xlsx")
    result=retrieval(log,sources,raw,proposal="budget.xlsx",span=(a,a+len("budget.xlsx")))
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED, raw


def test_r1_explicit_id_negation_forms_never_confirm(tmp_path):
    """Re-audit R-1: negation of an explicit source_id, not just a filename."""
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    sid=next(l.source_id for l in sources.scan().locators if l.relpath=="budget.xlsx")
    for raw in (f"don't use {sid}", f"anything but {sid}"):
        a=raw.index(sid)
        result=retrieval(log,sources,raw,proposal=sid,span=(a,a+len(sid)))
        state,service,p=registered(sources,result)
        assert state!=BindingState.CONFIRMED, raw


@pytest.mark.parametrize("text,status",[
    ("I'm not done yet","COMPLETED"),
    ("please do not mark this done yet","COMPLETED"),
    ("please don't cancel this","ABANDONED"),
    ("do not pause","PAUSED"),
    ("never failed before","FAILED"),
])
def test_f2_negated_status_words_are_not_user_transitions(text,status,tmp_path):
    log,sources,rec,root=setup(tmp_path)
    task,head=opened(rec)
    with pytest.raises(ValueError,match="EXPLICIT_USER_TRANSITION_REQUIRED"):
        rec.task_state(task,head.record_id,intake=intake(text),status=status)
    assert log.load().task(task).payload["status"]=="OPEN"


def test_f2_explicit_transitions_still_accepted(tmp_path):
    log,sources,rec,root=setup(tmp_path)
    task,head=opened(rec)
    assert rec.task_state(task,head.record_id,intake=intake("pause"),status="PAUSED").persisted
    assert rec.task_state(task,log.load().task(task).record_id,intake=intake("resume"),status="OPEN").persisted
    assert rec.task_state(task,log.load().task(task).record_id,intake=intake("done"),status="COMPLETED").persisted


@pytest.mark.parametrize("text,status",[
    ("nothing is done yet","COMPLETED"),
    ("none of it is done","COMPLETED"),
    ("done? nope","COMPLETED"),
    ("far from done","COMPLETED"),
    ("don‘t cancel this","ABANDONED"),
    ("donʼt pause","PAUSED"),
    ("it hasn't failed","FAILED"),
])
def test_r3_negated_status_forms_are_not_user_transitions(text,status,tmp_path):
    """Re-audit R-3: the R-1/R-2 cue gaps also let negated status phrasings
    bind as explicit USER_ASSERTED transitions."""
    log,sources,rec,root=setup(tmp_path)
    task,head=opened(rec)
    with pytest.raises(ValueError,match="EXPLICIT_USER_TRANSITION_REQUIRED"):
        rec.task_state(task,head.record_id,intake=intake(text),status=status)
    assert log.load().task(task).payload["status"]=="OPEN"


@pytest.fixture
def swap_registry():
    saved=module._VERIFIERS
    def swap(registry): module._VERIFIERS=MappingProxyType(registry)
    yield swap
    module._VERIFIERS=saved


@pytest.mark.parametrize("registry",[{},{"uri.verifier.m36_fixture":("BYTE_EVIDENCE","2",fixture_verifier)}])
def test_f3_registry_mismatch_fails_closed_not_quarantined(registry,swap_registry,tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    (root/"budget.xlsx").write_bytes(b"FAIL")
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    verdict=rec.invoke_verifier(claimed(rec,task,src).record_ids[0],"uri.verifier.m36_fixture",trace_id="a"*32,session_id="session")
    assert verdict.persisted
    swap_registry(registry)
    with pytest.raises(VerifierRegistryMismatch): log.load()
    assert not list(log.path.glob("quarantine/*.json"))
    write=claimed(rec,task,src)
    assert not write.persisted and write.reason=="VERIFIER_REGISTRY_MISMATCH"
    # 70e6065 (a87e158): every trusted write returns the mismatch instead of raising.
    ts_res=rec.task_state(task,"any-head",intake=intake("pause"),status="PAUSED")
    assert not ts_res.persisted and ts_res.reason=="VERIFIER_REGISTRY_MISMATCH"
    fg_res=rec.forget((task,),intake=intake("forget"))
    assert not fg_res.persisted and fg_res.reason=="VERIFIER_REGISTRY_MISMATCH"
    ot_id,ot_res=rec.open_task(intake("open new task"),"open new task")
    assert not ot_res.persisted and ot_res.reason=="VERIFIER_REGISTRY_MISMATCH"
    cr_res=rec.correction(task,"budget.xlsx","any-head",intake=intake("correct budget.xlsx"))
    assert not cr_res.persisted and cr_res.reason=="VERIFIER_REGISTRY_MISMATCH"
    if registry:  # an empty registry refuses the unregistered id before loading, as before
        iv_res=rec.invoke_verifier(verdict.record_ids[0],"uri.verifier.m36_fixture",trace_id="b"*32,session_id="session")
        assert not iv_res.persisted and iv_res.reason=="VERIFIER_REGISTRY_MISMATCH"
    result=retrieval(log,s,"resume the budget task")
    assert result.degraded=="VERIFIER_REGISTRY_MISMATCH"


def test_f3_verified_completion_does_not_reopen_without_registry(swap_registry,tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    task,head=opened(rec); bound=bind(log,s,"budget.xlsx")
    assert rec.task_state(task,head.record_id,intake=intake("budget.xlsx"),bindings=(bound,)).persisted
    head=log.load().task(task); raw=intake("complete"); obs=_runtime_observation(raw,"VERIFIED_COMPLETE")
    verdict=rec.invoke_verifier(claimed(rec,task,bound.source).record_ids[0],"uri.verifier.m36_fixture",trace_id="c"*32,session_id="session")
    assert rec.task_state(task,head.record_id,intake=raw,status="COMPLETED",runtime_action=obs,last_outcome_record_id=verdict.record_ids[0]).persisted
    swap_registry({})
    with pytest.raises(VerifierRegistryMismatch): log.load()
    swap_registry({"uri.verifier.m36_fixture":("BYTE_EVIDENCE","1",fixture_verifier)})
    assert log.load().task(task).payload["status"]=="COMPLETED"


def test_f3_tampered_receipt_is_still_quarantined(tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    verdict=rec.invoke_verifier(claimed(rec,task,src).record_ids[0],"uri.verifier.m36_fixture",trace_id="a"*32,session_id="session")
    record=log.load().records[verdict.record_ids[0]]
    (log.path/"attestations"/(record.payload["attestation_ref"]+".json")).write_bytes(b"{}")
    restored=log.load()
    assert record.record_id not in restored.records and restored.recovery_ids


def test_f4_forget_cannot_hide_verdict(tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    (root/"budget.xlsx").write_bytes(b"FAIL")
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    verdict=rec.invoke_verifier(claimed(rec,task,src).record_ids[0],"uri.verifier.m36_fixture",trace_id="a"*32,session_id="session")
    assert claimed(rec,task,src).persisted
    hidden=rec.forget(verdict.record_ids,intake=intake("forget that"))
    assert not hidden.persisted and hidden.reason=="INVALID_HIDE_TARGET"
    package=build_context(log.load(),s,task).to_dict()
    assert any(o["record_id"]==verdict.record_ids[0] and o["verification_status"]=="FAILED" for o in package["recent_outcomes"])


def test_f4_forget_cannot_strand_task_but_can_hide_whole_task(tmp_path):
    log,s,rec,root=setup(tmp_path)
    task,head=opened(rec)
    assert rec.forget((head.record_id,),intake=intake("forget")).reason=="INVALID_HIDE_TARGET"
    assert log.load().task(task).record_id==head.record_id
    assert rec.forget((log.load().openings[task],),intake=intake("forget")).persisted
    assert log.load().task(task) is None


def test_a1_whole_task_forget_cannot_hide_a_failed_verdict(tmp_path):
    """User ruling (2026-09-28): whole-task forget must not be allowed to hide
    a FAILED verifier verdict inside it (audit A-1). Blocked, not redacted."""
    bootstrap(); log,s,rec,root=setup(tmp_path)
    (root/"budget.xlsx").write_bytes(b"FAIL")
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    verdict=rec.invoke_verifier(claimed(rec,task,src).record_ids[0],"uri.verifier.m36_fixture",trace_id="a"*32,session_id="session")
    assert verdict.persisted
    opening=log.load().openings[task]
    hidden=rec.forget((opening,),intake=intake("forget the task"))
    assert not hidden.persisted and hidden.reason=="INVALID_HIDE_TARGET"
    package=build_context(log.load(),s,task).to_dict()
    assert package["task"] is not None
    assert any(o["record_id"]==verdict.record_ids[0] and o["verification_status"]=="FAILED" for o in package["recent_outcomes"])


def test_f5_dot_separated_stem_is_a_collision(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget-v2.xlsx","budget.v2.xlsx"))
    result=retrieval(log,sources,"budget v2")
    assert len(result.collision.matching_ids)==2 and result.collision.complete
    assert {c.source.relpath for c in result.candidates}>={"budget-v2.xlsx","budget.v2.xlsx"}
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED


def test_f6_unrelated_hidden_file_does_not_block_exact_title(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx",))
    (root/".DS_Store").write_bytes(b"finder metadata"); (root/".~lock.budget.xlsx#").write_bytes(b"lock")
    result=retrieval(log,sources,"update budget.xlsx",proposal="budget.xlsx",span=(7,18))
    assert result.collision.complete and not result.degraded
    state,service,p=registered(sources,result)
    assert state==BindingState.CONFIRMED


def test_f6_hidden_file_with_matching_name_still_blocks(tmp_path):
    log,sources,rec,root=setup(tmp_path,("notes.md",))
    (root/".notes.md").write_bytes(b"hidden twin")
    result=retrieval(log,sources,".notes.md")
    assert not result.collision.complete and result.collision.reason=="HIDDEN_NAME_MATCH"


def test_f6_hidden_directory_still_makes_scope_incomplete(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx",))
    (root/".git").mkdir(); (root/".git"/"budget.xlsx").write_bytes(b"x")
    assert not sources.scan().complete


# ---- Positive-allowlist gate (User decision 2026-09-28; replaces further blocklist growth) ----
# Forms deliberately absent from any negation list: the gate must reject them because
# they are not plainly affirmative, not because they were anticipated.
UNLISTED_NON_AFFIRMATIVE = [
    "don‛t use budget.xlsx", "don′t use budget.xlsx", "donʹt use budget.xlsx", "donˈt use budget.xlsx",
    "don t use budget.xlsx", "don­t use budget.xlsx", "ＮＯＴ budget.xlsx", "n​ot budget.xlsx",
    "shan't use budget.xlsx", "mightn't use budget.xlsx", "oughtn't use budget.xlsx", "daren't use budget.xlsx",
    "leave budget.xlsx out", "rule out budget.xlsx", "keep budget.xlsx out of this", "steer clear of budget.xlsx",
    "hold off on budget.xlsx", "w/o budget.xlsx", "sans budget.xlsx", "budget.xlsx is the wrong file",
    "budget.xlsx is off limits", "deselect budget.xlsx", "keep away from budget.xlsx", "budget.xlsx? no thanks",
    "pas budget.xlsx", "sin budget.xlsx", "open budget.xlsx... actually never mind", "update budget.xlsx but keep the format",
]


@pytest.mark.parametrize("raw",UNLISTED_NON_AFFIRMATIVE)
@pytest.mark.parametrize("tight",[False,True])
def test_allowlist_non_affirmative_turns_never_confirm(raw,tight,tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    a=raw.index("budget.xlsx")
    result=retrieval(log,sources,raw,proposal="budget.xlsx",span=(a,a+11) if tight else None)
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED, raw


AFFIRMATIVE_CONTROLS = [
    "update budget.xlsx", "please open budget.xlsx", "can you summarize budget.xlsx for me", "let's review budget.xlsx",
    "I'd like to check budget.xlsx", "open the budget.xlsx file please", "use budget.xlsx", '"budget.xlsx"',
    "Update budget.xlsx now!", "could you fix budget.xlsx?", "I'll edit budget.xlsx", "ok, open budget.xlsx again",
]


@pytest.mark.parametrize("raw",AFFIRMATIVE_CONTROLS)
def test_allowlist_plain_affirmative_requests_still_confirm(raw,tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    a=raw.index("budget.xlsx")
    result=retrieval(log,sources,raw,proposal="budget.xlsx",span=(a,a+11))
    state,service,p=registered(sources,result)
    assert state==BindingState.CONFIRMED, raw


def test_allowlist_non_affirmative_explicit_id_never_confirms(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    sid=next(l.source_id for l in sources.scan().locators if l.relpath=="budget.xlsx")
    for raw,ok in ((f"steer clear of {sid}",False),(f"don′t use {sid}",False),(f"please open {sid}",True)):
        a=raw.index(sid)
        result=retrieval(log,sources,raw,proposal=sid,span=(a,a+len(sid)))
        assert (registered(sources,result)[0]==BindingState.CONFIRMED)==ok, raw


def test_allowlist_gates_attachment_anchor(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","worker.py"))
    ids={x.relpath:x.source_id for x in sources.scan().locators}
    for raw,anchored in (("open the spreadsheet",True),("steer clear of the spreadsheet",False)):
        a=raw.index("spreadsheet")
        r=retrieval(log,sources,raw,span=(a,a+11),attachment_source_ids=(ids["budget.xlsx"],))
        p=MemoryAdapter(sources).project(r)
        assert (p.query is not None and p.query.deterministic_anchor is not None)==anchored, raw


def test_allowlist_gates_free_input_answer(tmp_path):
    from tests.test_m36_memory_support import resolve
    log,sources,rec,root=setup(tmp_path)
    for raw,ok in (("steer clear of budget.xlsx",False),("budget.xlsx? no thanks",False),("yes, budget.xlsx please",True)):
        result,p,service,b=resolve(log,sources,"budget sheet")
        answer=intake(raw,round_id=b.next_contract_id)
        a=raw.index("budget.xlsx")
        bound=MemoryAdapter(sources).respond_free_input(service,result,p.query,b.next_contract_id,answer,proposed_offsets=(a,a+11))
        assert (bound.state==BindingState.CONFIRMED)==ok, raw


@pytest.mark.parametrize("text,status",[
    ("don t cancel this","ABANDONED"), ("don′t cancel this","ABANDONED"), ("shan't cancel this","ABANDONED"),
    ("mightn't be done","COMPLETED"), ("don‛t pause","PAUSED"), ("oughtn't be marked failed","FAILED"),
    ("done? not really","COMPLETED"), ("is it done","COMPLETED"), ("pause and resume later","PAUSED"),
    ("cancel? maybe","ABANDONED"),
])
def test_allowlist_status_needs_plain_declaration(text,status,tmp_path):
    log,sources,rec,root=setup(tmp_path)
    task,head=opened(rec)
    with pytest.raises(ValueError,match="EXPLICIT_USER_TRANSITION_REQUIRED"):
        rec.task_state(task,head.record_id,intake=intake(text),status=status)
    assert log.load().task(task).payload["status"]=="OPEN"


@pytest.mark.parametrize("text,status",[
    ("done","COMPLETED"), ("it's done","COMPLETED"), ("we are done now","COMPLETED"), ("mark this task as complete","COMPLETED"),
    ("please cancel this task","ABANDONED"), ("pause for a moment","PAUSED"), ("ok, the task failed","FAILED"),
    ("can you cancel this task","ABANDONED"),
])
def test_allowlist_status_plain_declarations_accepted(text,status,tmp_path):
    log,sources,rec,root=setup(tmp_path)
    task,head=opened(rec)
    assert rec.task_state(task,head.record_id,intake=intake(text),status=status).persisted, text
    assert log.load().task(task).payload["status"]==status


def test_a1_forget_blocked_while_claim_awaits_verdict(tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    (root/"budget.xlsx").write_bytes(b"FAIL")
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    claim=claimed(rec,task,src).record_ids[0]
    hidden=rec.forget((log.load().openings[task],),intake=intake("forget the task"))
    assert not hidden.persisted and hidden.reason=="INVALID_HIDE_TARGET"
    verdict=rec.invoke_verifier(claim,"uri.verifier.m36_fixture",trace_id="a"*32,session_id="session")
    assert verdict.persisted
    package=build_context(log.load(),s,task).to_dict()
    assert any(o["record_id"]==verdict.record_ids[0] and o["verification_status"]=="FAILED" for o in package["recent_outcomes"])


def test_a1_nothing_recorded_against_a_forgotten_task(tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    (root/"budget.xlsx").write_bytes(b"FAIL")
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    assert rec.forget((log.load().openings[task],),intake=intake("forget the task")).persisted
    later=claimed(rec,task,src)
    assert not later.persisted and later.reason=="TASK_HIDDEN"
    assert log.load().task(task) is None


def test_a1_stale_claim_can_be_forgotten_before_the_task(tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    claim=claimed(rec,task,src).record_ids[0]
    assert not rec.forget((log.load().openings[task],),intake=intake("forget the task")).persisted
    assert rec.forget((claim,),intake=intake("forget that claim")).persisted
    assert rec.forget((log.load().openings[task],),intake=intake("forget the task")).persisted
    assert log.load().task(task) is None
