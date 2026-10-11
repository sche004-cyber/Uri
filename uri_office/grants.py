"""File access grants (AC7).

The service may touch only:
  * a workbook the owner opened through the panel's file picker (an OPEN grant, recorded at open), and
  * a destination the owner chose in the panel's save dialog (a SAVE_AS grant).
Every other path is refused. Paths must be absolute local paths to an existing (open) or creatable (save as) `.xlsx`
file; UNC/device paths, `..` segments, links/junctions that resolve elsewhere and alternate data streams are refused.
"""
from __future__ import annotations

import os
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from .errors import OfficeError

_DRIVE_ABS = re.compile(r"^[A-Za-z]:[\\/]")
MAX_BYTES = 50 * 1024 * 1024


@dataclass(frozen=True)
class Grant:
    grant_id: str
    kind: str          # "open" | "save_as"
    path: Path


def _check_shape(raw) -> Path:
    if not isinstance(raw, str) or not raw or len(raw) > 1024 or "\x00" in raw:
        raise OfficeError("PATH_REFUSED", "not a path")
    if raw.startswith(("\\\\", "//")) or not _DRIVE_ABS.match(raw):
        raise OfficeError("PATH_REFUSED", "only absolute local drive paths are allowed")
    parts = re.split(r"[\\/]", raw)
    if any(p in ("..", ".") for p in parts):
        raise OfficeError("PATH_REFUSED", "relative segments are not allowed")
    if ":" in raw[2:]:
        raise OfficeError("PATH_REFUSED", "alternate data streams are not allowed")
    p = Path(raw)
    if p.suffix.lower() != ".xlsx":
        raise OfficeError("PATH_REFUSED", "only .xlsx workbooks")
    return p


def _same_after_resolve(p: Path) -> bool:
    try:
        return os.path.normcase(str(p.resolve(strict=False))) == os.path.normcase(str(p))
    except OSError:
        return False


class Grants:
    def __init__(self):
        self._by_id: dict[str, Grant] = {}

    def grant_open(self, raw) -> Grant:
        p = _check_shape(raw)
        if not p.is_file() or p.is_symlink() or not _same_after_resolve(p):
            raise OfficeError("PATH_REFUSED", "not a regular local file")
        if p.stat().st_size > MAX_BYTES:
            raise OfficeError("FILE_TOO_LARGE", "the workbook is larger than 50 MB")
        return self._add("open", p)

    def grant_save_as(self, raw) -> Grant:
        p = _check_shape(raw)
        if not p.parent.is_dir() or not _same_after_resolve(p.parent / "x"):
            raise OfficeError("PATH_REFUSED", "the folder does not exist or is a link")
        if p.exists() and (not p.is_file() or p.is_symlink()):
            raise OfficeError("PATH_REFUSED", "not a regular file")
        return self._add("save_as", p)

    def _add(self, kind, p) -> Grant:
        g = Grant(uuid.uuid4().hex, kind, p)
        self._by_id[g.grant_id] = g
        return g

    def get(self, grant_id, kind) -> Grant:
        g = self._by_id.get(grant_id) if isinstance(grant_id, str) else None
        if g is None or g.kind != kind:
            raise OfficeError("NO_GRANT", "this file was not opened or approved by the owner", 403)
        return g

    def revoke(self, grant_id):
        self._by_id.pop(grant_id, None)
