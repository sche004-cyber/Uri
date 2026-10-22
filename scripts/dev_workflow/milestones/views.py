"""Read-only views: derived status indicators, status board, ready list, resume brief, JSON export.

Indicators are always derived from the projection (and, when available, Lifecycle V3 snapshots and Lifecycle V3.1
task summaries); they are never stored. Each indicator carries a text word so it does not depend on colour or emoji.
"""
from __future__ import annotations

import datetime

from scripts.dev_workflow.milestones import model as M

STATUS_SCHEMA = "uri-mm-status/1"
EMOJI = {"GREEN": "\U0001F7E2", "BLUE": "\U0001F535", "YELLOW": "\U0001F7E1", "RED": "\U0001F534",
         "WHITE": "⚪"}
WORD = {"GREEN": "COMPLETED", "BLUE": "IN PROGRESS", "YELLOW": "OWNER ACTION", "RED": "BLOCKED",
        "WHITE": "NOT ACTIVE"}
A2UI_TONE = {"GREEN": "success", "BLUE": "accent", "YELLOW": "warning", "RED": "danger", "WHITE": "neutral"}
DONE_STATES = ("ACCEPTED", "INTEGRATED", "DONE")
MIN_RESUME_CHARS = 200
OWNER_BLOCKS = ("OWNER_AUTHORIZATION", "OWNER_DECISION")


def open_approvals(p, subject):
    return [a for a in p["approvals"].values() if a["subject"] == subject and a["status"] == "REQUESTED"]


def open_blockers(p, subject):
    return [b for b in p["blockers"].values() if b["subject"] == subject and b["status"] == "OPEN"]


def _conflict_index(p):
    """Open conflicts indexed once per projection by entity/subject (review R4-06: status was milestones x
    conflicts)."""
    key = id(p["conflicts"]), len(p["conflicts"])
    cached = p.get("_cidx")
    if cached and cached[0] == key:
        return cached[1]
    idx = {None: [], "__ledger__": [], "__ids__": {}}
    groups = {}
    for c in p["conflicts"]:
        if c["resolved"]:
            continue
        idx[None].append(c)
        groups.setdefault((c["entity"], c["event"]["hash"]), []).append(c)
        if c.get("type") in ("ANCHOR_LOSS", "ABANDONED_BATCH_COMPLETED"):
            idx["__ledger__"].append(c)
        for k in {c["entity"], c.get("subject"), *(c.get("subjects") or [])} - {None}:
            idx.setdefault(k, []).append(c)
    for members in groups.values():  # one display id per (entity, event), computed once (review R18-02)
        shown = M.display_id(members, members[0])
        for c in members:
            idx["__ids__"][id(c)] = shown
    p["_cidx"] = (key, idx)
    return idx


def did(p, c) -> str:
    """Display id of conflict ``c`` (see model.display_id)."""
    return _conflict_index(p)["__ids__"].get(id(c)) or M.display_id(open_conflicts(p), c)


def open_conflicts(p, entity=None):
    """Unresolved conflicts; with ``entity``, those on that entity or whose subject is that milestone."""
    return list(_conflict_index(p).get(entity, []))


def negative_reviews_on_candidate(p, m):
    cand = m.get("candidate_commit")
    return [r for r in p["reviews"].values() if r["subject"] == m["id"] and r["commit"] == cand
            and r["result_class"] == "COMPLETED_WITH_RESULT"
            and (r["verdict"] not in ("ACCEPT", "ACCEPT WITH FINDINGS") or r["blocking_open"])]





def unmet_dependencies(p, m):
    return [d for d in m["depends_on"] if (p["milestones"].get(d) or {}).get("status") not in DONE_STATES
            or not M.independent_accept_reviews(p, p["milestones"][d])
            or negative_reviews_on_candidate(p, p["milestones"][d])]


def indicator(p, m, tasks: dict | None = None) -> dict:
    """Derived indicator. Priority: RED > YELLOW > GREEN > WHITE > BLUE (architecture §4)."""
    ident = m["id"]
    reds, yellows = [], []
    for b in open_blockers(p, ident):
        reds.append(f"blocker {b['id']} ({b['kind']}): {b['reason']} | needs: {b['needs']}")
    if p.get("integrity_errors"):
        reds.append(f"LEDGER INTEGRITY: {p['integrity_errors'][0]} (run `verify`; statuses may be untrustworthy)")
    for c in _conflict_index(p)["__ledger__"]:
        if c.get("type") == "ANCHOR_LOSS":
            detail = (c.get("lost") or (c.get("anchor_problems") or [None])[0]
                      or ("own segment adopted without an anchor" if c.get("kind") == "ANCHORS_ADOPTED" else None)
                      or "unknown history")
            reds.append(f"ledger integrity loss recorded by {c.get('kind')}: {detail}; review every open conflict "
                        "with `conflicts --entity LEDGER`, then resolve by the ids it shows")
        else:
            reds.append(f"batch {c.get('batch')} was declared abandoned but is complete and applied; review with "
                        "`conflicts --entity LEDGER`")
    # Status shows one issue line per milestone, so it never prints a ready-to-run id: an id covers every conflict
    # its event raised on that entity, and only `conflicts` displays all of them (review R19-01).
    own = open_conflicts(p, ident)
    if own:
        kinds = sorted({f"{c.get('type', 'VERSION')} on {c['entity']}" for c in own})
        reds.append(f"{len(own)} open conflict(s): {', '.join(kinds)}; review them with `conflicts --entity "
                    f"{ident}` (also lists conflicts whose subject is {ident}), then resolve by the ids shown there")
    if m["status"] in DONE_STATES and m.get("bound_commit") and m.get("candidate_commit") != m["bound_commit"]:
        # stays RED after its conflict is resolved: the positive status is not about this commit (review R22-02)
        reds.append(f"candidate {m.get('candidate_commit')} is not the commit {m['bound_commit']} that "
                    f"{m['status']} rests on; set the candidate back to {m['bound_commit']}, or set the status back "
                    "to IN_PROGRESS and have the new candidate reviewed")
    if m["status"] in DONE_STATES:
        if not M.independent_accept_reviews(p, m):
            reds.append(f"{m['status']} has no independent qualifying ACCEPT review on candidate "
                        f"{m.get('candidate_commit')}; record an independent review")
        neg = negative_reviews_on_candidate(p, m)
        if neg:
            reds.append(f"review {neg[0]['id']} on the candidate is {neg[0]['verdict']} although status is "
                        f"{m['status']}")
    for lc in m["lifecycle"]:
        s = lc.get("snapshot")
        if not s:
            continue
        if not s.get("chain_ok"):
            reds.append(f"lifecycle run {lc['state_dir']} fails its event-chain check")
        elif s.get("stage") == "BLOCKED":
            kind = (s.get("blocker") or {}).get("kind")
            text = f"lifecycle BLOCKED {kind}: {(s.get('blocker') or {}).get('reason')}"
            (yellows if kind in OWNER_BLOCKS else reds).append(text)
        elif s.get("stage") == "WAITING_FOR_MODEL":
            reds.append("lifecycle WAITING_FOR_MODEL (no independent reviewer available)")
    if tasks:
        if tasks.get("integrity_failure"):
            reds.append(f"task ledger integrity failure: {tasks.get('reason')}")
        for t in tasks.get("tasks") or []:
            if t.get("status") in ("BLOCKED", "INTERRUPTED"):
                reds.append(f"task {t.get('task_id')} {t.get('status')}")
    for a in open_approvals(p, ident):
        yellows.append(f"owner approval {a['id']} ({a['kind']}): {a['question']}")
    deps = unmet_dependencies(p, m)
    if reds:
        color, issue = "RED", reds[0]
    elif yellows:
        color, issue = "YELLOW", yellows[0]
    elif m["status"] in ("INTEGRATED", "DONE"):
        color, issue = "GREEN", None
    elif m["status"] in ("PLANNED", "PAUSED", "CANCELLED", "SUPERSEDED"):
        color, issue = "WHITE", (f"waits for {', '.join(deps)}" if deps else None)
    else:
        color, issue = "BLUE", None
        if tasks and any((t.get("open_blocking_findings") or 0) > 0 for t in tasks.get("tasks") or []):
            issue = "open blocking review findings in tasks (repair)"
    nxt = m.get("next_action")
    if color == "YELLOW" and not nxt:
        nxt = "owner decides " + ", ".join(a["id"] for a in open_approvals(p, ident))
    return {"color": color, "emoji": EMOJI[color], "word": WORD[color], "tone": A2UI_TONE[color],
            "phase": m["phase"], "status": m["status"], "issue": issue, "next_action": nxt,
            "more_issues": max(0, len(reds) + len(yellows) - 1)}


def ready(p, actor=None, now=None) -> list[str]:
    """Milestones that can be started or continued now: dependencies met, nothing open, not held by someone else."""
    now = now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
    out = []
    for m in p["milestones"].values():
        if m["status"] not in ("PLANNED", "IN_PROGRESS"):
            continue
        if unmet_dependencies(p, m) or open_blockers(p, m["id"]) or open_approvals(p, m["id"]):
            continue
        if open_conflicts(p, m["id"]):
            continue
        a = m.get("assignment")
        if a and a["agent"] != actor and a["expires_at"] > now:
            continue
        out.append(m["id"])
    return sorted(out, key=lambda i: _prio_key(p["milestones"][i]))


def _prio_key(m):
    pr = m.get("priority") or ""
    num = int(pr[1:]) if pr[:1] == "P" and pr[1:].isdigit() else 999
    return (num, m["id"])


def status_lines(p, emoji=True, task_source=None, milestone=None) -> list[str]:
    lines = []
    if p.get("integrity_errors"):
        lines.append(f"!! LEDGER INTEGRITY FAILURE ({len(p['integrity_errors'])}): {p['integrity_errors'][0]}")
        lines.append("!! Statuses below may be untrustworthy. Run `verify`; writes are refused until resolved.")
    for w in (p.get("integrity_warnings") or [])[:3]:
        lines.append(f"warning: {w}")
    ms = sorted(p["milestones"].values(), key=_prio_key)
    if milestone:
        ms = [m for m in ms if m["id"] == milestone]
    owner_first = []
    for a in sorted(p["approvals"].values(), key=lambda a: int(a["id"].split("-")[1])):
        if a["status"] == "REQUESTED" and (not milestone or a["subject"] == milestone):
            owner_first.append(f"{'%s ' % EMOJI['YELLOW'] if emoji else ''}OWNER DECISION {a['id']} [{a['subject']}] "
                               f"{a['kind']}: {a['question'][:200]}")
    if owner_first:
        lines.append(f"Owner decisions waiting: {len(owner_first)}")
        lines.extend("  " + x for x in owner_first)
    for m in ms:
        ind = indicator(p, m, task_source(m["id"]) if task_source else None)
        head = f"{ind['emoji'] + ' ' if emoji else ''}{ind['word']:<12} | {m['id']} | {m.get('priority') or '-'} | " \
               f"phase {m['phase']} | status {m['status']}"
        lines.append(head)
        if ind["issue"]:
            more = f" (+{ind['more_issues']} more)" if ind["more_issues"] else ""
            lines.append(f"    issue: {ind['issue'][:300]}{more}")
        if ind["next_action"]:
            lines.append(f"    next: {ind['next_action'][:300]}")
    oc = open_conflicts(p)
    if oc:
        lines.append(f"Unresolved conflicts: {len(oc)} (list them with `conflicts`; resolve with "
                     "`resolve-conflict <entity> --id <id> --note ...`)")
    reviews = len(p["reviews"])
    if reviews:
        lines.append(f"Reviews recorded: {reviews} (routine detail: `show <milestone>`)")
    return lines


def status_json(p, task_source=None, now=None) -> dict:
    out = {"schema": STATUS_SCHEMA,
           "generated_at": now or datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "ledger": {"events": p["events"], "conflicts_open": len(open_conflicts(p)),
                      "integrity_errors": p.get("integrity_errors", []),
                      "integrity_warnings": p.get("integrity_warnings", [])},
           "milestones": [], "approvals_open": [], "decisions": {}}
    rdy = set(ready(p))
    for m in sorted(p["milestones"].values(), key=_prio_key):
        tasks = task_source(m["id"]) if task_source else None
        ind = indicator(p, m, tasks)
        out["milestones"].append({
            "id": m["id"], "title": m["title"], "priority": m.get("priority"), "phase": m["phase"],
            "status": m["status"], "indicator": {k: ind[k] for k in ("color", "word", "tone", "issue", "next_action")},
            "depends_on": m["depends_on"], "ready": m["id"] in rdy,
            "open_approvals": [a["id"] for a in open_approvals(p, m["id"])],
            "open_blockers": [b["id"] for b in open_blockers(p, m["id"])],
            "assignment": m.get("assignment"), "worktree": m.get("worktree"), "branch": m.get("branch"),
            "candidate_commit": m.get("candidate_commit"), "integration": m.get("integration"),
            "lifecycle": [{"state_dir": x["state_dir"], "stage": (x.get("snapshot") or {}).get("stage"),
                           "blocker_kind": ((x.get("snapshot") or {}).get("blocker") or {}).get("kind")}
                          for x in m["lifecycle"]],
            "tasks": {"available": bool(tasks and tasks.get("available")),
                      "count": len((tasks or {}).get("tasks") or [])} if task_source else None})
    out["approvals_open"] = [{"id": a["id"], "subject": a["subject"], "kind": a["kind"], "question": a["question"]}
                             for a in p["approvals"].values() if a["status"] == "REQUESTED"]
    counts = {}
    for d in p["decisions"].values():
        counts[d["status"]] = counts.get(d["status"], 0) + 1
    out["decisions"] = counts
    return out


def resume_brief(p, ident, tasks: dict | None = None, max_chars: int = 6000, emoji=True) -> str:
    """Bounded continuity brief answering the seven questions for one milestone."""
    m = p["milestones"].get(ident)
    if not m:
        return f"No milestone {ident}."
    ind = indicator(p, m, tasks)
    ev = [e for e in p["evidence"].values() if e["subject"] == ident]
    banner = []
    if p.get("integrity_errors"):
        banner = [f"!! LEDGER INTEGRITY FAILURE: {p['integrity_errors'][0]} - do not trust this brief; run `verify`"]
    rv = sorted((r for r in p["reviews"].values() if r["subject"] == ident), key=lambda r: r["recorded"]["ts"])
    ho = sorted((h for h in p["handoffs"].values() if h["subject"] == ident), key=lambda h: h["recorded"]["ts"])
    rel_dec = [d for d in p["decisions"].values() if ident in " ".join(d.get("related") or [])]
    out = banner + [f"RESUME {ident} - {m['title']}",
           f"{ind['emoji'] + ' ' if emoji else ''}{ind['word']} | priority {m.get('priority') or '-'} | phase "
           f"{m['phase']} | status {m['status']} | worktree {m.get('worktree') or '-'} | branch {m.get('branch') or '-'}",
           f"candidate commit: {m.get('candidate_commit') or '-'} | base: {m.get('base_commit') or '-'}"]
    if m.get("assignment"):
        a = m["assignment"]
        out.append(f"assigned to {a['agent']} until {a['expires_at']}")
    out.append("")
    out.append("1. REQUESTED: " + (m.get("objective") or "(no objective recorded)"))
    if m.get("acceptance_ref"):
        out.append(f"   acceptance criteria: {m['acceptance_ref']}")
    out.append("2. COMPLETED:")
    sh = m["status_history"][-4:]
    out.extend(f"   - status {h['status']} at {h['at']} by {h['by']}: {h.get('reason') or ''}" for h in sh)
    if tasks and tasks.get("available"):
        done = [t for t in tasks["tasks"] if t.get("status") in ("ACCEPTED", "INTEGRATED")]
        out.extend(f"   - task {t.get('task_id')} {t.get('status')} {t.get('title', '')}" for t in done[:10])
    if ho:
        out.append(f"   last handoff {ho[-1]['id']}: {ho[-1]['summary']}" + (f" | done: {ho[-1]['done']}"
                                                                          if ho[-1].get("done") else ""))
    out.append(f"3. EVIDENCE ({len(ev)}):")
    for e in ev[-12:]:
        out.append(f"   - {e['id']} {e['kind']} {e['result_class']} {e['ref']}"
                   f"{' sha256 ' + e['sha256'][:12] if e.get('sha256') else ''}"
                   f"{' @' + e['commit'][:10] if e.get('commit') else ''}")
    out.append("   reviews: " + ("; ".join(f"{r['id']} {r['verdict']} ({r['assurance']}, {r['reviewer']['id']}) on "
                                           f"{r['commit'][:10]}" for r in rv[-6:]) or "none"))
    out.append("4. REJECTED / SUPERSEDED:")
    neg = [r for r in rv if r["verdict"] not in ("ACCEPT", "ACCEPT WITH FINDINGS")]
    out.extend(f"   - review {r['id']} {r['verdict']}: {r['summary'][:200]}" for r in neg[-5:])
    for d in rel_dec:
        if d["status"] != "ACTIVE" or d.get("alternatives_rejected"):
            out.append(f"   - {d['id']} {d['status']}: {d['title']}"
                       + (f" | rejected: {d['alternatives_rejected'][:200]}" if d.get("alternatives_rejected") else ""))
    out.append("5. UNFINISHED:")
    for b in open_blockers(p, ident):
        out.append(f"   - blocker {b['id']} {b['kind']}: {b['reason']} (needs {b['needs']})")
    deps = unmet_dependencies(p, m)
    if deps:
        out.append(f"   - waits for milestones {', '.join(deps)}")
    if tasks:
        if tasks.get("available"):
            for t in [t for t in tasks["tasks"] if t.get("status") not in ("ACCEPTED", "INTEGRATED", "ABANDONED")][:15]:
                out.append(f"   - task {t.get('task_id')} {t.get('status')} {t.get('title', '')}"
                           f"{' | next: ' + t['next_action'] if t.get('next_action') else ''}")
        else:
            out.append(f"   - task ledger: {tasks.get('reason')}")
    for lc in m["lifecycle"]:
        s = lc.get("snapshot") or {}
        out.append(f"   - lifecycle run {lc['state_dir']}: stage {s.get('stage') or 'not synced'}"
                   + (f", blocker {s['blocker']['kind']}" if s.get("blocker") else ""))
    out.append("6. SAFE NEXT: " + (ind["next_action"] or (ho[-1].get("next") if ho else None) or "(none recorded)"))
    if ind["color"] == "RED":
        out.append(f"   resolve first: {ind['issue']}")
    out.append("7. OWNER APPROVAL NEEDED:")
    oa = open_approvals(p, ident)
    out.extend(f"   - {a['id']} {a['kind']}: {a['question'][:300]}" for a in oa)
    if not oa:
        out.append("   - none open")
    text = "\n".join(out)
    max_chars = max(int(max_chars), MIN_RESUME_CHARS)  # a smaller bound would cut below the notice (review R22-04)
    if len(text) > max_chars:
        text = text[: max(0, max_chars - 60)].rsplit("\n", 1)[0] + f"\n[truncated at {max_chars} chars; use `show {ident}`]"
    return text


def conflict_rows(p, entity=None) -> list[dict]:
    """Open conflicts with their ids, for the `conflicts` command.

    Filtered by ``entity`` (an entity or a milestone named as subject), the listing still contains every member of
    each (entity, event) group it shows, because one id resolves the whole group (review R20-02)."""
    listed = open_conflicts(p, entity) if entity else open_conflicts(p)
    if entity:
        groups = {(c["entity"], c["event"]["hash"]) for c in listed}
        listed = [c for c in open_conflicts(p) if (c["entity"], c["event"]["hash"]) in groups]
    rows = []
    for c in listed:
        rows.append({"id": did(p, c), "type": c.get("type"), "entity": c["entity"],
                     "subject": c.get("subject"), "recorded_by": c.get("kind"),
                     "event": f"{c['event']['seg']}#{c['event']['seq']}", "at": c["event"].get("ts"),
                     "subjects": c.get("subjects"),
                     "detail": {k: c[k] for k in ("lost", "anchor_problems", "unknown_previous", "adopted",
                                                   "bound", "candidate", "problems", "missing", "expected", "actual", "duplicate", "batch") if k in c}})
    return rows
