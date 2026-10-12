"""Final (sixth) closure review: regressions for defects found while attacking the fifth-review repairs N1-N4,
plus the independent N1/N2 attacks that pin the accepted behaviour.

Real paired app (TestClient), real client persistence (DPAPI, consented commits), real GraphStore/FileStore
behind the client ports, real fake-harness subprocesses, real app restarts, real entrypoint subprocesses.
"""
import importlib.util
import json
import marshal
import shutil
import subprocess
import sys
import uuid
from pathlib import Path

import pytest

from test_c5_intent_adversarial import add_graph
from test_c5_intent_discovery import Stack, confirm_and_approve, say, two_reports, uid
from test_c5_loop import harness_stack, CLAUDE, CODEX   # noqa: F401  (fixture reused)
from uri_core.client_contracts import ReadQuery, canonical
from uri_core.client_runtime.turn_runner import TurnError, TurnRunner

ROOT = Path(__file__).resolve().parent
LONG = " ".join(f"item{i} approved" for i in range(120))
HARNESS_TEXT = "use the harness to write a greeting into out.txt"


@pytest.fixture
def s():
    stack = Stack(18261)
    yield stack
    stack.close()


def provenance(s, session):
    turns = s.runner.persistence.snapshot(session, [ReadQuery(store="history", method="get_session",
                                                               args=[session])]).reads[0].result
    return [(t["user_text"], (t.get("attachments") or [None])[0]) for t in turns]


# ---- N4 follow-up: the provenance record must not change what the caller/UI is shown ------------------------
def test_truncated_provenance_does_not_strip_the_confirmation_the_user_must_see(s):
    """Final review: _provenance aliased turn['confirmation'] and, past 4 KiB, popped its 'arguments' in place.
    The returned confirmation (rendered by the UI as 'Confirm exactly what URI will do') then showed nothing
    while its Confirm button still sent the digest."""
    session = two_reports(s)
    say(s, session, "remember that the budget report is due on Friday and " + LONG)
    awaiting = say(s, session, "the Q4 one")
    assert provenance(s, session)[-1][1]["truncated"]                        # the truncation path ran
    assert awaiting["confirmation"]["arguments"]["request_text"].startswith("remember that Budget report Q4.docx")


def test_truncated_provenance_does_not_strip_clarification_options(s):
    session = uid()
    add_graph(s, session, "Q4 report north " + "n" * 3000, "Q4 report south " + "s" * 3000)
    out = say(s, session, "remember that the Q4 report is final")
    assert out["clarification"]["kind"] == "reference" and len(out["clarification"]["options"]) == 2


def test_provenance_stays_within_its_bound_under_pressure(s):
    """Final review: long candidate titles kept in the question, or long approved arguments, exceeded the
    documented 4 KiB bound after the first truncation step. The record now degrades to fixed-size lineage."""
    session = two_reports(s)
    add_graph(s, session, "Q4 report north " + "n" * 3000, "Q4 report south " + "s" * 3000)
    other = uid()
    add_graph(s, other, "Q4 report north " + "n" * 3000, "Q4 report south " + "s" * 3000)
    say(s, other, "remember that the Q4 report is final")
    say(s, session, "remember that the budget report is due on Friday and " + LONG)
    say(s, session, "the Q4 one")
    corrected = say(s, session, "actually it is due on Monday, not Friday")
    approval, _ = confirm_and_approve(s, session, corrected)
    records = provenance(s, session) + provenance(s, other)
    assert all(p is None or len(canonical(p)) <= TurnRunner.PROVENANCE_LIMIT for _, p in records)
    done = dict(provenance(s, session))["Confirm"]
    assert done["approval"]["argument_digest"] == approval["approval_request"]["argument_digest"]
    assert done["approval"]["intent_digest"] == corrected["confirmation"]["digest"]
    assert done["intent"]["sources"] == {"statement": "user_correction"}


# ---- N1: checkpoint consumption across crash / restart --------------------------------------------------------
def _paused(runner, monkeypatch, session):
    monkeypatch.setenv("URI_FAKE_SCENARIO", "quota")
    p = runner.run(HARNESS_TEXT, session, CODEX, lambda req: True)
    assert p["code"] == "WAITING_FOR_MODEL"
    return p


def _effects(cm):
    return list((Path(cm.data["client_root"]) / "workspace").glob("results/*/out.txt"))


def _restarted(runner, persistence, call, cm):
    return TurnRunner(cm, persistence, call, cm.data["server_public_key"], runner.generation, harness=runner.harness)


def test_checkpoint_crash_before_consumption_dispatches_nothing_and_stays_one_continuation(harness_stack, monkeypatch):
    runner, persistence, app, call, cm = harness_stack
    session = uid(); p = _paused(runner, monkeypatch, session)
    turns = set(app.state.client_service._load()["turns"])
    real = Path.write_text

    def crash(self, data, *a, **k):
        if self.name == p["turn_id"] + ".json" and '"consumed": true' in data:
            raise KeyboardInterrupt("crash")
        return real(self, data, *a, **k)
    monkeypatch.setattr(Path, "write_text", crash)
    with pytest.raises(KeyboardInterrupt):
        runner.continue_waiting(session, p["turn_id"], CLAUDE, lambda r: pytest.fail("must not ask"))
    monkeypatch.setattr(Path, "write_text", real)
    assert set(app.state.client_service._load()["turns"]) == turns and _effects(cm) == []
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    again = _restarted(runner, persistence, call, cm)
    assert again.continue_waiting(session, p["turn_id"], CLAUDE, lambda r: True)["code"] == "SETTLED_VERIFIED"
    with pytest.raises(TurnError, match="CHECKPOINT_CONSUMED"):
        again.continue_waiting(session, p["turn_id"], CLAUDE, lambda r: True)
    assert len(_effects(cm)) == 1


@pytest.mark.parametrize("where", ["after_consumption", "after_claim"])
def test_checkpoint_crash_after_consumption_or_claim_then_restart_is_consumed(harness_stack, monkeypatch, where):
    runner, persistence, app, call, cm = harness_stack
    session = uid(); p = _paused(runner, monkeypatch, session)

    def crash(*a, **k):
        raise KeyboardInterrupt(where)
    monkeypatch.setattr(runner, "run" if where == "after_consumption" else "_run_harness", crash)
    with pytest.raises(KeyboardInterrupt):
        runner.continue_waiting(session, p["turn_id"], CLAUDE, lambda r: True)
    monkeypatch.setenv("URI_FAKE_SCENARIO", "honest")
    again = _restarted(runner, persistence, call, cm)
    for provider in (CLAUDE, CODEX):
        with pytest.raises(TurnError, match="CHECKPOINT_CONSUMED|SAME_PROVIDER"):
            again.continue_waiting(session, p["turn_id"], provider, lambda r: pytest.fail("must not ask"))
    assert _effects(cm) == []


# ---- N2: a wide set of planted shadows never runs before the isolated-mode decision ---------------------------
ENTRYPOINTS = ["scripts/run_uri_isolated_server.py", "scripts/run_uri_client_worker.py",
               "scripts/uri_server_launcher.py", "scripts/uri_client_launcher.py"]
SHADOWS = ["argparse", "hashlib", "secrets", "json", "pathlib", "uuid", "ctypes", "subprocess", "time", "psutil",
           "typing", "enum", "re", "functools", "collections", "sitecustomize", "usercustomize", "warnings"]


@pytest.mark.parametrize("kind", ["source", "sourceless"])
def test_wide_shadow_set_never_runs_before_the_isolated_mode_gate(kind):
    base = ROOT / "work/c1" / ("final_n2_" + uuid.uuid4().hex)
    marker = base / "marker"
    scripts = base / "scripts"
    scripts.mkdir(parents=True)
    try:
        for entry in ENTRYPOINTS + ["scripts/c1_bootstrap.py"]:
            shutil.copyfile(ROOT / entry, base / entry)
        for name in SHADOWS:
            src = f"open({str(marker)!r}, 'a').write({name!r} + '\\n')\n"
            if kind == "source":
                (scripts / (name + ".py")).write_text(src)
            else:
                (scripts / (name + ".pyc")).write_bytes(importlib.util.MAGIC_NUMBER + b"\0" * 12
                                                        + marshal.dumps(compile(src, name + ".py", "exec")))
        for entry in ENTRYPOINTS:
            for isolated in (False, True):
                argv = [sys.executable] + (["-I"] if isolated else []) + [str(base / entry)]
                argv += (["validate"] if "launcher" in entry else []) + ["--manifest", str(base / "missing.json")]
                r = subprocess.run(argv, cwd=str(scripts), capture_output=True, text=True, timeout=120)
                assert r.returncode != 0, (entry, isolated)
                assert isolated or "C1_ISOLATED_MODE_REQUIRED" in r.stderr, (entry, r.stderr)
                assert not marker.exists(), (entry, isolated, marker.read_text() if marker.exists() else "")
    finally:
        shutil.rmtree(base, ignore_errors=True)
