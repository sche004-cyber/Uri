"""Worker commands for W1, served by the integrated worker next to the OI commands (same framed stdio).

Commands (exact key sets, like `worker_bridge.COMMANDS`):
  web_providers        {}                                   -> provider availability (names and status only)
  web_research         {query, urls, feeds, use_brain}      -> {"job_id"}; runs in the background
  web_research_status  {job_id}                             -> state, progress, and the result when finished
  web_research_cancel  {job_id}                             -> cooperative cancel

At most ONE research job runs at a time (bounded background work; it never competes with itself for the single
Brain slot). Events use the envelope of `uri.oi.event.v1` under the schema `uri.assist.event.v1`; `turn_id` is the
job id. The OI event registry is not changed: existing UI code ignores unknown schemas/types.
"""
from __future__ import annotations

import itertools
import threading
import time
from typing import Callable, Optional

from . import pipeline as P
from . import search as S
from .safe_fetch import SafeFetcher
from .surface import build_surface

SCHEMA = "uri.assist.event.v1"
EVENT_TYPES = ("research.started", "research.progress", "research.finished")
COMMANDS = {
    "web_providers": ({"command"},),
    "web_research": ({"command", "query", "urls", "feeds", "use_brain"},),
    "web_research_status": ({"command", "job_id"},),
    "web_research_cancel": ({"command", "job_id"},),
}
OPEN_WHILE_BUSY = {"web_providers", "web_research_status", "web_research_cancel"}
MAX_QUERY = 400
MAX_URLS = 5
MAX_FEEDS = 3
KEEP_RESULTS = 8


class Refused(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Emitter:
    def __init__(self, write: Callable[[dict], None]):
        self._write, self._seq, self._lock = write, itertools.count(1), threading.Lock()

    def emit(self, job_id, type_, **data):
        if type_ not in EVENT_TYPES and not type_.startswith("assist."):
            raise ValueError("UNKNOWN_EVENT_TYPE:" + type_)
        with self._lock:
            ev = {"schema": SCHEMA, "seq": next(self._seq), "t": round(time.time(), 3), "turn_id": job_id,
                  "type": type_, "data": data}
        try:
            self._write(ev)
        except Exception:
            pass
        return ev


def valid(kind, command) -> bool:
    return kind in COMMANDS and isinstance(command, dict) and any(set(command) == s for s in COMMANDS[kind])


def _str_list(v, limit, item_max=2048):
    if not isinstance(v, list) or len(v) > limit or not all(isinstance(x, str) and 0 < len(x) <= item_max for x in v):
        raise Refused("ARGUMENT_INVALID")
    return list(v)


class WebResearch:
    def __init__(self, *, write_event: Callable[[dict], None], fetcher_factory: Callable[[], SafeFetcher] = SafeFetcher,
                 providers_factory: Callable[[], list] = S.default_providers,
                 brain_complete: Optional[Callable] = None, brain_idle: Optional[Callable[[], bool]] = None,
                 defer_start: bool = False):
        """brain_complete(messages) -> (status, text): the resident Brain, or None. brain_idle() -> bool: True when
        no user turn holds the Brain; research never takes the single slot from the user."""
        self.emitter = Emitter(write_event)
        self._fetcher_factory, self._providers_factory = fetcher_factory, providers_factory
        self._complete, self._brain_idle = brain_complete, brain_idle or (lambda: True)
        self._lock = threading.Lock()
        self._job = None             # (job, thread)
        self._results = {}           # job_id -> result dict (bounded)
        self._progress = {}
        # defer_start: a started job waits for release(), which the worker calls right AFTER it wrote the reply
        # carrying the job id, so no event of a job can precede that reply (interim review F1; same rule as OI).
        self._defer = defer_start
        self._go = None

    @property
    def busy(self):
        with self._lock:
            return self._job is not None and self._job[1].is_alive()

    def handle(self, kind, command):
        if not valid(kind, command):
            raise Refused("COMMAND_SCHEMA")
        if kind not in OPEN_WHILE_BUSY and self.busy:
            raise Refused("RESEARCH_IN_PROGRESS")
        return getattr(self, "_" + kind)(command)

    def _web_providers(self, _c):
        return {"providers": [{"provider": p.name, "available": p.available()} for p in self._providers_factory()],
                "brain_synthesis": self._complete is not None}

    def _guarded_complete(self):
        if self._complete is None:
            return None

        def complete(messages, *, cancel=None, timeout_s=None):
            if not self._brain_idle() or (cancel is not None and cancel.cancelled):
                return "BRAIN_BUSY", ""        # yield to the user's own turn; the extractive answer is used
            return P.call_brain(self._complete, messages, cancel=cancel, timeout_s=timeout_s)
        return complete

    def cancel_brain_work(self, reason: str = "user_turn"):
        """R1-05: a user turn needs the single Brain slot. A running research job's Brain call is stopped (or not
        started); the job finishes with its extractive answer."""
        with self._lock:
            job = self._job
        if job is not None and job[1].is_alive():
            job[0].yield_brain()

    def _web_research(self, c):
        q = c["query"]
        if not isinstance(q, str) or len(q) > MAX_QUERY:
            raise Refused("ARGUMENT_INVALID")
        urls, feeds = _str_list(c["urls"], MAX_URLS), _str_list(c["feeds"], MAX_FEEDS)
        if not isinstance(c["use_brain"], bool):
            raise Refused("ARGUMENT_INVALID")
        if not q.strip() and not urls and not feeds:
            raise Refused("EMPTY_REQUEST")
        req = P.ResearchRequest(query=q, urls=urls, feeds=feeds, use_brain=bool(c["use_brain"]))
        job = P.ResearchJob(req, fetcher=self._fetcher_factory(), providers=self._providers_factory(),
                            complete=self._guarded_complete(), progress=self._on_progress)
        self._progress[job.job_id] = {"stage": "queued"}

        def run():
            self.emitter.emit(job.job_id, "research.started", query=req.query[:400], urls=len(urls), feeds=len(feeds))
            result = job.run().to_dict()
            surface = None
            try:
                surface = build_surface(result)
                messages, digest = surface.messages(), surface.digest
            except Exception:
                messages, digest = None, None
            with self._lock:
                self._results[job.job_id] = {"result": result, "a2ui": messages, "surface_digest": digest}
                while len(self._results) > KEEP_RESULTS:
                    self._results.pop(next(iter(self._results)))
            self.emitter.emit(job.job_id, "research.finished", status=result["status"],
                              sources=len(result["sources"]), answer_sentences=len(result["answer"]),
                              a2ui=messages, surface_digest=digest)
        go = threading.Event()
        if not self._defer:
            go.set()

        def gated():
            go.wait()
            run()
        t = threading.Thread(target=gated, name="web-research-" + job.job_id[:8], daemon=True)
        with self._lock:
            self._job = (job, t)
            self._go = go
            for old in [k for k in self._progress if k != job.job_id and k not in self._results][:-KEEP_RESULTS or None]:
                self._progress.pop(old, None)
            while len(self._progress) > 2 * KEEP_RESULTS:
                self._progress.pop(next(iter(self._progress)))
        t.start()
        return {"job_id": job.job_id}

    def _on_progress(self, *, job_id, stage, **kw):
        self._progress[job_id] = {"stage": stage, **{k: v for k, v in kw.items() if isinstance(v, (int, float, str))}}
        self.emitter.emit(job_id, "research.progress", stage=stage,
                          **{k: v for k, v in kw.items() if isinstance(v, (int, float, str, list))})

    def _web_research_status(self, c):
        jid = c["job_id"]
        with self._lock:
            done = self._results.get(jid)
            running = self._job is not None and self._job[0].job_id == jid and self._job[1].is_alive()
        if done is not None:
            return {"state": "FINISHED", **done}
        if running:
            return {"state": "RUNNING", "progress": self._progress.get(jid)}
        raise Refused("JOB_UNKNOWN")

    def _web_research_cancel(self, c):
        with self._lock:
            job = self._job
        if job is None or job[0].job_id != c["job_id"] or not job[1].is_alive():
            raise Refused("JOB_NOT_RUNNING")
        job[0].cancel()
        return {"state": "CANCELLING"}

    def release(self):
        """Let a deferred job run (the worker calls this after writing the reply)."""
        go = self._go
        if go is not None:
            go.set()

    def wait(self, timeout=None):
        job = self._job
        if job is not None:
            job[1].join(timeout)

    def close(self):
        job = self._job
        if job is not None and job[1].is_alive():
            job[0].cancel()
            self.release()
            job[1].join(5.0)
