"""Per-scope opaque references for pseudonymized values (plan 2.3).

A token is `[[<CATEGORY>_<8 random hex>]]`. It is random, not derived from the value, so it reveals nothing and cannot be
resolved outside this process. One scope = one request, task or session; scopes never share tokens. Restoration only
resolves tokens of its own scope; any other token-shaped text is reported as foreign and left untouched.

Storage is memory by default. `PersistentVaultStore` keeps scopes that must survive a restart in Fernet-encrypted files
whose key is DPAPI-protected (`keys.persistent_key`); a file that cannot be decrypted is moved to `quarantine/` and the
scope is refused, never guessed.
"""
from __future__ import annotations

import json
import os
import re
import secrets
import threading
import time
from pathlib import Path

TOKEN = re.compile(r"\[\[([A-Z_]{3,16})_([0-9a-f]{8})\]\]")
_SCOPE_ID = re.compile(r"[A-Za-z0-9_.:-]{1,96}")


def _check_scope_id(scope_id):
    """Every entry point validates the id (review S1-03), not only open()."""
    if not isinstance(scope_id, str) or not _SCOPE_ID.fullmatch(scope_id):
        raise VaultError("SCOPE_ID_INVALID")


class VaultError(RuntimeError):
    def __init__(self, code):
        super().__init__(code)
        self.code = code


class Scope:
    def __init__(self, scope_id: str, expires_at: float, refs=None, requester=None):
        self.scope_id = scope_id
        self.expires_at = expires_at
        self.requester = requester
        self._by_token = dict(refs or {})                     # token -> (category, value)
        self._by_value = {(c, v): t for t, (c, v) in self._by_token.items()}
        self._lock = threading.Lock()

    def expired(self, now=None) -> bool:
        return (now if now is not None else time.time()) >= self.expires_at

    def token_for(self, category: str, value: str) -> str:
        with self._lock:
            tok = self._by_value.get((category, value))
            if tok is None:
                while True:
                    tok = f"[[{category}_{secrets.token_hex(4)}]]"
                    if tok not in self._by_token:
                        break
                self._by_token[tok] = (category, value)
                self._by_value[(category, value)] = tok
            return tok

    def restore(self, text: str):
        """Return (text, restored_count, foreign_count)."""
        restored = foreign = 0

        def sub(m):
            nonlocal restored, foreign
            hit = self._by_token.get(m.group(0))
            if hit is None:
                foreign += 1
                return m.group(0)
            restored += 1
            return hit[1]
        with self._lock:
            out = TOKEN.sub(sub, text)
        return out, restored, foreign

    def size(self) -> int:
        return len(self._by_token)

    def _dump(self) -> dict:
        with self._lock:
            return {"scope_id": self.scope_id, "expires_at": self.expires_at, "requester": self.requester,
                    "refs": [[t, c, v] for t, (c, v) in self._by_token.items()]}


class MemoryVaultStore:
    def __init__(self, *, clock=time.time):
        self.clock = clock
        self._scopes = {}
        self._lock = threading.Lock()

    def open(self, scope_id: str, ttl_s: float, *, requester=None) -> Scope:
        _check_scope_id(scope_id)
        with self._lock:
            s = self._scopes.get(scope_id)
            if s is not None and s.expired(self.clock()):
                self._drop(scope_id)
                s = None
            if s is None:
                s = self._load(scope_id) or Scope(scope_id, self.clock() + ttl_s, requester=requester)
                self._scopes[scope_id] = s
            if s.requester != requester:
                raise VaultError("SCOPE_OWNER_MISMATCH")
            return s

    def get(self, scope_id: str):
        _check_scope_id(scope_id)
        with self._lock:
            s = self._scopes.get(scope_id) or self._load(scope_id)
            if s is None:
                return None
            if s.expired(self.clock()):
                self._drop(scope_id)
                return None
            self._scopes[scope_id] = s
            return s

    def save(self, scope: Scope) -> None:
        pass

    def close(self, scope_id: str) -> None:
        _check_scope_id(scope_id)
        with self._lock:
            self._drop(scope_id)

    def purge_expired(self) -> int:
        with self._lock:
            dead = [k for k, s in self._scopes.items() if s.expired(self.clock())]
            for k in dead:
                self._drop(k)
            return len(dead) + self._purge_files()

    # persistence hooks (memory store: none)
    def _load(self, scope_id):
        return None

    def _drop(self, scope_id):
        self._scopes.pop(scope_id, None)

    def _purge_files(self) -> int:
        return 0


class PersistentVaultStore(MemoryVaultStore):
    def __init__(self, home, *, clock=time.time, key=None):
        super().__init__(clock=clock)
        from cryptography.fernet import Fernet
        import base64
        self.home = Path(home)
        (self.home / "refs").mkdir(parents=True, exist_ok=True)
        if key is None:
            from .keys import persistent_key
            key = persistent_key(self.home / "vault-key.dpapi")
        self._fernet = Fernet(base64.urlsafe_b64encode(key))

    def _path(self, scope_id):
        # Hex of the id's bytes: one file per id, no two ids share a file on a case-insensitive filesystem, and the
        # name can never hold a path separator (review S1-03).
        _check_scope_id(scope_id)
        return self.home / "refs" / (scope_id.encode("ascii").hex() + ".ref")

    def save(self, scope: Scope) -> None:
        data = self._fernet.encrypt(json.dumps(scope._dump()).encode("utf-8"))
        path = self._path(scope.scope_id)
        tmp = path.with_name(path.name + f".{os.getpid()}.{threading.get_ident()}.tmp")
        with open(tmp, "wb") as f:
            f.write(data)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)

    def _load(self, scope_id):
        path = self._path(scope_id)
        if not path.exists():
            return None
        try:
            d = json.loads(self._fernet.decrypt(path.read_bytes()).decode("utf-8"))
            if d.get("scope_id") != scope_id:
                raise ValueError("scope mismatch")
            return Scope(scope_id, float(d["expires_at"]), {t: (c, v) for t, c, v in d["refs"]}, d.get("requester"))
        except Exception:                                       # noqa: BLE001 - any doubt: quarantine and refuse
            q = self.home / "quarantine"
            q.mkdir(exist_ok=True)
            os.replace(path, q / (path.name + f".{int(self.clock())}"))
            raise VaultError("SCOPE_UNREADABLE") from None

    def _drop(self, scope_id):
        super()._drop(scope_id)
        self._path(scope_id).unlink(missing_ok=True)

    def _purge_files(self) -> int:
        n = 0
        for p in (self.home / "refs").glob("*.tmp"):
            p.unlink(missing_ok=True)                           # interrupted writes; the previous file is intact
        for p in list((self.home / "refs").glob("*.ref")):
            try:
                d = json.loads(self._fernet.decrypt(p.read_bytes()).decode("utf-8"))
                if self.clock() >= float(d["expires_at"]):
                    p.unlink(missing_ok=True)
                    n += 1
            except Exception:                                   # noqa: BLE001
                q = self.home / "quarantine"
                q.mkdir(exist_ok=True)
                os.replace(p, q / (p.name + f".{int(self.clock())}"))
        return n
