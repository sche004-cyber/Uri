"""Assist access control: one scope, five separate permissions, immediate revocation, stale-proof observations.

Permissions (never conflated; none implies another):
  OBSERVE   read the active scope when the user asks
  SUGGEST   show findings/suggestions derived from an observation
  REMEMBER  keep anything derived from an observation after the answer (A0: not grantable; nothing is stored)
  INSERT    put a user-selected value into a field (A1; not grantable in A0)
  ACT       perform a specific approved action (not grantable; consequential actions stay with Core's approval gate)

A grant names exactly one target. Every observation is stamped with (grant id, generation, target id, time). Revoke,
pause, expiry and target loss bump the generation, so anything captured before cannot be used afterwards.
Grants live in memory only: a worker restart always starts OFF.
"""
from __future__ import annotations

import threading
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Callable, Optional


class Permission(str, Enum):
    OBSERVE = "observe"
    SUGGEST = "suggest"
    REMEMBER = "remember"
    INSERT = "insert"
    ACT = "act"


class ScopeKind(str, Enum):
    BROWSER_TAB = "browser_tab"
    DESKTOP_WINDOW = "desktop_window"
    ENTIRE_SCREEN = "entire_screen"


class State(str, Enum):
    OFF = "OFF"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"


GRANTABLE_A0 = frozenset({Permission.OBSERVE, Permission.SUGGEST})
NOT_YET = {Permission.REMEMBER: "NOT_AVAILABLE_IN_A0", Permission.INSERT: "NOT_AVAILABLE_IN_A0",
           Permission.ACT: "NEVER_GRANTED_BY_ASSIST"}
DEFAULT_TTL_S = 30 * 60
MAX_TTL_S = 2 * 60 * 60
MAX_OBSERVATION_AGE_S = {"dom": 30.0, "uia": 30.0, "screenshot": 10.0}


class AccessRefused(PermissionError):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Scope:
    kind: ScopeKind
    target_id: str
    label: str
    origin: Optional[str] = None       # browser tab origin (scheme://host) when known


@dataclass
class Grant:
    grant_id: str
    scope: Scope
    permissions: frozenset
    granted_at: float
    expires_at: float
    generation: int


@dataclass(frozen=True)
class Stamp:
    """Binds an observation to the grant that allowed it."""
    grant_id: str
    generation: int
    target_id: str
    kind: str                 # dom | uia | screenshot
    captured_at: float


@dataclass
class AuditEntry:
    t: float
    event: str
    code: Optional[str] = None
    detail: dict = field(default_factory=dict)


class AccessController:
    def __init__(self, *, clock: Callable[[], float] = time.monotonic, audit_limit: int = 200):
        self._clock = clock
        self._lock = threading.RLock()
        self.state = State.OFF
        self.grant: Optional[Grant] = None
        self.generation = 0
        self.audit: list = []
        self._audit_limit = audit_limit
        self.last_refusal: Optional[str] = None

    # ---- audit (content-free) -------------------------------------------------------------------
    def _log(self, event, code=None, **detail):
        self.audit.append(AuditEntry(round(self._clock(), 3), event, code, detail))
        del self.audit[:-self._audit_limit]

    def _refuse(self, code):
        self.last_refusal = code
        self._log("refused", code)
        raise AccessRefused(code)

    # ---- transitions ----------------------------------------------------------------------------
    def grant_scope(self, kind, target_id: str, label: str, permissions, *, confirm_screen: bool = False,
                    origin: Optional[str] = None, ttl_s: float = DEFAULT_TTL_S) -> Grant:
        with self._lock:
            try:
                kind = ScopeKind(kind)
            except ValueError:
                self._refuse("SCOPE_KIND_INVALID")
            if not isinstance(target_id, str) or not target_id or len(target_id) > 200:
                self._refuse("TARGET_INVALID")
            try:
                perms = frozenset(Permission(p) for p in permissions)
            except (ValueError, TypeError):
                self._refuse("PERMISSION_INVALID")
            if Permission.OBSERVE not in perms:
                self._refuse("OBSERVE_REQUIRED")
            for p in perms:
                if p not in GRANTABLE_A0:
                    self._refuse("PERMISSION_" + p.name + "_" + NOT_YET[p])
            if kind == ScopeKind.ENTIRE_SCREEN and confirm_screen is not True:
                self._refuse("SCREEN_CONFIRMATION_REQUIRED")
            if kind != ScopeKind.ENTIRE_SCREEN and confirm_screen:
                self._refuse("SCREEN_CONFIRMATION_UNEXPECTED")
            ttl = max(60.0, min(float(ttl_s), MAX_TTL_S))
            now = self._clock()
            self.generation += 1          # any earlier grant's observations are now stale
            self.grant = Grant(str(uuid.uuid4()), Scope(kind, target_id, (label or "")[:200], origin), perms, now,
                               now + ttl, self.generation)
            self.state = State.ACTIVE
            self._log("granted", kind=kind.value, permissions=sorted(p.value for p in perms))
            return self.grant

    def pause(self):
        with self._lock:
            if self.state != State.ACTIVE:
                self._refuse("SCOPE_NOT_ACTIVE")
            self.state = State.PAUSED
            self.generation += 1
            self._log("paused")

    def resume(self):
        with self._lock:
            if self.state != State.PAUSED:
                self._refuse("SCOPE_NOT_PAUSED")
            self._expire_if_due()
            if self.state != State.PAUSED:
                self._refuse("SCOPE_EXPIRED")
            self.state = State.ACTIVE
            self.generation += 1
            self.grant.generation = self.generation
            self._log("resumed")

    def revoke(self, reason: str = "user"):
        with self._lock:
            was = self.state
            self.state, self.grant = State.OFF, None
            self.generation += 1
            self._log("revoked", reason=reason, was=was.value)

    def target_lost(self, target_id: str):
        with self._lock:
            if self.grant is not None and self.grant.scope.target_id == target_id:
                self.revoke("target_lost")

    def _expire_if_due(self):
        if self.grant is not None and self._clock() >= self.grant.expires_at:
            self.revoke("expired")

    # ---- checks ---------------------------------------------------------------------------------
    def require(self, permission: Permission) -> Grant:
        with self._lock:
            self._expire_if_due()
            if self.state == State.OFF:
                self._refuse("SCOPE_NOT_ACTIVE")
            if self.state == State.PAUSED:
                self._refuse("SCOPE_PAUSED")
            if permission not in self.grant.permissions:
                self._refuse("PERMISSION_NOT_GRANTED_" + permission.name)
            return self.grant

    def stamp(self, kind: str) -> Stamp:
        """Issue the stamp an adapter must attach to a capture. Requires OBSERVE now."""
        g = self.require(Permission.OBSERVE)
        return Stamp(g.grant_id, self.generation, g.scope.target_id, kind, self._clock())

    def check_fresh(self, stamp: Stamp, permission: Permission) -> Grant:
        """An observation may be used for `permission` only if its grant is still the active one, unchanged, for
        the same target, and the observation is younger than its kind's bound."""
        with self._lock:
            g = self.require(permission)
            if stamp.grant_id != g.grant_id or stamp.generation != self.generation:
                self._refuse("OBSERVATION_STALE")
            if stamp.target_id != g.scope.target_id:
                self._refuse("TARGET_CHANGED")
            if self._clock() - stamp.captured_at > MAX_OBSERVATION_AGE_S.get(stamp.kind, 10.0):
                self._refuse("OBSERVATION_STALE")
            return g

    def check_unchanged(self, stamp: Stamp, permission: Permission) -> Grant:
        """The grant that allowed `stamp` is still the active, unpaused one for the same target (no age limit).
        Used after a Brain answer: Stop/Pause/new grant during generation discards the answer."""
        with self._lock:
            g = self.require(permission)
            if stamp.grant_id != g.grant_id or stamp.generation != self.generation:
                self._refuse("OBSERVATION_STALE")
            if stamp.target_id != g.scope.target_id:
                self._refuse("TARGET_CHANGED")
            return g

    def snapshot(self) -> dict:
        with self._lock:
            self._expire_if_due()
            g = self.grant
            return {"state": self.state.value, "generation": self.generation,
                    "scope": None if g is None else {"kind": g.scope.kind.value, "target_id": g.scope.target_id,
                                                     "label": g.scope.label, "origin": g.scope.origin,
                                                     "expires_in_s": round(max(0.0, g.expires_at - self._clock()))},
                    "permissions": {p.value: (g is not None and p in g.permissions) for p in Permission},
                    "grantable": sorted(p.value for p in GRANTABLE_A0),
                    "not_yet": {p.value: why for p, why in NOT_YET.items()},
                    "last_refusal": self.last_refusal}
