"""C1 manifest, proof, containment and real Windows launcher regressions.

All state lives under this worktree/work/c1. Test cleanup signals only a
process whose listener, executable, arguments and creation time we proved.
"""
import copy
import http.server
import json
import os
from pathlib import Path
import secrets
import socket
import subprocess
import sys
import threading
import time
import urllib.request
import uuid

import psutil
import pytest
from uri_core.core.runtime_identity import (RuntimeManifest,RuntimeIdentity,RuntimeIdentityError,
    FixtureGuard,atomic_json,child_environment,provision,verify_proof)
from scripts.uri_server_launcher import listener,owned_instance,process_identity

ROOT=Path(__file__).resolve().parent
PYTHON=ROOT/".venv/Scripts/python.exe"


def free_port():
    with socket.socket() as s:s.bind(("127.0.0.1",0));return s.getsockname()[1]


@pytest.fixture
def manifest():
    path=provision(ROOT,ROOT/"work/c1"/uuid.uuid4().hex,PYTHON,free_port())
    return RuntimeManifest(path)


def cli(m,action="start"):
    return subprocess.run(["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"scripts/uri_server.ps1"),
        "-Manifest",str(m.path),"-Action",action,"-TimeoutSeconds","15"],capture_output=True,text=True)


def output(r):return json.loads(r.stdout.strip().splitlines()[-1])


def stop_owned(m,identity):
    proc=listener(m.data["port"])
    if proc is None:return
    now=owned_instance(m,proc)
    assert now==identity
    parent=proc.parent()
    proc.terminate();proc.wait(timeout=10)
    if parent:
        try:parent.wait(timeout=10)
        except psutil.NoSuchProcess:pass


def http_call(m,path,data=None,token=None):
    req=urllib.request.Request(f'http://127.0.0.1:{m.data["port"]}'+path,
        data=json.dumps(data).encode() if data is not None else None,
        headers={"Content-Type":"application/json"}|({"Authorization":"Bearer "+token} if token else {}))
    try:
        with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(req,timeout=5) as response:
            return response.status,json.load(response)
    except urllib.error.HTTPError as exc:return exc.code,None


def test_manifest_and_signed_projection(manifest):
    runtime=RuntimeIdentity(manifest);nonce=secrets.token_hex(32)
    result=runtime.public(nonce)
    verified=verify_proof(manifest,result,nonce)
    assert verified["build_manifest_digest"]==manifest.digest
    assert all(k not in result for k in ("source_root","state_root","interpreter","public_key","token"))
    assert str(ROOT) not in json.dumps(result)
    assert (Path(manifest.data["control_root"])/"signing_key.dpapi").stat().st_size>32
    with pytest.raises(RuntimeIdentityError,match="IDENTITY_PROOF_FAILED"):
        verify_proof(manifest,result,secrets.token_hex(32))
    result["generation"]=str(uuid.uuid4())
    with pytest.raises(RuntimeIdentityError,match="IDENTITY_PROOF_FAILED"):
        verify_proof(manifest,result,nonce)


@pytest.mark.parametrize("change,code",[
    ({"extra":True},"MANIFEST_SCHEMA_INVALID"),
    ({"schema_version":True},"MANIFEST_CONTRACT_MISMATCH"),
    ({"host":"0.0.0.0"},"NONPRODUCTION_LOOPBACK_REQUIRED"),
    ({"port":8000},"NONPRODUCTION_LOOPBACK_REQUIRED"),
    ({"port":True},"NONPRODUCTION_LOOPBACK_REQUIRED"),
    ({"source_checkpoint":"0"*40},"MANIFEST_CONTRACT_MISMATCH"),
    ({"model_policy":"warm"},"COMPOSITION_POLICY_MISMATCH"),
    ({"source_manifest_digest":"0"*64},"SOURCE_MANIFEST_MISMATCH"),
    ({"interpreter_sha256":"0"*64},"INTERPRETER_HASH_MISMATCH"),
    ({"dependency_manifest_digest":"0"*64},"DEPENDENCY_MANIFEST_MISMATCH"),
    ({"public_key_fingerprint":"0"*64},"PUBLIC_KEY_FINGERPRINT_MISMATCH"),
    ({"state_root":str(ROOT.parent)},"SYNTHETIC_ROOT_REQUIRED"),
    ({"control_root":str(ROOT.parent)},"STATE_ROOT_MISMATCH"),
    ({"entrypoint":str(ROOT/"scripts/run_uri_server.py")},"ENTRYPOINT_OR_INTERPRETER_MISMATCH"),
])
def test_manifest_fails_closed(manifest,change,code):
    atomic_json(manifest.path,manifest.data|change)
    with pytest.raises(RuntimeIdentityError,match=code):RuntimeManifest(manifest.path)


def test_refuses_existing_root_and_unknown_checkpoint(manifest):
    with pytest.raises(RuntimeIdentityError,match="FRESH_SYNTHETIC_ROOT_REQUIRED"):
        provision(ROOT,Path(manifest.data["state_root"]),PYTHON,free_port())
    with pytest.raises(RuntimeIdentityError,match="SYNTHETIC_ROOT_REQUIRED"):
        provision(ROOT,ROOT.parent/"not-a-fixture",PYTHON,free_port())


def test_guard_and_environment(manifest,monkeypatch):
    guard=FixtureGuard(manifest);state=Path(manifest.data["state_root"])
    guard("open",(str(state/"uri_workspace/test.json"),"w",os.O_WRONLY))
    for event,args in [("open",(str(ROOT.parent/"private.db"),"r",os.O_RDONLY)),
                       ("os.mkdir",(str(ROOT/"uri_workspace/not-permitted"),0o777)),
                       ("socket.connect",(None,("127.0.0.1",11434))),
                       ("subprocess.Popen",("ollama",[],None,None))]:
        with pytest.raises(PermissionError):guard(event,args)
    monkeypatch.setenv("ANTHROPIC_API_KEY","C1_TEST_SENTINEL")
    monkeypatch.setenv("URI_PROVIDER_KEY_SECRET","C1_TEST_SENTINEL")
    env=child_environment(state,PYTHON)
    assert "ANTHROPIC_API_KEY" not in env and "URI_PROVIDER_KEY_SECRET" not in env
    assert Path(env["USERPROFILE"]).is_relative_to(state)
    assert Path(env["APPDATA"]).is_relative_to(state)
    assert Path(env["TEMP"]).is_relative_to(state)
    assert guard.counts=={"blocked_external_reads":1,"blocked_external_writes":1,"blocked_startup_connections":1,"blocked_startup_subprocesses":1}


def test_junction_escape_is_denied(manifest):
    state=Path(manifest.data["state_root"])
    link=state/"escape"
    r=subprocess.run(["cmd.exe","/c","mklink","/J",str(link),str(ROOT.parent)],capture_output=True)
    assert r.returncode==0
    guard=FixtureGuard(manifest)
    with pytest.raises(PermissionError):guard("open",(str(link/"private.db"),"r",os.O_RDONLY))
    with pytest.raises(PermissionError):guard("open",(str(link/"private.db"),"w",os.O_WRONLY))


def test_foreign_listener_never_adopted_or_signalled(manifest):
    class Echo(http.server.BaseHTTPRequestHandler):
        requests=0
        def do_GET(self):
            type(self).requests+=1
            self.send_response(200);self.end_headers();self.wfile.write(b'{"status":"ok"}')
        def log_message(self,*args):pass
    foreign=http.server.ThreadingHTTPServer(("127.0.0.1",manifest.data["port"]),Echo)
    thread=threading.Thread(target=foreign.serve_forever,daemon=True);thread.start()
    try:
        r=cli(manifest)
        assert r.returncode==1 and output(r)["code"]=="FOREIGN_LISTENER"
        assert listener(manifest.data["port"]).pid==os.getpid()
        assert Echo.requests==0
        assert http_call(manifest,"/health")[0]==200
    finally:foreign.shutdown();foreign.server_close();thread.join(5)


def test_live_concurrent_repeat_auth_stale_and_restart(manifest):
    command=["powershell.exe","-NoProfile","-ExecutionPolicy","Bypass","-File",str(ROOT/"scripts/uri_server.ps1"),
        "-Manifest",str(manifest.path),"-Action","start","-TimeoutSeconds","15"]
    # A stale PID points to THIS test runner. Start must neither signal nor adopt it.
    record=Path(manifest.data["control_root"])/"instance.json"
    atomic_json(record,{"pid":os.getpid(),"create_time":0})
    processes=[subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True) for _ in range(2)]
    results=[];owned=None
    try:
        for child in processes:
            out,err=child.communicate(timeout=30)
            assert child.returncode==0,(out,err)
            results.append(json.loads(out.strip()))
        assert sorted(r["result"] for r in results)==["ALREADY_RUNNING","STARTED"]
        assert len({r["pid"] for r in results})==1
        assert len({r["generation"] for r in results})==1
        owned=owned_instance(manifest,listener(manifest.data["port"]))
        assert all(r["pid"]==owned["pid"] for r in results)
        assert psutil.Process(os.getpid()).is_running()
        assert http_call(manifest,"/health")[0]==200
        assert http_call(manifest,"/runtime/status")[0]==401
        assert http_call(manifest,"/runtime/status",token="invalid-c1-token")[0]==401
        assert http_call(manifest,"/runtime/identity?nonce=bad")[0]==400
        code,account=http_call(manifest,"/auth/signup",{"username":"c1_live_user","password":secrets.token_urlsafe(24)})
        assert code==200
        code,status=http_call(manifest,"/runtime/status",token=account["token"])
        assert code==200
        assert status["readiness"]["http"]==status["readiness"]["public_catalogue"]==status["readiness"]["legacy_synthetic_state"]=="READY"
        assert status["readiness"]["main_brain"]==status["readiness"]["edge"]=="NOT_SELECTED"
        assert status["startup_controls"]["blocked_external_reads"]==status["startup_controls"]["blocked_external_writes"]==0
        assert status["startup_controls"]["blocked_startup_subprocesses"]==0
        assert str(ROOT) not in json.dumps(status) and account["token"] not in json.dumps(status)
        code,user=http_call(manifest,"/auth/signup",{"username":"c1_nonadmin","password":secrets.token_urlsafe(24)})
        assert code==200 and http_call(manifest,"/runtime/status",token=user["token"])[0]==200
        assert (Path(manifest.data["state_root"])/"uri_workspace/portable_identity.json").exists()
        atomic_json(record,{"pid":os.getpid(),"create_time":0})
        repeated=output(cli(manifest))
        assert repeated["result"]=="ALREADY_RUNNING" and repeated["pid"]==owned["pid"]
        assert json.loads(record.read_text())["pid"]==owned["pid"]
        # Same ID on another port cannot create a competing server.
        altered=manifest.data|{"port":free_port()}
        atomic_json(manifest.path,altered)
        try:
            r=cli(RuntimeManifest(manifest.path))
            assert r.returncode==1 and output(r)["code"]=="INSTANCE_LOCKED"
            assert listener(altered["port"]) is None
        finally:atomic_json(manifest.path,manifest.data)
        assert owned_instance(manifest,listener(manifest.data["port"]))==owned
        stop_owned(manifest,owned);owned=None
        r=cli(manifest);assert r.returncode==0
        restarted=output(r);assert restarted["result"]=="STARTED"
        assert restarted["generation"]!=results[0]["generation"]
        owned=owned_instance(manifest,listener(manifest.data["port"]))
    finally:
        if owned:stop_owned(manifest,owned)


def test_timeout_reports_attempt_then_reconciles_without_duplicate(manifest):
    r=subprocess.run([str(PYTHON),"-B","-I",str(ROOT/"scripts/uri_server_launcher.py"),"start",
        "--manifest",str(manifest.path),"--timeout","0.001"],capture_output=True,text=True)
    assert r.returncode==1 and output(r)["code"]=="STARTUP_TIMEOUT"
    assert type(output(r)["attempt_pid"]) is int
    deadline=time.monotonic()+15;owned=None
    try:
        while time.monotonic()<deadline:
            proc=listener(manifest.data["port"])
            if proc:
                try:owned=owned_instance(manifest,proc);break
                except RuntimeIdentityError:pass
            time.sleep(.1)
        assert owned is not None
        second=output(cli(manifest))
        assert second["result"]=="ALREADY_RUNNING" and second["pid"]==owned["pid"]
    finally:
        if owned:stop_owned(manifest,owned)


def test_failed_bootstrap_never_claims_ready(manifest):
    # Test-only protected-key loss, no original profile or configuration touched.
    key=Path(manifest.data["control_root"])/"signing_key.dpapi"
    key.rename(key.with_suffix(".test-preserved"))
    r=cli(manifest)
    assert r.returncode==1 and output(r)["code"]=="START_PROCESS_EXITED"
    assert listener(manifest.data["port"]) is None
    assert not (Path(manifest.data["control_root"])/"instance.json").exists()
