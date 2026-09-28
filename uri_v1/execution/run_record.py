"""Append-only, hash-chained execution run lineage (URI-owned; not Memory).

A run record says what URI gave an executor, what URI observed afterwards and
what URI's verifier concluded. Executor claims are stored as claims. Harness
session ids and transcripts never enter M36 Memory; they may appear here only
as opaque handles and hashes.
"""
from __future__ import annotations

from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import threading

from uri_v1.user_storage import user_scoped_path

RUN_SCHEMA_VERSION = "m37.run-record.v1"
_EVENTS = frozenset({"RUN_STARTED", "RUN_RESULT", "VERIFICATION", "WRITEBACK", "RUN_ABORTED"})
_EXECUTORS = frozenset({"LOCAL_EDGE", "HARNESS"})
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
_GENESIS = "0" * 64
_lock = threading.RLock()


class RunRecordError(ValueError):
    pass


@contextmanager
def _exclusive(path: Path):
    """Process-exclusive append lock on a sidecar file.

    Deliberately not `uri_v1.user_storage.locked_append`: its module-global,
    non-reentrant thread lock is already held by M36 `MemoryLog.guard()` while a
    registered verifier runs, and the verifier appends here.
    """
    with _lock, open(str(path) + ".lock", "a+b") as lock:
        if os.name == "nt":
            import msvcrt
            lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        try:
            with open(path, "ab") as stream:
                yield stream
        finally:
            if os.name == "nt":
                lock.seek(0); msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(lock.fileno(), fcntl.LOCK_UN)


def _canonical(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


class RunStore:
    def __init__(self, user_id: str, root) -> None:
        self.user_id = user_id
        self.path = Path(user_scoped_path(user_id, os.path.join("execution", "runs.jsonl"), str(Path(root).resolve())))

    def _lines(self):
        if not self.path.exists(): return []
        out, prev = [], _GENESIS
        for n, line in enumerate(self.path.read_bytes().splitlines()):
            try: entry = json.loads(line)
            except ValueError: raise RunRecordError(f"RUN_LOG_CORRUPT:{n}")
            body = {k: v for k, v in entry.items() if k != "digest"}
            if body.get("prev") != prev or hashlib.sha256(_canonical(body)).hexdigest() != entry.get("digest"):
                raise RunRecordError(f"RUN_LOG_CHAIN_BROKEN:{n}")
            prev = entry["digest"]; out.append(entry)
        return out

    def append(self, run_id: str, event: str, data: dict) -> dict:
        if not _RUN_ID.fullmatch(run_id or ""): raise RunRecordError("INVALID_RUN_ID")
        if event not in _EVENTS: raise RunRecordError("UNKNOWN_EVENT")
        if event == "RUN_STARTED" and data.get("executor") not in _EXECUTORS: raise RunRecordError("UNKNOWN_EXECUTOR")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with _exclusive(self.path) as stream:
            lines = self._lines()
            if event == "RUN_STARTED" and any(e["run_id"] == run_id for e in lines): raise RunRecordError("RUN_EXISTS")
            if event != "RUN_STARTED" and not any(e["run_id"] == run_id and e["event"] == "RUN_STARTED" for e in lines):
                raise RunRecordError("RUN_UNKNOWN")
            body = {"schema_version": RUN_SCHEMA_VERSION, "user_id": self.user_id, "run_id": run_id, "event": event,
                    "seq": len(lines), "prev": lines[-1]["digest"] if lines else _GENESIS, "data": data}
            entry = dict(body, digest=hashlib.sha256(_canonical(body)).hexdigest())
            stream.write(_canonical(entry) + b"\n")
            stream.flush(); os.fsync(stream.fileno())
        return entry

    def get(self, run_id: str) -> dict | None:
        events = [e for e in self._lines() if e["run_id"] == run_id]
        if not events: return None
        run = {"run_id": run_id, "events": [e["event"] for e in events], "verifications": [], "writebacks": []}
        for e in events:
            if e["event"] == "RUN_STARTED": run["started"] = e["data"]
            elif e["event"] == "RUN_RESULT": run["result"] = e["data"]
            elif e["event"] == "VERIFICATION": run["verifications"].append(e["data"])
            elif e["event"] == "WRITEBACK": run["writebacks"].append(e["data"])
            elif e["event"] == "RUN_ABORTED": run["aborted"] = e["data"]
        return run
