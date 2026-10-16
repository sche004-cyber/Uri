"""File access grants (AC7). Platform-aware and fail-closed.

The service may touch only:
  * a workbook the owner opened through the panel's file picker (an OPEN grant, recorded at open), and
  * a destination the owner chose in the panel's save dialog (a SAVE_AS grant),
and only inside the allowed roots the service was started with (default: the user's home folder). No roots means
nothing is allowed.

Path rule, in two steps:
  1. Shape (pure, checked for both platforms on every OS):
       Windows  an absolute drive path `X:\\...`; refused: relative, drive-relative (`C:x`), UNC/network (`\\\\server`,
                `//server`), device and extended paths (`\\\\.\\`, `\\\\?\\`), reserved device names (CON, NUL, COM1, ...)
                in any segment, alternate data streams (`file.xlsx:stream`), trailing dots/spaces in a segment.
       POSIX    an absolute path `/...`; refused: relative, `//`-prefixed (network on some systems), device/kernel trees
                (/dev, /proc, /sys, /run).
       Both     `.`/`..` segments, NUL bytes, over-long paths, anything but `.xlsx`.
  2. Filesystem (current platform): the real path (links and junctions resolved) must equal the given path and lie
     inside an allowed root; an open target must be a regular file, a save-as folder must exist.
"""
from __future__ import annotations

import json
import ntpath
import os
import posixpath
import re
import uuid
from dataclasses import dataclass
from pathlib import Path

from .errors import OfficeError

MAX_BYTES = 50 * 1024 * 1024
# O2 (plan §5 grants.py): per-kind suffixes and size caps. The `.xlsx` default and its messages are unchanged.
KIND_SUFFIX = {"xlsx": ".xlsx", "docx": ".docx", "pptx": ".pptx", "pdf": ".pdf",
               # authoring (OD-A5): a presentation template, and a picture to insert
               "pptx_template": (".pptx", ".potx"), "image": (".png", ".jpg", ".jpeg", ".gif", ".bmp"),
               "docx_template": (".docx", ".dotx")}
KIND_MAX_BYTES = {"xlsx": MAX_BYTES, "docx": 50 * 1024 * 1024, "pptx": 50 * 1024 * 1024, "pdf": 100 * 1024 * 1024,
                  "pptx_template": 50 * 1024 * 1024, "image": 20 * 1024 * 1024, "docx_template": 50 * 1024 * 1024}
KIND_LABEL = {"xlsx": "workbook", "docx": "document", "pptx": "presentation", "pdf": "PDF",
              "pptx_template": "template", "image": "picture", "docx_template": "template"}


def _suffixes(kind) -> tuple:
    v = KIND_SUFFIX[kind]
    return v if isinstance(v, tuple) else (v,)
MAX_PATH = 1024
_WIN_ABS = re.compile(r"^[A-Za-z]:[\\/]")
_WIN_RESERVED = re.compile(r"^(CON|PRN|AUX|NUL|CONIN\$|CONOUT\$|COM[0-9¹²³]|LPT[0-9¹²³])(\..*)?$", re.IGNORECASE)
_POSIX_DEVICE_TREES = ("/dev", "/proc", "/sys", "/run")


@dataclass(frozen=True)
class Grant:
    grant_id: str
    kind: str          # "open" | "save_as"
    path: Path


def _refuse(why):
    raise OfficeError("PATH_REFUSED", why)


def check_shape(raw, flavor: str | None = None, *, suffixes=(".xlsx",)) -> str:
    """Pure shape check. `flavor` is "nt" or "posix" (default: this OS). Returns the path string unchanged."""
    flavor = flavor or ("nt" if os.name == "nt" else "posix")
    if not isinstance(raw, str) or not raw or len(raw) > MAX_PATH or "\x00" in raw:
        _refuse("not a path")
    if flavor == "nt":
        if raw.startswith(("\\\\", "//", "\\/", "/\\")):
            _refuse("network and device paths are not allowed")
        if not _WIN_ABS.match(raw):
            _refuse("only absolute drive paths like C:\\folder\\file.xlsx are allowed")
        segs = re.split(r"[\\/]", raw[3:])
        if ":" in raw[2:]:
            _refuse("alternate data streams are not allowed")
        for s in segs:
            if s in (".", ".."):
                _refuse("relative segments are not allowed")
            if s and (s != s.rstrip(" .")):
                _refuse("names ending in a dot or space are not allowed")
            if _WIN_RESERVED.match(s):
                _refuse("device names are not allowed")
        suffix = ntpath.splitext(raw)[1]
    elif flavor == "posix":
        if not raw.startswith("/"):
            _refuse("only absolute paths are allowed")
        if raw.startswith("//"):
            _refuse("network paths are not allowed")
        norm = posixpath.normpath(raw)
        if any(norm == t or norm.startswith(t + "/") for t in _POSIX_DEVICE_TREES):
            _refuse("device and system paths are not allowed")
        if any(s in (".", "..") for s in raw.split("/")):
            _refuse("relative segments are not allowed")
        suffix = posixpath.splitext(raw)[1]
    else:
        raise ValueError(flavor)
    if suffix.lower() not in suffixes:
        _refuse("only .xlsx workbooks" if tuple(suffixes) == (".xlsx",) else
                "only " + ", ".join(suffixes) + " files")
    return raw


def _norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p)))


def _inside(path: str, root: str) -> bool:
    try:
        return os.path.commonpath([path, root]) == root
    except ValueError:          # different drives
        return False


def check_folder_shape(raw, flavor: str | None = None) -> str:
    """OD-R1: a folder the owner may add. Same shape rules as files (absolute local drive path, no network, device,
    stream or relative names), and never a whole drive or a system folder: permission stays folder-scoped."""
    flavor = flavor or ("nt" if os.name == "nt" else "posix")
    if not isinstance(raw, str) or not raw.strip():
        _refuse("not a folder")
    raw = raw.rstrip("\\/") if len(raw.rstrip("\\/")) > 2 else raw
    check_shape(raw + ("\\x.xlsx" if flavor == "nt" else "/x.xlsx"), flavor)
    if flavor == "nt":
        if re.fullmatch(r"[A-Za-z]:[\\/]?", raw):
            _refuse("a whole drive cannot be added; choose a folder on it")
        low = raw.replace("/", "\\").casefold()
        for env in ("SystemRoot", "ProgramFiles", "ProgramFiles(x86)", "ProgramData", "ProgramW6432"):
            sysdir = os.environ.get(env)
            if sysdir and (low == sysdir.casefold() or low.startswith(sysdir.casefold().rstrip("\\") + "\\")):
                _refuse("system folders cannot be added")
    else:
        if raw == "/" or raw.count("/") < 2 and raw in ("/usr", "/bin", "/etc", "/var", "/opt", "/boot", "/lib"):
            _refuse("system folders cannot be added")
    return raw


class Grants:
    """Open and save-as grants for files the owner picked, inside the allowed folders: the user home (or the service's
    --allow-root folders) plus folders the owner added (OD-R1, kept in `folders_file`, revocable)."""

    def __init__(self, allowed_roots=None, folders_file: Path | None = None):
        roots = [Path.home()] if allowed_roots is None else list(allowed_roots)
        self.base_roots = []
        for r in roots:
            rp = Path(r)
            if rp.is_dir():
                self.base_roots.append(_norm(os.path.realpath(rp)))
        self.folders_file = Path(folders_file) if folders_file else None
        self.added: list[str] = []                       # as the owner chose them (display spelling)
        if self.folders_file and self.folders_file.is_file():
            try:
                data = json.loads(self.folders_file.read_text(encoding="utf-8"))
                if not isinstance(data, dict) or not isinstance(data.get("folders", []), list):
                    raise ValueError("invalid folders list")
                restored = []
                for f in data.get("folders", []):
                    if not isinstance(f, str) or not Path(f).is_dir():
                        raise ValueError("invalid saved folder")
                    check_folder_shape(f)
                    if _norm(os.path.realpath(f)) != _norm(f):
                        raise ValueError("invalid saved folder")
                    restored.append(f)
                self.added = restored
            except (ValueError, OfficeError, OSError):
                self.added = []                          # a damaged list grants nothing extra
        self._by_id: dict[str, Grant] = {}

    @property
    def roots(self) -> list:
        return self.base_roots + [_norm(f) for f in self.added
                                  if Path(f).is_dir() and _norm(os.path.realpath(f)) == _norm(f)]

    def folders(self) -> list:
        return ([{"path": r, "kind": "default", "removable": False} for r in self.base_roots] +
                [{"path": f, "kind": "added", "removable": True} for f in self.added])

    def _save(self):
        if self.folders_file is None:
            return
        tmp = self.folders_file.with_suffix(".tmp")
        tmp.write_text(json.dumps({"folders": self.added}, indent=1), encoding="utf-8")
        os.replace(tmp, self.folders_file)

    def add_folder(self, raw) -> dict:
        path = check_folder_shape(raw)
        p = Path(path)
        if not p.is_dir():
            _refuse("the folder does not exist")
        if _norm(os.path.realpath(p)) != _norm(p):
            _refuse("links, junctions and shortcuts are not followed")
        n = _norm(p)
        if any(n == r or _inside(n, r) for r in self.roots):
            return {"added": False, "already_allowed": True, "folders": self.folders()}
        # A new folder that contains added ones replaces them (one entry per tree).
        self.added = [f for f in self.added if not _inside(_norm(f), n)] + [path]
        self._save()
        return {"added": True, "folders": self.folders()}

    def remove_folder(self, raw) -> dict:
        """Stop allowing an added folder. Refused while a file from it is open or waiting to be saved (close it or
        finish the save first), so nothing is left half-granted."""
        match = next((f for f in self.added if _norm(f) == _norm(raw)), None) if isinstance(raw, str) else None
        if match is None:
            raise OfficeError("FOLDER_NOT_ADDED", "only folders you added can be removed")
        root = _norm(os.path.realpath(match))
        if any(_inside(_norm(gr.path), root) for gr in self._by_id.values()):
            raise OfficeError("FOLDER_IN_USE", "close the files from this folder first", 409)
        self.added = [f for f in self.added if f is not match]
        self._save()
        return {"removed": True, "folders": self.folders()}

    def _real_inside(self, p: Path, *, must_exist: bool) -> Path:
        if not self.roots:
            _refuse("no folders are allowed for this service")
        real = os.path.realpath(p, strict=must_exist) if must_exist else os.path.realpath(p)
        if _norm(real) != _norm(p):
            _refuse("links, junctions and shortcuts are not followed")
        if not any(_inside(_norm(real), r) for r in self.roots):
            _refuse("the file is outside the folders URI may use")
        return p

    def grant_open(self, raw, *, kind: str = "xlsx") -> Grant:
        p = Path(check_shape(raw, suffixes=_suffixes(kind)))
        try:
            self._real_inside(p, must_exist=True)
        except OSError:
            _refuse("the file does not exist")
        if not p.is_file() or p.is_symlink():
            _refuse("not a regular local file")
        cap = KIND_MAX_BYTES[kind]
        if p.stat().st_size > cap:
            raise OfficeError("FILE_TOO_LARGE", f"the {KIND_LABEL[kind]} is larger than {cap // (1024 * 1024)} MB")
        return self._add("open", p)

    def grant_save_as(self, raw, *, kind: str = "xlsx") -> Grant:
        p = Path(check_shape(raw, suffixes=_suffixes(kind)))
        if not p.parent.is_dir():
            _refuse("the folder does not exist")
        self._real_inside(p.parent, must_exist=True)
        if p.exists() and (not p.is_file() or p.is_symlink()):
            _refuse("not a regular file")
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
