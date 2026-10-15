"""Printing (phase O2P; amendment A1 §A4, §A6, §A7; owner OD-U12 and OD-U13).

One path for every kind: the document becomes a PDF first (a document session's preview PDF, a task's output PDF, or
a saved workbook converted by LibreOffice). Then:

  preview  -> the exact pages and settings, drawn by the raster worker, with the printer's printable area
  propose  -> a print card (A2UI, subject `print_job`) binding the PDF's SHA-256, the page list, the printer name,
              every setting, the printer's capability snapshot and status, and (for a printer that asks for a file)
              the owner-chosen output path
  apply    -> re-checks the printer (still there, same capabilities, not offline) and the PDF, then only QUEUES the
              job and returns; the print worker runs outside the approvals lock
  status   -> the job found by its unique document name `URI Office <token>` (no file name reaches the spooler)
  cancel   -> deletes that one job only

Every job, including a repeat of the same file, needs a new card. Nothing is printed without one. A network printer's
card says that the pages leave this PC. Printer names are untrusted text: shown, quoted, never interpreted.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import subprocess
import threading
import time
import uuid
from pathlib import Path

from uri_devices import printers as P

from . import engines as E
from . import jobobject as J
from .errors import OfficeError
from .workerproc import powershell_exe

PRINT_MEMORY = 1536 * 2**20          # spike S11: 600 dpi peaked at ~620 MB on a 3-page job
DEFAULT_DPI = 300                    # S11 decision (memory and spool size); 600 on request
MAX_PAGES = {300: 300, 600: 100}     # per-job spool budget (S11; physical drivers NOT VERIFIED)
JOB_TIMEOUT = 600.0
DUPLEX = ("simplex", "long", "short")
FIT = ("fit", "actual")


def _sha(p: Path) -> str:
    h = hashlib.sha256()
    with open(p, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


class PrintJob:
    def __init__(self, token, folder, record):
        self.token, self.folder, self.record = token, folder, record
        self.lock = threading.RLock()
        self.cancel = threading.Event()

    def view(self) -> dict:
        r = self.record
        return {k: r.get(k) for k in ("job", "state", "printer", "pages", "settings", "connection", "events",
                                      "error", "spooler", "created_at", "updated_at", "output_written")}

    def save(self):
        self.record["updated_at"] = time.time()
        tmp = self.folder / f"job.json.{uuid.uuid4().hex[:6]}.tmp"
        tmp.write_text(json.dumps(self.record), encoding="utf-8")
        os.replace(tmp, self.folder / "job.json")


class Printing:
    def __init__(self, state: Path, hub, approvals, grants, provider, pdf_source):
        """`pdf_source(source: dict) -> (pdf path, label)` gives the PDF for a document, task output or workbook."""
        self.state = Path(state)
        self.hub = hub
        self.approvals = approvals
        self.grants = grants
        self.provider = provider
        self.pdf_source = pdf_source
        self.root = hub.work_root / "print"
        self.root.mkdir(parents=True, exist_ok=True)
        self.jobs: dict[str, PrintJob] = {}
        self._q: queue.Queue = queue.Queue()
        threading.Thread(target=self._runner, daemon=True, name="print-jobs").start()

    # ---- discovery ---------------------------------------------------------------------------------------------
    def printers(self) -> dict:
        devs = self.provider.list()
        return {"printers": [d.view() for d in devs],
                "physical": any(d.connection in ("usb", "network", "unknown") for d in devs)}

    def printer(self, did: str) -> dict:
        d = self.provider.get(did)
        if d is None:
            raise OfficeError("UNKNOWN_PRINTER", "", 404)
        self.provider.capabilities(did)
        return d.view()

    # ---- settings --------------------------------------------------------------------------------------------------
    def _check(self, body: dict):
        d = self.provider.get(body.get("printer_id") or "")
        if d is None:
            raise OfficeError("UNKNOWN_PRINTER", "", 404)
        caps = self.provider.capabilities(d.id)
        st, detail = self.provider.status(d.id)
        s = body.get("settings") or {}
        papers = [p["name"] for p in caps.get("papers", [])]
        settings = {
            "copies": int(s.get("copies", 1)), "collate": bool(s.get("collate", False)),
            "landscape": bool(s.get("landscape", False)), "paper": s.get("paper") or (papers[0] if papers else None),
            "duplex": s.get("duplex", "simplex"), "color": bool(s.get("color", caps.get("color", False))),
            "fit": s.get("fit", "fit"), "dpi": int(s.get("dpi", DEFAULT_DPI)),
        }
        if not 1 <= settings["copies"] <= caps.get("max_copies", 1):
            raise OfficeError("SETTING_NOT_SUPPORTED", "copies", 409)
        if settings["duplex"] not in DUPLEX or (settings["duplex"] != "simplex" and not caps.get("duplex")):
            raise OfficeError("SETTING_NOT_SUPPORTED", "duplex", 409)
        if settings["color"] and not caps.get("color"):
            raise OfficeError("SETTING_NOT_SUPPORTED", "color", 409)
        if settings["paper"] not in papers:
            raise OfficeError("SETTING_NOT_SUPPORTED", "paper", 409)
        if settings["fit"] not in FIT or settings["dpi"] not in MAX_PAGES:
            raise OfficeError("SETTING_NOT_SUPPORTED", "fit or resolution", 409)
        if settings["collate"] and not caps.get("collate"):
            settings["collate"] = False
        return d, caps, (st, detail), settings

    def _pages(self, body, total: int) -> list:
        pages = body.get("pages")
        if pages in (None, "all"):
            return list(range(1, total + 1))
        if not isinstance(pages, list) or not pages or not all(isinstance(n, int) and 1 <= n <= total for n in pages):
            raise OfficeError("BAD_REQUEST", "page range", 400)
        return sorted(set(pages))

    def _info(self, printer: str, paper: str, landscape: bool) -> dict:
        r = self._run_worker({"op": "info", "printer": printer, "paper": paper, "landscape": landscape}, 60)
        return r[-1] if r else {}

    # ---- preview ---------------------------------------------------------------------------------------------------
    def preview(self, body: dict) -> dict:
        pdf, label = self.pdf_source(body.get("source") or {})
        d, caps, (st, detail), settings = self._check(body)
        info = self.hub.text_request("info", pdf=str(pdf))
        total = info.get("pages") or 0
        pages = self._pages(body, total)
        if len(pages) * settings["copies"] > MAX_PAGES[settings["dpi"]]:
            raise OfficeError("PRINT_TOO_LARGE", "Print fewer pages at a time.", 413)
        area = self._info(d.name, settings["paper"], settings["landscape"])
        warnings = []
        if settings["fit"] == "actual" and area.get("ok"):
            pw, ph = area["printable_mm"][2], area["printable_mm"][3]
            if settings["landscape"]:
                pw, ph = ph, pw
            for n in pages:
                bw, bh = (info.get("page_boxes") or [[612, 792]])[n - 1]
                if bw * 25.4 / 72 > pw + 0.5 or bh * 25.4 / 72 > ph + 0.5:
                    warnings.append(f"Page {n} is larger than the printable area and will be cut off.")
                    break
        return {"printer": d.view(), "status": st, "status_detail": detail, "settings": settings, "pages": pages,
                "total_pages": total, "printable_area": area, "warnings": warnings, "label": label}

    # ---- propose (the print card) ---------------------------------------------------------------------------------
    def propose(self, body: dict) -> dict:
        pv = self.preview(body)
        d = self.provider.get(body["printer_id"])
        if pv["status"] == "offline" or pv["status"] == "error":
            raise OfficeError("PRINTER_UNAVAILABLE", pv["status_detail"] or "The printer is not ready.", 409)
        pdf, label = self.pdf_source(body.get("source") or {})
        token = uuid.uuid4().hex[:16]
        folder = self.root / token
        folder.mkdir(parents=True)
        copy = folder / "print.pdf"
        shutil.copy2(pdf, copy)
        output = None
        if d.port.upper().startswith("PORTPROMPT") or d.port.upper() == "FILE:":
            # A printer that asks for a file (Microsoft Print to PDF): the owner picks the file through the save
            # dialog, so no Windows dialog ever opens from the print worker.
            g = self.grants.grant_save_as(body.get("output_path"), kind="pdf")
            if os.path.lexists(g.path):
                self.grants.revoke(g.grant_id)
                shutil.rmtree(folder, ignore_errors=True)
                raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
            output = {"path": str(g.path), "grant_id": g.grant_id}
        caps = self.provider.capabilities(d.id)          # the snapshot the card binds (read fresh, not cached)
        record = {"job": token, "state": "waiting_approval", "printer": d.name, "printer_id": d.id,
                  "connection": d.connection, "server": d.server, "pages": pv["pages"], "settings": pv["settings"],
                  "pdf_sha256": _sha(copy), "caps": caps, "status_at_proposal": pv["status"],
                  "output": output["path"] if output else None, "events": [], "created_at": time.time(),
                  "label": label}
        job = PrintJob(token, folder, record)
        job.grant_id = output["grant_id"] if output else None
        job.save()
        self.jobs[token] = job
        surface = self.approvals.propose_print(token, {
            "printer": d.name, "connection": d.connection, "server": d.server, "pages": pv["pages"],
            "settings": pv["settings"], "pdf_sha256": record["pdf_sha256"], "caps": caps,
            "printer_status": pv["status"], "output": record["output"], "label": label,
            "warnings": pv["warnings"]})
        return {"job": token, "messages": surface.messages(), "preview": pv}

    # ---- apply (from the approval) ---------------------------------------------------------------------------------
    def apply(self, body: dict) -> dict:
        job = self.jobs.get(body["job"])
        if job is None or job.record["state"] != "waiting_approval":
            raise OfficeError("STALE_CHANGE", "", 409)
        p = body["print"]
        d = self.provider.get(job.record["printer_id"])
        if d is None or d.name != p["printer"]:
            raise OfficeError("PRINTER_UNAVAILABLE", "The printer is no longer installed.", 409)
        st, detail = self.provider.status(d.id)
        caps = self.provider.capabilities(d.id)
        if caps != p["caps"]:
            raise OfficeError("STALE_CHANGE", "the printer's settings changed; review the print card again", 409)
        if st in ("offline", "error"):
            raise OfficeError("PRINTER_UNAVAILABLE", detail, 409)
        if _sha(job.folder / "print.pdf") != p["pdf_sha256"] or p["pages"] != job.record["pages"]:
            raise OfficeError("STALE_CHANGE", "", 409)
        if p["output"] and os.path.lexists(p["output"]):
            raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
        job.record["state"] = "queued"
        job.save()
        self._q.put(job.token)
        return {"job": job.token, "state": "queued"}

    def declined(self, token: str):
        job = self.jobs.get(token)
        if job is not None and job.record["state"] == "waiting_approval":
            job.record["state"] = "declined"
            job.save()
            self._cleanup(job)

    # ---- the print worker ------------------------------------------------------------------------------------------
    def _run_worker(self, req: dict, timeout: float, on_line=None) -> list:
        copy = E.run_copy("print_job.ps1", self.state)
        job = J.Job(memory_limit=PRINT_MEMORY)
        lines: list = []
        try:
            p = J.spawn([powershell_exe(), "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-File",
                         str(copy), str(self.hub.work_root)], job, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                        stderr=subprocess.DEVNULL, text=True, encoding="utf-8", errors="replace")
            p.stdin.write(json.dumps(req) + "\n")
            p.stdin.close()
            deadline = time.monotonic() + timeout

            def read():
                for line in p.stdout:
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        continue
                    lines.append(obj)
                    if on_line:
                        on_line(obj)
            t = threading.Thread(target=read, daemon=True)
            t.start()
            while t.is_alive() and time.monotonic() < deadline:
                t.join(0.2)
            if t.is_alive():
                job.close()
                raise OfficeError("PRINT_TIMEOUT", "", 504)
            p.wait(10)
        finally:
            job.close()
            try:
                copy.unlink()
            except OSError:
                pass
        return lines

    def _runner(self):
        while True:
            token = self._q.get()
            job = self.jobs.get(token)
            if job is None:
                continue
            try:
                self._print(job)
            except OfficeError as e:
                with job.lock:
                    job.record["state"] = "failed"
                    job.record["error"] = e.code
                    job.save()
            except Exception:  # noqa: BLE001
                with job.lock:
                    job.record["state"] = "failed"
                    job.record["error"] = "PRINT_FAILED"
                    job.save()
            finally:
                if job.record["state"] != "printing":
                    self._cleanup(job)

    def _print(self, job: PrintJob):
        r = job.record
        if job.cancel.is_set():
            r["state"] = "cancelled"
            job.save()
            return
        r["state"] = "printing"
        r["document_name"] = f"URI Office {job.token}"
        job.save()
        s = r["settings"]
        req = {"op": "print", "pdf": str(job.folder / "print.pdf"), "pages": r["pages"], "printer": r["printer"],
               "document_name": r["document_name"], "copies": s["copies"], "collate": s["collate"],
               "landscape": s["landscape"], "paper": s["paper"], "duplex": s["duplex"], "color": s["color"],
               "fit": s["fit"], "dpi": s["dpi"], "output_file": r["output"]}

        def on_line(obj):
            with job.lock:
                if obj.get("event") == "page":
                    r["events"].append({"page": obj["n"], "at": time.time()})
                    job.save()
        lines = self._run_worker(req, JOB_TIMEOUT, on_line)
        last = lines[-1] if lines else {}
        if not last.get("ok"):
            raise OfficeError(last.get("error") or "PRINT_FAILED", "", 500)
        r["worker"] = {k: last.get(k) for k in ("pages", "ms", "peak_ws_mb")}
        # The spooler's view of OUR job only. A job that already left the queue is "sent; status unavailable",
        # never claimed as printed (review A1-m3).
        seen = None
        for _ in range(20):
            j = P.find_job(r["printer"], r["document_name"])
            if j is None:
                break
            seen = j
            if "error" in j["status"] or "offline" in j["status"] or "paper_out" in j["status"]:
                break
            time.sleep(0.5)
        r["spooler"] = seen
        if r["output"]:
            out = Path(r["output"])
            for _ in range(40):
                if out.exists() and out.stat().st_size > 0:
                    break
                time.sleep(0.25)
            r["output_written"] = out.exists() and out.stat().st_size > 0
        r["state"] = "sent" if not (seen and {"error", "offline", "paper_out"} & set(seen["status"])) else \
            "printer_problem"
        job.save()

    # ---- status and cancel -----------------------------------------------------------------------------------------
    def get(self, token: str) -> PrintJob:
        job = self.jobs.get(token) if isinstance(token, str) else None
        if job is None:
            raise OfficeError("UNKNOWN_PRINT_JOB", "", 404)
        return job

    def status(self, token: str) -> dict:
        job = self.get(token)
        v = job.view()
        if job.record.get("document_name") and job.record["state"] in ("printing", "sent"):
            v["spooler_now"] = P.find_job(job.record["printer"], job.record["document_name"])
        return v

    def cancel(self, token: str) -> dict:
        job = self.get(token)
        with job.lock:
            st = job.record["state"]
            if st in ("waiting_approval", "queued"):
                job.cancel.set()
                self.approvals.close_workbook(token)
                job.record["state"] = "cancelled"
                job.save()
                self._cleanup(job)
            elif st in ("printing", "sent", "printer_problem") and job.record.get("document_name"):
                ok = P.cancel_job(job.record["printer"], job.record["document_name"])
                job.record["state"] = "cancelled" if ok else job.record["state"]
                job.record["cancel_result"] = "deleted" if ok else "not_in_queue"
                job.save()
            else:
                raise OfficeError("NOT_CANCELLABLE", "", 409)
        return job.view()

    def _cleanup(self, job: PrintJob):
        try:
            (job.folder / "print.pdf").unlink(missing_ok=True)
        except OSError:
            pass
        gid = getattr(job, "grant_id", None)
        if gid:
            self.grants.revoke(gid)
