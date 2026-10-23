"""DPAPI-protected persistent secrets (current Windows user). Fixes P0 defect D10 for launchers that may change.

`persistent_secret(path)` returns the same 32-byte secret (hex) on every start: created once with exclusive create, then
read back. A file that exists but cannot be unprotected stops the caller (`KeyUnavailable`) instead of silently
replacing it, because a replaced secret makes every stored provider key and credential unreadable.
"""
from __future__ import annotations

import os
import secrets
from pathlib import Path


class KeyUnavailable(RuntimeError):
    pass


def _dpapi(data: bytes, decrypt: bool) -> bytes:
    from uri_core.core.runtime_identity import RuntimeIdentityError, dpapi   # lazy: the module costs ~0.8 s to import
    try:
        return dpapi(data, decrypt)
    except RuntimeIdentityError as exc:
        raise KeyUnavailable("PROTECTED_KEY_UNAVAILABLE") from exc


def _read(path: Path) -> bytes:
    blob = path.read_bytes()
    raw = _dpapi(blob, True)
    if len(raw) != 32:
        raise KeyUnavailable("PROTECTED_KEY_UNAVAILABLE")
    return raw


def persistent_key(path) -> bytes:
    path = Path(path)
    if path.exists():
        return _read(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    raw = secrets.token_bytes(32)
    blob = _dpapi(raw, False)
    tmp = path.with_name(path.name + f".{os.getpid()}.tmp")
    tmp.write_bytes(blob)
    try:
        os.link(tmp, path)                 # atomic exclusive create: a concurrent first start keeps one secret
    except FileExistsError:
        return _read(path)
    except OSError:
        try:
            fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0))
        except FileExistsError:
            return _read(path)
        with os.fdopen(fd, "wb") as f:
            f.write(blob)
            f.flush()
            os.fsync(f.fileno())
    finally:
        tmp.unlink(missing_ok=True)
    return _read(path)


def persistent_secret(path) -> str:
    return persistent_key(path).hex()
