"""C3 opt-in manifest launcher. No server, model or production lifecycle."""
import sys

# Launcher process: C1 isolated-mode gate FIRST, before any import the script directory could shadow.
# (When imported by the pinned worker or by tests, the importer already governs imports.)
if __name__ == "__main__" and not sys.flags.isolated:
    raise SystemExit("C1_ISOLATED_MODE_REQUIRED")
import argparse
import json
from pathlib import Path
import subprocess

if __name__ == "__main__":  # launcher process (when imported, the importer has already set up imports)
    # C1 import gate, loaded by exact path BEFORE anything from the source root: the root never goes on
    # sys.path, and pinned packages compile only from plain source files (see scripts/c1_bootstrap.py).
    _C1_BOOT = Path(__file__).resolve().parents[1] / "scripts" / "c1_bootstrap.py"
    c1_bootstrap = type(sys)("c1_bootstrap")
    c1_bootstrap.__file__, c1_bootstrap.SOURCE = str(_C1_BOOT), _C1_BOOT.read_bytes()
    exec(compile(c1_bootstrap.SOURCE, str(_C1_BOOT), "exec"), c1_bootstrap.__dict__)
    sys.modules["c1_bootstrap"] = c1_bootstrap
    c1_bootstrap.install(_C1_BOOT.parents[1])
from uri_core.client_runtime.manifest import ClientManifest
from uri_core.core.runtime_identity import RuntimeIdentityError, child_environment, install_source_pin


def status(manifest):
    m = manifest.data
    path = Path(m["client_root"]) / "control/worker-instance.json"
    if not path.exists():
        return {"result": "NOT_RUNNING"}
    import psutil
    try:
        record = json.loads(path.read_text())
        proc = psutil.Process(record["pid"])
        cmd = proc.cmdline()
        if (proc.create_time() != record["create_time"] or record["manifest_digest"] != manifest.digest or
                record["client_id"] != m["client_id"] or Path(proc.exe()).resolve() != Path(m["process_image"]).resolve() or
                len(cmd) != 6 or Path(cmd[0]).resolve() != Path(m["interpreter"]).resolve() or
                cmd[1:] != ["-B", "-I", m["worker_entrypoint"], "--manifest", str(manifest.path)]):
            return {"result": "STALE_OR_FOREIGN_RECORD"}
        return {"result": "PROCESS_PRESENT", "pid": proc.pid, "generation": record["generation"]}
    except (KeyError, ValueError, OSError, psutil.Error):
        return {"result": "STALE_OR_FOREIGN_RECORD"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=("validate", "launch", "status"))
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--headless", action="store_true")
    a = parser.parse_args()
    try:
        manifest = ClientManifest(a.manifest)
        m = manifest.data
        # The launcher process too must have executed exactly the validated bytes.
        install_source_pin(Path(m["source_root"]).resolve(), manifest.source_files)
        if a.action == "validate":
            print(json.dumps({"result": "VALID", "client_id": m["client_id"], "ui": "UNQUALIFIED" if m["ui_binary"] is None else "PINNED"}))
            return 0
        observed = status(manifest)
        if a.action == "status":
            print(json.dumps(observed))
            return 0
        if observed["result"] == "PROCESS_PRESENT":
            print(json.dumps({**observed, "result": "ALREADY_PRESENT"}))
            return 0
        if not a.headless:
            raise RuntimeIdentityError("CLIENT_UI_PENDING_C6")
        # Foreground stdio ownership is deliberate; worker exits on EOF.
        # UI-owned hidden launch is the C6 consumer of this exact entrypoint.
        return subprocess.call([m["interpreter"], "-B", "-I", m["worker_entrypoint"], "--manifest", str(manifest.path)],
                               cwd=m["client_root"], env=child_environment(Path(m["client_root"]), Path(m["interpreter"])))
    except Exception:
        print('{"result":"REFUSED","code":"CLIENT_LAUNCH_REFUSED"}')
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
