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
        """Hash the whole tree, compare its root with the pin, store the manifest. About 107 s for LibreOffice."""
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
            self.store.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.store.with_name(self.store.name + f".{uuid.uuid4().hex[:8]}.tmp")
            tmp.write_text(json.dumps({"root": root, "files": entries, "verified_at": time.time()}),
                           encoding="utf-8")
            os.replace(tmp, self.store)
            self._entries = entries
            self.state, self.last_verified = "ready", time.time()
            return {"ok": True, "files": len(entries), "seconds": seconds, "mismatches": 0}

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
        """Every engine launch: re-hash executables, libraries and the bundled Python against the manifest."""
        with self._lock:
            entries = self._load()
            for rel, e in entries.items():
                if rel.lower().endswith(LAUNCH_SUFFIXES):
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
    if argv[:1] == ["manifest-root"]:
        # Developer tool: print the root of the tree as it is now (used once to record the pin, with provenance).
        entries = {rel: {"sha256": sha256_file(p), "size": p.stat().st_size}
                   for rel, p in _walk(Path(argv[1])) if rel != (argv[2] if len(argv) > 2 else None)}
        print(json.dumps({"root": manifest_root(entries), "files": len(entries),
                          "soffice_bin": entries.get("program/soffice.bin", {}).get("sha256")}))
        return 0
    print("usage: python -m uri_office.engines pin-workers | manifest-root <dir> [installer name]")
    return 2


if __name__ == "__main__":
    import sys
    raise SystemExit(_main(sys.argv[1:]))
