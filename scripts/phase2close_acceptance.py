"""Phase 2 closure: physical acceptance campaign helper (procedure: docs/plans/PHASE2CLOSE_PHYSICAL_ACCEPTANCE_RUNBOOK.md).

It automates what can be automated around the owner's physical session and records what only the owner can do.
It never logs in, reads or copies credentials, edits launchers/shortcuts/scheduled tasks/ports, or changes any
production root: everything it creates lives under <repo>/work/c1/acceptance-* (git-ignored), on a non-production port.

  preflight  read-only readiness checks -> JSON (tree vs accepted candidate, frozen checkpoint, interpreters, Flutter,
             CLIs present and their CURRENT login state as the CLIs themselves report it, Hyper-V presence)
  provision  a fresh isolated Phase 2 server + paired client + per-installation opt-in file, and the exact commands to
             start the Phase 2 server profile and the real URI app against it
  qualify    AFTER the owner logged a CLI in INSIDE the acceptance client profile: run the direct probe and the CLI's own
             login-status check under that profile; persist a signed NATIVE_QUALIFIED record into the acceptance
             client root ONLY when both succeed (otherwise nothing is written: fail closed)
  record     append the owner's observation for one runbook gate (PASS / FAIL / BLOCKED + note) to the campaign ledger
  collect    gather the campaign's execution records, server refusal lines and the gate ledger into one evidence JSON
  login-guide  print (never run) the exact interactive login command for one CLI inside the acceptance client profile
  status     per provider, the four separate states: INSTALLED, AUTHENTICATED (client profile), QUALIFIED (a signed
             record that re-validates under the worker's rules now), OPERATIONAL (the owner recorded PA-10 PASS)

Operational qualification (EXE-1, 2026-10-08): CLIs are qualified as their NATIVE binaries (`codex.exe` from the npm
vendor directory, `claude.exe` from the npm package), never as the `.cmd` launchers; the worker's sanitized PATH has no
`node` and is not widened. The Codex Windows sandbox backend of the client profile is the OWNER's choice (EXE-1b):
`provision --codex-sandbox unelevated|elevated` writes it into the client profile's own Codex home only when no config
file exists; without it the worker refuses Codex records. Measured: `unelevated` confines writes, NOT network.

Statuses written here are the OWNER's observations; this script never marks a physical gate passed by itself.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT.parent / "evidence"
ACCEPTED = EVIDENCE / "phase2ops-candidate-20261008-r6.zip"
ACCEPTED_SHA = "9a0be52c1ae5e59bf9ae16617e283c5a9f58ba098a1c2ae1d9649e184affb50a"
FROZEN = ROOT.parent.parent / "uri-phase1-integration" / "uri-agent" / "work" / "c1" / "checkpoints" / "final-closure-20261005-phase1.zip"
FROZEN_SHA = "31a34dcbb37ee48e1b06a1bcd60418a2e52ff9a0c65fd8cc7f3c59defeb98cf7"
OPT_IN = {"schema": "uri.phase2ops.ui_profile.v1", "worker_profile": "phase2d-supervised"}
GATES = ("PA-1 launch", "PA-2 approve", "PA-3 deny", "PA-4 cancel-before-dispatch", "PA-5 cancel-after-dispatch",
         "PA-6 close-restart-reconnect", "PA-7 worker-server-interruption", "PA-8 native-codex-login",
         "PA-9 native-claude-login", "PA-10 native-execution-in-worker", "PA-11 power-loss-vm", "PA-12 c7-cutover-authorization",
         "PA-13 chat-supervised-handoff")


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run(cmd, env=None, timeout=60):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=timeout,
                           stdin=subprocess.DEVNULL, env=env)
        return {"exit": r.returncode, "stdout": r.stdout.strip()[-400:], "stderr": r.stderr.strip()[-400:]}
    except FileNotFoundError:
        return {"exit": None, "error": "NOT_FOUND"}
    except subprocess.TimeoutExpired:
        return {"exit": None, "error": "TIMED_OUT"}


def preflight(a):
    out = {"taken": time.strftime("%Y-%m-%dT%H:%M:%S"), "checks": {}}
    c = out["checks"]
    c["accepted_candidate"] = {"path": str(ACCEPTED), "sha256_ok": ACCEPTED.is_file() and sha256(ACCEPTED) == ACCEPTED_SHA}
    c["frozen_phase1_checkpoint"] = {"path": str(FROZEN), "sha256_ok": FROZEN.is_file() and sha256(FROZEN) == FROZEN_SHA}
    if FROZEN.is_file():
        z = zipfile.ZipFile(FROZEN)
        drift = [n for n in z.namelist() if not n.endswith("/") and (ROOT / n).is_file()
                 and hashlib.sha256((ROOT / n).read_bytes()).hexdigest() != hashlib.sha256(z.read(n)).hexdigest()]
        c["frozen_files_byte_identical"] = {"ok": not drift, "drift": drift[:20]}
    c["git_head"] = run(["git", "-C", str(ROOT), "rev-parse", "--short", "HEAD"])
    c["venv_interpreter"] = {"ok": (ROOT / ".venv/Scripts/python.exe").is_file()}
    flutter = Path.home() / "flutter/bin/flutter.bat"
    c["flutter"] = {"ok": flutter.is_file(), "path": str(flutter)}
    c["windows_release_build"] = {"present": (ROOT / "uri_ui/build/windows/x64/runner/Release/uri_ui.exe").is_file()}
    sys.path.insert(0, str(ROOT))
    from uri_supervisor_bridge import qualification as q
    for name, cmd in (("codex_cli", ["codex", "--version"]), ("claude_code", ["claude", "--version"])):
        exe = shutil.which(name.split("_")[0])
        c[name] = {"executable": exe, "version": run([exe, "--version"]) if exe else {"error": "NOT_ON_PATH"}}
        try:
            native = q.native_executable(name, exe) if exe else None
            chain = q.launch_chain_for(name, native) if native else ({}, {})
            c[name]["native"] = {"executable": str(native) if native else None, "sha256": sha256(native) if native else None,
                                 "pinned_files": len(chain[0]), "resolve_pins": sorted(chain[1]),
                                 "version_sanitized_env": run([str(native), "--version"], env=_sanitized_probe_env())
                                 if native else None}
        except q.QualificationError as exc:
            c[name]["native"] = {"error": exc.code, "detail": exc.detail}
    # Login state as the CLIs report it, in the CURRENT shell profile (the client-profile state is checked by the
    # worker's own qualification at run time). No credential file is read.
    codex, claude = shutil.which("codex"), shutil.which("claude")
    if codex:
        r = run([codex, "login", "status"])
        c["codex_cli"]["shell_login_status"] = {"exit": r.get("exit"), "logged_in": "Logged in" in (r.get("stdout", "") + r.get("stderr", ""))}
    if claude:
        r = run([claude, "auth", "status"])
        txt = r.get("stdout", "")
        c["claude_code"]["shell_login_status"] = {"exit": r.get("exit"), "logged_in": '"loggedIn": true' in txt or '"loggedIn":true' in txt}
    hv = run(["powershell", "-NoProfile", "-Command", "(Get-Command Stop-VM -ErrorAction SilentlyContinue) -ne $null"])
    c["hyper_v_cmdlets"] = {"present": hv.get("stdout", "").strip().lower() == "true"}
    # PA-11 rig (operational qualification): which hard-power-off hypervisor tools exist here. Read-only.
    pf = os.environ.get("ProgramFiles", r"C:\Program Files")
    pf86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
    vbox = shutil.which("VBoxManage") or next((str(x) for x in (Path(pf) / "Oracle/VirtualBox/VBoxManage.exe",) if x.is_file()), None)
    vmrun = shutil.which("vmrun") or next((str(x) for x in (Path(pf86) / "VMware/VMware Workstation/vmrun.exe",
                                                           Path(pf) / "VMware/VMware Workstation/vmrun.exe") if x.is_file()), None)
    hp = run(["powershell", "-NoProfile", "-Command", "(Get-CimInstance Win32_ComputerSystem).HypervisorPresent"])
    c["vm_tooling"] = {"virtualbox_vboxmanage": vbox, "vmware_vmrun": vmrun,
                       "windows_hypervisor_present": hp.get("stdout", "").strip().lower() == "true",
                       "note": "PA-11 needs one of these hypervisors and a throwaway Windows VM; see the runbook"}
    out["ready_for_session"] = all([c["accepted_candidate"]["sha256_ok"], c["frozen_phase1_checkpoint"]["sha256_ok"],
                                    c.get("frozen_files_byte_identical", {}).get("ok", False), c["venv_interpreter"]["ok"],
                                    c["flutter"]["ok"]])
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def _sanitized_probe_env():
    """A worker-like environment for a read-only `--version` (no PATH beyond System32, no credentials)."""
    sr = os.environ.get("SYSTEMROOT", r"C:\Windows")
    return {"SYSTEMROOT": sr, "WINDIR": os.environ.get("WINDIR", sr), "PATH": str(Path(sr) / "System32")}


def codex_client_config(mode):
    return ('# Written by scripts/phase2close_acceptance.py provision --codex-sandbox (owner choice, EXE-1b).\n'
            '# unelevated: writes confined to the workspace, network NOT confined (measured 2026-10-08).\n'
            '# elevated: needs a one-time administrator setup by Codex; network restricted per Codex.\n'
            f'[windows]\nsandbox = "{mode}"\n')


def write_codex_client_config(client_root, mode):
    """EXE-1b (owner decision): create `<client>/home/.codex/config.toml` selecting the owner's chosen Windows sandbox
    backend, ONLY when that file does not exist (an existing owner file is never overwritten). Returns the mode in
    effect afterwards (None if an existing file selects none)."""
    if mode not in ("unelevated", "elevated"):
        raise SystemExit("CODEX_SANDBOX_MODE_INVALID")
    from uri_supervisor_bridge.qualification import client_cli_homes, codex_windows_sandbox_mode
    home = Path(client_cli_homes(client_root)["CODEX_HOME"])
    cfg = home / "config.toml"
    if not cfg.exists():
        with open(cfg, "x", encoding="utf-8") as fh:
            fh.write(codex_client_config(mode))
    return codex_windows_sandbox_mode(home)


def provision(a):
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from phase2d.conftest import HARNESS_ROWS  # noqa: E402  (the same policy rows the accepted tests use)
    from scripts.uri_server_launcher import listener
    from uri_core.client_runtime.manifest import ClientManifest, provision_client
    from uri_core.core.client_pairing import ClientPairingStore
    from uri_core.core.runtime_identity import RuntimeManifest, atomic_json, provision as provision_server
    from uri_supervisor_bridge.composition import policy_path, write_policy
    if Path(sys.executable).resolve() != (ROOT / ".venv/Scripts/python.exe").resolve():
        raise SystemExit("RUN_WITH_THE_WORKTREE_VENV: " + str(ROOT / ".venv/Scripts/python.exe"))
    base = ROOT / "work/c1" / ("acceptance-" + time.strftime("%Y%m%d-%H%M%S"))
    port = a.port or next(p for p in range(18300, 18340) if listener(p) is None)
    server = RuntimeManifest(provision_server(ROOT, base / "server", Path(sys.executable), port, "c2-paired-core"))
    write_policy(policy_path(server.data["state_root"]), HARNESS_ROWS)
    client = ClientManifest(provision_client(server.path, base / "client", str(uuid.uuid4()), ["remember_fact"]))
    if a.grant_harness:
        store = ClientPairingStore(server.data["control_root"], server.data["server_id"])
        with store.lock:
            data = store._load()
            data["clients"][client.data["client_id"]]["grants"].append("external_harness_task")
            atomic_json(store.path, data)
    client_root = Path(client.data["client_root"])
    atomic_json(client_root / "control" / "ui-supervised-profile.json", OPT_IN)
    # EXE-1b: the backend decides whether Codex commands get network access; it is chosen by the owner, never here.
    codex_sandbox = write_codex_client_config(client_root, a.codex_sandbox) if a.codex_sandbox else None
    campaign = {"schema": "uri.phase2close.acceptance.v1", "base": str(base), "port": port,
                "server_manifest": str(server.path), "client_manifest": str(client.path), "client_root": str(client_root),
                "client_profile_home": str(client_root / "home"), "harness_grant": bool(a.grant_harness),
                "codex_client_sandbox_mode": codex_sandbox,
                "provisioned": time.strftime("%Y-%m-%dT%H:%M:%S"), "gates": []}
    (base / "campaign.json").write_text(json.dumps(campaign, indent=1), encoding="utf-8")
    py = str(ROOT / ".venv/Scripts/python.exe")
    print(json.dumps(campaign, indent=1))
    print("\nStart the Phase 2 server profile (keep this window open):")
    print(f'  "{py}" -B -I "{ROOT / "scripts/run_uri_phase2_server.py"}" --manifest "{server.path}"')
    print("\nLaunch the real URI app against this client (second window):")
    print(f'  $env:URI_CLIENT_MANIFEST = "{client.path}"; cd "{ROOT / "uri_ui"}"; flutter run -d windows')
    print("\nCampaign file:", base / "campaign.json")
    return 0


def client_profile_env(client_root):
    """The home variables the worker's child environment uses (`runtime_identity.child_environment`): a CLI login
    performed under these is the client-profile login the worker can see; the owner's own profile is never used."""
    from uri_supervisor_bridge.qualification import client_cli_homes
    home = Path(client_root) / "home"
    # ISO-1: the profile variables alone do not isolate Codex (it resolves the Windows profile itself); CODEX_HOME does.
    return {"USERPROFILE": str(home), "HOME": str(home), "APPDATA": str(home / "roaming"), "LOCALAPPDATA": str(home / "local"),
            **client_cli_homes(client_root)}


SECRETISH = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


def probe_environment(client_root, base):
    """D1 (closure review round 1): the environment `qualify` probes under. It is the caller's environment MINUS every
    provider credential variable (each built-in executor's `auth_env` except the CODEX_HOME pin, the never-forward set,
    and any *_API_KEY / *_TOKEN / *_SECRET / *_PASSWORD name), PLUS the client-profile homes. A shell token can
    therefore never make the probe or the login-status check succeed: only a login stored under the client profile can.
    Returns (environment, names_removed); values are never returned or logged."""
    from uri_supervisor.executors import BUILTIN_SPECS, NEVER_FORWARD
    token_vars = {v for spec in BUILTIN_SPECS.values() for v in spec.auth_env if v != "CODEX_HOME"} | set(NEVER_FORWARD)
    removed = sorted(k for k in base if k in token_vars or k.upper().endswith(SECRETISH))
    env = {k: v for k, v in base.items() if k not in removed}
    env.update(client_profile_env(client_root))
    return env, removed


def _load_p2c():
    import importlib.util
    spec = importlib.util.spec_from_file_location("p2c", ROOT / "scripts" / "phase2c_native_qualification.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def qualify(a):
    import importlib.util
    sys.path.insert(0, str(ROOT))
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from phase2d.conftest import client_identity
    from uri_supervisor_bridge import qualification as q
    build_record, write_record = q.build_record, q.write_record
    p, data = _campaign(a.campaign)
    client_root = Path(data["client_root"])
    p2c = _load_p2c()
    evidence = Path(data["base"]) / "qualification" / a.provider
    evidence.mkdir(parents=True, exist_ok=True)
    profile = client_profile_env(client_root)
    saved = dict(os.environ)
    sanitized, removed = probe_environment(client_root, saved)
    os.environ.clear()
    os.environ.update(sanitized)              # only for this process's probe; restored below
    try:
        # EXE-1: probe and qualify the NATIVE binary (the worker cannot start the npm `.cmd` launchers).
        try:
            native = q.native_executable(a.provider, shutil.which({"codex_cli": "codex", "claude_code": "claude"}[a.provider],
                                                                 path=saved.get("PATH")))
        except q.QualificationError as exc:
            native = None
            launch_error = exc.code
        else:
            launch_error = None if native else "NOT_INSTALLED"
        probe = p2c.direct_probe(a.provider, a.model, evidence, executable=native) if native else {"ok": False, "status": launch_error}
        exe = probe.get("executable")
        live = q.native_auth_probe(a.provider, exe) if exe else None
    finally:
        os.environ.clear()
        os.environ.update(saved)
    probe_file = evidence / "probe.json"
    probe_file.write_text(json.dumps(probe, indent=1, default=str), encoding="utf-8")
    result = {"provider": a.provider, "model": a.model, "profile_home": profile["USERPROFILE"], "probe_status": probe.get("status"),
              "probe_ok": bool(probe.get("ok")), "live_auth": live, "persisted": False,
              "credential_vars_removed": removed, "when": time.strftime("%Y-%m-%dT%H:%M:%S")}
    if probe.get("ok") and live is True:
        cid, key = client_identity(client_root)
        rec = build_record(client_root=client_root, client_id=cid, signer=key, provider=a.provider, level="NATIVE_QUALIFIED",
                           spec_id=a.provider, executable=exe, executable_args=[], version=probe.get("version"), models=[a.model],
                           evidence_path=probe_file, qualified_by="scripts/phase2close_acceptance.py qualify",
                           notes="owner login inside the acceptance client profile + direct probe of the native binary + live auth status")
        write_record(client_root, rec)
        result.update(persisted=True, record={k: rec[k] for k in ("level", "version", "models", "expires_at", "record_sha256")})
    else:
        result["decision"] = "NOT PERSISTED (fail closed): the CLI is not usable under the client profile; owner login required"
    data.setdefault("qualifications", []).append(result)
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    print(json.dumps(result, indent=1, default=str))
    return 0 if result["persisted"] else 2


def _campaign(path):
    p = Path(path)
    p = p / "campaign.json" if p.is_dir() else p
    return p, json.loads(p.read_text(encoding="utf-8"))


def record(a):
    if a.gate not in GATES:
        raise SystemExit("UNKNOWN_GATE; one of: " + ", ".join(GATES))
    p, data = _campaign(a.campaign)
    data["gates"].append({"gate": a.gate, "result": a.result, "note": a.note, "observer": "owner",
                          "recorded": time.strftime("%Y-%m-%dT%H:%M:%S")})
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1), encoding="utf-8")
    os.replace(tmp, p)
    print(json.dumps(data["gates"][-1]))
    return 0


def collect(a):
    p, data = _campaign(a.campaign)
    client_root = Path(data["client_root"])
    recs = []
    for f in sorted((client_root / "control/supervisor/executions").glob("*.json")):
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
            recs.append({k: r.get(k) for k in ("execution_id", "state", "reason", "code", "queued_at", "ended_at",
                                                 "cancel_requested", "approval_retries", "task_id")}
                        | {"provider": (r.get("proposal") or {}).get("provider"), "model": (r.get("proposal") or {}).get("model")})
        except Exception as exc:  # noqa: BLE001
            recs.append({"file": f.name, "error": type(exc).__name__})
    refusals = []
    for log in Path(data["base"]).rglob("phase2-server.log"):
        refusals += [l for l in log.read_text(encoding="utf-8", errors="replace").splitlines() if l.startswith("CLIENT_REFUSAL")]
    last = {}
    for g in data["gates"]:
        last[g["gate"]] = g["result"]
    out = {"campaign": str(p), "collected": time.strftime("%Y-%m-%dT%H:%M:%S"), "executions": recs, "client_refusals": refusals,
           "gate_results": {g: last.get(g, "PENDING") for g in GATES}, "gate_log": data["gates"]}
    text = json.dumps(out, indent=1)
    if a.out:
        Path(a.out).write_text(text, encoding="utf-8")
    print(text)
    return 0


def login_guide(a):
    """Print the interactive login command for one CLI inside the acceptance client profile. Never runs it, never reads
    or copies a credential: the owner types the login in a NEW PowerShell window, under the client-profile homes."""
    sys.path.insert(0, str(ROOT))
    from uri_supervisor_bridge import qualification as q
    p, data = _campaign(a.campaign)
    client_root = Path(data["client_root"])
    env = client_profile_env(client_root)
    native = q.native_executable(a.provider)
    if native is None:
        raise SystemExit("NOT_INSTALLED: " + a.provider)
    sets = "; ".join(f'$env:{k} = "{v}"' for k, v in env.items())
    clear = "Remove-Item Env:CODEX_API_KEY, Env:OPENAI_API_KEY, Env:ANTHROPIC_API_KEY, Env:CLAUDE_CODE_OAUTH_TOKEN -ErrorAction SilentlyContinue"
    login = {"codex_cli": f'& "{native}" login', "claude_code": f'& "{native}" auth login'}[a.provider]
    status = {"codex_cli": f'& "{native}" login status', "claude_code": f'& "{native}" auth status'}[a.provider]
    print("Open a NEW PowerShell window (not an elevated one) and run, in order:\n")
    print("  " + clear)
    print("  " + sets)
    print("  " + login)
    print("  " + status + "    # must report logged in; this login lives ONLY in " + env["USERPROFILE"])
    print("\nThen close that window and run:\n")
    print(f'  "{ROOT / ".venv/Scripts/python.exe"}" -I "{Path(__file__).resolve()}" qualify "{p}" --provider {a.provider}'
          + (" --model <model>" if a.provider == "codex_cli" else ""))
    print("\nThe owner's own logins are not used and not changed. Do not copy credential files between profiles.")
    return 0


def status(a):
    """Four states per provider, each from its own evidence; none implies the next."""
    sys.path.insert(0, str(ROOT))
    sys.path.insert(0, str(ROOT / "tests"))
    from phase2d.conftest import trust_for
    from uri_supervisor_bridge import qualification as q
    p, data = _campaign(a.campaign)
    client_root = Path(data["client_root"])
    saved = dict(os.environ)
    sanitized, _removed = probe_environment(client_root, saved)
    gates = {}
    for g in data.get("gates", []):
        gates[g["gate"]] = g["result"]
    out = {"campaign": str(p), "taken": time.strftime("%Y-%m-%dT%H:%M:%S"), "providers": {}}
    codex_home = q.client_cli_homes(client_root, create=False)["CODEX_HOME"]
    records = {r["record"]["provider"]: r for r in q.load_records(client_root) if r["record"]}
    for provider, gate in (("codex_cli", "PA-8 native-codex-login"), ("claude_code", "PA-9 native-claude-login")):
        row = {}
        try:
            native = q.native_executable(provider)
        except q.QualificationError as exc:
            native, row["launch_error"] = None, exc.code
        row["installed"] = native is not None
        row["native_executable"] = str(native) if native else None
        os.environ.clear()
        os.environ.update(sanitized)
        try:
            row["authenticated_client_profile"] = q.native_auth_probe(provider, str(native)) if native else None
            rec = records.get(provider)
            if rec is None:
                row["qualified"], row["qualification_reason"] = False, "NO_RECORD"
            else:
                try:
                    q.revalidate(rec["record"], client_root=client_root, trust=trust_for(client_root),
                                 codex_home=codex_home if provider == "codex_cli" else None)
                    row["qualified"], row["qualification_reason"] = True, None
                except q.QualificationError as exc:
                    row["qualified"], row["qualification_reason"] = False, exc.code
        finally:
            os.environ.clear()
            os.environ.update(saved)
        row["login_gate"] = gates.get(gate, "PENDING")
        row["operational"] = gates.get("PA-10 native-execution-in-worker") == "PASS" and provider == "codex_cli"
        out["providers"][provider] = row
    out["codex_client_sandbox_mode"] = q.codex_windows_sandbox_mode(codex_home)
    print(json.dumps(out, indent=1))
    return 0


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)
    s = sub.add_parser("preflight")
    s.add_argument("--out")
    s = sub.add_parser("provision")
    s.add_argument("--port", type=int, default=None)
    s.add_argument("--grant-harness", action="store_true", help="grant external_harness_task to the acceptance client")
    s.add_argument("--codex-sandbox", choices=("unelevated", "elevated"), default=None,
                   help="owner choice (EXE-1b): the client profile's Codex Windows sandbox backend; without it the worker "
                        "refuses Codex records (CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED)")
    s = sub.add_parser("qualify")
    s.add_argument("campaign")
    s.add_argument("--provider", required=True, choices=("codex_cli", "claude_code"))
    s.add_argument("--model", default=None)
    s = sub.add_parser("record")
    s.add_argument("campaign")
    s.add_argument("gate")
    s.add_argument("result", choices=("PASS", "FAIL", "BLOCKED"))
    s.add_argument("--note", default="")
    s = sub.add_parser("login-guide")
    s.add_argument("campaign")
    s.add_argument("--provider", required=True, choices=("codex_cli", "claude_code"))
    s = sub.add_parser("status")
    s.add_argument("campaign")
    s = sub.add_parser("collect")
    s.add_argument("campaign")
    s.add_argument("--out")
    a = ap.parse_args()
    return {"preflight": preflight, "provision": provision, "qualify": qualify, "record": record, "collect": collect,
            "login-guide": login_guide, "status": status}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
