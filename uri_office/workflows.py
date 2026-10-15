"""Workflow runner (plan §5 `workflows.py`, §6.1 lifecycle, §6.3 record, AC-O2-7, AC-O2-9, AC-O2-12, AC-O2-14).

One folder per run under `files/workflows/<id>/` with `workflow.json` (no document text) and the working files.
Lifecycle for `save_as_pdf`, the one O2 workflow:

  create -> plan card (office.run_plan, plan_sha256) -> run: copy + sanitize (D) -> convert (E, LibreOffice)
  -> validate (D) -> page images (E, Windows) -> ready_to_save | needs_review
  -> [Accept warnings] -> Save (save dialog grant, kind=pdf) -> output card (office.apply_change)
  -> no-overwrite atomic write -> saved

Apply of a plan only records the decision and queues the run (never inside the approvals lock). Each workflow has its
own lock, taken before the approvals lock. At service start, runs that were `running` become `interrupted`, and open
output cards are closed. Resume re-confirms each input through a new picker grant and continues only when its SHA-256
equals the recorded value. Abandoned runs are removed after 7 days.
"""
from __future__ import annotations

import hashlib
import json
import os
import queue
import shutil
import threading
import time
import uuid
from pathlib import Path

from . import capabilities as CAP
from . import sanitize
from .contracts import Findings
from .errors import OfficeError
from .render import CONVERT
from .safe_write import publish_copy
from .validate import Validator, sha256
from concurrent.futures import TimeoutError as FutureTimeout

RETENTION_SECONDS = 7 * 24 * 3600
TERMINAL = ("saved", "cancelled", "failed", "discarded")


def _now():
    return time.time()


class Workflow:
    def __init__(self, folder: Path, record: dict):
        self.folder = folder
        self.record = record
        self.lock = threading.RLock()
        self.cancel = threading.Event()
        self.findings = Findings()
        self.private: dict = {}            # in-memory only: grant ids, session references

    @property
    def id(self) -> str:
        return self.record["workflow_id"]

    def save(self):
        self.record["updated_at"] = _now()
        tmp = self.folder / f"workflow.json.{uuid.uuid4().hex[:6]}.tmp"
        tmp.write_text(json.dumps(self.record, indent=1, default=str), encoding="utf-8")
        os.replace(tmp, self.folder / "workflow.json")

    def step(self, sid) -> dict:
        return next(s for s in self.record["steps"] if s["id"] == sid)

    def view(self) -> dict:
        r = self.record
        return {k: r.get(k) for k in ("workflow_id", "contract", "capability", "state", "created_at", "updated_at",
                                      "steps", "outputs", "errors", "warnings_accepted", "interrupted_at_step")} | {
            "inputs": [{"kind": i["kind"], "name": i["name"]} for i in r["inputs"]],
            "findings": self.findings.view() or r.get("findings", [])}


class Workflows:
    def __init__(self, office_state: Path, hub, grants, approvals, documents, workbook_lookup):
        self.hub = hub
        self.grants = grants
        self.approvals = approvals
        self.documents = documents
        self.workbook_lookup = workbook_lookup          # workbook_id -> M1/M2 Session (or raise)
        self.root = hub.work_root / "workflows"
        self.root.mkdir(parents=True, exist_ok=True)
        self.items: dict[str, Workflow] = {}
        self._items_lock = threading.Lock()
        self._q: queue.Queue = queue.Queue()
        self.validator = Validator(_HubText(hub), _HubRaster(hub))
        self._startup_scan()
        threading.Thread(target=self._runner, daemon=True, name="workflows").start()

    # ---- lookup --------------------------------------------------------------------------------------------------
    def get(self, wid) -> Workflow:
        w = self.items.get(wid) if isinstance(wid, str) else None
        if w is None:
            raise OfficeError("UNKNOWN_WORKFLOW", "", 404)
        return w

    def lock_of(self, wid):
        w = self.items.get(wid) if isinstance(wid, str) else None
        return w.lock if w else None

    def listing(self) -> dict:
        running, done = [], []
        with self._items_lock:
            items = list(self.items.values())
        for w in sorted(items, key=lambda w: w.record["created_at"], reverse=True):
            item = {k: w.record.get(k) for k in ("workflow_id", "capability", "state", "created_at", "updated_at")}
            (done if w.record["state"] in TERMINAL else running).append(item)
        return {"running": running, "done": done[:50]}

    # ---- create ----------------------------------------------------------------------------------------------------
    def create(self, capability: str, inputs: list, options: dict | None = None) -> dict:
        cap = CAP.get(capability)
        if cap is None:
            raise OfficeError("BAD_REQUEST", "unknown capability")
        if cap["status"] != "available":
            raise OfficeError("CAPABILITY_PLANNED", CAP.planned_message(capability), 409)
        if capability != "save_as_pdf":
            raise OfficeError("BAD_REQUEST", "this capability has no workflow")
        if not isinstance(inputs, list) or len(inputs) != 1 or not isinstance(inputs[0], dict):
            raise OfficeError("BAD_REQUEST", "one input")
        src = self._resolve_input(inputs[0])
        wid = uuid.uuid4().hex[:20]
        folder = self.root / wid
        folder.mkdir(parents=True)
        out_name = Path(src["name"]).stem + ".pdf"
        steps = [{"id": "prepare", "kind": "D", "label": "Make a safe working copy"},
                 {"id": "convert", "kind": "E", "engine": "libreoffice", "label": "Convert to PDF with LibreOffice"},
                 {"id": "validate", "kind": "D", "label": "Check the PDF (pages, fonts, blank pages, margins)"},
                 {"id": "preview", "kind": "E", "engine": "winrt_pdf", "label": "Draw the pages for review"}]
        record = {"workflow_id": wid, "contract": "o2.1", "capability": capability, "intent": capability,
                  "state": "planned", "created_at": _now(), "updated_at": _now(),
                  "inputs": [{"kind": src["kind"], "name": src["name"], "path": str(src["path"]),
                              "sha256": src["sha256"], "size": src["size"]}],
                  "steps": [{"id": s["id"], "kind": s["kind"], "engine": s.get("engine"), "engine_version": None,
                             "state": "pending", "started_at": None, "ended_at": None, "finding_ids": []}
                            for s in steps],
                  "outputs": [], "findings": [], "approvals": [], "errors": [], "warnings_accepted": False}
        w = Workflow(folder, record)
        w.private["source"] = src
        w.private["grant_ids"] = [src["grant_id"]]
        plan = {"capability": capability, "title": f"Save {src['name']} as PDF?",
                "steps": [{"id": s["id"], "kind": s["kind"], "label": s["label"]} for s in steps],
                "inputs": [{"name": src["name"], "kind": src["kind"], "sha256": src["sha256"]}],
                "outputs": [{"name": out_name, "kind": "pdf"}]}
        w.private["plan"] = plan
        with self._items_lock:
            self.items[wid] = w
        with w.lock:
            surface = self.approvals.propose_plan(wid, plan)
            record["state"] = "waiting_approval"
            record["approvals"].append({"surface_id": surface.surface_id, "subject": "plan",
                                        "sha256": surface.bound["plan_sha256"]})
            w.save()
        return {"workflow_id": wid, "messages": surface.messages(), "view": w.view()}

    def _resolve_input(self, item: dict) -> dict:
        """The file a workflow reads, with its kind, name, path, SHA-256 and size, and the bytes to work from."""
        if "document_id" in item:
            s = self.documents.get(item["document_id"])
            if s.kind not in ("docx", "pptx"):
                raise OfficeError("BAD_REQUEST", "this document is already a PDF")
            return {"kind": s.kind, "name": s.name, "path": s.path, "sha256": s.sha256, "size": s.size,
                    "render_copy": s.render_copy, "grant_id": s.grant_id}
        if "workbook_id" in item:
            s = self.workbook_lookup(item["workbook_id"])
            if s.engine != "local" or s.path is None:
                raise OfficeError("CAPABILITY_PLANNED", "Save as PDF works for workbooks saved on this PC.", 409)
            from .draft import LIVE
            # A1 review A1-M2: the PDF is made from the file on disk only; any change not yet saved blocks it.
            if any(ch["state"] in LIVE for ch in s.draft.changes):
                raise OfficeError("UNSAVED_CHANGES", "", 409)
            data = Path(s.path).read_bytes()
            sha = hashlib.sha256(data).hexdigest()
            if sha != s.open_sha:
                raise OfficeError("INPUT_CHANGED", "the workbook changed on disk; reload it first", 409)
            return {"kind": "xlsx", "name": Path(s.path).name, "path": Path(s.path), "sha256": sha,
                    "size": len(data), "grant_id": s.grant_id}
        raise OfficeError("BAD_REQUEST", "input")

    # ---- approvals ---------------------------------------------------------------------------------------------
    def apply(self, body: dict) -> dict:
        """Called by Office._apply for plan and output subjects, inside the approvals lock (the workflow lock is
        already held by Office.action). Never runs the work itself."""
        w = self.get(body["workflow_id"])
        if body["target"]["kind"] == "plan":
            if w.record["state"] != "waiting_approval" or body["plan"] != w.private.get("plan"):
                raise OfficeError("STALE_PLAN", "", 409)
            w.record["state"] = "running"
            w.record["plan_approved"] = True
            w.save()
            self._q.put(w.id)
            return {"workflow_id": w.id, "state": "running"}
        if body["target"]["kind"] == "output_files":
            return self._write_output(w, body)
        raise OfficeError("BAD_REQUEST", "subject")

    def declined(self, wid: str, subject_kind: str):
        w = self.items.get(wid)
        if w is None:
            return
        with w.lock:
            if subject_kind == "plan" and w.record["state"] == "waiting_approval":
                w.record["state"] = "discarded"
                w.save()
                self._clean_work_files(w)

    # ---- run -------------------------------------------------------------------------------------------------------
    def _runner(self):
        while True:
            wid = self._q.get()
            w = self.items.get(wid)
            if w is None:
                continue
            try:
                self._run_save_as_pdf(w)
            except Exception as e:  # noqa: BLE001 - recorded on the workflow, never raised out of the runner
                with w.lock:
                    if w.record["state"] == "running":
                        w.record["state"] = "failed"
                    code = e.code if isinstance(e, OfficeError) else "ENGINE_CRASHED"
                    w.record["errors"].append({"code": code, "step": self._current_step(w), "at": _now()})
                    w.save()

    def _current_step(self, w):
        for s in w.record["steps"]:
            if s["state"] == "running":
                return s["id"]
        return None

    def _begin(self, w, sid):
        if w.cancel.is_set():
            raise _Cancelled()
        with w.lock:
            st = w.step(sid)
            st.update(state="running", started_at=_now())
            w.save()
        return st

    def _end(self, w, sid, **extra):
        with w.lock:
            st = w.step(sid)
            st.update(state="done", ended_at=_now(), **extra)
            w.save()

    def _run_save_as_pdf(self, w: Workflow):
        inp = w.record["inputs"][0]
        kind = inp["kind"]
        try:
            # prepare: a sanitized working copy from the bytes whose hash was shown on the plan card
            self._begin(w, "prepare")
            if not w.private.get("grant_ids"):
                raise OfficeError("NO_GRANT", "", 403)
            for gid in w.private["grant_ids"]:
                self.grants.get(gid, "open")                 # the file must still be one the owner opened
            data = Path(inp["path"]).read_bytes()
            if hashlib.sha256(data).hexdigest() != inp["sha256"]:
                raise OfficeError("INPUT_CHANGED", "", 409)
            raw = w.folder / f"input.{kind}"
            raw.write_bytes(data)
            del data
            res = sanitize.make_render_copy(raw, w.folder, kind)
            raw.unlink()
            for check, sev, msg in res.findings():
                w.findings.add(check, "structural", sev, msg, file="source")
            self._end(w, "prepare", finding_ids=[f.id for f in w.findings.items])
            # convert
            st = self._begin(w, "convert")
            out = w.folder / (Path(inp["name"]).stem + ".pdf")
            try:
                r = self.hub.lo.submit(res.path, out, owner=w.id, priority=CONVERT).result(600)
            except OfficeError as e:
                if e.code == "CANCELLED" or w.cancel.is_set():
                    raise _Cancelled() from None
                raise
            except FutureTimeout:
                raise OfficeError("ENGINE_TIMEOUT", "", 503) from None
            self._end(w, "convert", engine_version=self.hub.lo.integrity.pin.get("version"),
                      seconds=r.get("seconds"))
            del st
            # validate
            self._begin(w, "validate")
            expected = None
            if kind == "pptx":
                from . import content
                expected = content.pptx_outline(res.path)[0]
            vf, facts = self.validator.check_output_pdf(out, kind=kind, work_dir=w.folder / "pages", source=res.path,
                                                        expected_pages=expected,
                                                        sources={inp["path"]: inp["sha256"]})
            before = len(w.findings.items)
            for f in vf.items:
                w.findings.add(f.check, f.kind, f.severity, f.message, file=f.file, page=f.page, weak=f.weak)
            self._end(w, "validate", finding_ids=[f.id for f in w.findings.items[before:]])
            # preview: the validator already drew every page at 440 px into pages/
            self._begin(w, "preview")
            self._end(w, "preview", engine_version="Windows.Data.Pdf")
            with w.lock:
                if w.cancel.is_set():
                    raise _Cancelled()
                w.private["output_path"] = out
                w.record["outputs"] = [{"name": out.name, "sha256": sha256(out), "pages": facts.get("pages"),
                                        "size": out.stat().st_size}]
                w.record["findings"] = w.findings.view()
                w.record["state"] = "needs_review" if w.findings.errors else "ready_to_save"
                w.save()
        except _Cancelled:
            with w.lock:
                w.record["state"] = "cancelled"
                for s in w.record["steps"]:
                    if s["state"] in ("pending", "running"):
                        s["state"] = "cancelled"
                w.save()
                self._clean_work_files(w)
        except OfficeError as e:
            with w.lock:
                cur = self._current_step(w)
                if cur:
                    w.step(cur).update(state="failed", ended_at=_now())
                w.record["state"] = "failed"
                w.record["errors"].append({"code": e.code, "step": cur, "at": _now()})
                w.save()
                self._clean_work_files(w)

    # ---- owner actions ---------------------------------------------------------------------------------------------
    def cancel(self, wid) -> dict:
        w = self.get(wid)
        with w.lock:
            st = w.record["state"]
            if st in TERMINAL:
                raise OfficeError("NOT_CANCELLABLE", "", 409)
            w.cancel.set()
            self.hub.lo.cancel_owner(w.id)
            if st in ("waiting_approval", "ready_to_save", "needs_review", "interrupted", "planned"):
                self.approvals.close_workbook(w.id)
                w.record["state"] = "cancelled"
                w.save()
                self._clean_work_files(w)
        return w.view()

    def accept_warnings(self, wid) -> dict:
        w = self.get(wid)
        with w.lock:
            if w.findings.errors:
                raise OfficeError("HAS_ERRORS", "", 409)
            if w.record["state"] != "ready_to_save":
                raise OfficeError("NOT_CANCELLABLE", "nothing to accept", 409)
            w.record["warnings_accepted"] = True
            w.save()
            self.approvals.audit("office.warnings_accepted", {"workflow_id": w.id,
                                                              "warnings": len(w.findings.warnings)})
        return w.view()

    def propose_save(self, wid, body) -> dict:
        w = self.get(wid)
        with w.lock:
            if w.record["state"] != "ready_to_save":
                raise OfficeError("HAS_ERRORS" if w.findings.errors else "NOT_CANCELLABLE", "", 409)
            if w.findings.warnings and not w.record["warnings_accepted"]:
                raise OfficeError("WARNINGS_NOT_ACCEPTED", "", 409)
            g = self.grants.grant_save_as(body.get("save_as_path"), kind="pdf")
            if os.path.lexists(g.path):
                self.grants.revoke(g.grant_id)
                raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
            old = w.private.get("dest_grant")
            if old:
                self.grants.revoke(old)
            w.private["dest_grant"] = g.grant_id
            out = w.record["outputs"]
            warnings = [{"id": f.id, "message": f.message} for f in w.findings.warnings]
            surface = self.approvals.propose_outputs(w.id, out, str(g.path), warnings, w.record["warnings_accepted"])
            w.record["approvals"].append({"surface_id": surface.surface_id, "subject": "output_files",
                                          "sha256": surface.bound["change_sha256"]})
            w.save()
        return {"messages": surface.messages()}

    def _write_output(self, w: Workflow, body: dict) -> dict:
        if w.record["state"] != "ready_to_save":
            raise OfficeError("STALE_CHANGE", "", 409)
        g = self.grants.get(w.private.get("dest_grant"), "save_as")
        if str(g.path) != body["target"]["destination"] or body["outputs"] != w.record["outputs"]:
            raise OfficeError("STALE_CHANGE", "", 409)
        if body["warnings_accepted"] != w.record["warnings_accepted"]:
            raise OfficeError("STALE_CHANGE", "", 409)
        out = w.private["output_path"]
        res = publish_copy(out, g.path, w.record["outputs"][0]["sha256"])
        inp = w.record["inputs"][0]
        if sha256(Path(inp["path"])) != inp["sha256"]:
            # The PDF was written from the shown bytes; the original changed meanwhile. Record it, do not hide it.
            w.record["errors"].append({"code": "INPUT_CHANGED", "step": "save", "at": _now()})
        w.record["state"] = "saved"
        w.record["saved"] = {"name": g.path.name}
        w.save()
        self.grants.revoke(g.grant_id)
        self._clean_work_files(w)
        return {"workflow_id": w.id, **res}

    def output_page(self, wid, n: int, width: int) -> Path:
        w = self.get(wid)
        out = w.private.get("output_path")
        if out is None or not Path(out).exists():
            raise OfficeError("PAGE_NOT_READY", "", 202)
        cache = w.folder / "pages"
        cache.mkdir(exist_ok=True)
        return self.hub.page_png(out, cache, n, width)

    # ---- start-up, resume, retention -----------------------------------------------------------------------------
    def _startup_scan(self):
        for folder in sorted(self.root.iterdir()) if self.root.exists() else []:
            f = folder / "workflow.json"
            if not f.is_file():
                continue
            try:
                record = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            w = Workflow(folder, record)
            st = record.get("state")
            if st != "running" and _now() - record.get("updated_at", 0) > RETENTION_SECONDS:
                shutil.rmtree(folder, ignore_errors=True)     # every abandoned or finished run, interrupted too
                continue
            self.approvals.close_workbook(record["workflow_id"])        # no card survives a restart
            if st in ("planned", "waiting_approval"):
                # Review round 1, finding 1: a plan the owner never approved is not resumable. It is discarded.
                record["state"] = "discarded"
                record["errors"].append({"code": "INTERRUPTED", "step": None, "at": _now()})
                w.save()
                self._clean_work_files(w)
            elif st in ("running", "ready_to_save", "needs_review"):
                done = [s["id"] for s in record["steps"] if s["state"] == "done"]
                record["interrupted_at_step"] = next((i + 1 for i, s in enumerate(record["steps"])
                                                      if s["state"] != "done"), len(record["steps"]))
                record["state"] = "interrupted"
                record["errors"].append({"code": "INTERRUPTED", "step": None, "at": _now(), "done": done})
                w.save()
            self.items[record["workflow_id"]] = w

    def resume(self, wid, body) -> dict:
        w = self.get(wid)
        with w.lock:
            if w.record["state"] != "interrupted":
                raise OfficeError("NOT_CANCELLABLE", "only an interrupted task can be resumed", 409)
            if not w.record.get("plan_approved"):
                # Only a run the owner approved can continue; anything else needs a new plan card.
                raise OfficeError("STALE_PLAN", "this task was never approved; start it again", 409)
            paths = body.get("inputs") or []
            if len(paths) != len(w.record["inputs"]):
                raise OfficeError("BAD_REQUEST", "re-confirm every input")
            for rec, item in zip(w.record["inputs"], paths):
                g = self.grants.grant_open(item.get("path"), kind=rec["kind"])
                if sha256(g.path) != rec["sha256"]:
                    w.record["state"] = "failed"
                    w.record["errors"].append({"code": "INPUT_CHANGED", "step": None, "at": _now()})
                    w.save()
                    self.grants.revoke(g.grant_id)
                    raise OfficeError("INPUT_CHANGED", "", 409)
                rec["path"] = str(g.path)
                w.private["grant_ids"] = [g.grant_id]
            for s in w.record["steps"]:
                if s["state"] != "done":
                    s.update(state="pending", started_at=None, ended_at=None)
            # Re-run from the first step: every O2 step is deterministic and cheap, and re-running keeps the output
            # bound to the re-confirmed input.
            for s in w.record["steps"]:
                s.update(state="pending")
            w.findings = Findings()
            w.record["state"] = "running"
            w.save()
            self._q.put(w.id)
        return w.view()

    def _clean_work_files(self, w: Workflow):
        for p in w.folder.iterdir():
            if p.name == "workflow.json":
                continue
            if p.is_dir() and not p.is_symlink():
                shutil.rmtree(p, ignore_errors=True)
            else:
                try:
                    p.unlink()
                except OSError:
                    pass


class _Cancelled(Exception):
    pass


class _HubText:
    def __init__(self, hub):
        self.hub = hub

    def request(self, op, **kw):
        return self.hub.text_request(op, **kw)


class _HubRaster:
    def __init__(self, hub):
        self.hub = hub

    def request(self, op, **kw):
        return self.hub.raster_request(op, **kw)
