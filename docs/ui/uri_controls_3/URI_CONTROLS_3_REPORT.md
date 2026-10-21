# URI-CONTROLS-3 - Thinking, Vision, URI Assist quick controls: implementation record

Branch `milestone/uri-controls-3-20261021`, worktree `D:\uri-dev\uri-controls-3`. Base: Ember V2.1 candidate
`68061d85` (itself on canonical `ec2fab54`), merged with the UI Controls & Typography candidate `e9ee7409` at
`5f9e5cc6` (clean merge). Owner decision 2026-10-21: "CONDITIONALLY APPROVED FOR INTEGRATION"; the final UI must
contain exactly three independently switchable ON/OFF controls (Thinking, Vision, URI Assist), Context replaced by
URI Assist, accessibility finding R1-01 repaired, one independent review of the final exact commit.

This file is the record. Review records, gate logs and live evidence are listed in section 6; the sections are kept
up to date by the commits that add evidence (history is never rewritten; corrections are added as dated notes).

## 1. Acceptance criteria (written before the repair)

| ID | Criterion |
|---|---|
| AC1 | The quick controls under the chat box are exactly three ON/OFF toggles, in this order: Thinking, Vision, URI Assist. No Context selection, Draft chip, Thinking Auto menu or second Depth picker remains in the UI. |
| AC2 | Each toggle operates its function, not only a visual: Thinking = the turn depth sent to the worker (Off = fast, On = normal); Vision = a qualified Brain profile reconfigure through the worker after a confirmation; URI Assist = the worker's Assist session (On opens the consent view and never grants by itself; Off revokes at once). |
| AC3 | The shown state is the runtime's: Vision glows only for the worker-verified profile; URI Assist only while the worker reports a grant; loading and unavailable states are shown with the reason. |
| AC4 | Permissions (Assist consent model) and GPU/VRAM rules (qualified catalog, fit refusal before anything stops, restore after a failed start) are unchanged. |
| AC5 | The conversation and session stay across a Brain switch, an Assist on/off and a worker restart (as before). |
| AC6 | R1-01: every toggle is reachable by Tab, switched by Enter and Space, shows a focus ring, keeps focus while loading, and is a toggle button with label, state and a tap action for screen readers. |
| AC7 | After a restart the toggles are consistent and responsive: Thinking is stored (`uri.living.thinking`) and restored; Vision follows the host's profile; URI Assist starts off after a worker restart (by design). |
| AC8 | No unrelated change, no new dependency; frozen-check clean; R1-02..R1-06 handled truthfully. |
| AC9 | Focused widget and Python tests cover the above; full suites, analyzer, release build pass; live run on the real Brain. |

## 2. What changed (code)

| Commit | Change |
|---|---|
| `5f9e5cc6` | merge of `e9ee7409` (UI Controls & Typography: push-to-enable toggles, one type system, host restore after a failed switch) |
| `0d77a015` | the R1 review record committed (was untracked; same SHA-256 as the P0 preserved copy) |
| `d1388d8c` | three toggles (Context and Draft removed, Thinking On/Off only, default Off, stored), URI Assist toggle, accessible `QcToggle` (FocusableActionDetector + Semantics), `QcSegmented` removed; R1-03 notice, R1-04 superseded-restore record (`ws_brain_host.py`), R1-05 wording, R1-06 dialog clause, R1-02 count |
| `708500fd` | formatting restored in `QcStyle`, non-deprecated semantics matchers, live driver |
| `abdfaa26` | R2 repairs: worker is the Assist authority (R2-01), Depth dropdown removed from the conversation pane (R2-02), focus kept while loading (R2-03), no Assist loading look (R2-04), tests (R2-05), unreadable Assist state is "unknown" (R2-06) |
| `b774bb85` | R3 repairs: the worker's Assist reading is trusted only while a worker is connected; a disagreement re-reads the Assist status at most once per health reading (R3-01); this record (R3-06) |
| `a87ee0a1` | R4 repairs: of the two worker readings (Assist status, brain health) the newer wins, by timestamps `AssistController.statusAt` / `OiConversation.brainHealthAt` (R4-01: a grant shows at once, also during a turn); only a newer health reading triggers a re-read (no ping-pong); the test fake returns a fresh Map per reading and the test asserts exactly one re-read per reading (R4-03). R4-02: a new worker resets the Assist mirror with a newer timestamp, so the old worker's health reading never wins |

Files: `uri_ui/lib/living/integration/{brain_quick_controls,qc_toggle,oi_conversation,oi_widgets}.dart`,
`uri_ui/lib/living/{living_app,widgets/living_composer}.dart`, `scripts/ws_brain_host.py`,
`uri_operational_intelligence/worker_bridge.py`, tests under `uri_ui/test/living/` and `tests/oi/`.

## 3. Design decisions and consequences (disclosed; owner may change)

| ID | Item |
|---|---|
| D-1 | Thinking default is **Off** (fast); the previous default was Auto (policy). On = the qualified NORMAL tier (768-token thinking budget). One line to change (`OiConversation.depth`). Owner preference item, not a defect. |
| D-2 | With Context and Draft gone, **Long context (64K)** is reachable only by Vision Off (the catalog couples them), and **Standard, draft off (P3)** cannot be chosen from the UI; it is still started by the host flag `--profile 32768,gpu,0`. From P3, Vision Off then On lands on Standard (about 1.2 GB more GPU memory). |
| D-3 | URI Assist On opens the Assist view (the consent step). It glows only after the user grants a target there. Paused shows as On with "Paused"; a click stops it (not resume). |
| D-4 | While URI Assist holds a grant, Vision cannot be turned off (closure D2/D6 interlock, kept). |
| D-5 | Assist perception: every perception adapter in canonical is a refusing placeholder (P0 finding D14), so a grant may be impossible on this build; the toggle then stays off and says why. Out of scope here (roadmap P9). |

## 4. Findings handled

R1 (on `e9ee7409`): R1-01 MEDIUM fixed (`d1388d8c`, `abdfaa26`); R1-02..R1-06 fixed; R1-07 noted in `SUCCESSOR.md`;
R1-08 INFO unchanged (literal-only typography guard).
R2 (on `d1388d8c`, REVISE): R2-01..R2-08 repaired in `abdfaa26`; R2-09/R2-10 are D-2/D-1/D-3 above.
R3 (on `abdfaa26`, REVISE): R3-01 MEDIUM and R3-06 repaired in `b774bb85`.
R4 (on `b774bb85`, REVISE): R4-01 MEDIUM, R4-02 LOW, R4-03 LOW, R4-04 INFO repaired in `a87ee0a1` and this record. R3-02 resolved in `b774bb85` (the
resync guard is per health reading; confirmed by R4). Open LOW: R3-03 (an unreadable Assist state leaves Vision unlocked, unchanged behaviour),
R3-04 (focus can drop when loading ends in a disabled state), R3-05 INFO (diagnostics wording).

## 5. Gates

| Commit | pytest `tests/oi tests/ws` | flutter test | analyze | release build | `ws_frozen_check` |
|---|---|---|---|---|---|
| `d1388d8c` | 807 passed, 23 skipped | 874 passed, 5 skipped | 10 info (5 new, removed in `708500fd`) | rc 0 | `[]` |
| `abdfaa26` | 807 passed, 23 skipped | 879 passed, 5 skipped | 5 info (baseline) | rc 0 | `[]` |
| `b774bb85` | 807 passed, 23 skipped | 881 passed, 5 skipped | 5 info (baseline) | rc 0 | `[]` |
| `1741e97e` | 807 passed, 23 skipped | 882 passed, 5 skipped | 5 info (baseline) | rc 0 | `[]` |

Logs: `D:\uri-dev\lifecycle\URI-CONTROLS-3\gates_<commit>\` (outside git; head.txt records HEAD and a clean tree).

## 6. Evidence index

| Item | Where |
|---|---|
| R1 review | `docs/ui/controls_typography_20261018/review/R1_report.md` |
| R2, R3, R4 reviews (fresh read-only subagents) | `docs/ui/uri_controls_3/review/` (copies of `D:\uri-dev\lifecycle\URI-CONTROLS-3\review_R*.md`) |
| Live driver | `docs/ui/uri_controls_3/live_harness/controls3_driver.dart` |
| Live runs | NOT RUN (BLOCKED). Attempt 2026-10-21 17:07-17:43Z, chain `D:\uri-dev\uri-controls-live\chain_c3.sh` (runtime `D:\uri-dev\uri-controls-live\runtime` materialised from `abdfaa26`, Python identical at `1741e97e`; installation `c3`, port 18360; P3 profile): the production Brain host waited in WAITING_FOR_GPU for 35 min (GPU_CONTENDED, fit -1066 MiB; desktop `dwm.exe` 1.77 GB), so no Brain started; stopped with the harness stop file. Earlier Ember attempt 16:27-17:05Z: same cause. No live result exists (NO_OUTPUT; nothing is counted as evidence). |
| Gates at the reviewed commit | `1741e97e`: pytest 807 passed / 23 skipped; flutter 882 passed / 5 skipped; analyze 5 info (baseline); release build rc 0; `ws_frozen_check` clean |
| Final review | R5 on `1741e97e` (code = `a87ee0a1`): ACCEPT WITH FINDINGS (R5-01 LOW wall-clock ordering of the two Assist readings; R5-02 LOW Vision-off offered up to one poll after a fresh grant, refused by the worker with ASSIST_NEEDS_VISION; R5-03 INFO docs). `docs/ui/uri_controls_3/review/review_R5_1741e97e.md` |

## 7. Status (2026-10-21)

**ACCEPTED (R5 ACCEPT WITH FINDINGS) - NOT INTEGRATED.** Blocker: the Lifecycle V3 Stage 8 live Windows UI
qualification (canonical policy DEV-LIFECYCLE-3, UI-first) has no result on this code because the GPU was contended
for the whole session. Next step: in a free GPU window run `bash D:/uri-dev/uri-controls-live/chain_c3.sh` (remove the
`stop-session` files under `D:\uri-dev\uri-controls-live\live\c3-*` first, or use new labels), check
`observations.json` of `c3-1` (driver `controls3_driver.dart`) and the UI V2 main / returning / perf runs, then merge
canonical `9488c0fd` (docs only since `68061d85`) and integrate. Open LOW: R3-03, R3-04, R5-01, R5-02; INFO R3-05, R5-03.
