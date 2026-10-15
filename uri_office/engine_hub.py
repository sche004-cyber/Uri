"""The engines one Office service owns (plan §5, A1 §A3): the LibreOffice manager, the pypdf text worker and the
WinRT raster worker, each in its own Job Object, plus the preview cache. `GET /engines` reads `status()`.

Start-up order (spike S6 policy): the LibreOffice manifest fast check runs in the background at service start; the
full verification runs only when there is no stored manifest (first use, about 100 s) or on "Verify engine".
"""
from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
from pathlib import Path

from . import engines as E
from . import sanitize
from .errors import OfficeError
from .render import LibreOffice
from .workerproc import Worker, WorkerFailed, powershell_exe, python_exe

TEXT_MEMORY = 1024 * 2**20
RASTER_MEMORY = 1536 * 2**20
PREVIEW_CACHE_BYTES = 1 * 2**30
# The WinRT raster worker holds 30-41 MB of dedicated GPU memory while it lives (live run 2026-10-15; GPU engine use
# 0 %). Idle PDF workers are stopped after this long so nothing stays on the GPU between uses.
WORKER_IDLE_SECONDS = 60.0


class EngineHub:
    def __init__(self, state: Path, *, start_checks: bool = True, lo: LibreOffice | None = None):
        self.state = Path(state)
        self.lo = lo or LibreOffice(self.state)
        self.work_root = self.lo.work_root
        self.previews = self.work_root / "previews"
        self.previews.mkdir(parents=True, exist_ok=True)
        self._raster_state = ("ready", None)
        self.text = Worker("pdf_text", self._text_args, memory_limit=TEXT_MEMORY)
        self.raster = Worker("winrt_raster", self._raster_args, memory_limit=RASTER_MEMORY)
        self._cache_lock = threading.Lock()
        self._stopped = threading.Event()
        if start_checks:
            threading.Thread(target=self._startup_check, daemon=True, name="engine-check").start()
        threading.Thread(target=self._idle_loop, daemon=True, name="worker-idle").start()

    def _idle_loop(self):
        import time as _t
        while not self._stopped.wait(5.0):
            for w in (self.raster, self.text):
                if w.running and w.last_used and _t.monotonic() - w.last_used > WORKER_IDLE_SECONDS:
                    if w._lock.acquire(blocking=False):          # never stop a worker in the middle of a request
                        try:
                            if _t.monotonic() - w.last_used > WORKER_IDLE_SECONDS:
                                w.stop()
                        finally:
                            w._lock.release()

    def _text_args(self):
        c = E.run_copy("pdf_text.py", self.state)
        return [python_exe(), "-I", "-B", str(c), str(self.work_root)], c.unlink

    def _raster_args(self):
        c = E.run_copy("winrt_raster.ps1", self.state)
        return [powershell_exe(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File", str(c),
                str(self.work_root)], c.unlink

    def _startup_check(self):
        ei = self.lo.integrity
        try:
            if ei.store.exists():
                ei.fast_check()
            else:
                ei.verify_full()
        except OfficeError:
            pass                                             # state and reason are recorded on the integrity object

    def verify(self) -> dict:
        return self.lo.integrity.verify_full()

    # ---- requests to the PDF workers, with error mapping --------------------------------------------------------
    def text_request(self, op, **kw) -> dict:
        try:
            return self.text.request(op, timeout=kw.pop("timeout", 60.0), **kw)
        except WorkerFailed as e:
            raise OfficeError("PREVIEW_UNAVAILABLE", f"text worker {e.code}", 503) from None

    def raster_request(self, op, **kw) -> dict:
        try:
            r = self.raster.request(op, timeout=kw.pop("timeout", 60.0), **kw)
        except WorkerFailed as e:
            if e.code == "CLM_ACTIVE":
                self._raster_state = ("unavailable", "CLM_ACTIVE")
                raise OfficeError("CLM_ACTIVE", "", 503) from None
            raise OfficeError("PREVIEW_UNAVAILABLE", f"raster worker {e.code}", 503) from None
        self._raster_state = ("ready", None)
        return r

    # ---- preview cache (plan §5: key = input SHA-256, engine manifest, sanitizer version, renderer) -----------
    def cache_dir(self, input_sha: str, renderer: str) -> Path:
        pin = self.lo.integrity.pin
        key = hashlib.sha256("|".join([input_sha, pin["manifest_root_sha256"], sanitize.VERSION, renderer,
                                       E.pins()["workers"].get("winrt_raster.ps1", "")]).encode()).hexdigest()[:32]
        d = self.previews / key
        d.mkdir(parents=True, exist_ok=True)
        os.utime(d)
        return d

    def page_png(self, pdf: Path, cache: Path, page: int, width: int) -> Path:
        target = cache / f"p{page}_w{width}.png"
        if not target.exists():
            r = self.raster_request("render", pdf=str(pdf), out_dir=str(cache), pages=[page], width=width)
            if not r.get("ok") or not target.exists():
                raise OfficeError("PREVIEW_UNAVAILABLE", r.get("error", "render failed"), 422)
            self.prune_cache()
        return target

    def prune_cache(self, limit: int = PREVIEW_CACHE_BYTES):
        with self._cache_lock:
            dirs = []
            total = 0
            for d in self.previews.iterdir():
                if d.is_dir() and not d.is_symlink():
                    size = sum(f.stat().st_size for f in d.iterdir() if f.is_file())
                    dirs.append((d.stat().st_mtime, d, size))
                    total += size
            for _, d, size in sorted(dirs):
                if total <= limit:
                    break
                shutil.rmtree(d, ignore_errors=True)
                total -= size

    def clear_previews(self) -> int:
        n = 0
        with self._cache_lock:
            for d in self.previews.iterdir():
                if d.is_dir() and not d.is_symlink():
                    shutil.rmtree(d, ignore_errors=True)
                    n += 1
        return n

    # ---- status ------------------------------------------------------------------------------------------------
    def states(self) -> dict:
        """{engine id: (state, reason)} for the capability registry."""
        lo = self.lo.status()
        return {"libreoffice": (lo["state"], lo["reason"]), "winrt_pdf": self._raster_state,
                "pdf_text": ("ready", None)}

    def status(self) -> dict:
        lo = self.lo.status()
        return {"engines": [
            {k: lo.get(k) for k in ("id", "state", "version", "pinned", "reason", "last_verified", "queued",
                                    "last_start_seconds", "starts")},
            {"id": "winrt_pdf", "state": "running" if self.raster.running else self._raster_state[0],
             "version": "Windows.Data.Pdf", "pinned": True, "reason": self._raster_state[1],
             "starts": self.raster.starts},
            {"id": "pdf_text", "state": "running" if self.text.running else "ready", "version": "pypdf",
             "pinned": True, "reason": None, "starts": self.text.starts},
        ], "checked_at": time.time()}

    def pids(self) -> list:
        return [p for p in (self.lo.pids() + [self.text.pid(), self.raster.pid()]) if p]

    def shutdown(self):
        self._stopped.set()
        self.lo.shutdown()
        self.text.stop()
        self.raster.stop()
