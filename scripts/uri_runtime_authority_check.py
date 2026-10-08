"""URI Runtime Authority check: detect any URI runtime path on this machine that the authority manifest does not authorize.

Read-only. It never starts, stops, adopts or edits anything. It inspects:
  * Windows scheduled tasks and Run keys whose actions mention URI-like commands,
  * shortcut (.lnk) and script launchers in Desktop / Start Menu / Startup folders,
  * processes that look like URI servers, workers, desktop UIs or local model runtimes,
  * TCP listeners on the URI port range and the declared model ports,
  * the shared Flutter preferences file that every uri_ui build reads (server URL only, never tokens),
and classifies each finding against docs/governance/URI_RUNTIME_AUTHORITY_MANIFEST.json:

  AUTHORIZED           matches an authorized launcher/root of the authoritative runtime
  TRANSITIONAL_LEGACY  a known live legacy path, explicitly accounted for until owner-approved cutover
  DONOR_ONLY           belongs to a preserved donor root; must never run as URI
  QUARANTINED          belongs to a quarantined root
  SHARED_DEPENDENCY    legitimate shared developer tool (Ollama, LM Studio, Codex service, ...)
  UNACCOUNTED          a URI-like runtime path the manifest does not know at all

Exit codes:  0 = nothing DONOR_ONLY / QUARANTINED / UNACCOUNTED is active or auto-starting
             1 = at least one such finding (contamination)
             2 = the manifest itself is invalid
With --strict, TRANSITIONAL_LEGACY findings also fail (use this after cutover).

Usage:
  python scripts/uri_runtime_authority_check.py [--manifest PATH] [--json OUT] [--strict]
  python scripts/uri_runtime_authority_check.py --snapshot SNAPSHOT.json    # classify a recorded snapshot (tests)
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = ROOT / "docs" / "governance" / "URI_RUNTIME_AUTHORITY_MANIFEST.json"
FAIL_CLASSES = {"DONOR_ONLY", "QUARANTINED", "UNACCOUNTED"}
URI_HINT = re.compile(r"(?i)(uri[_-]?(agent|core|ui|server|desktop|client|worker|supervis)|run_uri_|launch_uri|launch_desktop|"
                      r"run_desktop_server|uri_server|uri_client|launch uri|\\uri\\|/uri/|uri-m3|uri_v1|uri_core\.app)")
# A process counts as a URI runtime only when it runs one of these entrypoints (servers, workers, launchers, UI,
# model servers). Test runners and interactive agent shells that merely mention URI paths are not runtimes.
RUNTIME_HINT = re.compile(r"(?i)(run_uri_server|uri_server_launcher|run_uri_isolated_server|run_uri_phase2_server|"
                          r"run_desktop_server|run_uri_client_worker|run_uri_supervised_worker|uri_client_launcher|"
                          r"launch_uri\.ps1|launch_desktop\.ps1|uri_server_ctl\.ps1|uri_server\.ps1|uri_client\.ps1|"
                          r"launch uri\.bat|uri_ui\.exe|uvicorn\s+uri_core|uri_core\.app\.server|llama-server)")
AGENT_SHELL = re.compile(r"(?i)(\.claude[\\/]shell-snapshots|CLAUDE_CODE_SHELL|__claudeCodeScript)")
REQUIRED_KEYS =("schema", "authoritative_runtime", "roots", "transitional_legacy", "shared_dependencies", "ports")


# ----------------------------------------------------------------------------------------------- manifest
class ManifestError(ValueError):
    pass


def norm(p: str) -> str:
    """Case-folded Windows path with forward slashes and no trailing slash; also accepts /c/... shell paths."""
    if not p:
        return ""
    s = str(p).strip().strip('"')
    m = re.match(r"^/([a-zA-Z])/(.*)$", s)
    if m:
        s = f"{m.group(1)}:/{m.group(2)}"
    s = s.replace("\\", "/")
    while "//" in s:
        s = s.replace("//", "/")
    return s.rstrip("/").casefold()


def load_manifest(path: Path) -> dict:
    try:
        m = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise ManifestError(f"cannot read manifest: {exc}") from exc
    missing = [k for k in REQUIRED_KEYS if k not in m]
    if missing:
        raise ManifestError(f"manifest missing keys: {missing}")
    if m["schema"] != "uri-runtime-authority/1":
        raise ManifestError("unsupported schema")
    for r in m["roots"]:
        if r.get("classification") not in {"ACTIVE_AUTHORITATIVE", "PRESERVED_DONOR_ONLY", "QUARANTINED_UNTRUSTED"}:
            raise ManifestError(f"bad root classification: {r}")
        if not r.get("path"):
            raise ManifestError(f"root without path: {r}")
    # A root may not be both authoritative and something else (overlap must be explicit and nested, never equal).
    seen = {}
    for r in m["roots"]:
        k = norm(r["path"])
        if k in seen and seen[k] != r["classification"]:
            raise ManifestError(f"root {r['path']} has conflicting classifications")
        seen[k] = r["classification"]
    return m


# ----------------------------------------------------------------------------------------------- classify
SEVERITY = {"QUARANTINED_UNTRUSTED": 3, "PRESERVED_DONOR_ONLY": 2, "ACTIVE_AUTHORITATIVE": 1}


def _root_for(text: str, roots: list[dict]) -> dict | None:
    """Root referenced by the command/target text (path-boundary aware).

    When several roots appear (for example an authorized binary started with a quarantined model or a donor state
    root), the MOST RESTRICTIVE classification wins, then the longest path. An authorized prefix can never launder
    a donor or quarantined path that appears elsewhere in the same command.
    """
    t = norm(text)
    best = None
    for r in roots:
        rp = norm(r["path"])
        idx = t.find(rp)
        while idx != -1:
            end = idx + len(rp)
            start_ok = idx == 0 or t[idx - 1] in '/" \'=:'
            if start_ok and (end == len(t) or t[end] in '/" \''):
                key = (SEVERITY[r["classification"]], len(rp))
                if best is None or key > (SEVERITY[best["classification"]], len(norm(best["path"]))):
                    best = r
                break
            idx = t.find(rp, idx + 1)
    return best


def classify(text: str, manifest: dict) -> tuple[str, str]:
    t = norm(text)
    for legacy in manifest["transitional_legacy"]:
        if norm(legacy["match"]) in t:
            return "TRANSITIONAL_LEGACY", legacy["id"]
    root = _root_for(text, manifest["roots"])
    if root is not None:
        cls = {"ACTIVE_AUTHORITATIVE": "AUTHORIZED", "PRESERVED_DONOR_ONLY": "DONOR_ONLY",
               "QUARANTINED_UNTRUSTED": "QUARANTINED"}[root["classification"]]
        if cls == "AUTHORIZED":
            # Each active root lists its own entrypoints; an empty list means nothing may run from that root.
            allowed = [norm(e) for e in root.get("entrypoints", [])]
            if not any(a in t for a in allowed):
                return "UNACCOUNTED", f"{root['id']}: inside authoritative root but not an authorized entrypoint"
        return cls, root["id"]
    for dep in manifest["shared_dependencies"]:
        if norm(dep["match"]) in t:
            return "SHARED_DEPENDENCY", dep["id"]
    return "UNACCOUNTED", "no manifest entry"


def evaluate(snapshot: dict, manifest: dict, strict: bool = False) -> dict:
    findings = []

    def add(kind, ident, text, active):
        cls, ref = classify(text, manifest)
        findings.append({"kind": kind, "id": ident, "detail": text[:400], "active_or_autostart": active,
                         "classification": cls, "manifest_ref": ref})

    for t in snapshot.get("scheduled_tasks", []):
        if URI_HINT.search(t["action"]) or URI_HINT.search(t["name"]):
            add("scheduled_task", t["name"], t["action"], t.get("enabled", True))
    for r in snapshot.get("run_keys", []):
        if URI_HINT.search(r["value"]):
            add("run_key", r["name"], r["value"], True)
    for s in snapshot.get("shortcuts", []):
        if URI_HINT.search(s["target"]) or URI_HINT.search(s["path"]):
            add("startup_shortcut" if s.get("startup") else "shortcut", s["path"], s["target"], bool(s.get("startup")))
    for p in snapshot.get("processes", []):
        cmd = p["cmdline"]
        if RUNTIME_HINT.search(cmd) and not AGENT_SHELL.search(cmd):
            add("process", f"pid {p['pid']}", cmd, True)
    uri_ports = set(range(manifest["ports"]["uri_range"][0], manifest["ports"]["uri_range"][1] + 1))
    for lst in snapshot.get("listeners", []):
        if lst["port"] in uri_ports or lst["port"] in manifest["ports"].get("model_ports", []):
            text = lst.get("cmdline") or lst.get("image") or ""
            add("listener", f"{lst['address']}:{lst['port']}", text or "<unknown owner>", True)
    prefs = snapshot.get("ui_preferences")
    if prefs and prefs.get("serverBaseUrl"):
        url = prefs["serverBaseUrl"]
        owner = next((f for f in findings if f["kind"] == "listener" and f["id"].endswith(":" + url.rsplit(":", 1)[-1].strip("/"))), None)
        cls = owner["classification"] if owner else "UNACCOUNTED"
        findings.append({"kind": "ui_server_binding", "id": "uri_ui shared_preferences serverBaseUrl", "detail": url,
                         "active_or_autostart": True, "classification": cls,
                         "manifest_ref": (owner or {}).get("manifest_ref", "no listener on that port")})
    fail = FAIL_CLASSES | ({"TRANSITIONAL_LEGACY"} if strict else set())
    bad = [f for f in findings if f["active_or_autostart"] and f["classification"] in fail]
    authoritative_running = any(f["kind"] == "listener" and f["classification"] == "AUTHORIZED" for f in findings)
    return {"schema": "uri-runtime-authority-report/1", "strict": strict, "findings": findings,
            "contamination": bad, "authoritative_runtime_running": authoritative_running,
            "verdict": "CONTAMINATED" if bad else ("CLEAN" if authoritative_running else "NO_UNAUTHORIZED_RUNTIME")}


# ----------------------------------------------------------------------------------------------- live probe
PS_PROBE = r"""
$ErrorActionPreference='SilentlyContinue'
$o=[ordered]@{}
$o.scheduled_tasks=@(Get-ScheduledTask | ForEach-Object { $t=$_; foreach($a in $t.Actions){ [pscustomobject]@{name=$t.TaskPath+$t.TaskName; enabled=($t.State -ne 'Disabled'); action=("$($a.Execute) $($a.Arguments) [wd=$($a.WorkingDirectory)]")} } })
$o.run_keys=@(foreach($k in 'HKCU:\Software\Microsoft\Windows\CurrentVersion\Run','HKLM:\Software\Microsoft\Windows\CurrentVersion\Run'){ $v=Get-ItemProperty $k; if($v){ $v.PSObject.Properties | Where-Object { $_.Name -notmatch '^PS' } | ForEach-Object { [pscustomobject]@{name="$k\$($_.Name)"; value="$($_.Value)"} } } })
$sh=New-Object -ComObject WScript.Shell
$dirs=@("$env:USERPROFILE\Desktop","$env:PUBLIC\Desktop","$env:USERPROFILE\OneDrive\Desktop","$env:APPDATA\Microsoft\Windows\Start Menu\Programs","$env:ProgramData\Microsoft\Windows\Start Menu\Programs")
$startup=@("$env:APPDATA\Microsoft\Windows\Start Menu\Programs\Startup","$env:ProgramData\Microsoft\Windows\Start Menu\Programs\StartUp")
$o.shortcuts=@(foreach($d in $dirs+$startup){ $isS=($startup -contains $d); if(Test-Path $d){ Get-ChildItem $d -Recurse -Include *.lnk,*.bat,*.cmd -File | ForEach-Object { $tg= if($_.Extension -eq '.lnk'){ $l=$sh.CreateShortcut($_.FullName); "$($l.TargetPath) $($l.Arguments) [wd=$($l.WorkingDirectory)]" } else { (Get-Content $_.FullName -TotalCount 40) -join ' ; ' }; [pscustomobject]@{path=$_.FullName; target=$tg; startup=$isS} } } })
$o.processes=@(Get-CimInstance Win32_Process | Where-Object { $_.CommandLine } | ForEach-Object { [pscustomobject]@{pid=$_.ProcessId; ppid=$_.ParentProcessId; image="$($_.ExecutablePath)"; cmdline="$($_.CommandLine)"} })
$procs=@{}; foreach($p in $o.processes){ $procs[[int]$p.pid]=$p }
$o.listeners=@(Get-NetTCPConnection -State Listen | ForEach-Object { $p=$procs[[int]$_.OwningProcess]; $cmd= if($p){$p.cmdline}else{''}; if($p -and $procs.ContainsKey([int]$p.ppid) -and $cmd -notmatch 'uri'){ $cmd = $cmd + ' <parent> ' + $procs[[int]$p.ppid].cmdline }; [pscustomobject]@{address=$_.LocalAddress; port=[int]$_.LocalPort; pid=[int]$_.OwningProcess; image= if($p){$p.image}else{''}; cmdline=$cmd} })
$pf="$env:APPDATA\com.example\uri_ui\shared_preferences.json"
if(Test-Path $pf){ $j=Get-Content $pf -Raw | ConvertFrom-Json; $o.ui_preferences=[pscustomobject]@{path=$pf; serverBaseUrl=$j.'flutter.uri.serverBaseUrl'} }
$o | ConvertTo-Json -Depth 5 -Compress
"""


def live_snapshot() -> dict:
    if os.name != "nt":
        raise SystemExit("live probe is Windows-only; use --snapshot")
    r = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_PROBE], capture_output=True,
                       timeout=240, stdin=subprocess.DEVNULL)
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(f"probe failed: {r.stderr.decode(errors='replace')[:400]}")
    snap = json.loads(r.stdout.decode("utf-8", errors="replace"))
    # The probe's own PowerShell process carries this source text, which mentions URI paths; drop it.
    # Privacy: keep only command lines that look like URI runtimes; never persist unrelated process command lines.
    snap["processes"] = [p for p in snap.get("processes") or [] if "uri_runtime_authority_check" not in p["cmdline"]
                         and "$o.scheduled_tasks" not in p["cmdline"] and RUNTIME_HINT.search(p["cmdline"])
                         and not AGENT_SHELL.search(p["cmdline"])]
    for lst in snap.get("listeners") or []:
        if not (RUNTIME_HINT.search(lst.get("cmdline", "")) or URI_HINT.search(lst.get("cmdline", ""))):
            lst["cmdline"] = ""  # keep only the image path for non-URI listeners
    for k in ("scheduled_tasks", "run_keys", "shortcuts", "processes", "listeners"):
        v = snap.get(k)
        snap[k] = [] if v is None else (v if isinstance(v, list) else [v])
    return snap


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    ap.add_argument("--snapshot", help="classify a recorded snapshot JSON instead of probing this machine")
    ap.add_argument("--save-snapshot", help="write the live snapshot (no secrets are collected) to this path")
    ap.add_argument("--json", help="write the full report here")
    ap.add_argument("--strict", action="store_true", help="also fail on TRANSITIONAL_LEGACY (post-cutover mode)")
    a = ap.parse_args(argv)
    try:
        manifest = load_manifest(Path(a.manifest))
    except ManifestError as exc:
        print(f"MANIFEST_INVALID: {exc}")
        return 2
    snap = json.loads(Path(a.snapshot).read_text(encoding="utf-8")) if a.snapshot else live_snapshot()
    if a.save_snapshot:
        Path(a.save_snapshot).write_text(json.dumps(snap, indent=1), encoding="utf-8")
    rep = evaluate(snap, manifest, strict=a.strict)
    if a.json:
        Path(a.json).write_text(json.dumps(rep, indent=1), encoding="utf-8")
    for f in rep["findings"]:
        print(f"{f['classification']:20} {f['kind']:17} {f['id'][:60]:60} -> {f['manifest_ref']}")
    print(f"VERDICT {rep['verdict']}  contamination={len(rep['contamination'])}  authoritative_running={rep['authoritative_runtime_running']}")
    return 1 if rep["contamination"] else 0


if __name__ == "__main__":
    sys.exit(main())
