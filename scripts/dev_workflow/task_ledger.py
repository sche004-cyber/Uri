"""Lifecycle V3.1 persistent task ledger: task identity, context continuity, checkpoints, leases and recovery.

One SQLite file outside every worktree (``URI_TASK_LEDGER``, default ``~/.uri-dev/task_ledger.sqlite3``) holds every
development task. Each task has a stable id, an append-only hash-chained event log (same hash rule as the V3 driver's
``events.jsonl``) and projections (status, context items, findings, steps, reviews) written in the same transaction
as the event that causes them. Lifecycle V3 runs are linked and imported read-only; the V3 driver is unchanged.

    python -m scripts.dev_workflow.task_ledger <command> ... --actor kind:id     (``--help`` lists commands)

Ownership: the ledger owns task execution state. The Milestone Manager owns milestones, roadmap, dependencies and
owner decisions; the ledger keeps only an opaque ``milestone_ref`` (contract: docs/dev_workflow/contracts/
task_ledger_contract.json).

Trust boundary: actor identity is declared by the caller and enforced as declared (as V3's coordinator identity is);
review verdicts are never caller claims - they are recomputed from the stored reviewer output. The event chain is
tamper-evident, not tamper-proof.

Boundary Guarantee: Development tooling only. Not part of the URI runtime.
"""
from __future__ import annotations

import argparse
import contextlib
import datetime
import hashlib
import json
import os
import re
import secrets
import sqlite3
import subprocess
import sys
import time
from pathlib import Path

SCHEMA_VERSION = 1
GENESIS = "0" * 64
# Same hardening as the V3 driver's git calls (lifecycle.GIT): repository hooks, replace refs and fsmonitor ignored.
GIT = ["git", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]
GIT_ENV = {**os.environ, "GIT_NO_REPLACE_OBJECTS": "1"}

STATUSES = ("OPEN", "IN_PROGRESS", "IN_REVIEW", "REPAIR", "ACCEPTED", "INTEGRATED", "INTERRUPTED", "PAUSED",
            "BLOCKED", "ABANDONED")
ACTIVE = {"IN_PROGRESS", "IN_REVIEW", "REPAIR"}
TERMINAL = {"INTEGRATED", "ABANDONED"}
# Ordinary transitions. ACCEPTED and INTEGRATED are entered only through accept() / mark_integrated(); INTERRUPTED,
# PAUSED and BLOCKED from any non-terminal status, and left only through resume() / unblock().
TRANSITIONS = {
    "OPEN": {"IN_PROGRESS", "ABANDONED"},
    "IN_PROGRESS": {"IN_REVIEW", "ABANDONED"},
    "IN_REVIEW": {"REPAIR", "IN_PROGRESS", "ABANDONED"},
    "REPAIR": {"IN_REVIEW", "ABANDONED"},
    "ACCEPTED": {"IN_REVIEW", "REPAIR", "ABANDONED"},
    "INTERRUPTED": {"ABANDONED"},
    "PAUSED": set(),
    "BLOCKED": {"ABANDONED"},
    "INTEGRATED": set(),
    "ABANDONED": set(),
}

DEVELOPERS = {"claude", "codex"}                          # may execute development work
REVIEWERS = {"codex", "claude_cli", "subagent", "session"}  # may record an independent review
ACTOR_KINDS = DEVELOPERS | REVIEWERS | {"owner", "antigravity", "system"}
EVIDENCE_WRITERS = DEVELOPERS | {"owner", "antigravity"}   # may preserve notes/evidence, also while paused

CONTEXT_KINDS = ("objective", "requirement", "constraint", "decision", "progress", "evidence", "commit", "test",
                 "issue", "next_action", "todo", "done", "permission", "note")
# Retrieval order; evidence/note are ranked by the query and fill what budget is left.
PACKET_ORDER = ("objective", "requirement", "constraint", "decision", "permission", "issue", "next_action", "todo",
                "commit", "test", "progress", "done", "evidence", "note")
PACKET_LATEST = {"test": 3, "progress": 5, "commit": 5, "done": 10}

VERDICTS = ("ACCEPT", "ACCEPT WITH FINDINGS", "REJECT")


class LedgerError(Exception):
    pass


class Refused(LedgerError):
    """A rule refused the operation; nothing was written."""


def now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha256(b: bytes | str) -> str:
    return hashlib.sha256(b.encode() if isinstance(b, str) else b).hexdigest()


def event_hash(ev: dict) -> str:
    """The V3 driver's event hash rule (lifecycle.State.event), so both chains verify the same way."""
    return sha256(json.dumps({k: ev[k] for k in ("seq", "ts", "kind", "data", "prev")}, sort_keys=True))


def atomic_write(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with open(tmp, "wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------------------- sensitive data

_SECRET_RES = [
    ("private_key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----.*?(-----END [A-Z ]*PRIVATE KEY-----|\Z)", re.S)),
    ("anthropic_key", re.compile(r"sk-ant-[A-Za-z0-9\-_]{16,}")),
    ("openai_key", re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_\-]{20,}")),
    ("google_key", re.compile(r"\bAIza[0-9A-Za-z_\-]{35}")),
    ("github_token", re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,})")),
    ("slack_token", re.compile(r"\bxox[abposr]-[A-Za-z0-9\-]{10,}")),
    ("aws_key", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}\.[A-Za-z0-9_\-]{8,}")),
    ("bearer", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-~+/]{16,}=*")),
    ("basic_auth", re.compile(r"(?i)\bbasic\s+[A-Za-z0-9+/]{8,}={0,2}")),
    ("hf_token", re.compile(r"\bhf_[A-Za-z0-9]{20,}")),
    ("pypi_token", re.compile(r"\bpypi-[A-Za-z0-9_\-]{16,}")),
    ("stripe_key", re.compile(r"\b(?:sk|rk|pk)_(?:live|test)_[A-Za-z0-9]{16,}")),
    ("gitlab_token", re.compile(r"\bglpat-[A-Za-z0-9_\-]{16,}")),
    ("npm_token", re.compile(r"\bnpm_[A-Za-z0-9]{30,}")),
    ("azure_key", re.compile(r"(?i)\b(AccountKey|SharedAccessKey|sig)=([A-Za-z0-9+/%]{16,}=*)")),
    ("cli_password", re.compile(r"(?i)(--?(?:password|passwd|pass|pwd|token|secret|api-key)(?:=|\s+)|"
                                r"(?<!\S)-p)([^\s\"']{4,})")),
    ("url_credentials", re.compile(r"(?i)\b([a-z][a-z0-9+.\-]*://)[^\s/:@]+:[^\s/@]+@")),
    # KEY=VALUE / "key": "value" where the key names a secret
    ("assignment", re.compile(r"(?i)\b([A-Za-z0-9_\-]*(?:password|passwd|pass|pwd|secret|token|api[_\-]?key|apikey|"
                              r"access[_\-]?key|private[_\-]?key|client[_\-]?secret|credential)s?)"
                              r"(\"?\s*[:=]\s*\"?)([^\s\"',;]{4,})")),
]
_SECRET_PATH = re.compile(r"(?i)(^|[\\/])(\.env(\..*)?|[^\\/]*\.pem|[^\\/]*\.key|id_rsa[^\\/]*|id_ed25519[^\\/]*|"
                          r"credentials[^\\/]*|\.netrc|\.git-credentials|[^\\/]*\.p12|[^\\/]*\.pfx)$")


def redact(text: str) -> tuple[str, int]:
    """Replace secret-looking substrings with ``[REDACTED:<label>]``. Returns (text, number of redactions)."""
    if not isinstance(text, str) or not text:
        return text, 0
    n = 0
    for label, rx in _SECRET_RES:
        def sub(m, label=label):
            nonlocal n
            n += 1
            if label == "assignment":
                return f"{m.group(1)}{m.group(2)}[REDACTED:{label}]"
            if label == "url_credentials":
                return f"{m.group(1)}[REDACTED:{label}]@"
            if label in ("cli_password", "azure_key"):
                return f"{m.group(1)}{'=' if label == 'azure_key' else ''}[REDACTED:{label}]"
            return f"[REDACTED:{label}]"
        text = rx.sub(sub, text)
    return text, n


def redact_obj(obj):
    """Redact every string (keys too) of a JSON-like object; returns (object, count)."""
    total = 0

    def walk(o):
        nonlocal total
        if isinstance(o, str):
            t, n = redact(o)
            total += n
            return t
        if isinstance(o, dict):
            return {walk(k): walk(v) for k, v in o.items()}
        if isinstance(o, (list, tuple)):
            return [walk(v) for v in o]
        return o
    return walk(obj), total


def is_secret_path(path: str) -> bool:
    return bool(_SECRET_PATH.search(str(path).replace("\\", "/").rstrip("/")))


# --------------------------------------------------------------------------- actors

def parse_actor(actor: str) -> tuple[str, str]:
    if redact(actor)[1]:
        raise Refused("secret-bearing actor identifier is not allowed")
    kind, sep, ident = str(actor or "").partition(":")
    if not sep or not ident.strip() or kind not in ACTOR_KINDS:
        raise Refused(f"actor must be '<kind>:<id>' with kind in {sorted(ACTOR_KINDS)}; got {actor!r}")
    return kind, ident


def _require(actor: str, kinds: set, what: str) -> str:
    kind, _ = parse_actor(actor)
    if kind not in kinds:
        raise Refused(f"{what} needs an actor of kind {sorted(kinds)}; {actor} is not allowed")
    return kind


# --------------------------------------------------------------------------- git

def git(repo, *args, check=True, inp: str | None = None) -> str:
    p = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=GIT_ENV, input=inp)
    if check and p.returncode:
        raise LedgerError(f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.stdout.strip()


def _commit_exists(repo, sha: str) -> bool:
    return bool(repo) and subprocess.run([*GIT, "-C", str(repo), "cat-file", "-e", f"{sha}^{{commit}}"],
                                         capture_output=True, env=GIT_ENV).returncode == 0


def _resolve_commit(repo, ref: str) -> str:
    if not repo:
        if re.fullmatch(r"[0-9a-f]{40}", ref or ""):
            return ref
        raise Refused("a commit needs a full 40-hex sha when the task has no worktree")
    sha = git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}", check=False)
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        raise Refused(f"commit {ref!r} does not exist in {repo}")
    return sha


# --------------------------------------------------------------------------- store

DDL = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS tasks(
  task_id TEXT PRIMARY KEY, milestone_ref TEXT, title TEXT NOT NULL, status TEXT NOT NULL, version INTEGER NOT NULL,
  created_at TEXT NOT NULL, updated_at TEXT NOT NULL, head_commit TEXT, last_verified_commit TEXT,
  accepted_commit TEXT, worktree TEXT, branch TEXT, resume_to TEXT, blocker TEXT, chain_head TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS tasks_milestone ON tasks(milestone_ref);
CREATE TABLE IF NOT EXISTS events(
  task_id TEXT NOT NULL, seq INTEGER NOT NULL, ts TEXT NOT NULL, kind TEXT NOT NULL, data TEXT NOT NULL,
  prev TEXT NOT NULL, hash TEXT NOT NULL, PRIMARY KEY(task_id, seq));
CREATE TABLE IF NOT EXISTS context(
  id INTEGER PRIMARY KEY, task_id TEXT NOT NULL, kind TEXT NOT NULL, key TEXT, text TEXT NOT NULL,
  sha TEXT NOT NULL, actor TEXT NOT NULL, path TEXT, blob TEXT, commit_sha TEXT, created_at TEXT NOT NULL,
  expires_at REAL, superseded INTEGER NOT NULL DEFAULT 0, redactions INTEGER NOT NULL DEFAULT 0,
  UNIQUE(task_id, sha));
CREATE INDEX IF NOT EXISTS context_task ON context(task_id, kind, superseded);
CREATE TABLE IF NOT EXISTS findings(
  task_id TEXT NOT NULL, finding_id TEXT NOT NULL, severity TEXT, blocking INTEGER NOT NULL, owner_decision INTEGER
  NOT NULL DEFAULT 0, title TEXT, status TEXT NOT NULL, commit_sha TEXT, review_id TEXT, closed_by TEXT,
  PRIMARY KEY(task_id, finding_id));
CREATE TABLE IF NOT EXISTS steps(
  task_id TEXT NOT NULL, step_id TEXT NOT NULL, name TEXT NOT NULL, status TEXT NOT NULL, actor TEXT NOT NULL,
  token INTEGER, started_at TEXT NOT NULL, ended_at TEXT, PRIMARY KEY(task_id, step_id));
CREATE TABLE IF NOT EXISTS reviews(
  task_id TEXT NOT NULL, review_id TEXT NOT NULL, commit_sha TEXT NOT NULL, reviewer TEXT NOT NULL,
  provenance TEXT NOT NULL, verdict TEXT, independent INTEGER NOT NULL, raw_sha256 TEXT NOT NULL,
  seq INTEGER NOT NULL, PRIMARY KEY(task_id, review_id));
CREATE TABLE IF NOT EXISTS leases(
  resource TEXT PRIMARY KEY, task_id TEXT, holder TEXT NOT NULL, token INTEGER NOT NULL, acquired_at TEXT NOT NULL,
  expires_at REAL NOT NULL);
CREATE TABLE IF NOT EXISTS packet_cache(
  task_id TEXT NOT NULL, cache_key TEXT NOT NULL, version INTEGER NOT NULL, packet TEXT NOT NULL,
  valid_until REAL NOT NULL, PRIMARY KEY(task_id, cache_key));
CREATE TABLE IF NOT EXISTS v3_links(
  task_id TEXT NOT NULL, state_dir TEXT NOT NULL, synced_seq INTEGER NOT NULL DEFAULT 0,
  PRIMARY KEY(task_id, state_dir));
CREATE TABLE IF NOT EXISTS availability(dev TEXT PRIMARY KEY, available INTEGER NOT NULL, reason TEXT,
  actor TEXT NOT NULL, at TEXT NOT NULL);
"""


class _RedactingDB:
    """The ledger's only SQL entry point. Every string parameter of every statement passes through ``redact``, so no
    column (ids, names, paths, keys, titles) can carry a secret into the file, whatever code path wrote it (review
    R1-04/R2-01/R2-05/R3-01: per-field redaction kept missing fields). ``redact`` is idempotent, so lookups with the
    same values match what was stored. Event rows are excluded: their data is redacted field by field before it is
    hashed, and re-redacting the serialised JSON could change bytes the chain hash covers."""

    _RAW = ("INTO events", "INTO packet_cache")

    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def execute(self, sql: str, params=()):
        if params and not any(k in sql for k in self._RAW):
            params = tuple(redact(v)[0] if isinstance(v, str) else v for v in params)
        return self.conn.execute(sql, params)

    def close(self):
        self.conn.close()


def default_path() -> Path:
    env = os.environ.get("URI_TASK_LEDGER")
    return Path(env) if env else Path.home() / ".uri-dev" / "task_ledger.sqlite3"


class Ledger:
    def __init__(self, path: str | Path | None = None, *, cache_ttl: float = 3600.0):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.dir = self.path.parent
        self.cache_ttl = cache_ttl
        conn = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        self.db = _RedactingDB(conn)
        self.db.execute("PRAGMA busy_timeout=30000")
        self.db.execute("PRAGMA journal_mode=WAL")
        self.db.execute("PRAGMA synchronous=FULL")      # a committed transaction survives power loss
        with self.tx():
            for stmt in filter(str.strip, DDL.split(";")):
                self.db.execute(stmt)
            row = self.db.execute("SELECT v FROM meta WHERE k='schema'").fetchone()
            if row is None:
                self.db.execute("INSERT INTO meta VALUES('schema', ?)", (str(SCHEMA_VERSION),))
                self.db.execute("INSERT INTO meta VALUES('fence', '0')")
            elif int(row["v"]) > SCHEMA_VERSION:
                raise LedgerError(f"ledger schema {row['v']} is newer than this tool ({SCHEMA_VERSION})")
        self._clean_stray_tmp()

    def close(self) -> None:
        self.db.close()

    @contextlib.contextmanager
    def tx(self):
        """One serialised write transaction (BEGIN IMMEDIATE takes the write lock up front: no lock upgrade
        deadlock between processes). Either everything in it is committed or nothing is."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            yield
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        self.db.execute("COMMIT")

    def _clean_stray_tmp(self) -> None:
        for p in (self.dir / "handoffs").glob("*.tmp") if (self.dir / "handoffs").is_dir() else ():
            with contextlib.suppress(OSError):
                p.unlink()

    # ----------------------------------------------------------------- internal helpers (inside a transaction)

    def _task(self, task_id: str) -> sqlite3.Row:
        row = self.db.execute("SELECT * FROM tasks WHERE task_id=?", (task_id,)).fetchone()
        if row is None:
            raise Refused(f"no task {task_id}")
        return row

    def _append(self, task_id: str, kind: str, actor: str, data: dict, *, expected_version: int | None = None,
                **updates) -> dict:
        parse_actor(actor)  # All event writers, including internal V3 sync, share the actor guard.
        t = self._task(task_id)
        if expected_version is not None and t["version"] != expected_version:
            raise Refused(f"{task_id} is at version {t['version']}, not {expected_version} (changed by another "
                          f"writer; re-read and retry)")
        data, _ = redact_obj({"actor": actor, **data})
        ev = {"seq": t["version"] + 1, "ts": now_iso(), "kind": kind, "data": data, "prev": t["chain_head"]}
        ev["hash"] = event_hash(ev)
        self.db.execute("INSERT INTO events VALUES(?,?,?,?,?,?,?)", (task_id, ev["seq"], ev["ts"], kind,
                        json.dumps(data, sort_keys=True), ev["prev"], ev["hash"]))
        cols = {"version": ev["seq"], "chain_head": ev["hash"], "updated_at": ev["ts"], **updates}
        self.db.execute(f"UPDATE tasks SET {', '.join(f'{k}=?' for k in cols)} WHERE task_id=?",
                        (*cols.values(), task_id))
        return ev

    def _availability(self) -> dict:
        return {r["dev"]: bool(r["available"]) for r in self.db.execute("SELECT * FROM availability")}

    def development_paused(self) -> bool:
        a = self._availability()
        return all(a.get(d) is False for d in DEVELOPERS)

    def _guard_dev(self, t: sqlite3.Row, actor: str, what: str) -> None:
        """Every execution change: a developer actor, development not paused, task not paused or terminal."""
        _require(actor, DEVELOPERS | ({"owner"} if what in ("abandon", "unblock") else set()), what)
        if self.development_paused():
            raise Refused("DEVELOPMENT_PAUSED: Claude and Codex are both recorded unavailable; only notes/evidence "
                          "may be added until an available developer resumes")
        if t["status"] == "PAUSED" and what != "resume":
            raise Refused(f"{t['task_id']} is PAUSED; resume it first")
        if t["status"] in TERMINAL:
            raise Refused(f"{t['task_id']} is {t['status']} (terminal)")

    def _fence(self) -> int:
        n = int(self.db.execute("SELECT v FROM meta WHERE k='fence'").fetchone()["v"]) + 1
        self.db.execute("UPDATE meta SET v=? WHERE k='fence'", (str(n),))
        return n

    def _implementers(self, task_id: str) -> set:
        rows = self.db.execute("SELECT data FROM events WHERE task_id=? AND kind IN ('CREATED','STATUS','STEP_STARTED',"
                               "'STEP_ENDED','HEAD','TEST','CONTEXT','FINDING_CLOSED','CLAIM','RESUMED')", (task_id,))
        out = set()
        for r in rows:
            a = json.loads(r["data"]).get("actor")
            if a and parse_actor(a)[0] in DEVELOPERS | {"owner"}:
                out.add(a)
        return out

    # ----------------------------------------------------------------- tasks

    def create(self, title: str, objective: str, actor: str, *, milestone_ref: str | None = None,
               worktree: str | None = None, branch: str | None = None, task_id: str | None = None) -> str:
        return self._create(title, objective, actor, milestone_ref=milestone_ref, worktree=worktree,
                            branch=branch, task_id=task_id)

    def _create(self, title: str, objective: str, actor: str, *, milestone_ref: str | None = None,
                worktree: str | None = None, branch: str | None = None, task_id: str | None = None,
                import_source: Path | None = None) -> str:
        if import_source is None:
            _require(actor, DEVELOPERS | {"owner"}, "create")
        else:
            # Only the V3 importer may use the system actor; bind the deterministic id to a real run.
            if actor != "system:import-v3" or not (import_source / "events.jsonl").is_file() or \
                    not (import_source / "state.json").is_file():
                raise Refused("system task creation is only allowed for a V3 import source")
            state = json.loads((import_source / "state.json").read_text(encoding="utf-8"))
            base = re.sub(r"(-(r|c|u)\d+)+$", "", state.get("milestone") or import_source.parent.name)
            if task_id != "TASK-V3-" + sha256(f"uri-v3-milestone:{base}")[:12] or milestone_ref != base:
                raise Refused("V3 import task identity does not match its source")
        if task_id is not None and redact(task_id)[1]:
            raise Refused("secret-bearing task identifier is not allowed")
        if worktree and redact(str(worktree))[1]:
            raise Refused("a secret-bearing worktree path is not allowed (R3-01)")
        wt = str(Path(worktree).resolve()) if worktree else None
        if wt and branch is None:
            branch = git(wt, "rev-parse", "--abbrev-ref", "HEAD", check=False) or None
        head = git(wt, "rev-parse", "HEAD", check=False) if wt else None
        with self.tx():
            if self.development_paused() and parse_actor(actor)[0] != "system":
                raise Refused("DEVELOPMENT_PAUSED: no new task while Claude and Codex are both unavailable")
            for _ in range(5):
                tid = task_id or f"TASK-{datetime.datetime.now(datetime.timezone.utc):%Y%m%d}-{secrets.token_hex(4)}"
                if self.db.execute("SELECT 1 FROM tasks WHERE task_id=?", (tid,)).fetchone() is None:
                    break
                if task_id:
                    raise Refused(f"{tid} already exists")
            else:
                raise LedgerError("could not allocate a unique task id")
            title_r = redact(title)[0]
            milestone_ref, branch = redact(milestone_ref)[0], redact(branch)[0]   # R1-04: every row string
            ts = now_iso()
            self.db.execute("INSERT INTO tasks(task_id, milestone_ref, title, status, version, created_at, "
                            "updated_at, head_commit, worktree, branch, chain_head) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
                            (tid, milestone_ref, title_r, "OPEN", 0, ts, ts,
                             head if head and re.fullmatch(r"[0-9a-f]{40}", head) else None, wt, branch, GENESIS))
            self._append(tid, "CREATED", actor, {"title": title_r, "milestone_ref": milestone_ref, "worktree": wt,
                                                 "branch": branch, "head": head})
            if objective:
                self._add_context(tid, actor, "objective", objective, key="objective")
        return tid

    def get(self, task_id: str) -> dict:
        return dict(self._task(task_id))

    def list(self, milestone_ref: str | None = None) -> list[dict]:
        q, a = "SELECT * FROM tasks", ()
        if milestone_ref is not None:
            q, a = q + " WHERE milestone_ref=?", (milestone_ref,)
        return [dict(r) for r in self.db.execute(q + " ORDER BY created_at, task_id", a)]

    def transition(self, task_id: str, to: str, actor: str, reason: str = "", *, expected_version=None) -> dict:
        if to not in STATUSES:
            raise Refused(f"unknown status {to}")
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "abandon" if to == "ABANDONED" else "transition")
            if to in ("ACCEPTED", "INTEGRATED"):
                raise Refused(f"{to} is entered only through `accept` / `integrated`, which check evidence")
            if to not in TRANSITIONS[t["status"]]:
                raise Refused(f"{t['status']} -> {to} is not allowed")
            if self._open_steps(task_id) and to not in ("ABANDONED",):
                raise Refused(f"{task_id} has open steps {self._open_steps(task_id)}; end them first")
            upd = {"status": to}
            if t["status"] == "ACCEPTED":
                upd["accepted_commit"] = None
            return self._append(task_id, "STATUS", actor, {"frm": t["status"], "to": to, "reason": reason},
                                expected_version=expected_version, **upd)

    def block(self, task_id: str, actor: str, reason: str, needs: str) -> dict:
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "block")
            if t["status"] in ("BLOCKED", "PAUSED"):
                raise Refused(f"{task_id} is already {t['status']}")
            blocker = json.dumps(redact_obj({"reason": reason, "needs": needs})[0])
            self._interrupt_steps(task_id, "task blocked")
            return self._append(task_id, "BLOCKED", actor, {"frm": t["status"], "reason": reason, "needs": needs,
                                                            "resume_to": t["status"]},
                                status="BLOCKED", resume_to=t["status"], blocker=blocker)

    def unblock(self, task_id: str, actor: str, note: str) -> dict:
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "unblock")
            if t["status"] != "BLOCKED":
                raise Refused(f"{task_id} is not BLOCKED")
            self._require_integrity(task_id)
            to = self._resume_target(t)
            return self._append(task_id, "UNBLOCKED", actor, {"to": to, "note": note}, status=to, resume_to=None,
                                blocker=None)

    def set_milestone_ref(self, task_id: str, actor: str, milestone_ref: str | None) -> dict:
        milestone_ref = redact(milestone_ref)[0]
        with self.tx():
            self._guard_dev(self._task(task_id), actor, "milestone_ref")
            return self._append(task_id, "MILESTONE_REF", actor, {"milestone_ref": milestone_ref},
                                milestone_ref=milestone_ref)

    # ----------------------------------------------------------------- commits and tests

    def set_head(self, task_id: str, actor: str, commit: str) -> dict:
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "set head")
            sha = _resolve_commit(t["worktree"], commit)
            upd = {"head_commit": sha}
            data = {"commit": sha, "previous": t["head_commit"]}
            if t["accepted_commit"] and sha != t["accepted_commit"]:
                # The acceptance was for the exact previous commit; a new commit needs a new review (FB R1-06: in
                # every status, not only ACCEPTED).
                upd["accepted_commit"] = None
                if t["status"] == "ACCEPTED":
                    upd["status"] = "IN_REVIEW"
                data["acceptance_invalidated"] = t["accepted_commit"]
            ev = self._append(task_id, "HEAD", actor, data, **upd)
            self._add_context(task_id, actor, "commit", f"head {sha}", commit=sha, key=f"commit:{sha}")
            return ev

    def record_test(self, task_id: str, actor: str, commit: str, passed: bool, summary: str,
                    log_path: str | None = None) -> dict:
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "record test")
            sha = _resolve_commit(t["worktree"], commit)
            log = None
            if passed and not log_path:
                raise Refused("a passing test result needs its log (--log): a claimed pass is not evidence (R1-03)")
            if log_path:
                p = Path(log_path)
                if is_secret_path(p):
                    raise Refused(f"{p} looks like a secret-bearing file; not recorded")
                log = {"path": str(p.resolve()), "sha256": sha256(p.read_bytes())} if p.is_file() else None
                if log is None:
                    raise Refused(f"test log {p} does not exist (a claimed result needs its output)")
            upd = {"last_verified_commit": sha} if passed else {}
            ev = self._append(task_id, "TEST", actor, {"commit": sha, "passed": passed, "summary": summary,
                                                       "log": log}, **upd)
            self._add_context(task_id, actor, "test", f"{'PASS' if passed else 'FAIL'} @ {sha[:12]}: {summary}",
                              commit=sha)
            return ev

    # ----------------------------------------------------------------- context

    def add_context(self, task_id: str, actor: str, kind: str, text: str, *, key: str | None = None,
                    path: str | None = None, commit: str | None = None, ttl_s: float | None = None) -> dict:
        with self.tx():
            t = self._task(task_id)
            akind = parse_actor(actor)[0]
            if kind in ("evidence", "note"):
                if akind not in EVIDENCE_WRITERS:
                    raise Refused(f"{actor} may not add context")
                if t["status"] in TERMINAL:
                    raise Refused(f"{task_id} is {t['status']} (terminal)")
            else:
                self._guard_dev(t, actor, f"add {kind}")
            return self._add_context(task_id, actor, kind, text, key=key, path=path, commit=commit, ttl_s=ttl_s)

    def _add_context(self, task_id, actor, kind, text, *, key=None, path=None, commit=None, ttl_s=None) -> dict:
        if kind not in CONTEXT_KINDS:
            raise Refused(f"context kind must be one of {CONTEXT_KINDS}")
        t = self._task(task_id)
        blob = None
        if path:
            if is_secret_path(path):
                raise Refused(f"{path} looks like a secret-bearing file; it is never bound as context")
            if not t["worktree"]:
                raise Refused("a path-bound item needs a task worktree")
            rel = Path(path).as_posix()
            if not (Path(t["worktree"]) / rel).is_file():
                raise Refused(f"{rel} does not exist in {t['worktree']}")
            blob, path = git(t["worktree"], "hash-object", "--", rel), rel
        if commit:
            commit = _resolve_commit(t["worktree"], commit)
        text_r, n = redact(text)
        key_r = redact(key)[0] if key else None
        sha = sha256(json.dumps([kind, key_r, text_r, path, blob, commit]))
        old = self.db.execute("SELECT id, superseded FROM context WHERE task_id=? AND sha=?",
                              (task_id, sha)).fetchone()
        if old is not None:            # deduplicated: identical content is stored once
            if key_r and old["superseded"]:
                # R1-06: repeating an earlier keyed item makes it current again (and supersedes the newer one)
                self.db.execute("UPDATE context SET superseded=1 WHERE task_id=? AND kind=? AND key=? AND "
                                "superseded=0", (task_id, kind, key_r))
                self.db.execute("UPDATE context SET superseded=0 WHERE id=?", (old["id"],))
                self._append(task_id, "CONTEXT_RESTORED", actor, {"id": old["id"], "kind": kind, "key": key_r,
                                                                  "sha": sha})
                return {"id": old["id"], "sha": sha, "deduplicated": True, "restored": True}
            return {"id": old["id"], "sha": sha, "deduplicated": True}
        expires = time.time() + ttl_s if ttl_s else None
        if key_r:
            self.db.execute("UPDATE context SET superseded=1 WHERE task_id=? AND kind=? AND key=? AND superseded=0",
                            (task_id, kind, key_r))
        cur = self.db.execute("INSERT INTO context(task_id, kind, key, text, sha, actor, path, blob, commit_sha, "
                              "created_at, expires_at, redactions) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
                              (task_id, kind, key_r, text_r, sha, actor, path, blob, commit, now_iso(), expires, n))
        self._append(task_id, "CONTEXT", actor, {"id": cur.lastrowid, "kind": kind, "key": key_r, "sha": sha,
                                                 "path": path, "blob": blob, "commit": commit, "redactions": n})
        return {"id": cur.lastrowid, "sha": sha, "deduplicated": False, "redactions": n}

    def context_get(self, task_id: str, sha_prefix: str) -> dict:
        rows = self.db.execute("SELECT * FROM context WHERE task_id=? AND sha LIKE ?",
                               (task_id, sha_prefix + "%")).fetchall()
        if len(rows) != 1:
            raise Refused(f"{len(rows)} items match {sha_prefix!r}")
        return dict(rows[0])

    def _freshness(self, t, rows) -> tuple[dict, str]:
        """(staleness by context id, fingerprint of everything retrieval depends on outside the ledger)."""
        stale, parts = {}, []
        wt = t["worktree"]
        head = git(wt, "rev-parse", "HEAD", check=False) if wt and Path(wt).is_dir() else None
        parts.append(f"head={head}")
        paths = sorted({r["path"] for r in rows if r["path"]})
        if paths:
            if head is None:
                cur = {p: None for p in paths}
            else:
                existing = [p for p in paths if (Path(wt) / p).is_file()]
                hashes = git(wt, "hash-object", "--", *existing).splitlines() if existing else []
                cur = {p: None for p in paths}
                cur.update(dict(zip(existing, hashes)))
            parts.append(json.dumps(cur, sort_keys=True))
            for r in rows:
                if r["path"] and cur.get(r["path"]) != r["blob"]:
                    stale[r["id"]] = f"{r['path']} changed since it was recorded"
        commits = sorted({r["commit_sha"] for r in rows if r["commit_sha"]})
        if commits:
            if wt and Path(wt).is_dir():
                out = git(wt, "cat-file", "--batch-check", check=False, inp="\n".join(commits) + "\n").splitlines()
                missing = {c for c, line in zip(commits, out) if line.endswith("missing")}
            else:
                missing = set()
            parts.append("missing=" + ",".join(sorted(missing)))
            for r in rows:
                if r["commit_sha"] in missing:
                    stale[r["id"]] = f"commit {r['commit_sha'][:12]} no longer exists"
        nowt = time.time()
        for r in rows:
            if r["expires_at"] is not None and r["expires_at"] <= nowt:
                stale[r["id"]] = "expired"
        return stale, sha256("|".join(parts))

    def packet(self, task_id: str, *, budget: int = 6000, query: str = "", item_chars: int = 600,
               use_cache: bool = True) -> dict:
        """Relevant context for continuing a task, deterministic, under ``budget`` characters of item text."""
        t = self._task(task_id)
        rows = self.db.execute("SELECT * FROM context WHERE task_id=? AND superseded=0 ORDER BY id",
                               (task_id,)).fetchall()
        stale, fp = self._freshness(t, rows)
        params = json.dumps([budget, query, item_chars])
        key = sha256(f"{params}|{fp}|{sorted(stale)}")
        nowt = time.time()
        if use_cache:
            c = self.db.execute("SELECT * FROM packet_cache WHERE task_id=? AND cache_key=?",
                                (task_id, key)).fetchone()
            if c is not None and c["version"] == t["version"] and c["valid_until"] > nowt:
                p = json.loads(c["packet"])
                p["cache"] = "HIT"
                return p
        live = [r for r in rows if r["id"] not in stale]
        done_keys = {r["key"] for r in live if r["kind"] == "done" and r["key"]}
        by_kind: dict[str, list] = {}
        for r in live:
            if r["kind"] == "todo" and r["key"] in done_keys:
                continue
            by_kind.setdefault(r["kind"], []).append(r)
        qt = set(re.findall(r"\w+", query.lower()))
        items, used, omitted = [], 0, 0
        for kind in PACKET_ORDER:
            group = by_kind.get(kind, [])
            if kind in PACKET_LATEST:
                group = group[-PACKET_LATEST[kind]:]
            if kind in ("evidence", "note") and qt:
                group = sorted(group, key=lambda r: (-len(qt & set(re.findall(r"\w+", r["text"].lower()))),
                                                     -r["id"]))
            elif kind in ("evidence", "note"):
                group = list(reversed(group))
            for r in group:
                text = r["text"]
                if len(text) > item_chars:          # compression: excerpt + pointer to the full item
                    text = text[:item_chars] + f" ...[truncated; full: context-get {r['sha'][:12]}]"
                if used + len(text) > budget:
                    omitted += 1
                    continue
                used += len(text)
                items.append({"kind": r["kind"], "key": r["key"], "text": text, "sha": r["sha"][:12],
                              **({"path": r["path"]} if r["path"] else {}),
                              **({"commit": r["commit_sha"]} if r["commit_sha"] else {})})
        findings = [dict(f) for f in self.db.execute(
            "SELECT finding_id, severity, blocking, owner_decision, title FROM findings WHERE task_id=? AND "
            "status='OPEN' ORDER BY finding_id", (task_id,))]
        p = {"task": self._summary(t), "items": items, "open_findings": findings,
             "stale": [{"id": i, "why": w} for i, w in sorted(stale.items())], "omitted": omitted,
             "chars": used, "version": t["version"], "cache": "MISS"}
        expiries = [r["expires_at"] for r in live if r["expires_at"] is not None]
        valid = min([nowt + self.cache_ttl, *expiries])
        with self.tx():
            self.db.execute("DELETE FROM packet_cache WHERE task_id=? AND (version<>? OR valid_until<=?)",
                            (task_id, t["version"], nowt))
            self.db.execute("INSERT OR REPLACE INTO packet_cache VALUES(?,?,?,?,?)",
                            (task_id, key, t["version"], json.dumps(p, sort_keys=True), valid))
        return p

    # ----------------------------------------------------------------- steps, claims, leases

    def _open_steps(self, task_id: str) -> list[str]:
        return [r["step_id"] for r in self.db.execute(
            "SELECT step_id FROM steps WHERE task_id=? AND status='STARTED' ORDER BY rowid", (task_id,))]

    def _lease(self, resource: str):
        return self.db.execute("SELECT * FROM leases WHERE resource=?", (resource,)).fetchone()

    def acquire(self, task_id: str | None, actor: str, resources: list[str], ttl_s: float = 900.0) -> dict:
        """All-or-nothing: either every resource is leased to ``actor`` in one transaction or none is. Callers never
        wait while holding a lease, so leases cannot deadlock; expired leases are reclaimed."""
        _require(actor, DEVELOPERS | {"owner"}, "acquire leases")
        for r in resources:
            if redact(r)[1]:
                raise Refused("a secret-bearing lease name is not allowed (R3-01)")
            if re.match(r"(?i)gpu", r):
                raise Refused("GPU arbitration belongs to uri_operational_intelligence.gpu_lease; record that lease "
                              "as evidence instead of creating a second GPU lease here")
        with self.tx():
            if self.development_paused():
                raise Refused("DEVELOPMENT_PAUSED")
            if task_id:
                self._task(task_id)
            nowt = time.time()
            conflicts = []
            for r in sorted(set(resources)):
                cur = self._lease(r)
                if cur is not None and cur["expires_at"] > nowt and cur["holder"] != actor:
                    conflicts.append({"resource": r, "holder": cur["holder"], "task_id": cur["task_id"],
                                      "expires_in_s": round(cur["expires_at"] - nowt, 1)})
            if conflicts:
                raise Refused("LEASE_CONFLICT " + json.dumps(conflicts))
            tokens = {}
            for r in sorted(set(resources)):
                tok = self._fence()
                self.db.execute("INSERT OR REPLACE INTO leases VALUES(?,?,?,?,?,?)",
                                (r, task_id, actor, tok, now_iso(), nowt + ttl_s))
                tokens[r] = tok
            if task_id:
                self._append(task_id, "LEASES", actor, {"acquired": tokens, "ttl_s": ttl_s})
            return tokens

    def release(self, actor: str, resource: str, token: int) -> None:
        with self.tx():
            cur = self._lease(resource)
            if cur is None or cur["token"] != token or cur["holder"] != actor:
                raise Refused(f"{actor} does not hold {resource} with token {token}")
            self.db.execute("DELETE FROM leases WHERE resource=?", (resource,))
            if cur["task_id"]:
                self._append(cur["task_id"], "LEASE_RELEASED", actor, {"resource": resource, "token": token})

    def leases(self) -> list[dict]:
        nowt = time.time()
        return [{**dict(r), "expired": r["expires_at"] <= nowt} for r in self.db.execute("SELECT * FROM leases")]

    def claim(self, task_id: str, actor: str, ttl_s: float = 900.0) -> int:
        """The session lease on a task. Steps need it; when it expires with steps open, recovery interrupts them."""
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "claim")
            res, nowt = f"task:{task_id}", time.time()
            cur = self._lease(res)
            if cur is not None and cur["expires_at"] > nowt and cur["holder"] != actor:
                raise Refused(f"LEASE_CONFLICT {task_id} is claimed by {cur['holder']} for "
                              f"{round(cur['expires_at'] - nowt)} s more")
            tok = cur["token"] if cur is not None and cur["holder"] == actor and cur["expires_at"] > nowt \
                else self._fence()
            self.db.execute("INSERT OR REPLACE INTO leases VALUES(?,?,?,?,?,?)",
                            (res, task_id, actor, tok, now_iso(), nowt + ttl_s))
            if cur is None or cur["token"] != tok:
                self._append(task_id, "CLAIM", actor, {"token": tok, "ttl_s": ttl_s})
            return tok

    def _held_token(self, task_id: str, actor: str) -> int:
        cur = self._lease(f"task:{task_id}")
        if cur is None or cur["holder"] != actor or cur["expires_at"] <= time.time():
            raise Refused(f"{actor} does not hold a live claim on {task_id}; run `claim` first")
        return cur["token"]

    def step_start(self, task_id: str, actor: str, name: str) -> str:
        """Write-ahead intent: recorded before the work starts, so a crash leaves an open step, never a silent gap."""
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "start step")
            if t["status"] not in ACTIVE:
                raise Refused(f"steps run in {sorted(ACTIVE)}; {task_id} is {t['status']}")
            tok = self._held_token(task_id, actor)
            n = self.db.execute("SELECT COUNT(*) c FROM steps WHERE task_id=?", (task_id,)).fetchone()["c"] + 1
            sid = f"S{n}"
            name_r = redact(name)[0]
            self.db.execute("INSERT INTO steps VALUES(?,?,?,?,?,?,?,?)",
                            (task_id, sid, name_r, "STARTED", actor, tok, now_iso(), None))
            self._append(task_id, "STEP_STARTED", actor, {"step": sid, "name": name_r, "token": tok,
                                                          "head": t["head_commit"]})
            return sid

    def step_end(self, task_id: str, actor: str, step_id: str, ok: bool, note: str = "") -> dict:
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "end step")
            s = self.db.execute("SELECT * FROM steps WHERE task_id=? AND step_id=?", (task_id, step_id)).fetchone()
            if s is None or s["status"] != "STARTED":
                raise Refused(f"{step_id} is not an open step of {task_id} "
                              f"({s['status'] if s else 'unknown'}: an interrupted step cannot be completed)")
            tok = self._held_token(task_id, actor)
            if s["token"] != tok:      # fencing: a claim that lapsed and was re-taken cannot close the old step
                raise Refused(f"{step_id} was started under claim token {s['token']}, current token is {tok}")
            st = "COMPLETED" if ok else "FAILED"
            self.db.execute("UPDATE steps SET status=?, ended_at=? WHERE task_id=? AND step_id=?",
                            (st, now_iso(), task_id, step_id))
            ev = self._append(task_id, "STEP_ENDED", actor, {"step": step_id, "status": st, "note": note})
            if ok:
                self._add_context(task_id, actor, "progress", f"{step_id} {s['name']}: COMPLETED. {note}".strip())
            return ev

    def _interrupt_steps(self, task_id: str, why: str) -> list[str]:
        open_ = self._open_steps(task_id)
        for sid in open_:
            self.db.execute("UPDATE steps SET status='INTERRUPTED', ended_at=? WHERE task_id=? AND step_id=?",
                            (now_iso(), task_id, sid))
            self._append(task_id, "STEP_INTERRUPTED", "system:ledger", {"step": sid, "why": why})
        return open_

    # ----------------------------------------------------------------- recovery

    def recover(self, actor: str = "system:recover") -> list[dict]:
        """Crash/session-loss recovery. Never completes anything: open steps whose claim has lapsed become
        INTERRUPTED and the task INTERRUPTED (resume target kept); worktree drift is recorded."""
        out = []
        with self.tx():
            nowt = time.time()
            for t in self.db.execute("SELECT * FROM tasks").fetchall():
                tid = t["task_id"]
                if t["status"] in TERMINAL:
                    continue
                cur = self._lease(f"task:{tid}")
                lapsed = cur is None or cur["expires_at"] <= nowt
                if t["status"] in ACTIVE and lapsed:
                    steps = self._open_steps(tid)
                    if steps or cur is not None:
                        why = "claim lapsed (session ended, crashed or ran out of quota)"
                        self._interrupt_steps(tid, why)
                        self._append(tid, "INTERRUPTED", actor, {"frm": t["status"], "open_steps": steps,
                                                                 "why": why, "resume_to": t["status"]},
                                     status="INTERRUPTED", resume_to=t["status"])
                        out.append({"task_id": tid, "action": "INTERRUPTED", "steps": steps})
                if cur is not None and lapsed:
                    self.db.execute("DELETE FROM leases WHERE resource=?", (f"task:{tid}",))
                drift = self._drift(self._task(tid))
                if drift:
                    last = self.db.execute("SELECT data FROM events WHERE task_id=? AND kind='WORKTREE_DRIFT' "
                                           "ORDER BY seq DESC LIMIT 1", (tid,)).fetchone()
                    if last is None or {k: v for k, v in json.loads(last["data"]).items() if k != "actor"} != drift:
                        self._append(tid, "WORKTREE_DRIFT", actor, drift)
                        out.append({"task_id": tid, "action": "WORKTREE_DRIFT", **drift})
            self.db.execute("DELETE FROM leases WHERE expires_at<=? AND resource NOT LIKE 'task:%'", (nowt,))
        return out

    def _drift(self, t) -> dict | None:
        wt = t["worktree"]
        if not wt:
            return None
        if not Path(wt).is_dir():
            return {"worktree": wt, "problem": "worktree missing"}
        head = git(wt, "rev-parse", "HEAD", check=False)
        dirty = [line[3:] for line in git(wt, "status", "--porcelain=v1", "-uall", check=False).splitlines()]
        d = {}
        if t["head_commit"] and head != t["head_commit"]:
            d.update(expected_head=t["head_commit"], actual_head=head)
        if dirty:
            d["uncommitted"] = sorted(dirty)[:50]
        return d or None

    def resume(self, task_id: str, actor: str, note: str = "") -> dict:
        """Leave INTERRUPTED or PAUSED. Only an available developer (Claude or Codex) may resume; Antigravity and
        subagents never can (development pause policy)."""
        kind = _require(actor, DEVELOPERS, "resume")
        with self.tx():
            t = self._task(task_id)
            if self._availability().get(kind) is False:
                raise Refused(f"{kind} is recorded unavailable; record `availability --dev {kind} --available` "
                              f"first")
            if t["status"] not in ("INTERRUPTED", "PAUSED"):
                raise Refused(f"{task_id} is {t['status']}, not INTERRUPTED/PAUSED")
            self._require_integrity(task_id)
            to = self._resume_target(t)
            drift = self._drift(t)
            return self._append(task_id, "RESUMED", actor, {"frm": t["status"], "to": to, "note": note,
                                                            "worktree_check": drift or "clean, head as recorded"},
                                status=to, resume_to=None)

    def _acceptance_still_valid(self, t) -> bool:
        return bool(t["accepted_commit"]) and t["accepted_commit"] == t["head_commit"]

    RESUMABLE = ("OPEN", "IN_PROGRESS", "IN_REVIEW", "REPAIR", "ACCEPTED")

    def _resume_target(self, t) -> str:
        """Where an unblock/resume may go (FB R1-02): an ordinary working status, or ACCEPTED only while the
        acceptance still holds for the head. Never INTEGRATED, terminal or another hold."""
        to = t["resume_to"] or "IN_PROGRESS"
        if to not in self.RESUMABLE:
            raise Refused(f"resume target {to!r} is not allowed; the task row may have been edited")
        if to == "ACCEPTED" and not self._acceptance_still_valid(t):
            to = "IN_REVIEW"
        return to

    def _require_integrity(self, task_id: str) -> None:
        """Replay the task's chain before recording a review or making a decision, so edited rows cannot steer it."""
        errs = self.verify(task_id)
        if errs:
            raise Refused("LEDGER_INTEGRITY_FAILED: " + "; ".join(errs[:5]))

    # ----------------------------------------------------------------- development pause

    def set_availability(self, actor: str, dev: str, available: bool, reason: str = "") -> list[str]:
        """Record whether Claude/Codex can develop. When both are unavailable every non-terminal task is PAUSED with
        a checkpoint (open steps interrupted, resume target kept)."""
        kind = parse_actor(actor)[0]
        if dev not in DEVELOPERS:
            raise Refused(f"dev must be one of {sorted(DEVELOPERS)}")
        if kind not in DEVELOPERS | {"owner", "system"}:
            raise Refused(f"{actor} may not change development availability")
        if available and kind != "owner" and kind != dev:
            raise Refused(f"only {dev} itself (or the owner) can record {dev} available")
        paused = []
        with self.tx():
            self.db.execute("INSERT OR REPLACE INTO availability VALUES(?,?,?,?,?)",
                            (dev, int(available), redact(reason)[0], actor, now_iso()))
            if self.development_paused():
                for t in self.db.execute("SELECT * FROM tasks WHERE status NOT IN ('PAUSED','INTEGRATED',"
                                         "'ABANDONED')").fetchall():
                    steps = self._interrupt_steps(t["task_id"], "development paused")
                    target = t["resume_to"] if t["status"] in ("INTERRUPTED", "BLOCKED") and t["resume_to"] \
                        else t["status"]
                    self._append(t["task_id"], "PAUSED", actor,
                                 {"frm": t["status"], "reason": reason, "resume_to": target, "checkpoint": {
                                     "head": t["head_commit"], "last_verified": t["last_verified_commit"],
                                     "interrupted_steps": steps}},
                                 status="PAUSED", resume_to=target)
                    paused.append(t["task_id"])
        return paused

    # ----------------------------------------------------------------- findings, reviews, acceptance

    def add_finding(self, task_id: str, actor: str, finding_id: str, severity: str, title: str,
                    blocking: bool | None = None, owner_decision: bool = False) -> dict:
        with self.tx():
            t = self._task(task_id)
            if parse_actor(actor)[0] not in DEVELOPERS | REVIEWERS | {"owner"}:
                raise Refused(f"{actor} may not raise findings")
            if t["status"] in TERMINAL:
                raise Refused(f"{task_id} is terminal")
            return self._add_finding(task_id, actor, {"id": finding_id, "severity": severity, "title": title,
                                                      "blocking": blocking, "owner_decision": owner_decision},
                                     None, t["head_commit"])

    def _add_finding(self, task_id, actor, f: dict, review_id, commit) -> dict:
        from scripts.dev_workflow.lifecycle import is_blocking
        raw_id = str(f.get("id") or f"F{secrets.token_hex(3)}")
        if redact(raw_id)[1]:
            raise Refused("secret-bearing finding identifier is not allowed")
        # Reviewers number findings per round (R1-01 ...); stored ids are namespaced by the recording review so a
        # later review's R1-01 never replaces or closes another review's R1-01.
        fid = f"{review_id}/{raw_id}" if review_id else raw_id
        if self.db.execute("SELECT 1 FROM findings WHERE task_id=? AND finding_id=?", (task_id, fid)).fetchone():
            raise Refused(f"finding {fid} already exists")
        blocking = is_blocking({k: v for k, v in f.items() if k != "blocking" or v is not None})
        title = redact(str(f.get("title") or ""))[0]
        severity = redact(str(f.get("severity") or ""))[0]
        owner_decision = bool(f.get("owner_decision"))
        self.db.execute("INSERT INTO findings VALUES(?,?,?,?,?,?,?,?,?,?)",
                        (task_id, fid, severity, int(blocking), int(owner_decision), title,
                         "OPEN", commit, review_id, None))
        return self._append(task_id, "FINDING", actor, {"id": fid, "raw_id": raw_id, "severity": severity,
                                                         "blocking": blocking, "owner_decision": owner_decision,
                                                         "title": title, "review": review_id, "commit": commit})

    def close_finding(self, task_id: str, actor: str, finding_id: str, commit: str, note: str) -> dict:
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "close finding")
            f = self.db.execute("SELECT * FROM findings WHERE task_id=? AND finding_id=?",
                                (task_id, finding_id)).fetchone()
            if f is None or f["status"] != "OPEN":
                raise Refused(f"{finding_id} is not an open finding")
            sha = _resolve_commit(t["worktree"], commit)
            self.db.execute("UPDATE findings SET status='CLOSED', closed_by=? WHERE task_id=? AND finding_id=?",
                            (actor, task_id, finding_id))
            return self._append(task_id, "FINDING_CLOSED", actor, {"id": finding_id, "commit": sha, "note": note})

    def record_review(self, task_id: str, actor: str, commit: str, output_file: str, *,
                      mechanism: str = "") -> dict:
        """Record an independent review from the reviewer's own raw output. The verdict is recomputed with the V3
        driver's parser; the result must name the exact commit; the reviewer must not be an implementer."""
        from scripts.dev_workflow.lifecycle import effective_verdict, parse_review
        kind = _require(actor, REVIEWERS, "record a review")
        p = Path(output_file)
        raw = p.read_bytes()
        result, problem = parse_review(raw.decode("utf-8", errors="replace"))
        with self.tx():
            t = self._task(task_id)
            self._require_integrity(task_id)
            if t["status"] in TERMINAL:
                raise Refused(f"{task_id} is terminal")
            sha = _resolve_commit(t["worktree"], commit)
            if result is not None and result.get("candidate") != sha:
                problem = ("review result does not name the candidate commit it reviewed" if not result.get("candidate")
                           else f"review names candidate {result.get('candidate')}, not {sha}")
            verdict, blocking = (effective_verdict(result) if result is not None and not problem else (None, []))
            implementers = self._implementers(task_id)
            independent = verdict is not None and actor not in implementers
            n = self.db.execute("SELECT COUNT(*) c FROM reviews WHERE task_id=?", (task_id,)).fetchone()["c"] + 1
            rid = f"V{n}"
            store = self.dir / "reviews" / task_id
            red, nred = redact(raw.decode("utf-8", errors="replace"))
            atomic_write(store / f"{rid}.txt", red.encode("utf-8"))
            prov = f"{kind.upper()}_FALLBACK"           # R1-01: DRIVER_VERIFIED is set only by sync_v3
            ev = self._append(task_id, "REVIEW_RECORDED", actor, {
                "review": rid, "commit": sha, "verdict": verdict, "problem": problem, "independent": independent,
                "independence_basis": ("reviewer differs from every implementer actor; verdict recomputed from the "
                                       "reviewer's output; exact commit named") if independent else
                ("reviewer is an implementer" if actor in implementers else f"unusable result: {problem}"),
                "raw_sha256": sha256(raw), "stored": str(store / f"{rid}.txt"), "redactions": nred,
                "mechanism": mechanism, "provenance": prov, "blocking": [f.get("id") for f in blocking]})
            self.db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)",
                            (task_id, rid, sha, actor, prov, verdict, int(independent), sha256(raw), ev["seq"]))
            # FB R1-03: a FIXED claim closes earlier review findings only when this review could decide
            # acceptance (fallback basis present, development not paused); otherwise it stays evidence only.
            decisive = independent and not self.development_paused() and self._fallback_basis(t) is not None
            if verdict is not None:
                for f in result.get("findings") or []:
                    self._add_finding(task_id, actor, f, rid, sha)
                for pf in result.get("prior_findings") or []:
                    if str(pf.get("status", "")).upper() != "FIXED" or not decisive:
                        continue
                    raw = str(pf.get("id") or "")
                    earlier = self.db.execute(
                        "SELECT finding_id, review_id FROM findings WHERE task_id=? AND status='OPEN' AND "
                        "review_id IS NOT NULL AND review_id<>?", (task_id, rid)).fetchall()
                    matches = [row for row in earlier if row["finding_id"] == raw]
                    if not matches:
                        matches = [row for row in earlier if row["finding_id"] == f"{row['review_id']}/{raw}"]
                    if len(matches) != 1:
                        continue  # A reused short ID does not identify which earlier review found it.
                    finding_id = matches[0]["finding_id"]
                    self.db.execute("UPDATE findings SET status='CLOSED', closed_by=? WHERE task_id=? AND "
                                    "finding_id=?", (actor, task_id, finding_id))
                    self._append(task_id, "FINDING_CLOSED", actor, {"id": finding_id, "commit": sha,
                                                                    "note": f"reviewer {rid}: FIXED"})
            if verdict == "REJECT" and self._task(task_id)["status"] in ("IN_REVIEW", "ACCEPTED"):
                self._append(task_id, "STATUS", "system:ledger", {"frm": self._task(task_id)["status"],
                                                                  "to": "REPAIR", "reason": f"{rid} REJECT"},
                             status="REPAIR", accepted_commit=None)
            return {"review": rid, "verdict": verdict, "independent": independent, "problem": problem,
                    "blocking": [f.get("id") for f in blocking]}

    def accept(self, task_id: str, actor: str) -> dict:
        """Review paths (owner clarification 2026-10-21): the Lifecycle V3 driver's independent review is primary.
        A review recorded here (subagent, session, a CLI run outside the driver) is a FALLBACK and counts only when a
        linked V3 run's hash chain shows the driver could not obtain an independent reviewer for this exact commit
        (blocker NO_INDEPENDENT_REVIEWER). A driver verdict on the commit is never overridden by a fallback one."""
        if self.db.execute("SELECT 1 FROM v3_links WHERE task_id=?", (task_id,)).fetchone():
            self.sync_v3(task_id)                  # read the driver's latest verdicts before deciding
        with self.tx():
            t = self._task(task_id)
            self._guard_dev(t, actor, "accept")
            self._require_integrity(task_id)
            why = self._acceptance_problems(t)
            if why:
                raise Refused("NOT ACCEPTED: " + "; ".join(why))
            rev, path, basis = self._accepting_review(t)
            return self._append(task_id, "ACCEPTED", actor, {"commit": t["head_commit"], "review": rev["review_id"],
                                                             "reviewer": rev["reviewer"],
                                                             "provenance": rev["provenance"],
                                                             "verdict": rev["verdict"], "review_path": path,
                                                             "fallback_basis": basis},
                                status="ACCEPTED", accepted_commit=t["head_commit"])

    def _accepting_review(self, t):
        """(review row, path, fallback basis) deciding acceptance of the current head, or (None, why, None).
        Primary: the latest DRIVER_VERIFIED verdict on the head. Fallback: the latest independent non-driver review,
        only with a fallback basis. Unverified V3 rounds never count."""
        rows = [r for r in self.db.execute("SELECT * FROM reviews WHERE task_id=? AND commit_sha=? ORDER BY seq DESC",
                                           (t["task_id"], t["head_commit"] or "")) if r["verdict"] is not None]
        primary = [r for r in rows if r["provenance"] == "DRIVER_VERIFIED"]
        if primary:
            if not self._driver_review_intact(t["task_id"], primary[0]):
                return None, "driver review evidence changed or is missing", None
            return primary[0], "PRIMARY_V3", None
        fallback = [r for r in rows if r["provenance"] not in ("DRIVER_VERIFIED", "V3_UNVERIFIED")]
        if not fallback:
            return None, "no review of the exact head commit", None
        basis = self._fallback_basis(t)
        if basis is None:
            return None, ("a fallback review counts only when the Lifecycle V3 driver could not obtain an independent "
                          "reviewer for this exact commit: link its V3 run (blocked NO_INDEPENDENT_REVIEWER on this "
                          "commit) or obtain the driver's review"), None
        return fallback[0], "FALLBACK", basis

    def _driver_review_intact(self, task_id: str, review: sqlite3.Row) -> bool:
        """Recheck the selected imported verdict against its linked V3 event chain and round artifact."""
        recorded = self.db.execute("SELECT data FROM events WHERE task_id=? AND seq=? AND kind='REVIEW_RECORDED'",
                                   (task_id, review["seq"])).fetchone()
        if recorded is None:
            return False
        d = json.loads(recorded["data"])
        sd = Path(d.get("v3_state_dir") or "")
        if not self.db.execute("SELECT 1 FROM v3_links WHERE task_id=? AND state_dir=?",
                               (task_id, str(sd))).fetchone():
            return False
        try:
            evs, broken = self._v3_chain(sd)
            if broken:
                return False
            source = next((e["data"] for e in evs if e["hash"] == d.get("v3_event_hash") and
                           e["kind"] == "REVIEW_RECORDED"), None)
            if source is None:
                return False
            rdir = sd / "rounds" / f"R{d.get('v3_round')}"
            raw = (rdir / "round.json").read_bytes()
            if sha256(raw) != review["raw_sha256"] or sha256(raw) != source.get("round_sha256"):
                return False
            # The reviewer's own output, bound in the driver's REVIEW_RECORDED event (same rule as lifecycle.verify).
            out = rdir / ("reviewer_result.txt" if source.get("imported") else "reviewer_stdout.txt")
            if out.is_file():
                if sha256(out.read_bytes()) != source.get("stdout_sha256"):
                    return False
            elif source.get("stdout_sha256"):
                return False
            artifact = json.loads(raw)
        except (OSError, ValueError, KeyError, TypeError):
            return False
        return (source.get("round") == d.get("v3_round") == artifact.get("round") and
                source.get("candidate") == d.get("commit") == review["commit_sha"] == artifact.get("candidate") and
                source.get("verdict") == d.get("verdict") == review["verdict"] == artifact.get("effective_verdict") and
                source.get("independent") is True and artifact.get("independent") is True and
                not source.get("imported") and source.get("status") == artifact.get("status") ==
                "COMPLETED_WITH_RESULT")

    def _fallback_basis(self, t) -> dict | None:
        """Evidence from a linked V3 run's intact hash chain that its reviewer chain is exhausted for this exact
        commit: the current blocker (as the chain records it, like lifecycle.chained_blocker) is
        NO_INDEPENDENT_REVIEWER and the run's current candidate is the task head."""
        for link in self.db.execute("SELECT state_dir FROM v3_links WHERE task_id=? ORDER BY state_dir",
                                    (t["task_id"],)).fetchall():
            sd = Path(link["state_dir"])
            if not (sd / "events.jsonl").is_file():
                continue
            evs, broken = self._v3_chain(sd)
            if broken:
                continue
            blocker, blocker_ev, cand = None, None, None
            for ev in evs:
                d, k = ev["data"], ev["kind"]
                if d.get("candidate"):
                    cand = d["candidate"]
                if k.startswith("REPAIR") and d.get("commit"):
                    cand = d["commit"]
                if k == "STAGE" and d.get("stage") == "BLOCKED":
                    blocker, blocker_ev = d.get("blocker"), ev
                elif k in ("OWNER_UNBLOCK", "REVIEWER_RECHECK") or (k == "STAGE" and d.get("stage") != "BLOCKED"):
                    blocker, blocker_ev = None, None
            if (blocker or {}).get("kind") == "NO_INDEPENDENT_REVIEWER" and cand == t["head_commit"]:
                return {"v3_state_dir": str(sd), "v3_event_seq": blocker_ev["seq"], "v3_event_hash": blocker_ev["hash"],
                        "reason": blocker.get("reason")}
        return None

    def _acceptance_problems(self, t) -> list[str]:
        why = []
        if t["status"] != "IN_REVIEW":
            why.append(f"status is {t['status']}, not IN_REVIEW")
        if not t["head_commit"]:
            why.append("no head commit recorded")
        rev, path, _ = self._accepting_review(t)
        if rev is None:
            why.append(path)
        else:
            if rev["verdict"] not in VERDICTS[:2]:
                why.append(f"latest review {rev['review_id']} of the head is {rev['verdict']}")
            if not rev["independent"]:
                why.append(f"review {rev['review_id']} is not independent")
            if rev["reviewer"] in self._implementers(t["task_id"]):
                why.append(f"reviewer {rev['reviewer']} also implemented this task")
        n = self.db.execute("SELECT COUNT(*) c FROM findings WHERE task_id=? AND status='OPEN' AND blocking=1",
                            (t["task_id"],)).fetchone()["c"]
        if n:
            why.append(f"{n} open blocking finding(s)")
        if t["head_commit"] and not self._passing_test(t):
            # Regression gates: a passing test result with its log on the exact commit, whatever the review path.
            why.append("no passing test result recorded on the exact head commit")
        if self._open_steps(t["task_id"]):
            why.append("open steps")
        drift = self._drift(t)
        if drift and "actual_head" in drift or (drift and drift.get("problem")):
            why.append(f"worktree does not match the head: {drift}")
        return why

    def _passing_test(self, t) -> dict | None:
        """The latest TEST event on the head, if it passed and its log still has the recorded hash (R1-03)."""
        for r in self.db.execute("SELECT data FROM events WHERE task_id=? AND kind='TEST' ORDER BY seq DESC",
                                 (t["task_id"],)):
            d = json.loads(r["data"])
            if d.get("commit") != t["head_commit"]:
                continue
            log = d.get("log") or {}
            p = Path(log.get("path") or "")
            ok = d.get("passed") is True and p.is_file() and sha256(p.read_bytes()) == log.get("sha256")
            return d if ok else None
        return None

    def mark_integrated(self, task_id: str, actor: str, target_ref: str, receipt: str) -> dict:
        """INTEGRATED only on evidence: the accepted commit is an ancestor of ``target_ref`` and a receipt that names
        it exists. Integration itself (and its owner approval) happens outside the ledger."""
        with self.tx():
            t = self._task(task_id)
            _require(actor, DEVELOPERS | {"owner"}, "mark integrated")
            if t["status"] != "ACCEPTED" or not t["accepted_commit"]:
                raise Refused(f"{task_id} is {t['status']}; only an ACCEPTED task can be marked integrated")
            self._require_integrity(task_id)
            if not t["worktree"]:
                raise Refused("needs a worktree to check ancestry")
            target = _resolve_commit(t["worktree"], target_ref)
            anc = subprocess.run([*GIT, "-C", t["worktree"], "merge-base", "--is-ancestor", t["accepted_commit"],
                                  target], env=GIT_ENV, capture_output=True).returncode == 0
            if not anc:
                raise Refused(f"{t['accepted_commit'][:12]} is not an ancestor of {target_ref} ({target[:12]})")
            rp = Path(receipt)
            if not rp.is_file() or t["accepted_commit"] not in rp.read_text(encoding="utf-8", errors="replace"):
                raise Refused("receipt missing or does not name the accepted commit")
            return self._append(task_id, "INTEGRATED", actor, {"commit": t["accepted_commit"], "target": target,
                                                               "target_ref": target_ref,
                                                               "receipt": str(rp.resolve()),
                                                               "receipt_sha256": sha256(rp.read_bytes())},
                                status="INTEGRATED")

    # ----------------------------------------------------------------- Lifecycle V3 link and import

    def link_v3(self, task_id: str, actor: str, state_dir: str) -> dict:
        sd = str(Path(state_dir).resolve())
        if not (Path(sd) / "events.jsonl").is_file():
            raise Refused(f"{sd} is not a Lifecycle V3 state directory (no events.jsonl)")
        with self.tx():
            t = self._task(task_id)
            _require(actor, DEVELOPERS | {"owner", "system"}, "link a V3 run")
            if t["status"] in TERMINAL:
                raise Refused(f"{task_id} is terminal")
            self.db.execute("INSERT OR IGNORE INTO v3_links VALUES(?,?,0)", (task_id, sd))
            return self._append(task_id, "V3_LINKED", actor, {"state_dir": sd})

    @staticmethod
    def _v3_chain(sd: Path) -> tuple[list[dict], str | None]:
        prev, evs = GENESIS, []
        for line in (sd / "events.jsonl").read_text(encoding="utf-8").splitlines():
            ev = json.loads(line)
            if ev.get("prev") != prev or ev.get("hash") != event_hash(ev):
                return evs, f"V3 chain broken at event {ev.get('seq')}"
            prev = ev["hash"]
            evs.append(ev)
        return evs, None

    def sync_v3(self, task_id: str, actor: str = "system:v3-sync") -> list[dict]:
        """Bring linked V3 runs into the task: each review round with V3's own acceptance conditions (independent,
        COMPLETED_WITH_RESULT, round.json bound by hash, not imported) becomes a DRIVER_VERIFIED review; any other
        round is recorded as V3_UNVERIFIED and never counts. V3 files are only read."""
        out = []
        with self.tx():
            t = self._task(task_id)
            for link in self.db.execute("SELECT * FROM v3_links WHERE task_id=?", (task_id,)).fetchall():
                sd = Path(link["state_dir"])
                evs, broken = self._v3_chain(sd)
                if broken:
                    self._append(task_id, "V3_SYNC_FAILED", actor, {"state_dir": str(sd), "why": broken})
                    out.append({"state_dir": str(sd), "error": broken})
                    continue
                new = [e for e in evs if e["seq"] > link["synced_seq"]]
                stage = None
                for e in new:
                    d = e["data"]
                    if e["kind"] == "STAGE":
                        stage = d.get("stage")
                    if e["kind"] != "REVIEW_RECORDED":
                        continue
                    f = sd / "rounds" / f"R{d.get('round')}" / "round.json"
                    ok = (not d.get("imported") and d.get("independent") is True and
                          d.get("status") == "COMPLETED_WITH_RESULT" and d.get("verdict") in VERDICTS and
                          f.is_file() and sha256(f.read_bytes()) == d.get("round_sha256"))
                    if ok:
                        r = json.loads(f.read_text(encoding="utf-8"))
                        ok = (r.get("round") == d.get("round") and r.get("candidate") == d.get("candidate") and
                              r.get("independent") is True and r.get("effective_verdict") == d.get("verdict") and
                              r.get("status") == "COMPLETED_WITH_RESULT")
                    n = self.db.execute("SELECT COUNT(*) c FROM reviews WHERE task_id=?",
                                        (task_id,)).fetchone()["c"] + 1
                    rid = f"V{n}"
                    prov = "DRIVER_VERIFIED" if ok else "V3_UNVERIFIED"
                    reviewer = f"v3:{(d.get('worker') or {}).get('provider') or d.get('provider') or 'reviewer'}" \
                               f"/{sd.parent.name}/R{d.get('round')}"
                    ev = self._append(task_id, "REVIEW_RECORDED", actor, {
                        "review": rid, "commit": d.get("candidate"), "verdict": d.get("verdict"),
                        "independent": ok, "provenance": prov, "v3_state_dir": str(sd), "v3_round": d.get("round"),
                        "v3_event_hash": e["hash"], "raw_sha256": d.get("round_sha256") or ""})
                    self.db.execute("INSERT INTO reviews VALUES(?,?,?,?,?,?,?,?,?)",
                                    (task_id, rid, d.get("candidate") or "", reviewer, prov, d.get("verdict"),
                                     int(ok), d.get("round_sha256") or "", ev["seq"]))
                    out.append({"review": rid, "round": d.get("round"), "provenance": prov})
                if new:
                    self.db.execute("UPDATE v3_links SET synced_seq=? WHERE task_id=? AND state_dir=?",
                                    (evs[-1]["seq"], task_id, str(sd)))
                    self._append(task_id, "V3_SYNCED", actor, {"state_dir": str(sd), "events": len(new),
                                                               "through_seq": evs[-1]["seq"],
                                                               "v3_chain_head": evs[-1]["hash"],
                                                               "last_stage": stage})
            _ = t
        return out

    def import_v3(self, root: str, actor: str = "system:import-v3") -> dict:
        """Migration: one task per V3 milestone (revision suffixes ``-rN``/``-cN`` grouped), each run dir linked and
        synced. Source files are hashed before and after; the report proves they were not changed."""
        root_p = Path(root).resolve()
        dirs = sorted({p.parent for p in root_p.rglob("events.jsonl")
                       if (p.parent / "state.json").is_file() and ".work" not in p.parts and "work" not in p.parts})
        before = {str(f): sha256(f.read_bytes()) for d in dirs for f in sorted(d.rglob("*"))
                  if f.is_file() and ".work" not in f.parts}
        report = {"root": str(root_p), "runs": [], "tasks": {}}
        for d in dirs:
            st = json.loads((d / "state.json").read_text(encoding="utf-8"))
            name = st.get("milestone") or d.parent.name
            base = re.sub(r"(-(r|c|u)\d+)+$", "", name)
            tid = "TASK-V3-" + sha256(f"uri-v3-milestone:{base}")[:12]
            if self.db.execute("SELECT 1 FROM tasks WHERE task_id=?", (tid,)).fetchone() is None:
                if parse_actor(actor)[0] == "system":
                    self._create(f"{base} (imported Lifecycle V3 milestone)", "", actor,
                                 milestone_ref=base, task_id=tid, import_source=d)
                else:
                    self.create(f"{base} (imported Lifecycle V3 milestone)", "", actor,
                                milestone_ref=base, task_id=tid)
            linked = self.db.execute("SELECT 1 FROM v3_links WHERE task_id=? AND state_dir=?",
                                     (tid, str(d))).fetchone()
            if not linked:
                self.link_v3(tid, actor, str(d))
            synced = self.sync_v3(tid, actor)
            report["runs"].append({"state_dir": str(d), "milestone": name, "task_id": tid,
                                   "v3_stage": st.get("stage"), "candidate": st.get("candidate"),
                                   "reviews": synced})
            report["tasks"].setdefault(tid, base)
        after = {str(f): sha256(f.read_bytes()) for d in dirs for f in sorted(d.rglob("*"))
                 if f.is_file() and ".work" not in f.parts}
        changed = sorted(k for k in before if before.get(k) != after.get(k))
        report["source_files"] = len(before)
        report["source_unchanged"] = not changed and before.keys() == after.keys()
        report["changed_during_import"] = changed
        return report

    # ----------------------------------------------------------------- summaries, handoff, verification

    def _summary(self, t) -> dict:
        tid = t["task_id"]
        nb = self.db.execute("SELECT COUNT(*) c FROM findings WHERE task_id=? AND status='OPEN' AND blocking=1",
                             (tid,)).fetchone()["c"]
        na = self.db.execute("SELECT text FROM context WHERE task_id=? AND kind='next_action' AND superseded=0 "
                             "ORDER BY id DESC LIMIT 1", (tid,)).fetchone()
        return {"task_id": tid, "milestone_ref": t["milestone_ref"], "title": t["title"], "status": t["status"],
                "version": t["version"], "updated_at": t["updated_at"], "head_commit": t["head_commit"],
                "last_verified_commit": t["last_verified_commit"], "accepted_commit": t["accepted_commit"],
                "open_blocking_findings": nb, "paused": t["status"] == "PAUSED", "chain_head": t["chain_head"],
                "next_action": na["text"] if na else None, "worktree": t["worktree"], "branch": t["branch"],
                "v3_runs": [r["state_dir"] for r in self.db.execute(
                    "SELECT state_dir FROM v3_links WHERE task_id=? ORDER BY state_dir", (tid,))]}

    def summaries(self, milestone_ref: str | None = None) -> list[dict]:
        """The Milestone Manager read contract (docs/dev_workflow/contracts/task_ledger_contract.json)."""
        return [self._summary(self._task(t["task_id"])) for t in self.list(milestone_ref)]

    def handoff(self, task_id: str, *, write: bool = True) -> dict:
        """Compact, self-sufficient handoff built from the ledger alone (no chat)."""
        t = self._task(task_id)
        s = self._summary(t)
        ctx = lambda kind: [dict(r) for r in self.db.execute(  # noqa: E731
            "SELECT * FROM context WHERE task_id=? AND kind=? AND superseded=0 ORDER BY id", (task_id, kind))]
        done_keys = {r["key"] for r in ctx("done") if r["key"]}
        steps = [dict(r) for r in self.db.execute("SELECT * FROM steps WHERE task_id=? ORDER BY rowid", (task_id,))]
        findings = [dict(r) for r in self.db.execute("SELECT * FROM findings WHERE task_id=? AND status='OPEN' "
                                                     "ORDER BY finding_id", (task_id,))]
        lv = t["last_verified_commit"]
        repo = t["worktree"] if t["worktree"] and Path(t["worktree"]).is_dir() else None
        verified = {"commit": lv, "exists": _commit_exists(repo, lv) if lv and repo else None}
        if lv and repo and t["branch"] and t["branch"] != "HEAD":
            verified["on_branch"] = subprocess.run([*GIT, "-C", repo, "merge-base", "--is-ancestor", lv,
                                                    t["branch"]], env=GIT_ENV, capture_output=True).returncode == 0
        perms = [r["text"] for r in ctx("permission")]
        if t["status"] == "ACCEPTED":
            perms.append("owner approval for canonical integration (DEC-041/DEC-076)")
        if t["status"] == "PAUSED" or self.development_paused():
            perms.append("Claude or Codex available again (development pause); Antigravity/subagents cannot resume")
        perms += [f"owner decision on finding {f['finding_id']}: {f['title']}" for f in findings if f["owner_decision"]]
        drift = self._drift(t)
        blocker = json.loads(t["blocker"]) if t["blocker"] else None
        next_action = s["next_action"]
        pre = []
        if t["status"] in ("INTERRUPTED", "PAUSED"):
            pre.append(f"check the worktree, then `task_ledger resume {task_id} --actor claude:<session>` "
                       f"(resumes to {t['resume_to'] or 'IN_PROGRESS'})")
        if t["status"] == "BLOCKED":
            pre.append(f"resolve blocker: {blocker}")
        if drift:
            pre.append(f"reconcile worktree drift {drift} (set-head or restore) before continuing")
        h = {
            "schema": "uri-dev/task-handoff/1", "generated_at": now_iso(), "task_id": task_id,
            "title": t["title"], "milestone_ref": t["milestone_ref"], "status": t["status"],
            "resume_to": t["resume_to"], "worktree": t["worktree"], "branch": t["branch"],
            "head_commit": t["head_commit"], "last_verified_commit": verified, "accepted_commit": t["accepted_commit"],
            "objective": [r["text"] for r in ctx("objective")],
            "constraints": [r["text"] for r in ctx("constraint") + ctx("requirement")],
            "decisions": [r["text"] for r in ctx("decision")],
            "completed": [f"{x['step_id']} {x['name']}" for x in steps if x["status"] == "COMPLETED"] +
                         [r["text"] for r in ctx("done")],
            "interrupted_steps": [f"{x['step_id']} {x['name']}" for x in steps if x["status"] == "INTERRUPTED"],
            "remaining": [r["text"] for r in ctx("todo") if r["key"] not in done_keys],
            "blocking_findings": [{"id": f["finding_id"], "severity": f["severity"], "title": f["title"]}
                                  for f in findings if f["blocking"]],
            "other_open_findings": [f["finding_id"] for f in findings if not f["blocking"]],
            "blocker": blocker, "worktree_drift": drift, "required_permissions": perms,
            "next_executable_action": " then ".join(pre + ([next_action] if next_action else [])) or None,
            "latest_tests": [r["text"] for r in ctx("test")][-3:],
            "v3_runs": s["v3_runs"], "chain_head": t["chain_head"], "version": t["version"],
            "ledger": str(self.path),
        }
        h, _ = redact_obj(h)
        if write:
            d = self.dir / "handoffs"
            atomic_write(d / f"{task_id}.json", json.dumps(h, indent=1, sort_keys=True).encode("utf-8"))
            atomic_write(d / f"{task_id}.md", handoff_markdown(h).encode("utf-8"))
        return h

    def _replay_errors(self, t) -> list[str]:
        """R3-03: every projection a decision reads (status, accepted/head/verified commits, milestone_ref, open
        findings, steps) must equal what the chained events define; an edited row is an integrity failure."""
        tid = t["task_id"]
        p = _replay((r["kind"], json.loads(r["data"])) for r in self.db.execute(
            "SELECT kind, data FROM events WHERE task_id=? ORDER BY seq", (tid,)))
        errs = [f"{tid} {k} is {t[k]!r} but the event chain says {p[k]!r}"
                for k in ("status", "accepted_commit", "head_commit", "last_verified_commit", "milestone_ref",
                          "resume_to") if t[k] != p[k]]
        errs += [f"{tid} {v}" for v in p["violations"]]
        rows = {r["finding_id"]: {"status": r["status"], "blocking": r["blocking"], "severity": r["severity"],
                                  "owner_decision": r["owner_decision"], "review_id": r["review_id"],
                                  "commit_sha": r["commit_sha"]} for r in self.db.execute(
            "SELECT finding_id, status, blocking, severity, owner_decision, review_id, commit_sha "
            "FROM findings WHERE task_id=?", (tid,))}
        if rows != p["findings"]:
            errs.append(f"{tid} findings differ from the event chain")
        steps = {r["step_id"]: r["status"] for r in self.db.execute(
            "SELECT step_id, status FROM steps WHERE task_id=?", (tid,))}
        if steps != p["steps"]:
            errs.append(f"{tid} steps differ from the event chain")
        return errs

    def history(self, task_id: str) -> list[dict]:
        return [{**dict(r), "data": json.loads(r["data"])} for r in self.db.execute(
            "SELECT seq, ts, kind, data, hash FROM events WHERE task_id=? ORDER BY seq", (task_id,))]

    def verify(self, task_id: str | None = None) -> list[str]:
        """Recompute every task's chain and check the projections against it."""
        errs = []
        tasks = [self._task(task_id)] if task_id else self.db.execute("SELECT * FROM tasks").fetchall()
        for t in tasks:
            tid, prev, n = t["task_id"], GENESIS, 0
            for r in self.db.execute("SELECT * FROM events WHERE task_id=? ORDER BY seq", (tid,)):
                n += 1
                ev = {"seq": r["seq"], "ts": r["ts"], "kind": r["kind"], "data": json.loads(r["data"]),
                      "prev": r["prev"]}
                if r["seq"] != n:
                    errs.append(f"{tid} event seq {r['seq']} out of order (expected {n})")
                if r["prev"] != prev or r["hash"] != event_hash(ev):
                    errs.append(f"{tid} event {r['seq']} chain broken")
                prev = r["hash"]
            if t["version"] != n or t["chain_head"] != prev:
                errs.append(f"{tid} task row (version {t['version']}) differs from its chain ({n} events)")
            errs += self._replay_errors(t)
            for c in self.db.execute("SELECT * FROM context WHERE task_id=?", (tid,)):
                if sha256(json.dumps([c["kind"], c["key"], c["text"], c["path"], c["blob"], c["commit_sha"]])) \
                        != c["sha"]:
                    errs.append(f"{tid} context {c['id']} changed after recording")
            recorded = {json.loads(r["data"])["review"]: json.loads(r["data"]) for r in self.db.execute(
                "SELECT data FROM events WHERE task_id=? AND kind='REVIEW_RECORDED'", (tid,))}
            for rv in self.db.execute("SELECT * FROM reviews WHERE task_id=?", (tid,)):
                d = recorded.get(rv["review_id"])
                if d is None or d.get("commit") != rv["commit_sha"] or d.get("verdict") != rv["verdict"] or \
                        bool(d.get("independent")) != bool(rv["independent"]):
                    errs.append(f"{tid} review {rv['review_id']} differs from its REVIEW_RECORDED event")
        return errs


def _replay(events) -> dict:
    """Status, commits, milestone_ref, open findings and step states as the event chain defines them."""
    p = {"status": None, "accepted_commit": None, "head_commit": None, "last_verified_commit": None,
         "milestone_ref": None, "resume_to": None, "findings": {}, "steps": {}, "violations": []}
    for kind, d in events:
        if kind == "CREATED":
            p.update(status="OPEN", milestone_ref=d.get("milestone_ref"),
                     head_commit=d.get("head") if re.fullmatch(r"[0-9a-f]{40}", str(d.get("head"))) else None)
        elif kind == "STATUS":
            if d.get("frm") == "ACCEPTED" or d.get("to") == "REPAIR":
                p["accepted_commit"] = None
            p["status"] = d.get("to")
        elif kind in ("UNBLOCKED", "RESUMED"):
            to = d.get("to")
            if to not in ("OPEN", "IN_PROGRESS", "IN_REVIEW", "REPAIR", "ACCEPTED") or \
                    (to == "ACCEPTED" and (not p["accepted_commit"] or p["accepted_commit"] != p["head_commit"])):
                p["violations"].append(f"{kind} to {to!r} without the evidence that status needs")
            p.update(status=to, resume_to=None)
        elif kind in ("BLOCKED", "INTERRUPTED"):
            p.update(status=kind, resume_to=d.get("resume_to", d.get("frm")))
        elif kind == "PAUSED":
            target = d.get("resume_to") or (p["resume_to"] if d.get("frm") in ("INTERRUPTED", "BLOCKED") and
                                            p["resume_to"] else d.get("frm"))
            p.update(status="PAUSED", resume_to=target)
        elif kind == "INTEGRATED":
            p["status"] = "INTEGRATED"
        elif kind == "ACCEPTED":
            p.update(status="ACCEPTED", accepted_commit=d.get("commit"))
        elif kind == "HEAD":
            p["head_commit"] = d.get("commit")
            if d.get("acceptance_invalidated"):
                if p["status"] == "ACCEPTED":
                    p["status"] = "IN_REVIEW"
                p["accepted_commit"] = None
        elif kind == "TEST" and d.get("passed") is True:
            p["last_verified_commit"] = d.get("commit")
        elif kind == "MILESTONE_REF":
            p["milestone_ref"] = d.get("milestone_ref")
        elif kind == "FINDING":
            p["findings"][d.get("id")] = {"status": "OPEN", "blocking": int(bool(d.get("blocking"))),
                                          "severity": d.get("severity"),
                                          "owner_decision": int(bool(d.get("owner_decision"))),
                                          "review_id": d.get("review"), "commit_sha": d.get("commit")}
        elif kind == "FINDING_CLOSED" and d.get("id") in p["findings"]:
            p["findings"][d.get("id")]["status"] = "CLOSED"
        elif kind == "STEP_STARTED":
            p["steps"][d.get("step")] = "STARTED"
        elif kind == "STEP_ENDED":
            p["steps"][d.get("step")] = d.get("status")
        elif kind == "STEP_INTERRUPTED":
            p["steps"][d.get("step")] = "INTERRUPTED"
    return p


def handoff_markdown(h: dict) -> str:
    def lst(xs):
        return "\n".join(f"- {x}" for x in xs) if xs else "- (none)"
    lv = h["last_verified_commit"]
    return f"""# Handoff {h['task_id']} — {h['title']}

Generated {h['generated_at']} from the task ledger only (`{h['ledger']}`), chain head `{h['chain_head'][:16]}`, version {h['version']}.

| | |
|---|---|
| Status | **{h['status']}**{f" (resumes to {h['resume_to']})" if h['resume_to'] else ''} |
| Milestone ref | {h['milestone_ref']} |
| Worktree / branch | `{h['worktree']}` / `{h['branch']}` |
| Head commit | `{h['head_commit']}` |
| Last verified commit | `{lv.get('commit')}` (exists: {lv.get('exists')}, on branch: {lv.get('on_branch')}) |
| Accepted commit | `{h['accepted_commit']}` |

## Next executable action
{h['next_executable_action'] or '(none recorded)'}

## Objective
{lst(h['objective'])}

## Constraints and requirements
{lst(h['constraints'])}

## Decisions
{lst(h['decisions'])}

## Completed
{lst(h['completed'])}

## Remaining
{lst(h['remaining'])}

## Blocking findings
{lst([f"{f['id']} ({f['severity']}): {f['title']}" for f in h['blocking_findings']])}

## Required permissions
{lst(h['required_permissions'])}

## Interrupted steps / drift / blocker
{lst(h['interrupted_steps'] + ([f"worktree drift: {h['worktree_drift']}"] if h['worktree_drift'] else []) + ([f"blocker: {h['blocker']}"] if h['blocker'] else []))}

## Latest tests
{lst(h['latest_tests'])}
"""


# --------------------------------------------------------------------------- benchmark (AC-12)

def bench(n_events: int = 1000, n_context: int = 200) -> dict:
    """V3 ``State.event`` vs ledger event append at equal counts, plus retrieval latency. No GPU, temp dirs only."""
    import tempfile
    import tracemalloc
    from scripts.dev_workflow.lifecycle import State
    out = {"n_events": n_events}
    with tempfile.TemporaryDirectory() as td:
        st = State({"state_dir": str(Path(td) / "v3"), "milestone": "BENCH"})
        t0 = time.perf_counter()
        for i in range(n_events):
            st.event("BENCH", i=i, note="x" * 64)
        v3 = time.perf_counter() - t0
        v3_bytes = sum(f.stat().st_size for f in (Path(td) / "v3").iterdir())
        tracemalloc.start()
        t0 = time.perf_counter()
        lg = Ledger(Path(td) / "ledger.sqlite3")
        startup = time.perf_counter() - t0
        tid = lg.create("bench", "bench objective", "claude:bench")
        t0 = time.perf_counter()
        for i in range(n_events):
            with lg.tx():
                lg._append(tid, "BENCH", "claude:bench", {"i": i, "note": "x" * 64})
        led = time.perf_counter() - t0
        for i in range(n_context):
            lg.add_context(tid, "claude:bench", "evidence", f"evidence item {i} about module_{i % 17} " + "y" * 200)
        t0 = time.perf_counter()
        p1 = lg.packet(tid, query="module_3")
        miss = time.perf_counter() - t0
        t0 = time.perf_counter()
        p2 = lg.packet(tid, query="module_3")
        hit = time.perf_counter() - t0
        peak = tracemalloc.get_traced_memory()[1]
        tracemalloc.stop()
        lg.close()
        led_bytes = sum(f.stat().st_size for f in Path(td).glob("ledger.sqlite3*"))
        out.update({
            "v3_append_total_s": round(v3, 3), "v3_append_ms_per_event": round(1000 * v3 / n_events, 3),
            "v3_bytes": v3_bytes,
            "ledger_startup_ms": round(1000 * startup, 2),
            "ledger_append_total_s": round(led, 3), "ledger_append_ms_per_event": round(1000 * led / n_events, 3),
            "ledger_bytes": led_bytes,
            "packet_miss_ms": round(1000 * miss, 2), "packet_hit_ms": round(1000 * hit, 2),
            "packet_cache": [p1["cache"], p2["cache"]], "packet_items": len(p1["items"]),
            "python_peak_alloc_kib": round(peak / 1024, 1), "gpu": "none used"})
    return out


# --------------------------------------------------------------------------- CLI

def _out(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="task_ledger", description=__doc__.split("\n\n")[0])
    ap.add_argument("--ledger", help="ledger file (default: $URI_TASK_LEDGER or ~/.uri-dev/task_ledger.sqlite3)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def cmd(name, *args, actor=True):
        p = sub.add_parser(name)
        for a in args:
            p.add_argument(a) if not a.startswith("-") else None
        if actor:
            p.add_argument("--actor", required=True, help="kind:id, e.g. claude:<session> or subagent:<agent id>")
        return p

    p = cmd("new"); p.add_argument("--title", required=True); p.add_argument("--objective", default="")
    p.add_argument("--milestone"); p.add_argument("--worktree"); p.add_argument("--branch")
    p = cmd("show", "task", actor=False)
    p = cmd("list", actor=False); p.add_argument("--milestone")
    p = cmd("summary", actor=False); p.add_argument("--milestone"); p.add_argument("--json", action="store_true")
    p = cmd("status", "task", "to"); p.add_argument("--reason", default=""); p.add_argument("--expected-version", type=int)
    p = cmd("block", "task"); p.add_argument("--reason", required=True); p.add_argument("--needs", required=True)
    p = cmd("unblock", "task"); p.add_argument("--note", required=True)
    p = cmd("milestone-ref", "task", "ref")
    p = cmd("head", "task", "commit")
    p = cmd("test", "task", "commit"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--pass", dest="passed", action="store_true"); g.add_argument("--fail", dest="failed",
                                                                               action="store_true")
    p.add_argument("--summary", required=True); p.add_argument("--log", help="required with --pass")
    p = cmd("add", "task", "kind", "text"); p.add_argument("--key"); p.add_argument("--path"); p.add_argument("--commit")
    p.add_argument("--ttl", type=float)
    p = cmd("context", "task", actor=False); p.add_argument("--budget", type=int, default=6000)
    p.add_argument("--query", default=""); p.add_argument("--item-chars", type=int, default=600)
    p.add_argument("--no-cache", action="store_true")
    p = cmd("context-get", "task", "sha", actor=False)
    p = cmd("claim", "task"); p.add_argument("--ttl", type=float, default=900.0)
    p = cmd("step-start", "task", "name")
    p = cmd("step-end", "task", "step"); g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--ok", action="store_true"); g.add_argument("--failed", action="store_true")
    p.add_argument("--note", default="")
    p = cmd("acquire", "resources"); p.add_argument("--task"); p.add_argument("--ttl", type=float, default=900.0)
    p = cmd("release", "resource", "token")
    p = cmd("leases", actor=False)
    p = cmd("recover"); p.set_defaults(actor_default="system:recover")
    p = cmd("resume", "task"); p.add_argument("--note", default="")
    p = cmd("availability"); p.add_argument("--dev", required=True, choices=sorted(DEVELOPERS))
    g = p.add_mutually_exclusive_group(required=True); g.add_argument("--available", action="store_true")
    g.add_argument("--unavailable", action="store_true"); p.add_argument("--reason", default="")
    p = cmd("finding", "task", "id"); p.add_argument("--severity", required=True); p.add_argument("--title", required=True)
    p.add_argument("--blocking", choices=["true", "false"]); p.add_argument("--owner-decision", action="store_true")
    p = cmd("finding-close", "task", "id"); p.add_argument("--commit", required=True); p.add_argument("--note", required=True)
    p = cmd("review", "task", "commit", "output"); p.add_argument("--mechanism", default="")
    p = cmd("accept", "task")
    p = cmd("integrated", "task"); p.add_argument("--target", required=True); p.add_argument("--receipt", required=True)
    p = cmd("link-v3", "task", "state_dir")
    p = cmd("sync-v3", "task")
    p = cmd("import-v3", "root")
    p = cmd("handoff", "task", actor=False); p.add_argument("--no-write", action="store_true")
    p = cmd("history", "task", actor=False)
    p = cmd("verify", actor=False); p.add_argument("--task")
    p = cmd("bench", actor=False); p.add_argument("--events", type=int, default=1000)
    a = ap.parse_args(argv)
    if a.cmd == "bench":
        _out(bench(a.events))
        return 0
    lg = Ledger(a.ledger)
    try:
        c = a.cmd
        if c == "new":
            tid = lg.create(a.title, a.objective, a.actor, milestone_ref=a.milestone, worktree=a.worktree,
                            branch=a.branch)
            _out(lg._summary(lg._task(tid)))
        elif c == "show":
            _out({**lg._summary(lg._task(a.task)), "resume_to": lg.get(a.task)["resume_to"]})
        elif c == "list":
            _out([{k: t[k] for k in ("task_id", "status", "milestone_ref", "title", "updated_at")}
                  for t in lg.list(a.milestone)])
        elif c == "summary":
            # Milestone Manager contract: a summary is never served from a ledger whose chains fail verification.
            rows = lg.summaries(a.milestone)
            errs = [e for r in rows for e in lg.verify(r["task_id"])]
            if errs:
                sys.stderr.write("LEDGER_INTEGRITY_FAILED: " + "; ".join(errs[:10]) + "\n")
                return 4
            _out(rows)
        elif c == "status":
            _out(lg.transition(a.task, a.to, a.actor, a.reason, expected_version=a.expected_version))
        elif c == "block":
            _out(lg.block(a.task, a.actor, a.reason, a.needs))
        elif c == "unblock":
            _out(lg.unblock(a.task, a.actor, a.note))
        elif c == "milestone-ref":
            _out(lg.set_milestone_ref(a.task, a.actor, a.ref or None))
        elif c == "head":
            _out(lg.set_head(a.task, a.actor, a.commit))
        elif c == "test":
            _out(lg.record_test(a.task, a.actor, a.commit, a.passed, a.summary, a.log))
        elif c == "add":
            _out(lg.add_context(a.task, a.actor, a.kind, a.text, key=a.key, path=a.path, commit=a.commit,
                                ttl_s=a.ttl))
        elif c == "context":
            _out(lg.packet(a.task, budget=a.budget, query=a.query, item_chars=a.item_chars, use_cache=not a.no_cache))
        elif c == "context-get":
            _out(lg.context_get(a.task, a.sha))
        elif c == "claim":
            _out({"token": lg.claim(a.task, a.actor, a.ttl)})
        elif c == "step-start":
            _out({"step": lg.step_start(a.task, a.actor, a.name)})
        elif c == "step-end":
            _out(lg.step_end(a.task, a.actor, a.step, a.ok, a.note))
        elif c == "acquire":
            _out(lg.acquire(a.task, a.actor, [r for r in a.resources.split(",") if r], a.ttl))
        elif c == "release":
            lg.release(a.actor, a.resource, int(a.token))
            _out({"released": a.resource})
        elif c == "leases":
            _out(lg.leases())
        elif c == "recover":
            _out(lg.recover(a.actor))
        elif c == "resume":
            _out(lg.resume(a.task, a.actor, a.note))
        elif c == "availability":
            _out({"paused_tasks": lg.set_availability(a.actor, a.dev, a.available, a.reason),
                  "development_paused": lg.development_paused()})
        elif c == "finding":
            _out(lg.add_finding(a.task, a.actor, a.id, a.severity, a.title,
                                None if a.blocking is None else a.blocking == "true", a.owner_decision))
        elif c == "finding-close":
            _out(lg.close_finding(a.task, a.actor, a.id, a.commit, a.note))
        elif c == "review":
            _out(lg.record_review(a.task, a.actor, a.commit, a.output, mechanism=a.mechanism))
        elif c == "accept":
            _out(lg.accept(a.task, a.actor))
        elif c == "integrated":
            _out(lg.mark_integrated(a.task, a.actor, a.target, a.receipt))
        elif c == "link-v3":
            _out(lg.link_v3(a.task, a.actor, a.state_dir))
        elif c == "sync-v3":
            _out(lg.sync_v3(a.task, a.actor))
        elif c == "import-v3":
            _out(lg.import_v3(a.root, a.actor))
        elif c == "handoff":
            _out(lg.handoff(a.task, write=not a.no_write))
        elif c == "history":
            _out(lg.history(a.task))
        elif c == "verify":
            errs = lg.verify(a.task)
            _out({"ok": not errs, "errors": errs})
            return 0 if not errs else 4
        return 0
    except Refused as e:
        sys.stderr.write(f"REFUSED: {e}\n")
        return 3
    except LedgerError as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 2
    finally:
        lg.close()


if __name__ == "__main__":
    sys.exit(main())
