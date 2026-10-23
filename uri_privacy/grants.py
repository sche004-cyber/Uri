"""Scoped, expiring, revocable disclosure grants (plan 2.4).

A grant lets one requester disclose named categories, for one purpose, to one destination, for a limited time and
number of uses, because a user said so. It relaxes the gateway's sanitization of an action that is already authorized;
it never authorizes a capability (CapabilityResolver / ApprovalGate stay the authority) and it can never cover a
credential (`policy.grantable`).
"""
from __future__ import annotations

import json
import errno
import os
import re
import secrets
import threading
import time
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import policy as P
from .classify import classify

MAX_TTL_S = 24 * 3600
_USER = re.compile(r"^user:[A-Za-z0-9_.@-]{1,64}$")
_OPAQUE_USER = re.compile(r"user:[0-9a-f]{32}")
_SCOPE_LABEL = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,63}")
_GRANT_ID = re.compile(r"GR-[0-9a-f]{12}")


def _scope_label_safe(value) -> bool:
    # Scope labels are code identifiers, never user text. Restrict their shape and reject
    # values that the classifier recognizes as sensitive before storing them in cleartext.
    return (isinstance(value, str) and _SCOPE_LABEL.fullmatch(value) is not None
            and not classify(value).categories())


def _record_safe(g) -> bool:
    return (isinstance(g, Grant) and isinstance(g.grant_id, str) and _GRANT_ID.fullmatch(g.grant_id)
            and _scope_label_safe(g.requester) and _scope_label_safe(g.purpose)
            and isinstance(g.authorized_by, str) and _OPAQUE_USER.fullmatch(g.authorized_by)
            and isinstance(g.destination, str) and g.destination in {d.value for d in P.Destination}
            and isinstance(g.categories, list) and bool(g.categories)
            and all(isinstance(c, str) and P.grantable(c, g.destination) for c in g.categories)
            and all(type(n) in (int, float) for n in (g.expires_at, g.created_at))
            and (g.revoked_at is None or type(g.revoked_at) in (int, float))
            and type(g.uses_left) is int and g.uses_left >= 0
            and type(g.used) is int and g.used >= 0)


class GrantError(ValueError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


@dataclass
class Grant:
    grant_id: str
    requester: str
    categories: list
    purpose: str
    destination: str
    expires_at: float
    uses_left: int
    authorized_by: str
    created_at: float
    revoked_at: float | None = None
    used: int = field(default=0)

    def live(self, now) -> bool:
        return self.revoked_at is None and self.uses_left > 0 and now < self.expires_at


class GrantStore:
    def __init__(self, path=None, *, clock=time.time, principal_verifier=None):
        self.path = Path(path) if path else None
        self.clock = clock
        # A production store has no grant-creation authority until an authenticated
        # boundary supplies a verifier. A formatted user: string proves nothing.
        self.principal_verifier = principal_verifier
        self._lock = threading.Lock()
        self._grants = {}
        self._reload()

    def _reload(self):
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))   # malformed state fails closed
            grants = [Grant(**g) for g in data["grants"]]
            if any(not _record_safe(g) for g in grants):
                raise ValueError("GRANT_METADATA_INVALID")
            self._grants = {g.grant_id: g for g in grants}
        elif self.path:
            self._grants = {}

    @contextmanager
    def _transaction(self):
        with self._lock:
            if self.path is None:
                yield
                return
            self.path.parent.mkdir(parents=True, exist_ok=True)
            lock_path = self.path.with_name(self.path.name + ".lock")
            with open(lock_path, "a+b") as lock:
                if os.name == "nt":
                    import msvcrt
                    # Byte 0 is locked without ever being read or written: Windows byte-range locks are mandatory, so
                    # reading a byte another process has locked raises PermissionError (C1-01: the second process
                    # crashed instead of waiting). Locking a range past the end of the file is allowed.
                    lock.seek(0)
                    while True:
                        try:
                            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
                            break
                        except OSError as exc:
                            if exc.errno not in (errno.EACCES, errno.EDEADLK):
                                raise
                            time.sleep(0.01)
                else:
                    import fcntl
                    fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
                try:
                    self._reload()
                    yield
                finally:
                    if os.name == "nt":
                        lock.seek(0)
                        msvcrt.locking(lock.fileno(), msvcrt.LK_UNLCK, 1)
                    else:
                        fcntl.flock(lock.fileno(), fcntl.LOCK_UN)

    def _save(self):
        if not self.path:
            return
        if any(not _record_safe(g) for g in self._grants.values()):
            raise GrantError("GRANT_METADATA_INVALID")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"schema": "uri-privacy-grants/1", "grants": [asdict(g) for g in self._grants.values()]}, f)
            f.flush()
            os.fsync(f.fileno())
        for attempt in range(20):
            try:
                os.replace(tmp, self.path)
                break
            except PermissionError:      # Windows: a reader or scanner holds the file for a moment (C1-01)
                if attempt == 19:
                    raise
                time.sleep(0.02)

    def grant(self, *, requester, categories, purpose, destination, authorized_by, principal=None, ttl_s=900, uses=1) -> Grant:
        verified = None
        if self.principal_verifier is not None and principal is not None:
            try:
                verified = self.principal_verifier(principal)
            except Exception:  # an auth failure cannot create a grant
                pass
        if (not isinstance(authorized_by, str) or not _USER.match(authorized_by)
                or verified != authorized_by.removeprefix("user:")):
            raise GrantError("USER_AUTHORIZATION_REQUIRED")          # a component cannot grant itself
        if not requester or not purpose or not categories:
            raise GrantError("GRANT_SCOPE_INCOMPLETE")
        if not _scope_label_safe(requester) or not _scope_label_safe(purpose):
            raise GrantError("GRANT_METADATA_INVALID")
        dest = P.Destination(destination).value
        for c in categories:
            if not P.grantable(c, dest):
                raise GrantError("CATEGORY_NOT_GRANTABLE")          # credentials and local/log rows
        if not 0 < ttl_s <= MAX_TTL_S or not isinstance(uses, int) or uses < 1:
            raise GrantError("GRANT_LIMITS_INVALID")
        now = self.clock()
        g = Grant("GR-" + secrets.token_hex(6), requester, sorted(set(categories)), purpose, dest, now + ttl_s, uses,
                  "user:" + secrets.token_hex(16), now)
        with self._transaction():
            self._grants[g.grant_id] = g
            self._save()
        return g

    def match(self, *, requester, category, purpose, destination):
        now = self.clock()
        with self._transaction():
            for g in self._grants.values():
                if (g.live(now) and g.requester == requester and category in g.categories and g.purpose == purpose
                        and g.destination == P.Destination(destination).value):
                    return g.grant_id
        return None

    def consume(self, grant_ids) -> bool:
        """Use each grant once, atomically: all or none (concurrent callers cannot exceed uses_left)."""
        now = self.clock()
        grant_ids = tuple(dict.fromkeys(grant_ids))
        with self._transaction():
            gs = [self._grants.get(i) for i in grant_ids]
            if any(g is None or not g.live(now) for g in gs):
                return False
            for g in gs:
                g.uses_left -= 1
                g.used += 1
            self._save()
            return True

    def revoke(self, grant_id) -> bool:
        with self._transaction():
            g = self._grants.get(grant_id)
            if g is None or g.revoked_at is not None:
                return False
            g.revoked_at = self.clock()
            self._save()
            return True

    def revoke_requester(self, requester) -> int:
        """Revoke every live grant of this requester; returns how many were stopped."""
        now = self.clock()
        with self._transaction():
            n = 0
            for g in self._grants.values():
                if g.requester == requester and g.live(now):
                    g.revoked_at = self.clock()
                    n += 1
            self._save()
            return n

    def list(self, *, live_only=True) -> list:
        now = self.clock()
        with self._transaction():
            return [asdict(g) for g in self._grants.values() if g.live(now) or not live_only]
