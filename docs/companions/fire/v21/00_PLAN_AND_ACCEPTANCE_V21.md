# Ember V2.1 - Plan, acceptance criteria and decisions

Milestone: URI Ember Companion - V2.1 Fidelity Refinement. Branch `phase/fire-companion-v21-20261015`, worktree
`C:\Users\cheta\Development\uri-fire-companion-v21`, cut from V2's final commit `b73bd26c`. Local only: nothing is
merged, pushed or deployed.

## Acceptance criteria (from the brief)

| ID | Criterion | Evidence |
|---|---|---|
| AC-F1 | >= 90 % calibrated visual fidelity in all four reference states (FP-21 section 7, qualification round) | `03_FIDELITY_PROTOCOL_V21.md`, `evidence/fidelity/` |
| AC-F2 | Animation not worse than V2 (FP-21 section 7) | same |
| AC-F3 | Character identity preserved in the four states (character % >= 90) | same |
| AC-P1 | GPU and VRAM overhead acceptable: GPU below Solar's, VRAM no worse than V2 | `05_MEASUREMENTS_V21.md` |
| AC-P2 | Real Brain coexistence measured under an exclusive, verified GPU lease | `05_MEASUREMENTS_V21.md`, `06_LIVE_QUALIFICATION_V21.md` |
| AC-L1 | Live Windows journeys with real Core and Brain, first-time and returning user | `06_LIVE_QUALIFICATION_V21.md` |
| AC-R1 | No regression: full Flutter suite, frozen-file integrity | `evidence/tests/` |
| AC-R2 | Independent whole-diff review, findings repaired and rechecked | `evidence/review/` |
| AC-R3 | Lifecycle acceptance of the exact final commit | BLOCKED while the Claude CLI is logged out |
| AC-S1 | Startup state designed; shared changes proposed, not implemented without approval | `04_STARTUP_PROPOSAL_V21.md` |
| AC-A1 | Reference art and derived assets stay local | git: nothing pushed |
| AC-T1..T7 | Transparency readiness (owner directive "URI UI V2 compatibility", 2026-10-15), Stage 1 | `07_UI_V2_COMPATIBILITY_V21.md` |
| AC-U | Final UI V2 integration compatibility, Stage 2 | PENDING until the accepted UI V2 candidate exists |

## Phases

1. Research and diagnosis: `01_DIAGNOSIS_V21.md`.
2. Fidelity protocol FP-21: `03_FIDELITY_PROTOCOL_V21.md` (written before P1, committed after P2: see change log C-4; changes C-1..C-4).
3. Visual refinement: textured backdrop and in-disc framing (`9933ca2b`).
4. Startup: `04_STARTUP_PROPOSAL_V21.md` (AMBER).
5. Performance: `05_MEASUREMENTS_V21.md`.
6. Live: `06_LIVE_QUALIFICATION_V21.md`.
7. Review: `evidence/review/`.

## Owner decisions in this milestone

- **OD-V21-1 (2026-10-15, owner answer in session):** the GPU override authorization from V2 (OD-8) extends to the
  V2.1 live runs "same terms as OD-8": `-OverrideGpu` may be used (it bypasses only the free-VRAM check), the GPU
  lease must be followed, only a Brain this run started may be used, and a lost lease means stop and record
  BLOCKED.

- **OD-V21-2 (2026-10-15, owner directive, MANDATORY):** "Ember V2.1 - URI UI V2 Compatibility". Ember must render
  with genuine alpha (no permanent opaque background, no visible boundary), adapt to UI V2's companion architecture
  without UI V2 changing for it, and keep separate qualification records: A (visual and functional), B
  (transparency readiness), C (final UI V2 integration, deferred). The painted backdrop is approved for
  experimentation only. Ember may be proposed for canonical integration only when every Stage 3 condition is met.

## Boundaries kept

- No Dart file under `uri_ui/lib` changed. New test: `uri_ui/test/living/ember_transparency_test.dart`. Runtime code, Core and Runtime v1 untouched. The shared companion host
  (`living_companion.dart`, `companion_presence.dart`) unchanged.
- Reference art: as in V2, the reference sheet and derived images are in this branch's local history only.
