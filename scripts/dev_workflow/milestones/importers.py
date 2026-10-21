"""Read-only importers: P0 `decisions.md`, P0 `developmental.md`, Lifecycle V3 state directories.

Nothing here writes to the source files. Every imported row keeps its source path, optional git commit, line number,
the SHA-256 of the whole source file and of the raw row. Re-importing an unchanged row is a no-op; a changed row is
recorded as a revision next to the original (never an overwrite). Rows containing secret-like text are skipped and
reported, never stored.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from scripts.dev_workflow.milestones import model as M
from scripts.dev_workflow.milestones.model import ValidationError
from scripts.dev_workflow.milestones.store import file_sha256, sha256_text

DECISION_COLUMNS = ("id", "date", "title", "decision", "reasoning", "alternatives_rejected", "corrections_text",
                    "scope", "approval_requirement", "related", "applicability", "sources", "evidence_class_raw")
SUPERSEDE_RX = re.compile(r"(?i)\bsuperseded\b(?P<mid>[^|.]{0,60}?)\bby\b(?P<tail>[^|]{0,160})")
PARTIAL_RX = re.compile(r"(?i)in part|partly|partially|for later phases|run-scoped|in practice")
SOURCE_STATUS = (("PARTLY SUPERSEDED", "PARTIALLY_SUPERSEDED"), ("SUPERSEDED", "SUPERSEDED"), ("UNCLEAR", "UNCLEAR"),
                 ("NOT OWNER DECISION", "NOT_OWNER_DECISION"), ("ACTIVE", "ACTIVE"))


def successor_ids(tail: str) -> list[str]:
    """DEC ids named after 'superseded ... by', including shorthand like DEC-040/066/074."""
    out = []
    for m in re.finditer(r"DEC-(\d{3,5})((?:/\d{3,5})*)", tail):
        out.append(f"DEC-{m.group(1)}")
        out.extend(f"DEC-{n}" for n in m.group(2).split("/") if n)
    return list(dict.fromkeys(out))


def source_status(applicability: str) -> str:
    up = (applicability or "").upper()
    for key, value in SOURCE_STATUS:
        if up.startswith(key):
            return value
    return "UNCLEAR"


def split_row(line: str) -> list[str] | None:
    """Split a Markdown table row on unescaped pipes; None for non-rows and separator rows."""
    s = line.strip()
    if not (s.startswith("|") and s.endswith("|")):
        return None
    cells, cur, i = [], [], 1
    while i < len(s) - 1:
        ch = s[i]
        if ch == "\\" and s[i + 1] == "|":
            cur.append("|")
            i += 2
            continue
        if ch == "|":
            cells.append("".join(cur).strip())
            cur = []
        else:
            cur.append(ch)
        i += 1
    cells.append("".join(cur).strip())
    if all(re.fullmatch(r":?-{3,}:?", c) for c in cells if c):
        return None
    return cells


def _source(path: Path, commit, line_no: int, raw: str, file_hash: str) -> dict:
    return {"path": str(path).replace("\\", "/"), "commit": commit, "line": line_no, "file_sha256": file_hash,
            "row_sha256": sha256_text(raw.strip())}


def _evidence_class(raw: str) -> str:
    for c in M.EVIDENCE_CLASSES:
        if c in (raw or ""):
            return c
    if "OWNER-PROMPT" in (raw or ""):
        return "OWNER-PROMPT"
    return "OTHER"


def _text(v, limit=M.MAX_TEXT):
    v = (v or "").strip()
    return v if len(v) <= limit else v[: limit - 20] + " [truncated]"


# --------------------------------------------------------------------------- decisions.md

def parse_decisions(path: Path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    decisions, opens = [], []
    for i, line in enumerate(lines, 1):
        cells = split_row(line)
        if not cells:
            continue
        if re.fullmatch(r"DEC-\d{3,5}", cells[0]) and len(cells) >= len(DECISION_COLUMNS):
            decisions.append((i, line, dict(zip(DECISION_COLUMNS, cells))))
        elif re.fullmatch(r"OPEN-\d+", cells[0]) and len(cells) >= 4:
            opens.append((i, line, {"alias": cells[0], "question": cells[1], "context": cells[2],
                                    "where": cells[3]}))
    return decisions, opens


def import_decisions(mgr, path, commit=None) -> dict:
    path = Path(path)
    file_hash = file_sha256(path)
    decisions, opens = parse_decisions(path)
    report = {"source": str(path), "file_sha256": file_hash, "commit": commit, "recorded": 0, "revised": 0,
              "unchanged": 0, "skipped_secret": [], "supersessions": 0, "open_questions": 0}

    def build(p):
        items = []
        for line_no, raw, row in decisions:
            src = _source(path, commit, line_no, raw, file_hash)
            if M.find_secret(raw):
                report["skipped_secret"].append(row["id"])
                continue
            existing = p["decisions"].get(row["id"])
            if existing is None:
                data = {"id": row["id"], "title": _text(row["title"], 300), "decision": _text(row["decision"]),
                        "date": _text(row["date"], 40), "evidence_class": _evidence_class(row["evidence_class_raw"]),
                        "source": src, "proposal": None, "reasoning": _text(row["reasoning"]),
                        "alternatives_rejected": _text(row["alternatives_rejected"]),
                        "related": [_text(row["related"], 1000)] if row["related"].strip("— ") else [],
                        "consequences": None, "approval_ref": None, "imported": True,
                        "source_status": source_status(row["applicability"]),
                        "imported_fields": {k: _text(row[k]) for k in ("corrections_text", "scope",
                                            "approval_requirement", "applicability", "sources",
                                            "evidence_class_raw")}}
                items.append(("DECISION_RECORDED", data, {row["id"]: 0}))
                report["recorded"] += 1
            else:
                known = {existing.get("source", {}).get("row_sha256")} | {
                    r["source"]["row_sha256"] for r in existing.get("source_revisions", [])}
                if src["row_sha256"] in known:
                    report["unchanged"] += 1
                    continue
                items.append(("DECISION_SOURCE_REVISED", {"id": row["id"], "source": src, "raw": _text(raw)},
                              {row["id"]: p["versions"].get(row["id"], 0)}))
                report["revised"] += 1
        # Supersession links stated in the "Later corrections / supersession" column.
        ids = set(p["decisions"]) | {r[2]["id"] for r in decisions}
        for _, _, row in decisions:
            text = row["corrections_text"] + " | " + row["applicability"]
            for mt in SUPERSEDE_RX.finditer(text):
                partial = bool(PARTIAL_RX.search(mt.group("mid") + " " + mt.group("tail")[:40]))
                for by in successor_ids(mt.group("tail")):
                    if by not in ids or by == row["id"]:
                        continue
                    old = p["decisions"].get(row["id"])
                    if old and any(s["by"] == by for s in old["superseded_by"]):
                        continue
                    if any(k == "DECISION_SUPERSEDED" and d["id"] == row["id"] and d["by"] == by
                           for k, d, _ in items):
                        continue
                    # link_only: the imported row's own status column stays authoritative for its status.
                    items.append(("DECISION_SUPERSEDED", {"id": row["id"], "by": by, "partial": partial,
                                                          "link_only": True,
                                                          "note": f"from source text: {mt.group(0)[:200]}"}, {}))
                    report["supersessions"] += 1
        for line_no, raw, row in opens:
            if M.find_secret(raw):
                report["skipped_secret"].append(row["alias"])
                continue
            if any(a.get("alias") == row["alias"] for a in p["approvals"].values()):
                continue
            n = p["counters"].get("AP", 0) + 1 + sum(1 for k, _, _ in items if k == "APPROVAL_REQUESTED")
            aid = f"AP-{n}"
            items.append(("APPROVAL_REQUESTED", {"id": aid, "subject": "PROJECT", "kind": "DECISION",
                                                 "question": _text(f"{row['question']} (context: {row['context']}; "
                                                                   f"where: {row['where']})"),
                                                 "alias": row["alias"],
                                                 "origin": _source(path, commit, line_no, raw, file_hash)}, {aid: 0}))
            report["open_questions"] += 1
        items.append(("IMPORT_RECORDED", {"importer": "decisions.md", "source": str(path).replace("\\", "/"),
                                          "commit": commit, "file_sha256": file_hash,
                                          "counts": {k: v for k, v in report.items() if isinstance(v, int)}}, {}))
        return items

    mgr._write(build)
    return report


# --------------------------------------------------------------------------- developmental.md

SECTION_TYPES = {"B": "capability", "C": "roadmap", "J": "defect", "K": "next_action"}


def parse_register(path: Path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    section, header, rows = None, None, []
    for i, line in enumerate(lines, 1):
        h = re.match(r"^## ([A-Z])\.", line)
        if h:
            section, header = h.group(1), None
            continue
        if section not in SECTION_TYPES:
            continue
        cells = split_row(line)
        if cells is None:
            continue
        if header is None:
            header = [c.lower() for c in cells]
            continue
        rows.append((i, line, section, dict(zip(header, cells))))
    return rows


def _color(text: str):
    m = re.match(r"\s*\**\s*(GREEN|BLUE|YELLOW|RED|WHITE|UNKNOWN)\b", text or "")
    return m.group(1) if m else None


def import_register(mgr, path, commit=None) -> dict:
    path = Path(path)
    file_hash = file_sha256(path)
    rows = parse_register(path)
    report = {"source": str(path), "file_sha256": file_hash, "commit": commit, "recorded": 0, "revised": 0,
              "unchanged": 0, "skipped_secret": [], "skipped_bad_id": []}

    def build(p):
        items, used = [], set()
        for line_no, raw, section, row in rows:
            rtype = SECTION_TYPES[section]
            first = next(iter(row.values()), "")
            rid = "REG-" + section + "-" + re.sub(r"[^A-Z0-9._-]+", "_", first.upper()).strip("_")[:50]
            n, base_id = 2, rid
            while rid in used:  # duplicate first-column value in the source: deterministic suffix by order
                rid, n = f"{base_id}-{n}", n + 1
            used.add(rid)
            if not M.ID_RE.match(rid):
                report["skipped_bad_id"].append(rid)
                continue
            if M.find_secret(raw):
                report["skipped_secret"].append(rid)
                continue
            src = _source(path, commit, line_no, raw, file_hash)
            status_text = row.get("status") or row.get("state 2026-10-21") or ""
            fields = {k: _text(v, 1500) for k, v in row.items()}
            existing = p["records"].get(rid)
            if existing is None:
                items.append(("RECORD_IMPORTED", {"id": rid, "record_type": rtype, "fields": fields,
                                                  "color": _color(status_text), "source": src}, {rid: 0}))
                report["recorded"] += 1
            elif existing["source"]["row_sha256"] == src["row_sha256"]:
                report["unchanged"] += 1
            else:
                items.append(("RECORD_SOURCE_REVISED", {"id": rid, "record_type": rtype, "fields": fields,
                                                        "color": _color(status_text), "source": src},
                              {rid: p["versions"].get(rid, 0)}))
                report["revised"] += 1
        items.append(("IMPORT_RECORDED", {"importer": "developmental.md", "source": str(path).replace("\\", "/"),
                                          "commit": commit, "file_sha256": file_hash,
                                          "counts": {k: v for k, v in report.items() if isinstance(v, int)}}, {}))
        return items

    mgr._write(build)
    return report


# --------------------------------------------------------------------------- Lifecycle V3 state directories

def _lifecycle_hash(ev: dict) -> str:
    # Exactly as lifecycle.py State.event / verify(): sha256 over json.dumps(..., sort_keys=True) with defaults.
    return hashlib.sha256(json.dumps({k: ev[k] for k in ("seq", "ts", "kind", "data", "prev")},
                                     sort_keys=True).encode()).hexdigest()


def read_lifecycle_snapshot(state_dir) -> dict:
    """Read-only snapshot of a Lifecycle V3 run: chain check, stage, blocker, candidate, latest review, integration."""
    d = Path(state_dir)
    state_path, events_path = d / "state.json", d / "events.jsonl"
    if not state_path.is_file():
        raise ValidationError("NOT_FOUND", f"{state_path} does not exist")
    state = json.loads(state_path.read_text(encoding="utf-8"))
    errors, prev, events = [], "0" * 64, []
    raw_lines = events_path.read_text(encoding="utf-8").splitlines() if events_path.is_file() else []
    for n, line in enumerate(raw_lines, 1):
        try:
            ev = json.loads(line)
        except ValueError:
            errors.append(f"line {n} is not JSON")
            continue
        if ev.get("prev") != prev or ev.get("hash") != _lifecycle_hash(ev):
            errors.append(f"event {ev.get('seq')} chain broken")
        prev = ev.get("hash")
        events.append(ev)
    hist = state.get("history") or []
    if len(hist) != len(events) or any(a.get("hash") != b.get("hash") for a, b in zip(hist, events)):
        errors.append("state history and event log differ")
    review = None
    for ev in events:
        if ev.get("kind") == "REVIEW_RECORDED":
            review = {k: ev["data"].get(k) for k in ("round", "candidate", "verdict", "independent", "outcome",
                                                      "provider", "status")}
    blocker = state.get("blocker") if state.get("stage") == "BLOCKED" else None
    integ = state.get("integration") or None
    receipt = d / "receipt.json"
    return {"milestone": state.get("milestone"), "stage": state.get("stage"),
            "blocker": {k: blocker.get(k) for k in ("kind", "reason", "needs")} if blocker else None,
            "candidate": state.get("candidate"), "baseline": state.get("baseline"),
            "config_sha256": state.get("config_sha256"), "events": len(events), "head": prev if events else None,
            "chain_ok": not errors, "errors": errors[:5], "latest_review": review,
            "integration": {k: integ.get(k) for k in ("status", "target_ref", "target_tip_after", "candidate")}
            if isinstance(integ, dict) else None,
            "receipt_sha256": file_sha256(receipt) if receipt.is_file() else None,
            "state_sha256": file_sha256(state_path)}
