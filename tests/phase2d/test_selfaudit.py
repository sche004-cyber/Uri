"""Phase 2D self-audit (author's own attack, NOT an independent audit). Each case names the control it probes.
Cases already pinned by earlier suites are referenced, not duplicated. SYNTHETIC executor; REAL server where used."""
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from phase2b.conftest import CLAUDE, CODEX, uid
from phase2d.conftest import ROOT, fixture_record, signed_record, trust_for
from uri_core.client_runtime.turn_runner import TurnError
from uri_supervisor.ledger import LedgerError
from uri_supervisor_bridge.bridge import NOT_STARTED, SupervisorBridge
from uri_supervisor_bridge.qualification import compose_client
from phase2d.conftest import signed_record, trust_for

TEXT = "use the harness to write a greeting into out.txt"


# -- modified intent / approval digest after confirmation (real server, protocol level) ----------------------------

def test_rogue_ui_editing_the_approval_envelope_cannot_change_what_runs(stack, monkeypatch):
    """A UI that holds the approval envelope and edits the arguments: the worker approves by digest, the server issues
    a ticket for ITS pending arguments, and the bridge re-verifies the arguments it will run against that ticket."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    entry = stack.service.pending[turn["turn_id"]]
    entry[3]["approval_request"]["arguments"]["inputs"]["instruction"] = "write a greeting and delete everything"
    final = stack.decide(turn, True)
    assert final["code"] == "SETTLED_FAILED" and stack.tasks() == 0           # ARGUMENT_DIGEST_MISMATCH before any task


def test_rogue_ui_editing_the_approval_digest_is_refused_by_the_server(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT)
    entry = stack.service.pending[turn["turn_id"]]
    entry[3]["approval_request"]["approval_digest"] = "f" * 64
    with pytest.raises(TurnError, match="APPROVAL_DIGEST_MISMATCH"):
        stack.decide(turn, True)
    assert stack.tasks() == 0


def test_provider_swap_inside_the_pending_record_is_refused_before_any_executor(stack, monkeypatch):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    turn = stack.start(TEXT, reasoning=CLAUDE)
    text, session, reasoning, env = stack.service.pending[turn["turn_id"]]
    stack.service.pending[turn["turn_id"]] = (text, session, CODEX, env)   # UI/worker memory tampered after begin
    final = stack.decide(turn, True)
    assert final["code"] == "SETTLED_FAILED" and stack.tasks() == 0         # AUTHORITY_SELECTION_MISMATCH (D-C1)


# -- forged ticket at the protocol boundary ---------------------------------------------------------------------------

def test_forged_ticket_handed_to_the_worker_is_a_schema_violation(stack):
    with pytest.raises(TurnError, match="COMMAND_SCHEMA"):
        stack.service.handle("turn_decide", {"command": "turn_decide", "turn_id": uid(), "approve": True, "ticket": {"forged": 1}})
    with pytest.raises(TurnError, match="COMMAND_SCHEMA"):
        stack.service.handle("turn_execute", {"command": "turn_execute", "ticket": {"forged": 1}})


# -- stale qualification: binary swap between qualification and use ------------------------------------------------

def test_executable_replaced_after_qualification_is_refused_at_both_layers(tmp_path, authority, monkeypatch):
    """Mirrors the real case (npm `codex.CMD` shim): the qualified executable is a .cmd launcher. Replacing its bytes
    after qualification is refused by the bridge pin (if the bridge already composed) and by re-validation (next load)."""
    from phase2b.conftest import FAKE
    from uri_supervisor_bridge.qualification import build_record, write_record
    client = tmp_path / "client"
    shim = tmp_path / "fake-harness.cmd"
    shim.write_bytes(("@\"%s\" \"%s\" %%*" % (sys.executable, FAKE)).encode("ascii") + bytes([13, 10]))
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": [None]}))
    rec = signed_record(client, provider="claude_code", level="FIXTURE_ONLY", spec_id="generic_ndjson", executable=shim,
                        executable_args=[], version="0.0.1", models=[None], evidence_path=ev, qualified_by="t",
                        pinned_files={}, resolve_pins={})
    write_record(client, rec)
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert comp.qualified() == ["claude_code"], comp.report
    b = SupervisorBridge(client, registry=comp.registry, executors=comp.executors, timeout_s=10, inactivity_s=3)
    try:
        shim.write_bytes(shim.read_bytes() + b"rem swapped" + bytes([13, 10]))   # swapped AFTER composition
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, CLAUDE, now=now))
        # Since review round 2 (R2-1) the registry re-validates the record before the bridge's own pin check, so the
        # first refusal is the registry's; the bridge-level pin is asserted directly as the second layer.
        assert out[0] == "failed" and out[2] in (NOT_STARTED + "HARNESS_HARNESS_NOT_USABLE", NOT_STARTED + "EXECUTOR_BINARY_HASH_MISMATCH")
        assert b.L.q1("SELECT COUNT(*) FROM task")[0] == 0
        assert comp.executors["claude_code"].revalidate() == "EXECUTABLE_HASH_MISMATCH"
        from uri_supervisor_bridge.bridge import _file_sha256
        assert _file_sha256(comp.executors["claude_code"].resolved_executable) != comp.executors["claude_code"].executable_sha256
    finally:
        b.close()
    assert compose_client(client, trust=trust_for(client), allow_fixture=True).report[0]["reason"] == "EXECUTABLE_HASH_MISMATCH"


# -- corrupted persisted state ----------------------------------------------------------------------------------------

def test_corrupted_ledger_refuses_the_bridge_and_runs_nothing(tmp_path):
    from phase2b.conftest import fake_binding, fake_registry
    client = tmp_path / "client"
    db = client / "control" / "supervisor" / "ledger.db"
    db.parent.mkdir(parents=True)
    db.write_bytes(b"this is not a sqlite database" * 100)
    with pytest.raises((LedgerError, sqlite3.DatabaseError)):
        SupervisorBridge(client, registry=fake_registry("claude_code"), executors={"claude_code": fake_binding("claude_code")})


def test_corrupted_qualification_record_runs_nothing(tmp_path, authority, monkeypatch):
    client = tmp_path / "client"
    path, rec = fixture_record(client, "claude_code")
    path.write_bytes(path.read_bytes()[:-20])
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert comp.executors == {} and comp.report[0]["status"] == "INVALIDATED"
    b = SupervisorBridge(client, registry=comp.registry, executors=comp.executors)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, CLAUDE, now=now))
        assert out[0] == "failed" and out[2].startswith(NOT_STARTED) and b.L.q1("SELECT COUNT(*) FROM task")[0] == 0
    finally:
        b.close()


# -- duplicate submit / duplicate resume ----------------------------------------------------------------------------

def test_duplicate_submit_of_a_verified_intent_is_blocked_by_the_server_ledger(stack, monkeypatch):
    """Replayed client state after a verified run: INTENT_ALREADY_EXECUTED (frozen guard), zero new tasks."""
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    session = uid()
    before = stack.persistence.snapshot(session, []).model_dump()
    turn = stack.start(TEXT, session=session)
    confirmed_session = stack.service.pending[turn["turn_id"]][3].get("session_update")
    assert stack.decide(turn, True)["code"] == "SETTLED_VERIFIED"
    assert stack.tasks() == 1
    # replay: feed the server the pre-execution confirmed session (as a restored device would)
    from uri_core.client_contracts import ReadQuery
    if confirmed_session is not None:
        stack.runner._commit_consented(session, [("sessions", "get_session", [session], "save_session", {"session_id": session}, confirmed_session)])
        again = stack.runner.begin("Confirm", session, CLAUDE, None)
        assert again.get("code") in ("INTENT_ALREADY_EXECUTED", "INTENT_STATE_STALE", "CONVERSATION", "INTENT_CONFIRMED_NOT_EXECUTED") or again["state"] != "approval_required", again
    assert stack.tasks() == 1 and len(stack.result_files()) == 1


# -- the two frozen worker profiles never read native credential stores ---------------------------------------------

def test_phase2_profiles_contain_no_credential_or_login_paths():
    for rel in ("scripts/run_uri_supervised_worker.py", "scripts/run_uri_phase2_server.py", "uri_supervisor_bridge/qualification.py",
                "uri_supervisor_bridge/composition.py", "uri_supervisor_bridge/worker_service.py"):
        text = (ROOT / rel).read_text(encoding="utf-8")
        code = "\n".join(l for l in text.splitlines() if not l.strip().startswith("#") and not l.strip().startswith('"""'))
        for token in ("auth.json", ".credentials", "login\"]", "\"login\",", "'login',", "setup-token", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
            if token in ("\"login\",", "'login',") and "login\", \"status\"" in code:
                continue
            assert token not in code, (rel, token)
    # the only `login` the composition ever spells is the read-only status subcommand
    q = (ROOT / "uri_supervisor_bridge/qualification.py").read_text(encoding="utf-8")
    assert re.findall(r"\"login\",\s*\"status\"", q) and "codex login\"" not in q


# -- a second live worker on the same client is refused (reconnect cannot double-execute) ----------------------------

def test_two_live_phase2_workers_on_one_client_are_refused():
    """Static pin of the frozen single-instance mutex in the Phase 2 worker profile (the dynamic proof is the frozen
    C3 worker test suite; this guards against the profile dropping the gate)."""
    text = (ROOT / "scripts/run_uri_supervised_worker.py").read_text(encoding="utf-8")
    assert 'NamedMutex("Local\\\\URI_Client_" + m["client_id"], 0)' in text
    assert "install_source_pin(" in text and "FixtureGuard" in text and "sys.addaudithook(guard)" in text
    # the only relaxation of the frozen guard is the null device
    assert text.count("def check_path") == 1 and "_NULL = Path(os.devnull).resolve()" in text
    assert "CLIENT_CWD_MISMATCH" in text and "CLIENT_KEY_MISMATCH" in text and "CLIENT_PROCESS_IMAGE" in text


def test_frozen_entrypoints_and_ui_untouched():
    """Cutover never happened: the frozen worker, server, launcher and UI still compose Phase 1 exactly."""
    worker = (ROOT / "scripts/run_uri_client_worker.py").read_text(encoding="utf-8")
    assert "TurnService(manifest, persistence, harness=harnesses)" in worker and "uri_supervisor" not in worker
    server = (ROOT / "scripts/run_uri_isolated_server.py").read_text(encoding="utf-8")
    assert "default_composition()" in server and "uri_supervisor" not in server
    ui = (ROOT / "uri_ui/lib/services/paired_runtime.dart").read_text(encoding="utf-8")
    assert "manifest['worker_entrypoint']" in ui and "supervised" not in ui


def test_phase2_test_scope_cannot_collect_preserved_runtime_state():
    ini = (ROOT / "scripts/phase2d_pytest.ini").read_text(encoding="utf-8")
    assert "norecursedirs" in ini and " work " in ini + " " and "evidence" in ini
    r = subprocess.run([sys.executable, "-I", "-m", "pytest", "-c", str(ROOT / "scripts/phase2d_pytest.ini"), "--rootdir", str(ROOT),
                        "--collect-only", "-q", "tests/phase2d/test_policy_composition.py"], capture_output=True, text=True, cwd=str(ROOT), timeout=300)
    assert r.returncode == 0 and "work/c1" not in r.stdout and "rollback_" not in r.stdout, r.stdout[-500:]


# -- crash after ledger COMPLETE, before the bridge settles (copy-out / receipt never happened) ------------------------

def test_crash_after_complete_before_settlement_never_relaunches_and_closes_authority(tmp_path):
    """The supervisor commits COMPLETE (`recovery_after_decision` crash point) and the bridge dies before `_settle`:
    no result was copied out, no receipt was built. Restart: the task stays COMPLETE, its still-open authorization is
    revoked, nothing launches, the same ticket is DUPLICATE_OPERATION (the frozen journal/server then hold the turn as
    execution_uncertain: a verified receipt can only come from a live bridge settlement)."""
    from phase2b.conftest import SyntheticAuthority, fake_binding, fake_registry
    from phase2b.test_bridge_restart import cfg_for, child, effects
    auth = SyntheticAuthority()
    cfg, signed, request, now = cfg_for(tmp_path, auth, scenario="honest")
    r = child(cfg, crash_at="recovery_after_decision")
    assert r.returncode == 137, r.stderr[-500:]
    assert effects(tmp_path) == 1
    client = tmp_path / "client"
    assert not list((client / "workspace" / "results").rglob("*")) if (client / "workspace" / "results").exists() else True
    b = SupervisorBridge(client, registry=fake_registry("claude_code"), executors={"claude_code": fake_binding("claude_code")},
                         timeout_s=20, inactivity_s=5)
    try:
        work = auth.verify(signed, request, CLAUDE, now=now)
        t = b.L.task(work.task_id)
        assert t["state"] == "COMPLETE"
        assert b.reconcile_restart() == [{"task_id": work.task_id, "was": "COMPLETE", "state": "COMPLETE", "authority": "revoked"}]
        open_auth = b.L.q1("SELECT COUNT(*) FROM authorization WHERE task_id=? AND superseded_at_us IS NULL AND (valid_until_us IS NULL OR valid_until_us>?)",
                           (work.task_id, b.L.now_us()))[0]
        assert open_auth == 0
        assert b.execute(work) == ("execution_uncertain", [], "DUPLICATE_OPERATION")
        assert b.L.q1("SELECT COUNT(*) FROM attempt WHERE task_id=?", (work.task_id,))[0] == 1 and effects(tmp_path) == 1
    finally:
        b.close()



# -- independent review round 1, D4: payload behind an unchanged launcher shim ----------------------------------------

def _shim_chain(tmp_path):
    """A launcher shim whose bytes never change, a resolved `payload` it runs by name on PATH, and a pinned script."""
    from phase2b.conftest import FAKE
    import hashlib
    bindir = tmp_path / "bin"
    bindir.mkdir()
    payload = bindir / "payload.cmd"
    payload.write_bytes(('@"%s" "%s" %%*' % (sys.executable, FAKE)).encode("ascii") + bytes([13, 10]))
    shim = tmp_path / "launcher.cmd"
    shim.write_bytes(b"@payload.cmd %*" + bytes([13, 10]))
    pinned = {str(payload.resolve()): hashlib.sha256(payload.read_bytes()).hexdigest()}
    return shim, payload, bindir, pinned


def test_payload_replaced_behind_an_unchanged_shim_is_refused(tmp_path, authority, monkeypatch):
    shim, payload, bindir, pinned = _shim_chain(tmp_path)
    monkeypatch.setenv("PATH", str(bindir) + ";" + __import__("os").environ["PATH"])
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": [None]}))
    rec = signed_record(client, provider="claude_code", level="FIXTURE_ONLY", spec_id="generic_ndjson", executable=shim,
                        executable_args=[], version="0.0.1", models=[None], evidence_path=ev, qualified_by="t",
                        pinned_files=pinned, resolve_pins={"payload.cmd": str(payload.resolve())})
    from uri_supervisor_bridge.qualification import write_record
    write_record(client, rec)
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert comp.qualified() == ["claude_code"], comp.report
    b = SupervisorBridge(client, registry=comp.registry, executors=comp.executors, timeout_s=15, inactivity_s=4)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        assert b.execute(authority.verify(signed, request, CLAUDE, now=now))[0] == "verified"
        payload.write_bytes(payload.read_bytes() + b"rem replaced payload" + bytes([13, 10]))      # shim bytes unchanged
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, CLAUDE, now=now))
        assert out[0] == "failed" and out[2] in (NOT_STARTED + "HARNESS_HARNESS_NOT_USABLE", NOT_STARTED + "EXECUTOR_LAUNCH_CHAIN_MISMATCH")
        assert b.L.q1("SELECT COUNT(*) FROM task")[0] == 1
        assert b._launch_chain_intact(comp.executors["claude_code"]) is False          # bridge layer, independently
        assert comp.executors["claude_code"].revalidate() == "LAUNCH_CHAIN_HASH_MISMATCH"
    finally:
        b.close()
    assert compose_client(client, trust=trust_for(client), allow_fixture=True).report[0]["reason"] == "LAUNCH_CHAIN_HASH_MISMATCH"


def test_resolution_redirected_to_another_payload_is_refused(tmp_path, monkeypatch):
    """Same pinned payload bytes, but PATH now resolves the launcher's name to a different file first."""
    shim, payload, bindir, pinned = _shim_chain(tmp_path)
    evil = tmp_path / "evil"
    evil.mkdir()
    (evil / "payload.cmd").write_bytes(payload.read_bytes())
    from uri_supervisor_bridge.qualification import QualificationError, check_launch_chain
    env = {"PATH": str(bindir)}
    check_launch_chain(pinned, {"payload.cmd": str(payload.resolve())}, env)
    import pytest as _pt
    with _pt.raises(QualificationError, match="LAUNCH_CHAIN_RESOLUTION_CHANGED"):
        check_launch_chain(pinned, {"payload.cmd": str(payload.resolve())}, {"PATH": str(evil) + ";" + str(bindir)})


def test_native_cmd_launcher_without_pinned_chain_is_refused(tmp_path):
    import hashlib
    shim, payload, bindir, pinned = _shim_chain(tmp_path)
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"provider": "codex_cli", "ok": True, "version": "0.0.1", "model": "m",
                              "executable_sha256": hashlib.sha256(shim.read_bytes()).hexdigest()}))
    rec = signed_record(client, provider="codex_cli", level="NATIVE_QUALIFIED", spec_id="codex_cli", executable=shim,
                        executable_args=[], version="0.0.1", models=["m"], evidence_path=ev, qualified_by="t",
                        pinned_files={}, resolve_pins={})
    from uri_supervisor_bridge.qualification import write_record
    write_record(client, rec)
    comp = compose_client(client, trust=trust_for(client), auth_probe=lambda h: True)
    assert comp.report[0]["reason"] == "LAUNCH_CHAIN_NOT_PINNED" and comp.executors == {}


def test_real_npm_codex_launch_chain_is_discovered_and_pins_the_payload():
    """REAL installation (read-only): the npm shim's chain pins node, codex.js and the vendor codex.exe."""
    import shutil as sh
    exe = sh.which("codex")
    if exe is None or not exe.lower().endswith(".cmd"):
        import pytest as _pt
        _pt.skip("npm codex shim not installed here")
    from uri_supervisor_bridge.qualification import check_launch_chain, npm_codex_launch_chain
    pinned, resolve = npm_codex_launch_chain(exe)
    names = {Path(p).name.lower() for p in pinned}
    assert {"codex.js", "codex.exe"} <= names and ("node.exe" in names)
    check_launch_chain(pinned, resolve)


# -- independent review round 1, D6 (disputed by the implementer; this test is the evidence) ---------------------------

def test_auth_is_probed_live_at_every_execution_not_cached_at_composition(tmp_path, authority, monkeypatch):
    """The registry calls the auth probe on every selectable(); the bridge calls selectable() before every task. A
    provider that logs out after composition is refused at the next execution, before any task exists."""
    import hashlib
    from phase2b.conftest import FAKE
    from uri_supervisor_bridge.qualification import write_record
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"provider": "codex_cli", "ok": True, "version": "0.0.1", "model": None,
                              "executable_sha256": hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()}))
    write_record(client, signed_record(client, provider="codex_cli", level="NATIVE_QUALIFIED", spec_id="codex_cli",
                                       executable=sys.executable, executable_args=[FAKE], version="0.0.1", models=[None],
                                       evidence_path=ev, qualified_by="t"))
    state = {"auth": True, "calls": 0}

    def probe(hid):
        state["calls"] += 1
        return state["auth"]
    comp = compose_client(client, trust=trust_for(client), auth_probe=probe)
    b = SupervisorBridge(client, registry=comp.registry, executors=comp.executors, timeout_s=10, inactivity_s=3)
    try:
        before = state["calls"]
        state["auth"] = False                                       # logged out after composition
        signed, request, now = authority.issue()
        from phase2b.conftest import CODEX
        out = b.execute(authority.verify(signed, request, CODEX, now=now))
        assert out[0] == "failed" and out[2].startswith(NOT_STARTED + "HARNESS_") and state["calls"] > before
        assert b.L.q1("SELECT COUNT(*) FROM task")[0] == 0
    finally:
        b.close()
