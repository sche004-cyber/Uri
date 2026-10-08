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
    # Collapse '.' and '..' segments so 'C:/allowed/../../donor' can never match the 'C:/allowed' prefix.
    out = []
    for seg in s.split("/"):
        if seg == ".":
            continue
        if seg == ".." and out and out[-1] not in ("..", "") and not re.fullmatch(r"[A-Za-z]:", out[-1]):
            out.pop()
            continue
        out.append(seg)
    return "/".join(out).rstrip("/").casefold()


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


CLS = {"ACTIVE_AUTHORITATIVE": "AUTHORIZED", "PRESERVED_DONOR_ONLY": "DONOR_ONLY", "QUARANTINED_UNTRUSTED": "QUARANTINED"}
# Worst first: when one command line contains several launches, the most severe classification wins.
RANK = {"QUARANTINED": 6, "DONOR_ONLY": 5, "UNACCOUNTED": 4, "TRANSITIONAL_LEGACY": 3, "SHARED_DEPENDENCY": 2, "AUTHORIZED": 1}
TOKEN = re.compile(r'"([^"]*)"|\'([^\']*)\'|(\S+)')
INTERPRETERS = {"python.exe", "pythonw.exe", "python", "pythonw", "py.exe", "py", "python3.exe", "python3"}
SHELLS = {"powershell.exe", "powershell", "pwsh.exe", "pwsh"}
SECRET_ARG = re.compile(r"(?i)((?:--?|/)?(?:api[-_]?key|access[-_]?token|refresh[-_]?token|token|secret|password|passwd|pwd|"
                        r"client[-_]?secret|authorization)\s*[=: ]\s*)(?:bearer\s+|basic\s+)?(\"[^\"]*\"|'[^']*'|\S+)")
BEARER = re.compile(r"(?i)\b(bearer|basic)\s+[A-Za-z0-9._~+/=-]{6,}")
ENCODED = re.compile(r"(?i)(-(?:encodedcommand|enc|ec|e)\s+)([A-Za-z0-9+/=]{8,})")


def redact(text: str) -> str:
    """Remove secret-looking values before anything is stored or printed. Encoded PowerShell payloads are replaced
    by their decoded, redacted text so nothing recoverable remains."""
    import base64
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="replace")
    elif not isinstance(text, str):
        text = "" if text is None else str(text)

    def enc(m):
        try:
            decoded = base64.b64decode(m.group(2)).decode("utf-16-le", errors="replace")
        except (ValueError, TypeError):
            decoded = "<undecodable>"
        return m.group(1) + "<encoded; decoded: " + _redact_plain(decoded).replace(">", ")") + ">"
    return _redact_plain(ENCODED.sub(enc, text or ""))


def _redact_plain(text: str) -> str:
    text = BEARER.sub(lambda m: m.group(1) + " <redacted>", text)
    return SECRET_ARG.sub(lambda m: m.group(1) + "<redacted>", text)


PATH_WITH_SPACES = re.compile(r"^\s*([A-Za-z]:[\\/][^\"]*?\.(?:exe|bat|cmd|ps1|py|pyw|lnk))(?=\s|$)", re.I)
WD = re.compile(r"\s*\[wd=([^\]]*)\]\s*$")
# Unquoted command separators for cmd.exe and PowerShell: & && | || ; and newlines. '>&' / '<&' are redirections.
# Only '>&' and '<&' (e.g. 2>&1) are redirections; any other '&' (including '1&' and '&1') separates commands.
SEPARATORS = re.compile(r"&&|(?<![<>])&|\|\||\||;|\r?\n")


def _split_commands(text: str) -> list[str]:
    out, buf, q = [], [], None
    i = 0
    while i < len(text):
        c = text[i]
        if c in "\"'":
            q = None if q == c else (c if q is None else q)
        if q is None:
            m = SEPARATORS.match(text, i)
            if m and m.group(0):
                out.append("".join(buf)); buf = []; i = m.end(); continue
        buf.append(c); i += 1
    out.append("".join(buf))
    return [x.strip() for x in out if x.strip()]


def _tokens(text: str) -> list[str]:
    text = text.replace('""', '"')  # cmd.exe /c ""a" "b"" quoting
    head = []
    m = PATH_WITH_SPACES.match(text)
    if m and not text.lstrip().startswith('"'):
        head, text = [m.group(1)], text[m.end():]  # unquoted executable path that contains spaces
    return head + [a or b or c for a, b, c in TOKEN.findall(text) if (a or b or c)]


def _decode_encoded_command(tokens: list[str]) -> str | None:
    for i, tk in enumerate(tokens):
        if tk.lower() in ("-encodedcommand", "-enc", "-e", "-ec") and i + 1 < len(tokens):
            import base64
            try:
                return base64.b64decode(tokens[i + 1]).decode("utf-16-le", errors="replace")
            except (ValueError, TypeError):
                return "<undecodable -EncodedCommand>"
    return None


def _absolute(path: str, wd: str) -> str:
    p = path.strip()
    if p.startswith("\\\\?\\"):
        p = p[4:]
    if wd and not re.match(r"^([A-Za-z]:|[\\/])", p) and not p.startswith(("module:", "inline-code", "encoded:")):
        p = wd.rstrip("\\/") + "/" + p
    return p


def launch_targets(text: str, depth: int = 0) -> list[tuple[str, str]]:
    """Every (executable, target) launched by a command line. The target is what actually runs: the script for an
    interpreter, the -File script or -Command program for PowerShell, each chained command for cmd /c, the module for
    python -m, else the executable. Relative targets are resolved against a trailing [wd=...]."""
    text = text or ""
    wdm = WD.search(text)
    wd = wdm.group(1).strip() if wdm else ""
    text = WD.sub("", text)
    results = []
    for part in _split_commands(text) or [""]:
        for exe, target in _launch_one(part, depth):
            results.append((_absolute(exe, wd), _absolute(target, wd)))
    return results or [("", "")]


def _launch_one(text: str, depth: int) -> list[tuple[str, str]]:
    toks = _tokens(text)
    if not toks:
        return []
    if toks[0] == "&" and len(toks) > 1:  # PowerShell call operator
        toks = toks[1:]
    exe = toks[0]
    base = exe.replace("\\", "/").rsplit("/", 1)[-1].lower()
    rest = toks[1:]
    if depth < 4 and base in ("cmd.exe", "cmd"):
        for i, tk in enumerate(rest):
            if tk.lower() in ("/c", "/k"):
                inner = (text.split(tk, 1)[1] if tk in text else " ".join(rest[i + 1:])).strip()
                if inner.startswith('""') and inner.endswith('"'):
                    inner = inner[1:-1]  # cmd /c ""prog" args" -> "prog" args
                return launch_targets(inner, depth + 1)
        return [(exe, exe)]
    if base in SHELLS:
        decoded = _decode_encoded_command(rest)
        if decoded is not None:
            return launch_targets(decoded, depth + 1) if depth < 4 else [(exe, "encoded:" + decoded)]
        for i, tk in enumerate(rest):
            low = tk.lower()
            if low in ("-file", "-f") and i + 1 < len(rest):
                return [(exe, rest[i + 1])]
            if low in ("-command", "-c") and i + 1 < len(rest):
                cmd = text[text.lower().index(low) + len(low):] if low in text.lower() else " ".join(rest[i + 1:])
                cmd = cmd.strip()
                if len(cmd) >= 2 and cmd[0] == cmd[-1] and cmd[0] in "\"'":
                    cmd = cmd[1:-1]
                return launch_targets(cmd, depth + 1) if depth < 4 else [(exe, cmd)]
        positional = [t for t in rest if not t.startswith("-")]
        return [(exe, positional[0])] if positional else [(exe, exe)]
    if base in INTERPRETERS or base.startswith("python"):
        skip_next = False
        for i, tk in enumerate(rest):
            if skip_next:
                skip_next = False
                continue
            if tk == "-m" and i + 1 < len(rest):
                return [(exe, "module:" + rest[i + 1])]
            if tk == "-c":
                return [(exe, "inline-code")]
            if tk.startswith("-"):
                skip_next = tk in ("-W", "-X")
                continue
            return [(exe, tk)]
        return [(exe, exe)]
    return [(exe, exe)]


def launch_target(text: str) -> tuple[str, str]:
    """First launched (executable, target); kept for callers that need one."""
    return launch_targets(text)[0]


def _root_containing(path: str, roots: list[dict]) -> dict | None:
    p = norm(path)
    best = None
    for r in roots:
        rp = norm(r["path"])
        if p == rp or p.startswith(rp + "/"):
            if best is None or len(rp) > len(norm(best["path"])):
                best = r
    return best


def _classify_one(exe: str, target: str, text: str, manifest: dict) -> tuple[str, str]:
    roots = manifest["roots"]
    t_target = norm(target)
    target_root = _root_containing(target, roots) or (_root_containing(exe, roots) if target.startswith(("module:", "inline-code")) else None)
    # Any donor/quarantined root referenced ANYWHERE in the command (state dir, model, argument) that does not contain
    # the target is a contamination signal of its own: an authorized or legacy prefix can never launder it.
    other = _root_for(text, [r for r in roots if r is not target_root and r["classification"] != "ACTIVE_AUTHORITATIVE"])
    for legacy in manifest["transitional_legacy"]:
        if t_target == norm(legacy["match"]):
            if other is not None and not (target_root and norm(other["path"]).startswith(norm(target_root["path"]))):
                return CLS[other["classification"]], other["id"] + " (referenced by a transitional command)"
            return "TRANSITIONAL_LEGACY", legacy["id"]
    if target_root is not None:
        cls = CLS[target_root["classification"]]
        if cls == "AUTHORIZED":
            if other is not None:
                return CLS[other["classification"]], other["id"] + " (referenced by an authorized entrypoint)"
            allowed = {norm(target_root["path"] + "/" + e) for e in target_root.get("entrypoints", [])}
            if t_target not in allowed:
                return "UNACCOUNTED", f"{target_root['id']}: inside authoritative root but not an authorized entrypoint"
        return cls, target_root["id"]
    if other is not None:
        return CLS[other["classification"]], other["id"] + " (referenced as an argument)"
    for dep in manifest["shared_dependencies"]:
        dp = norm(dep["path"])
        if (t_target == dp or t_target.startswith(dp + "/")) and URI_HINT.search(text) is None:
            return "SHARED_DEPENDENCY", dep["id"]
    return "UNACCOUNTED", "no manifest entry"


def classify(text: str, manifest: dict) -> tuple[str, str]:
    """Classify every launch in the command line; the most severe result wins (chained commands cannot hide)."""
    results = [_classify_one(exe, target, text, manifest) for exe, target in launch_targets(text)]
    return max(results, key=lambda r: RANK[r[0]])


SHELL_EXES = {"bash.exe", "bash", "sh.exe", "sh", "cmd.exe", "cmd", "powershell.exe", "powershell", "pwsh.exe", "pwsh"}


def _basename(path: str) -> str:
    return path.replace(chr(92), "/").rsplit("/", 1)[-1].lower()


TRUSTED_SHELL_PATHS = ("c:/program files/git/bin/bash.exe", "c:/program files/git/usr/bin/bash.exe",
                       "c:/windows/system32/cmd.exe", "c:/windows/system32/windowspowershell/v1.0/powershell.exe",
                       "c:/program files/powershell/7/pwsh.exe")


def _is_agent_shell(cmd: str, roots: list | None = None) -> bool:
    """An interactive agent shell: the executable is a genuine system shell at a trusted absolute path, it carries
    the agent marker, and nothing it launches lives in any manifest root. Anything else is evaluated normally."""
    toks = _tokens(cmd)
    if not toks or not AGENT_SHELL.search(cmd):
        return False
    exe = norm(toks[0])
    if exe not in TRUSTED_SHELL_PATHS:
        return False
    if roots:
        for ex, tg in launch_targets(cmd):
            for path in (ex, tg):
                if path and not path.startswith(("module:", "inline-code", "encoded:")) and _root_containing(path, roots):
                    return False
    return True


def _is_python_like(cmd: str) -> bool:
    exe, target = launch_target(cmd)
    base = exe.replace("\\", "/").rsplit("/", 1)[-1].lower()
    return base in INTERPRETERS or base.startswith("python") or "uvicorn" in cmd.lower()


def _autostart_relevant(cmd: str) -> bool:
    """A URI-looking command, an interpreter-launched program, or an opaque encoded PowerShell command."""
    if URI_HINT.search(cmd) or RUNTIME_HINT.search(cmd):
        return True
    exe, target = launch_target(cmd)
    return _is_python_like(cmd) or target.startswith("encoded:") or "-encodedcommand" in cmd.lower()


def evaluate(snapshot: dict, manifest: dict, strict: bool = False) -> dict:
    findings = []

    def add(kind, ident, text, active, extra=None):
        cls, ref = classify(text, manifest)
        f = {"kind": kind, "id": ident, "detail": redact(text)[:400], "active_or_autostart": active,
             "classification": cls, "manifest_ref": ref}
        f.update(extra or {})
        findings.append(f)

    roots = manifest["roots"]

    def refs_root(text):
        """True when the command launches from, or mentions, ANY manifest root (any classification)."""
        if not text:
            return False
        return _root_for(text, roots) is not None or any(_root_containing(tg, roots) or _root_containing(ex, roots)
                                                          for ex, tg in launch_targets(text))

    for t in snapshot.get("scheduled_tasks", []):
        if _autostart_relevant(t["action"]) or URI_HINT.search(t["name"]) or refs_root(t["action"]):
            add("scheduled_task", t["name"], t["action"], t.get("enabled", True))
    for r in snapshot.get("run_keys", []):
        if _autostart_relevant(r["value"]) or refs_root(r["value"]):
            add("run_key", r["name"], r["value"], True)
    for s in snapshot.get("shortcuts", []):
        if URI_HINT.search(s["target"]) or URI_HINT.search(s["path"]) or refs_root(s["target"]) or                 (s.get("startup") and _autostart_relevant(s["target"])):
            add("startup_shortcut" if s.get("startup") else "shortcut", s["path"], s["target"], bool(s.get("startup")))
    uri_ports = set(range(manifest["ports"]["uri_range"][0], manifest["ports"]["uri_range"][1] + 1))
    model_ports = set(manifest["ports"].get("model_ports", []))
    def listener_text(lst):
        return " ".join(x for x in (lst.get("cmdline") or "", lst.get("image") or "") if x)

    def listener_relevant(lst):
        text = listener_text(lst)
        return (lst["port"] in uri_ports or lst["port"] in model_ports or _is_python_like(text) or refs_root(text))

    listener_pids = {lst.get("pid") for lst in snapshot.get("listeners", []) if listener_relevant(lst)}

    def launched_from_nonactive_root(cmd, image):
        outer = _tokens(WD.sub("", cmd or ""))[:1]  # the outer executable itself (e.g. a cmd.exe or shell copy)
        for ex, tg in launch_targets(cmd) + [(image, image)] + [(o, o) for o in outer]:
            for path in (tg, ex):
                r = _root_containing(path, roots) if path and not path.startswith(("module:", "inline-code", "encoded:")) else None
                if r is not None and r["classification"] != "ACTIVE_AUTHORITATIVE":
                    return True
        return False
    for p in snapshot.get("processes", []):
        cmd = p["cmdline"]
        if _is_agent_shell(cmd, roots):
            continue
        if RUNTIME_HINT.search(cmd) or p.get("pid") in listener_pids:
            add("process", f"pid {p['pid']}", cmd, True)
        elif launched_from_nonactive_root(cmd, p.get("image", "")):
            # No name-based exemption: anything executing from a donor or quarantined root counts, including
            # development test runs (Codex rounds 6-7 showed every name/argument exemption can be abused).
            add("process", f"pid {p['pid']}", cmd, True)
    for lst in snapshot.get("listeners", []):
        text = lst.get("cmdline") or lst.get("image") or ""
        # URI and model ports always; any other port when an interpreter/uvicorn owns it or it runs from a manifest root.
        if listener_relevant(lst):
            add("listener", f"{lst['address']}:{lst['port']}", text or "<unknown owner>", True,
                {"address": lst["address"], "port": lst["port"]})
    prefs = snapshot.get("ui_preferences")
    if prefs and prefs.get("serverBaseUrl"):
        url = prefs["serverBaseUrl"]
        m = re.match(r"^\w+://\[?([^\]/]+?)\]?:(\d+)", url)
        host, port = (m.group(1), int(m.group(2))) if m else ("", -1)
        ok_addr = {host, "0.0.0.0", "::"} | ({"127.0.0.1"} if host == "localhost" else set())
        owner = next((f for f in findings if f["kind"] == "listener" and f.get("port") == port and f.get("address") in ok_addr), None)
        cls = owner["classification"] if owner else "UNACCOUNTED"
        findings.append({"kind": "ui_server_binding", "id": "uri_ui shared_preferences serverBaseUrl", "detail": url,
                         "active_or_autostart": True, "classification": cls,
                         "manifest_ref": (owner or {}).get("manifest_ref", "no listener serving that address and port")})
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


def live_snapshot(roots: list | None = None) -> dict:
    if os.name != "nt":
        raise SystemExit("live probe is Windows-only; use --snapshot")
    child = subprocess.Popen(["powershell", "-NoProfile", "-NonInteractive", "-Command", PS_PROBE], stdout=subprocess.PIPE,
                             stderr=subprocess.PIPE, stdin=subprocess.DEVNULL)
    out, err = child.communicate(timeout=240)
    r = subprocess.CompletedProcess(child.args, child.returncode, out, err)
    self_pids = {os.getpid(), child.pid}
    if r.returncode != 0 or not r.stdout.strip():
        raise SystemExit(f"probe failed: {r.stderr.decode(errors='replace')[:400]}")
    snap = json.loads(r.stdout.decode("utf-8", errors="replace"))
    for k in ("scheduled_tasks", "run_keys", "shortcuts", "processes", "listeners"):
        v = snap.get(k)
        snap[k] = [] if v is None else (v if isinstance(v, list) else [v])
    # The probe's own PowerShell process carries this source text, which mentions URI paths; drop it.
    # Privacy: keep only command lines that look like URI runtimes; never persist unrelated process command lines.
    listen_pids = {l.get("pid") for l in (snap.get("listeners") or []) if isinstance(l, dict)}
    snap["processes"] = [p for p in snap.get("processes") or [] if p.get("pid") not in self_pids
                         and not _is_agent_shell(p["cmdline"], roots)
                         and (RUNTIME_HINT.search(p["cmdline"]) or (p.get("pid") in listen_pids and _is_python_like(p["cmdline"]))
                              or (roots and any(_root_containing(x, roots) for ex, tg in launch_targets(p["cmdline"])
                                                for x in (ex, tg, p.get("image", "")) if x)))]
    for lst in snap.get("listeners") or []:
        c = lst.get("cmdline", "")
        if not (RUNTIME_HINT.search(c) or URI_HINT.search(c) or _is_python_like(c)):
            lst["cmdline"] = ""  # keep only the image path for non-URI listeners
    # Redact secret-looking argument values everywhere before the snapshot can be saved or printed.
    for p in snap["processes"]:
        p["cmdline"] = redact(p["cmdline"])
    for lst in snap.get("listeners") or []:
        lst["cmdline"] = redact(lst.get("cmdline", ""))
    for t in snap.get("scheduled_tasks") or []:
        t["action"] = redact(t["action"])
    for r in snap.get("run_keys") or []:
        r["value"] = redact(r["value"])
    for s in snap.get("shortcuts") or []:
        s["target"] = redact(s["target"])
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
    snap = json.loads(Path(a.snapshot).read_text(encoding="utf-8")) if a.snapshot else live_snapshot(manifest["roots"])
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
