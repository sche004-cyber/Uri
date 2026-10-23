"""Post-integration housekeeping (LIFECYCLE-V3.1-STORAGE): safe, idempotent cleanup of disposable worktrees,
caches and merged branches, and verified evidence archives (cold tier) with restore.

    python -m scripts.dev_workflow.housekeeping inventory --repo R [--canonical-ref REF] [--root D ...]
                                                          [--records F|D ...] [--ledger F] [--min-age-hours H]
                                                          [--no-sizes] --out PLAN.json
    python -m scripts.dev_workflow.housekeeping apply --plan PLAN.json --journal-dir D [--archive-root D]
                                                      [--approve ID ...] [--classes OBSOLETE_BRANCH]
    python -m scripts.dev_workflow.housekeeping archive <dir> --archive-root D [--label L]
    python -m scripts.dev_workflow.housekeeping verify-archive <archive-id|zip> --archive-root D
    python -m scripts.dev_workflow.housekeeping restore <archive-id|zip> --archive-root D --to <new empty dir>
    python -m scripts.dev_workflow.housekeeping recover --journal-dir D [--repo R]
    python -m scripts.dev_workflow.housekeeping verify-chain <journal.jsonl|archive_index.jsonl>

``inventory`` is a read-only dry run: it writes a plan and changes nothing. ``apply`` acts only on DISPOSABLE,
PRUNABLE and CACHE items (OBSOLETE_BRANCH only when named in ``--classes``) and on items the owner names with
``--approve``; PROTECTED and ESSENTIAL_EVIDENCE items are refused even when approved, and an approved item that holds
uncommitted work or evidence is archived and verified before it is removed. Every item is re-inventoried before it is
touched (SKIPPED_CHANGED if it moved). A hash-chained write-ahead journal records INTENT before and DONE/FAILED after
every action; ``recover`` resolves an INTENT left by a crash from the real state. The receipt lists restore commands.

Boundary Guarantee: Development tooling only. Not part of the URI runtime. It never pushes, never touches remotes or
tags, never follows symlinks or junctions, and never deletes anything outside the plan.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import os
import re
import secrets
import shutil
import sqlite3
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from scripts.dev_workflow.milestones.store import atomic_write_bytes, file_sha256, os_lock

SCHEMA = "uri-housekeeping/1"
GENESIS = "0" * 64
GIT = ["git", "--no-optional-locks", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]
CANONICAL_REF = "uri-repo/integration/git-sync-20261008"
EVIDENCE_MARKERS = {"receipt.json", "RECEIPT.md", "events.jsonl", "state.json", "report_data.json",
                    "chain_summary.json"}
EVIDENCE_SUFFIXES = (".junit.xml",)
CACHE_DIRS = {"__pycache__", ".pytest_cache"}
SKIP_WALK = {".git", "node_modules", ".dart_tool", "build", "__pycache__", ".pytest_cache"}
PRESERVED_BRANCH_PREFIXES = ("preserve/", "receipts/", "audit/", "ledger/", "accepted/")
AUTO_CLASSES = {"DISPOSABLE", "PRUNABLE", "CACHE"}
OPTIONAL_CLASSES = {"OBSOLETE_BRANCH"}
APPROVABLE = {"DIRTY", "EVIDENCE", "REFERENCED", "LOCAL_ONLY", "AMBIGUOUS"}
NEVER = {"PROTECTED", "ESSENTIAL_EVIDENCE"}
MARKER_WALK_DEPTH = 6
RECORD_MAX_BYTES = 8 << 20
PATH_RE = re.compile(r"(?<![A-Za-z])([A-Za-z]:[\\/][^\s`'\"|<>()\[\]{},;*?]+)")


class HKError(Exception):
    def __init__(self, code: str, msg: str):
        super().__init__(f"{code}: {msg}")
        self.code = code


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def sha_text(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


def canon_json(obj) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def norm(p) -> str:
    return os.path.normcase(os.path.abspath(str(p))).replace("\\", "/").rstrip("/")


def git(repo, *args, check=False, timeout=300, inp: str | None = None) -> tuple[int, str, str]:
    try:
        p = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout, input=inp)
    except subprocess.TimeoutExpired:
        if check:
            raise HKError("GIT_TIMEOUT", f"git {' '.join(args)}")
        return 124, "", "timeout"
    if check and p.returncode:
        raise HKError("GIT_FAILED", f"git {' '.join(args)}: {p.stderr.strip()}")
    return p.returncode, p.stdout.strip(), p.stderr.strip()


def is_link(path: str | Path) -> bool:
    p = str(path)
    try:
        if os.path.islink(p):
            return True
        if hasattr(os.path, "isjunction") and os.path.isjunction(p):
            return True
        st = os.lstat(p)
        return bool(getattr(st, "st_file_attributes", 0) & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    except OSError:
        return False


def walk(root: Path, *, skip=frozenset(), max_depth: int | None = None):
    """os.walk that never follows symlinks or junctions (the Brain model folders on D: are junctions)."""
    root = Path(root)
    base_depth = len(root.parts)
    for d, dirs, files in os.walk(root, followlinks=False):
        depth = len(Path(d).parts) - base_depth
        dirs[:] = [x for x in dirs if x not in skip and not is_link(os.path.join(d, x))
                   and (max_depth is None or depth < max_depth)]
        yield Path(d), dirs, files


def tree_size(root: Path, budget_s: float = 120.0) -> tuple[int, bool]:
    total, deadline = 0, time.monotonic() + budget_s
    for d, _dirs, files in walk(root):
        for f in files:
            try:
                total += os.lstat(os.path.join(d, f)).st_size
            except OSError:
                pass
        if time.monotonic() > deadline:
            return total, False
    return total, True


def content_snapshot(root: Path) -> tuple[str, list[str]]:
    """Hash every entry without traversing links; fail closed if an entry cannot be read."""
    h = hashlib.sha256()
    links = []

    def visit(d: Path):
        for p in sorted(d.iterdir(), key=lambda p: p.name):
            rel = p.relative_to(root).as_posix()
            st = p.lstat()
            if is_link(p):
                links.append(rel)
                try:
                    target = os.readlink(p)
                except OSError:
                    target = "unknown-reparse-target"
                h.update(canon_json([rel, "link", target, st.st_mode,
                                     getattr(st, "st_reparse_tag", None)]).encode())
            elif stat.S_ISDIR(st.st_mode):
                h.update(canon_json([rel, "dir"]).encode())
                visit(p)
            elif stat.S_ISREG(st.st_mode):
                h.update(canon_json([rel, "file", st.st_mode, st.st_size, file_sha256(p)]).encode())
            else:
                raise HKError("UNSUPPORTED_ENTRY", f"{p} is not a regular file, directory or link")

    visit(root)
    return h.hexdigest(), links


# --------------------------------------------------------------------------- hash-chained append-only log

class Chain:
    """JSONL log; each line {seq, ts, kind, data, prev, hash}, hash = sha256(canonical JSON without hash). Appends are
    serialised by an OS lock and fsynced."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def read(self) -> list[dict]:
        if not self.path.is_file():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                try:
                    out.append(json.loads(line))
                except ValueError:
                    out.append({"_torn": line})
        return out

    def verify(self) -> list[str]:
        errs, prev = [], GENESIS
        for i, ev in enumerate(self.read(), 1):
            if "_torn" in ev:
                errs.append(f"line {i}: not JSON (torn write?)")
                break
            body = {k: v for k, v in ev.items() if k != "hash"}
            if ev.get("seq") != i or ev.get("prev") != prev or sha_text(canon_json(body)) != ev.get("hash"):
                errs.append(f"line {i}: chain broken")
                break
            prev = ev["hash"]
        return errs

    def append(self, kind: str, data: dict) -> dict:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with os_lock(self.path.with_name(self.path.name + ".lock")):
            evs = self.read()
            errs = self.verify()
            if errs:
                raise HKError("CHAIN_BROKEN", f"{self.path}: {errs[0]}")
            ev = {"seq": len(evs) + 1, "ts": utcnow(), "kind": kind, "data": data,
                  "prev": evs[-1]["hash"] if evs else GENESIS}
            ev["hash"] = sha_text(canon_json(ev))
            with self.path.open("ab") as f:
                f.write((canon_json(ev) + "\n").encode("utf-8"))
                f.flush()
                os.fsync(f.fileno())
            return ev


# --------------------------------------------------------------------------- context for classification

def _worktrees(repo: Path) -> list[dict]:
    _, out, _ = git(repo, "worktree", "list", "--porcelain", check=True)
    wts, cur = [], None
    for line in out.splitlines() + [""]:
        if not line.strip():
            if cur:
                wts.append(cur)
            cur = None
            continue
        key, _, val = line.partition(" ")
        if key == "worktree":
            cur = {"path": val, "head": None, "branch": None, "locked": False, "prunable": False, "bare": False}
        elif cur is None:
            continue
        elif key == "HEAD":
            cur["head"] = val
        elif key == "branch":
            cur["branch"] = val
        elif key == "detached":
            cur["branch"] = None
        elif key == "locked":
            cur["locked"] = True
        elif key == "prunable":
            cur["prunable"] = True
        elif key == "bare":
            cur["bare"] = True
    for i, w in enumerate(wts):
        w["main"] = i == 0
    return wts


def _record_paths(records: list[str]) -> dict[str, set[str]]:
    """Absolute paths cited by authoritative records (decisions.md, developmental.md, audit/MM docs, receipts), each
    with the record files that cite it (I-1: the owner judges a citation by its source)."""
    found: dict[str, set[str]] = {}
    files: list[Path] = []
    for r in records:
        p = Path(r)
        if p.is_file():
            files.append(p)
        elif p.is_dir():
            for d, _dirs, fs in walk(p, skip=SKIP_WALK):
                files += [d / f for f in fs if f.endswith((".md", ".json", ".txt"))]
    for f in files:
        try:
            if f.stat().st_size > RECORD_MAX_BYTES:
                continue
            text = f.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for m in PATH_RE.finditer(text):
            found.setdefault(norm(m.group(1).rstrip(".:")), set()).add(f.as_posix())
    return found


def _ledger_refs(ledger: str | None) -> tuple[set[str], set[str]]:
    """(worktree paths of non-terminal ledger tasks, branches of non-terminal tasks); v3 state dirs are added to the
    first set (referenced evidence)."""
    try:
        from scripts.dev_workflow.task_ledger import TERMINAL, default_path
    except ImportError:
        return set(), set()
    p = Path(ledger) if ledger else default_path()
    if not p.is_file():
        return set(), set()
    wal = p.with_name(p.name + "-wal")
    if wal.exists() and wal.stat().st_size:
        raise HKError("LEDGER_BUSY", f"{p} has an active WAL; inventory cannot use an immutable snapshot")
    # Inventory must not initialize, migrate or checkpoint the source ledger.
    db = sqlite3.connect(p.resolve().as_uri() + "?mode=ro&immutable=1", uri=True)
    db.row_factory = sqlite3.Row
    try:
        paths, branches = set(), set()
        for t in db.execute("SELECT * FROM tasks"):
            if t["status"] in TERMINAL:
                continue
            if t["worktree"]:
                paths.add(norm(t["worktree"]))
            if t["branch"]:
                branches.add(t["branch"])
        for r in db.execute("SELECT state_dir FROM v3_links"):
            paths.add(norm(r["state_dir"]))
        return paths, branches
    finally:
        db.close()


class Ctx:
    def __init__(self, repo: Path, canonical_ref: str, records: list[str], ledger: str | None,
                 min_age_hours: float, sizes: bool):
        self.repo = Path(repo)
        self.records, self.ledger = list(records), ledger
        rc, sha, _ = git(repo, "rev-parse", "--verify", "-q", f"{canonical_ref}^{{commit}}")
        if rc or not sha:
            raise HKError("NO_CANONICAL", f"{canonical_ref} does not resolve in {repo}; refusing to classify")
        self.canonical_ref, self.canonical = canonical_ref, sha
        _, full, _ = git(repo, "rev-parse", "--symbolic-full-name", canonical_ref)
        self.canonical_full = full or None
        _, common, _ = git(repo, "rev-parse", "--path-format=absolute", "--git-common-dir")
        self.common_dir = Path(common) if common else None
        self.cited = _record_paths(records)
        self.task_paths, self.task_branches = _ledger_refs(ledger)
        self.min_age_s = min_age_hours * 3600
        self.sizes = sizes
        self.cwd = norm(os.getcwd())
        self.wt_paths: set[str] = set()
        self._reach: dict[str, str] = {}
        self._dir_cls: dict[str, str] = {}

    def fresh(self) -> tuple["Ctx", dict[str, dict]]:
        """Rebuild authority and git registration at each source recheck."""
        ctx = Ctx(self.repo, self.canonical_ref, self.records, self.ledger,
                  self.min_age_s / 3600, False)
        wts = {norm(w["path"]): w for w in _worktrees(ctx.repo)}
        ctx.wt_paths = set(wts)
        return ctx, wts

    def cited_under(self, path: str) -> list[str]:
        p = norm(path)
        return sorted(c for c in self.cited if c == p or c.startswith(p + "/"))[:5]

    def cited_by(self, path: str) -> list[str]:
        p = norm(path)
        files = set()
        for c, srcs in self.cited.items():
            if c == p or c.startswith(p + "/"):
                files |= srcs
        return sorted(files)[:10]

    def dir_class(self, path: Path) -> str:
        """Memoised directory class for cache-ancestor checks (one classification per directory per context)."""
        key = norm(path)
        if key not in self._dir_cls:
            self._dir_cls[key] = classify_dir(self, path)["cls"]
        return self._dir_cls[key]

    def task_ref(self, path: str) -> bool:
        p = norm(path)
        return any(t == p or t.startswith(p + "/") for t in self.task_paths)

    def reach(self, sha: str) -> str:
        """CANONICAL | REMOTE | LOCAL | NONE: where a commit is kept if its worktree goes away."""
        if sha not in self._reach:
            rc, _, _ = git(self.repo, "merge-base", "--is-ancestor", sha, self.canonical)
            if rc == 0:
                self._reach[sha] = "CANONICAL"
            else:
                _, out, _ = git(self.repo, "rev-list", "-n", "1", sha, "--not", "--remotes")
                if not out:
                    self._reach[sha] = "REMOTE"
                else:
                    _, out2, _ = git(self.repo, "rev-list", "-n", "1", sha, "--not", "--branches", "--tags")
                    self._reach[sha] = "LOCAL" if not out2 else "NONE"
        return self._reach[sha]


def _markers(path: Path, *, cache: bool = False) -> list[str]:
    hits = []
    # A cache is about to be deleted in full: inspect its full contents, including
    # nested cache directories that the normal inventory walk intentionally skips.
    for d, _dirs, files in walk(path, skip=frozenset() if cache else SKIP_WALK,
                                max_depth=None if cache else MARKER_WALK_DEPTH):
        for f in files:
            if f in EVIDENCE_MARKERS or f.endswith(EVIDENCE_SUFFIXES):
                hits.append((d / f).relative_to(path).as_posix())
    return sorted(hits)


def _untracked_markers(path: Path, markers: list[str]) -> list[str]:
    if not markers:
        return []
    rc, out, _ = git(path, "ls-files", "--", *markers)
    tracked = set(out.splitlines()) if rc == 0 else set()
    return [m for m in markers if m not in tracked]


def _gitdir(path: Path) -> Path | None:
    """The worktree's absolute git dir, from git itself (a relative `gitdir:` line resolves against the worktree,
    never against this process's cwd; FB-3 FB3-03). None: not determinable."""
    rc, out, _ = git(path, "rev-parse", "--absolute-git-dir")
    return Path(out) if rc == 0 and out and Path(out).is_dir() else None


def _unreferenced(ctx: "Ctx", shas) -> list[str] | None:
    """Of these commits, those that no branch, tag, remote or canonical holds. Every sha is checked (FB-3 FB3-04: no
    truncation; rev-list --stdin has no command-line limit). None when git fails (callers then protect)."""
    shas = list(dict.fromkeys(s for s in shas if len(s) == 40 and set(s) - {"0"}))
    if not shas:
        return []
    rc, out, _ = git(ctx.repo, "cat-file", "--batch-check", inp="".join(f"{s}\n" for s in shas))
    if rc != 0:
        return None
    present = [s for s, line in zip(shas, out.splitlines()) if not line.endswith("missing")]
    if not present:
        return []
    rc, out, _ = git(ctx.repo, "rev-list", "--stdin", "--not", "--branches", "--tags", "--remotes", ctx.canonical,
                     inp="".join(f"{s}\n" for s in present))
    return out.splitlines() if rc == 0 else None


def _reflog(where, ref: str) -> list[str] | None:
    """Every commit a ref's reflog names, read by git itself, so any ref backend (files or reftable) works
    (FB-4 FB4-04). None: git could not read it."""
    rc, out, _ = git(where, "reflog", "show", "--format=%H", ref, "--")
    return out.split() if rc == 0 else None


def _commits_only_in_log(ctx: "Ctx", log: Path) -> list[str] | None:
    """Reflog-file variant of the check (kept for files-backend logs read directly)."""
    if not log.is_file():
        return []
    try:
        shas = [s for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                for s in line.split()[:2]]
    except OSError:
        return None
    return _unreferenced(ctx, shas)


def _hidden_edits(path: Path) -> list[str] | None:
    """Tracked files whose local state git status does not report: assume-unchanged (lowercase tag) or skip-worktree
    ('S') index flags (FB-2 FB2-01). None: git failed."""
    rc, out, _ = git(path, "ls-files", "-v", "-z")
    if rc != 0:
        return None
    hidden = []
    for entry in out.split("\0"):
        if len(entry) > 2 and entry[1] == " " and (entry[0].islower() or entry[0] == "S"):
            hidden.append(entry[2:])
    return sorted(hidden)


def _reflog_only_commits(ctx: "Ctx", path: Path) -> list[str] | None:
    """Commits in the worktree's own HEAD reflog that no branch, tag, remote or canonical holds: removing the
    worktree removes that reflog (FB-2 FB2-02). None: could not be determined."""
    shas = _reflog(path, "HEAD")
    return None if shas is None else _unreferenced(ctx, shas)


def _idle_s(path: Path) -> float:
    stamps = []
    try:
        gd = _gitdir(path)
        if gd is not None:
            for n in ("HEAD", "index", "logs/HEAD"):
                if (gd / n).exists():
                    stamps.append((gd / n).stat().st_mtime)
        stamps.append(path.stat().st_mtime)
    except (OSError, IndexError):
        pass
    return max(0.0, time.time() - max(stamps)) if stamps else 0.0


def lifecycle_run_of(path: Path) -> tuple[Path, str] | None:
    """(state dir, stage) when ``path`` lies inside a lifecycle driver state dir (its ``.work`` trees: qualify,
    baseline, audit checkouts). A run that is not COMPLETE may still use or recreate them."""
    p = Path(path)
    for anc in list(p.parents)[:8]:
        if (anc / "state.json").is_file() and (anc / "events.jsonl").is_file():
            try:
                stage = json.loads((anc / "state.json").read_text(encoding="utf-8")).get("stage") or "UNKNOWN"
            except (OSError, ValueError):
                stage = "UNREADABLE"
            return anc, str(stage)
    return None


def _regenerable(entry: str) -> bool:
    """Ignored entries that are pure caches (rebuilt automatically). Everything else ignored - .env, credentials,
    uri_workspace/evidence, work/c1 checkpoints, build outputs - is content outside git (FB-1 N-01)."""
    parts = [x for x in entry.replace("\\", "/").split("/") if x]
    return bool(parts) and (any(x in CACHE_DIRS for x in parts) or parts[-1].endswith((".pyc", ".pyo")))


def _ignored_content(path: Path) -> list[str] | None:
    """Ignored, untracked entries of a worktree that are not regenerable caches (None: git failed)."""
    rc, out, _ = git(path, "ls-files", "-z", "--others", "--ignored", "--exclude-standard", "--directory")
    if rc != 0:
        return None
    return sorted(e for e in out.split("\0") if e and not _regenerable(e))


def classify_worktree(ctx: Ctx, w: dict) -> dict:
    path = Path(w["path"])
    item = {"id": "wt:" + sha_text(norm(path))[:12], "kind": "worktree", "path": str(path), "head": w["head"],
            "branch": w["branch"], "reasons": []}
    if w["main"] or w["bare"]:
        item.update(cls="PROTECTED", action="none")
        item["reasons"].append("main worktree")
        item["fingerprint"] = sha_text(canon_json([w["head"], w["branch"], "main"]))
        return item
    run = lifecycle_run_of(path)
    active_run = run is not None and run[1] != "COMPLETE"
    if not path.is_dir():
        # FB-1 N-02: the registration may be the only thing keeping a detached commit reachable
        reach = ctx.reach(w["head"]) if w["head"] else "NONE"
        orphan = reach == "NONE"
        keep = w["locked"] or active_run or orphan
        item.update(cls="PROTECTED" if keep else "PRUNABLE", action="none" if keep else "worktree-prune", reach=reach)
        item["reasons"].append("directory missing" + (" but locked" if w["locked"] else "")
                               + (f" inside lifecycle run {run[0].as_posix()} (stage {run[1]})" if active_run else "")
                               + (" and its HEAD is on no branch, tag, remote or canonical (commits would be lost)"
                                  if orphan else ""))
        if w["head"]:
            item["restore"] = f"git -C {ctx.repo.as_posix()} worktree add --detach {path.as_posix()} {w['head']}"
        item["fingerprint"] = sha_text(canon_json([w["head"], w["branch"], "missing", w["locked"], active_run, reach]))
        return item
    rc, status, _ = git(path, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules")
    dirty = len(status.splitlines()) if rc == 0 else -1
    um = _untracked_markers(path, _markers(path))
    ignored = _ignored_content(path)
    hidden = _hidden_edits(path)
    reflog_only = _reflog_only_commits(ctx, path)
    reach = ctx.reach(w["head"]) if w["head"] else "NONE"
    cited = ctx.cited_under(str(path))
    idle = _idle_s(path)
    item.update(dirty=dirty, evidence=um[:20], evidence_count=len(um), reach=reach, cited=cited,
                ignored=(ignored or [])[:20], ignored_count=len(ignored) if ignored is not None else -1,
                hidden=(hidden or [])[:20], hidden_count=len(hidden) if hidden is not None else -1,
                reflog_only=(reflog_only or [])[:20],
                cited_by=ctx.cited_by(str(path)) if cited else [],
                idle_hours=round(idle / 3600, 1))
    branch_short = w["branch"][len("refs/heads/"):] if w["branch"] else None
    protect = []
    if w["locked"]:
        protect.append("locked")
    if active_run:
        protect.append(f"driver work tree of lifecycle run {run[0].as_posix()} (stage {run[1]})")
    if norm(path) == ctx.cwd or ctx.cwd.startswith(norm(path) + "/"):
        protect.append("current working directory")
    if ctx.task_ref(str(path)) or (branch_short and branch_short in ctx.task_branches):
        protect.append("worktree of a non-terminal ledger task")
    if reach == "NONE":
        protect.append("HEAD is on no branch, tag, remote or canonical (commits would be lost)")
    if branch_short and reach in ("LOCAL", "NONE"):
        protect.append(f"branch {branch_short} has commits on neither canonical nor any remote")
    if rc != 0:
        protect.append("git status failed")
    if ignored is None:
        protect.append("git ls-files (ignored entries) failed")
    if hidden is None:
        protect.append("git ls-files -v (index flags) failed")
    if reflog_only is None:
        protect.append("worktree reflog could not be checked")
    elif reflog_only:
        protect.append(f"{len(reflog_only)} commit(s) kept only by this worktree's HEAD reflog (would be lost)")
    if protect:
        item.update(cls="PROTECTED", action="none")
        item["reasons"] += protect
    elif um:
        item.update(cls="EVIDENCE", action="archive-then-remove (needs --approve)")
        item["reasons"].append(f"{len(um)} untracked evidence files" + (f", {dirty} uncommitted/untracked entries"
                                                                        if dirty > 0 else ""))
    elif dirty > 0 or ignored or hidden:
        item.update(cls="DIRTY", action="archive-then-remove (needs --approve)")
        item["reasons"].append(", ".join(x for x in (f"{dirty} uncommitted/untracked entries" if dirty > 0 else "",
                                                     f"{len(ignored)} ignored entries outside git" if ignored else "",
                                                     f"{len(hidden)} tracked file(s) hidden from git status by "
                                                     "assume-unchanged/skip-worktree" if hidden else "")
                                         if x))
    elif cited:
        item.update(cls="REFERENCED", action="remove (needs --approve; clean, nothing outside git)")
        item["reasons"].append("cited by an authoritative record")
    elif reach == "LOCAL":
        item.update(cls="LOCAL_ONLY", action="remove (needs --approve; clean, nothing outside git)")
        item["reasons"].append("HEAD kept only by a local branch or tag")
    elif idle < ctx.min_age_s:
        item.update(cls="AMBIGUOUS", action="remove (needs --approve; clean, nothing outside git)")
        item["reasons"].append(f"used {idle / 3600:.1f} h ago (< {ctx.min_age_s / 3600:.0f} h)")
    else:
        item.update(cls="DISPOSABLE", action="worktree-remove")
        item["reasons"].append(f"clean, HEAD on {reach.lower()}, unreferenced, idle {idle / 3600:.0f} h")
    item["restore"] = (f"git -C {ctx.repo.as_posix()} worktree add "
                       + (f"{path.as_posix()} {branch_short}" if branch_short else
                          f"--detach {path.as_posix()} {w['head']}"))
    snapshot, links = content_snapshot(path) if item["cls"] != "PROTECTED" else (None, [])
    item["links"] = links
    item["fingerprint"] = sha_text(canon_json([w["head"], w["branch"], w["locked"], dirty, um, reach,
                                                status, snapshot, ignored, hidden, reflog_only]))
    return item


def classify_dir(ctx: Ctx, path: Path) -> dict:
    um = _markers(path)
    cited = ctx.cited_under(str(path))
    item = {"id": "dir:" + sha_text(norm(path))[:12], "kind": "dir", "path": str(path), "evidence": um[:20],
            "evidence_count": len(um), "cited": cited, "cited_by": ctx.cited_by(str(path)) if cited else [],
            "reasons": []}
    nested = sorted(w for w in ctx.wt_paths if w.startswith(norm(path) + "/"))
    if nested:
        item.update(cls="PROTECTED", action="none (handle its worktrees individually)", nested_worktrees=len(nested))
        item["reasons"].append(f"contains {len(nested)} registered worktree(s)")
    elif ctx.task_ref(str(path)):
        item.update(cls="PROTECTED", action="none")
        item["reasons"].append("referenced by a non-terminal ledger task or linked lifecycle run")
    elif um or cited:
        item.update(cls="ESSENTIAL_EVIDENCE", action="keep (archive copy to cold tier allowed)")
        item["reasons"].append(("evidence files" if um else "") + (" + " if um and cited else "")
                               + ("cited by a record" if cited else ""))
    else:
        item.update(cls="AMBIGUOUS", action="archive-then-remove (needs --approve)")
        item["reasons"].append("no evidence markers and not cited; purpose unknown")
    snapshot, links = content_snapshot(path) if item["cls"] != "PROTECTED" else (None, [])
    item["links"] = links
    item["fingerprint"] = sha_text(canon_json([um, cited, snapshot]))
    return item


def _caches(root: Path) -> list[Path]:
    out = []
    for d, dirs, _files in walk(root, skip=SKIP_WALK - CACHE_DIRS):
        for x in list(dirs):
            if (d / x / ".git").exists():       # FB-1 N-07: another repository or worktree; never descend
                dirs.remove(x)
                continue
            if x in CACHE_DIRS:
                out.append(d / x)
                dirs.remove(x)
    return out


def classify_cache(ctx: Ctx, path: Path, parent: Path) -> dict:
    markers = _markers(path, cache=True)
    cited = ctx.cited_under(str(path))
    ancestors = [parent]
    ancestors.extend(a for a in path.parents if a != parent and norm(a).startswith(norm(parent) + "/"))
    protected = [str(a) for a in ancestors if ctx.dir_class(a) in NEVER]
    cls = "PROTECTED" if protected else "ESSENTIAL_EVIDENCE" if markers or cited else "CACHE"
    snapshot, links = content_snapshot(path)
    return {"id": "cache:" + sha_text(norm(path))[:12], "kind": "cache", "path": str(path),
            "cls": cls, "action": "delete (regenerable)" if cls == "CACHE" else "none",
            "reasons": (["protected or evidence-bearing ancestor: " + ", ".join(protected)] if protected else
                        ["evidence markers or authoritative references"] if cls == "ESSENTIAL_EVIDENCE" else
                        ["regenerable cache"]), "evidence": markers[:20], "evidence_count": len(markers),
            "cited": cited, "parent_path": str(parent), "fingerprint": snapshot, "links": links}


def cache_group(parent: Path, parent_id: str, members: list[dict]) -> dict:
    """One plan item for all regenerable caches under one top-level directory (I-3: the live plan had 14,769
    single-cache items)."""
    paths = sorted(m["path"] for m in members)
    return {"id": "caches:" + sha_text(norm(parent))[:12], "kind": "caches", "path": str(parent), "paths": paths,
            "cls": "CACHE", "action": f"delete {len(paths)} regenerable cache dir(s)", "parent": parent_id,
            "reasons": [f"{len(paths)} regenerable cache dir(s) (__pycache__, .pytest_cache)"],
            "links": any(m.get("links") for m in members),
            "fingerprint": sha_text(canon_json(sorted((m["path"], m["fingerprint"]) for m in members)))}


def _symref_targets(ctx: Ctx) -> set[str]:
    """Refs that a symbolic ref points to (deleting one leaves the symref dangling)."""
    _, out, _ = git(ctx.repo, "for-each-ref", "--format=%(symref)")
    return {x for x in out.split() if x}


def _branch_reflog_only(ctx: Ctx, name: str) -> list[str] | None:
    """Commits kept only by refs/heads/<name>'s own reflog (deleting the ref deletes that reflog)."""
    shas = _reflog(ctx.repo, "refs/heads/" + name)
    return None if shas is None else _unreferenced(ctx, shas)


def classify_branches(ctx: Ctx, checked_out: set[str]) -> list[dict]:
    _, out, _ = git(ctx.repo, "for-each-ref", "refs/heads", "--format=%(refname) %(objectname) %(symref)",
                    check=True)
    items = []
    rows = [(line.split(" ") + ["", ""])[:3] for line in out.splitlines()]
    sym_targets = _symref_targets(ctx)
    for ref, sha, symref in rows:
        name = ref[len("refs/heads/"):]
        if symref or ref in sym_targets:                    # FB-4 FB4-02: never a symref, never a symref's target
            continue
        if sha == ctx.canonical and not ctx.canonical_full:  # FB-4 FB4-05: canonical given as a SHA: this branch
            continue                                          # may be the only ref holding canonical's tip
        if ref in checked_out or name.startswith(PRESERVED_BRANCH_PREFIXES) or name in ctx.task_branches:
            continue
        if ref == ctx.canonical_full:                       # FB-3 FB3-01: never the canonical ref itself
            continue
        if ctx.reach(sha) != "CANONICAL":
            continue
        if _branch_reflog_only(ctx, name) != []:            # FB-3 FB3-05: its reflog alone holds commits, or unknown
            continue
        items.append({"id": "br:" + sha_text(ref)[:12], "kind": "branch", "path": ref, "head": sha,
                      "cls": "OBSOLETE_BRANCH", "action": "delete-ref (needs --classes OBSOLETE_BRANCH)",
                      "reasons": [f"tip is contained in canonical {ctx.canonical[:12]}"],
                      "restore": f"git -C {ctx.repo.as_posix()} branch {name} {sha}",
                      "fingerprint": sha_text(canon_json([ref, sha]))})
    return items


def inventory(repo, *, canonical_ref=CANONICAL_REF, roots=(), records=(), ledger=None, min_age_hours=24.0,
              sizes=True) -> dict:
    t0 = time.monotonic()
    ctx = Ctx(Path(repo), canonical_ref, list(records), ledger, min_age_hours, sizes)
    wts = _worktrees(ctx.repo)
    wt_paths = {norm(w["path"]) for w in wts}
    ctx.wt_paths = wt_paths
    items = [classify_worktree(ctx, w) for w in wts]
    for root in roots:
        root = Path(root)
        if not root.is_dir():
            continue
        for child in sorted(root.iterdir()):
            if not child.is_dir() or is_link(child) or norm(child) in wt_paths or (child / ".git").exists():
                continue
            it = classify_dir(ctx, child)
            items.append(it)
            if it["cls"] == "PROTECTED":
                continue
            group = []
            for c in _caches(child):
                cache_item = classify_cache(ctx, c, child)
                cache_item["parent"] = it["id"]
                if cache_item["cls"] == "CACHE":
                    group.append(cache_item)
                else:
                    items.append(cache_item)       # protected or evidence-bearing caches stay visible one by one
            if group:
                items.append(cache_group(child, it["id"], group))
    items += classify_branches(ctx, {w["branch"] for w in wts if w["branch"]})
    if sizes:
        for it in items:
            if it["kind"] == "caches":
                sizes_ = [tree_size(Path(q)) for q in it["paths"] if Path(q).is_dir()]
                it["bytes"], it["bytes_complete"] = sum(b for b, _ in sizes_), all(c for _, c in sizes_)
            elif it["kind"] in ("worktree", "dir", "cache") and Path(it["path"]).is_dir():
                it["bytes"], it["bytes_complete"] = tree_size(Path(it["path"]))
    summary: dict[str, dict] = {}
    for it in items:
        s = summary.setdefault(it["cls"], {"count": 0, "bytes": 0})
        s["count"] += 1
        s["bytes"] += it.get("bytes", 0)
    plan = {"schema": SCHEMA, "plan_id": f"hk-{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ}-"
                                         f"{secrets.token_hex(3)}",
            "created_at": utcnow(), "repo": str(ctx.repo), "canonical": {"ref": canonical_ref, "sha": ctx.canonical},
            "roots": [str(r) for r in roots], "records": [str(r) for r in records], "ledger": ledger,
            "min_age_hours": min_age_hours, "items": items, "summary": summary,
            "elapsed_s": round(time.monotonic() - t0, 2),
            "policy": {"auto": sorted(AUTO_CLASSES), "optional": sorted(OPTIONAL_CLASSES),
                       "approvable": sorted(APPROVABLE), "never": sorted(NEVER)}}
    return plan


# --------------------------------------------------------------------------- archive / verify / restore

def _safe_member(name: str) -> bool:
    p = name.replace("\\", "/")
    return bool(p) and not p.startswith("/") and ":" not in p and ".." not in p.split("/")


def archive(src, archive_root, label: str | None = None) -> dict:
    src = Path(src)
    if not src.is_dir() or is_link(src):
        raise HKError("NOT_A_DIR", f"{src} is not a real directory")
    root = Path(archive_root)
    root.mkdir(parents=True, exist_ok=True)
    label = re.sub(r"[^A-Za-z0-9_.-]", "-", label or src.name)[:80]
    aid = f"{label}-{datetime.datetime.now(datetime.timezone.utc):%Y%m%dT%H%M%SZ}-{secrets.token_hex(3)}"
    final, tmp = root / f"{aid}.zip", root / f"{aid}.zip.tmp"
    manifest, links, total = [], [], 0
    with zipfile.ZipFile(tmp, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as z:
        for d, dirs, files in walk(src):
            for x in os.listdir(d):
                if is_link(d / x):
                    links.append((d / x).relative_to(src).as_posix())
            for f in sorted(files):
                fp = d / f
                if is_link(fp):
                    continue
                rel = fp.relative_to(src).as_posix()
                if rel == ".git":       # a worktree's link file; the commits live in the repository
                    continue
                z.write(fp, "data/" + rel)
                h = file_sha256(fp)
                size = fp.stat().st_size
                manifest.append({"path": rel, "sha256": h, "size": size})
                total += size
        z.writestr("manifest.json", json.dumps({"schema": SCHEMA, "source": str(src), "files": manifest,
                                                "links_not_followed": links}, indent=1, sort_keys=True))
    errs = _verify_zip(tmp)
    if errs:
        tmp.unlink(missing_ok=True)
        raise HKError("ARCHIVE_VERIFY_FAILED", "; ".join(errs[:5]))
    zsha = file_sha256(tmp)
    os.replace(tmp, final)
    data = {"archive_id": aid, "source": str(src), "zip": str(final), "zip_sha256": zsha, "files": len(manifest),
            "bytes": total, "zip_bytes": final.stat().st_size, "label": label, "links_not_followed": len(links)}
    Chain(root / "archive_index.jsonl").append("ARCHIVED", data)
    return data


def _verify_zip(zpath: Path) -> list[str]:
    errs = []
    try:
        with zipfile.ZipFile(zpath) as z:
            man = json.loads(z.read("manifest.json"))
            names = set(z.namelist())
            for e in man["files"]:
                n = "data/" + e["path"]
                if not _safe_member(e["path"]) or n not in names:
                    errs.append(f"{e['path']}: missing or unsafe")
                    continue
                h = hashlib.sha256()
                with z.open(n) as f:
                    for chunk in iter(lambda: f.read(1 << 20), b""):
                        h.update(chunk)
                if h.hexdigest() != e["sha256"]:
                    errs.append(f"{e['path']}: sha256 mismatch")
            extra = names - {"manifest.json"} - {"data/" + e["path"] for e in man["files"]}
            errs += [f"{n}: not in manifest" for n in sorted(extra)]
    except (OSError, KeyError, ValueError, zipfile.BadZipFile) as e:
        errs.append(f"unreadable archive: {e}")
    return errs


def _resolve_archive(ident: str, archive_root) -> tuple[Path, dict | None]:
    p = Path(ident)
    if p.suffix == ".zip" and p.is_file():
        entry = next((e["data"] for e in Chain(Path(archive_root) / "archive_index.jsonl").read()
                      if e.get("data", {}).get("zip") and norm(e["data"]["zip"]) == norm(p)), None)
        return p, entry
    for e in Chain(Path(archive_root) / "archive_index.jsonl").read():
        if e.get("data", {}).get("archive_id") == ident:
            return Path(e["data"]["zip"]), e["data"]
    raise HKError("ARCHIVE_NOT_FOUND", ident)


def verify_archive(ident: str, archive_root) -> dict:
    zpath, entry = _resolve_archive(ident, archive_root)
    errs = Chain(Path(archive_root) / "archive_index.jsonl").verify()
    if not zpath.is_file():
        return {"ok": False, "errors": [f"{zpath} missing"] + errs}
    if entry and file_sha256(zpath) != entry["zip_sha256"]:
        errs.append("zip sha256 differs from the archive index")
    if entry is None:
        errs.append("archive not in the archive index")
    errs += _verify_zip(zpath)
    return {"ok": not errs, "zip": str(zpath), "errors": errs}


def restore(ident: str, archive_root, to) -> dict:
    v = verify_archive(ident, archive_root)
    if not v["ok"]:
        raise HKError("ARCHIVE_INVALID", "; ".join(v["errors"][:5]))
    dest = Path(to)
    if dest.exists() and (not dest.is_dir() or any(dest.iterdir())):
        raise HKError("TARGET_NOT_EMPTY", f"{dest} exists and is not an empty directory")
    dest.mkdir(parents=True, exist_ok=True)
    n = 0
    with zipfile.ZipFile(v["zip"]) as z:
        man = json.loads(z.read("manifest.json"))
        for e in man["files"]:
            if not _safe_member(e["path"]):
                raise HKError("UNSAFE_MEMBER", e["path"])
            out = (dest / e["path"]).resolve()
            if not str(out).startswith(str(dest.resolve())):
                raise HKError("UNSAFE_MEMBER", e["path"])
            out.parent.mkdir(parents=True, exist_ok=True)
            data = z.read("data/" + e["path"])
            if hashlib.sha256(data).hexdigest() != e["sha256"]:
                raise HKError("HASH_MISMATCH", e["path"])
            out.write_bytes(data)
            n += 1
    return {"restored_files": n, "to": str(dest), "links_not_restored": man.get("links_not_followed", [])}


# --------------------------------------------------------------------------- apply / recover

def _rmtree(path: Path) -> None:
    def onerr(func, p, _exc):
        os.chmod(p, stat.S_IWRITE)
        func(p)
    if is_link(path):
        raise HKError("LINK_REFUSED", f"{path} is a link; never deleted through")
    shutil.rmtree(path, onexc=onerr) if sys.version_info >= (3, 12) else shutil.rmtree(path, onerror=onerr)


def _journal_done(journal: Chain, plan_id: str) -> dict[str, dict]:
    done = {}
    for ev in journal.read():
        d = ev.get("data", {})
        if d.get("plan_id") == plan_id and ev.get("kind") in ("DONE", "RECOVERED_DONE"):
            done[d["item"]] = d
    return done


def _recheck_cache(ctx: Ctx, it: dict) -> dict | None:
    path = Path(it["path"])
    if not path.is_dir():
        return None
    parent = Path(it["parent_path"]) if it.get("parent_path") else None
    location = norm(path)
    if (parent is None or not parent.is_dir() or (parent / ".git").exists() or
            not location.startswith(norm(parent) + "/") or
            any(location == w or location.startswith(w + "/") for w in ctx.wt_paths) or
            any(location == t or location.startswith(t + "/") for t in ctx.task_paths)):
        return {**it, "cls": "PROTECTED", "reasons": ["cache location is now protected"]}
    return classify_cache(ctx, path, parent)


def _current(ctx: Ctx, it: dict) -> dict | None:
    """Re-inventory one plan item now (None = it no longer exists)."""
    ctx, wts = ctx.fresh()
    if it["kind"] == "worktree":
        w = wts.get(norm(it["path"]))
        return classify_worktree(ctx, w) if w else None
    if it["kind"] == "dir":
        return classify_dir(ctx, Path(it["path"])) if Path(it["path"]).is_dir() else None
    if it["kind"] == "cache":
        return _recheck_cache(ctx, it)
    if it["kind"] == "caches":
        subs = [_recheck_cache(ctx, {"path": q, "parent_path": it["path"]}) for q in it["paths"]]
        if any(x is None for x in subs):
            return {**it, "fingerprint": "", "reasons": ["a cache dir disappeared since the plan"]}
        if any(x["cls"] != "CACHE" for x in subs):
            return {**it, "cls": "PROTECTED", "reasons": ["a cache dir is now protected or holds evidence"]}
        return {**it, "links": any(x.get("links") for x in subs),
                "fingerprint": sha_text(canon_json(sorted((x["path"], x["fingerprint"]) for x in subs)))}
    if it["kind"] == "branch":
        rc, sha, _ = git(ctx.repo, "rev-parse", "--verify", "-q", it["path"])
        if rc or not sha:
            return None
        cur = {**it, "head": sha, "fingerprint": sha_text(canon_json([it["path"], sha]))}
        name = it["path"][len("refs/heads/"):]
        checked_out = {w["branch"] for w in wts.values() if w.get("branch")}
        symbolic = git(ctx.repo, "symbolic-ref", "-q", it["path"])[0] == 0 or it["path"] in _symref_targets(ctx)
        if (ctx.reach(sha) != "CANONICAL" or it["path"] in checked_out or name in ctx.task_branches
                or name.startswith(PRESERVED_BRANCH_PREFIXES)          # FB-1 N-04
                or it["path"] == ctx.canonical_full or _branch_reflog_only(ctx, name) != []   # FB3-01, FB3-05
                or symbolic or (sha == ctx.canonical and not ctx.canonical_full)):   # FB4-02, FB4-05
            cur["cls"] = "PROTECTED"
        return cur
    return None


def _cache_item_problem(it: dict, plan: dict) -> str | None:
    """A cache item may name only __pycache__/.pytest_cache directories below a top-level directory of one of the
    plan's roots (FB-2 FB2-04: a hand-edited item must not turn an arbitrary directory into an automatic delete)."""
    if it["kind"] == "branch":                          # FB-4 FB4-03: never tags, remotes or other refs
        ref = str(it.get("path") or "")
        ok = ref.startswith("refs/heads/") and subprocess.run(
            ["git", "check-ref-format", ref], capture_output=True).returncode == 0
        return None if ok else f"{ref} is not a local branch ref"
    if it["kind"] not in ("cache", "caches"):
        return None
    roots = {norm(r) for r in plan.get("roots", [])}
    parent = norm(it["parent_path"] if it["kind"] == "cache" else it["path"])
    if norm(Path(parent).parent) not in roots:
        return "cache item's parent is not a top-level directory of a plan root"
    members = [it["path"]] if it["kind"] == "cache" else list(it.get("paths") or [])
    if not members:
        return "cache item has no members"
    for m in members:
        if Path(m).name not in CACHE_DIRS or not norm(m).startswith(parent + "/"):
            return f"{m} is not a cache directory below {parent}"
    return None


def apply(plan_path, *, journal_dir, archive_root=None, approve=(), classes=(), ledger=None) -> dict:
    plan_bytes = Path(plan_path).read_bytes()
    plan = json.loads(plan_bytes)
    if plan.get("schema") != SCHEMA:
        raise HKError("BAD_PLAN", "not a housekeeping plan")
    bad = set(classes) - OPTIONAL_CLASSES
    if bad:
        raise HKError("BAD_CLASSES", f"--classes accepts only {sorted(OPTIONAL_CLASSES)}; got {sorted(bad)}")
    approve = set(approve)
    known = {it["id"] for it in plan["items"]}
    if approve - known:
        raise HKError("UNKNOWN_APPROVAL", f"not in the plan: {sorted(approve - known)}")
    jdir = Path(journal_dir)
    jdir.mkdir(parents=True, exist_ok=True)
    journal = Chain(jdir / "journal.jsonl")
    errs = journal.verify()
    if errs:
        raise HKError("CHAIN_BROKEN", f"journal: {errs[0]} (run recover / inspect before applying)")
    results = []
    with os_lock(jdir / "apply.lock", timeout=5):
        ctx = Ctx(Path(plan["repo"]), plan["canonical"]["ref"], plan.get("records", []),
                  ledger if ledger is not None else plan.get("ledger"), plan.get("min_age_hours", 24.0), False)
        if ctx.canonical != plan["canonical"]["sha"]:
            results.append({"note": f"canonical moved {plan['canonical']['sha'][:12]} -> {ctx.canonical[:12]}; "
                                    "items are re-classified against the new tip"})
        done = _journal_done(journal, plan["plan_id"])
        for it in plan["items"]:
            r = {"item": it["id"], "kind": it["kind"], "path": it["path"], "planned_class": it["cls"]}
            results.append(r)
            wanted = it["cls"] in AUTO_CLASSES or (it["cls"] in OPTIONAL_CLASSES and it["cls"] in classes) \
                or it["id"] in approve
            if it["id"] in done:
                r["outcome"] = "ALREADY_DONE"
                r.update({k: done[it["id"]][k] for k in ("archive", "restore") if k in done[it["id"]]})
                continue
            if not wanted:
                r["outcome"] = "NOT_SELECTED"
                continue
            if it["cls"] in NEVER:
                r["outcome"] = "REFUSED"
                r["why"] = f"class {it['cls']} is never removed"
                continue
            why = _cache_item_problem(it, plan)
            if why:
                r["outcome"] = "REFUSED"
                r["why"] = why
                continue
            try:
                cur = _current(ctx, it)
            except HKError as e:
                r.update(outcome="FAILED", error=f"recheck failed: {e}")
                continue
            if cur is None:
                r["outcome"] = "GONE_BEFORE_APPLY"
                continue
            if cur["fingerprint"] != it["fingerprint"] or cur["cls"] != it["cls"]:
                r["outcome"] = "SKIPPED_CHANGED"
                r["now"] = {"class": cur["cls"], "reasons": cur.get("reasons")}
                continue
            approved_only = it["cls"] in APPROVABLE
            # I-2: an approved worktree with nothing outside git (clean, no evidence, HEAD kept by a ref) is removed
            # without an archive; its restore command recreates it byte for byte. Anything else is archived first.
            clean_kept = (it["kind"] == "worktree" and cur.get("dirty") == 0 and not cur.get("evidence_count")
                          and cur.get("ignored_count") == 0 and cur.get("hidden_count") == 0
                          and cur.get("reach") in ("CANONICAL", "REMOTE", "LOCAL"))
            needs_archive = approved_only and it["kind"] in ("worktree", "dir") and not clean_kept
            if needs_archive and not archive_root:
                r["outcome"] = "REFUSED"
                r["why"] = "archive-then-remove needs --archive-root"
                continue
            action = {"worktree": "worktree-remove", "dir": "archive-then-remove", "cache": "rmtree",
                      "caches": "rmtree-caches", "branch": "delete-ref"}[it["kind"]]
            if it["cls"] == "PRUNABLE":
                action = "worktree-prune"
            elif it["kind"] == "worktree" and needs_archive:
                action = "archive-then-remove"
            journal.append("INTENT", {"plan_id": plan["plan_id"], "item": it["id"], "action": action,
                                      "path": it["path"], "paths": it.get("paths"), "fingerprint": it["fingerprint"],
                                      "restore": it.get("restore")})
            try:
                detail = {}
                if action in ("archive-then-remove",):
                    if cur.get("links"):
                        raise HKError("LINKS_PRESENT", f"{it['path']} contains links omitted by archive")
                    a = archive(it["path"], archive_root, label=it["id"].replace(":", "-"))
                    if a["links_not_followed"] or not verify_archive(a["archive_id"], archive_root)["ok"]:
                        raise HKError("ARCHIVE_INCOMPLETE", f"{it['path']} archive omits links or failed verification")
                    detail["archive"] = a["archive_id"]
                    journal.append("ARCHIVE_READY", {"plan_id": plan["plan_id"], "item": it["id"],
                                                     "action": action, "path": it["path"],
                                                     "archive": a["archive_id"], "restore": it.get("restore")})
                # The plan and archive are only valid for these exact source bytes. Check as late as possible.
                latest = _current(ctx, it)
                if latest is None or latest["cls"] != it["cls"] or latest["fingerprint"] != it["fingerprint"]:
                    raise HKError("SOURCE_CHANGED", f"{it['path']} changed before removal")
                if latest.get("links") and action in ("archive-then-remove", "worktree-remove", "rmtree",
                                                      "rmtree-caches"):
                    raise HKError("LINKS_PRESENT", f"{it['path']} contains links omitted by archive")
                if action == "archive-then-remove":
                    if it["kind"] == "worktree":
                        git(ctx.repo, "worktree", "remove", "--force", it["path"], check=True)
                    else:
                        _rmtree(Path(it["path"]))
                elif action == "worktree-remove":
                    git(ctx.repo, "worktree", "remove", it["path"], check=True)    # no --force: git refuses dirt
                elif action == "worktree-prune":
                    # per item: `git worktree prune` is global and would also drop registrations outside the plan
                    # (for example a running driver's missing .work tree)
                    git(ctx.repo, "worktree", "remove", it["path"], check=True)
                elif action == "rmtree":
                    _rmtree(Path(it["path"]))
                elif action == "rmtree-caches":
                    for q in it["paths"]:
                        _rmtree(Path(q))
                elif action == "delete-ref":
                    git(ctx.repo, "update-ref", "--no-deref", "-d", it["path"], it["head"], check=True)
                r.update(outcome="DONE", action=action, bytes=it.get("bytes", 0), restore=it.get("restore"), **detail)
                journal.append("DONE", {"plan_id": plan["plan_id"], "item": it["id"], "action": action,
                                        "restore": it.get("restore"), **detail})
            except (HKError, OSError) as e:
                r.update(outcome="FAILED", action=action, error=str(e))
                journal.append("FAILED", {"plan_id": plan["plan_id"], "item": it["id"], "action": action,
                                          "error": str(e)[:500]})
    rows = [r for r in results if "item" in r]
    receipt = {"schema": SCHEMA + "/receipt", "plan_id": plan["plan_id"], "plan": str(plan_path),
               "plan_sha256": hashlib.sha256(plan_bytes).hexdigest(), "applied_at": utcnow(),
               "canonical_now": ctx.canonical, "approved": sorted(approve), "classes": sorted(classes),
               "counts": {k: sum(1 for r in rows if r.get("outcome") == k) for k in sorted({r.get("outcome")
                                                                                          for r in rows})},
               "bytes_freed": sum(r.get("bytes", 0) for r in rows if r.get("outcome") == "DONE"),
               "results": results, "journal_head": (journal.read() or [{}])[-1].get("hash"),
               "journal_ok": not journal.verify()}
    stamp = datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    rp = jdir / f"receipt-{plan['plan_id']}-{stamp}.json"
    atomic_write_bytes(rp, (json.dumps(receipt, indent=1, sort_keys=True) + "\n").encode("utf-8"))
    md = [f"# Housekeeping receipt {plan['plan_id']}", "", f"- applied {receipt['applied_at']}, plan sha256 "
          f"`{receipt['plan_sha256']}`", f"- canonical now `{ctx.canonical}`", f"- counts {receipt['counts']}",
          f"- bytes freed {receipt['bytes_freed']:,}", f"- journal head `{receipt['journal_head']}`", "",
          "| item | path | outcome | restore |", "|---|---|---|---|"]
    md += [f"| {r['item']} | `{r['path']}` | {r.get('outcome')} | "
           f"{('`' + r['restore'] + '`') if r.get('outcome') == 'DONE' and r.get('restore') else ''}"
           f"{(' archive `' + r['archive'] + '`') if r.get('archive') else ''} |" for r in rows
           if r.get("outcome") not in ("NOT_SELECTED",)]
    atomic_write_bytes(rp.with_suffix(".md"), ("\n".join(md) + "\n").encode("utf-8"))
    receipt["receipt"] = str(rp)
    return receipt


def recover(journal_dir, repo=None) -> dict:
    jdir = Path(journal_dir)
    journal = Chain(jdir / "journal.jsonl")
    evs = journal.read()
    errs = journal.verify()
    if errs:
        return {"ok": False, "errors": errs, "note": "journal chain broken; nothing recovered automatically"}
    open_: dict[tuple, dict] = {}
    for ev in evs:
        d = ev.get("data", {})
        key = (d.get("plan_id"), d.get("item"))
        if ev["kind"] == "INTENT":
            open_[key] = d
        elif ev["kind"] == "ARCHIVE_READY" and key in open_:
            open_[key].update({k: d[k] for k in ("archive", "restore") if k in d})
        elif ev["kind"] in ("DONE", "FAILED", "RECOVERED_DONE", "RECOVERED_NOT_DONE"):
            open_.pop(key, None)
    out = []
    wt_paths = {norm(w["path"]) for w in _worktrees(Path(repo))} if repo else None
    for (plan_id, item), d in open_.items():
        path = d.get("path", "")
        if d["action"] == "delete-ref":
            gone = repo is not None and git(repo, "rev-parse", "--verify", "-q", path)[0] != 0
        elif d["action"] == "rmtree-caches" and d.get("paths"):
            gone = all(not Path(q).exists() for q in d["paths"])        # FB-1 N-06: the members, not the parent
        elif d["action"] in ("worktree-remove", "worktree-prune", "archive-then-remove") and \
                d.get("path") and wt_paths is not None and not str(item).startswith("dir:"):
            gone = not Path(path).exists() and norm(path) not in wt_paths
        else:
            gone = not Path(path).exists()
        kind = "RECOVERED_DONE" if gone else "RECOVERED_NOT_DONE"
        pointer = {k: d[k] for k in ("archive", "restore") if d.get(k)}
        journal.append(kind, {"plan_id": plan_id, "item": item, "action": d["action"], **pointer,
                              "observed": "target absent" if gone else "target still present"})
        out.append({"item": item, "plan_id": plan_id, "result": kind, **pointer})
    tmp = sorted(str(p) for p in jdir.glob("*.tmp"))
    return {"ok": True, "recovered": out, "leftover_tmp_files": tmp}


# --------------------------------------------------------------------------- CLI

def _out(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):   # a Windows pipe defaults to the ANSI code page
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="housekeeping", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("inventory"); p.add_argument("--repo", required=True)
    p.add_argument("--canonical-ref", default=CANONICAL_REF); p.add_argument("--root", action="append", default=[])
    p.add_argument("--records", action="append", default=[]); p.add_argument("--ledger")
    p.add_argument("--min-age-hours", type=float, default=24.0); p.add_argument("--no-sizes", action="store_true")
    p.add_argument("--out", required=True)
    p = sub.add_parser("apply"); p.add_argument("--plan", required=True); p.add_argument("--journal-dir", required=True)
    p.add_argument("--archive-root"); p.add_argument("--approve", action="append", default=[])
    p.add_argument("--classes", action="append", default=[]); p.add_argument("--ledger")
    p = sub.add_parser("archive"); p.add_argument("dir"); p.add_argument("--archive-root", required=True)
    p.add_argument("--label")
    p = sub.add_parser("verify-archive"); p.add_argument("archive"); p.add_argument("--archive-root", required=True)
    p = sub.add_parser("restore"); p.add_argument("archive"); p.add_argument("--archive-root", required=True)
    p.add_argument("--to", required=True)
    p = sub.add_parser("recover"); p.add_argument("--journal-dir", required=True); p.add_argument("--repo")
    p = sub.add_parser("verify-chain"); p.add_argument("file")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "inventory":
            plan = inventory(a.repo, canonical_ref=a.canonical_ref, roots=a.root, records=a.records,
                             ledger=a.ledger, min_age_hours=a.min_age_hours, sizes=not a.no_sizes)
            atomic_write_bytes(Path(a.out), (json.dumps(plan, indent=1, sort_keys=True) + "\n").encode("utf-8"))
            _out({"plan": a.out, "plan_id": plan["plan_id"], "summary": plan["summary"],
                  "elapsed_s": plan["elapsed_s"], "canonical": plan["canonical"]})
        elif a.cmd == "apply":
            r = apply(a.plan, journal_dir=a.journal_dir, archive_root=a.archive_root, approve=a.approve,
                      classes=a.classes, ledger=a.ledger)
            _out({k: r[k] for k in ("receipt", "counts", "bytes_freed", "journal_ok", "plan_id")})
            return 0 if r["journal_ok"] and not r["counts"].get("FAILED") else 1
        elif a.cmd == "archive":
            _out(archive(a.dir, a.archive_root, a.label))
        elif a.cmd == "verify-archive":
            v = verify_archive(a.archive, a.archive_root)
            _out(v)
            return 0 if v["ok"] else 1
        elif a.cmd == "restore":
            _out(restore(a.archive, a.archive_root, a.to))
        elif a.cmd == "recover":
            r = recover(a.journal_dir, a.repo)
            _out(r)
            return 0 if r["ok"] else 1
        elif a.cmd == "verify-chain":
            errs = Chain(Path(a.file)).verify()
            _out({"ok": not errs, "errors": errs})
            return 0 if not errs else 1
    except HKError as e:
        sys.stderr.write(f"ERROR {e}\n")
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
