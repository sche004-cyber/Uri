"""Durable SQLite ledger: connection discipline, transactions, events, and the checked state transition.

Durability: WAL + `synchronous=FULL` on every connection (SQLite WAL docs: with FULL the WAL is
synced on each commit, so a committed transaction survives power loss; `synchronous=NORMAL` can
lose the most recent commits in WAL mode). Every authoritative write is its own `BEGIN IMMEDIATE`
transaction, so the writer lock is taken up front and busy contention surfaces as a typed error,
never as a half-applied multi-step change.
"""
from __future__ import annotations

import contextlib
import json
import sqlite3
import threading
import uuid
from pathlib import Path

from . import SCHEMA_VERSION
from .clock import Clock
from .schema import SQL, TRANSITIONS, append_only_sql


class LedgerError(Exception):
    code = "LEDGER_ERROR"

    def __init__(self, code=None, detail=None):
        self.code = code or self.code
        self.detail = detail
        super().__init__(self.code if detail is None else f"{self.code}: {detail}")


class LedgerRefused(LedgerError):
    """A mechanical invariant (trigger/constraint) refused the write. `code` is the invariant name."""


class LedgerBusy(LedgerError):
    code = "LEDGER_BUSY"


class LedgerWriteFailed(LedgerError):
    """Durable write could not be made (e.g. disk full). Nothing downstream may proceed."""
    code = "LEDGER_WRITE_FAILED"


def jdump(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


class Ledger:
    def __init__(self, path, clock: Clock | None = None, busy_timeout_ms: int = 5000):
        self.path = str(path)
        self.clock = clock or Clock()
        self._busy_ms = busy_timeout_ms
        self._lock = threading.RLock()
        self._depth = 0
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path, timeout=busy_timeout_ms / 1000, isolation_level=None,
                                   check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._pragmas()
        self._migrate()

    # ---- connection ----------------------------------------------------------------------
    def _pragmas(self):
        db = self._db
        db.execute(f"PRAGMA busy_timeout={int(self._busy_ms)}")
        mode = db.execute("PRAGMA journal_mode=WAL").fetchone()[0]
        db.execute("PRAGMA synchronous=FULL")
        db.execute("PRAGMA foreign_keys=ON")
        rep = self.durability_report()
        if rep["journal_mode"] != "wal" or rep["synchronous"] != "FULL":
            raise LedgerError("DURABILITY_NOT_ESTABLISHED", jdump(rep))

    def durability_report(self):
        db = self._db
        sync = {0: "OFF", 1: "NORMAL", 2: "FULL", 3: "EXTRA"}[db.execute("PRAGMA synchronous").fetchone()[0]]
        return {"journal_mode": db.execute("PRAGMA journal_mode").fetchone()[0].lower(), "synchronous": sync,
                "foreign_keys": bool(db.execute("PRAGMA foreign_keys").fetchone()[0]),
                "sqlite_version": sqlite3.sqlite_version}

    def _migrate(self):
        with self._lock:
            ver = self._db.execute("PRAGMA user_version").fetchone()[0]
            if ver == SCHEMA_VERSION:
                return
            if ver != 0:
                raise LedgerError("SCHEMA_VERSION_UNSUPPORTED", str(ver))
            with self.tx() as db:
                for stmt in _split(SQL + "\n" + append_only_sql()):
                    db.execute(stmt)
                db.executemany("INSERT INTO allowed_transition VALUES (?,?,?)", TRANSITIONS)
                db.executemany("INSERT INTO meta VALUES (?,?)", [
                    ("ledger_id", uuid.uuid4().hex), ("admission_round", "0"), ("aging_interval", "5"),
                    ("schema_created_us", str(self.clock.wall_us()))])
                db.execute(f"PRAGMA user_version={SCHEMA_VERSION}")

    def close(self):
        with self._lock:
            self._db.close()

    # ---- transactions --------------------------------------------------------------------
    @contextlib.contextmanager
    def tx(self):
        """Serialised writer transaction. Re-entrant: nested use joins the outer transaction."""
        with self._lock:
            if self._depth:
                self._depth += 1
                try:
                    yield self._db
                finally:
                    self._depth -= 1
                return
            try:
                self._db.execute("BEGIN IMMEDIATE")
            except sqlite3.OperationalError as e:
                raise self._map(e) from None
            self._depth = 1
            try:
                yield self._db
                self._db.execute("COMMIT")
            except BaseException as e:
                with contextlib.suppress(sqlite3.Error):
                    self._db.execute("ROLLBACK")
                if isinstance(e, sqlite3.Error):
                    raise self._map(e) from None
                raise
            finally:
                self._depth = 0

    @staticmethod
    def _map(e: sqlite3.Error):
        msg = str(e)
        if isinstance(e, sqlite3.IntegrityError):
            return LedgerRefused(msg) if " " not in msg else LedgerRefused("CONSTRAINT", msg)
        if "locked" in msg or "busy" in msg:
            return LedgerBusy(detail=msg)
        if "full" in msg.lower() or "disk" in msg.lower() or "readonly" in msg.lower() or "I/O" in msg:
            return LedgerWriteFailed(detail=msg)
        return LedgerError("SQLITE_ERROR", msg)

    def q(self, sql, args=()):
        with self._lock:
            try:
                return self._db.execute(sql, args).fetchall()
            except sqlite3.Error as e:
                raise self._map(e) from None

    def q1(self, sql, args=()):
        rows = self.q(sql, args)
        return rows[0] if rows else None

    # ---- primitives ----------------------------------------------------------------------
    def now_us(self):
        return self.clock.wall_us()

    def authority_now_us(self) -> int:
        """Wall time for VALIDITY decisions (grants, provider reset times). Never runs backwards: a clock step
        back cannot revive an expired authorization. Persisted high-water mark; forward jumps are accepted."""
        with self.tx() as db:
            row = db.execute("SELECT value FROM meta WHERE key='wall_hwm'").fetchone()
            hwm = int(row[0]) if row else 0
            now = max(self.clock.wall_us(), hwm)
            if now != hwm:
                db.execute("INSERT INTO meta(key,value) VALUES('wall_hwm',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value", (str(now),))
            return now

    @contextlib.contextmanager
    def read_tx(self):
        """Consistent read snapshot (WAL): watermark and rows come from the same point in the ledger."""
        with self._lock:
            if self._depth:
                yield
                return
            self._db.execute("BEGIN")
            try:
                yield
            finally:
                with contextlib.suppress(sqlite3.Error):
                    self._db.execute("COMMIT")

    def meta(self, key, default=None):
        row = self.q1("SELECT value FROM meta WHERE key=?", (key,))
        return row[0] if row else default

    def ledger_id(self):
        return self.meta("ledger_id")

    def watermark(self) -> int:
        return self.q1("SELECT COALESCE(MAX(seq),0) FROM event")[0]

    def current_epoch(self) -> int:
        return self.q1("SELECT COALESCE(MAX(epoch),0) FROM scheduler_epoch")[0]

    def begin_epoch(self, owner_pid=None, owner_create_time=None) -> tuple[int, str]:
        """Start a new scheduler epoch. Monotonic lease values are meaningful only inside it."""
        iid = uuid.uuid4().hex
        with self.tx() as db:
            cur = db.execute("INSERT INTO scheduler_epoch(instance_id,started_at_us,owner_pid,owner_create_time) VALUES (?,?,?,?)",
                             (iid, self.now_us(), owner_pid, owner_create_time))
            epoch = cur.lastrowid
            self.emit("epoch.begin", payload={"epoch": epoch, "instance_id": iid}, ref=("scheduler_epoch", epoch))
        return epoch, iid

    def epoch_instance(self, epoch):
        row = self.q1("SELECT instance_id FROM scheduler_epoch WHERE epoch=?", (epoch,))
        return row[0] if row else None

    def emit(self, kind, task_id=None, attempt_id=None, ref=None, payload=None, occurred_at_us=None):
        """Append an immutable ledger event. Must be called inside tx()."""
        now = self.now_us()
        cur = self._db.execute(
            "INSERT INTO event(kind,task_id,attempt_id,occurred_at_us,recorded_at_us,ref_table,ref_id,payload) VALUES (?,?,?,?,?,?,?,?)",
            (kind, task_id, attempt_id, occurred_at_us if occurred_at_us is not None else now, now,
             ref[0] if ref else None, ref[1] if ref else None, jdump(payload) if payload is not None else None))
        return cur.lastrowid

    def transition(self, task_id, to_state, reason_code, reason_detail=None, *, basis=None, completion_ref=None,
                   attempt_id=None, set_fence="keep", extra=None):
        """Checked task state change. All legality is also enforced by triggers.

        basis = ("evidence"|"user_decision", id) for exits from UNCERTAIN/NEEDS_USER.
        """
        with self.tx() as db:
            row = db.execute("SELECT state,current_fence FROM task WHERE task_id=?", (task_id,)).fetchone()
            if row is None:
                raise LedgerError("UNKNOWN_TASK", task_id)
            old = row["state"]
            unresolved = ("UNCERTAIN", "NEEDS_USER")
            keep_hwm = old in unresolved and to_state in unresolved     # escalation must not reset the 'new evidence' watermark
            sets = {"state": to_state, "reason_code": reason_code, "reason_detail": reason_detail,
                    "state_changed_at_us": self.now_us(),
                    "basis_kind": basis[0] if basis else None, "basis_ref": basis[1] if basis else None,
                    "completion_ref": completion_ref,
                    }
            if not keep_hwm:
                sets["enter_evidence_hwm"] = db.execute("SELECT COALESCE(MAX(evidence_id),0) FROM evidence").fetchone()[0]
                sets["enter_decision_hwm"] = db.execute("SELECT COALESCE(MAX(decision_id),0) FROM user_decision").fetchone()[0]
            if set_fence != "keep":
                sets["current_fence"] = set_fence
            sets.update(extra or {})
            cols = ", ".join(f"{k}=?" for k in sets)
            try:
                db.execute(f"UPDATE task SET {cols} WHERE task_id=?", (*sets.values(), task_id))
            except sqlite3.IntegrityError as e:
                raise LedgerRefused(str(e)) from None
            self.emit("task.state", task_id, attempt_id, ref=("task", db.execute(
                "SELECT task_seq FROM task WHERE task_id=?", (task_id,)).fetchone()[0]),
                payload={"from": old, "to": to_state, "reason": reason_code})
        return old

    def task(self, task_id):
        return self.q1("SELECT * FROM task WHERE task_id=?", (task_id,))

    def attempt(self, attempt_id):
        return self.q1("SELECT * FROM attempt WHERE attempt_id=?", (attempt_id,))

    def cite_exists(self, table, row_id, task_id=None):
        if table not in {"evidence", "stream_event", "recovery_decision", "event", "completion_record", "effect_intent",
                         "uncertainty", "effect_observation", "user_decision", "postcondition_result"}:
            return False
        key = {"event": "seq"}.get(table, table + "_id") if table != "effect_observation" else "obs_id"
        if table == "postcondition_result":
            key = "result_id"
        row = self.q1(f"SELECT * FROM {table} WHERE {key}=?", (row_id,))
        if row is None:
            return False
        if task_id is not None and "task_id" in row.keys() and row["task_id"] != task_id:
            return False
        return True


def _split(script: str):
    """Split a script into statements; trigger bodies contain ';' so use sqlite3.complete_statement."""
    buf, out = "", []
    for line in script.splitlines():
        buf += line + "\n"
        if sqlite3.complete_statement(buf):
            if buf.strip():
                out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out
