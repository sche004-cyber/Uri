"""Scoped, expiring, revocable disclosure grants (plan 2.4).

A grant lets one requester disclose named categories, for one purpose, to one destination, for a limited time and
number of uses, because a user said so. It relaxes the gateway's sanitization of an action that is already authorized;
it never authorizes a capability (CapabilityResolver / ApprovalGate stay the authority) and it can never cover a
credential (`policy.grantable`).
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

from . import policy as P

MAX_TTL_S = 24 * 3600
_USER = re.compile(r"^user:[A-Za-z0-9_.@-]{1,64}$")


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
    def __init__(self, path=None, *, clock=time.time):
        self.path = Path(path) if path else None
        self.clock = clock
        self._lock = threading.Lock()
        self._grants = {}
        if self.path and self.path.exists():
            data = json.loads(self.path.read_text(encoding="utf-8"))   # a malformed file raises: fail closed
            self._grants = {g["grant_id"]: Grant(**g) for g in data["grants"]}

    def _save(self):
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_name(self.path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump({"schema": "uri-privacy-grants/1", "grants": [asdict(g) for g in self._grants.values()]}, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)

    def grant(self, *, requester, categories, purpose, destination, authorized_by, ttl_s=900, uses=1) -> Grant:
        if not isinstance(authorized_by, str) or not _USER.match(authorized_by):
            raise GrantError("USER_AUTHORIZATION_REQUIRED")          # a component cannot grant itself
        if not requester or not purpose or not categories:
            raise GrantError("GRANT_SCOPE_INCOMPLETE")
        dest = P.Destination(destination).value
        for c in categories:
            if not P.grantable(c, dest):
                raise GrantError("CATEGORY_NOT_GRANTABLE")          # credentials and local/log rows
        if not 0 < ttl_s <= MAX_TTL_S or not isinstance(uses, int) or uses < 1:
            raise GrantError("GRANT_LIMITS_INVALID")
        now = self.clock()
        g = Grant("GR-" + secrets.token_hex(6), requester, sorted(set(categories)), purpose, dest, now + ttl_s, uses,
                  authorized_by, now)
        with self._lock:
            self._grants[g.grant_id] = g
            self._save()
        return g

    def match(self, *, requester, category, purpose, destination):
        now = self.clock()
        with self._lock:
            for g in self._grants.values():
                if (g.live(now) and g.requester == requester and category in g.categories and g.purpose == purpose
                        and g.destination == P.Destination(destination).value):
                    return g.grant_id
        return None

    def consume(self, grant_ids) -> bool:
        """Use each grant once, atomically: all or none (concurrent callers cannot exceed uses_left)."""
        now = self.clock()
        with self._lock:
            gs = [self._grants.get(i) for i in grant_ids]
            if any(g is None or not g.live(now) for g in gs):
                return False
            for g in gs:
                g.uses_left -= 1
                g.used += 1
            self._save()
            return True

    def revoke(self, grant_id) -> bool:
        with self._lock:
            g = self._grants.get(grant_id)
            if g is None or g.revoked_at is not None:
                return False
            g.revoked_at = self.clock()
            self._save()
            return True

    def revoke_requester(self, requester) -> int:
        """Revoke every live grant of this requester; returns how many were stopped."""
        now = self.clock()
        with self._lock:
            n = 0
            for g in self._grants.values():
                if g.requester == requester and g.live(now):
                    g.revoked_at = self.clock()
                    n += 1
            self._save()
            return n

    def list(self, *, live_only=True) -> list:
        now = self.clock()
        with self._lock:
            return [asdict(g) for g in self._grants.values() if g.live(now) or not live_only]
