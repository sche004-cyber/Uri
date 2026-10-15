"""Engine pins and integrity (plan §3 "Engine integrity", spike S6 policy change, A1 §A7 worker scripts).

* `engines.json` (in the repository) pins LibreOffice: version, folder under `%LOCALAPPDATA%\\URI\\engines\\`,
  the SHA-256 of `soffice.bin`, the root hash of the full-tree manifest and the file count. It also pins the SHA-256
  of each worker script the service runs.
* **Qualification / "Verify engine"** (`verify_full`, about 107 s): hashes every file of the tree, checks the root
  against the pin, and stores the per-file manifest in `<state>/engines/<id>.manifest.json`.
* **Service start** (`fast_check`): compares the file list, sizes and modification times with the stored manifest.
* **Every engine launch** (`launch_check`, about 4 s): re-hashes the executables, libraries and the bundled Python
  (`.exe .dll .com .bin .pyd`) against the stored manifest, plus `soffice.bin` against its pin.
* **Worker scripts** (`run_copy`): read the script bytes, check them against the pin, write those exact bytes to a
  new file in `<state>/run/` and return that path, which closes the check-then-run window.

Any mismatch makes the engine `unavailable` with a named reason. An unverified engine is never run.
"""
from __future__ import annotations

import hashlib
import json
import os
import threading
import time
import uuid
from pathlib import Path

from .errors import OfficeError

HERE = Path(__file__).resolve().parent
PINS_FILE = HERE / "engines.json"
WORKERS_DIR = HERE / "workers"
LAUNCH_SUFFIXES = (".exe", ".dll", ".com", ".bin", ".pyd")
LAUNCH_CODE_SUFFIXES = (".py", ".pth", ".ini", ".cfg", ".pyc")      # Python code and start-up files under program/


def engines_root() -> Path:
    base = os.environ.get("URI_ENGINES_ROOT")          # tests point this at a fake tree
    if base:
        return Path(base)
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "URI" / "engines"


def pins() -> dict:
    return json.loads(PINS_FILE.read_text(encoding="utf-8"))


def sha256_file(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def manifest_root(entries: dict) -> str:
    """Root hash over sorted `relpath\\tsha256\\tsize\\n` lines. Modification times are not part of it."""
    h = hashlib.sha256()
    for rel in sorted(entries):
        e = entries[rel]
        h.update(f"{rel}\t{e['sha256']}\t{e['size']}\n".encode("utf-8"))
    return h.hexdigest()


def _walk(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames.sort()
        for n in sorted(filenames):
            p = Path(dirpath) / n
            yield p.relative_to(root).as_posix(), p


class EngineIntegrity:
    """Integrity state of one pinned engine tree. Thread-safe; the engine manager asks it before each launch."""

    def __init__(self, engine_id: str, state_dir: Path, pin: dict | None = None):
        self.id = engine_id
        self.pin = pin if pin is not None else pins()[engine_id]
        self.root = engines_root() / self.pin["dir"]
        self.store = Path(state_dir) / "engines" / f"{engine_id}.manifest.json"
        self._lock = threading.Lock()
        self.state = "unverified"
        self.reason: str | None = None
        self.last_verified: float | None = None
        self._entries: dict | None = None

    # ---- checks ----------------------------------------------------------------------------------------------
    def _fail(self, code: str, detail: str):
        self.state, self.reason = "unavailable", code
        raise OfficeError(code, detail, 503)

    def _program(self) -> Path:
        return self.root / "program"

    def verify_full(self, progress=None) -> dict:
        """Hash the whole tree, compare its root with the pin, store the manifest. About 107 s for LibreOffice.
        A failure that is not an integrity verdict (memory, disk, the signature tool) leaves the engine
        `unavailable` with ENGINE_CHECK_FAILED, never stuck in `verifying`; the owner can run the check again."""
        try:
            return self._verify_full(progress)
        except OfficeError:
            raise
        except Exception as e:  # noqa: BLE001
            self._entries = None
            self.state, self.reason = "unavailable", "ENGINE_CHECK_FAILED"
            raise OfficeError("ENGINE_CHECK_FAILED", type(e).__name__, 503) from None

    def _verify_full(self, progress=None) -> dict:
        with self._lock:
            if not self._program().is_dir():
                self._fail("ENGINE_MISSING", "engine folder not found")
            self.state, self.reason = "verifying", None
            t0 = time.perf_counter()
            entries = {}
            for rel, p in _walk(self.root):
                if rel == self.pin.get("installer_name"):          # the MSI kept beside the extract is not engine code
                    continue
                st = p.stat()
                entries[rel] = {"sha256": sha256_file(p), "size": st.st_size, "mtime_ns": st.st_mtime_ns}
                if progress and len(entries) % 500 == 0:
                    progress(len(entries))
            root = manifest_root(entries)
            ok = root == self.pin["manifest_root_sha256"] and len(entries) == self.pin["manifest_files"]
            sb = entries.get("program/soffice.bin", {}).get("sha256")
            ok = ok and sb == self.pin["soffice_bin_sha256"]
            seconds = round(time.perf_counter() - t0, 1)
            if not ok:
                self._entries = None
                self.store.unlink(missing_ok=True)
                self._fail("ENGINE_INTEGRITY", "engine files differ from the pinned engine")
            signers = None
            if self.pin.get("signers_allowed") and os.name == "nt":
                signers = signer_survey(self.root)
                bad = signer_problems(signers, self.pin)
                if bad:
                    self._entries = None
                    self.store.unlink(missing_ok=True)
                    self._fail("ENGINE_INTEGRITY", f"engine signature check failed for {len(bad)} file(s): {bad[:3]}")
            self.store.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store.with_name(self.store.name + f".{uuid.uuid4().hex[:8]}.tmp")
            tmp.write_text(json.dumps({"root": root, "files": entries, "verified_at": time.time()}),
                           encoding="utf-8")
            os.replace(tmp, self.store)
            self._entries = entries
            self.state, self.last_verified = "ready", time.time()
            out = {"ok": True, "files": len(entries), "seconds": round(time.perf_counter() - t0, 1), "mismatches": 0,
                   "hash_seconds": seconds}
            if signers is not None:
                out["signed_files_checked"] = len(signers)
            return out

    def _load(self) -> dict:
        if self._entries is None:
            if not self.store.exists():
                self.state, self.reason = "unverified", "ENGINE_UNAVAILABLE"
                raise OfficeError("ENGINE_UNAVAILABLE", "the engine has not been verified yet", 503)
            data = json.loads(self.store.read_text(encoding="utf-8"))
            if manifest_root(data["files"]) != self.pin["manifest_root_sha256"] or data["root"] != \
                    self.pin["manifest_root_sha256"]:
                self.store.unlink(missing_ok=True)
                self._fail("ENGINE_INTEGRITY", "the stored engine manifest does not match the pin")
            self._entries = data["files"]
            self.last_verified = data.get("verified_at")
        return self._entries

    def fast_check(self) -> None:
        """Service start: the file list, sizes and modification times equal the stored manifest."""
        with self._lock:
            if not self._program().is_dir():
                self._fail("ENGINE_MISSING", "engine folder not found")
            entries = self._load()
            seen = 0
            for rel, p in _walk(self.root):
                if rel == self.pin.get("installer_name"):
                    continue
                e = entries.get(rel)
                st = p.stat()
                if e is None or e["size"] != st.st_size or e["mtime_ns"] != st.st_mtime_ns:
                    self._entries = None
                    self._fail("ENGINE_INTEGRITY", "engine files changed since they were verified")
                seen += 1
            if seen != len(entries):
                self._entries = None
                self._fail("ENGINE_INTEGRITY", "engine files are missing")
            self.state, self.reason = "ready", None

    def launch_check(self) -> None:
        """Every engine launch: the `program/` tree has exactly the manifest's files (an added `sitecustomize.py`,
        `.pth` or DLL is refused), and executables, libraries and the bundled Python's code are re-hashed
        (review round 1, finding 5)."""
        with self._lock:
            entries = self._load()
            program = {rel for rel in entries if rel.startswith("program/")}
            seen = set()
            for rel, p in _walk(self.root / "program"):
                full = "program/" + rel
                seen.add(full)
                if full not in program:
                    self._entries = None
                    self._fail("ENGINE_INTEGRITY", "a file was added to the engine's program folder")
            if seen != program:
                self._entries = None
                self._fail("ENGINE_INTEGRITY", "an engine program file is missing")
            for rel, e in entries.items():
                if rel.lower().endswith(LAUNCH_SUFFIXES) or (rel.startswith("program/") and
                                                             rel.lower().endswith(LAUNCH_CODE_SUFFIXES)):
                    p = self.root / rel
                    try:
                        ok = sha256_file(p) == e["sha256"]
                    except OSError:
                        ok = False
                    if not ok:
                        self._entries = None
                        self._fail("ENGINE_INTEGRITY", "an engine program file changed")
            if entries.get("program/soffice.bin", {}).get("sha256") != self.pin["soffice_bin_sha256"]:
                self._fail("ENGINE_INTEGRITY", "soffice.bin differs from the pin")
            self.state, self.reason = "ready", None

    def status(self) -> dict:
        return {"id": self.id, "state": self.state, "version": self.pin.get("version"), "pinned": True,
                "reason": self.reason, "last_verified": self.last_verified}


def run_copy(script_name: str, state_dir: Path) -> Path:
    """Check a worker script against its pin and return a fresh copy of exactly the checked bytes under
    `<state>/run/`. The caller runs the copy and deletes it afterwards."""
    pinned = pins()["workers"].get(script_name)
    if pinned is None:
        raise OfficeError("WORKER_INTEGRITY", "unknown worker", 503)
    data = (WORKERS_DIR / script_name).read_bytes()
    if hashlib.sha256(data).hexdigest() != pinned:
        raise OfficeError("WORKER_INTEGRITY", "a worker script differs from its pin", 503)
    run = Path(state_dir) / "run"
    run.mkdir(parents=True, exist_ok=True)
    stem, suffix = os.path.splitext(script_name)
    dest = run / f"{stem}-{uuid.uuid4().hex[:12]}{suffix}"
    fd = os.open(dest, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o600)
    with os.fdopen(fd, "wb") as fh:
        fh.write(data)
    return dest


_SIGNER_PS = r"""
$ErrorActionPreference = 'Stop'
$root = $env:URI_SIGNER_ROOT
$files = Get-ChildItem -LiteralPath $root -Recurse -File | Where-Object { @('.exe','.dll','.bin','.com','.pyd') -contains $_.Extension.ToLower() }
$out = foreach ($s in ($files | Get-AuthenticodeSignature)) {
  [pscustomobject]@{ path = $s.Path.Substring($root.Length).TrimStart([char]92).Replace([string][char]92, '/');
                     status = $s.Status.ToString(); signer = if ($s.SignerCertificate) { $s.SignerCertificate.Subject } else { $null } }
}
@($out) | ConvertTo-Json -Compress
"""


def signer_survey(root: Path) -> list:
    """Authenticode status and signer subject of every executable and library in the engine tree (plan F11). Run at
    full verification only (about 18 s for LibreOffice 26.8.1); the SHA-256 manifest stays the primary control."""
    import subprocess
    from .workerproc import powershell_exe
    r = subprocess.run([powershell_exe(), "-NoProfile", "-NonInteractive", "-Command", _SIGNER_PS],
                       capture_output=True, text=True, timeout=600, env=dict(os.environ, URI_SIGNER_ROOT=str(root)),
                       creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
    if r.returncode != 0:
        raise OfficeError("ENGINE_INTEGRITY", "the engine signature check could not run", 503)
    data = json.loads(r.stdout or "[]")
    return data if isinstance(data, list) else [data]


def signer_problems(survey: list, pin: dict) -> list:
    """Files whose signature is not Valid from an allowed signer, except the pinned unsigned files (which the SHA-256
    manifest still covers). A signed file that became unsigned, or a new signer, is a problem."""
    allowed = set(pin.get("signers_allowed", []))
    unsigned_ok = set(pin.get("unsigned_allowed", []))
    bad = []
    for row in survey:
        if row.get("status") == "Valid" and row.get("signer") in allowed:
            continue
        if row.get("status") == "NotSigned" and row.get("path") in unsigned_ok:
            continue
        bad.append(f"{row.get('path')}: {row.get('status')}")
    return bad


def worker_hashes() -> dict:
    """Current hashes of the worker scripts (used by `python -m uri_office.engines pin-workers` and the pin test)."""
    return {p.name: sha256_file(p) for p in sorted(WORKERS_DIR.iterdir())
            if p.is_file() and p.suffix in (".py", ".ps1")}


def _main(argv):
    if argv[:1] == ["pin-workers"]:
        data = pins()
        data["workers"] = worker_hashes()
        PINS_FILE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(json.dumps(data["workers"], indent=1))
        return 0
    if argv[:1] == ["pin-signers"]:
        # Developer tool: record the signers and the unsigned files of the pinned tree (run once, after verify_full
        # has confirmed the tree is the pinned one).
        data = pins()
        lo = data["libreoffice"]
        survey = signer_survey(engines_root() / lo["dir"])
        lo["signers_allowed"] = sorted({r["signer"] for r in survey if r.get("status") == "Valid" and r.get("signer")})
        lo["unsigned_allowed"] = sorted(r["path"] for r in survey if r.get("status") == "NotSigned")
        lo["signed_files"] = sum(1 for r in survey if r.get("status") == "Valid")
        others = [r for r in survey if r.get("status") not in ("Valid", "NotSigned")]
        if others:
            print(json.dumps({"refused": others[:10]}))
            return 1
        PINS_FILE.write_text(json.dumps(data, indent=1) + "\n", encoding="utf-8")
        print(json.dumps({k: lo[k] for k in ("signers_allowed", "signed_files")} | {"unsigned": len(lo["unsigned_allowed"])}))
        return 0
    if argv[:1] == ["manifest-root"]:
        # Developer tool: print the root of the tree as it is now (used once to record the pin, with provenance).
        entries = {rel: {"sha256": sha256_file(p), "size": p.stat().st_size}
                   for rel, p in _walk(Path(argv[1])) if rel != (argv[2] if len(argv) > 2 else None)}
        print(json.dumps({"root": manifest_root(entries), "files": len(entries),
                          "soffice_bin": entries.get("program/soffice.bin", {}).get("sha256")}))
        return 0
    print("usage: python -m uri_office.engines pin-workers | pin-signers | manifest-root <dir> [installer name]")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
