"""Append-only, hash-chained, crash-safe event store for the Milestone Manager.

Layout of a ledger home (see docs/milestone_manager/MILESTONE_MANAGER_ARCHITECTURE.md section 3):

    <home>/mm.json                shared config (schema, autocommit, decision id namespace); git-tracked
    <home>/events/<host>.jsonl    one append-only segment per host; each line is one event; git-tracked
    <home>/local/host.json        this machine's host id (never tracked: a clone must run `init-host`)
    <home>/local/anchors.json     this machine's per-segment high-water marks (never tracked; review R2-04)
    <home>/.gitignore             ignores local/ and .lock
    (no projection cache: every read and write folds the verified log; review R1-02)
    <home>/quarantine/            torn tails moved aside by recover()
    <home>/.lock                  OS lock file

Guarantees:
- every append is flushed and fsynced before the call returns;
- an event's ``hash`` is sha256 over its canonical JSON without ``hash``; ``prev`` is the previous hash in the same
  segment (genesis 64 zeros), so editing, inserting, reordering or deleting a line *before the last one* breaks the
  chain. Deleting the newest line(s) leaves a valid shorter chain; that is detected against ``local/anchors.json``
  (and, stronger, against git history when autocommit is on), not by the chain itself. A missing or unreadable
  anchors file while events exist is itself an integrity error (review R2-03); `reanchor` records an explicit reset;
- timestamps never go backwards inside a segment, and segments are merged preserving each segment's order
  (review R2-06);
- several events written by one command form a batch that is written with a single write + fsync; the fold applies
  a batch only when all its events are present, so a crash never leaves half a command applied;
- events after the first chain error in a segment are never trusted (``Segment.valid_events``);
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
    # Windows refuses to replace a file another process has open (a reader); retry briefly (review R2-02).
    for attempt in range(40):
        try:
            os.replace(tmp, path)
            return
        except PermissionError:
            if attempt == 39:
                raise
            time.sleep(0.025 * (attempt + 1))


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

    def __init__(self, name: str, events: list[dict], good_bytes: int, torn: bytes, errors: list[str],
                 first_bad: int | None = None):
        self.name = name
        self.events = events
        self.good_bytes = good_bytes
        self.torn = torn
        self.errors = errors
        self.first_bad = first_bad  # index into ``events`` of the first untrustworthy event, or None

    @property
    def valid_events(self) -> list[dict]:
        """The trusted prefix: every event before the first chain, hash, sequence or parse error."""
        return self.events if self.first_bad is None else self.events[: self.first_bad]

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
    events, errors, first_bad = [], [], None
    prev = GENESIS if prev is None else prev
    seq = seq0
    for i, line in enumerate(complete.split(b"\n")[:-1]):
        n_err = len(errors)
        try:
            ev = json.loads(line.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            errors.append(f"{name}: line {seq + 1} is not valid JSON ({e.__class__.__name__})")
            seq += 1
            first_bad = len(events) if first_bad is None else first_bad
            continue
        seq += 1
        if not isinstance(ev, dict) or "hash" not in ev:
            errors.append(f"{name}: line {seq} is not an event object")
            first_bad = len(events) if first_bad is None else first_bad
            continue
        if ev.get("seg") != name:
            errors.append(f"{name}: event {seq} names segment {ev.get('seg')!r}")
        if ev.get("seq") != seq:
            errors.append(f"{name}: event at line {seq} has seq {ev.get('seq')!r} (inserted, deleted or reordered)")
        if ev.get("prev") != prev:
            errors.append(f"{name}: event {seq} prev does not match the previous hash (chain broken)")
        if event_hash(ev) != ev["hash"]:
            errors.append(f"{name}: event {seq} content does not match its hash (edited)")
        if len(errors) > n_err and first_bad is None:
            first_bad = len(events)
        prev = ev["hash"]
        events.append(ev)
    return Segment(name, events, start + len(complete), torn, errors, first_bad)


# --------------------------------------------------------------------------- store

class EventStore:
    def __init__(self, home: str | os.PathLike):
        self.home = Path(home)
        self.config_path = self.home / "mm.json"
        self.events_dir = self.home / "events"
        self.local_dir = self.home / "local"
        self.host_path = self.local_dir / "host.json"
        self.lock_path = self.home / ".lock"
        self.quarantine_dir = self.home / "quarantine"
        if not self.config_path.is_file():
            raise StoreError("NOT_INITIALISED", f"{self.home} has no mm.json; run `init` first")
        self.config = json.loads(self.config_path.read_text(encoding="utf-8"))
        if self.config.get("schema") != SCHEMA:
            raise StoreError("SCHEMA", f"unsupported ledger schema {self.config.get('schema')!r}")
        try:
            self.host = json.loads(self.host_path.read_text(encoding="utf-8"))["host_id"]
        except (OSError, ValueError, KeyError, TypeError):
            raise StoreError("NO_HOST_ID", f"{self.host_path} is missing: this machine has no host id for this "
                                           "ledger (a clone must run `init-host --host-id <new id>`)")
        if not HOST_RE.match(str(self.host)):
            raise StoreError("BAD_HOST_ID", f"host id must match {HOST_RE.pattern}")
        self.segment_path = self.events_dir / f"{self.host}.jsonl"
        self._tail = None  # (good_bytes, head, count, last_ts) of our own segment, valid only while locked

    # ---- creation

    @staticmethod
    def _write_local(home: Path, host_id: str) -> None:
        if not HOST_RE.match(host_id or ""):
            raise StoreError("BAD_HOST_ID", f"host id must match {HOST_RE.pattern}")
        atomic_write_bytes(home / "local" / "host.json",
                           (json.dumps({"host_id": host_id, "registered_at": utc_now()}, indent=1) + "\n").encode())
        gi = home / ".gitignore"
        if not gi.is_file():
            atomic_write_bytes(gi, b"local/\n.lock\n*.tmp\n")

    @staticmethod
    def init(home: str | os.PathLike, host_id: str | None = None, autocommit: bool = False) -> "EventStore":
        home = Path(home)
        host_id = host_id or default_host_id()
        if not HOST_RE.match(host_id):
            raise StoreError("BAD_HOST_ID", f"host id must match {HOST_RE.pattern}")
        cfg_path = home / "mm.json"
        if cfg_path.is_file():
            raise StoreError("ALREADY_INITIALISED", f"{cfg_path} exists (a clone uses `init-host`)")
        (home / "events").mkdir(parents=True, exist_ok=True)
        cfg = {"schema": SCHEMA, "autocommit": bool(autocommit), "created_at": utc_now(), "dec_namespace": "LDEC"}
        atomic_write_bytes(cfg_path, (json.dumps(cfg, indent=1, sort_keys=True) + "\n").encode("utf-8"))
        EventStore._write_local(home, host_id)
        st = EventStore(home)
        st.write_anchors([])
        return st

    @staticmethod
    def init_host(home: str | os.PathLike, host_id: str) -> "EventStore":
        """Register this machine on an existing (e.g. cloned) ledger with a host id of its own.

        Refuses a host id whose segment already exists (that segment belongs to another machine) and adopts the
        current verified segments as this machine's anchors."""
        home = Path(home)
        if not (home / "mm.json").is_file():
            raise StoreError("NOT_INITIALISED", f"{home} has no mm.json")
        if (home / "local" / "host.json").is_file():
            raise StoreError("ALREADY_REGISTERED", "this machine already has a host id for this ledger")
        if (home / "events" / f"{host_id}.jsonl").exists():
            raise StoreError("HOST_ID_TAKEN", f"segment {host_id}.jsonl exists: it belongs to another machine; "
                                              "choose a new host id")
        EventStore._write_local(home, host_id)
        st = EventStore(home)
        segs = st.read_all()
        bad = [e for s in segs for e in s.errors]
        if bad:
            raise StoreError("CHAIN_BROKEN", "cannot adopt anchors from a ledger that fails verification: " + bad[0])
        st.write_anchors(segs)
        return st

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
        """Append one event. Caller must hold the lock (``with store.locked():``)."""
        return self.append_many([(kind, data, base)], actor, session, ts)[0]

    def append_many(self, items, actor: str, session: str | None = None, ts: str | None = None) -> list[dict]:
        """Append ``[(kind, data, base), ...]`` as one batch: one write, one fsync, same timestamp.

        With more than one item every event carries ``batch = {id, n, i}``; the fold applies the batch only when all
        ``n`` events are present. Caller must hold the lock."""
        if not items:
            return []
        if self._tail is None:
            seg = read_segment(self.segment_path)
            if seg.torn:
                raise StoreError("TORN_TAIL", f"{self.segment_path.name} ends with {len(seg.torn)} incomplete "
                                              "bytes; run `recover` first")
            if seg.errors:
                raise StoreError("CHAIN_BROKEN", "; ".join(seg.errors[:3]))
            self._tail = (seg.good_bytes, seg.head, len(seg.events), seg.events[-1]["ts"] if seg.events else "")
        good, head, count, last_ts = self._tail
        ts = max(ts or utc_now(), last_ts)  # never earlier than this segment's last event (clock steps back)
        batch_id = sha256_text(f"{self.host}:{count + 1}:{ts}")[:16] if len(items) > 1 else None
        events, blob = [], b""
        for i, (kind, data, base) in enumerate(items):
            ev = {"v": EVENT_VERSION, "seg": self.host, "seq": count + 1 + i, "ts": ts, "actor": actor,
                  "session": session, "kind": kind, "data": data, "base": base or {}, "prev": head}
            if batch_id:
                ev["batch"] = {"id": batch_id, "n": len(items), "i": i}
            ev["hash"] = event_hash(ev)
            head = ev["hash"]
            events.append(ev)
            blob += (canonical(ev) + "\n").encode("utf-8")
        self.events_dir.mkdir(parents=True, exist_ok=True)
        with self.segment_path.open("ab") as f:
            if f.tell() != good:
                raise StoreError("CONCURRENT_WRITE", f"{self.segment_path.name} changed outside the lock")
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
        self._tail = (good + len(blob), head, count + len(items), ts)
        return events

    # ---- anchors (truncation detection)

    @property
    def anchors_path(self) -> Path:
        return self.local_dir / "anchors.json"

    def read_anchors(self) -> dict | None:
        """The anchors, or None when the file is missing or unreadable."""
        try:
            a = json.loads(self.anchors_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        if not isinstance(a, dict) or not all(isinstance(v, dict) for v in a.values()):
            return None
        return a

    def write_anchors(self, segs) -> None:
        """Record per-segment {count, head} of the trusted prefix; never moves backwards."""
        anchors = self.read_anchors() or {}
        for s in segs:
            cur = anchors.get(s.name)
            valid = s.valid_events
            if cur is None or len(valid) >= cur.get("count", 0):
                anchors[s.name] = {"count": len(valid), "head": valid[-1]["hash"] if valid else GENESIS}
        atomic_write_bytes(self.anchors_path, json.dumps(anchors, indent=1, sort_keys=True).encode("utf-8"))

    def anchor_errors(self, segs) -> list[str]:
        """Truncation or rewrite of anchored events: the anchored event must still be at its position."""
        errs, by_name = [], {s.name: s for s in segs}
        anchors = self.read_anchors()
        if anchors is None:
            if any(s.events for s in segs):
                errs.append(f"{self.anchors_path} is missing or unreadable while the ledger holds events: deletion "
                            "of the newest events cannot be ruled out (check git history, then `reanchor`)")
            return errs
        for name, a in sorted(anchors.items()):
            s = by_name.get(name)
            n = a.get("count", 0) if isinstance(a, dict) else 0
            if n == 0:
                continue
            if s is None:
                errs.append(f"{name}: segment missing (anchored at {n} events)")
            elif len(s.events) < n:
                errs.append(f"{name}: has {len(s.events)} events but {n} were anchored (newest events deleted)")
            elif s.events[n - 1].get("hash") != a.get("head"):
                errs.append(f"{name}: event {n} differs from the anchored head (rewritten)")
        return errs

    def reanchor(self, actor: str, reason: str, session: str | None = None) -> dict:
        """Explicitly re-base the anchors on the current segments, recorded as an ANCHORS_RESET event."""
        if not reason or not actor:
            raise StoreError("USAGE", "reanchor needs --actor and --reason")
        with self.locked():
            segs = self.read_all()
            bad = [e for s in segs for e in s.errors]
            if bad:
                raise StoreError("CHAIN_BROKEN", "reanchor only re-bases anchors; chain errors need an owner "
                                                 "decision: " + bad[0])
            before = self.read_anchors()
            info = {"reason": reason, "previous": before,
                    "counts": {s.name: len(s.events) for s in segs}}
            self.append("ANCHORS_RESET", info, actor=actor, session=session)
            self.write_anchors_force(self.read_all())
            self.autocommit("ANCHORS_RESET")
            return info

    def write_anchors_force(self, segs) -> None:
        anchors = {s.name: {"count": len(s.valid_events),
                            "head": s.valid_events[-1]["hash"] if s.valid_events else GENESIS} for s in segs}
        atomic_write_bytes(self.anchors_path, json.dumps(anchors, indent=1, sort_keys=True).encode("utf-8"))

    # ---- verification and recovery

    def verify(self) -> dict:
        segs = self.read_all()
        errors, torn, heads, total = [], [], {}, 0
        seen_names = set()
        errors.extend(self.anchor_errors(segs))
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
            self.write_anchors([read_segment(self.segment_path)])
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
        p = self._git("status", "--porcelain", "--", "events", "mm.json", ".gitignore")
        dirty = [line[3:] for line in p.stdout.splitlines() if line.strip()]
        return {"tracked": True, "uncommitted": dirty}

    def autocommit(self, label: str) -> dict:
        """Commit the event segments when the home is a git work tree and autocommit is on. Never pushes.

        A failure is reported, not raised: the event is already fsynced; verify() shows uncommitted segments."""
        if not self.config.get("autocommit") or not self.in_git():
            return {"committed": False}
        add = self._git("add", "--", "events", "mm.json", ".gitignore")
        if add.returncode:
            return {"committed": False, "error": add.stderr.strip()[:300]}
        if not self._git("diff", "--cached", "--quiet").returncode:
            return {"committed": False}
        c = self._git("-c", "user.name=URI Milestone Manager", "-c", "user.email=mm@uri.local",
                      "commit", "--no-verify", "-q", "-m", f"mm: {label}")
        return {"committed": c.returncode == 0, **({"error": c.stderr.strip()[:300]} if c.returncode else {})}
