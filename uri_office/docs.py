"""Read-only document sessions for DOCX, PPTX and PDF (plan §5 `docs.py`, contract §4 DocView).

Opening a document:
  1. a picker grant for its kind (`grants.grant_open(..., kind=)`);
  2. the original is read once into `files/docs/<id>/` (it is never written); its SHA-256 and size are recorded;
  3. DOCX/PPTX: the sanitizer makes the render copy, then LibreOffice converts it to `preview.pdf` in the background
     at preview priority; PDF: the copy itself is the preview PDF (only the workers parse it);
  4. the outline comes from the render copy (python-docx / python-pptx) or from the text worker (PDF).
Page images are rendered on demand by the raster worker into the preview cache.
"""
from __future__ import annotations

import hashlib
import shutil
import threading
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path

from . import content, sanitize
from .contracts import Findings
from .errors import OfficeError
from .render import PREVIEW

MAX_DOCS = 8
MAX_PDF_PAGES = 2000
MAX_TEXT_CHARS = 2_000_000          # OD-3: the PDF text one request returns (the worker enforces the same cap)
MAX_OCR_PAGES = 20                  # OD-3: scanned pages read per request; the rest are listed as skipped
SUFFIX_KIND = {".docx": "docx", ".pptx": "pptx", ".pdf": "pdf"}


@dataclass
class DocSession:
    document_id: str
    kind: str
    name: str
    grant_id: str
    path: Path
    sha256: str
    size: int
    folder: Path
    render_copy: Path | None = None
    preview_pdf: Path | None = None
    cache: Path | None = None
    pages: int | None = None
    slides: int | None = None
    outline: list = field(default_factory=list)
    findings: Findings = field(default_factory=Findings)
    state: str = "rendering"            # rendering | ready | unavailable
    reason: str | None = None
    render_seconds: float | None = None
    opened_at: float = field(default_factory=time.time)
    lock: threading.RLock = field(default_factory=threading.RLock)
    ready: threading.Event = field(default_factory=threading.Event)

    def view(self) -> dict:
        return {"document_id": self.document_id, "kind": self.kind, "name": self.name, "pages": self.pages,
                "slides": self.slides, "outline": self.outline,
                "preview": {"state": self.state, "reason": self.reason, "seconds": self.render_seconds},
                "findings": self.findings.view(), "sha256_prefix": self.sha256[:12], "read_only": True,
                "renderer": "LibreOffice" if self.kind in ("docx", "pptx") else "Windows"}


class Documents:
    def __init__(self, hub, grants, audit=None):
        self.hub = hub
        self.grants = grants
        self.audit = audit or (lambda kind, payload: None)
        self.sessions: dict[str, DocSession] = {}
        self._lock = threading.Lock()
        self.root = hub.work_root / "docs"
        self.root.mkdir(parents=True, exist_ok=True)

    def get(self, did) -> DocSession:
        s = self.sessions.get(did) if isinstance(did, str) else None
        if s is None:
            raise OfficeError("UNKNOWN_DOCUMENT", "", 404)
        return s

    def open(self, raw_path) -> DocSession:
        if not isinstance(raw_path, str):
            raise OfficeError("PATH_REFUSED", "not a path")
        kind = SUFFIX_KIND.get(Path(raw_path).suffix.lower())
        if kind is None:
            raise OfficeError("UNSUPPORTED_KIND", "", 415)
        with self._lock:
            if len(self.sessions) >= MAX_DOCS:
                raise OfficeError("TOO_MANY_OPEN", "close a document first")
        g = self.grants.grant_open(raw_path, kind=kind)
        did = uuid.uuid4().hex[:16]
        folder = self.root / did
        folder.mkdir(parents=True)
        try:
            data = g.path.read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            src = folder / f"source.{kind}"
            src.write_bytes(data)
            del data
            s = DocSession(did, kind, g.path.name, g.grant_id, g.path, sha, src.stat().st_size, folder)
            if kind in ("docx", "pptx"):
                r = sanitize.make_render_copy(src, folder, kind)      # refusals raise before the session exists
                s.render_copy = r.path
                for check, sev, msg in r.findings():
                    s.findings.add(check, "structural", sev, msg, file="source")
                src.unlink()                                          # only the sanitized copy is kept
                if kind == "docx":
                    s.outline = content.docx_outline(r.path)
                else:
                    s.slides, s.outline = content.pptx_outline(r.path)
            else:
                s.preview_pdf = src
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            self.grants.revoke(g.grant_id)
            raise
        s.cache = self.hub.cache_dir(sha, kind)
        with self._lock:
            self.sessions[did] = s
        self.audit("office.document_opened", {"document_id": did, "kind": kind})
        threading.Thread(target=self._prepare, args=(s,), daemon=True, name=f"doc-{did}").start()
        return s

    def open_bytes(self, name: str, kind: str, data: bytes, *, owner: str) -> DocSession:
        """Authoring (milestone A): a preview document for a working copy held by an authoring session. Same
        sanitize -> render -> raster path as an opened file; no grant (nothing on disk belongs to it)."""
        if kind not in ("docx", "pptx"):
            raise OfficeError("UNSUPPORTED_KIND", "", 415)
        did = uuid.uuid4().hex[:16]
        folder = self.root / did
        folder.mkdir(parents=True)
        try:
            src = folder / f"source.{kind}"
            src.write_bytes(data)
            sha = hashlib.sha256(data).hexdigest()
            s = DocSession(did, kind, name, None, src, sha, len(data), folder)
            r = sanitize.make_render_copy(src, folder, kind)
            s.render_copy = r.path
            for check, sev, msg in r.findings():
                s.findings.add(check, "structural", sev, msg, file="source")
            src.unlink()
            if kind == "docx":
                s.outline = content.docx_outline(r.path)
            else:
                s.slides, s.outline = content.pptx_outline(r.path)
        except BaseException:
            shutil.rmtree(folder, ignore_errors=True)
            raise
        s.cache = self.hub.cache_dir(sha, kind)
        with self._lock:
            self.sessions[did] = s
        threading.Thread(target=self._prepare, args=(s,), daemon=True, name=f"doc-{did}").start()
        return s

    def _prepare(self, s: DocSession):
        t0 = time.perf_counter()
        with self._lock:
            closed = self.sessions.get(s.document_id) is not s
        if closed:                                           # Codex O2-R5-04: closed before a retry started
            s.ready.set()
            return
        try:
            if s.kind in ("docx", "pptx"):
                cached = s.cache / "preview.pdf"
                if cached.exists():
                    s.preview_pdf = cached
                else:
                    out = s.folder / "preview.pdf"
                    self.hub.lo.submit(s.render_copy, out, owner=s.document_id, priority=PREVIEW).result(300)
                    with self._lock:
                        if self.sessions.get(s.document_id) is not s:      # closed while it was converted
                            raise OfficeError("UNKNOWN_DOCUMENT", "closed", 404)
                    shutil.copy2(out, cached)
                    s.preview_pdf = out
            info = self.hub.text_request("info", pdf=str(s.preview_pdf))
            if not info.get("ok"):
                raise OfficeError("PREVIEW_UNAVAILABLE", info.get("error", ""), 422)
            if info.get("encrypted"):
                raise OfficeError("ENCRYPTED", "", 422)
            if info["pages"] > MAX_PDF_PAGES:
                raise OfficeError("TOO_MANY_PAGES", "", 413)
            with s.lock:
                s.pages = info["pages"]
                if s.kind == "pdf":
                    s.outline = [{"title": o["title"], "level": o["level"], "page": o["page"]}
                                 for o in info.get("outline", [])]
                    if not info.get("outline"):
                        s.outline = []
                if s.kind == "pptx" and s.slides is not None and s.slides != s.pages:
                    s.findings.add("page_count", "render", "warning",
                                   f"The preview has {s.pages} pages; the file has {s.slides} slides.")
                s.state = "ready"
                s.render_seconds = round(time.perf_counter() - t0, 2)
        except OfficeError as e:
            with s.lock:
                s.state, s.reason = "unavailable", e.code
        except Exception as e:  # noqa: BLE001
            with s.lock:
                s.state, s.reason = "unavailable", type(e).__name__
        finally:
            s.ready.set()

    def page(self, did, n: int, width: int) -> Path:
        s = self.get(did)
        if s.state == "rendering":
            raise OfficeError("PAGE_NOT_READY", "", 202)
        if s.state != "ready":
            raise OfficeError("PREVIEW_UNAVAILABLE", s.reason or "", 422)
        if not 1 <= n <= (s.pages or 0):
            raise OfficeError("UNKNOWN_PAGE", "", 404)
        return self.hub.page_png(s.preview_pdf, s.cache, n, width)

    def search(self, did, text) -> dict:
        s = self.get(did)
        if not isinstance(text, str) or not text.strip() or len(text) > 200:
            raise OfficeError("BAD_REQUEST", "search text")
        if s.state != "ready":
            raise OfficeError("PAGE_NOT_READY", "", 202)
        r = self.hub.text_request("search", pdf=str(s.preview_pdf), text=text, timeout=120)
        if not r.get("ok"):
            raise OfficeError("PREVIEW_UNAVAILABLE", r.get("error", ""), 422)
        if r.get("text_pages", 0) == 0:
            raise OfficeError("NO_TEXT_LAYER", "", 422)
        return {"matches": r["matches"], "truncated": r["truncated"]}

    def text(self, did, *, ocr: bool = False, max_chars: int = MAX_TEXT_CHARS) -> dict:
        """OD-3: a PDF's text for the owner ("Copy text", "To Word"), page by page, capped in total. Pages with no
        text layer are listed; with `ocr` (an explicit owner request only) up to MAX_OCR_PAGES of them are read with
        Tesseract from the page images the raster path makes. Nothing is written except the page-image cache."""
        s = self.get(did)
        if s.kind != "pdf":
            raise OfficeError("NOT_A_PDF", "text is taken from PDF files", 409)
        if s.state != "ready":
            raise OfficeError("PAGE_NOT_READY", "", 202)
        r = self.hub.text_request("text", pdf=str(s.preview_pdf), max_chars=min(int(max_chars), MAX_TEXT_CHARS),
                                  timeout=300)
        if not r.get("ok"):
            raise OfficeError("PREVIEW_UNAVAILABLE", r.get("error", ""), 422)
        pages = [{"page": p["page"], "text": p["text"], "source": "text" if p["text"].strip() else "none",
                  "failed": bool(p.get("failed"))} for p in r["pages"]]
        empty = [p["page"] for p in pages if p["source"] == "none"]
        skipped = []
        if ocr and empty:
            from . import ocr as OCR
            exe = OCR.tesseract_exe()
            if exe is None:
                raise OfficeError("OCR_UNAVAILABLE", "Tesseract is not installed on this PC", 503)
            todo, skipped = empty[:MAX_OCR_PAGES], empty[MAX_OCR_PAGES:]
            by_page = {p["page"]: p for p in pages}
            total = sum(len(p["text"]) for p in pages)
            for n in todo:
                if total >= max_chars:
                    skipped.append(n)
                    continue
                png = self.hub.page_png(s.preview_pdf, s.cache, n, OCR.OCR_WIDTH)
                t = OCR.ocr_png(png, exe)[: max(0, max_chars - total)]
                total += len(t)
                by_page[n].update(text=t, source="ocr" if t.strip() else "none")
            skipped.sort()
        joined = "\n\n".join(f"--- Page {p['page']} ---\n{p['text'].strip()}" for p in pages)
        no_text = [p["page"] for p in pages if p["source"] == "none"]
        self.audit("office.document_text", {"document_id": did, "pages": len(pages), "ocr_pages":
                                            sum(p["source"] == "ocr" for p in pages)})
        return {"document_id": did, "name": s.name, "pages": pages, "text": joined, "chars": len(joined),
                "truncated": bool(r.get("truncated")), "pages_without_text": no_text, "ocr_used": bool(ocr),
                "ocr_skipped": skipped, "total_pages": s.pages}

    def retry(self, did) -> dict:
        """Prepare the preview again after it was unavailable (for example the engine check had not finished). The
        sanitized copy is reused; nothing is read from the owner's file again."""
        s = self.get(did)
        with s.lock:
            if s.state != "unavailable":
                return s.view()
            s.state, s.reason = "rendering", None
            s.ready.clear()
        threading.Thread(target=self._prepare, args=(s,), daemon=True, name=f"doc-{did}-retry").start()
        return s.view()

    def close(self, did) -> dict:
        with self._lock:
            s = self.sessions.pop(did, None)
        if s is None:
            raise OfficeError("UNKNOWN_DOCUMENT", "", 404)
        self.hub.lo.cancel_owner(did)
        if s.grant_id is not None:                      # an authoring preview holds no grant
            self.grants.revoke(s.grant_id)
        s.ready.wait(5)
        shutil.rmtree(s.folder, ignore_errors=True)
        self.audit("office.document_closed", {"document_id": did})
        return {"closed": True}
