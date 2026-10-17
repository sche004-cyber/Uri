# URI-RUNTIME-VRAM-R1 — independent audit package

Status: PENDING AUDIT. Codex is not available (weekly limit until 2026-10-22 14:03; the `codex` MCP server failed to
connect in this session). The claude_cli reviewer is not logged in. The owner can give the prompt below to any
independent reviewer that has read access to this PC's repository.

## What is under review

- Branch `research/runtime-vram-r1-20261017`, worktree `D:\uri-dev\uri-runtime-vram-r1`, base canonical `25048709`.
  The review head is the commit named in the owner's message (the final commit of this milestone).
- Code candidate (not integrated):
  - `uri_operational_intelligence/runtime_profiles.py` (new)
  - `uri_operational_intelligence/runtime_v1.py` (+3 lines: `--no-mmproj-offload` only when a derived config sets
    `vision_offload: false`)
  - `scripts/ws_brain_host.py` (the lease and fit use the profile's measured request; `--profile`; `profile` in the
    report)
  - `tests/oi/test_runtime_profiles.py` (new)
  - `docs/operational_intelligence/RUNTIME_PROFILES_UI_CONTRACT.md`
- Research harness and evidence: `research/runtime_vram_r1/` (report `RUNTIME_VRAM_R1_REPORT.md`, criteria
  `ACCEPTANCE_CRITERIA.md`, the Lifecycle V3.1 proposal) and `model_lab/evidence/runs/vr1_*`.
- The Phase 1 suite-P worktree `D:\uri-dev\uri-vram-r1-p1` (detached at `e8e3b652`, with untracked `model_lab/` copied
  from canonical: identical harness files).

## Prompt for the independent reviewer (copy everything between the lines)

---
You are an independent reviewer for the URI milestone URI-RUNTIME-VRAM-R1 ("VRAM optimization and resource-aware
Brain"). You did not write this work. Verify every claim against primary evidence. Do not trust the report's wording.

Repository: the git worktree `D:\uri-dev\uri-runtime-vram-r1`, branch `research/runtime-vram-r1-20261017`. Review the
head commit the owner gives you, against base `25048709`. Read first: `research/runtime_vram_r1/ACCEPTANCE_CRITERIA.md`,
then `research/runtime_vram_r1/RUNTIME_VRAM_R1_REPORT.md`.

Hard rules you must check:
1. Frozen Runtime v1 is unchanged: `git diff 25048709 -- model_lab/integration/local_brain.json
   model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` must be empty. For the frozen configuration,
   `runtime_v1.expected_argv` must give byte-identical output, and `runtime_profiles.derive_config(frozen, 32768,
   "gpu", True)` must return the same object.
2. Admission never runs on an estimate: every `MEASURED_MIB` entry must match `buffers.device_total_mib` of a
   `COMPLETED_WITH_RESULT` probe in `research/runtime_vram_r1/evidence/probe/*/probe.json`.
3. Evidence integrity: only `COMPLETED_WITH_RESULT` runs may support a positive claim. Several runs FAILED (harness
   errors: relative interpreter path, suite P identity check, a duplicate queue). Confirm the report discloses each
   one and uses none of them as support.
4. The D/DG explanation (finding CWD-1): with cwd = `research/runtime_vram_r1`, Core opens
   `uri_workspace\capabilities_registry.json` relative to the cwd and loads 2 capabilities instead of 17. Check this
   offline: build `scripts.m30_4_decision_quality_analysis.real_directory()` from both working directories and compare
   `len(summaries())`. Then confirm that the same-environment control `vr1_ctl_frozen_dgp` and the 64K reruns score
   D/DG 0.861 with 0 score-changing cases against `ue_cand_mtp2` (`research/runtime_vram_r1/compare_suite.py <run_dir>`).
5. Accuracy: for each candidate profile, list every score-changing case against the frozen baseline and judge whether
   any is a regression. The RH flips 0->1 also appear in the 2026-10-06 qualification (`ue_cand` vs `ue_cand_mtp2`).
6. Memory claims: check the demotion figures (device request vs process dedicated, non-local vs host-visible
   buffers) in `summary.json`, `coexist_summary.json` and the raw probe files. Note n=1 where it applies.
7. Code review of the candidate: correctness, tests (`python -m pytest tests/oi tests/ws -q -p no:cacheprovider`),
   whether the frozen path is preserved in `ws_brain_host.py`, and whether anything could silently substitute a
   profile for the frozen Brain.
8. The recommendation follows from the evidence, the limitations are stated, and nothing claims integration,
   deployment or qualification that did not happen.

Return exactly:
A. VERDICT: one of ACCEPT / ACCEPT WITH FINDINGS / REVISE / REJECT / BLOCKED, with the reviewed commit SHA.
B. FINDINGS: a numbered list. For each: severity (HIGH/MEDIUM/LOW), file:line or evidence path, what is wrong,
   and what would fix it.
C. CHECKS RUN: the commands you ran and their results. Say what you could not verify and why.
D. FOLLOW-UP PROMPT: a ready-to-paste message for the ORIGINAL URI-RUNTIME-VRAM-R1 session that states your verdict,
   lists the findings to repair (or that none remain), and says what evidence it must produce for a re-check.
---
