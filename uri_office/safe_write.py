"""No-overwrite, atomic output write for O2 outputs (plan rev 3.1 §5.1 "Output write", reviews F23 and N8).

At apply time: re-check the destination folder's real path against the grant (no junction swapped in since the grant),
copy the approved bytes into a new temporary file in that folder, flush and fsync, check again that the temp file's
real path is where it should be, then give it the final name with an operation that fails if the name exists
(`os.rename` on Windows; `os.link` elsewhere). Any failure removes the temporary file, so nothing partial is left.
This is O2's own writer; the M1/M2 Excel path is not changed here (its repair is OD-U15, on its own branch).
"""
from __future__ import annotations

import errno
import hashlib
import os
import uuid
from pathlib import Path

from .errors import OfficeError


def _same_place(p: Path) -> bool:
    return os.path.normcase(os.path.realpath(p)) == os.path.normcase(os.path.abspath(p))


def publish_copy(src: Path, dest: Path, expect_sha256: str) -> dict:
    """Copy `src` to `dest` without ever replacing a file. `src` must still hash to `expect_sha256`."""
    if not _same_place(dest.parent):
        raise OfficeError("PATH_REFUSED", "links, junctions and shortcuts are not followed")
    if os.path.lexists(dest):
        raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409)
    tmp = dest.parent / f".~uri-{uuid.uuid4().hex[:12]}{dest.suffix}.part"
    h = hashlib.sha256()
    try:
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_BINARY", 0), 0o644)
        with os.fdopen(fd, "wb") as out, open(src, "rb") as fin:
            for chunk in iter(lambda: fin.read(1 << 20), b""):
                h.update(chunk)
                out.write(chunk)
            out.flush()
            os.fsync(out.fileno())
        if h.hexdigest() != expect_sha256:
            raise OfficeError("TARGET_CHANGED", "the output changed after it was shown", 409)
        if not (_same_place(tmp) and _same_place(dest.parent)):
            raise OfficeError("PATH_REFUSED", "links, junctions and shortcuts are not followed")
        try:
            if os.name == "nt":
                os.rename(tmp, dest)
            else:
                os.link(tmp, dest)
        except FileExistsError:
            raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409) from None
        except OSError as e:
            if os.path.lexists(dest):
                raise OfficeError("DESTINATION_EXISTS", "choose a new file name", 409) from None
            if e.errno == errno.ENOSPC:
                raise OfficeError("DISK_FULL", "", 507) from None
            raise OfficeError("WRITE_FAILED", type(e).__name__, 500) from None
    except OSError as e:
        if e.errno == errno.ENOSPC:
            raise OfficeError("DISK_FULL", "", 507) from None
        raise OfficeError("WRITE_FAILED", type(e).__name__, 500) from None
    finally:
        try:
            if os.path.lexists(tmp):
                tmp.unlink()
        except OSError:
            pass
    return {"saved_to": dest.name, "sha256": expect_sha256}
