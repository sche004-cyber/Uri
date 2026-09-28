"""Bounded COPY_IN_COPY_OUT workspace (User ruling OD-3).

Only the named, hash-bound inputs are copied from M36 authorized roots into a
URI-owned scratch directory. URI, not the executor, computes what changed.
Write-back to an original happens only through `write_back`, which requires a
verified run, an explicit trusted user approval, and an original that still has
the hash recorded at copy-in.

Layout under <scratch_root>/<user_id>/workspaces/<run_id>/:
  files/          the only directory an executor may see or change
  manifest.json   copy-in manifest (outside files/)
  bundle/         per-run instructions and configuration (outside files/)
  verify/         fresh verification copies (outside files/)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

from uri_v1.memory.contracts import TrustedInput
from uri_v1.user_storage import user_scoped_path
from .acceptance import workspace_relpath
from .approval import approval_declined

WORKSPACE_SCHEMA_VERSION = "m37.workspace.v1"
_RUN_ID = re.compile(r"^[0-9a-f]{32}$")
MAX_FILES = 2000
MAX_TOTAL_BYTES = 512 * 1024 * 1024
_APPROVAL_WORDS = frozenset({"approve", "approved", "yes", "apply", "accept", "confirm"})


class WorkspaceStrategy(str, Enum):
    COPY_IN_COPY_OUT = "COPY_IN_COPY_OUT"
    DIRECT_ORIGINAL = "DIRECT_ORIGINAL"


class WorkspaceError(ValueError):
    """Typed failure: the reason code is the message."""


@dataclass(frozen=True)
class WorkspaceInput:
    role: str
    source_id: str
    content_sha256: str


@dataclass(frozen=True)
class ManifestEntry:
    role: str
    source_id: str
    root_id: str
    original_relpath: str
    relpath: str
    content_sha256: str
    size_bytes: int


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as stream:
        while chunk := stream.read(1024 * 1024): h.update(chunk)
    return h.hexdigest()


def new_run_id() -> str:
    return uuid.uuid4().hex


def diff_fingerprint(diff: dict) -> str:
    """Content-addressed fingerprint of a `Workspace.diff()` result's changes.

    Used to bind a VERIFICATION event to exactly the candidate bytes it verified,
    so `write_back` can check the live workspace against what the latest
    verification covered rather than against whatever RUN_RESULT happens to be
    last recorded (R-6): those can diverge when a run is recorded more than once.
    """
    changes = sorted((c["relpath"], c["after_sha256"]) for c in diff.get("changes", []))
    return hashlib.sha256(json.dumps(changes, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _atomic_json(path: Path, value) -> None:
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"))
    os.replace(tmp, path)


class Workspace:
    def __init__(self, base: Path, run_id: str, manifest: tuple):
        self.base, self.run_id, self.manifest = base, run_id, manifest

    @property
    def files(self) -> Path: return self.base / "files"

    @property
    def bundle(self) -> Path: return self.base / "bundle"

    @property
    def manifest_sha256(self) -> str:
        return hashlib.sha256((self.base / "manifest.json").read_bytes()).hexdigest()

    @classmethod
    def create(cls, *, user_id, scratch_root, sources, inputs, run_id=None,
               strategy=WorkspaceStrategy.COPY_IN_COPY_OUT) -> "Workspace":
        strategy = WorkspaceStrategy(strategy)
        if strategy is not WorkspaceStrategy.COPY_IN_COPY_OUT:
            # OD-3 allows DIRECT_ORIGINAL only by an explicit per-task user choice;
            # the minimum has no such flow, so it is refused rather than approximated.
            raise WorkspaceError("DIRECT_ORIGINAL_NOT_AVAILABLE_IN_MINIMUM")
        run_id = run_id or new_run_id()
        if not _RUN_ID.fullmatch(run_id): raise WorkspaceError("INVALID_RUN_ID")
        if not inputs or len(inputs) > 64: raise WorkspaceError("INPUTS_REQUIRED")
        base = Path(user_scoped_path(user_id, os.path.join("workspaces", run_id), str(Path(scratch_root).resolve())))
        roots = sources.roots()
        for root in roots.values():
            if Path(root).resolve() in (base, *base.parents) or base in Path(root).resolve().parents:
                raise WorkspaceError("WORKSPACE_OVERLAPS_AUTHORIZED_ROOT")
        base.mkdir(parents=True, exist_ok=False)
        files = base / "files"; files.mkdir(); (base / "bundle").mkdir(); (base / "verify").mkdir()
        entries, seen = [], set()
        try:
            scan = sources.scan()
            for item in inputs:
                if not isinstance(item, WorkspaceInput): raise WorkspaceError("INPUT_TYPE")
                locator = sources.locate(item.source_id, scan)
                ref = sources.fingerprint(locator) if locator else None
                if ref is None or ref.content_sha256 is None or ref.content_sha256 != item.content_sha256:
                    raise WorkspaceError("INPUT_NOT_CURRENT")
                name = workspace_relpath(ref.relpath.split("/")[-1])
                if name.casefold() in seen: raise WorkspaceError("DUPLICATE_INPUT_NAME")
                seen.add(name.casefold())
                data = (Path(roots[ref.root_id]) / ref.relpath).read_bytes()
                if hashlib.sha256(data).hexdigest() != item.content_sha256: raise WorkspaceError("INPUT_CHANGED_DURING_COPY")
                target = files / name
                with open(target, "xb") as out: out.write(data)
                if sha256_file(target) != item.content_sha256: raise WorkspaceError("COPY_HASH_MISMATCH")
                entries.append(ManifestEntry(item.role, ref.source_id, ref.root_id, ref.relpath, name, item.content_sha256, len(data)))
        except BaseException:
            shutil.rmtree(base, ignore_errors=True)
            raise
        manifest = tuple(entries)
        _atomic_json(base / "manifest.json", {"schema_version": WORKSPACE_SCHEMA_VERSION, "run_id": run_id,
                                              "strategy": strategy.value, "entries": [e.__dict__ for e in manifest]})
        return cls(base, run_id, manifest)

    @classmethod
    def open(cls, base) -> "Workspace":
        base = Path(base)
        raw = json.loads((base / "manifest.json").read_bytes())
        if raw.get("schema_version") != WORKSPACE_SCHEMA_VERSION: raise WorkspaceError("WORKSPACE_SCHEMA")
        return cls(base, raw["run_id"], tuple(ManifestEntry(**e) for e in raw["entries"]))

    # -- single writer -------------------------------------------------------
    def acquire(self, owner: str) -> None:
        try:
            fd = os.open(self.base / "writer.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            raise WorkspaceError("WORKSPACE_BUSY")
        with os.fdopen(fd, "w") as stream: stream.write(owner)

    def release(self, owner: str) -> None:
        lock = self.base / "writer.lock"
        if lock.read_text() != owner: raise WorkspaceError("WORKSPACE_LOCK_NOT_OWNED")
        lock.unlink()

    # -- URI-computed changes --------------------------------------------------
    def snapshot(self, directory: Path | None = None) -> tuple[dict, list]:
        """Hash every regular file; report anything else as a containment violation."""
        directory = Path(directory or self.files)
        found, violations, total = {}, [], 0
        for current, dirs, names in os.walk(directory, followlinks=False):
            for d in list(dirs):
                p = Path(current) / d
                if p.is_symlink() or not stat.S_ISDIR(os.lstat(p).st_mode):
                    violations.append(p.relative_to(directory).as_posix()); dirs.remove(d)
            for n in names:
                p = Path(current) / n; rel = p.relative_to(directory).as_posix()
                mode = os.lstat(p).st_mode
                if not stat.S_ISREG(mode):
                    violations.append(rel); continue
                total += os.lstat(p).st_size
                if len(found) >= MAX_FILES or total > MAX_TOTAL_BYTES: raise WorkspaceError("WORKSPACE_TOO_LARGE")
                found[rel] = sha256_file(p)
        return found, sorted(violations)

    def diff(self, directory: Path | None = None) -> dict:
        after, violations = self.snapshot(directory)
        before = {e.relpath: e.content_sha256 for e in self.manifest}
        changes = []
        for rel in sorted(set(before) | set(after)):
            b, a = before.get(rel), after.get(rel)
            if b == a: continue
            op = "ADDED" if b is None else "DELETED" if a is None else "MODIFIED"
            changes.append({"relpath": rel, "before_sha256": b, "after_sha256": a, "op": op})
        return {"changes": changes, "containment_violations": violations}

    def originals_unchanged(self, sources) -> list:
        """Return manifest entries whose original no longer has the copy-in hash."""
        return [e.relpath for e in self.manifest if not sources.verify_source(e.source_id, e.content_sha256)]

    def verification_copy(self) -> Path:
        target = self.base / "verify" / uuid.uuid4().hex
        after, violations = self.snapshot()
        if violations: raise WorkspaceError("CONTAINMENT_VIOLATION")
        for rel in after:
            dest = target / rel; dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(self.files / rel, dest)
        target.mkdir(parents=True, exist_ok=True)
        return target

    # -- approval-gated write-back ----------------------------------------------
    def write_back(self, approval: "WritebackApproval", *, sources, run_store) -> list:
        """Write approved, verified changes back to their originals.

        The verification status is never taken from the caller (F-7): it is read
        from `run_store`, the same append-only record URI's own verifier writes
        to, for this exact run. A run with no VERIFIED verification cannot write
        back. The candidate is also required to still match what was verified
        (defence in depth alongside the verifier's own post-run re-diff, F-8):
        anything that changed the workspace after verification invalidates the
        write-back.

        The candidate is checked against the diff fingerprint recorded on the
        latest VERIFICATION event itself, not against the latest RUN_RESULT (R-6):
        a run recorded more than once can leave the last RUN_RESULT describing
        bytes that were never the ones the last VERIFIED verdict actually covered,
        and comparing against RUN_RESULT would then write back never-verified
        bytes under a stale VERIFIED status.
        """
        if not isinstance(approval, WritebackApproval) or approval.run_id != self.run_id or not approval.valid():
            raise WorkspaceError("WRITEBACK_APPROVAL_REQUIRED")
        if approval.intake.user_id != self.base.parent.parent.name: raise WorkspaceError("WRITEBACK_APPROVAL_WRONG_USER")
        run = run_store.get(self.run_id)
        # M38 repair round 3: a script-based repair with no exact recompute oracle can
        # only be checked causally (verify.py's differential-rerun), so it is recorded
        # as "STRUCTURALLY_VERIFIED" rather than plain "VERIFIED" -- a real, weaker-but-
        # sufficient verdict for write-back, not a failure to reach VERIFIED.
        if run is None or not run.get("verifications") or run["verifications"][-1].get("status") not in ("VERIFIED", "STRUCTURALLY_VERIFIED"):
            raise WorkspaceError("WRITEBACK_REQUIRES_VERIFIED_RUN")
        diff = self.diff()
        if diff["containment_violations"]: raise WorkspaceError("CONTAINMENT_VIOLATION")
        verified_fingerprint = run["verifications"][-1].get("diff_sha256")
        if verified_fingerprint is None or verified_fingerprint != diff_fingerprint(diff):
            raise WorkspaceError("WRITEBACK_CANDIDATE_CHANGED")
        by_rel = {e.relpath: e for e in self.manifest}
        changes = {c["relpath"]: c for c in diff["changes"]}
        written = []
        for rel in approval.relpaths:
            change, entry = changes.get(rel), by_rel.get(rel)
            if not change or change["op"] != "MODIFIED" or entry is None: raise WorkspaceError("WRITEBACK_ONLY_MODIFIED_INPUTS")
            if change["after_sha256"] != approval.expected_after.get(rel): raise WorkspaceError("WRITEBACK_CANDIDATE_CHANGED")
            if not sources.verify_source(entry.source_id, entry.content_sha256): raise WorkspaceError("ORIGINAL_CHANGED_SINCE_COPY_IN")
            original = Path(sources.roots()[entry.root_id]) / entry.original_relpath
            tmp = original.with_name("." + original.name + "." + uuid.uuid4().hex + ".uri-writeback")
            shutil.copyfile(self.files / rel, tmp)
            if sha256_file(tmp) != change["after_sha256"]:
                tmp.unlink(); raise WorkspaceError("WRITEBACK_COPY_MISMATCH")
            os.replace(tmp, original)
            written.append({"relpath": rel, "source_id": entry.source_id, "before_sha256": entry.content_sha256,
                            "after_sha256": change["after_sha256"]})
        return written


# Issued only by `WritebackApproval.from_user`. `valid()` requires it, so an approval
# built directly or copied with `dataclasses.replace` never passes write-back's gate,
# whatever its text (Codex audit, requalification of 6420f3e: "show me the diff",
# "what changed?", "thanks" all validated when constructed directly).
_ISSUED = object()


@dataclass(frozen=True)
class WritebackApproval:
    """Explicit user approval for writing named verified artifacts back to originals."""
    run_id: str
    relpaths: tuple
    expected_after: dict
    intake: TrustedInput
    _issued: object = field(default=None, init=False, compare=False, repr=False)

    @classmethod
    def from_user(cls, intake, run_id, expected_after: dict) -> "WritebackApproval":
        if not isinstance(intake, TrustedInput) or not intake.trusted: raise WorkspaceError("TRUSTED_USER_INPUT_REQUIRED")
        # A negated or informally declined approval ("don't apply it", "nah apply it")
        # is not an approval (same rule as M36 audit F-2; informal negatives 2026-09-28).
        if approval_declined(intake.raw_text) or not set(re.findall(r"\w+", intake.raw_text.casefold())) & _APPROVAL_WORDS:
            raise WorkspaceError("EXPLICIT_APPROVAL_REQUIRED")
        if not expected_after: raise WorkspaceError("WRITEBACK_TARGETS_REQUIRED")
        approval = cls(run_id, tuple(sorted(expected_after)), dict(expected_after), intake)
        object.__setattr__(approval, "_issued", _ISSUED)
        return approval

    def valid(self) -> bool:
        # Only an approval `from_user` issued is valid: it alone applies the full bar
        # (trusted, not declined, an actual approval word). The decline re-check stays
        # as defense in depth (Codex audit, 2026-09-28).
        return (self._issued is _ISSUED and isinstance(self.intake, TrustedInput) and self.intake.trusted
                and bool(self.relpaths) and not approval_declined(self.intake.raw_text))

    def __reduce__(self): raise TypeError("approvals cannot be serialized")
