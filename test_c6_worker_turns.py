"""C6 backend contract: a UI drives harness discovery + a gated turn through the REAL worker process
over framed stdio against a REAL isolated server process. No UI is started here."""
from pathlib import Path
import subprocess
import sys
import uuid

from scripts.uri_server_launcher import launch, listener
from uri_core.client_runtime.frames import read_frame, write_frame
from uri_core.client_runtime.manifest import ClientManifest, provision_client
from uri_core.core.runtime_identity import RuntimeManifest, child_environment, provision

ROOT = Path(__file__).resolve().parent


def uid():
    return str(uuid.uuid4())


def test_worker_turn_and_harness_commands_over_real_frames():
    base = ROOT / "work/c1" / ("c6_worker_" + uuid.uuid4().hex)
    port = next(p for p in range(18240, 18260) if listener(p) is None)
    server = RuntimeManifest(provision(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    client = ClientManifest(provision_client(server.path, base / "c", uid(), ["remember_fact"]))
    started = launch(server, "start")
    proc = None
    try:
        m = client.data
        proc = subprocess.Popen([m["interpreter"], "-B", "-I", m["worker_entrypoint"], "--manifest", str(client.path)],
            cwd=m["client_root"], env=child_environment(Path(m["client_root"]), Path(m["interpreter"])),
            stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        def cmd(value):
            write_frame(proc.stdin, value)
            return read_frame(proc.stdout)

        found = cmd({"command": "harness_discover"})
        assert found["result"] == "OK" and found["value"]["fallback"] == "none"
        by_id = {h["harness_id"]: h for h in found["value"]["harnesses"]}
        assert all(not h["usable"] for h in by_id.values()) and by_id["antigravity"]["qualification"] == "REFUSED"
        session = uid()
        nobrain = {"kind": "server_local_model", "provider": "uri-deterministic", "model": None}
        ask = cmd({"command": "turn_start", "session_id": session, "text": "remember that worker driven fact", "reasoning": nobrain})
        assert ask["result"] == "OK" and ask["value"]["state"] == "approval_required"
        assert cmd({"command": "turn_decide", "turn_id": uid(), "approve": True})["result"] == "REFUSED"   # unknown turn
        done = cmd({"command": "turn_decide", "turn_id": ask["value"]["turn_id"], "approve": True})
        assert done["result"] == "OK" and done["value"]["code"] == "SETTLED_VERIFIED"
        # Intent discovery over the worker protocol: clarify -> answer -> explicit confirm -> approve.
        clar = cmd({"command": "turn_start", "session_id": session, "text": "remember that it is due on Friday", "reasoning": nobrain})
        assert clar["value"]["code"] == "INTENT_CLARIFICATION" and clar["value"]["clarification"]["kind"] == "reference_free"
        conf = cmd({"command": "turn_start", "session_id": session, "text": "the travel form", "reasoning": nobrain})
        c = conf["value"]["confirmation"]
        assert conf["value"]["code"] == "INTENT_CONFIRMATION_REQUIRED"
        assert c["arguments"]["request_text"] == "remember that the travel form is due on Friday"
        assert cmd({"command": "turn_intent", "session_id": session, "text": "Confirm", "reasoning": nobrain,
                    "intent_decision": {"intent_id": c["intent_id"], "revision": c["revision"], "decision": "confirm",
                                        "digest": "0" * 64}})["value"]["code"] == "INTENT_DECISION_STALE"
        go = cmd({"command": "turn_intent", "session_id": session, "text": "Confirm", "reasoning": nobrain,
                  "intent_decision": {"intent_id": c["intent_id"], "revision": c["revision"], "decision": "confirm",
                                      "digest": c["digest"]}})
        assert go["value"]["state"] == "approval_required" and go["value"]["intent"]["digest"] == c["digest"]
        done = cmd({"command": "turn_decide", "turn_id": go["value"]["turn_id"], "approve": True})
        assert done["value"]["code"] == "SETTLED_VERIFIED"
        harness = {"kind": "client_external_harness", "provider": "claude_code", "model": None}
        refused = cmd({"command": "turn_start", "session_id": session, "text": "remember that x", "reasoning": harness})
        assert refused["result"] == "OK" and refused["value"]["code"] == "ADAPTER_NOT_QUALIFIED"
        assert cmd({"command": "close"})["result"] == "CLOSED"
        proc.stdin.close()
        assert proc.wait(15) == 0
        proc = None
    finally:
        if proc is not None and proc.poll() is None:
            proc.kill()
        server_proc = listener(port)
        if server_proc is not None:
            assert started["pid"] == server_proc.pid
            server_proc.terminate()
            server_proc.wait(15)
