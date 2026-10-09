"""Scheduler-domain A2UI host with the real engine (AUTOMATED SIMULATION: scripted in-process harness).

Proposal -> revise -> stale digest -> draft-changed -> confirm; artifact review surfaces; calendar review; restart.
"""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scheduler"))
from test_engine import Clock, FakeHarness  # noqa: E402

from uri_scheduler.a2ui_host import A2uiHostError, SchedulerA2ui  # noqa: E402
from uri_scheduler.engine import Scheduler  # noqa: E402


@pytest.fixture
def env(tmp_path):
    clock = Clock("2026-10-09T10:00:00+05:30")
    h = FakeHarness()
    s = Scheduler(tmp_path / "state", harness=h, now_fn=clock).start()
    yield s, SchedulerA2ui(s, "owner"), h, clock, tmp_path
    s.close()


def model(msgs):
    import copy
    return copy.deepcopy(next(m["updateDataModel"]["value"] for m in msgs if "updateDataModel" in m))


def components(msgs):
    return {c["id"]: c for m in msgs if "updateComponents" in m for c in m["updateComponents"]["components"]}


def click(host, sid, msgs, comp, **draft):
    """What the renderer sends: the Button's declared context resolved against the (edited) data model."""
    m = model(msgs)
    m["draft"].update(draft)
    decl = components(msgs)[comp]["action"]["event"]
    ctx = {"surface_digest": m["bound"]["surface"]["digest"]}
    for k, v in decl.get("context", {}).items():
        if isinstance(v, dict):
            cur = m
            for seg in v["path"].strip("/").split("/"):
                cur = cur[seg]
            ctx[k] = cur
        else:
            ctx[k] = v
    return host.action({"name": decl["name"], "surfaceId": sid, "sourceComponentId": comp,
                        "timestamp": "2026-10-09T10:00:00Z", "context": ctx})


def test_proposal_revise_confirm_journey(env):
    s, host, h, clock, _ = env
    r = host.propose_from_request({"festivals": ["diwali", "dussehra"], "time": "09:00", "offset_days": 2,
                                   "assumptions": ["'major festivals' means the national list; edit below."]})
    sid, msgs = r["surface_id"], r["messages"]
    assert s.job(r["job_id"])["state"] == "PROPOSED" and s.store.q1("SELECT COUNT(*) FROM occurrence")[0] == 0
    comps = components(msgs)
    assert {"picker", "time", "offset", "confirm", "revise", "discard"} <= set(comps)
    assert "Dussehra" in comps["upcoming"]["text"] and "2026-10-18 09:00 IST" in comps["upcoming"]["text"]
    # confirming an edited draft that was never proposed is refused
    with pytest.raises(A2uiHostError) as e:
        click(host, sid, msgs, "confirm", selection=["diwali"])
    assert e.value.code == "DRAFT_CHANGED"
    # revise: a new proposal (new hash), the old PROPOSED job is cancelled, same surface id, new revision
    out = click(host, sid, msgs, "revise", selection=["diwali", "holi"], time="08:30", offset="3")
    assert out["result"] == "REVISED" and s.job(r["job_id"])["state"] == "CANCELLED"
    new = msgs[:1] + out["messages"]
    # the old version of the surface can no longer act
    with pytest.raises(A2uiHostError) as e:
        click(host, sid, msgs, "confirm")
    assert e.value.code == "STALE_SURFACE"
    done = click(host, sid, new, "confirm")
    assert done["result"] == "ACTIVATED" and s.job(out["job_id"])["state"] == "ACTIVE"
    sched = s.job(out["job_id"])["schedule"]
    assert sched["offset_days"] == -3 and sched["time"] == "08:30" and sorted(sched["selection"]) == ["diwali", "holi"]
    assert "not available" not in components(done["messages"])["harness"]["text"]   # fake harness is AVAILABLE
    kinds = [ev["payload"]["result"] for ev in s.store.events(limit=500) if ev["kind"] == "a2ui.action"]
    assert kinds.count("OK") == 2 and "STALE_SURFACE" in kinds and "DRAFT_CHANGED" in kinds


def test_request_validation(env):
    s, host, *_ = env
    for req, code in (({"festivals": ["muharram"]}, "UNKNOWN_FESTIVAL"), ({"festivals": []}, "BAD_SELECTION"),
                      ({"time": "9am"}, "BAD_TIME_OR_OFFSET"), ({"offset_days": 30}, "BAD_TIME_OR_OFFSET"),
                      ({"assumptions": ["x" * 400]}, "BAD_ASSUMPTIONS"), ({"festivals": ["no_such"]}, "UNKNOWN_FESTIVAL")):
        with pytest.raises(A2uiHostError) as e:
            host.propose_from_request(req)
        assert e.value.code == code
    r = host.propose_from_request({})            # nothing named: the 12 major festivals, 09:00, 2 days before
    from uri_scheduler.a2ui_host import DEFAULT_SELECTION
    assert set(s.job(r["job_id"])["schedule"]["selection"]) == set(DEFAULT_SELECTION)


def test_discard_and_unknown_surface(env):
    s, host, *_ = env
    r = host.propose_from_request({"festivals": ["diwali"]})
    out = click(host, r["surface_id"], r["messages"], "discard")
    assert out["messages"][0] == {"version": "v0.9", "deleteSurface": {"surfaceId": r["surface_id"]}}
    assert s.job(r["job_id"])["state"] == "CANCELLED"
    with pytest.raises(A2uiHostError) as e:
        click(host, r["surface_id"], r["messages"], "confirm")
    assert e.value.code == "UNKNOWN_SURFACE"


def test_artifact_review_surface_approve_and_refine(env):
    s, host, h, clock, _ = env
    p = s.propose(owner="owner", title="once", template_id="festival_gif.v1",
                  params={"festival": {"key": "diwali", "name": "Diwali", "date": "2026-11-08"}},
                  schedule={"kind": "once", "at": "2026-10-09T10:05"})
    s.confirm(p["job_id"], "owner", p["proposal_sha256"])
    clock.set("2026-10-09T10:06:00+05:30")
    s.tick()
    msgs = host.open_messages()
    sid = next(m["createSurface"]["surfaceId"] for m in msgs if "createSurface" in m)
    assert sid.startswith("review-")
    mine = [m for m in msgs if m[next(iter(k for k in m if k != "version"))]["surfaceId"] == sid]
    comps = components(mine)
    assert comps["mode"]["text"] == "Synthetic fixture output" and comps["mode"]["tone"] == "warning"   # never "Claude"
    art = s.artifact(comps["image"]["artifactId"])
    assert comps["image"]["sha256"] == art["sha256"]
    with pytest.raises(A2uiHostError) as e:
        click(host, sid, mine, "refine", instruction="")
    assert e.value.code in ("BAD_CONTEXT_VALUE", "INSTRUCTION_REQUIRED")
    out = click(host, sid, mine, "refine", instruction="more marigolds")
    assert out["result"] == "REFINE" and out["occurrence_state"] == "REVISION_QUEUED"
    assert all(sid not in str(m) for m in host.open_messages())          # closed after the decision
    s.tick()
    msgs = host.open_messages()
    sid2 = next(m["createSurface"]["surfaceId"] for m in msgs if "createSurface" in m)
    mine2 = [m for m in msgs if sid2 in str(m)]
    out = click(host, sid2, mine2, "approve")
    assert out["result"] == "APPROVE" and out["occurrence_state"] == "APPROVED"


def test_calendar_review_dispute_and_correct(env):
    s, host, *_ = env
    r = host.calendar_surface()
    comps = components(r["messages"])
    assert any(o["value"] == "dussehra:2026" for o in comps["record"]["options"])
    with pytest.raises(A2uiHostError) as e:
        click(host, r["surface_id"], r["messages"], "set_date", record="dussehra:2026", start="")
    assert e.value.code in ("DATE_REQUIRED",)
    out = click(host, r["surface_id"], r["messages"], "set_date", record="diwali:2026", start="2026-11-09", note="local")
    assert out["result"] == "CORRECTED" and out["version"].endswith("+owner.1")
    rec = next(x for x in s.calendar.records("in_festivals") if x["festival_key"] == "diwali" and x["year"] == 2026)
    assert rec["start"] == "2026-11-09" and rec["correction"]["note"] == "local"
    with pytest.raises(A2uiHostError) as e:          # the calendar surface was re-rendered: the old version is stale
        click(host, r["surface_id"], r["messages"], "dispute", record="holi:2027")
    assert e.value.code == "STALE_SURFACE"


def test_surfaces_survive_restart_and_still_enforce_digest(env):
    s, host, h, clock, tmp = env
    r = host.propose_from_request({"festivals": ["diwali"]})
    s.close()
    s2 = Scheduler(tmp / "state", harness=h, now_fn=clock).start()
    try:
        host2 = SchedulerA2ui(s2, "owner")
        msgs = [m for m in host2.open_messages() if r["surface_id"] in str(m)]
        assert msgs == r["messages"]                                         # byte-identical re-render
        with pytest.raises(A2uiHostError) as e:
            click(host2, r["surface_id"], msgs, "confirm", selection=["holi"])
        assert e.value.code == "DRAFT_CHANGED"
        assert click(host2, r["surface_id"], msgs, "confirm")["result"] == "ACTIVATED"
        other = SchedulerA2ui(s2, "intruder")
        with pytest.raises(A2uiHostError) as e:
            other.action({"name": "surface.dismiss", "surfaceId": r["surface_id"], "sourceComponentId": "dismiss",
                          "context": {}})
        assert e.value.code == "NOT_OWNER"
    finally:
        s2.close()


def test_sikkim_request_leaves_out_undated_festivals_and_says_so(env):
    """A 'Sikkim festivals' handoff names festivals whose 2026 date has passed and whose 2027 date is not notified."""
    from uri_operational_intelligence.schedule_intent import interpret
    s, host, *_ = env
    req = interpret("make a greeting card a week before each Sikkim festival")["request"]
    r = host.propose_from_request(req)
    sel = s.job(r["job_id"])["schedule"]["selection"]
    assert "losar" not in sel and "losoong_namsoong" in sel and "tihar_sikkim" in sel
    text = " ".join(c.get("text", "") for c in r["messages"][1]["updateComponents"]["components"] if c["id"] == "assumptions")
    assert "not included" in text and "Losar" in text
    with pytest.raises(A2uiHostError) as e:
        host.propose_from_request({"festivals": ["losar"]})
    assert e.value.code == "NO_UPCOMING_FESTIVAL"


def test_r1_discard_and_confirm_are_serialized(env):
    """A2UI audit round 1, F2: an action is one critical section under the engine mutex."""
    import threading
    s, host, *_ = env
    r = host.propose_from_request({"festivals": ["diwali"]})
    done = threading.Event()
    with s._mutex:
        t = threading.Thread(target=lambda: (click(host, r["surface_id"], r["messages"], "discard"), done.set()))
        t.start()
        assert not done.wait(0.3)                       # waits while another holder (e.g. a confirm) has the mutex
    assert done.wait(10)
    t.join()
    assert s.job(r["job_id"])["state"] == "CANCELLED"


def test_r4_hostile_strings_are_refused_before_any_state_change(env):
    """A2UI audit round 4, R4-1/R4-2: no orphaned proposal, no 500 from auditing hostile identifiers."""
    s, host, *_ = env
    n = s.store.q1("SELECT COUNT(*) FROM job")[0]
    with pytest.raises(A2uiHostError) as e:
        host.propose_from_request({"festivals": ["diwali"], "assumptions": ["x\ud800"]})
    assert e.value.code == "BAD_ASSUMPTIONS" and s.store.q1("SELECT COUNT(*) FROM job")[0] == n
    r = host.propose_from_request({"festivals": ["diwali"]})
    for bad in ({"name": "x\ud800"}, {"sourceComponentId": "\udfff"}, {"name": 5}):
        msg = dict({"name": "surface.dismiss", "surfaceId": r["surface_id"], "sourceComponentId": "discard",
                    "context": {}}, **bad)
        with pytest.raises(A2uiHostError) as e:
            host.action(msg)
        assert e.value.code == "BAD_ACTION_MESSAGE"
    with pytest.raises(A2uiHostError) as e:      # a hostile value in the context: refused by the gate, audited safely
        click(host, r["surface_id"], r["messages"], "revise", time="09:00\ud800")
    assert e.value.code == "BAD_CONTEXT_VALUE"
    assert s.store.verify_chain()["ok"]


def test_r4_proposal_is_withdrawn_if_its_surface_cannot_be_saved(env, monkeypatch):
    s, host, *_ = env
    def boom(*a, **k):
        raise RuntimeError("disk full")
    monkeypatch.setattr(host, "_save", boom)
    with pytest.raises(RuntimeError):
        host.propose_from_request({"festivals": ["diwali"]})
    states = [r[0] for r in s.store.q("SELECT state FROM job")]
    assert states and all(x == "CANCELLED" for x in states)
