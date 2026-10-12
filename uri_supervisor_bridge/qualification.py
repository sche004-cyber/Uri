"""Phase 2D: persisted, evidence-backed executor qualification for the client-side composition (schema v2).

A qualification record says: THIS client (client_id + its Ed25519 public key) qualified THIS provider, run as THIS
launch chain (executable file + every pinned file the launcher executes, each with SHA-256) at THIS reported version,
for THESE models, at THIS level, on the strength of THIS evidence file, until THIS expiry. It lives in the client's own
state root (`<client_root>/control/supervisor/qualification/<provider>.json`, evidence under `.../qualification/evidence/`)
and is re-validated on every load:

  * signature: Ed25519 by the client's own key over the canonical record (independent review round 1, D1/D3: an
    unkeyed digest could be recomputed after editing `models`; an unbound record could be copied to another client);
  * binding: `client_id` and `client_public_key` must equal the composing client's manifest values;
  * expiry: `expires_at` (epoch seconds) must lie in the future;
  * evidence: the client-owned evidence file must still hash to `evidence_sha256` AND its content must agree with the
    record (provider, success, version, executable hash) (review D2: the evidence was never re-read);
  * launch chain: the executable and every `pinned_files` entry must still hash as recorded, and every `resolve_pins`
    name (for example `node` for the npm shim) must still resolve, on the executor PATH, to the pinned file (review D4:
    only the `.cmd` shim was pinned, not the program it launches);
  * `--version` must still report the recorded version; `FIXTURE_ONLY` only when the composition allows fixtures.

Anything that fails leaves the provider where the frozen Phase 1 registry leaves it by default: `NATIVE_UNQUALIFIED`,
not usable. Authentication is never persisted: it is probed live on every registry decision (`codex login status`,
`claude auth status`) under the executor's environment allow-list, never by reading a credential file or logging in.

Trust limit (stated, not hidden): the signing key is the client key protected by current-user DPAPI (Phase 1 C1:
same-user logical isolation only). A process running as the same Windows user can sign. The record defends against
hand edits, copies between clients, stale evidence and launcher/payload replacement, not against same-user malware.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import time
import uuid
from dataclasses import dataclass, replace
from pathlib import Path

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

from uri_core.client_runtime.harness import HarnessRegistry, harness_env, probe_version, resolve_command
from uri_supervisor.executors import BUILTIN_SPECS, GENERIC_NDJSON, ExecutorSpec

from .bridge import ExecutorBinding, _file_sha256, _same_file

SCHEMA = "uri.phase2d.qualification.v2"
LEVELS = ("NATIVE_QUALIFIED", "FIXTURE_ONLY")
DEFAULT_TTL_S = 30 * 24 * 3600
MAX_TTL_S = 90 * 24 * 3600
_PROVIDER = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}$")
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_UUID = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")
_EVIDENCE_NAME = re.compile(r"^[a-z][a-z0-9_]{0,63}-[0-9a-f]{16}\.json$")
_RESOLVE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")
REQUIRED = ("schema", "provider", "level", "spec_id", "client_id", "client_public_key", "executable", "executable_args",
            "executable_sha256", "pinned_files", "resolve_pins", "version", "models", "evidence_file", "evidence_sha256",
            "qualified_at", "expires_at", "qualified_by", "record_sha256", "signature")
OPTIONAL = ("notes",)
# Live, read-only authentication status commands.
AUTH_STATUS_ARGV = {"codex_cli": ("login", "status"), "claude_code": ("auth", "status")}
AUTH_VARS = {"claude_code": ("CLAUDE_CODE_OAUTH_TOKEN",), "codex_cli": ("CODEX_API_KEY", "CODEX_HOME")}


class QualificationError(ValueError):
    def __init__(self, code, detail=None):
        super().__init__(code if detail is None else f"{code}: {detail}")
        self.code, self.detail = code, detail


@dataclass(frozen=True)
class RecordTrust:
    """The composing client's identity: records must be bound to it and signed by its key."""
    client_id: str
    public_key_hex: str

    @staticmethod
    def from_manifest(data: dict) -> "RecordTrust":
        return RecordTrust(data["client_id"], data["client_public_key"])

    @staticmethod
    def from_private_key(client_id, key: Ed25519PrivateKey) -> "RecordTrust":
        return RecordTrust(client_id, _public_hex(key))


def _public_hex(key: Ed25519PrivateKey) -> str:
    return key.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def qualification_dir(client_root) -> Path:
    return Path(client_root).resolve() / "control" / "supervisor" / "qualification"


def evidence_dir(client_root) -> Path:
    return qualification_dir(client_root) / "evidence"


def _canonical(record: dict) -> bytes:
    return json.dumps({k: v for k, v in record.items() if k not in ("record_sha256", "signature")}, sort_keys=True,
                      separators=(",", ":"), ensure_ascii=True).encode("utf-8")


def record_digest(record: dict) -> str:
    return hashlib.sha256(_canonical(record)).hexdigest()


# ---- launch chain discovery --------------------------------------------------------------------------------------

def executor_path(environ=None) -> str:
    """The PATH the supervisor forwards to executors (same allow-list as `ExecutorSpec.build_env`)."""
    env = environ if environ is not None else os.environ
    return env.get("PATH", "")


def npm_codex_launch_chain(shim, environ=None):
    """For the npm `codex.cmd` launcher: every file the launch executes or loads by name, and the `node` resolution.
    Returns (pinned_files {abs path: sha256}, resolve_pins {name: abs path}). Raises QualificationError if the chain
    cannot be established (unknown layout = no native qualification)."""
    shim = Path(shim).resolve()
    dp0 = shim.parent
    pinned, resolve = {}, {}
    local_node = dp0 / "node.exe"
    if local_node.is_file():
        node = local_node.resolve()
    else:
        found = shutil.which("node", path=executor_path(environ))
        if not found:
            raise QualificationError("LAUNCH_CHAIN_NODE_UNRESOLVED")
        node = Path(found).resolve()
        resolve["node"] = str(node)
    pkg = dp0 / "node_modules" / "@openai" / "codex"
    entry = pkg / "bin" / "codex.js"
    if not entry.is_file():
        raise QualificationError("LAUNCH_CHAIN_ENTRY_MISSING")
    platform_pkg = pkg / "node_modules" / "@openai" / "codex-win32-x64"
    vendor = platform_pkg / "vendor" / "x86_64-pc-windows-msvc"
    if not (vendor / "bin" / "codex.exe").is_file():
        raise QualificationError("LAUNCH_CHAIN_VENDOR_MISSING")
    files = [node, entry, pkg / "package.json", platform_pkg / "package.json"]
    files += sorted(p for p in vendor.rglob("*") if p.is_file() and p.suffix.lower() in (".exe", ".dll", ".js", ".cmd", ".ps1"))
    for f in files:
        pinned[str(Path(f).resolve())] = _file_sha256(f)
    return pinned, resolve


# EXE-1 (Phase 2 operational qualification, 2026-10-08). The npm `codex.cmd` shim only runs `node codex.js`, and
# codex.js (0.158.0) only locates and spawns the platform package's NATIVE binary (`vendor/<triple>/bin/codex.exe`),
# adding two package-manager marker variables. The worker's sanitized PATH has no `node`, so the shim cannot start
# there. Qualifying the native binary itself needs NO interpreter and NO PATH change: the launch chain is that binary
# plus every executable/library file of its own vendor directory (pinned by hash), and nothing is resolved by name.
CODEX_NATIVE_TRIPLE = "x86_64-pc-windows-msvc"
CODEX_NATIVE_LAYOUT = {"layoutVersion": 1, "entrypoint": "bin/codex.exe"}


def npm_codex_native_executable(shim) -> Path:
    """The native binary the npm launcher `shim` (codex.cmd) would start. Raises QualificationError when the npm
    layout is not the known one (unknown layout = no native qualification)."""
    shim = Path(shim).resolve()
    vendor = (shim.parent / "node_modules" / "@openai" / "codex" / "node_modules" / "@openai" / "codex-win32-x64"
              / "vendor" / CODEX_NATIVE_TRIPLE)
    exe = vendor / "bin" / "codex.exe"
    if not exe.is_file():
        raise QualificationError("LAUNCH_CHAIN_VENDOR_MISSING")
    return exe.resolve()


def npm_claude_native_executable(shim) -> Path:
    """The native binary the npm launcher `shim` (claude.cmd) starts directly (`bin/claude.exe`, no interpreter)."""
    exe = Path(shim).resolve().parent / "node_modules" / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
    if not exe.is_file():
        raise QualificationError("LAUNCH_CHAIN_VENDOR_MISSING")
    return exe.resolve()


def native_executable(provider, found=None) -> Path | None:
    """EXE-1: the native binary to qualify for `provider`. `found` defaults to the PATH lookup of the CLI name. An npm
    launcher (`.cmd`) is replaced by the native binary it starts; anything else is returned unchanged. None when the CLI
    is not installed."""
    found = found or shutil.which({"codex_cli": "codex", "claude_code": "claude"}.get(provider, provider))
    if not found:
        return None
    if Path(found).suffix.lower() == ".cmd":
        if provider == "codex_cli":
            return npm_codex_native_executable(found)
        if provider == "claude_code":
            return npm_claude_native_executable(found)
    return Path(found).resolve()


def codex_native_launch_chain(executable):
    """For the npm-vendored native `codex.exe`: (pinned_files, {}) covering the binary, its layout descriptor and every
    .exe/.dll of its vendor directory (command runner, sandbox setup, code-mode host, rg). None when `executable` is
    not inside a vendored layout (a standalone binary is pinned by its own hash only). Raises QualificationError when
    the layout descriptor exists but is not the known one."""
    exe = Path(executable).resolve()
    vendor = exe.parent.parent
    meta = vendor / "codex-package.json"
    vendored_looking = exe.name.lower() == "codex.exe" or any(part.lower() == "vendor" for part in exe.parts)
    if not meta.is_file() or exe.name.lower() != "codex.exe" or exe.parent.name.lower() != "bin":
        if vendored_looking:
            # Review round 1, OQ-R1-1: a `codex.exe` (or anything under a `vendor` directory) whose layout descriptor is
            # missing or misplaced is a damaged or unknown vendored layout, not a standalone binary: refused.
            raise QualificationError("LAUNCH_CHAIN_LAYOUT_UNKNOWN", "codex-package.json missing")
        return None
    try:
        layout = json.loads(meta.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        raise QualificationError("LAUNCH_CHAIN_LAYOUT_UNKNOWN", "codex-package.json") from None
    if (not isinstance(layout, dict) or any(layout.get(k) != v for k, v in CODEX_NATIVE_LAYOUT.items())
            or layout.get("target") != vendor.name):
        raise QualificationError("LAUNCH_CHAIN_LAYOUT_UNKNOWN", "codex-package.json")
    files = [meta, *sorted(p for p in vendor.rglob("*") if p.is_file() and p.suffix.lower() in (".exe", ".dll"))]
    return {str(Path(f).resolve()): _file_sha256(f) for f in files}, {}


def launch_chain_for(spec_id, executable, environ=None):
    if spec_id == "codex_cli" and Path(executable).suffix.lower() == ".cmd":
        return npm_codex_launch_chain(executable, environ)
    if spec_id == "codex_cli" and Path(executable).suffix.lower() == ".exe":
        chain = codex_native_launch_chain(executable)
        if chain is not None:
            return chain
    if Path(executable).suffix.lower() in (".cmd", ".bat", ".ps1"):
        raise QualificationError("LAUNCH_CHAIN_UNKNOWN_LAUNCHER", Path(executable).name)
    return {}, {}


# ---- record construction ----------------------------------------------------------------------------------------

def build_record(*, client_root, client_id, signer: Ed25519PrivateKey, provider, level, spec_id, executable,
                 executable_args, version, models, evidence_path, qualified_by, notes=None, pinned_files=None,
                 resolve_pins=None, ttl_s=DEFAULT_TTL_S, now=None) -> dict:
    """Build and sign a record from observed facts. The caller is the trusted qualification run of THIS client. The
    evidence file is copied into the client's own qualification store (content-addressed) and hashed there."""
    if not isinstance(provider, str) or not _PROVIDER.fullmatch(provider):
        raise QualificationError("PROVIDER_ID_INVALID")
    if level not in LEVELS:
        raise QualificationError("LEVEL_INVALID", str(level))
    if spec_id not in BUILTIN_SPECS:
        raise QualificationError("SPEC_UNKNOWN", str(spec_id))
    if not isinstance(client_id, str) or not _UUID.fullmatch(client_id):
        raise QualificationError("CLIENT_ID_INVALID")
    exe = Path(executable)
    if not exe.is_file():
        raise QualificationError("EXECUTABLE_MISSING")
    args = [str(a) for a in (executable_args or [])]
    ev = Path(evidence_path)
    if not ev.is_file():
        raise QualificationError("EVIDENCE_MISSING")
    if not isinstance(models, (list, tuple)) or not models:
        raise QualificationError("MODELS_REQUIRED")
    for m in models:
        if m is not None and (not isinstance(m, str) or not _MODEL.fullmatch(m)):
            raise QualificationError("MODEL_ID_INVALID", str(m))
    if version is not None and not isinstance(version, str):
        raise QualificationError("VERSION_INVALID")
    if not isinstance(ttl_s, int) or not 60 <= ttl_s <= MAX_TTL_S:
        raise QualificationError("TTL_INVALID")
    if pinned_files is None and resolve_pins is None:
        pinned_files, resolve_pins = launch_chain_for(spec_id, exe)
    data = ev.read_bytes()
    ev_sha = hashlib.sha256(data).hexdigest()
    ev_name = f"{provider}-{ev_sha[:16]}.json"
    d = evidence_dir(client_root)
    d.mkdir(parents=True, exist_ok=True)
    (d / ev_name).write_bytes(data)
    now = int(time.time() if now is None else now)
    record = {"schema": SCHEMA, "provider": provider, "level": level, "spec_id": spec_id, "client_id": client_id,
              "client_public_key": _public_hex(signer), "executable": str(exe.resolve()), "executable_args": args,
              "executable_sha256": _file_sha256(exe), "pinned_files": dict(sorted((pinned_files or {}).items())),
              "resolve_pins": dict(sorted((resolve_pins or {}).items())), "version": version, "models": list(models),
              "evidence_file": ev_name, "evidence_sha256": ev_sha, "qualified_at": now, "expires_at": now + ttl_s,
              "qualified_by": str(qualified_by), "notes": notes or ""}
    record["record_sha256"] = record_digest(record)
    record["signature"] = signer.sign(_canonical(record)).hex()
    return record


def write_record(client_root, record: dict) -> Path:
    """Atomic write of one provider's record (replaces an older record for the same provider)."""
    validate_shape(record)
    d = qualification_dir(client_root)
    d.mkdir(parents=True, exist_ok=True)
    path = d / (record["provider"] + ".json")
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with open(tmp, "x", encoding="utf-8") as f:
        json.dump(record, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)
    return path


def validate_shape(record) -> dict:
    if not isinstance(record, dict) or set(record) - set(REQUIRED) - set(OPTIONAL) or any(k not in record for k in REQUIRED):
        raise QualificationError("RECORD_SCHEMA")
    if record["schema"] != SCHEMA:
        raise QualificationError("RECORD_SCHEMA", "schema")
    if not isinstance(record["provider"], str) or not _PROVIDER.fullmatch(record["provider"]):
        raise QualificationError("RECORD_SCHEMA", "provider")
    if record["level"] not in LEVELS:
        raise QualificationError("RECORD_SCHEMA", "level")
    if record["spec_id"] not in BUILTIN_SPECS:
        raise QualificationError("RECORD_SCHEMA", "spec_id")
    if not isinstance(record["client_id"], str) or not _UUID.fullmatch(record["client_id"]):
        raise QualificationError("RECORD_SCHEMA", "client_id")
    if not isinstance(record["client_public_key"], str) or not re.fullmatch(r"[0-9a-f]{64}", record["client_public_key"]):
        raise QualificationError("RECORD_SCHEMA", "client_public_key")
    if not isinstance(record["executable"], str) or not record["executable"]:
        raise QualificationError("RECORD_SCHEMA", "executable")
    if not isinstance(record["executable_args"], list) or any(not isinstance(a, str) for a in record["executable_args"]):
        raise QualificationError("RECORD_SCHEMA", "executable_args")
    pf = record["pinned_files"]
    if not isinstance(pf, dict) or any(not isinstance(k, str) or not isinstance(v, str) or not _HEX64.fullmatch(v) for k, v in pf.items()):
        raise QualificationError("RECORD_SCHEMA", "pinned_files")
    rp = record["resolve_pins"]
    if not isinstance(rp, dict) or any(not isinstance(k, str) or not _RESOLVE_NAME.fullmatch(k) or not isinstance(v, str) or v not in pf
                                       for k, v in rp.items()):
        raise QualificationError("RECORD_SCHEMA", "resolve_pins")
    for key in ("executable_sha256", "evidence_sha256", "record_sha256"):
        if not isinstance(record[key], str) or not _HEX64.fullmatch(record[key]):
            raise QualificationError("RECORD_SCHEMA", key)
    if not isinstance(record["evidence_file"], str) or not _EVIDENCE_NAME.fullmatch(record["evidence_file"]):
        raise QualificationError("RECORD_SCHEMA", "evidence_file")
    for key in ("qualified_at", "expires_at"):
        if type(record[key]) is not int:
            raise QualificationError("RECORD_SCHEMA", key)
    if not 0 < record["expires_at"] - record["qualified_at"] <= MAX_TTL_S:
        raise QualificationError("RECORD_SCHEMA", "ttl")
    if record["version"] is not None and not isinstance(record["version"], str):
        raise QualificationError("RECORD_SCHEMA", "version")
    models = record["models"]
    if not isinstance(models, list) or not models or any(m is not None and (not isinstance(m, str) or not _MODEL.fullmatch(m)) for m in models):
        raise QualificationError("RECORD_SCHEMA", "models")
    if not isinstance(record["signature"], str) or not re.fullmatch(r"[0-9a-f]{128}", record["signature"]):
        raise QualificationError("RECORD_SCHEMA", "signature")
    if record_digest(record) != record["record_sha256"]:
        raise QualificationError("RECORD_DIGEST_MISMATCH")
    return record


def verify_trust(record, trust: RecordTrust):
    """Binding + signature. The digest alone is recomputable by anyone; the signature is not (review D1/D3)."""
    if trust is None:
        raise QualificationError("NO_TRUST_ANCHOR")
    if record["client_id"] != trust.client_id or record["client_public_key"] != trust.public_key_hex:
        raise QualificationError("RECORD_CLIENT_MISMATCH")
    try:
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(trust.public_key_hex)).verify(bytes.fromhex(record["signature"]), _canonical(record))
    except (InvalidSignature, ValueError):
        raise QualificationError("RECORD_SIGNATURE_INVALID") from None


def load_records(client_root) -> list:
    """Every record file, parsed or marked unreadable. Never raises for one bad file."""
    out = []
    d = qualification_dir(client_root)
    if not d.is_dir():
        return out
    for p in sorted(d.glob("*.json")):
        try:
            rec = json.loads(p.read_text(encoding="utf-8"))
            validate_shape(rec)
            if rec["provider"] != p.stem:
                raise QualificationError("RECORD_PROVIDER_FILENAME_MISMATCH")
            out.append({"path": str(p), "record": rec, "error": None})
        except (OSError, ValueError) as exc:
            code = exc.code if isinstance(exc, QualificationError) else "RECORD_UNREADABLE"
            out.append({"path": str(p), "record": None, "error": code})
    return out


def client_cli_homes(client_root, create=True) -> dict:
    """ISO-1 (Phase 2 closure, 2026-10-08): the CLI homes of the CLIENT PROFILE, to be set in the worker's environment.

    The worker's sanitized environment points USERPROFILE/HOME at `<client_root>/home`, which isolates Claude Code
    (it resolves its config through the process home). Codex 0.158.0 does NOT: without CODEX_HOME it resolves the
    Windows user profile itself and reads the OWNER's global login (observed: `codex login status` -> "Logged in using
    ChatGPT" with only the profile variables overridden; "Not logged in" once CODEX_HOME names the client profile).
    Pinning CODEX_HOME keeps every Codex probe and executor of this client on the client profile's own login, so a
    shared owner login can never qualify or run a client executor (C7 stop condition "shared client authentication")."""
    home = Path(client_root) / "home"
    pins = {"CODEX_HOME": str(home / ".codex")}
    if create:
        for value in pins.values():
            Path(value).mkdir(parents=True, exist_ok=True)
    return pins


def _same_dir(a, b) -> bool:
    try:
        ra, rb = os.path.realpath(a), os.path.realpath(b)
        return os.path.isdir(ra) and os.path.isdir(rb) and (os.path.normcase(ra) == os.path.normcase(rb) or os.path.samefile(ra, rb))
    except OSError:
        return False


CODEX_SANDBOX_MODES = ("unelevated", "elevated")


def codex_windows_sandbox_mode(codex_home):
    """The Windows sandbox backend the client profile's own Codex configuration selects (`[windows] sandbox`), or None.

    Found 2026-10-08 (EXE-1 work): with a FRESH Codex home and no sandbox mode, Codex 0.158.0 refuses every command
    of a `--sandbox workspace-write` run ("rejected: blocked by policy"), so a run can never write its result. With
    `unelevated` (restricted token, no system change) a workspace write succeeds and a write outside the workspace is
    denied; `elevated` needs a one-time administrator setup (sandbox accounts) that is the owner's decision. URI only
    reads the setting here; it is written once, explicitly, by `scripts/phase2close_acceptance.py provision`."""
    import tomllib
    cfg = Path(codex_home) / "config.toml"
    if not cfg.is_file():
        return None
    try:
        data = tomllib.loads(cfg.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    windows = data.get("windows")
    mode = windows.get("sandbox") if isinstance(windows, dict) else None
    return mode if mode in CODEX_SANDBOX_MODES else None


def check_codex_client_home(record, codex_home, environ=None):
    """Worker-only invariant for a Codex record (EXE-1 / ISO-1): the environment the executor will receive MUST name the
    client profile's own Codex home (never absent: absent = Codex silently falls back to the Windows user's global
    login), and that home must select a Windows sandbox backend (otherwise every command would be refused mid-run).
    Raises QualificationError; checked at composition and again before every execution (`still_valid`)."""
    if codex_home is None or "codex_cli" not in (record["provider"], record["spec_id"]):
        return
    env = os.environ if environ is None else environ
    value = env.get("CODEX_HOME")
    if not value or not _same_dir(value, codex_home):
        raise QualificationError("CODEX_HOME_NOT_CLIENT_PROFILE")
    if record["level"] == "NATIVE_QUALIFIED" and codex_windows_sandbox_mode(codex_home) is None:
        raise QualificationError("CODEX_WINDOWS_SANDBOX_NOT_CONFIGURED")
    if record["level"] == "NATIVE_QUALIFIED" and not _pins_recognised_codex_layout(record):
        raise QualificationError("LAUNCH_CHAIN_LAYOUT_NOT_PINNED")


def _pins_recognised_codex_layout(record) -> bool:
    """Worker rule (review round 1, OQ-R1-1): a NATIVE Codex record composes in the worker only when its executable is
    the `bin/codex.exe` of a vendored layout whose descriptor (`codex-package.json`) is among the record's pinned files.
    The pins themselves are re-hashed by `check_launch_chain`, so a later swap still invalidates the record."""
    exe = Path(record["executable"])
    meta = exe.parent.parent / "codex-package.json"
    if exe.name.lower() != "codex.exe" or exe.parent.name.lower() != "bin":
        return False
    return any(_same_file(p, meta) is True for p in record["pinned_files"])


def native_auth_probe(provider, executable, environ=None, timeout_s=30):
    """Live read-only authentication status. True / False / None (unknown). Never logs in, never reads a credential
    file: the CLI's own status command decides, under the same environment allow-list the executor gets."""
    argv = AUTH_STATUS_ARGV.get(provider)
    if argv is None:
        return None
    env = harness_env(AUTH_VARS.get(provider, ()), environ)
    try:
        p = subprocess.run([executable, *argv], capture_output=True, timeout=timeout_s, stdin=subprocess.DEVNULL, env=env)
    except (OSError, subprocess.TimeoutExpired):
        return None
    out = p.stdout.decode("utf-8", "replace")
    err = p.stderr.decode("utf-8", "replace")
    if provider == "claude_code":
        try:
            data = json.loads(out)
            return bool(data.get("loggedIn")) if isinstance(data, dict) else None
        except ValueError:
            return None
    # Codex 0.158.0 prints "Logged in using ChatGPT" on STDERR with exit 0 (Phase 2D defect D-D1: stdout alone read as
    # "not logged in"). "Not logged in" exits non-zero. Both streams are inspected; exit status decides first.
    text = (out + chr(10) + err).lower()
    if p.returncode != 0 or "not logged in" in text:
        return False
    return "logged in" in text


@dataclass(frozen=True)
class ClientComposition:
    registry: HarnessRegistry
    executors: dict
    report: list          # one row per record file: provider, status (QUALIFIED | INVALIDATED), reason, level, ...
    allow_fixture: bool

    def qualified(self):
        return sorted(r["provider"] for r in self.report if r["status"] == "QUALIFIED")


def _spec_for(record) -> ExecutorSpec:
    spec = BUILTIN_SPECS[record["spec_id"]]
    if record["level"] == "FIXTURE_ONLY":
        if record["spec_id"] != GENERIC_NDJSON.executor_id:
            raise QualificationError("FIXTURE_SPEC_REQUIRED")
        return replace(GENERIC_NDJSON, executor_id=record["provider"], stdin="instructions")
    if spec.executor_id != record["provider"]:
        raise QualificationError("SPEC_PROVIDER_MISMATCH")
    return spec


def check_launch_chain(pinned_files, resolve_pins, environ=None):
    """Every pinned file still present with its hash; every resolve pin still resolves to its pinned file on the
    executor PATH. Raises QualificationError. Shared by load-time re-validation and the bridge's per-run check."""
    for path, digest in dict(pinned_files).items():
        if not Path(path).is_file():
            raise QualificationError("LAUNCH_CHAIN_MISSING", Path(path).name)
        if _file_sha256(path) != digest:
            raise QualificationError("LAUNCH_CHAIN_HASH_MISMATCH", Path(path).name)
    for name, path in dict(resolve_pins).items():
        found = shutil.which(name, path=executor_path(environ))
        if not found or _same_file(found, path) is not True:
            raise QualificationError("LAUNCH_CHAIN_RESOLUTION_CHANGED", name)


def _check_evidence(record, client_root):
    p = evidence_dir(client_root) / record["evidence_file"]
    if not p.is_file():
        raise QualificationError("EVIDENCE_MISSING")
    data = p.read_bytes()
    if hashlib.sha256(data).hexdigest() != record["evidence_sha256"]:
        raise QualificationError("EVIDENCE_HASH_MISMATCH")
    try:
        ev = json.loads(data)
    except ValueError:
        raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "not json") from None
    if not isinstance(ev, dict) or ev.get("provider") != record["provider"]:
        raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "provider")
    if record["level"] == "FIXTURE_ONLY":
        if ev.get("fixture") is not True:
            raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "fixture")
        # Fixture evidence MUST name exactly the models it covers; the record may not claim more or other ones
        # (review round 2, R2-2; round 3, R3-1/R3-2: a missing or malformed list is refused, never a crash).
        models = ev.get("models")
        if not isinstance(models, list) or not models or any(m is not None and not isinstance(m, str) for m in models):
            raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "models")
        if models != list(record["models"]):
            raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "models")
        return
    # NATIVE: the direct probe record of the qualification run must show a successful probe of this very executable,
    # at this version. The record qualifies EXACTLY the probed model, nothing more (review round 2, R2-2: a signed
    # record could list models that were never exercised).
    if ev.get("ok") is not True or ev.get("version") != record["version"] or ev.get("executable_sha256") != record["executable_sha256"]:
        raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "probe")
    if list(record["models"]) != [ev.get("model")]:
        raise QualificationError("EVIDENCE_CONTENT_MISMATCH", "model")


def revalidate(record, *, client_root, trust: RecordTrust, allow_fixture=False, now=None, environ=None,
               codex_home=None) -> tuple:
    """-> (spec, resolved executable, args) or raises QualificationError with the invalidation reason.
    `codex_home` (worker composition only): see `check_codex_client_home`."""
    verify_trust(record, trust)
    if int(time.time() if now is None else now) >= record["expires_at"]:
        raise QualificationError("RECORD_EXPIRED")
    if record["level"] == "FIXTURE_ONLY" and not allow_fixture:
        raise QualificationError("LEVEL_NOT_ALLOWED", "FIXTURE_ONLY")
    spec = _spec_for(record)
    _check_evidence(record, client_root)
    exe = record["executable"]
    cmd = resolve_command(exe)
    if not cmd or not Path(exe).is_file() or _same_file(cmd[0], exe) is not True:
        raise QualificationError("EXECUTABLE_MISSING")
    if _file_sha256(exe) != record["executable_sha256"]:
        raise QualificationError("EXECUTABLE_HASH_MISMATCH")
    if record["level"] == "NATIVE_QUALIFIED" and Path(exe).suffix.lower() in (".cmd", ".bat", ".ps1") and not record["pinned_files"]:
        raise QualificationError("LAUNCH_CHAIN_NOT_PINNED")
    check_launch_chain(record["pinned_files"], record["resolve_pins"], environ)
    check_codex_client_home(record, codex_home, environ)
    for a in record["executable_args"]:
        if Path(a).is_absolute() and Path(a).suffix == ".py" and not Path(a).is_file():
            raise QualificationError("EXECUTABLE_ARGS_MISSING")
    probe = probe_version([exe, *record["executable_args"]])
    if not probe["installed"] or probe["version"] != record["version"] or record["version"] is None:
        raise QualificationError("VERSION_MISMATCH", f"{probe.get('version')} != {record['version']}")
    return spec, exe, list(record["executable_args"])


def compose_client(client_root, *, trust: RecordTrust, allow_fixture=False, auth_probe=None, environ=None,
                   adapters_factory=None, now=None, clock=None, codex_home=None) -> ClientComposition:
    """Phase 1 `HarnessRegistry` (all adapters, nothing qualified) plus every persisted record that re-validates now
    for THIS client (`trust`).

    `auth_probe(harness_id) -> True|False|None` defaults to the live CLI status probe for providers with a valid record
    (fixture records are authenticated by definition) and None (AUTH_UNVERIFIED) for everything else. The registry calls
    it on every `discover()`/`selectable()`, i.e. immediately before each bridge execution: nothing is cached."""
    from uri_harness_adapters import default_registry
    factory = adapters_factory or default_registry
    # `now` fixes composition time (tests); `clock` is consulted at every later re-validation (default: wall clock).
    now_fn = clock or (lambda: time.time() if now is None else now)
    rows, executables, bindings, exe_of, levels, composed = [], {}, {}, {}, {}, {}
    for item in load_records(client_root):
        rec = item["record"]
        if rec is None:
            rows.append({"provider": Path(item["path"]).stem, "status": "INVALIDATED", "reason": item["error"], "path": item["path"]})
            continue
        try:
            spec, exe, args = revalidate(rec, client_root=client_root, trust=trust, allow_fixture=allow_fixture, now=now_fn(), environ=environ,
                       codex_home=codex_home)
        except QualificationError as exc:
            rows.append({"provider": rec["provider"], "status": "INVALIDATED", "reason": exc.code, "detail": exc.detail,
                         "level": rec["level"], "path": item["path"]})
            continue
        executables[rec["provider"]] = [exe, *args]
        exe_of[rec["provider"]], levels[rec["provider"]] = exe, rec["level"]
        composed[rec["provider"]] = (item["path"], rec["record_sha256"])
        bindings[rec["provider"]] = ExecutorBinding(spec=spec, resolved_executable=exe, extra_argv=tuple(args), version=rec["version"],
                                                   executable_sha256=rec["executable_sha256"], qualified_models=tuple(rec["models"]),
                                                   pinned_files=tuple(sorted(rec["pinned_files"].items())),
                                                   resolve_pins=tuple(sorted(rec["resolve_pins"].items())),
                                                   revalidate=(lambda p=rec["provider"]: still_valid(p)))
        rows.append({"provider": rec["provider"], "status": "QUALIFIED", "reason": None, "level": rec["level"], "models": list(rec["models"]),
                     "executable": exe, "executable_sha256": rec["executable_sha256"], "pinned_files": len(rec["pinned_files"]),
                     "version": rec["version"], "evidence_sha256": rec["evidence_sha256"], "qualified_at": rec["qualified_at"],
                     "expires_at": rec["expires_at"], "path": item["path"]})

    def still_valid(provider):
        """None while the record composed for `provider` still holds NOW: same record bytes on disk (no silent swap
        for another record, even a validly signed one), and a full re-validation (signature, expiry, evidence, launch
        chain, version). Otherwise the reason code. Review round 2, R2-1."""
        path, digest = composed[provider]
        try:
            rec_now = validate_shape(json.loads(Path(path).read_text(encoding="utf-8")))
        except (OSError, ValueError) as exc:
            return exc.code if isinstance(exc, QualificationError) else "RECORD_UNREADABLE"
        if rec_now["record_sha256"] != digest:
            return "RECORD_CHANGED_SINCE_COMPOSITION"
        try:
            revalidate(rec_now, client_root=client_root, trust=trust, allow_fixture=allow_fixture, now=now_fn(), environ=environ,
                       codex_home=codex_home)
        except QualificationError as exc:
            return exc.code
        return None

    def probe(harness_id):
        if harness_id not in exe_of:
            return None
        if still_valid(harness_id) is not None:
            return None            # qualification no longer holds: AUTH_UNVERIFIED -> not usable (fail closed)
        if levels[harness_id] == "FIXTURE_ONLY":
            return True
        if auth_probe is not None:
            return auth_probe(harness_id)
        return native_auth_probe(harness_id, exe_of[harness_id], environ)

    registry = factory(executables, auth_probe=probe)
    for row in rows:
        if row["status"] != "QUALIFIED":
            continue
        p = row["provider"]
        if p not in registry.adapters or registry.adapters[p].refused:
            row.update(status="INVALIDATED", reason="PROVIDER_REFUSED_OR_UNKNOWN")
            bindings.pop(p, None)
            continue
        registry.qualify(p, row["level"], row["evidence_sha256"])
    return ClientComposition(registry=registry, executors=bindings, report=rows, allow_fixture=bool(allow_fixture))
