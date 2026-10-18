"""BRAIN-QUICK-CONTROLS: Vision / Context / Speed profiles, host reconfigure, profile-aware identity, image turns."""
import base64
import json
import sys
import time
from pathlib import Path

import pytest

from uri_operational_intelligence import brain_client as BC
from uri_operational_intelligence import brain_health as BH
from uri_operational_intelligence import brain_profile as BP
from uri_operational_intelligence import images as IMG
from uri_operational_intelligence import runtime_profiles as RP
from uri_operational_intelligence import runtime_v1 as R
from uri_operational_intelligence import worker_bridge as IW
from uri_operational_intelligence.orchestrator import Orchestrator
from uri_operational_intelligence.runtime_v1 import Readiness
from uri_operational_intelligence.task_ledger import TaskLedger
from uri_operational_intelligence.worker_bridge import BridgeRefused, IntegratedTurns
from tests.oi.fake_llama import FakeLlama
from tests.oi.test_oi_orchestrator import FakeCore

SID = "3f1c7a52-8e6b-4c1e-9a55-0d5f8a0b6c11"
PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
JPEG = b"\xff\xd8\xff\xe0" + b"\x00" * 64


def frozen():
    return R.load_config()


def b64(data):
    return base64.b64encode(data).decode("ascii")


# ---- offer and choice ---------------------------------------------------------------------------------------------
def test_every_offered_profile_is_measured_and_vision_never_runs_with_mtp():
    for key in BP.OFFERED:
        assert key in RP.MEASURED_MIB
        assert not (key[1] != "off" and key[2]), "Vision has priority: no vision + MTP profile is offered"
    assert BP.DEFAULT_KEY in BP.OFFERED
    assert RP.FROZEN_KEY not in BP.OFFERED              # CONTENDED on a 16 GB card: never offered by the controls
    assert (131072, "off", True) not in BP.OFFERED      # demoted at load (R1): never offered
    assert all(RP.required_mib(k) < 16384 for k in BP.OFFERED)


def test_offer_labels_tight_options_from_the_measured_request():
    rows = {r["id"]: r for r in BP.offer()["options"]}
    assert rows["c64k-visgpu-mtpoff"]["tight"] is True and rows["c64k-visgpu-mtpoff"]["margin_mib"] == 308
    assert rows["c32k-visgpu-mtpoff"]["tight"] is False
    assert BP.offer()["default"] == {"vision": True, "context": 32768, "speed": False}


def test_key_from_controls_refuses_what_is_not_offered():
    assert BP.key_from_controls(True, 65536) == (65536, "gpu", False)
    assert BP.key_from_controls(False, 16384, True) == (16384, "off", True)
    for args, code in [((True, 32768, True), "SPEED_NEEDS_VISION_OFF"), ((True, 131072), "PROFILE_NOT_OFFERED"),
                       ((False, 65536, True), "PROFILE_NOT_OFFERED"), ((False, 12345), "PROFILE_NOT_OFFERED"),
                       (("yes", 32768), "CONTROL_INVALID"), ((True, True), "CONTROL_INVALID")]:
        with pytest.raises(BP.ChoiceError) as e:
            BP.key_from_controls(*args)
        assert e.value.code == code


def test_choice_file_round_trip_and_damaged_file_reports_the_error(tmp_path):
    assert BP.read_choice(tmp_path) == (BP.DEFAULT_KEY, "default", None)
    BP.write_choice(tmp_path, (65536, "off", False))
    assert BP.read_choice(tmp_path) == ((65536, "off", False), "user", None)
    (tmp_path / BP.CHOICE_FILE).write_text("{not json", encoding="utf-8")
    assert BP.read_choice(tmp_path) == (BP.DEFAULT_KEY, "default", "CHOICE_UNREADABLE")
    (tmp_path / BP.CHOICE_FILE).write_text(json.dumps({"schema": BP.SCHEMA, "ctx": 131072, "vision": "gpu",
                                                       "mtp": False}), encoding="utf-8")
    assert BP.read_choice(tmp_path) == (BP.DEFAULT_KEY, "default", "PROFILE_NOT_OFFERED")
    with pytest.raises(BP.ChoiceError):
        BP.write_choice(tmp_path, RP.FROZEN_KEY)


def test_the_frozen_file_is_never_written(tmp_path):
    before = Path(R.CONFIG_PATH).read_bytes()
    for key in BP.OFFERED:
        BP.write_choice(tmp_path, key)
        BP.config_for(frozen(), key)
    assert Path(R.CONFIG_PATH).read_bytes() == before


# ---- host request -------------------------------------------------------------------------------------------------
def test_reconfigure_request_carries_the_profile_and_nothing_else_does(tmp_path):
    req = BH.write_host_request(tmp_path, "reconfigure", (65536, "gpu", False))
    assert req["profile"] == {"ctx": 65536, "vision": "gpu", "mtp": False}
    with pytest.raises(ValueError):
        BH.write_host_request(tmp_path, "reconfigure")
    with pytest.raises(ValueError):
        BH.write_host_request(tmp_path, "restart", (65536, "gpu", False))
    assert "profile" not in BH.write_host_request(tmp_path, "restart")


def _host(tmp_path, cfg=None):
    sys.path.insert(0, str(Path(R.REPO_ROOT) / "scripts"))
    import ws_brain_host as H
    (tmp_path / "rep").mkdir(exist_ok=True)
    return H.Host(tmp_path / "rep", minutes=0.01, override=False, cfg=cfg, state_dir=tmp_path / "s",
                  census=lambda: {"ok": False}, lease_dir=tmp_path / "l")


def test_host_starts_the_persisted_choice_or_the_default(tmp_path):
    h = _host(tmp_path)
    assert h.report["profile"]["id"] == RP.profile_id(BP.DEFAULT_KEY)
    assert h.report["profile_choice"] == {"source": "default", "error": None}
    assert h.required_mib == RP.MEASURED_MIB[BP.DEFAULT_KEY]
    BP.write_choice(tmp_path / "rep", (131072, "off", False))
    h = _host(tmp_path)
    assert h.report["profile"]["id"] == "c128k-visoff-mtpoff" and h.required_mib == 14466
    argv = R.expected_argv(h.cfg)
    assert argv[argv.index("-c") + 1] == "131072" and "--no-mmproj" in argv and "-md" not in argv


def test_host_reconfigure_switches_argv_and_budget_without_fallback(tmp_path):
    h = _host(tmp_path)
    calls = []

    class Mgr:
        owns_instance = True

    h.mgr = Mgr()
    h.lease = object()
    h.stop_brain = lambda: calls.append(("stop", h.report["profile"]["id"])) or setattr(h, "mgr", None)

    def start():
        calls.append(("start", R.expected_argv(h.cfg), h.required_mib))
        return False                                    # the target did not become ready
    h.start_brain = start
    BH.write_host_request(tmp_path / "rep", "reconfigure", (65536, "off", False))
    assert h.take_request() == "reconfigure" and h.request_profile == (65536, "off", False)
    h.reconfigure(h.request_profile)
    assert calls[0] == ("stop", RP.profile_id(BP.DEFAULT_KEY))
    assert calls[1][2] == 13658 and calls[1][1][calls[1][1].index("-c") + 1] == "65536"
    assert h.report["profile"]["id"] == "c64k-visoff-mtpoff"           # no fallback to the previous profile
    assert h.report["last_switch"]["result"] == "NOT_READY" and "switch" not in h.report


def test_host_ignores_a_reconfigure_to_an_unoffered_profile(tmp_path):
    h = _host(tmp_path)
    path = tmp_path / "rep" / BH.REQUEST_FILE
    for prof in ({"ctx": 32768, "vision": "gpu", "mtp": True}, {"ctx": 131072, "vision": "off", "mtp": True},
                 {"ctx": 65536, "vision": "cpu", "mtp": True}, {"ctx": "x"}, None):
        req = {"schema": BH.REQUEST_SCHEMA, "id": "r%s" % time.monotonic_ns(), "action": "reconfigure",
               "requested_at": time.time(), "profile": prof}
        path.write_text(json.dumps(req), encoding="utf-8")
        assert h.take_request() is None
        assert h.report["requests"][req["id"]] == "IGNORED_INVALID_OR_STALE"


def test_host_reconfigure_to_the_running_profile_does_not_restart(tmp_path):
    h = _host(tmp_path)

    class Mgr:
        owns_instance = True
    h.mgr = Mgr()
    h.stop_brain = lambda: pytest.fail("must not stop")
    h.reconfigure(BP.DEFAULT_KEY)
    assert h.report["last_switch"]["result"] == "UNCHANGED"


# ---- profile-aware readiness ---------------------------------------------------------------------------------------
class FakeMgr:
    def __init__(self, cfg, modalities):
        self.cfg, self.modalities = cfg, modalities

    def status(self):
        return Readiness(R.READY, "u", live_identity={"server": {"modalities": self.modalities}},
                         detail=RP.profile_id((self.cfg["runtime"]["ctx"],
                                               "gpu" if self.cfg["runtime"].get("vision_enabled") else "off",
                                               bool(self.cfg["model"].get("mtp_draft")))))


def test_readiness_follows_the_host_profile_and_its_live_vision(tmp_path):
    rep = {"profile": RP.describe(BP.config_for(frozen(), (65536, "gpu", False)))}
    mods = {"vision": True}
    st = BP.ProfileStatus(frozen(), tmp_path, host_report=lambda: (rep, True), choice_dir=tmp_path,
                          manager_factory=lambda cfg: FakeMgr(cfg, mods))
    r = st()
    assert r.state == R.READY and r.detail == "c64k-visgpu-mtpoff"
    mods["vision"] = False
    assert st().state == R.IDENTITY_MISMATCH and st().detail == "VISION_NOT_LIVE"
    rep["profile"] = RP.describe(BP.config_for(frozen(), (32768, "off", False)))
    mods["vision"] = True
    assert st().detail == "VISION_UNEXPECTED"
    rep["profile"] = {"id": "x", "ctx": 99, "vision": "gpu", "mtp": False}
    assert st().state == R.IDENTITY_MISMATCH and st().detail == "PROFILE_UNKNOWN"


def test_without_a_live_host_readiness_uses_the_persisted_choice(tmp_path):
    BP.write_choice(tmp_path, (16384, "off", True))
    st = BP.ProfileStatus(frozen(), tmp_path, host_report=lambda: (None, False), choice_dir=tmp_path,
                          manager_factory=lambda cfg: FakeMgr(cfg, {"vision": False}))
    assert st().detail == "c16k-visoff-mtpon"


def test_readiness_reads_the_host_profile_once_per_call(tmp_path):
    """R1-02: the config and the manager cache come from one read; a report change between reads cannot cache the
    wrong config under the new profile, and an unknown profile is PROFILE_UNKNOWN, never an exception."""
    reps = iter([RP.describe(BP.config_for(frozen(), k)) for k in ((32768, "gpu", False), (65536, "off", False))]
                + [{"id": "x", "ctx": 99, "vision": "gpu", "mtp": False}])
    built = []
    st = BP.ProfileStatus(frozen(), tmp_path, host_report=lambda: ({"profile": next(reps)}, True), choice_dir=tmp_path,
                          manager_factory=lambda cfg: built.append(cfg) or FakeMgr(cfg, {"vision": True}))
    assert st().detail == "c32k-visgpu-mtpoff"
    assert [c["runtime"]["ctx"] for c in built] == [32768]
    r = st()
    assert r.detail == "VISION_UNEXPECTED" and [c["runtime"]["ctx"] for c in built] == [32768, 65536]
    assert st().detail == "PROFILE_UNKNOWN"


def test_frozen_profile_argv_is_unchanged_by_this_milestone():
    cfg = frozen()
    assert BP.config_for(cfg, RP.FROZEN_KEY) is cfg
    argv = R.expected_argv(cfg)
    assert "--mmproj" in argv and "-md" in argv and "--no-mmproj-offload" not in argv


# ---- images -------------------------------------------------------------------------------------------------------
def test_image_parse_checks_type_size_and_shape():
    imgs = IMG.parse([{"name": "a.png", "mime": "image/png", "data": b64(PNG)}])
    assert imgs[0].data == PNG and IMG.placeholder(imgs[0]) == "[Attached image: a.png]"
    cases = [
        ([], "IMAGES_INVALID"), ("x", "IMAGES_INVALID"),
        ([{"name": "a", "mime": "image/png", "data": b64(PNG)}] * 3, "IMAGES_INVALID"),
        ([{"name": "a", "mime": "image/gif", "data": b64(PNG)}], "IMAGE_TYPE_UNSUPPORTED"),
        ([{"name": "a", "mime": "image/png", "data": b64(JPEG)}], "IMAGE_TYPE_MISMATCH"),
        ([{"name": "a", "mime": "image/png", "data": "!!"}], "IMAGE_DATA_INVALID"),
        ([{"name": "a\nb", "mime": "image/png", "data": b64(PNG)}], "IMAGE_NAME_INVALID"),
        ([{"name": "a", "mime": "image/png", "data": b64(PNG), "x": 1}], "IMAGES_INVALID"),
        ([{"name": "a", "mime": "image/png", "data": b64(PNG + b"\x00" * IMG.MAX_TOTAL_BYTES)}], "IMAGES_TOO_LARGE"),
    ]
    for raw, code in cases:
        with pytest.raises(IMG.ImageRejected) as e:
            IMG.parse(raw)
        assert e.value.code == code


def test_a_full_image_turn_fits_the_worker_frame():
    from uri_core.client_contracts import FRAME_LIMIT
    half = IMG.MAX_TOTAL_BYTES // 2
    frame = {"command": "oi_turn", "session_id": SID, "text": "x" * 20000, "depth": "auto",
             "images": [{"name": "n" * 120, "mime": "image/png", "data": b64(PNG + b"\x00" * (half - len(PNG)))}] * 2}
    assert len(json.dumps(frame).encode()) < FRAME_LIMIT


@pytest.fixture
def fake():
    with FakeLlama() as f:
        yield f


def _bridge(fake, tmp_path, vision=True, ready="READY", host=None):
    cfg = {"model": {"id": "qwen-test"}, "runtime": {"port": 18470, "ctx": 32768, "vision_enabled": vision}}
    status = lambda: Readiness(ready, fake.url, model_id="qwen-test")
    o = Orchestrator(client=BC.BrainClient(fake.url), core=FakeCore(), brain_selection={}, ledger=TaskLedger(tmp_path),
                     capability_ids={"remember_fact"}, readiness=status, harness_statuses=lambda: [])
    events = []
    requests = []
    host_state = host if host is not None else {"rep": None}

    def host_request(action, profile=None):
        req = BH.write_host_request(tmp_path, action, profile)
        requests.append(req)
        return req
    b = IntegratedTurns(orchestrator=o, cfg=cfg, status=status, write_event=events.append,
                        host_report=lambda: (host_state["rep"], host_state["rep"] is not None),
                        host_request=host_request, choice_dir=tmp_path)
    return b, events, requests, host_state


def test_image_turn_reaches_the_brain_as_image_url_and_history_keeps_a_placeholder(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "A cat.")], "finish": "stop"})
    b, events, _, _ = _bridge(fake, tmp_path)
    r = b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "What is in this picture?",
                             "depth": "auto", "images": [{"name": "cat.png", "mime": "image/png", "data": b64(PNG)}]})
    b.wait(10)
    body = fake.requests[-1]
    content = body["messages"][-1]["content"]
    assert content[0] == {"type": "text", "text": "What is in this picture?"}
    assert content[1]["image_url"]["url"] == "data:image/png;base64," + b64(PNG)
    assert b.history[SID][0]["content"] == "What is in this picture?\n[Attached image: cat.png]"
    assert all(isinstance(m["content"], str) for m in b.history[SID])
    assert r["accepted"] and any(e["type"] == "answer.done" for e in events)


def test_image_with_vision_off_or_brain_not_ready_is_refused_not_dropped(fake, tmp_path):
    img = [{"name": "a.png", "mime": "image/png", "data": b64(PNG)}]
    # R4-01: a vision profile whose server is not READY is "not ready", never "Vision is off".
    for vision, ready, code in ((False, "READY", "VISION_OFF"), (False, "LOADING", "VISION_OFF"),
                                (True, "LOADING", "VISION_NOT_READY"), (True, "FAILED", "VISION_NOT_READY"),
                                (True, "IDENTITY_MISMATCH", "VISION_NOT_READY")):
        b, _, _, _ = _bridge(fake, tmp_path, vision=vision, ready=ready)
        with pytest.raises(BridgeRefused) as e:
            b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "what is this", "depth": "auto",
                                 "images": img})
        assert e.value.code == code, (vision, ready)
    assert fake.requests == []


def test_image_with_an_action_request_is_refused_with_a_reason(fake, tmp_path):
    b, events, _, _ = _bridge(fake, tmp_path)
    b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "Remember that this is my car",
                         "depth": "auto", "images": [{"name": "a.png", "mime": "image/png", "data": b64(PNG)}]})
    b.wait(10)
    errs = [e["data"] for e in events if e["type"] == "error"]
    assert errs and errs[0]["code"] == "IMAGE_ACTION_UNSUPPORTED"
    assert fake.requests == []


def test_image_while_a_clarification_waits_is_refused_with_its_own_code(fake, tmp_path):
    """R4-03: the answer to URI's question goes to Core (no images): its own code, not 'ask about the image'."""
    b, _, _, _ = _bridge(fake, tmp_path)
    b.pending["t-clar"] = {"session_id": SID, "env": {"clarification": {"question": "Which file?"}}}
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "the second one", "depth": "auto",
                             "images": [{"name": "a.png", "mime": "image/png", "data": b64(PNG)}]})
    assert e.value.code == "IMAGE_DURING_CLARIFICATION"
    assert fake.requests == [] and "t-clar" in b.pending


def test_brain_restart_never_carries_a_reconfigure(fake, tmp_path):
    """R3-05: a profile switch has its own validated command; brain_restart 'reconfigure' is ACTION_INVALID."""
    b, _, requests, _ = _bridge(fake, tmp_path)
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_restart", {"command": "brain_restart", "action": "reconfigure"})
    assert e.value.code == "ACTION_INVALID" and requests == []


def test_image_with_a_draft_request_is_refused_not_answered_in_chat(fake, tmp_path):
    """R1-01: a request the draft desk takes as a text task cannot carry the picture into a draft."""
    b, _, _, _ = _bridge(fake, tmp_path)
    img = [{"name": "a.png", "mime": "image/png", "data": b64(PNG)}]
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "Write an email to Bob describing this "
                             "picture", "depth": "auto", "images": img})
    assert e.value.code == "IMAGE_DRAFT_UNSUPPORTED" and fake.requests == [] and not b.desk.drafts


def test_history_is_fitted_to_the_active_context(fake, tmp_path):
    """R1-03: after a shrink the Brain sees only the most recent part that fits; the stored history is unchanged."""
    b, _, _, _ = _bridge(fake, tmp_path)
    b.cfg = dict(b.cfg, runtime=dict(b.cfg["runtime"], ctx=16384))
    turn = "y" * 9000
    b.history[SID] = [{"role": r, "content": "%d %s" % (i, turn)} for i, r in enumerate(["user", "assistant"] * 6)]
    fitted = b._fit_history(b.history[SID], "next question", None)
    budget = (16384 - IW.CONTEXT_RESERVE_TOKENS) * IW.CHARS_PER_TOKEN
    assert fitted == b.history[SID][-len(fitted):] and fitted[0]["role"] == "user"
    assert 0 < sum(len(m["content"]) for m in fitted) <= budget < sum(len(m["content"]) for m in b.history[SID])
    assert len(b.history[SID]) == 12
    with_images = b._fit_history(b.history[SID], "next question", (1, 2))
    assert len(with_images) <= len(fitted)
    b.cfg = dict(b.cfg, runtime=dict(b.cfg["runtime"], ctx=131072))
    assert b._fit_history(b.history[SID], "q", None) == b.history[SID]


def test_context_reserve_covers_the_worst_case_answer_turn():
    """r3 R1-02: the reserve holds the NORMAL answer, the full system and capability text and the memory cap."""
    from uri_operational_intelligence import answer as A
    from uri_operational_intelligence import reasoning_policy as RPOL
    caps = sorted(A.CAPABILITY_WORDS) + ["external_harness_task"]
    msgs = A.build_messages("", capability_ids=caps, memory={"status": "available", "facts": [], "truncated": False})
    system_chars = sum(len(m["content"]) for m in msgs)
    assert system_chars <= 4096
    assert RPOL.MAX_TOKENS["normal"] <= 4000 and RPOL.tier_params(RPOL.NORMAL)["max_tokens"] <= 4000
    assert IW.CONTEXT_RESERVE_TOKENS >= 4000 + 4096 // IW.CHARS_PER_TOKEN + 8192 // IW.CHARS_PER_TOKEN
    assert IW.IMAGE_TOKENS * 28 * 28 >= 1280 * 1280


def test_no_switch_while_the_host_loads_or_stops(fake, tmp_path):
    """R1-05: the host reads only stop requests while it loads; a switch would wait unread and go stale."""
    for state in ("STARTING_HOST", "STARTING", "CALIBRATING", "STOPPING"):
        b, _, requests, host = _bridge(fake, tmp_path, host={"rep": _live((32768, "gpu", False), state=state)})
        with pytest.raises(BridgeRefused) as e:
            b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": False, "context": 65536,
                                           "speed": False})
        assert e.value.code == "BRAIN_LOADING" and requests == [], state


# ---- profile set via the bridge ------------------------------------------------------------------------------------
def _live(desc_key, state="READY"):
    return {"state": state, "profile": RP.describe(BP.config_for(frozen(), desc_key)), "requests": {}}


def test_profile_set_writes_choice_and_one_reconfigure_request(fake, tmp_path):
    b, _, reqs, host = _bridge(fake, tmp_path)
    host["rep"] = _live(BP.DEFAULT_KEY)
    out = b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": False, "context": 65536,
                                         "speed": False})
    assert out["requested"] == "reconfigure" and out["profile"] == "c64k-visoff-mtpoff"
    assert len(reqs) == 1 and reqs[0]["profile"] == {"ctx": 65536, "vision": "off", "mtp": False}
    # R1-02: the worker never persists the choice; the host writes it when it takes the switch
    assert BP.read_choice(tmp_path) == (BP.DEFAULT_KEY, "default", None)
    # a second change while the first is pending is refused, and a turn is gated too
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": True, "context": 32768,
                                       "speed": False})
    assert e.value.code == "BRAIN_REQUEST_PENDING"
    with pytest.raises(BridgeRefused) as e:
        b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "hi", "depth": "auto"})
    assert e.value.code == "BRAIN_RESTARTING"
    state = b.handle("brain_profile_get", {"command": "brain_profile_get"})["state"]
    assert state["pending_request"] is True and state["choice"]["id"] == RP.profile_id(BP.DEFAULT_KEY)
    assert state["active"]["id"] == RP.profile_id(BP.DEFAULT_KEY)          # truthful: still the running one
    host["rep"]["requests"] = {reqs[0]["id"]: "DONE"}
    assert b.handle("brain_profile_get", {"command": "brain_profile_get"})["state"]["pending_request"] is False


def test_profile_set_same_profile_is_unchanged_and_refusals(fake, tmp_path):
    b, _, reqs, host = _bridge(fake, tmp_path)
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": True, "context": 32768, "speed": False})
    assert e.value.code == "BRAIN_HOST_NOT_RUNNING"
    host["rep"] = _live(BP.DEFAULT_KEY)
    out = b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": True, "context": 32768,
                                         "speed": False})
    assert out["unchanged"] is True and reqs == []
    for cmd, code in [({"vision": True, "context": 32768, "speed": True}, "SPEED_NEEDS_VISION_OFF"),
                      ({"vision": True, "context": 131072, "speed": False}, "PROFILE_NOT_OFFERED"),
                      ({"vision": 1, "context": 32768, "speed": False}, "CONTROL_INVALID")]:
        with pytest.raises(BridgeRefused) as e:
            b.handle("brain_profile_set", dict(cmd, command="brain_profile_set"))
        assert e.value.code == code
    host["rep"]["profile"] = {"id": "x"}
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": False, "context": 65536,
                                       "speed": False})
    assert e.value.code == "PROFILE_UNKNOWN"


def test_shrinking_below_the_live_conversation_needs_confirmation_and_history_survives(fake, tmp_path):
    b, _, reqs, host = _bridge(fake, tmp_path)
    host["rep"] = _live((65536, "off", False))
    b.history[SID] = [{"role": "user", "content": "x" * 80000}, {"role": "assistant", "content": "ok"}]
    cmd = {"command": "brain_profile_set", "vision": False, "context": 16384, "speed": False}
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", cmd)
    assert e.value.code == "CONTEXT_SMALLER_THAN_CONVERSATION" and reqs == []
    out = b.handle("brain_profile_set", dict(cmd, confirm_shrink=True))
    assert out["requested"] == "reconfigure"
    assert b.history[SID][0]["content"] == "x" * 80000      # the switch never touches the conversation


def _kept_at(b, ctx):
    """How many history entries _fit_history sends the Brain at `ctx` (the bridge itself is left unchanged)."""
    b._active_cfg = lambda: {"runtime": {"ctx": ctx}}
    try:
        return len(b._fit_history(b.history[SID], "", ()))
    finally:
        del b._active_cfg


def test_shrink_check_uses_the_same_budget_as_the_history_sent_to_the_brain(fake, tmp_path):
    """R1-01 (r3): a mid-sized conversation that fits 32K but not 16K must need confirm_shrink, because at 16K
    _fit_history sends the Brain only part of it. The check and the budget agree exactly at the boundary."""
    b, _, reqs, host = _bridge(fake, tmp_path)
    host["rep"] = _live((32768, "off", False))
    b.history[SID] = [m for i in range(3) for m in ({"role": "user", "content": f"doc{i}" + "u" * 14996},
                                                     {"role": "assistant", "content": "a" * 1000})]
    full = len(b.history[SID])
    cmd = {"command": "brain_profile_set", "vision": False, "context": 16384, "speed": False}
    assert _kept_at(b, 32768) == full and _kept_at(b, 16384) < full
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", cmd)
    assert e.value.code == "CONTEXT_SMALLER_THAN_CONVERSATION" and reqs == []
    # r3 R2-01: a conversation that fills the 16K budget exactly still needs the confirmation, because the next
    # turn (its text and up to two images) would push part of it out.
    budget = (16384 - IW.CONTEXT_RESERVE_TOKENS) * IW.CHARS_PER_TOKEN
    b.history[SID] = [{"role": "user", "content": "q" * (budget - 1000)}, {"role": "assistant", "content": "a" * 1000}]
    assert _kept_at(b, 16384) == 2
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", cmd)
    assert e.value.code == "CONTEXT_SMALLER_THAN_CONVERSATION"
    # boundary: a conversation that leaves room for the next turn switches; one more character needs the confirmation
    edge = (16384 - IW.CONTEXT_RESERVE_TOKENS - IW.NEXT_TURN_TOKENS) * IW.CHARS_PER_TOKEN
    b.history[SID] = [{"role": "user", "content": "q" * (edge - 1000)}, {"role": "assistant", "content": "a" * 1000}]
    assert b.handle("brain_profile_set", cmd)["requested"] == "reconfigure"
    b._restart = None
    host["rep"] = _live((32768, "off", False))
    b.history[SID][1]["content"] += "a"
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", cmd)
    assert e.value.code == "CONTEXT_SMALLER_THAN_CONVERSATION"
    assert b.handle("brain_profile_set", dict(cmd, confirm_shrink=True))["requested"] == "reconfigure"


def test_growing_the_context_never_asks_to_confirm_a_shrink(fake, tmp_path):
    b, _, reqs, host = _bridge(fake, tmp_path)
    host["rep"] = _live((16384, "off", False))
    b.history[SID] = [{"role": "user", "content": "x" * 300000}, {"role": "assistant", "content": "ok"}]
    out = b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": False, "context": 32768,
                                         "speed": False})
    assert out["requested"] == "reconfigure" and len(reqs) == 1


def test_profile_set_is_refused_while_a_turn_runs(fake, tmp_path):
    fake.scripts.append({"chunks": [("answer", "slow")], "finish": "stop", "delay": 0.5})
    b, _, reqs, host = _bridge(fake, tmp_path)
    host["rep"] = _live(BP.DEFAULT_KEY)
    b.handle("oi_turn", {"command": "oi_turn", "session_id": SID, "text": "What is VRAM?", "depth": "auto"})
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": False, "context": 65536,
                                       "speed": False})
    assert e.value.code == "TURN_IN_PROGRESS" and reqs == []
    assert b.handle("brain_profile_get", {"command": "brain_profile_get"})["offer"]["options"]
    b.wait(10)


def test_health_reports_active_profile_and_live_vision(fake, tmp_path):
    b, _, _, host = _bridge(fake, tmp_path)
    host["rep"] = _live((65536, "gpu", False))
    h = b.handle("brain_health", {"command": "brain_health"})
    assert h["profile"]["active"]["id"] == "c64k-visgpu-mtpoff" and h["profile"]["active"]["vision"] is True
    assert h["profile"]["vision_live"] is True and h["profile"]["switching"] is None
    host["rep"]["switch"] = {"from": {"id": "a"}, "to": {"id": "b"}}
    assert b.handle("brain_health", {"command": "brain_health"})["profile"]["switching"] == {"from": "a", "to": "b"}


# ---- review R1 repairs ---------------------------------------------------------------------------------------------
def _contended_host(tmp_path, monkeypatch, foreign_mib=2200.0, real_quiet=False):
    """A host whose census shows a foreign GPU consumer: 64K + vision does not fit, 32K + vision does."""
    sys.path.insert(0, str(Path(R.REPO_ROOT) / "scripts"))
    import ws_brain_host as H
    monkeypatch.setattr(H, "GPU_POLL_S", 0.2)
    if not real_quiet:
        monkeypatch.setattr(H, "QUIET_S", 0.0)
    census = lambda: {"ok": True, "card_mib": 16368, "unattributed_mib": 0.0, "t": time.time(), "sample_s": 0.1,
                      "processes": [{"pid": 999999, "name": "chrome.exe", "dedicated_mib": foreign_mib}]}
    (tmp_path / "rep").mkdir(exist_ok=True)
    h = H.Host(tmp_path / "rep", minutes=1.0, override=False, state_dir=tmp_path / "s", census=census,
               lease_dir=tmp_path / "l")
    from uri_operational_intelligence import gpu_lease as G
    assert G.assess_fit(census(), required_mib=RP.MEASURED_MIB[(65536, "gpu", False)])["verdict"] == G.CONTENDED
    assert G.assess_fit(census(), required_mib=RP.MEASURED_MIB[BP.DEFAULT_KEY])["verdict"] != G.CONTENDED
    return H, h


def _wait_for(pred, timeout=10.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if pred():
            return True
        time.sleep(0.05)
    return False


def test_r1_01_a_switch_waiting_for_gpu_takes_a_new_choice_and_goes_back(tmp_path, monkeypatch):
    """R1-01: a reconfigure to an offered profile that does not fit waits for the GPU; a second reconfigure taken
    during that wait retargets the pending start (back to the previous profile), so the user is never locked out."""
    import threading
    H, h = _contended_host(tmp_path, monkeypatch)

    class Mgr:
        owns_instance = True
    h.mgr, h.lease = Mgr(), object()
    h.stop_brain = lambda: setattr(h, "mgr", None)
    started = []
    h.start_brain = lambda: h.wait_for_gpu() and not started.append(h.report["profile"]["id"])
    first = BH.write_host_request(tmp_path / "rep", "reconfigure", (65536, "gpu", False))
    assert h.take_request() == "reconfigure"
    t = threading.Thread(target=h.reconfigure, args=(h.request_profile,), daemon=True)
    t.start()
    assert _wait_for(lambda: h.report.get("detail") == "GPU_CONTENDED")
    assert h.report["state"] == "WAITING_FOR_GPU" and h.report["switch"]["to"]["id"] == "c64k-visgpu-mtpoff"
    back = BH.write_host_request(tmp_path / "rep", "reconfigure", BP.DEFAULT_KEY)
    t.join(10)
    assert not t.is_alive(), "the second request must be taken during the GPU wait"
    assert h.report["requests"][back["id"]] == "ACCEPTED"
    assert h.report["requests"][first["id"]] == "SUPERSEDED"
    assert started == [RP.profile_id(BP.DEFAULT_KEY)] and h.report["profile"]["id"] == RP.profile_id(BP.DEFAULT_KEY)
    assert h.required_mib == RP.MEASURED_MIB[BP.DEFAULT_KEY]
    assert h.report["last_switch"]["result"] == "DONE" and "switch" not in h.report
    assert BP.read_choice(tmp_path / "rep")[0] == BP.DEFAULT_KEY
    h.finish_request()
    assert h.report["requests"][back["id"]] == "DONE"


def test_r3_01_going_back_from_a_target_too_large_starts_without_a_quiet_window(tmp_path, monkeypatch):
    """R3-01: with the real QUIET_S, a target that only fails because of its own size (the same foreign use fits the
    previous profile) is not foreign contention: going back starts at once, no 'another job has finished' wait is
    shown, and nothing is written to the machine-wide contention record."""
    import threading
    from uri_operational_intelligence import gpu_lease as G
    H, h = _contended_host(tmp_path, monkeypatch, real_quiet=True)
    assert H.QUIET_S >= 60

    class Mgr:
        owns_instance = True
    h.mgr, h.lease = Mgr(), object()
    h.stop_brain = lambda: setattr(h, "mgr", None)
    started = []
    h.start_brain = lambda: h.wait_for_gpu() and not started.append(h.report["profile"]["id"])
    BH.write_host_request(tmp_path / "rep", "reconfigure", (65536, "gpu", False))
    assert h.take_request() == "reconfigure"
    t = threading.Thread(target=h.reconfigure, args=(h.request_profile,), daemon=True)
    t.start()
    assert _wait_for(lambda: h.report.get("detail") == "GPU_CONTENDED")
    BH.write_host_request(tmp_path / "rep", "reconfigure", BP.DEFAULT_KEY)
    t.join(10)
    assert not t.is_alive(), "going back must not wait the quiet window"
    assert started == [RP.profile_id(BP.DEFAULT_KEY)]
    assert all(e.get("detail") != "GPU_QUIET_WINDOW" for e in h.report["history"])
    assert G.last_contention(tmp_path / "l") is None


def test_r3_01_a_foreign_job_that_ends_still_gets_the_quiet_window(tmp_path, monkeypatch):
    """R3-01 counterpart: foreign use that blocks every offered profile is contention; when it ends the host still
    waits the real quiet window and the machine-wide record is written."""
    import threading
    from uri_operational_intelligence import gpu_lease as G
    sys.path.insert(0, str(Path(R.REPO_ROOT) / "scripts"))
    import ws_brain_host as H
    monkeypatch.setattr(H, "GPU_POLL_S", 0.2)
    use = {"mib": 14000.0}
    census = lambda: {"ok": True, "card_mib": 16368, "unattributed_mib": 0.0, "t": time.time(), "sample_s": 0.1,
                      "processes": [{"pid": 999999, "name": "llama-server.exe", "dedicated_mib": use["mib"]}]}
    (tmp_path / "rep").mkdir(exist_ok=True)
    h = H.Host(tmp_path / "rep", minutes=1.0, override=False, state_dir=tmp_path / "s", census=census,
               lease_dir=tmp_path / "l")
    box = {}
    t = threading.Thread(target=lambda: box.update(r=h.wait_for_gpu()), daemon=True)
    t.start()
    assert _wait_for(lambda: h.report.get("detail") == "GPU_CONTENDED")
    assert G.last_contention(tmp_path / "l") is not None
    use["mib"] = 300.0
    assert _wait_for(lambda: h.report.get("detail") == "GPU_QUIET_WINDOW")
    assert "another job has finished" in h.report["explain"] and t.is_alive()
    h.deadline = time.monotonic() - 1          # end the host; the wait returns without a start
    t.join(10)
    assert box.get("r") is False


def test_r1_01_the_worker_accepts_a_new_choice_while_the_host_waits_for_gpu(fake, tmp_path):
    """R1-01: while the host has taken the switch and only waits for GPU memory, brain_profile_set is not refused
    with BRAIN_REQUEST_PENDING, and the profile state says the host is waiting. An untaken request is never replaced."""
    b, _, reqs, host = _bridge(fake, tmp_path)
    host["rep"] = _live(BP.DEFAULT_KEY)
    b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": True, "context": 65536, "speed": False})
    # untaken by the host yet: still refused (the first request would be overwritten unread)
    host["rep"] = dict(_live((65536, "gpu", False), state="WAITING_FOR_GPU"))
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": True, "context": 32768,
                                       "speed": False})
    assert e.value.code == "BRAIN_REQUEST_PENDING"
    host["rep"]["requests"] = {reqs[0]["id"]: "ACCEPTED"}
    host["rep"]["switch"] = {"from": {"id": RP.profile_id(BP.DEFAULT_KEY)}, "to": {"id": "c64k-visgpu-mtpoff"}}
    state = b.handle("brain_profile_get", {"command": "brain_profile_get"})["state"]
    assert state["host_waiting"] is True and state["host_state"] == "WAITING_FOR_GPU"
    out = b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": True, "context": 32768,
                                         "speed": False})
    assert out["requested"] == "reconfigure" and reqs[-1]["profile"] == {"ctx": 32768, "vision": "gpu", "mtp": False}
    # while the Brain loads, a change is still refused
    host["rep"]["state"] = "LOADING"
    host["rep"]["requests"] = {reqs[-1]["id"]: "ACCEPTED"}
    with pytest.raises(BridgeRefused) as e:
        b.handle("brain_profile_set", {"command": "brain_profile_set", "vision": False, "context": 32768,
                                       "speed": False})
    assert e.value.code == "BRAIN_REQUEST_PENDING"


def test_r1_02_choice_is_written_only_when_the_host_takes_the_switch(tmp_path):
    """R1-02: a refused switch (attached instance) leaves the previous choice; an accepted one persists it; the
    switch outcome carries what the UI needs to say it (from, to, result, explain)."""
    h = _host(tmp_path)
    BP.write_choice(tmp_path / "rep", BP.DEFAULT_KEY)

    class Attached:
        owns_instance = False
    h.mgr = Attached()
    h.reconfigure((65536, "off", False))
    assert h.report["last_switch"]["result"] == "REFUSED_ATTACHED"
    assert h.report["last_switch"]["from"] == RP.profile_id(BP.DEFAULT_KEY)
    assert BP.read_choice(tmp_path / "rep")[0] == BP.DEFAULT_KEY

    class Owned:
        owns_instance = True
    h.mgr, h.lease = Owned(), object()
    h.stop_brain = lambda: setattr(h, "mgr", None)

    def start():
        h.set("FAILED", detail="X", explain="The Brain did not become ready (X).")
        return False
    h.start_brain = start
    h.reconfigure((65536, "off", False))
    assert BP.read_choice(tmp_path / "rep")[0] == (65536, "off", False)
    ls = h.report["last_switch"]
    assert ls["result"] == "NOT_READY" and ls["from"] == RP.profile_id(BP.DEFAULT_KEY)
    assert ls["to"] == "c64k-visoff-mtpoff" and "did not become ready" in ls["explain"]


def test_r1_02_profile_state_reports_switch_outcome_request_result_and_choice_errors(fake, tmp_path):
    b, _, _, host = _bridge(fake, tmp_path)
    host["rep"] = _live((65536, "gpu", False), state="FAILED")
    host["rep"]["explain"] = "The Brain did not become ready (X)."
    host["rep"]["last_switch"] = {"from": "c32k-visgpu-mtpoff", "to": "c64k-visgpu-mtpoff", "result": "NOT_READY"}
    host["rep"]["last_request"] = {"id": "r1", "action": "reconfigure", "result": "IGNORED_INVALID_OR_STALE",
                                   "t": 1.0, "extra": "x"}
    host["rep"]["profile_choice"] = {"source": "default", "error": "CHOICE_UNREADABLE"}
    (tmp_path / BP.CHOICE_FILE).write_text("{bad", encoding="utf-8")
    state = b.handle("brain_profile_get", {"command": "brain_profile_get"})["state"]
    assert state["host_state"] == "FAILED" and "did not become ready" in state["host_explain"]
    assert state["last_switch"]["result"] == "NOT_READY" and state["host_waiting"] is False
    assert state["last_request"] == {"id": "r1", "action": "reconfigure", "result": "IGNORED_INVALID_OR_STALE",
                                     "t": 1.0}
    assert state["choice"]["error"] == "CHOICE_UNREADABLE" and state["host_choice_error"] == "CHOICE_UNREADABLE"
