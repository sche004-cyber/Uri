"""Migration rehearsal for the Milestone Manager (not a promotion).

Builds a fresh ledger at --home from the P0 registers (read-only) and the owner's 2026-10-21 roadmap, then prints
verify / status / resume output for the evidence folder. Markdown registers stay authoritative until the owner
promotes a ledger (implementation plan, phase 5).

    python docs/milestone_manager/migration/run_rehearsal.py --home D:/uri-dev/mm-ledger-rehearsal \
        --p0 D:/uri-dev/uri-p0-audit --p0-commit 8e1d6324 --out docs/milestone_manager/evidence/rehearsal
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from scripts.dev_workflow.milestones import importers, views  # noqa: E402
from scripts.dev_workflow.milestones.service import Manager  # noqa: E402
from scripts.dev_workflow.milestones.store import EventStore  # noqa: E402

ACTOR = "claude:milestone-manager-session-20261021"
OWNER_PROMPT = "owner prompt 'TASK: P0 — URI Milestone Manager', 2026-10-21, section F (roadmap)"
AMENDMENT = "owner message 'LIFECYCLE EXECUTION AMENDMENT — OWNER APPROVED', 2026-10-21"

# (id, priority, title, depends_on, status, phase, note)
ROADMAP = [
    ("MILESTONE-MANAGER", "P0", "Milestone Manager", [], "IN_PROGRESS", "TESTING",
     "This milestone. Worktree D:/uri-dev/uri-milestone-manager, branch milestone/milestone-manager-20261021."),
    ("LIFECYCLE-V3-1", "P1", "Lifecycle V3.1 (task intelligence)", [], "IN_PROGRESS", "IMPLEMENTATION",
     "Developed in parallel by session v1-2e on milestone/lifecycle-v3-1-task-intelligence-20261021; contract "
     "uri-dev/task-ledger-contract/1. No hard dependency either way."),
    ("PERSONAL-DATA-SOVEREIGNTY", "P2", "Personal Data Sovereignty", [], "PLANNED", "RESEARCH",
     "No design exists (DEC-089). Defect D10 (key-store secret per start) feeds it."),
    ("WRITING-INTELLIGENCE", "P3", "Writing Intelligence", [], "PLANNED", "RESEARCH",
     "Builds on CAP-TI1/CAP-VO1. Remote processing would need PERSONAL-DATA-SOVEREIGNTY; local-only work need not."),
    ("MEETING-INTELLIGENCE", "P4", "Meeting Intelligence", ["PERSONAL-DATA-SOVEREIGNTY"], "PLANNED", "RESEARCH",
     "Recordings are personal data; also needs CAP-VO1 human acoustic qualification."),
    ("OFFICE-CLIENT-INSTALLER", "P5", "URI Office Client Installer", [], "PLANNED", "RESEARCH",
     "Needs CAP-PK1 gaps CONS-7, R-3, R-4 and the OD-2 distribution gate."),
    ("MISSION-CONTROL", "P6", "Mission Control", ["MILESTONE-MANAGER"], "PLANNED", "RESEARCH",
     "Consumes uri-mm-status/1 and the V3.1 task contract."),
    ("SKILL-COMMAND-CENTER", "P7", "Skill Command Center", ["MILESTONE-MANAGER"], "PLANNED", "RESEARCH",
     "Owns skill qualification; links qualifications to MM milestones / V3.1 tasks."),
    ("DEVELOPER-STUDIO", "P8", "URI Developer Studio", ["MILESTONE-MANAGER", "LIFECYCLE-V3-1"], "PLANNED",
     "RESEARCH", "Register lists P1 and CAP-LC1/LC2 as prerequisites."),
    ("ADVANCED-VISION-ASSIST", "P9", "Advanced Vision Assist", [], "PLANNED", "RESEARCH",
     "Needs D14 perception adapters and the F-1 owner decision (AP for OPEN-04). GPU-exclusive live runs."),
    ("BRAIN-RUNTIME-OPTIMIZATION", "P10", "Brain Runtime Optimization", [], "PLANNED", "RESEARCH",
     "Needs the P1-profile decision (OPEN-03). GPU-exclusive; cannot run live tests beside other GPU work."),
]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--home", required=True)
    ap.add_argument("--p0", required=True)
    ap.add_argument("--p0-commit", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--candidate-commit")
    a = ap.parse_args()
    home, out = Path(a.home), Path(a.out)
    if (home / "mm.json").exists():
        sys.exit(f"{home} already holds a ledger; rehearsals start fresh")
    EventStore.init(home, "owner-pc")
    m = Manager(home, actor=ACTOR, session="rehearsal")
    rep_dec = importers.import_decisions(m, Path(a.p0) / "decisions.md", a.p0_commit)
    rep_reg = importers.import_register(m, Path(a.p0) / "developmental.md", a.p0_commit)
    m.record_decision(
        "Roadmap order P0..P10 (Milestone Manager first)",
        "Approved priority order: P0 Milestone Manager, P1 Lifecycle V3.1, P2 Personal Data Sovereignty, P3 Writing "
        "Intelligence, P4 Meeting Intelligence, P5 Office Client Installer, P6 Mission Control, P7 Skill Command "
        "Center, P8 Developer Studio, P9 Advanced Vision Assist, P10 Brain Runtime Optimization. Priorities do not "
        "automatically imply strict sequential dependencies.",
        "2026-10-21", "OWNER-PROMPT", OWNER_PROMPT, ident="LDEC-001",
        reasoning="Stated in the owner prompt; no further reasoning recorded.",
        consequences="Milestone Manager and Lifecycle V3.1 are separate milestones (DEC-088 combined them as P1). "
                     "DEC-088's P11 Multi-Client Deployment is not in this list: status asked as an open question.",
        related=["MILESTONE-MANAGER", "LIFECYCLE-V3-1"], supersedes="DEC-088", partial=True,
        note="numbering and the P1 split only; P11 unresolved")
    m.record_decision(
        "Milestone Manager runs the full Lifecycle V3; integration needs separate authorisation",
        "Execute research, discovery, architecture, implementation, testing, independent review, repair, acceptance "
        "and controlled integration in an isolated worktree; independent subagents qualify as reviewers; no routine "
        "owner involvement in review/repair; canonical integration only with separate owner authorisation after P0 "
        "prerequisites, gates, independent acceptance, frozen-core integrity and no blocking findings.",
        "2026-10-21", "OWNER-PROMPT", AMENDMENT, ident="LDEC-002", related=["MILESTONE-MANAGER"])
    m.record_decision(
        "Task state belongs to Lifecycle V3.1; Milestone Manager reads it through a contract",
        "Lifecycle V3.1 owns task ids, task context/evidence, execution transitions, review/acceptance gates, "
        "checkpoints, leases and recovery. The Milestone Manager owns milestones, roadmap, dependencies, owner "
        "decisions and project-level state, and reads tasks via `task_ledger summary --json` "
        "(uri-dev/task-ledger-contract/1).",
        "2026-10-21", "AGENT-RECORD",
        "agreement between the Milestone Manager session and the Lifecycle V3.1 session v1-2e, 2026-10-21 (messages)",
        ident="LDEC-003", related=["MILESTONE-MANAGER", "LIFECYCLE-V3-1"],
        alternatives_rejected="Milestone Manager keeps its own task list with leases and checkpoints (two sources of "
                              "truth for tasks).",
        reasoning="Owner prompt section G: avoid duplicate sources of truth; Lifecycle manages execution.")
    for ident, prio, title, deps, status, phase, note in ROADMAP:
        extra = {}
        if ident == "MILESTONE-MANAGER":
            extra = {"worktree": "D:/uri-dev/uri-milestone-manager", "branch": "milestone/milestone-manager-20261021",
                     "base_commit": "ec2fab5493578a4f5a805642153d56b4d5ea59fa",
                     "acceptance_ref": "docs/milestone_manager/ACCEPTANCE_CRITERIA.md"}
        if ident == "LIFECYCLE-V3-1":
            extra = {"worktree": "D:/uri-dev/uri-lifecycle-v31",
                     "branch": "milestone/lifecycle-v3-1-task-intelligence-20261021"}
        m.create_milestone(ident, title, objective=note, priority=prio, phase=phase, depends_on=deps,
                           status=status, next_action=None, **extra)
    if a.candidate_commit:
        m.update_milestone("MILESTONE-MANAGER", candidate_commit=a.candidate_commit)
    m.request_approval("PROJECT", "SCOPE", "Is P11 Multi-Client Deployment (DEC-088) still on the roadmap? It is "
                                           "absent from the 2026-10-21 P0..P10 list (LDEC-001).")
    m.request_approval("MILESTONE-MANAGER", "POLICY",
                       "Promote a Milestone Manager ledger as authoritative (replacing developmental.md / "
                       "decisions.md as the place of record), and where should it live (recommended: a dedicated git "
                       "worktree on an orphan branch ledger/milestones, autocommit on, push only with approval)?")
    m.record_handoff("MILESTONE-MANAGER", "Migration rehearsal ledger built from P0 registers @" + a.p0_commit,
                     done="imports + roadmap seed", next_action="independent review of the candidate")
    out.mkdir(parents=True, exist_ok=True)
    p = m.rebuild()
    verify = m.store.verify()
    (out / "import_reports.json").write_bytes(json.dumps({"decisions": rep_dec, "register": rep_reg}, indent=1,
                                                         sort_keys=True, default=str).encode())
    (out / "verify.json").write_bytes(json.dumps(verify, indent=1, sort_keys=True).encode())
    (out / "status.txt").write_bytes("\n".join(views.status_lines(p, emoji=False)).encode())
    (out / "status.json").write_bytes(json.dumps(views.status_json(p), indent=1, sort_keys=True).encode())
    (out / "resume_MILESTONE-MANAGER.txt").write_bytes(
        views.resume_brief(p, "MILESTONE-MANAGER", m.task_summaries("MILESTONE-MANAGER"), emoji=False).encode())
    print(json.dumps({"events": p["events"], "verify_ok": verify["ok"], "milestones": len(p["milestones"]),
                      "decisions": len(p["decisions"]), "approvals": len(p["approvals"]),
                      "records": len(p["records"]), "ready": views.ready(p)}, indent=1))


if __name__ == "__main__":
    main()
