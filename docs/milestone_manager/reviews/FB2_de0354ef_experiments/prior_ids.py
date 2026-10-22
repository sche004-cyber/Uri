import sys, os, shutil, json
src, base = sys.argv[1], sys.argv[2]; sys.path.insert(0, src)
from scripts.dev_workflow.milestones.store import EventStore, check_free_text, StoreError
from scripts.dev_workflow.milestones.service import Manager
from scripts.dev_workflow.milestones.model import find_secret, ValidationError
from scripts.dev_workflow.milestones import views
C1, C2 = "a"*40, "b"*40
def fresh(n):
    h = os.path.join(base, "prior_" + n); shutil.rmtree(h, ignore_errors=True); EventStore.init(h, "h1"); return h, Manager(h, actor="impl:a", session="s")
def accept(m, mid, rev="rev:y", commit=C1):
    m.update_milestone(mid, candidate_commit=commit)
    m.record_review(mid, commit, "subagent", rev, "SUBAGENT", "ACCEPT", 0, 0, "COMPLETED_WITH_RESULT", "ok")
    m.set_status(mid, "ACCEPTED", "r")
# D1-01
h, m = fresh("d101"); m.create_milestone("MA", "a"); accept(m, "MA")
p = m.projection(); print("D1-01 before:", views.indicator(p, p["milestones"]["MA"])["color"])
try: m.record_implementer("MA", "rev:y")
except Exception as e: print("  record_implementer refused", getattr(e, "code", e))
p = m.projection(); ind = views.indicator(p, p["milestones"]["MA"]); print("D1-01 after reviewer becomes implementer:", ind["color"], "|", str(ind.get("issue"))[:120])
# D1-02 / R2-01 / R3-01 / R4-01 / R5-01 / R6-01 / R7-01 / R8-01 / D2-01 / D2-02: direct store
st = EventStore(h)
cases = {"D1-02 data": dict(data={"note": "password=hunter2"}), "D1-02 actor": dict(actor="password=hunter2"),
         "D1-02 session": dict(session="token=abcdef123456"),
         "R2-01 base": dict(base={"password=12345678": 0}),
         "R3-01": dict(data={"access_token": "abc123def456ghi789jkl012mno345"}),
         "R4-01": dict(data={"api_key": {"value": "abcd1234xyz9876"}}),
         "R5-01": dict(data={"credentials": {"password": {"value": "s3cret/abc123"}}}),
         "R6-01": dict(data={"password": {"value": "/s3cret99"}}),
         "R7-01": dict(data={"metadata": {"password": "abc,defghi9"}}),
         "R8-01": dict(data={"password": {"value": "$uperS3cret!"}}),
         "D2-01": dict(data={"password": {"value": "abc"}}),
         "D2-02": dict(data={"note": "password: ${PASSWORD} hunter2"})}
for lab, kw in cases.items():
    data = kw.get("data", {"note": "ok"}); actor = kw.get("actor", "rev:fb2"); sess = kw.get("session")
    size = os.path.getsize(st.segment_path)
    try:
        with st.locked():
            st.append_many([("HANDOFF_RECORDED", data, kw.get("base"))], actor=actor, session=sess)
        print(lab, "ACCEPTED  <-- NOT FIXED")
    except StoreError as e:
        print(lab, "refused", e.code, "segment unchanged:", size == os.path.getsize(st.segment_path))
# R2-02 / R3-02: ready()
h, m = fresh("r202"); m.create_milestone("MA", "a"); m.create_milestone("MB", "b", depends_on=["MA"]); accept(m, "MA")
print("R2-02 ready before neg:", views.ready(m.projection()))
m.record_review("MA", C1, "subagent", "rev:z", "SUBAGENT", "REJECT", 1, 1, "COMPLETED_WITH_RESULT", "no")
print("R2-02 ready after later REJECT on same candidate:", views.ready(m.projection()))
h, m = fresh("r302"); m.create_milestone("MA", "a"); m.create_milestone("MB", "b", depends_on=["MA"]); accept(m, "MA")
try: m.update_milestone("MA", candidate_commit=C2); print("R3-02 candidate change ACCEPTED")
except ValidationError as e: print("R3-02 candidate change refused", e.code)
# simulate the R3-02 projection directly
p = m.projection(); p["milestones"]["MA"]["candidate_commit"] = C2
p["reviews"]["RVX"] = {"id": "RVX", "subject": "MA", "commit": C2, "reviewer": {"kind": "subagent", "id": "rev:q"}, "assurance": "SUBAGENT",
                       "verdict": "ACCEPT", "blocking_open": 0, "findings_total": 0, "result_class": "COMPLETED_WITH_RESULT"}
print("R3-02 unmet deps for B with A bound C1/candidate C2:", views.unmet_dependencies(p, p["milestones"]["MB"]))
# R23-03
h, m = fresh("r2303"); mid = "M" + "X"*63; m.create_milestone(mid, "t")
for i in range(40): m.record_handoff(mid, "summary " + "y"*200 + str(i))
p = m.projection(); txt = views.resume_brief(p, mid, max_chars=200)
print("R23-03 resume len with max_chars=200 and 64-char id:", len(txt))
