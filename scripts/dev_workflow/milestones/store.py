"""Append-only, hash-chained, crash-safe event store for the Milestone Manager.

Layout of a ledger home (see docs/milestone_manager/MILESTONE_MANAGER_ARCHITECTURE.md section 3):

    <home>/mm.json                config (schema, host id, autocommit)
    <home>/events/<host>.jsonl    one append-only segment per host; each line is one event
    <home>/cache/projection.json  disposable fold cache (owned by service.py)
    <home>/quarantine/            torn tails moved aside by recover()
    <home>/.lock                  OS lock file

Guarantees:
- every append is flushed and fsynced before the call returns;
- an event's ``hash`` is sha256 over its canonical JSON without ``hash``; ``prev`` is the previous hash in the same
  segment (genesis 64 zeros), so editing, deleting, inserting or reordering a line breaks the chain;
- a torn last line (power loss mid-write) is ignored by reads, reported by verify() and moved aside by recover();
- writers are serialised by an OS lock that the OS releases when the process dies (no stale lock files).

Tamper-evident, not tamper-proof: whoever can rewrite a whole segment can rebuild a consistent chain. Anchor the
head hashes by committing the ledger to git (autocommit) or recording them elsewhere.
"""
from __future__ import annotations

import contextlib
import datetime
import hashlib
import json
import os
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

SCHEMA = "uri-mm-ledger/1"
EVENT_VERSION = 1
GENESIS = "0" * 64
HOST_RE = re.compile(r"^[a-z0-9][a-z0-9_-]{0,47}$")
LOCK_TIMEOUT_S = 30.0
# Git as the lifecycle driver runs it: no hooks, no replace refs, no fsmonitor (lifecycle.py GIT).
GIT = ["git", "--no-replace-objects", "-c", "core.hooksPath=" + os.devnull, "-c", "core.fsmonitor=false"]


class StoreError(Exception):
    """A store-level refusal; ``code`` is a stable machine-readable reason."""

    def __init__(self, code: str, message: str):
        super().__init__(f"{code}: {message}")
        self.code = code


def utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def canonical(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def event_hash(ev: dict) -> str:
    return sha256_text(canonical({k: v for k, v in ev.items() if k != "hash"}))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def default_host_id() -> str:
    raw = re.sub(r"[^a-z0-9_-]", "-", socket.gethostname().lower()).strip("-") or "host"
    return raw[:48]


def atomic_write_bytes(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` via a temp file, fsync and rename (exact bytes, no newline translation)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    with tmp.open("wb") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


# --------------------------------------------------------------------------- OS lock

@contextlib.contextmanager
def os_lock(path: Path, timeout: float = LOCK_TIMEOUT_S):
    """Exclusive inter-process lock on ``path``. Released by the OS if the holder dies."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(path), os.O_RDWR | os.O_CREAT, 0o600)
    deadline = time.monotonic() + timeout
    try:
        if sys.platform == "win32":
            import msvcrt
            while True:
                try:
                    os.lseek(fd, 0, os.SEEK_SET)
                    msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise StoreError("LOCK_TIMEOUT", f"ledger lock {path} busy for {timeout:.0f}s")
                    time.sleep(0.02)
            try:
                yield
            finally:
                os.lseek(fd, 0, os.SEEK_SET)
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
        else:
            import fcntl
            while True:
                try:
                    fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    break
                except OSError:
                    if time.monotonic() > deadline:
                        raise StoreError("LOCK_TIMEOUT", f"ledger lock {path} busy for {timeout:.0f}s")
                    time.sleep(0.02)
            try:
                yield
            finally:
                fcntl.flock(fd, fcntl.LOCK_UN)
    finally:
        os.close(fd)


# --------------------------------------------------------------------------- segment reading

class Segment:
    """Parsed view of one segment file: complete events, the byte length they cover, and any torn tail."""

    def __init__(self, name: str, events: list[dict], good_bytes: int, torn: bytes, errors: list[str]):
        self.name = name
        self.events = events
        self.good_bytes = good_bytes
        self.torn = torn
        self.errors = errors

    @property
    def head(self) -> str:
        return self.events[-1]["hash"] if self.events else GENESIS


def read_segment(path: Path, start: int = 0, prev: str | None = None, seq0: int = 0) -> Segment:
    """Read events from byte ``start``. ``prev``/``seq0`` continue the chain check from an earlier read."""
    name = path.stem
    data = path.read_bytes() if path.is_file() else b""
    body = data[start:]
    nl = body.rfind(b"\n")
    complete, torn = (body[: nl + 1], body[nl + 1:]) if nl >= 0 else (b"", body)
    events, errors = [], []
    prev = GENESIS if prev is None else prev
    seq = seq0
    for i, line in enumerate(complete.split(b"\n")[:-1]):
        try:
            ev = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            errors.append(f"{name}: line {seq + 1} is not valid JSON ({e.__class__.__name__})")
            seq += 1
            continue
        seq += 1
        if not isinstance(ev, dict) or "hash" not in ev:
            errors.append(f"{name}: line {seq} is not an event object")
            continue
        if ev.get("seg") != name:
            errors.append(f"{name}: event {seq} names segment {ev.get('seg')!r}")
        if ev.get("seq") != seq:
            errors.append(f"{name}: event at line {seq} has seq {ev.get('seq')!r} (inserted, deleted or reordered)")
        if ev.get("prev") != prev:
            errors.append(f"{name}: event {seq} prev does not match the previous hash (chain broken)")
        if event_hash(ev) != ev["hash"]:
            errors.append(f"{name}: event {seq} content does not match its hash (edited)")
        prev = ev["hash"]
        events.append(ev)
    return Segment(name, events, start + len(complete), torn, errors)


# --------------------------------------------------------------------------- store

class EventStore:
    def __init__(self, home: str | os.PathLike):
        self.home = Path(home)
        self.config_path = self.home / "mm.json"
        self.events_dir = self.home / "events"
        self.lock_path = self.home / ".lock"
        self.quarantine_dir = self.home / "quarantine"
        if not self.config_path.is_file():
            raise StoreError("NOT_INITIALISED", f"{self.home} has no mm.json; run `init` first")
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        if self.config.get("schema") != SCHEMA:
            raise StoreError("SCHEMA", f"unsupported ledger schema {self.config.get('schema')!r}")
        self.host = self.config["host_id"]
        self.segment_path = self.events_dir / f"{self.host}.jsonl"
        self._tail = None  # (good_bytes, head, seq) of our own segment, valid only while the lock is held

    # ---- creation

    @staticmethod
    def init(home: str | os.PathLike, host_id: str | None = None, autocommit: bool = False) -> "EventStore":
        home = Path(home)
        host_id = host_id or default_host_id()
        if not HOST_RE.match(host_id):
            raise StoreError("BAD_HOST_ID", f"host id must match {HOST_RE.pattern}")
        cfg_path = home / "mm.json"
        if cfg_path.is_file():
            raise StoreError("ALREADY_INITIALISED", f"{cfg_path} exists")
        (home / "events").mkdir(parents=True, exist_ok=True)
        cfg = {"schema": SCHEMA, "host_id": host_id, "autocommit": bool(autocommit), "created_at": utc_now()}
        atomic_write_bytes(cfg_path, (json.dumps(cfg, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        return EventStore(home)

    # ---- locking

    @contextlib.contextmanager
    def locked(self):
        with os_lock(self.lock_path):
            self._tail = None
            try:
                yield self
            finally:
                self._tail = None

    # ---- reading

    def segment_paths(self) -> list[Path]:
        return sorted(self.events_dir.glob("*.jsonl")) if self.events_dir.is_dir() else []

    def read_all(self) -> list[Segment]:
        return [read_segment(p) for p in self.segment_paths()]

    # ---- writing

    def append(self, kind: str, data: dict, actor: str, session: str | None = None, base: dict | None = None,
               ts: str | None = None) -> dict:
        """Append one event to this host's segment. Caller must hold the lock (``with store.locked():``)."""
        if self._tail is None:
            seg = read_segment(self.segment_path)
            if seg.torn:
                raise StoreError("TORN_TAIL", f"{self.segment_path.name} ends with {len(seg.torn)} incomplete "
                                              "bytes; run `recover` first")
            if seg.errors:
                raise StoreError("CHAIN_BROKEN", "; ".join(seg.errors[:3]))
            self._tail = (seg.good_bytes, seg.head, len(seg.events))
        good, head, count = self._tail
        ev = {"v": EVENT_VERSION, "seg": self.host, "seq": count + 1, "ts": ts or utc_now(), "actor": actor,
              "session": session, "kind": kind, "data": data, "base": base or {}, "prev": head}
        ev["hash"] = event_hash(ev)
        line = (canonical(ev) + "\n").encode("utf-8")
        self.events_dir.mkdir(parents=True, exist_ok=True)
        with self.segment_path.open("ab") as f:
            if f.tell() != good:
                raise StoreError("CONCURRENT_WRITE", f"{self.segment_path.name} changed outside the lock")
            f.write(line)
            f.flush()
            os.fsync(f.fileno())
        self._tail = (good + len(line), ev["hash"], count + 1)
        return ev

    # ---- verification and recovery

    def verify(self) -> dict:
        segs = self.read_all()
        errors, torn, heads, total = [], [], {}, 0
        seen_names = set()
        for s in segs:
            errors.extend(s.errors)
            if s.torn:
                torn.append({"segment": s.name, "bytes": len(s.torn)})
            heads[s.name] = {"events": len(s.events), "head": s.head}
            total += len(s.events)
            if s.name in seen_names:
                errors.append(f"duplicate segment {s.name}")
            seen_names.add(s.name)
        report = {"ok": not errors and not torn, "events": total, "segments": heads, "errors": errors, "torn": torn}
        report["git"] = self.git_state()
        return report

    def recover(self, actor: str, session: str | None = None) -> dict:
        """Move a torn tail of this host's segment to quarantine and record that as an event."""
        with self.locked():
            seg = read_segment(self.segment_path)
            if seg.errors:
                raise StoreError("CHAIN_BROKEN", "recover only repairs a torn tail; chain errors need an owner "
                                                 "decision: " + "; ".join(seg.errors[:3]))
            if not seg.torn:
                return {"recovered": False}
            self.quarantine_dir.mkdir(parents=True, exist_ok=True)
            qname = f"{self.host}.{utc_now().replace(':', '').replace('.', '')}.torn"
            atomic_write_bytes(self.quarantine_dir / qname, seg.torn)
            with self.segment_path.open("r+b") as f:
                f.truncate(seg.good_bytes)
                f.flush()
                os.fsync(f.fileno())
            info = {"segment": self.host, "bytes": len(seg.torn), "sha256": hashlib.sha256(seg.torn).hexdigest(),
                    "quarantine": f"quarantine/{qname}"}
            self.append("STORE_RECOVERED", info, actor=actor, session=session)
            self.autocommit("STORE_RECOVERED")
            return {"recovered": True, **info}

    # ---- git durability

    def _git(self, *args, check=False):
        return subprocess.run([*GIT, "-C", str(self.home), *args], capture_output=True, text=True,
                              encoding="utf-8", errors="replace")

    def in_git(self) -> bool:
        try:
            p = self._git("rev-parse", "--is-inside-work-tree")
        except OSError:
            return False
        return p.returncode == 0 and p.stdout.strip() == "true"

    def git_state(self) -> dict:
        if not self.in_git():
            return {"tracked": False}
        p = self._git("status", "--porcelain", "--", "events", "mm.json")
        dirty = [line[3:] for line in p.stdout.splitlines() if line.strip()]
        return {"tracked": True, "uncommitted": dirty}

    def autocommit(self, label: str) -> dict:
        """Commit the event segments when the home is a git work tree and autocommit is on. Never pushes.

        A failure is reported, not raised: the event is already fsynced; verify() shows uncommitted segments."""
        if not self.config.get("autocommit") or not self.in_git():
            return {"committed": False}
        add = self._git("add", "--", "events", "mm.json")
        if add.returncode:
            return {"committed": False, "error": add.stderr.strip()[:300]}
        if not self._git("diff", "--cached", "--quiet").returncode:
            return {"committed": False}
        c = self._git("-c", "user.name=URI Milestone Manager", "-c", "user.email=mm@uri.local",
                      "commit", "--no-verify", "-q", "-m", f"mm: {label}")
        return {"committed": c.returncode == 0, **({"error": c.stderr.strip()[:300]} if c.returncode else {})}
