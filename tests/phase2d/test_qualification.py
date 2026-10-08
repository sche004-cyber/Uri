"""Persisted qualification (Phase 2D): records are evidence, re-validated on every load; anything that drifts
(binary, version, record bytes, level, provider) leaves the provider NATIVE_UNQUALIFIED and unusable."""
import json
import shutil
import sys
from pathlib import Path

import pytest

from phase2b.conftest import CLAUDE, FAKE
from phase2d.conftest import fixture_record, signed_record, trust_for
from uri_supervisor_bridge.bridge import NOT_STARTED, SupervisorBridge
from uri_supervisor_bridge.qualification import (QualificationError, build_record, compose_client, load_records,
                                                 native_auth_probe, qualification_dir, record_digest, validate_shape, write_record)


def row(comp, provider):
    return next(r for r in comp.report if r["provider"] == provider)


def discover(comp, provider):
    return next(r for r in comp.registry.discover() if r["harness_id"] == provider)


def test_fixture_record_round_trip_qualifies_only_when_fixtures_are_allowed(tmp_path):
    client = tmp_path / "client"
    path, rec = fixture_record(client, "claude_code", (None, "m-1"))
    assert path == qualification_dir(client) / "claude_code.json" and validate_shape(json.loads(path.read_text()))
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["status"] == "QUALIFIED" and comp.qualified() == ["claude_code"]
    d = discover(comp, "claude_code")
    assert d["usable"] is True and d["qualification"] == "FIXTURE_ONLY" and d["auth_state"] == "AUTHENTICATED"
    b = comp.executors["claude_code"]
    assert b.executable_sha256 == rec["executable_sha256"] and b.qualified_models == (None, "m-1") and b.version == "0.0.1"
    strict = compose_client(client, trust=trust_for(client), allow_fixture=False)
    assert row(strict, "claude_code")["reason"] == "LEVEL_NOT_ALLOWED" and strict.executors == {}
    assert discover(strict, "claude_code")["usable"] is False and discover(strict, "claude_code")["qualification"] == "NATIVE_UNQUALIFIED"


def test_nothing_persisted_means_nothing_qualified(tmp_path):
    comp = compose_client(tmp_path / "client", trust=trust_for(tmp_path / "client"))
    assert comp.report == [] and comp.executors == {} and all(not r["usable"] for r in comp.registry.discover())


def test_replaced_executable_invalidates(tmp_path):
    client = tmp_path / "client"
    exe = tmp_path / "python-copy.exe"
    shutil.copyfile(sys.executable, exe)
    # the copied interpreter cannot import its own stdlib from here: version probe fails, so build the record by hand
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": [None]}))
    rec = signed_record(client, provider="claude_code", level="FIXTURE_ONLY", spec_id="generic_ndjson", executable=exe,
                        executable_args=[FAKE], version="0.0.1", models=[None], evidence_path=ev, qualified_by="test")
    write_record(client, rec)
    exe.write_bytes(exe.read_bytes() + b"\0")
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "EXECUTABLE_HASH_MISMATCH" and comp.executors == {}
    exe.unlink()
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "EXECUTABLE_MISSING"


def test_version_drift_invalidates(tmp_path):
    client = tmp_path / "client"
    fixture_record(client, "claude_code", version="9.9.9")
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "VERSION_MISMATCH" and comp.executors == {}


def test_hand_edited_record_is_refused_even_with_a_recomputed_digest(tmp_path):
    """Regression for independent review round 1, D1: editing `models` and recomputing the public digest used to be
    accepted. The record is now signed by the client key; the recomputed digest passes shape, the signature does not."""
    client = tmp_path / "client"
    path, rec = fixture_record(client, "claude_code", (None,))
    edited = {**rec, "models": [None, "sneaky-model"]}
    path.write_text(json.dumps(edited))
    assert load_records(client)[0]["error"] == "RECORD_DIGEST_MISMATCH"
    edited["record_sha256"] = record_digest(edited)
    path.write_text(json.dumps(edited))
    assert load_records(client)[0]["error"] is None
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "RECORD_SIGNATURE_INVALID" and comp.executors == {}


def test_record_signed_by_another_key_or_for_another_client_is_refused(tmp_path):
    """Regression for D3: a record copied from client A into client B (or forged with any other key) does not qualify."""
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
    a, b = tmp_path / "a", tmp_path / "b"
    path, rec = fixture_record(a, "claude_code", (None,))
    assert compose_client(a, trust=trust_for(a), allow_fixture=True).qualified() == ["claude_code"]
    dest = qualification_dir(b)
    (dest / "evidence").mkdir(parents=True)
    (dest / "claude_code.json").write_text(path.read_text())
    for f in (qualification_dir(a) / "evidence").iterdir():
        (dest / "evidence" / f.name).write_bytes(f.read_bytes())
    comp = compose_client(b, trust=trust_for(b), allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "RECORD_CLIENT_MISMATCH" and comp.executors == {}
    tb = trust_for(b)
    forged = dict(rec, client_id=tb.client_id, client_public_key=tb.public_key_hex)
    forged["record_sha256"] = record_digest(forged)
    body = json.dumps({k: v for k, v in forged.items() if k not in ("record_sha256", "signature")},
                      sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    forged["signature"] = Ed25519PrivateKey.generate().sign(body).hex()
    (dest / "claude_code.json").write_text(json.dumps(forged))
    comp = compose_client(b, trust=tb, allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "RECORD_SIGNATURE_INVALID"


def test_evidence_is_rehashed_and_content_checked_on_every_load(tmp_path):
    """Regression for D2: replacing or editing the evidence after qualification used to be accepted."""
    client = tmp_path / "client"
    path, rec = fixture_record(client, "claude_code")
    ev = qualification_dir(client) / "evidence" / rec["evidence_file"]
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": [None], "x": 1}))
    assert row(compose_client(client, trust=trust_for(client), allow_fixture=True), "claude_code")["reason"] == "EVIDENCE_HASH_MISMATCH"
    ev.unlink()
    assert row(compose_client(client, trust=trust_for(client), allow_fixture=True), "claude_code")["reason"] == "EVIDENCE_MISSING"
    other = tmp_path / "wrong.json"
    other.write_text(json.dumps({"fixture": True, "provider": "codex_cli", "models": [None]}))
    fixture_record(client, "claude_code", evidence=other)
    assert row(compose_client(client, trust=trust_for(client), allow_fixture=True), "claude_code")["reason"] == "EVIDENCE_CONTENT_MISMATCH"


def test_expired_record_is_refused(tmp_path):
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": [None]}))
    rec = signed_record(client, provider="claude_code", level="FIXTURE_ONLY", spec_id="generic_ndjson", executable=sys.executable,
                        executable_args=[FAKE], version="0.0.1", models=[None], evidence_path=ev, qualified_by="t",
                        ttl_s=60, now=1_000)
    write_record(client, rec)
    assert row(compose_client(client, trust=trust_for(client), allow_fixture=True), "claude_code")["reason"] == "RECORD_EXPIRED"


def test_no_trust_anchor_qualifies_nothing(tmp_path):
    client = tmp_path / "client"
    fixture_record(client, "claude_code")
    assert row(compose_client(client, trust=None, allow_fixture=True), "claude_code")["reason"] == "NO_TRUST_ANCHOR"


@pytest.mark.parametrize("bad", ["not json", "[]", "{}", '{"schema":"x"}'])
def test_corrupt_record_files_are_reported_not_trusted(tmp_path, bad):
    client = tmp_path / "client"
    d = qualification_dir(client)
    d.mkdir(parents=True)
    (d / "claude_code.json").write_text(bad)
    items = load_records(client)
    assert items[0]["record"] is None and items[0]["error"] in ("RECORD_UNREADABLE", "RECORD_SCHEMA")
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["status"] == "INVALIDATED" and comp.executors == {}


def test_record_filename_must_name_its_provider(tmp_path):
    client = tmp_path / "client"
    path, rec = fixture_record(client, "claude_code")
    path.rename(path.with_name("codex_cli.json"))
    assert load_records(client)[0]["error"] == "RECORD_PROVIDER_FILENAME_MISMATCH"


@pytest.mark.parametrize("provider", ["antigravity", "unknownharness"])
def test_refused_or_unknown_providers_never_qualify(tmp_path, provider):
    client = tmp_path / "client"
    fixture_record(client, provider)
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, provider)["reason"] == "PROVIDER_REFUSED_OR_UNKNOWN" and provider not in comp.executors
    if provider == "antigravity":
        assert discover(comp, provider)["qualification"] == "REFUSED"


def test_build_record_refuses_bad_inputs(tmp_path):
    ev = tmp_path / "ev.json"
    ev.write_text("{}")
    from phase2d.conftest import client_identity
    cid, key = client_identity(tmp_path / "c")
    ok = dict(client_root=tmp_path / "c", client_id=cid, signer=key, provider="claude_code", level="FIXTURE_ONLY", spec_id="generic_ndjson", executable=sys.executable, executable_args=[FAKE],
              version="0.0.1", models=[None], evidence_path=ev, qualified_by="t")
    for k, v, code in [("provider", "Bad Provider", "PROVIDER_ID_INVALID"), ("level", "SUPER", "LEVEL_INVALID"), ("spec_id", "nope", "SPEC_UNKNOWN"),
                       ("executable", tmp_path / "missing.exe", "EXECUTABLE_MISSING"), ("evidence_path", tmp_path / "no.json", "EVIDENCE_MISSING"),
                       ("models", [], "MODELS_REQUIRED"), ("models", ["bad model"], "MODEL_ID_INVALID"),
                       ("client_id", "not-a-uuid", "CLIENT_ID_INVALID"), ("ttl_s", 10**9, "TTL_INVALID")]:
        with pytest.raises(QualificationError, match=code):
            build_record(**{**ok, k: v})


def test_model_pin_refuses_an_unqualified_model_before_any_task(tmp_path, authority, monkeypatch):
    client = tmp_path / "client"
    fixture_record(client, "claude_code", ("m-1",))
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    b = SupervisorBridge(client, registry=comp.registry, executors=comp.executors, timeout_s=15, inactivity_s=4)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        for model in (None, "m-2"):
            out = b.execute(authority.verify(signed, request, {**CLAUDE, "model": model}, now=now))
            assert out == ("failed", [], NOT_STARTED + "MODEL_NOT_QUALIFIED"), model
        assert b.L.q1("SELECT COUNT(*) FROM task")[0] == 0
        assert b.execute(authority.verify(signed, request, {**CLAUDE, "model": "m-1"}, now=now))[0] == "verified"
    finally:
        b.close()


def test_native_record_needs_live_authentication(tmp_path):
    """A NATIVE_QUALIFIED record for codex_cli pointing at the fake executable (version/hash valid): the registry row
    is NATIVE_QUALIFIED but usable only when the live auth probe says so. Nothing is persisted about auth."""
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    import hashlib
    ev.write_text(json.dumps({"provider": "codex_cli", "ok": True, "version": "0.0.1", "model": "gpt-6-sol",
                              "executable_sha256": hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()}))
    rec = signed_record(client, provider="codex_cli", level="NATIVE_QUALIFIED", spec_id="codex_cli", executable=sys.executable,
                        executable_args=[FAKE], version="0.0.1", models=["gpt-6-sol"], evidence_path=ev, qualified_by="t")
    write_record(client, rec)
    for verdict, state, usable in ((True, "AUTHENTICATED", True), (False, "NOT_AUTHENTICATED", False), (None, "AUTH_UNVERIFIED", False)):
        comp = compose_client(client, trust=trust_for(client), auth_probe=lambda hid, v=verdict: v)
        d = discover(comp, "codex_cli")
        assert (d["qualification"], d["auth_state"], d["usable"]) == ("NATIVE_QUALIFIED", state, usable)
        assert row(comp, "codex_cli")["status"] == "QUALIFIED"
    # default probe runs the CLI's own status command against THIS executable: the fake answers nonsense -> False
    comp = compose_client(client, trust=trust_for(client))
    assert discover(comp, "codex_cli")["usable"] is False
    assert native_auth_probe("codex_cli", sys.executable) is False and native_auth_probe("other", sys.executable) is None
    assert native_auth_probe("claude_code", sys.executable) is None       # not JSON -> unknown


def test_live_status_probe_on_installed_clis_never_raises():
    """REAL CLIs if installed: the probe only runs the status subcommand (never logs in)."""
    import shutil as sh
    for provider, exe in (("codex_cli", "codex"), ("claude_code", "claude")):
        path = sh.which(exe)
        if path is None:
            continue
        assert native_auth_probe(provider, path) in (True, False, None)


@pytest.mark.parametrize("stream,text,exit_code,expect", [
    ("2", "Logged in using ChatGPT", 0, True),      # D-D1: Codex 0.158.0 reports on STDERR with exit 0
    ("1", "Logged in using ChatGPT", 0, True),
    ("1", "Not logged in", 1, False),
    ("2", "Not logged in", 0, False),
    ("1", "", 1, False),
])
def test_codex_status_probe_reads_both_streams_and_exit_status(tmp_path, stream, text, exit_code, expect):
    """Regression for defect D-D1 (Phase 2D): the live status probe read stdout only, so a logged-in Codex (which
    prints on stderr) was reported NOT_AUTHENTICATED. A .cmd stand-in reproduces each stream/exit combination."""
    shim = tmp_path / "codex.cmd"
    echo = (f"echo {text} 1>&2" if stream == "2" else f"echo {text}") if text else ""
    body = "@echo off\r\n" + (echo + "\r\n" if echo else "") + f"exit /b {exit_code}\r\n"
    shim.write_bytes(body.encode("ascii"))
    assert native_auth_probe("codex_cli", str(shim)) is expect



# -- independent review round 2, R2-1: validity must hold at EVERY execution, not only at composition ----------------

def _bridge_for(client, comp):
    return SupervisorBridge(client, registry=comp.registry, executors=comp.executors, timeout_s=15, inactivity_s=4)


def _usable(comp, provider):
    return next(r for r in comp.registry.discover() if r["harness_id"] == provider)["usable"]


def test_record_expiring_after_composition_stops_execution(tmp_path, authority, monkeypatch):
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": [None]}))
    rec = signed_record(client, provider="claude_code", level="FIXTURE_ONLY", spec_id="generic_ndjson", executable=sys.executable,
                        executable_args=[FAKE], version="0.0.1", models=[None], evidence_path=ev, qualified_by="t",
                        ttl_s=60, now=10_000)
    write_record(client, rec)
    clock = {"t": 10_030}
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True, clock=lambda: clock["t"])
    assert comp.qualified() == ["claude_code"] and _usable(comp, "claude_code")
    b = _bridge_for(client, comp)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        assert b.execute(authority.verify(signed, request, CLAUDE, now=now))[0] == "verified"
        clock["t"] = 10_061                                                   # the record expires while the worker lives
        assert not _usable(comp, "claude_code")
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, CLAUDE, now=now))
        assert out[0] == "failed" and out[2].startswith(NOT_STARTED) and b.L.q1("SELECT COUNT(*) FROM task")[0] == 1, out
    finally:
        b.close()


def test_evidence_deleted_after_composition_stops_execution(tmp_path, authority, monkeypatch):
    client = tmp_path / "client"
    path, rec = fixture_record(client, "claude_code")
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    b = _bridge_for(client, comp)
    try:
        (qualification_dir(client) / "evidence" / rec["evidence_file"]).unlink()
        assert not _usable(comp, "claude_code")
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, CLAUDE, now=now))
        assert out[0] == "failed" and out[2].startswith(NOT_STARTED) and b.L.q1("SELECT COUNT(*) FROM task")[0] == 0, out
        # the precise reason is visible on the binding hook
        assert comp.executors["claude_code"].revalidate() == "EVIDENCE_MISSING"
    finally:
        b.close()


def test_record_replaced_after_composition_even_validly_signed_stops_execution(tmp_path, authority, monkeypatch):
    client = tmp_path / "client"
    fixture_record(client, "claude_code", ("m-1",))
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    other = tmp_path / "other-ev.json"
    other.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": ["m-1"], "note": "a different qualification run"}))
    fixture_record(client, "claude_code", ("m-1",), evidence=other)                          # new, valid, different record
    assert comp.executors["claude_code"].revalidate() == "RECORD_CHANGED_SINCE_COMPOSITION"
    b = _bridge_for(client, comp)
    try:
        monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
        signed, request, now = authority.issue()
        out = b.execute(authority.verify(signed, request, {**CLAUDE, "model": "m-1"}, now=now))
        assert out[0] == "failed" and out[2].startswith(NOT_STARTED) and b.L.q1("SELECT COUNT(*) FROM task")[0] == 0
    finally:
        b.close()


# -- independent review round 2, R2-2: a record may qualify only the model(s) its evidence exercised ------------------

def test_native_record_listing_an_untested_model_is_refused(tmp_path):
    import hashlib
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"provider": "codex_cli", "ok": True, "version": "0.0.1", "model": "model-a",
                              "executable_sha256": hashlib.sha256(open(sys.executable, "rb").read()).hexdigest()}))
    write_record(client, signed_record(client, provider="codex_cli", level="NATIVE_QUALIFIED", spec_id="codex_cli",
                                       executable=sys.executable, executable_args=[FAKE], version="0.0.1",
                                       models=["model-a", "model-b"], evidence_path=ev, qualified_by="t"))
    comp = compose_client(client, trust=trust_for(client), auth_probe=lambda h: True)
    assert row(comp, "codex_cli")["reason"] == "EVIDENCE_CONTENT_MISMATCH" and comp.executors == {}


def test_fixture_evidence_naming_models_bounds_the_record(tmp_path):
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": ["m-1"]}))
    fixture_record(client, "claude_code", ("m-1", "m-2"), evidence=ev)
    assert row(compose_client(client, trust=trust_for(client), allow_fixture=True), "claude_code")["reason"] == "EVIDENCE_CONTENT_MISMATCH"


# -- independent review round 3 (low, fixture-only): R3-1 malformed evidence models, R3-2 evidence must name models ----

def test_r3_1_malformed_fixture_evidence_models_is_refused_not_a_crash(tmp_path):
    client = tmp_path / "client"
    for bad in (42, "m-1", {"m": 1}, [], [1], [None, 2]):
        ev = tmp_path / f"ev-{abs(hash(repr(bad)))}.json"
        ev.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": bad}))
        fixture_record(client, "claude_code", (None,), evidence=ev)
        comp = compose_client(client, trust=trust_for(client), allow_fixture=True)          # must not raise
        assert row(comp, "claude_code")["reason"] == "EVIDENCE_CONTENT_MISMATCH" and comp.executors == {}, bad


def test_r3_2_fixture_evidence_without_models_backs_nothing(tmp_path):
    client = tmp_path / "client"
    ev = tmp_path / "ev.json"
    ev.write_text(json.dumps({"fixture": True, "provider": "claude_code"}))                   # no `models` at all
    fixture_record(client, "claude_code", ("m-1", "m-2"), evidence=ev)
    comp = compose_client(client, trust=trust_for(client), allow_fixture=True)
    assert row(comp, "claude_code")["reason"] == "EVIDENCE_CONTENT_MISMATCH" and comp.executors == {}
    ev2 = tmp_path / "ev2.json"
    ev2.write_text(json.dumps({"fixture": True, "provider": "claude_code", "models": ["m-1", "m-2"]}))
    fixture_record(client, "claude_code", ("m-1", "m-2"), evidence=ev2)                    # exact list: qualified
    assert row(compose_client(client, trust=trust_for(client), allow_fixture=True), "claude_code")["status"] == "QUALIFIED"
