"""Scheduler state: one SQLite file (WAL, synchronous=FULL), every write in a `BEGIN IMMEDIATE` transaction.

Tables
  job          one schedule owned by one principal; state PROPOSED -> ACTIVE <-> PAUSED -> CANCELLED
  occurrence   one due unit of work; UNIQUE(job_id, occurrence_key) is the duplicate-prevention invariant
  attempt      one harness execution for an occurrence (live or fixture, labelled)
  artifact     one produced file version (sha256-bound), chained by parent_artifact_id across refinements
  review       one owner action on one exact artifact version (bound to its sha256)
  event        append-only audit log, SHA-256 hash-chained (each row hashes the previous row's hash)
  calendar_snapshot  the calendar versions the scheduler reconciled against
"""
from __future__ import annotations

import contextlib
import hashlib
import json
import sqlite3
import threading
import time
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS job(
  job_id TEXT PRIMARY KEY, owner TEXT NOT NULL, title TEXT NOT NULL, template_id TEXT NOT NULL,
  params_json TEXT NOT NULL, schedule_json TEXT NOT NULL, timezone TEXT NOT NULL,
  authority_json TEXT NOT NULL, policy_json TEXT NOT NULL,
  state TEXT NOT NULL CHECK(state IN ('PROPOSED','ACTIVE','PAUSED','CANCELLED')),
  proposal_sha256 TEXT NOT NULL, confirmed_by TEXT, confirmed_at_us INTEGER,
  created_at_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS occurrence(
  occ_id INTEGER PRIMARY KEY AUTOINCREMENT, job_id TEXT NOT NULL REFERENCES job(job_id),
  occurrence_key TEXT NOT NULL, due_at_us INTEGER NOT NULL, deadline_us INTEGER,
  state TEXT NOT NULL, reason TEXT, attempts INTEGER NOT NULL DEFAULT 0, retry_at_us INTEGER,
  late INTEGER NOT NULL DEFAULT 0, meta_json TEXT NOT NULL DEFAULT '{}', request_json TEXT,
  lease_owner TEXT, lease_until_us INTEGER,
  created_at_us INTEGER NOT NULL, updated_at_us INTEGER NOT NULL,
  UNIQUE(job_id, occurrence_key));
CREATE INDEX IF NOT EXISTS occ_due ON occurrence(state, due_at_us);
CREATE TABLE IF NOT EXISTS attempt(
  attempt_id INTEGER PRIMARY KEY AUTOINCREMENT, occ_id INTEGER NOT NULL REFERENCES occurrence(occ_id),
  kind TEXT NOT NULL, mode TEXT NOT NULL CHECK(mode IN ('LIVE','FIXTURE')), harness TEXT NOT NULL,
  started_at_us INTEGER NOT NULL, ended_at_us INTEGER, outcome TEXT, reason TEXT,
  supervisor_task_id TEXT UNIQUE, receipt_json TEXT);
CREATE TABLE IF NOT EXISTS artifact(
  artifact_id INTEGER PRIMARY KEY AUTOINCREMENT, occ_id INTEGER NOT NULL REFERENCES occurrence(occ_id),
  attempt_id INTEGER NOT NULL REFERENCES attempt(attempt_id), version INTEGER NOT NULL,
  parent_artifact_id INTEGER REFERENCES artifact(artifact_id), kind TEXT NOT NULL, path TEXT NOT NULL,
  sha256 TEXT NOT NULL, bytes INTEGER NOT NULL, info_json TEXT NOT NULL, concept TEXT NOT NULL DEFAULT '',
  status TEXT NOT NULL CHECK(status IN ('CANDIDATE','APPROVED','REJECTED','SUPERSEDED')),
  created_at_us INTEGER NOT NULL, UNIQUE(occ_id, version));
CREATE TABLE IF NOT EXISTS review(
  review_id INTEGER PRIMARY KEY AUTOINCREMENT, artifact_id INTEGER NOT NULL REFERENCES artifact(artifact_id),
  principal TEXT NOT NULL, action TEXT NOT NULL CHECK(action IN ('approve','refine','regenerate','reject')),
  instruction TEXT, artifact_sha256 TEXT NOT NULL, at_us INTEGER NOT NULL);
CREATE TABLE IF NOT EXISTS event(
  seq INTEGER PRIMARY KEY AUTOINCREMENT, at_us INTEGER NOT NULL, kind TEXT NOT NULL, job_id TEXT, occ_id INTEGER,
  payload_json TEXT NOT NULL, prev_hash TEXT NOT NULL, hash TEXT NOT NULL);
CREATE TRIGGER IF NOT EXISTS event_no_update BEFORE UPDATE ON event BEGIN SELECT RAISE(ABORT,'EVENT_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS event_no_delete BEFORE DELETE ON event BEGIN SELECT RAISE(ABORT,'EVENT_APPEND_ONLY'); END;
CREATE TRIGGER IF NOT EXISTS review_no_update BEFORE UPDATE ON review BEGIN SELECT RAISE(ABORT,'REVIEW_APPEND_ONLY'); END;
CREATE TABLE IF NOT EXISTS calendar_snapshot(
  calendar_id TEXT NOT NULL, version TEXT NOT NULL, digest TEXT NOT NULL, data_json TEXT NOT NULL,
  recorded_at_us INTEGER NOT NULL, PRIMARY KEY(calendar_id, digest));
"""

GENESIS = "0" * 64


def jdump(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False, default=str)


def now_us() -> int:
    return int(time.time() * 1_000_000)


class Store:
    def __init__(self, path, now_fn=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.now_fn = now_fn or now_us
        self._lock = threading.RLock()
        self.db = sqlite3.connect(str(self.path), isolation_level=None, check_same_thread=False, timeout=10)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")
        self.db.execute("PRAGMA foreign_keys=ON")
        self.db.executescript(SCHEMA)
        with self.tx() as db:
            if db.execute("SELECT 1 FROM meta WHERE key='schema_version'").fetchone() is None:
                db.execute("INSERT INTO meta(key,value) VALUES ('schema_version','1')")

    def close(self):
        with contextlib.suppress(sqlite3.Error):
            self.db.close()

    def now(self) -> int:
        return int(self.now_fn())

    @contextlib.contextmanager
    def tx(self):
        with self._lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                yield self.db
            except BaseException:
                self.db.execute("ROLLBACK")
                raise
            else:
                self.db.execute("COMMIT")

    def q(self, sql, args=()):
        with self._lock:
            return self.db.execute(sql, args).fetchall()

    def q1(self, sql, args=()):
        with self._lock:
            return self.db.execute(sql, args).fetchone()

    # ---- audit ---------------------------------------------------------------------------------
    def emit(self, db, kind, *, job_id=None, occ_id=None, payload=None):
        """Append one hash-chained event inside the caller's transaction."""
        prev = db.execute("SELECT hash FROM event ORDER BY seq DESC LIMIT 1").fetchone()
        prev_hash = prev[0] if prev else GENESIS
        at = self.now()
        body = jdump({"at_us": at, "kind": kind, "job_id": job_id, "occ_id": occ_id, "payload": payload or {},
                      "prev": prev_hash})
        h = hashlib.sha256(body.encode()).hexdigest()
        db.execute("INSERT INTO event(at_us,kind,job_id,occ_id,payload_json,prev_hash,hash) VALUES (?,?,?,?,?,?,?)",
                   (at, kind, job_id, occ_id, jdump(payload or {}), prev_hash, h))
        return h

    def verify_chain(self) -> dict:
        prev = GENESIS
        n = 0
        for r in self.q("SELECT * FROM event ORDER BY seq"):
            body = jdump({"at_us": r["at_us"], "kind": r["kind"], "job_id": r["job_id"], "occ_id": r["occ_id"],
                          "payload": json.loads(r["payload_json"]), "prev": prev})
            if r["prev_hash"] != prev or hashlib.sha256(body.encode()).hexdigest() != r["hash"]:
                return {"ok": False, "broken_at": r["seq"], "checked": n}
            prev = r["hash"]
            n += 1
        return {"ok": True, "checked": n, "head": prev}

    def events(self, job_id=None, occ_id=None, limit=500):
        sql, args = "SELECT * FROM event", []
        if occ_id is not None:
            sql += " WHERE occ_id=?"
            args.append(occ_id)
        elif job_id is not None:
            sql += " WHERE job_id=?"
            args.append(job_id)
        sql += " ORDER BY seq DESC LIMIT ?"
        args.append(limit)
        return [dict(r) | {"payload": json.loads(r["payload_json"])} for r in self.q(sql, args)]
