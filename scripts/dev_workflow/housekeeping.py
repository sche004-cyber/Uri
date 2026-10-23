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
import stat
import subprocess
import sys
import time
import zipfile
from pathlib import Path

from scripts.dev_workflow.milestones.store import atomic_write_bytes, file_sha256, os_lock

SCHEMA = "uri-housekeeping/1"
GENESIS = "0" * 64
GIT = ["git", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]
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


def git(repo, *args, check=False, timeout=300) -> tuple[int, str, str]:
    try:
        p = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)
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


def _record_paths(records: list[str]) -> set[str]:
    """Absolute paths cited by authoritative records (decisions.md, developmental.md, audit/MM docs, receipts)."""
    found: set[str] = set()
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
            found.add(norm(m.group(1).rstrip(".:")))
    return found


def _ledger_refs(ledger: str | None) -> tuple[set[str], set[str]]:
    """(worktree paths of non-terminal ledger tasks, branches of non-terminal tasks); v3 state dirs are added to the
    first set (referenced evidence)."""
    try:
        from scripts.dev_workflow.task_ledger import Ledger, TERMINAL
    except ImportError:
        return set(), set()
    p = Path(ledger) if ledger else None
    if p is not None and not p.is_file():
        return set(), set()
    lg = Ledger(p)
    try:
        paths, branches = set(), set()
        for t in lg.db.execute("SELECT * FROM tasks"):
            if t["status"] in TERMINAL:
                continue
            if t["worktree"]:
                paths.add(norm(t["worktree"]))
            if t["branch"]:
                branches.add(t["branch"])
        for r in lg.db.execute("SELECT state_dir FROM v3_links"):
            paths.add(norm(r["state_dir"]))
        return paths, branches
    finally:
        lg.close()


class Ctx:
    def __init__(self, repo: Path, canonical_ref: str, records: list[str], ledger: str | None,
                 min_age_hours: float, sizes: bool):
        self.repo = Path(repo)
        rc, sha, _ = git(repo, "rev-parse", "--verify", "-q", f"{canonical_ref}^{{commit}}")
        if rc or not sha:
            raise HKError("NO_CANONICAL", f"{canonical_ref} does not resolve in {repo}; refusing to classify")
        self.canonical_ref, self.canonical = canonical_ref, sha
        self.cited = _record_paths(records)
        self.task_paths, self.task_branches = _ledger_refs(ledger)
        self.min_age_s = min_age_hours * 3600
        self.sizes = sizes
        self.cwd = norm(os.getcwd())
        self.wt_paths: set[str] = set()
        self._reach: dict[str, str] = {}

    def cited_under(self, path: str) -> list[str]:
        p = norm(path)
        return sorted(c for c in self.cited if c == p or c.startswith(p + "/"))[:5]

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


def _markers(path: Path) -> list[str]:
    hits = []
    for d, _dirs, files in walk(path, skip=SKIP_WALK, max_depth=MARKER_WALK_DEPTH):
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


def _idle_s(path: Path) -> float:
    stamps = []
    gitf = path / ".git"
    try:
        if gitf.is_file():
            gd = Path(gitf.read_text(encoding="utf-8").split("gitdir:", 1)[1].strip())
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
        keep = w["locked"] or active_run
        item.update(cls="PROTECTED" if keep else "PRUNABLE", action="none" if keep else "worktree-prune")
        item["reasons"].append("directory missing" + (" but locked" if w["locked"] else "")
                               + (f" inside lifecycle run {run[0].as_posix()} (stage {run[1]})" if active_run else ""))
        item["fingerprint"] = sha_text(canon_json([w["head"], w["branch"], "missing", w["locked"], active_run]))
        return item
    rc, status, _ = git(path, "status", "--porcelain", "--untracked-files=normal", "--ignore-submodules")
    dirty = len(status.splitlines()) if rc == 0 else -1
    um = _untracked_markers(path, _markers(path))
    reach = ctx.reach(w["head"]) if w["head"] else "NONE"
    cited = ctx.cited_under(str(path))
    idle = _idle_s(path)
    item.update(dirty=dirty, evidence=um[:20], evidence_count=len(um), reach=reach, cited=cited,
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
    if protect:
        item.update(cls="PROTECTED", action="none")
        item["reasons"] += protect
    elif um:
        item.update(cls="EVIDENCE", action="archive-then-remove (needs --approve)")
        item["reasons"].append(f"{len(um)} untracked evidence files" + (f", {dirty} uncommitted/untracked entries"
                                                                        if dirty > 0 else ""))
    elif dirty > 0:
        item.update(cls="DIRTY", action="archive-then-remove (needs --approve)")
        item["reasons"].append(f"{dirty} uncommitted/untracked entries")
    elif cited:
        item.update(cls="REFERENCED", action="archive-then-remove (needs --approve)")
        item["reasons"].append("cited by an authoritative record")
    elif reach == "LOCAL":
        item.update(cls="LOCAL_ONLY", action="remove (needs --approve)")
        item["reasons"].append("HEAD kept only by a local branch or tag")
    elif idle < ctx.min_age_s:
        item.update(cls="AMBIGUOUS", action="none")
        item["reasons"].append(f"used {idle / 3600:.1f} h ago (< {ctx.min_age_s / 3600:.0f} h)")
    else:
        item.update(cls="DISPOSABLE", action="worktree-remove")
        item["reasons"].append(f"clean, HEAD on {reach.lower()}, unreferenced, idle {idle / 3600:.0f} h")
    item["restore"] = (f"git -C {ctx.repo.as_posix()} worktree add "
                       + (f"{path.as_posix()} {branch_short}" if branch_short else
                          f"--detach {path.as_posix()} {w['head']}"))
    item["fingerprint"] = sha_text(canon_json([w["head"], w["branch"], w["locked"], dirty, um, reach]))
    return item


def classify_dir(ctx: Ctx, path: Path) -> dict:
    um = _markers(path)
    cited = ctx.cited_under(str(path))
    item = {"id": "dir:" + sha_text(norm(path))[:12], "kind": "dir", "path": str(path), "evidence": um[:20],
            "evidence_count": len(um), "cited": cited, "reasons": []}
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
    entries = sorted(e.name for e in path.iterdir()) if path.is_dir() else []
    item["fingerprint"] = sha_text(canon_json([um, cited, entries]))
    return item


def _caches(root: Path) -> list[Path]:
    out = []
    for d, dirs, _files in walk(root, skip=SKIP_WALK - CACHE_DIRS):
        for x in list(dirs):
            if x in CACHE_DIRS:
                out.append(d / x)
                dirs.remove(x)
    return out


def classify_branches(ctx: Ctx, checked_out: set[str]) -> list[dict]:
    _, out, _ = git(ctx.repo, "for-each-ref", "refs/heads", "--format=%(refname) %(objectname)", check=True)
    items = []
    for line in out.splitlines():
        ref, _, sha = line.partition(" ")
        name = ref[len("refs/heads/"):]
        if ref in checked_out or name.startswith(PRESERVED_BRANCH_PREFIXES) or name in ctx.task_branches:
            continue
        if ctx.reach(sha) != "CANONICAL":
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
            for c in _caches(child):
                items.append({"id": "cache:" + sha_text(norm(c))[:12], "kind": "cache", "path": str(c),
                              "cls": "CACHE", "action": "delete (regenerable)", "reasons": ["regenerable cache"],
                              "parent": it["id"], "fingerprint": sha_text(canon_json([norm(c)]))})
    items += classify_branches(ctx, {w["branch"] for w in wts if w["branch"]})
    if sizes:
        for it in items:
            if it["kind"] in ("worktree", "dir", "cache") and Path(it["path"]).is_dir():
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


def _journal_done(journal: Chain, plan_id: str) -> dict[str, str]:
    done = {}
    for ev in journal.read():
        d = ev.get("data", {})
        if d.get("plan_id") == plan_id and ev.get("kind") in ("DONE", "RECOVERED_DONE"):
            done[d["item"]] = ev["kind"]
    return done


def _current(ctx: Ctx, it: dict, wts: dict[str, dict]) -> dict | None:
    """Re-inventory one plan item now (None = it no longer exists)."""
    if it["kind"] == "worktree":
        w = wts.get(norm(it["path"]))
        return classify_worktree(ctx, w) if w else None
    if it["kind"] == "dir":
        return classify_dir(ctx, Path(it["path"])) if Path(it["path"]).is_dir() else None
    if it["kind"] == "cache":
        return {**it} if Path(it["path"]).is_dir() else None
    if it["kind"] == "branch":
        rc, sha, _ = git(ctx.repo, "rev-parse", "--verify", "-q", it["path"])
        if rc or not sha:
            return None
        cur = {**it, "head": sha, "fingerprint": sha_text(canon_json([it["path"], sha]))}
        if ctx.reach(sha) != "CANONICAL":
            cur["cls"] = "PROTECTED"
        return cur
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
        wts = {norm(w["path"]): w for w in _worktrees(ctx.repo)}
        ctx.wt_paths = set(wts)
        done = _journal_done(journal, plan["plan_id"])
        for it in plan["items"]:
            r = {"item": it["id"], "kind": it["kind"], "path": it["path"], "planned_class": it["cls"]}
            results.append(r)
            wanted = it["cls"] in AUTO_CLASSES or (it["cls"] in OPTIONAL_CLASSES and it["cls"] in classes) \
                or it["id"] in approve
            if it["id"] in done:
                r["outcome"] = "ALREADY_DONE"
                continue
            if not wanted:
                r["outcome"] = "NOT_SELECTED"
                continue
            if it["cls"] in NEVER:
                r["outcome"] = "REFUSED"
                r["why"] = f"class {it['cls']} is never removed"
                continue
            cur = _current(ctx, it, wts)
            if cur is None:
                r["outcome"] = "GONE_BEFORE_APPLY"
                continue
            if cur["fingerprint"] != it["fingerprint"] or cur["cls"] != it["cls"]:
                r["outcome"] = "SKIPPED_CHANGED"
                r["now"] = {"class": cur["cls"], "reasons": cur.get("reasons")}
                continue
            approved_only = it["cls"] in APPROVABLE
            if approved_only and not archive_root and it["kind"] in ("worktree", "dir") and \
                    it["cls"] != "LOCAL_ONLY":
                r["outcome"] = "REFUSED"
                r["why"] = "archive-then-remove needs --archive-root"
                continue
            action = {"worktree": "worktree-remove", "dir": "archive-then-remove", "cache": "rmtree",
                      "branch": "delete-ref"}[it["kind"]]
            if it["cls"] == "PRUNABLE":
                action = "worktree-prune"
            elif it["kind"] == "worktree" and approved_only and it["cls"] != "LOCAL_ONLY":
                action = "archive-then-remove"
            journal.append("INTENT", {"plan_id": plan["plan_id"], "item": it["id"], "action": action,
                                      "path": it["path"], "fingerprint": it["fingerprint"]})
            try:
                detail = {}
                if action in ("archive-then-remove",):
                    a = archive(it["path"], archive_root, label=it["id"].replace(":", "-"))
                    detail["archive"] = a["archive_id"]
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
                elif action == "delete-ref":
                    git(ctx.repo, "update-ref", "-d", it["path"], it["head"], check=True)
                r.update(outcome="DONE", action=action, bytes=it.get("bytes", 0), restore=it.get("restore"), **detail)
                journal.append("DONE", {"plan_id": plan["plan_id"], "item": it["id"], "action": action, **detail})
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
        elif ev["kind"] in ("DONE", "FAILED", "RECOVERED_DONE", "RECOVERED_NOT_DONE"):
            open_.pop(key, None)
    out = []
    wt_paths = {norm(w["path"]) for w in _worktrees(Path(repo))} if repo else None
    for (plan_id, item), d in open_.items():
        path = d.get("path", "")
        if d["action"] == "delete-ref":
            gone = repo is not None and git(repo, "rev-parse", "--verify", "-q", path)[0] != 0
        elif d["action"] in ("worktree-remove", "worktree-prune", "archive-then-remove") and \
                d.get("path") and wt_paths is not None and not str(item).startswith("dir:"):
            gone = not Path(path).exists() and norm(path) not in wt_paths
        else:
            gone = not Path(path).exists()
        kind = "RECOVERED_DONE" if gone else "RECOVERED_NOT_DONE"
        journal.append(kind, {"plan_id": plan_id, "item": item, "action": d["action"],
                              "observed": "target absent" if gone else "target still present"})
        out.append({"item": item, "plan_id": plan_id, "result": kind})
    tmp = sorted(str(p) for p in jdir.glob("*.tmp"))
    return {"ok": True, "recovered": out, "leftover_tmp_files": tmp}


# --------------------------------------------------------------------------- CLI

def _out(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def main(argv=None) -> int:
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
