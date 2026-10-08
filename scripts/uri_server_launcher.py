"""Opt-in Windows C1 start/status. No stop/restart/install actions."""
import sys

# Launcher process: C1 isolated-mode gate FIRST, before any import the script directory could shadow.
# (When imported by the pinned server/worker or by tests, the importer already governs imports.)
if __name__ == "__main__" and not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import ctypes
import json
import os
from pathlib import Path
import secrets
import subprocess
import time
import urllib.request

if __name__=="__main__":  # launcher process (when imported, the importer has already set up imports)
    # C1 import gate, loaded by exact path BEFORE anything from the source root: the root never goes on
    # sys.path, and pinned packages compile only from plain source files (see scripts/c1_bootstrap.py).
    _C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
    c1_bootstrap = type(sys)("c1_bootstrap")
    c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
    exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
    sys.modules["c1_bootstrap"] = c1_bootstrap
    c1_bootstrap.install(_C1_BOOT.parents[1])
import psutil
from uri_core.core.runtime_identity import RuntimeManifest,RuntimeIdentityError,absolute,atomic_json,child_environment,install_source_pin,verify_proof


class NamedMutex:
    def __init__(self,name,timeout=30):self.name=name;self.timeout=timeout;self.handle=None
    def __enter__(self):
        if os.name!="nt":raise RuntimeIdentityError("WINDOWS_REQUIRED")
        k=ctypes.windll.kernel32
        k.CreateMutexW.argtypes=[ctypes.c_void_p,ctypes.c_bool,ctypes.c_wchar_p];k.CreateMutexW.restype=ctypes.c_void_p
        k.WaitForSingleObject.argtypes=[ctypes.c_void_p,ctypes.c_ulong];k.WaitForSingleObject.restype=ctypes.c_ulong
        k.ReleaseMutex.argtypes=[ctypes.c_void_p];k.CloseHandle.argtypes=[ctypes.c_void_p]
        self.handle=k.CreateMutexW(None,False,self.name)
        if not self.handle:raise RuntimeIdentityError("MUTEX_UNAVAILABLE")
        result=k.WaitForSingleObject(self.handle,int(self.timeout*1000))
        if result not in (0,0x80):
            k.CloseHandle(self.handle);self.handle=None
            raise RuntimeIdentityError("INSTANCE_LOCKED")
        return self
    def __exit__(self,*args):
        if self.handle:
            ctypes.windll.kernel32.ReleaseMutex(self.handle)
            ctypes.windll.kernel32.CloseHandle(self.handle)
            self.handle=None


def listener(port):
    try:
        rows=[r for r in psutil.net_connections(kind="tcp") if r.status==psutil.CONN_LISTEN and r.laddr.port==port]
    except (psutil.AccessDenied,OSError):raise RuntimeIdentityError("SOCKET_PROVENANCE_UNAVAILABLE") from None
    owners={r.pid for r in rows}
    if not rows:return None
    if None in owners or len(owners)!=1:raise RuntimeIdentityError("AMBIGUOUS_SOCKET_OWNER")
    return psutil.Process(next(iter(owners)))


def process_identity(manifest,proc):
    m=manifest.data
    expected=["-B","-I",m["entrypoint"],"--manifest",str(manifest.path)]
    try:
        argv=proc.cmdline()
        if absolute(proc.exe())!=absolute(m["process_image"]) or not argv or absolute(argv[0])!=absolute(m["interpreter"]) or argv[1:]!=expected:
            raise RuntimeIdentityError("FOREIGN_LISTENER")
        return {"pid":proc.pid,"create_time":proc.create_time()}
    except (psutil.Error,OSError):raise RuntimeIdentityError("PROCESS_PROVENANCE_UNAVAILABLE") from None


def owned_instance(manifest,proc):
    observed=process_identity(manifest,proc)
    nonce=secrets.token_hex(32)
    url=f'http://127.0.0.1:{manifest.data["port"]}/runtime/identity?nonce={nonce}'
    # Ignore parent proxy settings; never send a credential during identity discovery.
    opener=urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(url,timeout=2) as response:
            body=response.read(8193)
            if len(body)>8192:raise ValueError()
            result=json.loads(body)
        identity=verify_proof(manifest,result,nonce)
    except RuntimeIdentityError:raise
    except Exception:raise RuntimeIdentityError("IDENTITY_NOT_READY") from None
    # Recheck socket/process after HTTP to reject exit/PID reuse races.
    current=listener(manifest.data["port"])
    if current is None or process_identity(manifest,current)!=observed:
        raise RuntimeIdentityError("PROCESS_GENERATION_CHANGED")
    return observed|{"generation":identity["generation"],"server_id":identity["server_id"],
                     "manifest_digest":manifest.digest,"port":manifest.data["port"]}


def launch(manifest,action,timeout=30):
    m=manifest.data;record=Path(m["control_root"])/"instance.json"
    if action=="validate":return {"result":"VALID","server_id":m["server_id"],"manifest_digest":manifest.digest}
    # Server ID serializes repeat launches; port lock also covers different IDs.
    with NamedMutex("Local\\URI_Server_"+m["server_id"],timeout),NamedMutex("Local\\URI_Port_"+str(m["port"]),timeout):
        proc=listener(m["port"])
        if proc is not None:
            owned=owned_instance(manifest,proc)
            atomic_json(record,owned)
            return {"result":"ALREADY_RUNNING" if action=="start" else "RUNNING",**owned}
        if action=="status":return {"result":"NOT_RUNNING","server_id":m["server_id"]}
        # Record is advisory only. Never signal the PID it names. The lifetime
        # mutex rejects a live same-ID instance on a different port/root.
        with NamedMutex("Local\\URI_Instance_"+m["server_id"],0):pass
        log=Path(m["state_root"])/"logs/server.log"
        env=child_environment(Path(m["state_root"]),Path(m["interpreter"]))
        with open(log,"ab",buffering=0) as output:
            child=subprocess.Popen([m["interpreter"],"-B","-I",m["entrypoint"],"--manifest",str(manifest.path)],
                cwd=m["state_root"],env=env,stdin=subprocess.DEVNULL,stdout=output,stderr=output,
                creationflags=subprocess.CREATE_NO_WINDOW)
        parent_start=psutil.Process(child.pid).create_time()
        deadline=time.monotonic()+timeout
        while time.monotonic()<deadline:
            proc=listener(m["port"])
            if proc is not None:
                process_identity(manifest,proc)  # Wrong listener fails immediately.
                try:
                    # A matching server must descend from this exact launch.
                    ancestors=proc.parents()
                    is_child=(proc.pid==child.pid and proc.create_time()==parent_start) or any(p.pid==child.pid and p.create_time()==parent_start for p in ancestors)
                    if not is_child:raise RuntimeIdentityError("UNRELATED_MATCHING_PROCESS")
                    owned=owned_instance(manifest,proc)
                    atomic_json(record,owned)
                    return {"result":"STARTED",**owned}
                except RuntimeIdentityError as exc:
                    if str(exc)!="IDENTITY_NOT_READY":raise
            if child.poll() is not None:raise RuntimeIdentityError("START_PROCESS_EXITED")
            time.sleep(.1)
        # No process-name or stale-PID termination on timeout. A later invocation
        # may identify this attempt, but this invocation never claims readiness.
        raise RuntimeIdentityError("STARTUP_TIMEOUT",attempt_pid=child.pid)


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=("validate","start","status"))
    parser.add_argument("--manifest",required=True)
    parser.add_argument("--timeout",type=float,default=30)
    args=parser.parse_args()
    try:
        if not 0<args.timeout<=60:raise RuntimeIdentityError("TIMEOUT_INVALID")
        manifest=RuntimeManifest(args.manifest)
        # The launcher process too must have executed exactly the validated bytes.
        install_source_pin(absolute(manifest.data["source_root"]),manifest.data["source_files"])
        result=launch(manifest,args.action,args.timeout)
        print(json.dumps(result));return 0
    except RuntimeIdentityError as exc:
        result={"result":"REFUSED","code":str(exc)}
        if exc.attempt_pid is not None:result["attempt_pid"]=exc.attempt_pid
        print(json.dumps(result));return 1
    except Exception:
        print(json.dumps({"result":"REFUSED","code":"RUNTIME_VALIDATION_FAILED"}));return 1


if __name__=="__main__":sys.exit(main())
