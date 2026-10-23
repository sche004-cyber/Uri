"""Development memory (LIFECYCLE-V3.1-STORAGE): compact session-start brief and on-demand recall for URI
development knowledge, across Claude sessions, context resets and quota interruptions.

    python -m scripts.dev_workflow.devmemory refresh [--ledger F] [--decisions F ...] [--mm-home D]
                                                     [--receipts-root D ...] [--archive-index F ...]
                                                     [--repo D] [--canonical-ref REF]
    python -m scripts.dev_workflow.devmemory brief [--budget-tokens N]
    python -m scripts.dev_workflow.devmemory recall "<query>" [--task T] [--kind K] [--budget-tokens N]
                                                              [--include-stale]
    python -m scripts.dev_workflow.devmemory remember <task> <lesson|failed_approach|environment|procedure>
                                                      "<text>" --actor kind:id [--commit SHA] [--path P]
    python -m scripts.dev_workflow.devmemory stats | rebuild

The index (``URI_DEVMEMORY``, default ``~/.uri-dev/devmemory.sqlite3``) is DERIVED and rebuildable, never a source
of truth: it holds no fact that is not in an authoritative source, ``rebuild`` reproduces it from the sources, and
``remember`` writes to the task ledger (the source), never to the index. Sources (read-only): the Lifecycle V3.1
task ledger, ``decisions.md`` registers, a Milestone Manager home (when one is given; no authoritative home exists
until owner decision AP-14), lifecycle driver ``receipt.json`` files and the housekeeping archive index.

Every item carries provenance (source, ref, commit/path/blob where known) and a confidence class: VERIFIED
(hash-chained ledger row of a task whose chain verifies, or a receipt with ``evidence_ok_for_candidate``), RECORDED
(register row from a repository record or an owner prompt, Milestone Manager event), REPORTED (memory-only or
recommendation rows). Tiers are derived: hot (what a session must see first), warm (searchable), cold (superseded,
closed or archived; pointers only in the brief). Items whose recorded file changed on canonical or whose commit no
longer exists are stale: excluded from the brief and shown by recall only on request, with the reason.

All text passes the task ledger's ``redact``; rows with secret-looking paths are not indexed.

Boundary Guarantee: Development tooling only. Not part of the URI runtime. No model is trained or fine-tuned.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import math
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

from scripts.dev_workflow.task_ledger import Ledger, LedgerError, TERMINAL, is_secret_path, redact

SCHEMA = 1
KNOWLEDGE_KINDS = ("lesson", "failed_approach", "environment", "procedure")
HOT_CONTEXT_KINDS = {"next_action", "constraint", "issue", "permission", *KNOWLEDGE_KINDS}
CANONICAL_REF = "uri-repo/integration/git-sync-20261008"
GIT = ["git", "--no-optional-locks", "--no-replace-objects", "-c", "core.hooksPath=/dev/null", "-c", "core.fsmonitor=false"]
REPORTED_CLASSES = ("MEMORY-ONLY", "ANTIGRAVITY")
CLOSED_OPEN_MARKERS = re.compile(r"\*\*(DONE|DECIDED|CLASSIFIED)\b")
MAX_TEXT = 4000
FLAG_KEYS = ("_active", "_status", "_blocker", "_next", "_blocking", "_open")

DDL = """
CREATE TABLE IF NOT EXISTS meta(k TEXT PRIMARY KEY, v TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS sources(source TEXT PRIMARY KEY, fingerprint TEXT NOT NULL, refreshed_at TEXT NOT NULL,
  items INTEGER NOT NULL, redactions INTEGER NOT NULL DEFAULT 0);
CREATE TABLE IF NOT EXISTS items(id TEXT PRIMARY KEY, text_sha TEXT NOT NULL, source TEXT NOT NULL, ref TEXT NOT NULL,
  kind TEXT NOT NULL, tier TEXT NOT NULL, title TEXT NOT NULL, text TEXT NOT NULL, task_id TEXT, commit_sha TEXT,
  path TEXT, blob TEXT, confidence TEXT NOT NULL, stale INTEGER NOT NULL DEFAULT 0, stale_why TEXT,
  integrated INTEGER, also_refs TEXT NOT NULL DEFAULT '[]', at TEXT, flags TEXT NOT NULL DEFAULT '{}');
CREATE INDEX IF NOT EXISTS items_source ON items(source);
CREATE INDEX IF NOT EXISTS items_text ON items(text_sha);
CREATE VIRTUAL TABLE IF NOT EXISTS fts USING fts5(id UNINDEXED, title, text, tokenize='unicode61');
"""


class MemoryError_(Exception):
    pass


def utcnow() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def default_path() -> Path:
    env = os.environ.get("URI_DEVMEMORY")
    return Path(env) if env else Path.home() / ".uri-dev" / "devmemory.sqlite3"


def sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def file_sha(path: Path) -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def tokens(text: str) -> int:
    return math.ceil(len(text) / 4)


def git(repo, *args, inp: str | None = None) -> tuple[int, str]:
    try:
        p = subprocess.run([*GIT, "-C", str(repo), *args], capture_output=True, text=True, encoding="utf-8",
                           errors="replace", input=inp, timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return 1, str(e)
    return p.returncode, p.stdout.strip()


class Git:
    """Batched, cached git lookups for invalidation (one process per batch, not per item)."""

    def __init__(self, repo: str | None, canonical_ref: str):
        self.repo = repo
        self.canonical = None
        self._anc: dict[str, bool | None] = {}
        if repo:
            rc, out = git(repo, "rev-parse", "--verify", "-q", f"{canonical_ref}^{{commit}}")
            self.canonical = out if rc == 0 and out else None

    def blobs_at(self, rev: str, paths: list[str]) -> dict[str, str | None]:
        if not self.repo or not rev or not paths:
            return {p: None for p in paths}
        rc, out = git(self.repo, "cat-file", "--batch-check", inp="".join(f"{rev}:{p}\n" for p in paths))
        res = {}
        for p, line in zip(paths, out.splitlines() if rc == 0 else []):
            parts = line.split()
            res[p] = parts[0] if len(parts) == 3 and parts[1] == "blob" else None
        return {p: res.get(p) for p in paths}

    def worktree_blobs(self, wt: str, paths: list[str]) -> dict[str, str | None]:
        existing = [p for p in paths if (Path(wt) / p).is_file()]
        out = {p: None for p in paths}
        if existing:
            rc, text = git(wt, "hash-object", "--", *existing)
            if rc == 0:
                out.update(dict(zip(existing, text.splitlines())))
        return out

    def commits_exist(self, shas: list[str]) -> set[str]:
        if not self.repo or not shas:
            return set()
        rc, out = git(self.repo, "cat-file", "--batch-check", inp="".join(f"{s}\n" for s in shas))
        if rc:
            return set()
        return {s for s, line in zip(shas, out.splitlines()) if not line.endswith("missing")}

    def integrated(self, commit: str) -> bool | None:
        if not self.repo or not self.canonical or not commit:
            return None
        if commit not in self._anc:
            rc, _ = git(self.repo, "merge-base", "--is-ancestor", commit, self.canonical)
            self._anc[commit] = True if rc == 0 else (False if rc == 1 else None)
        return self._anc[commit]


# --------------------------------------------------------------------------- index

class Index:
    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else default_path()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(self.path), timeout=30, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(DDL)
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('schema', ?)", (str(SCHEMA),))
        self.db.execute("INSERT OR IGNORE INTO meta VALUES('derived', 'true')")

    def close(self):
        self.db.close()

    def meta(self, k: str, default=None):
        r = self.db.execute("SELECT v FROM meta WHERE k=?", (k,)).fetchone()
        return json.loads(r["v"]) if r else default

    def set_meta(self, k: str, v) -> None:
        self.db.execute("INSERT OR REPLACE INTO meta VALUES(?,?)", (k, json.dumps(v, sort_keys=True)))

    def replace_source(self, source: str, fp: str, items: list[dict], redactions: int) -> int:
        """Swap one source's items in a single transaction. Identical text already stored under another ref of the
        same source is stored once, with the extra refs in ``also_refs`` (deduplication)."""
        self.db.execute("BEGIN IMMEDIATE")
        try:
            old = [r["id"] for r in self.db.execute("SELECT id FROM items WHERE source=?", (source,))]
            for i in old:
                self.db.execute("DELETE FROM fts WHERE id=?", (i,))
            self.db.execute("DELETE FROM items WHERE source=?", (source,))
            seen: dict[str, str] = {}
            n = 0
            for it in items:
                tsha = sha(it["text"])
                dkey = f"{it['kind']}|{tsha}"
                if dkey in seen:
                    row = self.db.execute("SELECT also_refs FROM items WHERE id=?", (seen[dkey],)).fetchone()
                    refs = json.loads(row["also_refs"])
                    if it["ref"] not in refs:
                        refs.append(it["ref"])
                    self.db.execute("UPDATE items SET also_refs=? WHERE id=?", (json.dumps(refs), seen[dkey]))
                    continue
                iid = sha(f"{source}|{it['ref']}|{it['text']}")
                seen[dkey] = iid
                self.db.execute(
                    "INSERT OR REPLACE INTO items(id,text_sha,source,ref,kind,tier,title,text,task_id,commit_sha,path,"
                    "blob,confidence,stale,stale_why,integrated,also_refs,at,flags) "
                    "VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (iid, tsha, source, it["ref"], it["kind"], it["tier"], it["title"], it["text"], it.get("task_id"),
                     it.get("commit"), it.get("path"), it.get("blob"), it["confidence"], int(bool(it.get("stale"))),
                     it.get("stale_why"), None if it.get("integrated") is None else int(it["integrated"]), "[]",
                     it.get("at"), json.dumps(it.get("flags") or {}, sort_keys=True)))
                self.db.execute("INSERT INTO fts(id,title,text) VALUES(?,?,?)", (iid, it["title"], it["text"]))
                n += 1
            self.db.execute("INSERT OR REPLACE INTO sources VALUES(?,?,?,?,?)", (source, fp, utcnow(), n, redactions))
            self.db.execute("COMMIT")
        except BaseException:
            self.db.execute("ROLLBACK")
            raise
        return n

    def drop_missing_sources(self, keep: set[str]) -> list[str]:
        gone = [r["source"] for r in self.db.execute("SELECT source FROM sources") if r["source"] not in keep]
        for s in gone:
            self.replace_source(s, "", [], 0)
            self.db.execute("DELETE FROM sources WHERE source=?", (s,))
        return gone


def _clip(text: str, n: int = MAX_TEXT) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[:n] + " ...[clipped]"


def _clean(text: str) -> tuple[str, int]:
    return redact(_clip(text))


# --------------------------------------------------------------------------- collectors (read-only)

def collect_ledger(path: str | None, g: Git) -> tuple[str, list[dict], int]:
    lg = Ledger(path)
    try:
        tasks = lg.db.execute("SELECT * FROM tasks ORDER BY created_at").fetchall()
        heads, wt_heads = [], []
        for t in tasks:
            heads.append(f"{t['task_id']}={t['chain_head']}")
            if t["status"] not in TERMINAL and t["worktree"] and Path(t["worktree"]).is_dir():
                rc, h = git(t["worktree"], "rev-parse", "HEAD")
                wt_heads.append(f"{t['task_id']}@{h if rc == 0 else '?'}")
        fp = sha("|".join([*heads, *wt_heads, f"canon={g.canonical}"]))
        items, red = [], 0
        for t in tasks:
            tid = t["task_id"]
            chain_ok = not lg.verify(tid)
            conf = "VERIFIED" if chain_ok else "UNVERIFIED"
            active = t["status"] not in TERMINAL
            summary = lg._summary(t)
            text, n = _clean(f"{t['title']} | status {t['status']} | milestone {t['milestone_ref'] or '-'} | "
                             f"head {t['head_commit'] or '-'} | accepted {t['accepted_commit'] or '-'} | "
                             f"next: {summary.get('next_action') or '-'} | blocker: {t['blocker'] or '-'}")
            red += n
            items.append({"ref": tid, "kind": "task", "tier": "hot" if active else "cold", "title": f"{tid} {t['title']}",
                          "text": text, "task_id": tid, "confidence": conf, "at": t["updated_at"],
                          "_active": active, "_status": t["status"], "_blocker": t["blocker"],
                          "_next": summary.get("next_action")})
            rows = lg.db.execute("SELECT * FROM context WHERE task_id=? AND superseded=0 ORDER BY id", (tid,)).fetchall()
            for r in rows:
                if r["path"] and is_secret_path(r["path"]):
                    continue
                text, n = _clean(r["text"])
                red += n
                hot = active and r["kind"] in HOT_CONTEXT_KINDS or r["kind"] in KNOWLEDGE_KINDS
                items.append({"ref": f"{tid}/ctx/{r['sha'][:12]}", "kind": r["kind"],
                              "tier": "hot" if hot else ("warm" if active or r["kind"] in ("decision", "constraint")
                                                         else "cold"),
                              "title": f"{tid} {r['kind']}{(' ' + r['key']) if r['key'] else ''}", "text": text,
                              "task_id": tid, "commit": r["commit_sha"], "path": r["path"], "blob": r["blob"],
                              "confidence": conf, "at": r["created_at"], "_wt": t["worktree"], "_active": active})
            for f in lg.db.execute("SELECT * FROM findings WHERE task_id=? AND status='OPEN'", (tid,)):
                text, n = _clean(f"{f['finding_id']} [{f['severity']}{', blocking' if f['blocking'] else ''}"
                                 f"{', owner decision' if f['owner_decision'] else ''}] {f['title']}")
                red += n
                items.append({"ref": f"{tid}/finding/{f['finding_id']}", "kind": "finding",
                              "tier": "hot" if active and f["blocking"] else "warm", "title": f"{tid} finding",
                              "text": text, "task_id": tid, "commit": f["commit_sha"], "confidence": conf,
                              "_blocking": bool(f["blocking"]) and active})
    finally:
        lg.close()
    _invalidate(items, g)
    return fp, items, red


def _invalidate(items: list[dict], g: Git) -> None:
    """Mark items stale whose recorded file blob no longer matches (canonical for closed tasks, the task's worktree
    for open ones) or whose commit no longer exists; label commits that canonical contains."""
    canon_paths = sorted({i["path"] for i in items if i.get("path") and i.get("blob") and not i.get("_active")})
    canon = g.blobs_at(g.canonical, canon_paths) if g.canonical else {}
    by_wt: dict[str, list[str]] = {}
    for i in items:
        if i.get("path") and i.get("blob") and i.get("_active") and i.get("_wt") and Path(i["_wt"]).is_dir():
            by_wt.setdefault(i["_wt"], []).append(i["path"])
    wt_blobs = {wt: g.worktree_blobs(wt, sorted(set(ps))) for wt, ps in by_wt.items()}
    commits = sorted({i["commit"] for i in items if i.get("commit")})
    exists = g.commits_exist(commits) if g.repo else None
    for i in items:
        if i.get("path") and i.get("blob"):
            if i.get("_active") and i.get("_wt") in wt_blobs:
                cur, where = wt_blobs[i["_wt"]].get(i["path"]), "the task worktree"
            elif g.canonical:
                cur, where = canon.get(i["path"]), "canonical"
            else:
                cur, where = i["blob"], None
            if where and cur != i["blob"]:
                i["stale"], i["stale_why"] = True, f"{i['path']} changed in {where} since it was recorded"
        if i.get("commit") and exists is not None:
            if i["commit"] not in exists:
                i["stale"], i["stale_why"] = True, f"commit {i['commit'][:12]} does not exist in the repository"
            else:
                i["integrated"] = g.integrated(i["commit"])


def collect_decisions(path: Path) -> tuple[str, list[dict], int]:
    from scripts.dev_workflow.milestones.importers import parse_decisions
    fp = file_sha(path)
    decisions, opens = parse_decisions(path)
    items, red = [], 0
    ref_base = path.as_posix()
    for line_no, _raw, d in decisions:
        cls = d.get("evidence_class_raw", "")
        conf = "REPORTED" if any(c in cls for c in REPORTED_CLASSES) and "REPO-RECORD" not in cls else "RECORDED"
        appl = d.get("applicability", "")
        superseded = appl.upper().startswith("SUPERSEDED")
        text, n = _clean(f"{d.get('title', '')}: {d.get('decision', '')} | reasoning: {d.get('reasoning', '-')} | "
                         f"corrections: {d.get('corrections_text', '-')} | applicability: {appl} | source: "
                         f"{d.get('sources', '-')} | class: {cls}")
        red += n
        items.append({"ref": f"{d['id']}@{ref_base}:{line_no}", "kind": "decision",
                      "tier": "cold" if superseded else "warm", "title": f"{d['id']} {d.get('title', '')}",
                      "text": text, "confidence": conf, "stale": superseded,
                      "stale_why": "superseded decision" if superseded else None, "at": d.get("date")})
    for line_no, _raw, o in opens:
        closed = bool(CLOSED_OPEN_MARKERS.search(o["question"]))
        text, n = _clean(f"{o['question']} | context: {o['context']} | where: {o['where']}")
        red += n
        items.append({"ref": f"{o['alias']}@{ref_base}:{line_no}", "kind": "open_decision",
                      "tier": "cold" if closed else "hot", "title": f"{o['alias']} owner decision",
                      "text": text, "confidence": "RECORDED", "_open": not closed})
    return fp, items, red


def collect_mm(home: Path) -> tuple[str, list[dict], int]:
    from scripts.dev_workflow.milestones.service import Manager
    segs = sorted((home / "events").glob("*.jsonl"))
    fp = sha("|".join(f"{p.name}={file_sha(p)}" for p in segs))
    p = Manager(home).projection()
    items, red = [], 0

    def add(ref, kind, tier, title, body, open_=False):
        nonlocal red
        text, n = _clean(body)
        red += n
        items.append({"ref": f"mm:{ref}", "kind": kind, "tier": tier, "title": title, "text": text,
                      "confidence": "RECORDED", "_open": open_})

    for mid, m in p.get("milestones", {}).items():
        add(mid, "milestone", "warm", f"{mid} {m.get('title', '')}",
            f"{m.get('title', '')} | status {m.get('status')} | phase {m.get('phase')} | priority {m.get('priority')}")
    for aid, a in p.get("approvals", {}).items():
        open_ = a.get("status") == "REQUESTED"
        add(aid, "open_decision" if open_ else "approval", "hot" if open_ else "cold", f"{aid} owner approval",
            f"{a.get('question', '')} | subject {a.get('subject')} | status {a.get('status')}", open_)
    for bid, b in p.get("blockers", {}).items():
        open_ = b.get("status") == "OPEN"
        add(bid, "blocker", "hot" if open_ else "cold", f"{bid} blocker",
            f"{b.get('reason', '')} | needs {b.get('needs')} | subject {b.get('subject')} | status {b.get('status')}")
    for did, d in p.get("decisions", {}).items():
        add(did, "decision", "warm" if d.get("status") == "ACTIVE" else "cold", f"{did} {d.get('title', '')}",
            f"{d.get('title', '')}: {d.get('decision', '')} | status {d.get('status')}")
    for hid, h in p.get("handoffs", {}).items():
        add(hid, "handoff", "warm", f"{hid} handoff", f"{h.get('subject')}: {h.get('summary', '')} | next "
                                                      f"{h.get('next_action', '-')}")
    return fp, items, red


def collect_receipts(root: Path, g: Git) -> tuple[str, list[dict], int]:
    files = sorted(root.glob("*/receipt.json")) + sorted(root.glob("*/state/receipt.json"))
    fp = sha("|".join(f"{f.as_posix()}={file_sha(f)}" for f in files) + f"|canon={g.canonical}")
    items, red = [], 0
    for f in files:
        try:
            r = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ok = r.get("evidence_ok_for_candidate") is True
        integ = r.get("integration") or {}
        blocker = r.get("blocker") or {}
        text, n = _clean(f"lifecycle run {r.get('milestone')}: stage {r.get('stage')} | candidate {r.get('candidate')}"
                         f" | baseline {r.get('baseline')} | rounds {r.get('rounds')} | evidence_ok {ok} | "
                         f"integration {integ.get('status', '-')} | blocker {blocker.get('kind', '-')} "
                         f"{blocker.get('needs', '')} | receipt {f.as_posix()}")
        red += n
        items.append({"ref": f.as_posix(), "kind": "receipt", "tier": "warm", "title": f"receipt {r.get('milestone')}",
                      "text": text, "commit": r.get("candidate"), "confidence": "VERIFIED" if ok else "RECORDED",
                      "at": r.get("written_at")})
    _invalidate(items, g)
    return fp, items, red


def collect_archive_index(path: Path) -> tuple[str, list[dict], int]:
    fp = file_sha(path)
    items, red = [], 0
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            e = json.loads(line)
        except ValueError:
            continue
        if e.get("kind") != "ARCHIVED":
            continue
        d = e.get("data", {})
        text, n = _clean(f"archived {d.get('source')} -> {d.get('zip')} ({d.get('files')} files, "
                         f"{d.get('bytes')} bytes, zip sha256 {d.get('zip_sha256')}) label {d.get('label')}")
        red += n
        items.append({"ref": f"archive:{d.get('archive_id')}", "kind": "archive", "tier": "cold",
                      "title": f"archive {d.get('label')}", "text": text, "confidence": "VERIFIED",
                      "path": None, "at": e.get("ts")})
    return fp, items, red


# --------------------------------------------------------------------------- refresh / brief / recall

def _sources(cfg: dict) -> list[tuple[str, callable]]:
    g = Git(cfg.get("repo"), cfg.get("canonical_ref") or CANONICAL_REF)
    out = [("ledger", lambda: collect_ledger(cfg.get("ledger"), g))]
    for d in cfg.get("decisions", []):
        out.append((f"decisions:{Path(d).as_posix()}", lambda d=d: collect_decisions(Path(d))))
    if cfg.get("mm_home"):
        out.append((f"mm:{Path(cfg['mm_home']).as_posix()}", lambda: collect_mm(Path(cfg["mm_home"]))))
    for r in cfg.get("receipts_roots", []):
        out.append((f"receipts:{Path(r).as_posix()}", lambda r=r: collect_receipts(Path(r), g)))
    for a in cfg.get("archive_indexes", []):
        out.append((f"archive:{Path(a).as_posix()}", lambda a=a: collect_archive_index(Path(a))))
    return out, g


def refresh(ix: Index, cfg: dict | None = None, force: bool = False) -> dict:
    if cfg is not None:
        ix.set_meta("config", cfg)
    cfg = ix.meta("config", {}) or {}
    sources, g = _sources(cfg)
    report = {"canonical": g.canonical, "sources": {}}
    for name, fn in sources:
        try:
            fp, items, red = fn()
        except (OSError, ValueError, LedgerError, sqlite3.Error) as e:
            report["sources"][name] = f"ERROR {type(e).__name__}: {e}"
            continue
        # The source identity alone misses validity changes (an uncommitted edit to a recorded file); the collected
        # items, staleness included, are part of the fingerprint.
        fp = sha(fp + "|" + json.dumps([{k: v for k, v in i.items() if k != "_wt"} for i in items], sort_keys=True,
                                       default=str))
        row = ix.db.execute("SELECT fingerprint FROM sources WHERE source=?", (name,)).fetchone()
        if row and row["fingerprint"] == fp and not force:
            report["sources"][name] = "unchanged"
            continue
        rows = [{**{k: v for k, v in i.items() if not k.startswith("_")},
                 "flags": {k[1:]: v for k, v in i.items() if k in FLAG_KEYS}} for i in items]
        n = ix.replace_source(name, fp, rows, red)
        report["sources"][name] = f"rebuilt {n} items ({red} redactions)"
    gone = ix.drop_missing_sources({n for n, _ in sources})
    if gone:
        report["dropped_sources"] = gone
    ix.set_meta("canonical", {"ref": cfg.get("canonical_ref") or CANONICAL_REF, "sha": g.canonical,
                              "at": utcnow()})
    return report


def brief(ix: Index, budget_tokens: int = 1200) -> dict:
    """Compact session-start context: hot items only, in priority order, inside the token budget."""
    canon = ix.meta("canonical", {}) or {}
    hot = []
    for r in ix.db.execute("SELECT ref, kind, title, text, flags FROM items WHERE tier='hot' AND stale=0 "
                           "ORDER BY source, at, ref"):
        hot.append({"ref": r["ref"], "kind": r["kind"], "title": r["title"], "text": r["text"],
                    **{f"_{k}": v for k, v in json.loads(r["flags"]).items()}})
    budget = budget_tokens * 4
    lines = [f"# URI development brief ({utcnow()}; derived index, sources are authoritative)",
             f"canonical {canon.get('ref')} @ {(canon.get('sha') or 'UNKNOWN')[:12]}"]
    used = sum(len(x) + 1 for x in lines)
    omitted = 0
    sections = [
        ("Active tasks", [h for h in hot if h["kind"] == "task" and h.get("_active")],
         lambda h: f"- {h['ref']} [{h.get('_status')}] {h['title'].split(' ', 1)[-1]} | next: {h.get('_next') or '-'}"
                   + (f" | BLOCKED: {h['_blocker']}" if h.get("_blocker") else "")),
        ("Open blocking findings", [h for h in hot if h["kind"] == "finding" and h.get("_blocking")],
         lambda h: f"- {h['ref']}: {h['text']}"),
        ("Open owner decisions and blockers", [h for h in hot if h["kind"] in ("open_decision", "blocker")],
         lambda h: f"- {h['title'].split(' ', 1)[0]}: {h['text']}"),
        ("Lessons, failed approaches, environment limits",
         [h for h in hot if h["kind"] in KNOWLEDGE_KINDS],
         lambda h: f"- [{h['kind']}] {h['text']} ({h['ref']})"),
        ("Active constraints and next actions",
         [h for h in hot if h["kind"] in ("constraint", "issue", "permission", "next_action")],
         lambda h: f"- [{h['kind']}] {h['text']} ({h['ref']})"),
    ]
    for title, rows, fmt in sections:
        if not rows:
            continue
        head = f"## {title} ({len(rows)})"
        if used + len(head) + 1 > budget:
            omitted += len(rows)
            continue
        lines.append(head)
        used += len(head) + 1
        for h in rows:
            line = fmt(h)
            if len(line) > 400:
                line = line[:400] + " ...[recall for more]"
            if used + len(line) + 1 > budget:
                omitted += 1
                continue
            lines.append(line)
            used += len(line) + 1
    tail = (f"(~{tokens(chr(10).join(lines))} tokens of {budget_tokens}; {omitted} hot items omitted) More: "
            "`devmemory recall \"<topic>\"`, `task_ledger handoff <task>`, `task_ledger context-get <task> <sha>`.")
    lines.append(tail)
    text = "\n".join(lines)
    return {"text": text, "tokens": tokens(text), "budget_tokens": budget_tokens, "omitted": omitted,
            "canonical": canon}


def _fts_query(q: str) -> str:
    words = re.findall(r"\w+", q.lower())
    return " OR ".join(f'"{w}"' for w in words if len(w) > 1)


def recall(ix: Index, query: str, *, task: str | None = None, kind: str | None = None, budget_tokens: int = 800,
           include_stale: bool = False, limit: int = 50) -> dict:
    fq = _fts_query(query)
    if not fq:
        return {"query": query, "hits": [], "tokens": 0}
    sql = ("SELECT i.*, bm25(fts, 4.0, 1.0) AS score FROM fts JOIN items i ON i.id = fts.id WHERE fts MATCH ?"
           + ("" if include_stale else " AND i.stale = 0") + (" AND i.task_id = ?" if task else "")
           + (" AND i.kind = ?" if kind else "") + " ORDER BY score LIMIT ?")
    params = [fq] + ([task] if task else []) + ([kind] if kind else []) + [limit]
    hits, used, omitted = [], 0, 0
    budget = budget_tokens * 4
    for r in ix.db.execute(sql, params):
        text = r["text"] if len(r["text"]) <= 600 else r["text"][:600] + " ...[truncated]"
        h = {"ref": r["ref"], "source": r["source"], "kind": r["kind"], "tier": r["tier"], "title": r["title"],
             "text": text, "confidence": r["confidence"], "commit": r["commit_sha"], "path": r["path"],
             "integrated": None if r["integrated"] is None else bool(r["integrated"]),
             "also_refs": json.loads(r["also_refs"]), "score": round(r["score"], 3)}
        if r["stale"]:
            h["stale"] = r["stale_why"]
        size = len(json.dumps(h))
        if used + size > budget:
            omitted += 1
            continue
        used += size
        hits.append(h)
    return {"query": query, "hits": hits, "tokens": math.ceil(used / 4), "omitted": omitted}


def stats(ix: Index) -> dict:
    src = [dict(r) for r in ix.db.execute("SELECT * FROM sources ORDER BY source")]
    tiers = {r["tier"]: r["n"] for r in ix.db.execute("SELECT tier, COUNT(*) n FROM items GROUP BY tier")}
    conf = {r["confidence"]: r["n"] for r in ix.db.execute("SELECT confidence, COUNT(*) n FROM items GROUP BY 1")}
    stale = ix.db.execute("SELECT COUNT(*) n FROM items WHERE stale=1").fetchone()["n"]
    dup = ix.db.execute("SELECT COALESCE(SUM(json_array_length(also_refs)),0) n FROM items").fetchone()["n"]
    chars = ix.db.execute("SELECT COALESCE(SUM(LENGTH(text)),0) n FROM items").fetchone()["n"]
    return {"index": str(ix.path), "bytes": ix.path.stat().st_size, "items": sum(tiers.values()), "tiers": tiers,
            "confidence": conf, "stale": stale, "deduplicated_refs": dup, "indexed_tokens": math.ceil(chars / 4),
            "redactions": sum(s["redactions"] for s in src), "sources": src,
            "canonical": ix.meta("canonical", {})}


def remember(task: str, kind: str, text: str, actor: str, *, commit: str | None = None, path: str | None = None,
             ledger: str | None = None) -> dict:
    """Knowledge goes to the task ledger (the source of truth); the index picks it up on the next refresh."""
    if kind not in KNOWLEDGE_KINDS:
        raise MemoryError_(f"kind must be one of {KNOWLEDGE_KINDS}")
    lg = Ledger(ledger)
    try:
        return lg.add_context(task, actor, kind, text, path=path, commit=commit)
    finally:
        lg.close()


# --------------------------------------------------------------------------- CLI

def _out(obj) -> None:
    sys.stdout.write(json.dumps(obj, indent=1, sort_keys=True, default=str) + "\n")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="devmemory", description=__doc__.split("\n\n")[0])
    ap.add_argument("--index", help="index file (default $URI_DEVMEMORY or ~/.uri-dev/devmemory.sqlite3)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("refresh", "rebuild"):
        p = sub.add_parser(name)
        p.add_argument("--ledger"); p.add_argument("--decisions", action="append")
        p.add_argument("--mm-home"); p.add_argument("--receipts-root", action="append")
        p.add_argument("--archive-index", action="append"); p.add_argument("--repo")
        p.add_argument("--canonical-ref")
    p = sub.add_parser("brief"); p.add_argument("--budget-tokens", type=int, default=1200)
    p.add_argument("--no-refresh", action="store_true"); p.add_argument("--json", action="store_true")
    p = sub.add_parser("recall"); p.add_argument("query"); p.add_argument("--task"); p.add_argument("--kind")
    p.add_argument("--budget-tokens", type=int, default=800); p.add_argument("--include-stale", action="store_true")
    p.add_argument("--no-refresh", action="store_true")
    p = sub.add_parser("remember"); p.add_argument("task"); p.add_argument("kind", choices=KNOWLEDGE_KINDS)
    p.add_argument("text"); p.add_argument("--actor", required=True); p.add_argument("--commit")
    p.add_argument("--path"); p.add_argument("--ledger")
    sub.add_parser("stats")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "remember":
            row = remember(a.task, a.kind, a.text, a.actor, commit=a.commit, path=a.path, ledger=a.ledger)
            ix = Index(a.index)
            try:
                refresh(ix)
            finally:
                ix.close()
            _out(row)
            return 0
        if a.cmd == "rebuild":
            p = Path(a.index) if a.index else default_path()
            old = Index(p)
            cfg_old = old.meta("config", {}) or {}
            old.close()
            for suffix in ("", "-wal", "-shm"):
                q = Path(str(p) + suffix)
                if q.exists():
                    q.unlink()
        ix = Index(a.index)
        try:
            if a.cmd in ("refresh", "rebuild"):
                prev = ix.meta("config", {}) or (cfg_old if a.cmd == "rebuild" else {})
                cfg = {"ledger": a.ledger or prev.get("ledger"),
                       "decisions": a.decisions or prev.get("decisions", []),
                       "mm_home": a.mm_home or prev.get("mm_home"),
                       "receipts_roots": a.receipts_root or prev.get("receipts_roots", []),
                       "archive_indexes": a.archive_index or prev.get("archive_indexes", []),
                       "repo": a.repo or prev.get("repo"),
                       "canonical_ref": a.canonical_ref or prev.get("canonical_ref") or CANONICAL_REF}
                _out(refresh(ix, cfg, force=a.cmd == "rebuild"))
            elif a.cmd == "brief":
                if not a.no_refresh:
                    refresh(ix)
                b = brief(ix, a.budget_tokens)
                if a.json:
                    _out(b)
                else:
                    sys.stdout.write(b["text"] + "\n")
            elif a.cmd == "recall":
                if not a.no_refresh:
                    refresh(ix)
                _out(recall(ix, a.query, task=a.task, kind=a.kind, budget_tokens=a.budget_tokens,
                            include_stale=a.include_stale))
            elif a.cmd == "stats":
                _out(stats(ix))
        finally:
            ix.close()
    except (MemoryError_, LedgerError) as e:
        sys.stderr.write(f"ERROR: {e}\n")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
