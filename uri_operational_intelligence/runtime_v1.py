"""Runtime v1 discovery, identity verification, readiness and lifecycle.

Source of truth: `model_lab/integration/local_brain.json` (the frozen Runtime v1 configuration) plus the pinned
hashes of the freeze record (`model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` section 1). This module
never edits either. It starts AT MOST ONE llama-server, on the configured loopback port, with exactly the frozen
argv; it attaches to an already-running instance only when that instance is provably the pinned binary serving the
pinned model; it never stops a process it did not start.

Identity has two layers:
  * artifact identity: SHA-256 of the server binary, the Vulkan backend DLL, the model, the vision projector and
    the MTP draft. Large files are re-hashed in full on first use and whenever their size or mtime changes; a
    stat-matched cache entry is reported as method "cached" (never as a fresh full hash);
  * live identity: the listening process' executable path and command line, and the server's own /props report
    (model path, context size, build).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import threading
import time
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path

import httpx

REPO_ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = REPO_ROOT / "model_lab" / "integration" / "local_brain.json"
DEFAULT_STATE = REPO_ROOT / "work" / "oi" / "state"

# Freeze record section 1 pins this DLL; local_brain.json does not carry it.
VULKAN_DLL_SHA256 = "3742b48f47a09eec0c04c27b8ff109e4ef125692822c0092bcec0235b9223210"
EXPECTED_BUILD = "b11425"

# Readiness states (UI contract: docs/operational_intelligence/OI_UI_INTEGRATION_CONTRACT.md)
NOT_CONFIGURED = "NOT_CONFIGURED"
ARTIFACT_MISSING = "ARTIFACT_MISSING"
IDENTITY_MISMATCH = "IDENTITY_MISMATCH"
STOPPED = "STOPPED"
STARTING = "STARTING"
LOADING = "LOADING"
READY = "READY"
FOREIGN_INSTANCE = "FOREIGN_INSTANCE"
FAILED = "FAILED"


class RuntimeError_(RuntimeError):
    """Raised with a stable code as its message."""

    def __init__(self, code, detail=None):
        super().__init__(code)
        self.code, self.detail = code, detail


def load_config(path=CONFIG_PATH) -> dict:
    p = Path(path)
    if not p.is_file():
        raise RuntimeError_(NOT_CONFIGURED, str(p))
    cfg = json.loads(p.read_text(encoding="utf-8"))
    if cfg.get("schema") != "uri.local_brain.v1":
        raise RuntimeError_(NOT_CONFIGURED, "schema")
    return cfg


def config_digest(cfg) -> str:
    return hashlib.sha256(json.dumps(cfg, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def base_url(cfg) -> str:
    return f"http://127.0.0.1:{int(cfg['runtime']['port'])}"


def expected_argv(cfg) -> list:
    """Exactly the frozen argv (freeze record section 2 / local_brain.py ResidentRuntime.argv)."""
    r, m = cfg["runtime"], cfg["model"]
    a = [r["binary"], "-m", m["path"], "-c", str(r["ctx"]), "-ngl", str(r["ngl"]), "-fa", "on",
         "-ctk", r["cache_type"], "-ctv", r["cache_type"], "-np", "1", "--host", "127.0.0.1",
         "--port", str(r["port"]), "--jinja", "--reasoning-format", "deepseek", "--no-webui",
         "--load-mode", r["load_mode"], "--cache-ram", str(r["cache_ram_mib"])]
    if m.get("mmproj") and r.get("vision_enabled"):
        a += ["--mmproj", m["mmproj"]]
    else:
        a += ["--no-mmproj"]
    return a + list(r.get("extra_args", []))


def pinned_artifacts(cfg) -> list:
    r, m = cfg["runtime"], cfg["model"]
    rows = [("server_binary", r["binary"], r["binary_sha256"]),
            ("vulkan_backend", str(Path(r["binary"]).with_name("ggml-vulkan.dll")), VULKAN_DLL_SHA256),
            ("model", m["path"], m["sha256"])]
    if m.get("mmproj") and r.get("vision_enabled"):
        rows.append(("vision_projector", m["mmproj"], m["mmproj_sha256"]))
    if m.get("mtp_draft"):
        rows.append(("mtp_draft", m["mtp_draft"]["path"], m["mtp_draft"]["sha256"]))
    return [{"role": a, "path": str(Path(p)), "sha256": h} for a, p, h in rows]


def _sha256(path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 24), b""):
            h.update(chunk)
    return h.hexdigest()


def _atomic_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + "." + uuid.uuid4().hex + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=1, sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def verify_artifacts(cfg, state_dir=DEFAULT_STATE, full=False) -> dict:
    """Per-artifact MATCH / MISMATCH / MISSING with the method used ("full" or "cached")."""
    cache_path = Path(state_dir) / "artifact_hash_cache.json"
    try:
        cache = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        cache = {}
    rows, changed = [], False
    for art in pinned_artifacts(cfg):
        p = Path(art["path"])
        row = dict(art)
        if not p.is_file():
            row.update(status="MISSING", method=None, observed=None)
            rows.append(row)
            continue
        st = p.stat()
        key = str(p.resolve()).lower()
        hit = cache.get(key)
        # Cache hit needs size, mtime, ctime AND file id (st_ino) unchanged. This guards against accidental change and
        # file replacement; it is not tamper-proof against a same-user writer who restores all metadata (full=True
        # re-hashes; the host runs a full verify on request and on every first sight of a file).
        if (not full and hit and hit["size"] == st.st_size and hit["mtime_ns"] == st.st_mtime_ns
                and hit.get("ctime_ns") == st.st_ctime_ns and hit.get("ino") == st.st_ino):
            observed, method = hit["sha256"], "cached"
        else:
            t0 = time.monotonic()
            observed, method = _sha256(p), "full"
            cache[key] = {"size": st.st_size, "mtime_ns": st.st_mtime_ns, "ctime_ns": st.st_ctime_ns, "ino": st.st_ino,
                          "sha256": observed,
                          "hashed_at": time.time(), "hash_seconds": round(time.monotonic() - t0, 2)}
            changed = True
        row.update(status="MATCH" if observed == art["sha256"] else "MISMATCH", method=method, observed=observed)
        rows.append(row)
    if changed:
        _atomic_json(cache_path, cache)
    statuses = {r["status"] for r in rows}
    overall = "MATCH" if statuses == {"MATCH"} else ("MISSING" if "MISSING" in statuses else "MISMATCH")
    return {"overall": overall, "artifacts": rows,
            "methods": sorted({r["method"] for r in rows if r["method"]})}


@dataclass
class Readiness:
    state: str
    url: str
    owned: bool = False
    pid: int | None = None
    model_id: str | None = None
    detail: str | None = None
    live_identity: dict = field(default_factory=dict)
    artifact_identity: dict | None = None
    checked_at: float = field(default_factory=time.time)

    def to_dict(self):
        return asdict(self)


def _listener_pid(port):
    import psutil
    try:
        for c in psutil.net_connections(kind="tcp"):
            if c.status == psutil.CONN_LISTEN and c.laddr and c.laddr.port == port:
                return c.pid
    except (psutil.AccessDenied, OSError):
        return None
    return None


def _create_time(pid):
    import psutil
    try:
        return psutil.Process(pid).create_time()
    except (psutil.Error, OSError):
        return None


def inspect_process(pid, cfg) -> dict:
    """Is the process listening on the Runtime v1 port the pinned binary with the frozen argv?"""
    import psutil
    try:
        p = psutil.Process(pid)
        exe, cmdline = p.exe(), p.cmdline()
    except (psutil.Error, OSError) as exc:
        return {"pid": pid, "authorized": False, "reason": "PROCESS_UNREADABLE:" + type(exc).__name__}
    want = expected_argv(cfg)
    same_exe = os.path.normcase(os.path.abspath(exe)) == os.path.normcase(os.path.abspath(cfg["runtime"]["binary"]))
    # argv[0] spelling may differ (quoting, slashes); compare the arguments exactly.
    same_args = [a.replace("\\", "/") for a in cmdline[1:]] == [a.replace("\\", "/") for a in want[1:]]
    return {"pid": pid, "exe": exe, "authorized": bool(same_exe and same_args),
            "reason": None if same_exe and same_args else ("EXECUTABLE_MISMATCH" if not same_exe else "ARGV_MISMATCH")}


def probe_server(url, timeout=2.0) -> dict:
    """GET /health and /props. Never raises."""
    out = {"reachable": False}
    try:
        with httpx.Client(base_url=url, timeout=timeout) as c:
            h = c.get("/health")
            out.update(reachable=True, health_status=h.status_code)
            if h.status_code == 200:
                p = c.get("/props")
                if p.status_code == 200:
                    props = p.json()
                    gen = props.get("default_generation_settings") or {}
                    out.update(model_path=props.get("model_path"), build_info=props.get("build_info"),
                               n_ctx=gen.get("n_ctx") or props.get("n_ctx"),
                               total_slots=props.get("total_slots"),
                               modalities=props.get("modalities"))
    except (httpx.HTTPError, ValueError) as exc:
        out["error"] = type(exc).__name__
    return out


def live_identity_problems(cfg, props) -> list:
    problems = []
    mp = props.get("model_path")
    if not mp or os.path.normcase(os.path.abspath(mp)) != os.path.normcase(os.path.abspath(cfg["model"]["path"])):
        problems.append("MODEL_PATH_MISMATCH")
    if props.get("n_ctx") is not None and int(props["n_ctx"]) != int(cfg["runtime"]["ctx"]):
        problems.append("CONTEXT_SIZE_MISMATCH")
    if props.get("build_info") and EXPECTED_BUILD not in str(props["build_info"]):
        problems.append("BUILD_MISMATCH")
    if props.get("total_slots") not in (None, 1):
        problems.append("SLOT_COUNT_MISMATCH")
    return problems


class RuntimeManager:
    """Single resident Runtime v1 instance: start-or-attach, readiness, stop-if-owned."""

    def __init__(self, cfg=None, state_dir=DEFAULT_STATE):
        self.cfg = cfg or load_config()
        self.state_dir = Path(state_dir)
        self.url = base_url(self.cfg)
        self.port = int(self.cfg["runtime"]["port"])
        self._contained = None
        self._lock_fd = None
        self._guard = threading.Lock()
        self.last_artifacts = None
        self._verified_pid = None
        self.started_at = None
        self.load_seconds = None

    # ---- readiness ------------------------------------------------------------------------------
    def status(self) -> Readiness:
        probe = probe_server(self.url)
        model_id = self.cfg["model"]["id"]
        if not probe["reachable"]:
            if self._contained is not None and self._contained.proc.poll() is None:
                return Readiness(STARTING, self.url, owned=True, pid=self._contained.proc.pid, model_id=model_id,
                                 artifact_identity=self.last_artifacts)
            return Readiness(STOPPED, self.url, model_id=model_id, artifact_identity=self.last_artifacts)
        pid = _listener_pid(self.port)
        proc = inspect_process(pid, self.cfg) if pid else {"pid": None, "authorized": False,
                                                           "reason": "LISTENER_PID_UNKNOWN"}
        owned = bool(self._contained is not None and pid == self._contained.proc.pid)
        if not proc["authorized"]:
            return Readiness(FOREIGN_INSTANCE, self.url, owned=owned, pid=pid, model_id=model_id,
                             detail=proc["reason"], live_identity={"process": proc, "server": probe})
        if probe.get("health_status") == 503:
            return Readiness(LOADING, self.url, owned=owned, pid=pid, model_id=model_id,
                             live_identity={"process": proc, "server": probe}, artifact_identity=self.last_artifacts)
        if probe.get("health_status") != 200:
            return Readiness(FAILED, self.url, owned=owned, pid=pid, model_id=model_id,
                             detail="HEALTH_%s" % probe.get("health_status"), live_identity={"process": proc, "server": probe})
        problems = live_identity_problems(self.cfg, probe)
        if not problems:
            # Every READY answer re-checks the pinned artifacts (metadata cache: a few stat calls when nothing
            # changed; a full re-hash of any file whose size/mtime/ctime/id changed; MISSING if a file is gone).
            self.last_artifacts = verify_artifacts(self.cfg, self.state_dir)
            if self.last_artifacts["overall"] != "MATCH":
                problems.append("ARTIFACT_" + self.last_artifacts["overall"])
            proc["create_time"] = _create_time(pid)
        state = READY if not problems else IDENTITY_MISMATCH
        return Readiness(state, self.url, owned=owned, pid=pid, model_id=model_id,
                         detail=",".join(problems) or None, live_identity={"process": proc, "server": probe},
                         artifact_identity=self.last_artifacts)

    # ---- lifecycle ------------------------------------------------------------------------------
    def _acquire_lock(self):
        """Cross-process: only one OI manager may start Runtime v1 at a time on this machine."""
        import msvcrt
        self.state_dir.mkdir(parents=True, exist_ok=True)
        path = self.state_dir / "runtime_v1.start.lock"
        fd = os.open(path, os.O_RDWR | os.O_CREAT)
        try:
            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
        except OSError:
            os.close(fd)
            raise RuntimeError_("START_LOCK_HELD", str(path)) from None
        self._lock_fd = fd

    def _release_lock(self):
        import msvcrt
        if self._lock_fd is not None:
            try:
                os.lseek(self._lock_fd, 0, 0)
                msvcrt.locking(self._lock_fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
            os.close(self._lock_fd)
            self._lock_fd = None

    def ensure_ready(self, *, start=True, full_verify=False, timeout=300.0, on_state=None) -> Readiness:
        """Attach to an authorized running instance, or start one (if `start`). Never starts a second instance and
        never touches a foreign process on the port."""
        with self._guard:
            current = self.status()
            if current.state in (READY, LOADING):
                # Attaching to a running instance still requires the pinned artifacts on disk to verify.
                self.last_artifacts = verify_artifacts(self.cfg, self.state_dir, full=full_verify)
                if self.last_artifacts["overall"] != "MATCH":
                    self._verified_pid = None
                    return Readiness(IDENTITY_MISMATCH, self.url, pid=current.pid, model_id=self.cfg["model"]["id"],
                                     detail="ARTIFACT_" + self.last_artifacts["overall"],
                                     artifact_identity=self.last_artifacts, live_identity=current.live_identity)
                if current.state == LOADING:
                    return self._wait_ready(timeout, on_state)
                current.artifact_identity = self.last_artifacts
                return current
            if current.state in (FOREIGN_INSTANCE, IDENTITY_MISMATCH, FAILED):
                return current
            if not start:
                return current
            self._acquire_lock()
            try:
                # Re-check under the lock: another manager may have started it meanwhile.
                current = self.status()
                if current.state != STOPPED:
                    return self._wait_ready(timeout, on_state) if current.state == LOADING else current
                if on_state:
                    on_state(STARTING)
                self.last_artifacts = verify_artifacts(self.cfg, self.state_dir, full=full_verify)
                self._verified_pid = None
                if self.last_artifacts["overall"] != "MATCH":
                    state = ARTIFACT_MISSING if self.last_artifacts["overall"] == "MISSING" else IDENTITY_MISMATCH
                    return Readiness(state, self.url, model_id=self.cfg["model"]["id"],
                                     detail="ARTIFACT_" + self.last_artifacts["overall"],
                                     artifact_identity=self.last_artifacts)
                self._spawn()
                return self._wait_ready(timeout, on_state)
            finally:
                self._release_lock()

    def _spawn(self):
        from uri_supervisor.winproc import spawn_contained
        log_dir = self.state_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log = open(log_dir / ("llama-server-%s.log" % time.strftime("%Y%m%d-%H%M%S")), "wb")
        name = "uri-oi-runtime-v1-" + uuid.uuid4().hex
        self.started_at = time.monotonic()
        # Kill-on-close job: if this manager process dies, the OS ends the server (no orphan, no duplicate).
        self._contained = spawn_contained(expected_argv(self.cfg), name, stdout=log, stderr=subprocess.STDOUT,
                                          stdin=subprocess.DEVNULL)
        _atomic_json(self.state_dir / "runtime_v1.instance.json",
                     {"pid": self._contained.proc.pid, "create_time": self._contained.identity.create_time,
                      "job": name, "argv": expected_argv(self.cfg), "config_digest": config_digest(self.cfg),
                      "started_wall": time.time()})

    def _wait_ready(self, timeout, on_state=None) -> Readiness:
        t0 = time.monotonic()
        last = None
        while time.monotonic() - t0 < timeout:
            if self._contained is not None and self._contained.proc.poll() is not None:
                return Readiness(FAILED, self.url, model_id=self.cfg["model"]["id"],
                                 detail="LOCAL_BRAIN_EXITED:%s" % self._contained.proc.returncode,
                                 artifact_identity=self.last_artifacts)
            r = self.status()
            if r.state != last and on_state:
                on_state(r.state)
            last = r.state
            if r.state in (READY, FOREIGN_INSTANCE, IDENTITY_MISMATCH, FAILED):
                if r.state == READY and self.started_at is not None and self.load_seconds is None:
                    self.load_seconds = round(time.monotonic() - self.started_at, 1)
                return r
            time.sleep(0.5)
        return Readiness(FAILED, self.url, model_id=self.cfg["model"]["id"], detail="LOCAL_BRAIN_START_TIMEOUT",
                         artifact_identity=self.last_artifacts)

    def stop(self) -> bool:
        """Stops only an instance THIS manager started. Returns True when the job is confirmed empty."""
        c, self._contained = self._contained, None
        if c is None:
            return False
        try:
            ok = c.kill()
        finally:
            c.close()
        return ok

    @property
    def owns_instance(self) -> bool:
        return self._contained is not None and self._contained.proc.poll() is None
