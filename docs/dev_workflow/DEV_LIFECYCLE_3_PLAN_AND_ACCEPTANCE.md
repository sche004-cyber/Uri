# DEV-LIFECYCLE-3 — UI-first live qualification and auditor selection: plan and acceptance criteria

Status: plan, 2026-10-15. Milestone id `DEV-LIFECYCLE-3`. Baseline: canonical
`https://github.com/sche004-cyber/Uri` branch `integration/git-sync-20261008` at `1b5423bc` (verified with
`git ls-remote uri-repo` on 2026-10-15). Candidate branch `milestone/dev-lifecycle-3-ui-first-20261015`.

## 1. Source

Owner directive "PERMANENT DEVELOPMENT LIFECYCLE REFINEMENT — UI-FIRST LIVE QUALIFICATION AND INDEPENDENT
AUDIT" (chat, 2026-10-15). The message ends mid-sentence ("Reports and dashboards should"); the missing tail is
NOT VERIFIED. This plan reads it as the existing rule that reports and dashboards are generated from the structured
evidence and never replace it. Owner decision D18 (brief, simple result summaries), which was scheduled for
"DEV-LIFECYCLE-3", is folded in.

## 2. Scope

Policy and documentation only. Changed files:

- `.claude/skills/uri-development-lifecycle/SKILL.md` (the one authoritative skill text)
- `.agents/skills/uri-development-lifecycle/SKILL.md` (pointer; Codex wording only)
- `docs/dev_workflow/URI_DEVELOPMENT_LIFECYCLE.md` (reference; new section 8)
- `docs/dev_workflow/lifecycle/TEMPLATE.json` (default reviewer, UX review focus, evidence-class note)
- `docs/dev_workflow/lifecycle/UI_QUALIFICATION_TEMPLATE.json` (new: structured qualification record)
- `CLAUDE.md`, `AGENTS.md` (lifecycle paragraphs only)
- `docs/governance/OWNER_DECISIONS_20261011.md` (record the directive; mark D18 applied)
- this file

Not changed: `scripts/dev_workflow/**` (the driver), tests, protected paths (`ws_frozen_check`), `.gitignore`,
the AO-4 four-stage governance document, any runtime code. The driver keeps every existing gate; no gate is
weakened. Driver-level enforcement of the UI qualification record is a possible later milestone (section 5).

## 3. Acceptance criteria

| ID | Criterion | How it is checked |
|---|---|---|
| AC-1 | One lifecycle. The 12 owner stages are mapped onto the existing skill and driver stages; no competing lifecycle document is created; the older `uri-development` skill and the AO-4 four-stage document are not contradicted | read SKILL.md, reference doc; grep for other lifecycle definitions |
| AC-2 | UI-first rule. Every user-facing capability needs live qualification through the real URI Windows app, Core and services (Brain where applicable); mock UI tests and CLI runs do not count; indirect capabilities are qualified through their user-facing consumer; purely internal infrastructure documents why it has no UI and uses integration/operational verification | SKILL.md + reference section 8 |
| AC-3 | Live testing covers discoverability, visibility, usability, feedback, functional gaps and consistency (A–F), first-time and returning-user journeys, and evidence-led, minimal, dismissible, re-openable onboarding | reference section 8 |
| AC-4 | Mandatory UX loop (live test → classify → smallest repair → regression → live retest → independent review → accept/iterate). Material defects block qualification; minor ones may be deferred only when the independent auditor confirms essential journeys are not compromised | SKILL.md + reference |
| AC-5 | Auditor selection: Codex (`codex_cli`) first, after a real access check; fallback a separate Claude process (`claude_cli`) or, outside the driver, a separate Claude session with read-only access and no implementation authority; neither available ⇒ `INDEPENDENT AUDIT: BLOCKED`; a known-down Codex is not retried; fallback reason and reviewer identity recorded | SKILL.md |
| AC-6 | Existing guarantees unchanged: only a driver-counted independent round (claude_cli/codex_cli, exact SHA) supports VERIFIED and integration (owner D1); `import-review` never counts as ACCEPT; no self-certification; owner gates, frozen paths, stop and repair policy kept | diff of SKILL.md shows no removed rule; driver untouched |
| AC-7 | Verdict vocabulary ACCEPT / ACCEPT WITH FINDINGS / REVISE / REJECT / BLOCKED is defined and mapped to driver outcomes; a source-code ACCEPT is not phase qualification | SKILL.md |
| AC-8 | Auditor evidence classes: code inspected, tests independently executed, evidence reviewed, live behaviour independently observed, claims not verified — carried into every reviewer prompt through the template `environment_notes` | TEMPLATE.json; `review_prompt()` already includes `environment_notes` (lifecycle.py) |
| AC-9 | Structured UI qualification record with every field in directive section 9; status PASS / FAIL / NOT VERIFIED / BLOCKED; PASS only from COMPLETED_WITH_RESULT evidence; bound to the exact code commit tested | UI_QUALIFICATION_TEMPLATE.json is valid JSON and has those fields |
| AC-10 | Integration preconditions (directive section 10) listed; owner authorisation is requested only with a PASS record or with the owner's explicit acceptance of named NOT VERIFIED items | SKILL.md |
| AC-11 | URI Office application recorded: O2/O3/O4/O5 order, O2P printing deferred and off by default with its code and evidence preserved, O2 qualification items listed, O2 not frozen while mandatory live checks are open | SKILL.md (Office section) |
| AC-12 | D18 applied: owner summaries are short and in plain words | SKILL.md reporting section |
| AC-13 | No regression: `tests/dev_workflow` passes on the candidate as on the baseline; TEMPLATE.json still loads with `load_config` | gate run |
| AC-14 | Independent review of this candidate by Codex, or a recorded fallback | lifecycle run record |

## 4. Owner-only decisions

None needed to land the policy text: the owner directive is the decision. Canonical integration of this milestone
follows D1 and needs the owner's authorisation for this target (`authorized: false` until given).

Open point for the owner (does not block): the directive allows a separate Claude session as fallback auditor.
Such a review is recorded with `import-review`; under D1 it routes findings but does not by itself authorise
canonical integration. The skill keeps D1 unchanged and says so.

## 5. Not in scope / later

- Driver enforcement (refuse integration unless a PASS UI qualification record for the candidate exists).
- Running the O2 live UI qualification itself (separate Office work on the Office branches).
</content>
</invoke>
