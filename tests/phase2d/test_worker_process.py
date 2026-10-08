"""REAL processes: the Phase 2 server profile (`scripts/run_uri_phase2_server.py`, explicit policy file) and the Phase 2
worker profile (`scripts/run_uri_supervised_worker.py`) under the frozen manifests, driven over the frozen framed
stdio protocol with the exact frames the frozen UI sends. Executor: fake harness via a persisted FIXTURE_ONLY record
(`--allow-fixture-qualification`). Nothing here touches the frozen launchers or any production entry."""
import json
import subprocess
import sys
import time
import uuid
from pathlib import Path

import psutil
import pytest

from phase2b.conftest import CLAUDE, uid
from phase2d.conftest import ROOT, HARNESS_ROWS, fixture_record
from scripts.uri_server_launcher import listener
from uri_core.client_runtime.frames import read_frame, write_frame
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.core.runtime_identity import RuntimeManifest, atomic_json, child_environment, provision
from uri_supervisor_bridge.composition import policy_path, write_policy

SERVER = str(ROOT / "scripts/run_uri_phase2_server.py")
WORKER = str(ROOT / "scripts/run_uri_supervised_worker.py")
TEXT = "use the harness to write a greeting into out.txt"


def wait_listener(port, timeout=40):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        p = listener(port)
        if p is not None:
            return p
        time.sleep(0.2)
    raise AssertionError("phase2 server did not listen")


@pytest.fixture
def procs():
    base = ROOT / "work/c1" / ("p2d_proc_" + uuid.uuid4().hex)
    port = next(p for p in range(18260, 18290) if listener(p) is None)
    server = RuntimeManifest(provision(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    write_policy(policy_path(server.data["state_root"]), HARNESS_ROWS)
    client = ClientManifest(provision_client(server.path, base / "c", uid(), ["remember_fact"]))
    from uri_core.core.client_pairing import ClientPairingStore
    store = ClientPairingStore(server.data["control_root"], server.data["server_id"])
    with store.lock:
        data = store._load()
        data["clients"][client.data["client_id"]]["grants"].append("external_harness_task")
        atomic_json(store.path, data)
    fixture_record(Path(client.data["client_root"]), "claude_code", (None,))
    sm = server.data
    log = Path(sm["state_root"]) / "logs" / "phase2-server.log"
    log.parent.mkdir(parents=True, exist_ok=True)
    sp = subprocess.Popen([sm["interpreter"], "-B", "-I", SERVER, "--manifest", str(server.path)], cwd=sm["state_root"],
                          env=child_environment(Path(sm["state_root"]), Path(sm["interpreter"])), stdin=subprocess.DEVNULL,
                          stdout=open(log, "ab"), stderr=subprocess.STDOUT)
    wp = None
    try:
        wait_listener(port)
        m = client.data
        wp = subprocess.Popen([m["interpreter"], "-B", "-I", WORKER, "--manifest", str(client.path), "--allow-fixture-qualification"],
                              cwd=m["client_root"], env={**child_environment(Path(m["client_root"]), Path(m["interpreter"])), "URI_FAKE_SCENARIO": "honest"},
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        yield {"server": sp, "worker": wp, "client": client, "server_manifest": server, "base": base, "port": port}
    finally:
        if wp is not None and wp.poll() is None:
            wp.kill()
        if sp.poll() is None:
            sp.kill()
        sp.wait(15)


def frames(wp):
    def cmd(value):
        write_frame(wp.stdin, value)
        return read_frame(wp.stdout)
    return cmd


def test_phase2_profiles_run_the_governed_path_over_real_frames(procs):
    wp, client = procs["worker"], procs["client"]
    cmd = frames(wp)
    pre = cmd({"command": "preflight"})
    assert pre["result"] == "OK" and pre["value"]["worker_profile"] == "phase2d-supervised" and pre["value"]["production_cutover"] is False
    found = cmd({"command": "harness_discover"})
    assert found["result"] == "OK", found
    assert found["value"]["qualification_live"] == {"claude_code": None}, found["value"]["qualification_live"]
    by_id = {h["harness_id"]: h for h in found["value"]["harnesses"]}
    assert by_id["claude_code"]["usable"] is True and by_id["claude_code"]["qualification"] == "FIXTURE_ONLY"
    assert by_id["codex_cli"]["usable"] is False and by_id["codex_cli"]["qualification"] == "NATIVE_UNQUALIFIED"
    assert by_id["antigravity"]["qualification"] == "REFUSED"
    assert found["value"]["qualification"][0]["status"] == "QUALIFIED" and found["value"]["supervisor"] == "uri_supervisor_bridge"
    inst = json.loads((Path(client.data["client_root"]) / "control/worker-instance.json").read_text())
    assert inst["profile"] == "phase2d-supervised" and inst["qualified"] == ["claude_code"] and len(inst["phase2_source_digest"]) == 64
    session = uid()
    turn = cmd({"command": "turn_start", "session_id": session, "text": TEXT, "reasoning": CLAUDE})
    assert turn["result"] == "OK" and turn["value"]["state"] == "approval_required", turn
    req = turn["value"]["approval_request"]
    bad = cmd({"command": "turn_decide", "turn_id": turn["value"]["turn_id"], "approve": True, "approval_digest": "0" * 64})
    assert bad == {"result": "REFUSED", "code": "APPROVAL_DIGEST_MISMATCH"}
    dead = cmd({"command": "turn_decide", "turn_id": turn["value"]["turn_id"], "approve": True})
    assert dead == {"result": "REFUSED", "code": "TURN_NOT_PENDING"}
    assert cmd({"command": "turn_decide", "turn_id": turn["value"]["turn_id"], "approve": True, "ticket": {}})["result"] == "REFUSED"
    # the dropped turn holds its session until the server expires it (frozen rule): continue in a new session
    assert cmd({"command": "turn_start", "session_id": session, "text": TEXT, "reasoning": CLAUDE})["code"].startswith("SERVER_REFUSED:")
    turn = cmd({"command": "turn_start", "session_id": uid(), "text": TEXT, "reasoning": CLAUDE})
    assert turn["result"] == "OK" and turn["value"]["state"] == "approval_required", turn
    req = turn["value"]["approval_request"]
    done = cmd({"command": "turn_decide", "turn_id": turn["value"]["turn_id"], "approve": True, "approval_digest": req["approval_digest"]})
    assert done["result"] == "OK" and done["value"]["code"] == "SETTLED_VERIFIED", done
    results = list((Path(client.data["client_root"]) / "workspace/results").rglob("out.txt"))
    assert len(results) == 1 and results[0].read_text().startswith("hello from fake harness")
    import sqlite3
    con = sqlite3.connect(f"file:{Path(client.data['client_root']) / 'control/supervisor/ledger.db'}?mode=ro", uri=True)
    assert [r[0] for r in con.execute("SELECT state FROM task")] == ["COMPLETE"]
    con.close()
    assert cmd({"command": "close"})["result"] == "CLOSED"
    wp.stdin.close()
    assert wp.wait(15) == 0


def test_worker_profile_refuses_fixture_records_without_the_flag(procs):
    """Same client root, a second worker started WITHOUT --allow-fixture-qualification: the record is INVALIDATED and
    the harness is not usable; the first worker must be gone first (single instance)."""
    wp, client = procs["worker"], procs["client"]
    cmd = frames(wp)
    assert cmd({"command": "close"})["result"] == "CLOSED"
    wp.stdin.close()
    wp.wait(15)
    m = client.data
    strict = subprocess.Popen([m["interpreter"], "-B", "-I", WORKER, "--manifest", str(client.path)], cwd=m["client_root"],
                              env=child_environment(Path(m["client_root"]), Path(m["interpreter"])),
                              stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        c2 = frames(strict)
        found = c2({"command": "harness_discover"})
        assert found["result"] == "OK"
        assert all(not h["usable"] for h in found["value"]["harnesses"])
        assert found["value"]["qualification"][0]["status"] == "INVALIDATED" and found["value"]["qualification"][0]["reason"] == "LEVEL_NOT_ALLOWED"
        turn = c2({"command": "turn_start", "session_id": uid(), "text": TEXT, "reasoning": CLAUDE})
        assert turn["value"]["state"] == "approval_required"
        done = c2({"command": "turn_decide", "turn_id": turn["value"]["turn_id"], "approve": True})
        assert done["result"] == "OK" and done["value"]["code"] == "SETTLED_FAILED"
        assert not list((Path(m["client_root"]) / "workspace/results").rglob("out.txt"))
        assert c2({"command": "close"})["result"] == "CLOSED"
        strict.stdin.close()
        assert strict.wait(15) == 0
    finally:
        if strict.poll() is None:
            strict.kill()
