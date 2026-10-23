# Owner directive 2026-10-23 — Remaining AP Decisions | P0 Coordination (verbatim)

Source: owner chat 2026-10-23, received by the Milestone Manager session and relayed verbatim to the P0 session
(cross-session message, 2026-10-23). Recorded as `decisions.md` DEC-103. Text below is unchanged.

---

URI — CONSOLIDATED OWNER DIRECTIVE
Remaining AP Decisions | P0 Coordination

OBJECTIVE

Resolve the remaining open AP items systematically using verified evidence, existing owner decisions, and URI's established development lifecycle.

Prioritize a working, secure, efficient URI over preserving obsolete components or earlier technical assumptions.

Do not repeatedly escalate routine technical decisions to me. I am currently away from my Windows PC.

AUTHORITATIVE REFERENCES

- Canonical repository and exact-commit evidence
- decisions.md, including DEC-101 and DEC-102
- Milestone Manager ledger and ratification records
- Lifecycle V3/V3.1 policies and acceptance requirements
- Existing independent review and live-test evidence
- Frozen-core integrity and rollback requirements

First reconcile current repository and ledger states. Do not assume previously reported commit hashes remain the latest state.

1. TECHNICAL INVESTIGATION AND RESOLUTION

Scope: AP-3, AP-4, AP-6, AP-7, AP-8, AP-11, AP-12, AP-21, AP-32.

For each item:
- Retrieve its exact OPEN/DEC references.
- Identify existing approvals, findings, and blockers.
- Check whether the work is already assigned or underway.
- Reuse existing qualified implementations where possible.
- Investigate alternatives using available evidence.
- Repair defects within established permissions.
- Run relevant regressions and functional tests.
- Obtain genuine independent review.
- Recommend the best technically qualified outcome.
- Preserve rollback and fallback capabilities.

Specific guidance:

AP-3: Investigate the P1 Brain crash before deciding whether retirement or repair is justified. Do not preserve an unstable profile merely because it already exists.

AP-4: Evaluate automatic Vision fallback to 32K without MTP. Prioritize reliable Vision operation over optional MTP. Verify context preservation, VRAM usage, and real workflows.

AP-6: Investigate the secure-rollback uri_web import failure. Do not weaken frozen-core or security protections.

AP-7: Evaluate Qwen3.8-27B as an experimental Brain candidate. Do not replace the qualified Brain without comparative accuracy, stability, latency, and VRAM evidence.

AP-8: Audit the _V1 line for remaining functional value. Salvage only useful components; otherwise preserve necessary historical evidence and recommend retirement. Do not perform destructive removal prematurely.

AP-11 and AP-12: Determine Thinking defaults and 64K context behavior using measured performance, reliability, and real URI task requirements.

AP-21: Investigate safe GPU headroom improvements. Respect the existing GPU lease and resource limits. No risky instability or stress testing.

AP-32: Prioritize repair of clashing test filenames so the complete suite can collect cleanly. Keep changes narrowly scoped and independently reviewed.

2. PRIVACY AND SECURITY — AP-16 THROUGH AP-20

Treat M95 privacy decisions OD-1 through OD-5 as security-sensitive work.

Investigate frozen-file hooks, DPAPI defects, permission handling, and grant-approval UI requirements.

Use isolated development worktrees.

Apply least privilege, local-first processing, credential isolation, explicit permissions, and appropriate auditability.

Do not weaken security boundaries to make tests pass.

Security exceptions, new sensitive-access permissions, or material privacy-policy changes still require explicit owner approval.

3. CONSOLIDATION — AP-9 AND AP-10

AP-9: Preserve qualified local research and relevant branches after checking secrets, provenance, duplication, and repository hygiene.

Recognize work already completed on the audit branch.

AP-10: Reconcile Phase 2 carryovers, CONS-1 through CONS-7, main-branch rename, cutover, and related unfinished items.

Separate:
- Already completed
- Technically resolvable
- Blocked by dependencies
- Requiring live Windows verification
- Requiring genuine owner approval

Do not repeat completed work or reopen accepted gates without new evidence.

4. ROADMAP — AP-13

Retain P11 Multi-Client Deployment as a deferred roadmap milestone.

Do not begin deployment implementation.

Preserve dependencies on privacy, authentication, client packaging, server reliability, and permission isolation.

5. OWNER AVAILABILITY — AP-2

AP-2 is DEFERRED because I am away from my PC.

Existing approval remains valid.

Do not remotely disable the \URIServer task, attempt elevation, or use a workaround.

Do not treat this as a blocker for unrelated work.

6. EXECUTION AND COORDINATION

P0 is responsible for auditing, reconciliation, coordination, and recording authoritative outcomes.

P0 must not become a competing implementation manager.

Use:
- Milestone Manager for milestone and decision state
- Lifecycle V3.1 for task execution and handoffs
- Existing qualified review mechanisms
- Skill Command Center where relevant

Before assigning work, check active task ownership, branches, dependencies, and resource conflicts.

Avoid parallel modifications to the same subsystem.

Respect the established Claude/Codex availability policy. Do not use Antigravity or additional subagents to bypass a development pause.

7. OWNER APPROVAL POLICY

Evidence-based technical investigation, ordinary repairs, testing, and independent review may proceed without repeated owner intervention.

Independent ACCEPT alone does not authorize canonical integration where separate owner authorization is required.

Do not:
- Invent owner decisions.
- Treat recommendations as approvals.
- Waive unresolved security findings.
- Bypass frozen-file protections.
- Perform unauthorized canonical integrations.
- Remove functional fallback paths prematurely.
- Reopen completed decisions without new evidence.

Escalate only genuinely consequential owner decisions, policy exceptions, security exceptions, or actions that existing authorization does not cover.

If a decision needs live Windows verification while I am away, mark it BLOCKED — OWNER PC REQUIRED. Continue unrelated eligible work.

8. RECORDKEEPING AND EFFICIENCY

Every task must retain:
- Stable task identifier
- Exact commit and branch
- Relevant OPEN/DEC references
- Findings and evidence
- Test results
- Independent review verdict
- Outstanding blockers
- Next action and responsible owner

Do not create competing sources of truth.

Use existing lifecycle memory, deduplication, evidence indexing, and post-integration cleanup rules.

Preserve essential evidence while avoiding unnecessary test artifacts, duplicate logs, and repository bloat.

9. REQUIRED OUTPUT

First produce a concise reconciliation table showing:

AP ID | Current state | Evidence | Assigned owner | Next action | Approval required?

Then coordinate the authorized work through existing task owners and lifecycle mechanisms.

Prioritize:
1. AP-32 — clean test collection
2. AP-16–20 — M95 security and privacy
3. AP-6 — secure rollback
4. AP-3, AP-4, AP-21 — Brain/Vision/runtime reliability
5. AP-8–12 — legacy and configuration decisions
6. AP-9, AP-10, AP-13 — consolidation and roadmap

Adjust order if verified dependencies require it.

Do not report success merely because a task was assigned or tests passed.

Distinguish IMPLEMENTED, REVIEWED, ACCEPTED, LIVE VERIFIED, INTEGRATED, DEFERRED, and BLOCKED.

After reconciliation, report:
- Items resolved
- Work currently authorized and underway
- Items needing live PC access
- Genuine remaining owner decisions
- Any conflicts between P0 and the ledger

Proceed with authorized coordination and development. Do not wait for routine owner confirmation.

Preserve existing security, acceptance, integration, and rollback gates throughout.
