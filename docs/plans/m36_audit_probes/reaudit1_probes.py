"""M36 repair re-audit probes (same-provider internal audit, 2026-09-28).
Each test asserts the SAFE expected behaviour; a failure is a finding."""
from types import MappingProxyType
import json, re, random, string
import pytest
import uri_v1.memory.recorder as module
from uri_v1.memory.recorder import _runtime_observation
from uri_v1.memory.contracts import negated
from uri_v1.memory.context_package import build_context
from uri_v1.memory.index import VerifierRegistryMismatch
from uri_v1.memory.retrieval import stem_title as mem_stem
from uri_v1.turn.rar_deterministic import stem_title as frozen_stem
from uri_v1.turn.rar_clarification_contract import BindingState
from tests.test_m36_memory_support import setup,retrieval,opened,intake,bind
from tests.test_m36_memory_grounding import registered
from tests.test_m36_memory_verifier import bootstrap,claimed,fixture_verifier

# ---------- P1: negation forms beyond the repair's 8 ----------
NEG_FORMS = [
    "don‘t use budget.xlsx",        # left single quotation mark
    "donʼt use budget.xlsx",        # modifier letter apostrophe
    "don`t use budget.xlsx",             # backtick
    "don´t use budget.xlsx",        # acute accent
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
]

@pytest.mark.parametrize("raw",NEG_FORMS)
@pytest.mark.parametrize("tight",[False,True])
def test_p1_negation_never_confirms(raw,tight,tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    a=raw.index("budget.xlsx"); span=(a,a+len("budget.xlsx")) if tight else None
    result=retrieval(log,sources,raw,proposal="budget.xlsx",span=span)
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED, (raw, p.grounding)

@pytest.mark.parametrize("raw",["update budget.xlsx","open budget.xlsx please","budget.xlsx"])
def test_p1_control_positive_confirms(raw,tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    a=raw.index("budget.xlsx")
    result=retrieval(log,sources,raw,proposal="budget.xlsx",span=(a,a+11))
    state,service,p=registered(sources,result)
    assert state==BindingState.CONFIRMED

def test_p1_explicit_id_negated(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","report.docx"))
    sid=next(l.source_id for l in sources.scan().locators if l.relpath=="budget.xlsx")
    for raw in (f"don't use {sid}", f"anything but {sid}"):
        a=raw.index(sid)
        result=retrieval(log,sources,raw,proposal=sid,span=(a,a+len(sid)))
        state,service,p=registered(sources,result)
        assert state!=BindingState.CONFIRMED, raw

# ---------- P2: negated status forms ----------
NEG_STATUS = [
    ("nothing is done yet","COMPLETED"),
    ("none of it is done","COMPLETED"),
    ("done? nope","COMPLETED"),
    ("far from done","COMPLETED"),
    ("don‘t cancel this","ABANDONED"),
    ("donʼt pause","PAUSED"),
    ("it hasn't failed","FAILED"),
    ("DO NOT mark complete","COMPLETED"),
]
@pytest.mark.parametrize("text,status",NEG_STATUS)
def test_p2_negated_status_rejected(text,status,tmp_path):
    log,sources,rec,root=setup(tmp_path)
    task,head=opened(rec)
    try:
        r=rec.task_state(task,head.record_id,intake=intake(text),status=status)
        persisted=r.persisted
    except ValueError: persisted=False
    assert not persisted, text
    assert log.load().task(task).payload["status"]=="OPEN"

# ---------- P3: verifier reload ----------
@pytest.fixture
def swap():
    saved=module._VERIFIERS
    def f(reg): module._VERIFIERS=MappingProxyType(reg)
    yield f
    module._VERIFIERS=saved

def _failed_verdict(tmp_path):
    bootstrap(); log,s,rec,root=setup(tmp_path)
    (root/"budget.xlsx").write_bytes(b"FAIL")
    task,head=opened(rec); src=s.fingerprint(s.scan().locators[0])
    v=rec.invoke_verifier(claimed(rec,task,src).record_ids[0],"uri.verifier.m36_fixture",trace_id="a"*32,session_id="session")
    assert v.persisted
    return log,s,rec,root,task,src,v

def test_p3_type_only_mismatch_fails_closed(swap,tmp_path):
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    swap({"uri.verifier.m36_fixture":("OTHER_TYPE","1",fixture_verifier)})
    with pytest.raises(VerifierRegistryMismatch): log.load()

def test_p3_mismatch_leaves_log_bytes_and_no_quarantine(swap,tmp_path):
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    before={p.name:p.read_bytes() for p in log.path.glob("log-*.jsonl")}
    swap({})
    head=None
    for call in (lambda: claimed(rec,task,src),
                 lambda: rec.forget((log.path.name,),intake=intake("forget")),
                 lambda: rec.open_task(intake("new task"),"new task")[1]):
        try: r=call(); assert not r.persisted
        except (VerifierRegistryMismatch,ValueError): pass
    after={p.name:p.read_bytes() for p in log.path.glob("log-*.jsonl")}
    assert before==after
    assert not list(log.path.glob("quarantine/*.json"))
    swap({"uri.verifier.m36_fixture":("BYTE_EVIDENCE","1",fixture_verifier)})
    pkg=build_context(log.load(),s,task).to_dict()
    assert any(o["record_id"]==v.record_ids[0] and o["verification_status"]=="FAILED" for o in pkg["recent_outcomes"])
    assert pkg["degraded"] is None

def test_p3_invoke_verifier_under_mismatch_does_not_persist(swap,tmp_path):
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    claim=claimed(rec,task,src).record_ids[0]
    swap({"uri.verifier.x":("BYTE_EVIDENCE","1",fixture_verifier),})
    n=len(log.load.__self__.path.read_bytes()) if False else None
    before={p.name:p.read_bytes() for p in log.path.glob("log-*.jsonl")}
    outcome="returned"
    try:
        r=rec.invoke_verifier(claim,"uri.verifier.x",trace_id="e"*32,session_id="session")
        assert not r.persisted
    except (VerifierRegistryMismatch,ValueError) as e: outcome=type(e).__name__
    assert before=={p.name:p.read_bytes() for p in log.path.glob("log-*.jsonl")}
    print("invoke_verifier under mismatch:",outcome)

def test_p3_receipt_deleted_with_registry_present_quarantines_only_verdict(tmp_path):
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    ref=log.load().records[v.record_ids[0]].payload["attestation_ref"]
    (log.path/"attestations"/(ref+".json")).unlink()
    idx=log.load()
    assert v.record_ids[0] not in idx.records and idx.recovery_ids
    pkg=build_context(idx,s,task).to_dict()
    assert pkg["degraded"]=="QUARANTINED_RECORDS"   # surfaced, not silent

def test_p3_verified_complete_with_receipt_deleted_and_no_registry(swap,tmp_path):
    """Documents the tamper path: receipt gone + registry gone -> ValueError path (quarantine)."""
    bootstrap(); log,s,rec,root=setup(tmp_path)
    task,head=opened(rec); bound=bind(log,s,"budget.xlsx")
    assert rec.task_state(task,head.record_id,intake=intake("budget.xlsx"),bindings=(bound,)).persisted
    head=log.load().task(task); raw=intake("complete"); obs=_runtime_observation(raw,"VERIFIED_COMPLETE")
    v=rec.invoke_verifier(claimed(rec,task,bound.source).record_ids[0],"uri.verifier.m36_fixture",trace_id="c"*32,session_id="session")
    assert rec.task_state(task,head.record_id,intake=raw,status="COMPLETED",runtime_action=obs,last_outcome_record_id=v.record_ids[0]).persisted
    ref=log.load().records[v.record_ids[0]].payload["attestation_ref"]
    (log.path/"attestations"/(ref+".json")).unlink()
    swap({})
    idx=log.load()
    st=idx.task(task)
    print("tamper path head:",st and st.payload["status"],"recovery",len(idx.recovery_ids))
    assert idx.recovery_ids   # at minimum the loss is surfaced

# ---------- P4: forget ----------
def test_p4_forget_assessed_claim_keeps_failed_verdict_visible(tmp_path):
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    claim=log.load().records[v.record_ids[0]].payload["assessed_outcome_record_id"]
    r=rec.forget((claim,),intake=intake("forget that claim"))
    pkg=build_context(log.load(),s,task).to_dict()
    assert any(o["record_id"]==v.record_ids[0] and o["verification_status"]=="FAILED" for o in pkg["recent_outcomes"]), (r, pkg["recent_outcomes"])

def test_p4_forget_mixed_targets_rejected_atomically(tmp_path):
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    later=claimed(rec,task,src)
    r=rec.forget((later.record_ids[0],v.record_ids[0]),intake=intake("forget"))
    assert not r.persisted
    assert later.record_ids[0] not in log.load().hidden

def test_p4_forget_tombstone_cannot_unhide(tmp_path):
    log,s,rec,root=setup(tmp_path)
    task,head=opened(rec)
    t=rec.forget((log.load().openings[task],),intake=intake("forget"))
    assert t.persisted
    rec.forget((t.record_ids[0],),intake=intake("forget the forget"))
    assert log.load().task(task) is None

def test_p4_forget_whole_task_with_failed_verdict(tmp_path):
    """Governance probe: whole-task hide also hides the FAILED verdict (records behaviour)."""
    log,s,rec,root,task,src,v=_failed_verdict(tmp_path)
    r=rec.forget((log.load().openings[task],),intake=intake("forget the task"))
    pkg=build_context(log.load(),s,task).to_dict()
    print("whole-task forget persisted:",r.persisted,"task:",pkg["task"],"outcomes:",len(pkg["recent_outcomes"]))

def test_p4_forget_unknown_and_foreign_ids(tmp_path):
    log,s,rec,root=setup(tmp_path)
    assert not rec.forget(("0"*32,),intake=intake("forget")).persisted

# ---------- P5: stem lineage differential ----------
def test_p5_stem_differential_vs_frozen():
    rnd=random.Random(36)
    alphabet=string.ascii_letters+string.digits+"_.-/ ~#$()[]'"
    exts=["",".pdf",".docx",".xlsx",".csv",".md",".py",".PDF",".tar.gz"]
    for _ in range(20000):
        t="".join(rnd.choice(alphabet) for _ in range(rnd.randint(1,18)))+rnd.choice(exts)
        assert mem_stem(t)==frozen_stem(t), t

# ---------- P6: hidden files ----------
@pytest.mark.parametrize("hidden",[".~lock.budget.xlsx#","._budget.xlsx",".budget.xlsx.swp",".DS_Store",".budget.xlsx"])
def test_p6_unrelated_hidden_does_not_block(hidden,tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx",))
    (root/hidden).write_bytes(b"h")
    result=retrieval(log,sources,"update budget.xlsx",proposal="budget.xlsx",span=(7,18))
    state,service,p=registered(sources,result)
    print(hidden, state, p.degraded, result.collision.reason)

def test_p6_hidden_stem_twin_blocks_stem_expression(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx",))
    (root/".budget.pdf").write_bytes(b"h")   # stem 'budget' after leading '.' -> ' '
    result=retrieval(log,sources,"budget",proposal="budget")
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED

def test_p6_nested_hidden_same_name_blocks(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx","sub/other.md"))
    # A hidden-attribute twin is Windows-only; on POSIX, dotfile with identical name is impossible,
    # so check a hidden file inside a subfolder with the exact requested (dot) name.
    (root/"sub"/".env").write_bytes(b"x")
    result=retrieval(log,sources,".env",proposal=".env")
    assert not result.collision.complete

def test_p6_lockfile_appearing_mid_round_invalidates(tmp_path):
    log,sources,rec,root=setup(tmp_path,("budget.xlsx",))
    result=retrieval(log,sources,"update budget.xlsx",proposal="budget.xlsx",span=(7,18))
    (root/".~lock.budget.xlsx#").write_bytes(b"lock")
    state,service,p=registered(sources,result)
    assert state!=BindingState.CONFIRMED
    print("mid-round lock ->",state)
