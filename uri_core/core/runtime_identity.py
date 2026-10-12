"""C1 opt-in identity and synthetic composition. No private store imports.

Only the isolated developer composition uses this module. Legacy launchers
keep their existing defaults. The fixture guard is not production sandboxing.
"""
from __future__ import annotations

import ctypes
import hashlib
import importlib.machinery
import importlib.metadata
import importlib.util
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import uuid

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey

BASELINE = "e8e3b65259c45fc823addc3ef8969425a265bd1b"
COMPOSITION = "c1-isolated-compatibility"
PAIRED_COMPOSITION = "c2-paired-core"
CONTRACT = "uri-runtime/1"


class RuntimeIdentityError(ValueError):
    """Safe machine code; never contains a path, key, or provider exception."""
    def __init__(self, code, attempt_pid=None):
        super().__init__(code)
        self.attempt_pid=attempt_pid


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()


def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def absolute(value):
    if not isinstance(value, str) or not Path(value).is_absolute():
        raise RuntimeIdentityError("ABSOLUTE_PATH_REQUIRED")
    return Path(value).resolve()


def source_files(root):
    # Every source package the runtime may import is pinned: Core plus the client-only provider
    # adapter boundary (uri_harness_adapters), which Core itself never imports.
    paths = [p for package in ("uri_core", "uri_harness_adapters") for p in (root / package).rglob("*") if p.is_file()
             and "__pycache__" not in p.parts and p.suffix in (".py", ".json", ".yaml", ".yml", ".toml")]
    paths += [root / "requirements.txt", root / "uri_workspace/capabilities_registry.json"]
    contract = root / "docs/architecture/C2_STORE_METHOD_CONTRACT.json"
    if contract.is_file():
        paths.append(contract)
    paths += [root / "scripts" / name for name in (
        "c1_bootstrap.py", "run_uri_isolated_server.py", "uri_server_launcher.py", "provision_uri_server.py",
        "uri_server.ps1", "uri_server_manifest.schema.json",
    )]
    paths += [root / "scripts" / name for name in (
        "run_uri_client_worker.py", "provision_uri_client.py", "uri_client_launcher.py", "uri_client.ps1",
        "uri_client_manifest.schema.json",
    ) if (root / "scripts" / name).is_file()]
    return {p.relative_to(root).as_posix(): sha(p) for p in sorted(paths)}


def dependency_digest():
    # Described installed dependency identity, not a claim to hash the OS image.
    rows = []
    for dist in importlib.metadata.distributions():
        rows.append([dist.metadata["Name"], dist.version,
                     hashlib.sha256((dist.read_text("METADATA") or "").encode()).hexdigest(),
                     hashlib.sha256((dist.read_text("RECORD") or "").encode()).hexdigest()])
    pth = {p.name: sha(p) for p in (Path(sys.prefix) / "Lib/site-packages").glob("*.pth")}
    git_exe=shutil.which("git")
    if git_exe is None:raise RuntimeIdentityError("GIT_UNAVAILABLE")
    return hashlib.sha256(canonical({"python":sys.version, "distributions":sorted(rows), "pth":pth,
                                     "git":sha(git_exe)})).hexdigest()


PINNED_PACKAGES = ("uri_core", "uri_harness_adapters", "scripts")


class _PinnedSourceLoader(importlib.machinery.SourceFileLoader):
    """Compile exactly the bytes whose digest is pinned; never consult cached bytecode."""
    def __init__(self, fullname, path, digest):
        super().__init__(fullname, path)
        self.digest = digest

    def get_code(self, fullname):
        data = self.get_data(self.path)
        if hashlib.sha256(data).hexdigest() != self.digest:
            raise ImportError("C1_SOURCE_DRIFT", name=fullname)
        self.executed_digest = self.digest
        return self.source_to_code(data, self.path)


class PinnedSourceFinder:
    """Every later import from a pinned package executes the pinned bytes or fails.

    Closes the paths a start-up hash alone leaves open: stale __pycache__ bytecode
    (timestamp-validated, so -B does not help), extension modules or sourceless
    .pyc files that shadow a .py, files added or edited after validation (lazy
    imports), and namespace portions contributed by other sys.path entries.
    """
    def __init__(self, root, files):
        self.root = Path(root)
        self.files = dict(files)

    def find_spec(self, fullname, path=None, target=None):
        if fullname.partition(".")[0] not in PINNED_PACKAGES:
            return None
        rel = fullname.replace(".", "/")
        if rel + "/__init__.py" in self.files and rel + ".py" in self.files:
            raise ImportError("C1_SOURCE_AMBIGUOUS", name=fullname)
        for candidate, package in ((rel + "/__init__.py", True), (rel + ".py", False)):
            if candidate in self.files:
                origin = str(self.root / candidate)
                return importlib.util.spec_from_file_location(
                    fullname, origin, loader=_PinnedSourceLoader(fullname, origin, self.files[candidate]),
                    submodule_search_locations=[str(self.root / rel)] if package else None)
        if any(name.startswith(rel + "/") for name in self.files):
            spec = importlib.machinery.ModuleSpec(fullname, None, is_package=True)
            spec.submodule_search_locations = [str(self.root / rel)]
            return spec
        raise ImportError("C1_SOURCE_NOT_PINNED", name=fullname)


def install_source_pin(root, files):
    """Bind already-imported pinned modules to their digests, then govern all later imports.

    The entrypoint must have loaded scripts/c1_bootstrap.py by exact path before importing anything
    from the source root: only its loader records the digest of the bytes a module actually compiled,
    and only it keeps the source root off sys.path (so nothing planted there shadows another module).
    """
    root = Path(root).resolve()
    boot = sys.modules.get("c1_bootstrap")
    if (boot is None or Path(getattr(boot, "__file__", None) or os.devnull).resolve() != root / "scripts/c1_bootstrap.py"
            or hashlib.sha256(getattr(boot, "SOURCE", b"") or b"").hexdigest() != files.get("scripts/c1_bootstrap.py")
            or any(Path(p or os.curdir).resolve() == root for p in sys.path)):
        raise RuntimeIdentityError("C1_BOOTSTRAP_UNPINNED")
    for name, module in list(sys.modules.items()):
        if module is None or name.partition(".")[0] not in PINNED_PACKAGES:
            continue
        rel = name.replace(".", "/")
        location = getattr(module, "__file__", None)
        if location is None:
            if rel + "/__init__.py" in files or rel + ".py" in files:
                raise RuntimeIdentityError("SOURCE_MODULE_UNPINNED")
            # Namespace package (uri_core, scripts): Python merges a portion from every sys.path
            # entry (pywin32 contributes a site-packages 'scripts' directory, for example). Pin it
            # to the source-root portion only; the finder governs every later submodule import.
            own = root / name.replace(".", "/")
            if own not in {Path(p).resolve() for p in getattr(module, "__path__", ())}:
                raise RuntimeIdentityError("SOURCE_MODULE_UNPINNED")
            module.__path__ = [str(own)]
            continue
        # The module's NAME decides which pinned file it must be (a miscased or redirected import is
        # refused), and the digest its loader recorded when compiling must equal that pin: comparing a
        # fresh re-read of the file would accept bytes changed after they ran.
        candidates = [c for c in (rel + "/__init__.py", rel + ".py") if c in files]
        loader = getattr(getattr(module, "__spec__", None), "loader", None)
        if (len(candidates) != 1 or Path(location).resolve() != (root / candidates[0]).resolve()
                or getattr(loader, "executed_digest", None) != files[candidates[0]]):
            raise RuntimeIdentityError("SOURCE_MODULE_UNPINNED")
    finder = PinnedSourceFinder(root, files)
    sys.meta_path[:] = [f for f in sys.meta_path if not isinstance(f, PinnedSourceFinder)]
    sys.meta_path.insert(0, finder)
    importlib.invalidate_caches()
    return finder


def dpapi(data, decrypt=False):
    """Current-user DPAPI (CRYPTPROTECT_UI_FORBIDDEN, no entropy): same-user logical isolation only."""
    if os.name != "nt":
        raise RuntimeIdentityError("WINDOWS_REQUIRED")
    class Blob(ctypes.Structure):
        # DATA_BLOB: DWORD cbData (c_ulong is 32-bit on Windows), BYTE *pbData.
        _fields_ = [("size", ctypes.c_ulong), ("data", ctypes.POINTER(ctypes.c_ubyte))]
    if not isinstance(data, bytes) or len(data) >= 2**32:
        raise RuntimeIdentityError("PROTECTED_KEY_UNAVAILABLE")
    # Private library handles: never mutate the process-wide windll prototypes.
    crypt32 = ctypes.WinDLL("crypt32", use_last_error=True)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    fn = crypt32.CryptUnprotectData if decrypt else crypt32.CryptProtectData
    fn.argtypes = [ctypes.POINTER(Blob), ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
                   ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(Blob)]
    fn.restype = ctypes.c_int
    kernel32.LocalFree.argtypes = [ctypes.c_void_p]
    kernel32.LocalFree.restype = ctypes.c_void_p
    buf = ctypes.create_string_buffer(data, len(data) or 1)
    src = Blob(len(data), ctypes.cast(buf, ctypes.POINTER(ctypes.c_ubyte)))
    dst = Blob()
    try:
        if not fn(ctypes.byref(src), None, None, None, None, 1, ctypes.byref(dst)):
            raise RuntimeIdentityError("PROTECTED_KEY_UNAVAILABLE")
        try:
            return ctypes.string_at(dst.data, dst.size)
        finally:
            if decrypt:
                ctypes.memset(dst.data, 0, dst.size)  # plaintext key material
            kernel32.LocalFree(dst.data)
    finally:
        if not decrypt:
            ctypes.memset(buf, 0, len(data))  # plaintext copy made by create_string_buffer


def atomic_json(path, value):
    path = Path(path)
    temp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with open(temp, "x", encoding="utf-8") as f:
        json.dump(value, f, sort_keys=True, indent=2)
        f.flush(); os.fsync(f.fileno())
    os.replace(temp, path)


def child_environment(state, interpreter):
    # Do not inherit URI/provider/harness variables, API keys, or native homes.
    env = {k:os.environ[k] for k in ("SYSTEMROOT", "WINDIR", "COMSPEC", "PATHEXT") if k in os.environ}
    git_exe=shutil.which("git")
    if git_exe is None:raise RuntimeIdentityError("GIT_UNAVAILABLE")
    home = str(state / "home")
    env.update({"PATH":os.pathsep.join([str(interpreter.parent),str(Path(env.get("SYSTEMROOT", "C:/Windows"))/"System32"),str(Path(git_exe).parent)]),
                "USERPROFILE":home, "HOME":home, "APPDATA":str(state/"home/roaming"),
                "LOCALAPPDATA":str(state/"home/local"), "TEMP":str(state/"temp"), "TMP":str(state/"temp"),
                "PYTHONDONTWRITEBYTECODE":"1"})
    return env


def provision(root, state, interpreter, port, composition=COMPOSITION):
    """Explicit local developer provisioning into a NEW synthetic directory."""
    import psutil
    if composition not in (COMPOSITION, PAIRED_COMPOSITION):
        raise RuntimeIdentityError("MANIFEST_CONTRACT_MISMATCH")
    root, state, interpreter = absolute(str(root)), absolute(str(state)), absolute(str(interpreter))
    if not state.is_relative_to(root / "work/c1") or state == root / "work/c1":
        raise RuntimeIdentityError("SYNTHETIC_ROOT_REQUIRED")
    if interpreter != root / ".venv/Scripts/python.exe" or not interpreter.is_file():
        raise RuntimeIdentityError("ISOLATED_INTERPRETER_REQUIRED")
    if not isinstance(port, int) or not 1024 <= port <= 65535 or port in (8000,8018,8021,11434,1234):
        raise RuntimeIdentityError("NONPRODUCTION_PORT_REQUIRED")
    head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
    if head != BASELINE:
        raise RuntimeIdentityError("SOURCE_CHECKPOINT_MISMATCH")
    files = source_files(root)
    dependencies = dependency_digest()
    if state.exists():
        raise RuntimeIdentityError("FRESH_SYNTHETIC_ROOT_REQUIRED")
    state.mkdir(parents=True)
    sid = subprocess.check_output(["whoami", "/user", "/fo", "csv", "/nh"], text=True).strip().split(",")[-1].strip('"')
    acl = subprocess.run(["icacls", str(state), "/inheritance:r", "/grant:r", "*"+sid+":(OI)(CI)F", "*S-1-5-18:(OI)(CI)F"], capture_output=True)
    if acl.returncode:
        raise RuntimeIdentityError("STATE_ACL_FAILED")
    for rel in ("control", "catalogue", "logs", "uri_workspace", "home/roaming", "home/local", "temp"):
        (state/rel).mkdir(parents=True, exist_ok=True)
    # Only this accepted PUBLIC catalogue is seeded. No legacy data/config.
    catalogue = (root/"uri_workspace/capabilities_registry.json").read_bytes()
    (state/"uri_workspace/capabilities_registry.json").write_bytes(catalogue)
    (state/"catalogue/capabilities_registry.json").write_bytes(catalogue)
    private = Ed25519PrivateKey.generate()
    public = private.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw)
    (state/"control/signing_key.dpapi").write_bytes(dpapi(private.private_bytes(
        serialization.Encoding.Raw, serialization.PrivateFormat.Raw, serialization.NoEncryption())))
    manifest = {"schema_version":1, "server_id":str(uuid.uuid4()), "composition_id":composition,
        "contract_version":CONTRACT, "source_root":str(root), "source_checkpoint":BASELINE,
        "source_files":files, "source_manifest_digest":hashlib.sha256(canonical(files)).hexdigest(),
        "entrypoint":str(root/"scripts/run_uri_isolated_server.py"), "interpreter":str(interpreter),
        "interpreter_sha256":sha(interpreter), "process_image":psutil.Process().exe(),
        "process_image_sha256":sha(psutil.Process().exe()), "dependency_manifest_digest":dependencies,
        "state_root":str(state), "control_root":str(state/"control"), "catalogue_root":str(state/"catalogue"),
        "host":"127.0.0.1", "port":port, "model_policy":"lazy-not-selected",
        "log_policy":"fixture-local", "public_key":public.hex(),
        "public_key_fingerprint":hashlib.sha256(public).hexdigest()}
    atomic_json(state/"synthetic-fixture.json", {"server_id":manifest["server_id"], "composition_id":composition})
    atomic_json(state/"manifest.json", manifest)
    return state/"manifest.json"


class RuntimeManifest:
    def __init__(self, path, validate=True):
        self.path = absolute(str(path))
        try:
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            raise RuntimeIdentityError("MANIFEST_UNREADABLE") from None
        if validate:
            self.validate()
        self.digest = hashlib.sha256(canonical(self.data)).hexdigest()

    def validate(self):
        m=self.data
        # Exact schema prevents unnoticed ambient/default configuration.
        required=set(("schema_version server_id composition_id contract_version source_root source_checkpoint "
            "source_files source_manifest_digest entrypoint interpreter interpreter_sha256 process_image "
            "process_image_sha256 dependency_manifest_digest state_root control_root catalogue_root host port "
            "model_policy log_policy public_key public_key_fingerprint").split())
        if not isinstance(m,dict) or set(m)!=required:
            raise RuntimeIdentityError("MANIFEST_SCHEMA_INVALID")
        try: uuid.UUID(m["server_id"])
        except (ValueError,TypeError,AttributeError): raise RuntimeIdentityError("SERVER_ID_INVALID") from None
        if type(m["schema_version"]) is not int or m["schema_version"]!=1 or m["composition_id"] not in (COMPOSITION, PAIRED_COMPOSITION) or m["contract_version"]!=CONTRACT or m["source_checkpoint"]!=BASELINE:
            raise RuntimeIdentityError("MANIFEST_CONTRACT_MISMATCH")
        if m["host"]!="127.0.0.1" or type(m["port"]) is not int or not 1024<=m["port"]<=65535 or m["port"] in (8000,8018,8021,11434,1234):
            raise RuntimeIdentityError("NONPRODUCTION_LOOPBACK_REQUIRED")
        root=absolute(m["source_root"]); state=absolute(m["state_root"])
        if root!=Path(__file__).resolve().parents[2]:
            raise RuntimeIdentityError("SOURCE_ROOT_MISMATCH")
        if self.path!=state/"manifest.json" or not state.is_relative_to(root/"work/c1") or state==root/"work/c1":
            raise RuntimeIdentityError("SYNTHETIC_ROOT_REQUIRED")
        if absolute(m["control_root"])!=state/"control" or absolute(m["catalogue_root"])!=state/"catalogue":
            raise RuntimeIdentityError("STATE_ROOT_MISMATCH")
        if absolute(m["entrypoint"])!=root/"scripts/run_uri_isolated_server.py" or absolute(m["interpreter"])!=root/".venv/Scripts/python.exe":
            raise RuntimeIdentityError("ENTRYPOINT_OR_INTERPRETER_MISMATCH")
        if absolute(sys.executable)!=absolute(m["interpreter"]):
            raise RuntimeIdentityError("LAUNCHER_INTERPRETER_MISMATCH")
        if m["model_policy"]!="lazy-not-selected" or m["log_policy"]!="fixture-local":
            raise RuntimeIdentityError("COMPOSITION_POLICY_MISMATCH")
        fixture=json.loads((state/"synthetic-fixture.json").read_text())
        if fixture!={"server_id":m["server_id"],"composition_id":m["composition_id"]}:
            raise RuntimeIdentityError("FIXTURE_IDENTITY_MISMATCH")
        head=subprocess.check_output(["git","-C",str(root),"rev-parse","HEAD"], text=True).strip()
        if head!=m["source_checkpoint"]:
            raise RuntimeIdentityError("SOURCE_CHECKPOINT_MISMATCH")
        observed=source_files(root)
        if m["source_files"]!=observed or m["source_manifest_digest"]!=hashlib.sha256(canonical(observed)).hexdigest():
            raise RuntimeIdentityError("SOURCE_MANIFEST_MISMATCH")
        if sha(m["interpreter"])!=m["interpreter_sha256"] or sha(m["process_image"])!=m["process_image_sha256"]:
            raise RuntimeIdentityError("INTERPRETER_HASH_MISMATCH")
        import psutil
        if absolute(psutil.Process().exe())!=absolute(m["process_image"]):
            raise RuntimeIdentityError("PROCESS_IMAGE_MISMATCH")
        if dependency_digest()!=m["dependency_manifest_digest"]:
            raise RuntimeIdentityError("DEPENDENCY_MANIFEST_MISMATCH")
        try:
            public=bytes.fromhex(m["public_key"])
            Ed25519PublicKey.from_public_bytes(public)
        except (ValueError,TypeError): raise RuntimeIdentityError("PUBLIC_KEY_INVALID") from None
        if hashlib.sha256(public).hexdigest()!=m["public_key_fingerprint"]:
            raise RuntimeIdentityError("PUBLIC_KEY_FINGERPRINT_MISMATCH")
        # Both seeded copies are authority-bearing: the legacy composition reads uri_workspace/, the
        # paired ClientService reads catalogue_root/. Each must equal the pinned public catalogue.
        pinned=m["source_files"]["uri_workspace/capabilities_registry.json"]
        for copy in (state/"uri_workspace/capabilities_registry.json", state/"catalogue/capabilities_registry.json"):
            if not copy.is_file() or sha(copy)!=pinned:
                raise RuntimeIdentityError("CATALOGUE_FIXTURE_MISMATCH")

    def identity_fields(self):
        return {k:self.data[k] for k in ("server_id","composition_id","contract_version","source_checkpoint")} | {"build_manifest_digest":self.digest}


class RuntimeIdentity:
    def __init__(self, manifest):
        self.manifest=manifest
        self.generation=str(uuid.uuid4())
        raw=dpapi((Path(manifest.data["control_root"])/"signing_key.dpapi").read_bytes(),True)
        self.key=Ed25519PrivateKey.from_private_bytes(raw)
        public=self.key.public_key().public_bytes(serialization.Encoding.Raw,serialization.PublicFormat.Raw)
        if public.hex()!=manifest.data["public_key"]:
            raise RuntimeIdentityError("SIGNING_KEY_MISMATCH")
        self.guard=None; self.started=False; self.catalogue_ready=False; self.legacy_state_ready=False

    def public(self, nonce=None):
        result=self.manifest.identity_fields() | {"generation":self.generation}
        if nonce is not None:
            if not isinstance(nonce,str) or len(nonce)!=64 or any(c not in "0123456789abcdef" for c in nonce):
                raise RuntimeIdentityError("NONCE_INVALID")
            result |= {"nonce":nonce,"signature":self.key.sign(canonical({"identity":result,"nonce":nonce})).hex()}
        return result

    def status(self):
        return {"identity":self.public(),"readiness":{
            "http":"READY" if self.started else "STARTING",
            "public_catalogue":"READY" if self.catalogue_ready else "DEGRADED",
            "legacy_synthetic_state":("NOT_REQUIRED" if self.manifest.data["composition_id"]==PAIRED_COMPOSITION else
                                      "READY" if self.legacy_state_ready else "DEGRADED"),
            "main_brain":"NOT_SELECTED", "edge":"NOT_SELECTED", "paired_clients":(
                "AVAILABLE" if self.manifest.data["composition_id"]==PAIRED_COMPOSITION else "NOT_IMPLEMENTED_C1"),
            "harnesses":"NOT_IMPLEMENTED_C1",
            "isolation":"SYNTHETIC_FIXTURE_ONLY"},
            "startup_controls":dict(self.guard.counts) if self.guard else {}}


def verify_proof(manifest, result, nonce):
    try:
        if set(result)!=set(manifest.identity_fields())|{"generation","nonce","signature"}:
            raise ValueError()
        if any(result[k]!=v for k,v in manifest.identity_fields().items()) or result["nonce"]!=nonce:
            raise ValueError()
        uuid.UUID(result["generation"])
        identity={k:v for k,v in result.items() if k not in ("nonce","signature")}
        Ed25519PublicKey.from_public_bytes(bytes.fromhex(manifest.data["public_key"])).verify(
            bytes.fromhex(result["signature"]),canonical({"identity":identity,"nonce":nonce}))
    except Exception:
        raise RuntimeIdentityError("IDENTITY_PROOF_FAILED") from None
    return identity


class FixtureGuard:
    """Bound Python file accesses and prevent subprocess/network warm-up.

    Defense against accidental legacy startup access, not malicious native
    code or an adversary sharing this Windows account. Installed before Core.
    """
    def __init__(self, manifest):
        self.state=absolute(manifest.data["state_root"]); self.source=absolute(manifest.data["source_root"])
        self.read_roots=[self.state,self.source/"uri_core",self.source/"uri_harness_adapters",self.source/"scripts",Path(sys.prefix).resolve(),Path(sys.base_prefix).resolve(),Path(os.environ["SYSTEMROOT"]).resolve()]
        self.read_files={self.source/"docs/architecture/C2_STORE_METHOD_CONTRACT.json"}
        self.starting=True
        self.counts={"blocked_external_reads":0,"blocked_external_writes":0,"blocked_startup_connections":0,"blocked_startup_subprocesses":0}

    def check_path(self, value, write=False):
        if isinstance(value,int) or value is None: return
        path=Path(os.fsdecode(value)).resolve()
        allowed=path.is_relative_to(self.state) if write else path in self.read_files or path==self.source or any(path.is_relative_to(r) for r in self.read_roots)
        if not allowed:
            self.counts["blocked_external_writes" if write else "blocked_external_reads"]+=1
            raise PermissionError("C1_FIXTURE_PATH_DENIED")

    def __call__(self,event,args):
        if event=="open":
            mode,flags=args[1],args[2]
            write=(isinstance(mode,str) and any(c in mode for c in "wax+")) or (isinstance(flags,int) and bool(flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC|os.O_APPEND)))
            self.check_path(args[0],write)
        elif event in ("os.listdir","os.scandir"):
            self.check_path(args[0])
        elif event in ("os.mkdir","os.remove","os.rmdir","os.truncate"):
            self.check_path(args[0],True)
        elif event in ("os.rename","os.link","os.symlink"):
            self.check_path(args[0],True);self.check_path(args[1],True)
        elif self.starting and event in ("socket.connect","subprocess.Popen"):
            self.counts["blocked_startup_connections" if event=="socket.connect" else "blocked_startup_subprocesses"]+=1
            raise PermissionError("C1_STARTUP_EXTERNAL_ACTION_DENIED")
