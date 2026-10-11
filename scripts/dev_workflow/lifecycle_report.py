"""Visual milestone report for uri-development-lifecycle.

``write_report`` turns a milestone's state into two files next to the receipt:
- ``REPORT.html``: a self-contained page (inline CSS and SVG, no scripts, no network, light and dark) the owner can
  open anywhere, including on the PC;
- ``report_data.json``: the same figures as rows (rounds, findings, repairs, gates, blockers, owner actions) for the
  coordinating session to publish as a dashboard.

Every figure is derived from the state the driver recorded; nothing is typed in by hand.

Boundary Guarantee: Development tooling only. Not part of the URI runtime.
"""
from __future__ import annotations

import html
import json
from pathlib import Path

STAGE_TONE = {"COMPLETE": "good", "VERIFIED": "good", "BLOCKED": "bad", "NOT_VERIFIED": "bad",
              "WAITING_FOR_MODEL": "warn", "FIXING": "warn", "AUDITING": "warn", "VERIFYING": "warn"}
STAGE_TEXT = {
    "COMPLETE": "Independently accepted, qualified and integrated.",
    "VERIFIED": "Independently accepted and qualified; integration not performed (policy or waiting).",
    "BLOCKED": "Stopped: needs a decision or a resource before it can continue.",
    "NOT_VERIFIED": "Not qualified.",
    "WAITING_FOR_MODEL": "Waiting: no usable independent review yet. Not qualified.",
}


def _blocking(f: dict) -> bool:
    sev = str(f.get("severity", "")).strip().upper()
    b = str(f.get("blocking")).strip().lower()
    if sev == "LOW":
        return b == "true"
    if sev == "MEDIUM":
        return b != "false"
    return True


def report_data(state: dict, status: dict) -> dict:
    """Rows for the dashboard, all taken from the recorded state."""
    repaired = {}
    for r in state.get("repairs") or []:
        if r.get("status") == "COMMITTED":
            for fid in r.get("addresses") or []:
                repaired[fid] = r.get("commit")
    rounds, findings = [], []
    for r in state.get("rounds") or []:
        res = r.get("result") or {}
        fs = [f for f in res.get("findings") or [] if isinstance(f, dict)]
        w = r.get("worker") or {}
        rounds.append({"round": f"R{r['round']}", "candidate": str(r.get("candidate", ""))[:12],
                       "reviewer": w.get("provider"), "session": w.get("session_id"),
                       "verdict": r.get("effective_verdict") or ("running" if "status" not in r else "none"),
                       "status": r.get("status") or "running", "independent": r.get("independent"),
                       "findings": len(fs), "blocking": sum(_blocking(f) for f in fs),
                       "finished": r.get("ended_at")})
        for f in fs:
            fid = f.get("id")
            findings.append({"round": f"R{r['round']}", "id": fid, "severity": str(f.get("severity", "")).upper(),
                             "blocking": _blocking(f), "title": f.get("title"),
                             "status": f"repaired {repaired[fid][:7]}" if fid in repaired else
                             ("open" if _blocking(f) else "non-blocking")})
    repairs = [{"repair": f"P{r['repair']}", "status": r.get("status"), "commit": (r.get("commit") or "")[:12],
                "addresses": ", ".join(map(str, r.get("addresses") or [])), "reason": r.get("reason") or ""}
               for r in state.get("repairs") or []]
    gates = []
    for sha, q in (state.get("gates") or {}).items():
        for gid, e in (q.get("gates") or {}).items():
            c, cand = e.get("comparison") or {}, e.get("candidate") or {}
            gates.append({"commit": sha[:12], "gate": gid, "ok": bool(e.get("ok")), "passed": cand.get("passed"),
                          "failed": len(cand.get("failures") or {}), "new": len(c.get("new_failures") or []),
                          "changed_cause": len(c.get("changed_cause") or []), "vanished": len(c.get("vanished") or []),
                          "status": cand.get("status")})
    owner = []
    b = state.get("blocker") or {}
    if b:
        owner.append({"kind": b.get("kind"), "reason": b.get("reason"), "needs": b.get("needs")})
    integ = state.get("integration") or {}
    if integ.get("status") == "AWAITING_OWNER_AUTHORIZATION" and not b:
        owner.append({"kind": "OWNER_AUTHORIZATION", "reason": "integration awaits authorisation", "needs": integ.get("command")})
    latest = rounds[-1] if rounds else {}
    open_blocking = [f for f in findings if f["round"] == latest.get("round") and f["blocking"] and f["status"] == "open"]
    summary = {"milestone": status.get("milestone"), "stage": status.get("stage"), "baseline": status.get("baseline"),
               "candidate": status.get("candidate"), "rounds": len(rounds),
               "repairs_committed": sum(1 for r in repairs if r["status"] == "COMMITTED"),
               "findings_total": len(findings), "findings_repaired": sum(1 for f in findings if f["status"].startswith("repaired")),
               "open_blocking": len(open_blocking), "owner_actions": len(owner),
               "evidence_ok": bool(status.get("evidence_ok_for_candidate")),
               "receipt_chain_ok": not status.get("verify_errors"), "written_at": status.get("written_at"),
               "integration": integ.get("status") or "none"}
    return {"summary": summary, "rounds": rounds, "findings": findings, "repairs": repairs, "gates": gates,
            "owner": owner}


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _rounds_svg(rounds: list) -> str:
    if not rounds:
        return '<p class="note">No review round yet.</p>'
    w, h, ml, mb, mt = 640, 200, 30, 28, 8
    top = max(4, max(r["findings"] for r in rounds))
    bw = (w - ml - 8) / len(rounds)
    y = lambda v: mt + (h - mt - mb) * (1 - v / top)
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Findings per review round">']
    for t in range(0, top + 1, max(1, top // 4)):
        out.append(f'<line x1="{ml}" x2="{w - 8}" y1="{y(t):.1f}" y2="{y(t):.1f}" class="grid"/>'
                   f'<text x="{ml - 6}" y="{y(t) + 4:.1f}" text-anchor="end" class="tick">{t}</text>')
    for i, r in enumerate(rounds):
        bwi = min(bw * 0.64, 56)
        x = ml + i * bw + (bw - bwi) / 2
        tone = "bad" if r["verdict"] == "REJECT" else ("good" if str(r["verdict"]).startswith("ACCEPT") else "muted")
        out.append(f'<g><title>{_e(r["round"])} {_e(r["candidate"])}: {_e(r["verdict"])}, {r["blocking"]} blocking of '
                   f'{r["findings"]}</title>'
                   f'<rect x="{x:.1f}" width="{bwi:.1f}" y="{y(r["findings"]):.1f}" height="{y(0) - y(r["findings"]):.1f}" '
                   f'rx="4" class="bar {tone} light"/>'
                   f'<rect x="{x:.1f}" width="{bwi:.1f}" y="{y(r["blocking"]):.1f}" height="{y(0) - y(r["blocking"]):.1f}" '
                   f'rx="4" class="bar {tone}"/>'
                   + (f'<rect x="{x:.1f}" width="{bwi:.1f}" y="{y(0) - 4:.1f}" height="4" rx="2" class="bar {tone}"/>'
                      f'<text x="{x + bwi / 2:.1f}" y="{y(0) - 10:.1f}" text-anchor="middle" class="tick">'
                      f'{_e(r["verdict"]).split()[0].lower()}</text>' if r["findings"] == 0 else "")
                   + '</g>'
                   f'<text x="{x + bwi / 2:.1f}" y="{h - 10}" text-anchor="middle" class="tick">{_e(r["round"])}</text>')
    out.append("</svg>")
    return "".join(out)


def _table(rows: list, cols: list, pills=()) -> str:
    if not rows:
        return '<p class="note">None.</p>'
    head = "".join(f"<th>{_e(label)}</th>" for _, label in cols)
    body = []
    for r in rows:
        cells = []
        for key, _ in cols:
            v = r.get(key)
            if key in pills:
                s = str(v)
                tone = ("bad" if s in ("REJECT", "open", "REFUSED", "HIGH", "False") or s.startswith("BLOCK") else
                        "good" if s.startswith(("ACCEPT", "repaired", "COMMITTED", "True")) else
                        "warn" if s in ("MEDIUM", "running") else "")
                cells.append(f'<td><span class="pill {tone}">{_e(v)}</span></td>')
            else:
                cells.append(f"<td>{_e(v)}</td>")
        body.append("<tr>" + "".join(cells) + "</tr>")
    return f'<div class="tbl"><table><thead><tr>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>'


CSS = """
:root{--bg:#f7f8fa;--panel:#fff;--fg:#1d232b;--muted:#5d6774;--line:#dde1e7;--good:#1f7a4d;--bad:#b3261e;--warn:#9a6200;
--goodf:#2e9e66;--badf:#d0453b;--mutedf:#a9b1bc;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#14171b;--panel:#1c2026;--fg:#e6e9ee;--muted:#9aa4b1;
--line:#2d333b;--good:#5fd19a;--bad:#ff8a80;--warn:#f2b84b;--goodf:#3fb37d;--badf:#e5675d;--mutedf:#59626e;color-scheme:dark}}
:root[data-theme=dark]{--bg:#14171b;--panel:#1c2026;--fg:#e6e9ee;--muted:#9aa4b1;--line:#2d333b;--good:#5fd19a;--bad:#ff8a80;
--warn:#f2b84b;--goodf:#3fb37d;--badf:#e5675d;--mutedf:#59626e;color-scheme:dark}
body{background:var(--bg);color:var(--fg);font:14px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif;margin:0;
padding-block:24px;padding-inline:16px}
.wrap{max-width:1100px;margin-inline:auto;display:grid;gap:20px}
h1{font:400 1.8rem/1.2 Georgia,"Times New Roman",serif;margin:0;text-wrap:balance}h2{font-size:1.05rem;margin:0}
.sub,.note{color:var(--muted);margin:0}.tiles{display:grid;gap:12px;grid-template-columns:repeat(auto-fit,minmax(min(100%,10rem),1fr))}
.card,.tile{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:16px;min-width:0;display:grid;gap:8px;align-content:start}
.tile .n{font:400 1.9rem/1.1 Georgia,serif;font-variant-numeric:tabular-nums}.tile .l{color:var(--muted);font-size:.85rem}
.tile.bad .n{color:var(--bad)}.tile.warn .n{color:var(--warn)}.tile.good .n{color:var(--good)}
.grid2{display:grid;gap:16px;grid-template-columns:repeat(auto-fit,minmax(min(100%,26rem),1fr))}
.tbl{overflow:auto;max-height:28rem}table{border-collapse:collapse;width:100%;font-size:.85rem;font-variant-numeric:tabular-nums}
th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}
th{position:sticky;top:0;background:var(--panel);color:var(--muted);font-weight:600}
.pill{display:inline-block;padding:0 8px;border-radius:999px;border:1px solid var(--line);white-space:nowrap}
.pill.good{color:var(--good);border-color:currentColor}.pill.bad{color:var(--bad);border-color:currentColor}
.pill.warn{color:var(--warn);border-color:currentColor}.stage{font-size:.95rem;padding:2px 12px}
svg .grid{stroke:var(--line)}svg .tick{fill:var(--muted);font-size:11px}svg .bar.good{fill:var(--goodf)}
svg .bar.bad{fill:var(--badf)}svg .bar.muted{fill:var(--mutedf)}svg .bar.light{opacity:.35}
code{font-size:.85em;word-break:break-all}
"""


def render_html(data: dict) -> str:
    s = data["summary"]
    tone = STAGE_TONE.get(s["stage"], "")
    tiles = [("Review rounds", s["rounds"], ""), ("Findings repaired", f'{s["findings_repaired"]} / {s["findings_total"]}', "good"),
             ("Open blocking findings", s["open_blocking"], "bad" if s["open_blocking"] else "good"),
             ("Repairs committed", s["repairs_committed"], ""),
             ("Needs you", s["owner_actions"], "warn" if s["owner_actions"] else "good")]
    tiles_html = "".join(f'<div class="tile {t}"><span class="l">{_e(l)}</span><span class="n">{_e(v)}</span></div>'
                         for l, v, t in tiles)
    evidence = ("Independent ACCEPT and passing gates are recorded on this exact commit." if s["evidence_ok"] else
                "Not qualified: no independent ACCEPT with passing gates on this exact commit yet.")
    chain = "Receipt chain verified." if s["receipt_chain_ok"] else "Receipt chain verification FAILED."
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>{_e(s['milestone'])} report</title>
<style>{CSS}</style></head><body><div class="wrap">
<header><h1>{_e(s['milestone'])}</h1>
<p class="sub"><span class="pill stage {tone}">{_e(s['stage'])}</span> {_e(STAGE_TEXT.get(s['stage'], 'In progress.'))}
{_e(evidence)} {_e(chain)}</p>
<p class="note">Baseline <code>{_e(s['baseline'])}</code> · candidate <code>{_e(s['candidate'])}</code> ·
integration {_e(s['integration'])} · written {_e(s['written_at'])}</p></header>
<section class="tiles">{tiles_html}</section>
<section class="card"><h2>Needs you</h2>{_table(data['owner'], [('kind', 'What'), ('reason', 'Why'), ('needs', 'What to do')])}</section>
<div class="grid2">
<section class="card"><h2>Review rounds</h2><p class="note">Findings per round, darker part blocking; red rejected,
green accepted. Each round is a separate reviewer process.</p>{_rounds_svg(data['rounds'])}</section>
<section class="card"><h2>Qualification gates</h2>{_table(data['gates'], [('commit', 'Commit'), ('gate', 'Gate'),
('ok', 'OK'), ('passed', 'Passed'), ('failed', 'Failed'), ('new', 'New'), ('vanished', 'Vanished')], pills=('ok',))}</section>
</div>
<section class="card"><h2>Reviewer log</h2>{_table(data['rounds'], [('round', 'Round'), ('candidate', 'Commit'),
('reviewer', 'Reviewer'), ('session', 'Session'), ('verdict', 'Verdict'), ('blocking', 'Blocking'), ('findings', 'Findings'),
('independent', 'Independent'), ('finished', 'Finished')], pills=('verdict', 'independent'))}</section>
<section class="card"><h2>Findings</h2>{_table(data['findings'], [('round', 'Round'), ('id', 'Id'), ('severity', 'Severity'),
('status', 'Status'), ('title', 'Finding')], pills=('severity', 'status'))}</section>
<section class="card"><h2>Repairs</h2>{_table(data['repairs'], [('repair', '#'), ('status', 'Status'), ('commit', 'Commit'),
('addresses', 'Addresses'), ('reason', 'Reason')], pills=('status',))}</section>
<p class="note">Generated by scripts/dev_workflow/lifecycle_report.py from the milestone's recorded state.</p>
</div></body></html>"""


def write_report(state_dir: Path, state: dict, status: dict) -> Path:
    data = report_data(state, status)
    (state_dir / "report_data.json").write_bytes(json.dumps(data, indent=1, sort_keys=True).encode("utf-8"))
    out = state_dir / "REPORT.html"
    out.write_bytes(render_html(data).encode("utf-8"))
    return out
