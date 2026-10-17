# URI-RUNTIME-VRAM-R1 — VRAM optimization and resource-aware Brain (final report)

Date 2026-10-17. Branch `research/runtime-vram-r1-20261017`, worktree `D:\uri-dev\uri-runtime-vram-r1`, base
canonical `25048709`. Acceptance criteria were written before measurement: `ACCEPTANCE_CRITERIA.md`. This report
includes the two owner additions of the same day: mutually exclusive Vision / MTP allocation, and the resume
directive.

**Status: RESEARCH COMPLETE, REVISED AFTER INDEPENDENT AUDIT (REVISE on c79ae681; repairs in section 14). CANDIDATE NOT QUALIFIED FOR INTEGRATION. RE-CHECK PENDING.** Nothing is
merged, deployed or frozen. Frozen Runtime v1 is untouched: `git diff 25048709 --
model_lab/integration/local_brain.json model_lab/URI_RESIDENT_INTELLIGENCE_RUNTIME_V1_FREEZE.md` is empty. In every
profile the model, quantization, binary, KV type (q8_0), batch sizes and checkpoint flags are the frozen ones. Only
`-c`, the vision projector placement and the MTP draft vary.

Reopening basis (freeze record section 14): "an unacceptable stability problem under realistic use". The frozen
Brain could not start on the ordinary desktop. That blocked the UI V2 and Office live qualifications.

Units are MiB. "Request" = the sum of llama-server's own `Vulkan0 ... buffer size` lines, including the vision
projector weights. "Dedicated" / "non-local" = the Windows per-process GPU counters. "Demoted" (estimate) = the
process's non-local GPU usage minus its host-visible (`Vulkan_Host`) buffers. Plain CPU buffers (for example the vision
projector with `--no-mmproj-offload`) are not GPU memory and are reported separately (corrected after audit finding 6). Desktop during all tests: about 1,296 MiB used by other
processes (dwm 804, ChatGPT 103, Claude 62, Edge WebView 62, Edge 44, ...), so 15,072 MiB was free for one process.
Evidence: `research/runtime_vram_r1/evidence/` (`summary.json`, `summary_table.md`, `coexist_summary.json`, per-run
folders). Suite runs are in `model_lab/evidence/runs/vr1_*` and `evidence/suite_p/`.

## 1. Root cause of GPU memory pressure (AC1)

1. **The frozen Brain requests 15,620.5 MiB of device memory** (re-measured; the lease constant is 15,626). The card
   offers about 15,072 MiB to one process on this desktop. That leaves about 550 MiB that cannot be resident.
2. **Which buffers become non-resident decides the outcome.** In today's frozen-equivalent load about 883 MiB of
   device memory was non-local (non-local 1,732 minus host-visible 848.9). That is consistent with the vision
   projector weights (857.6) plus part of the CLIP buffers being the non-resident part: text was unaffected and only
   image encode slowed. This is an inference from the counters, not a direct observation of which buffer moved. Text decode stayed at 108 / 141 tok/s, but image
   encode slowed to 1.4-2.0 s (0.51-0.53 s when vision is resident). When the driver demotes MoE weight blocks
   instead (Adaptive Runtime R1, the Office r7 record, and 128K+MTP today: 943 MiB demoted, 23 / 31 tok/s), decode
   collapses by 60-80% for the life of the process. Placement is not controllable, so a 15.6 GiB request on this
   desktop is a gamble. The lease's CONTENDED refusal is correct as a safety rule, even though today's
   frozen-equivalent load happened to land well.
3. **Reconciliation of earlier reports.** The Qwen3.8 experiment's "frozen-equivalent request 14,915" left out the
   projector weights: its parser did not read `load_hparams: model size` and counted a re-reserved draft compute
   buffer twice. The corrected figure is 15,620.5. Its statement "no demotion up to a 14,915 MiB request" therefore
   referred to a 15.6 GiB request with the vision weights non-resident.
4. **Process residency is about 160-220 MiB above the request** (driver overhead). Other processes can yield memory,
   so a request slightly above "free" can still be fully resident at load. 64K+MTP: 15,043 request, 15,260
   resident. Later pressure then evicts from the Brain (section 7).
5. **Host RAM is a second pressure point (finding RAM-1).** Two PowerShell processes belonging to other Claude
   sessions held 3.5-4.0 GB each. During one load, available system memory fell to 570 MiB (24 GB machine). I did not
   touch them. The lab harness now refuses a load below 3,000 MiB available.

## 2. VRAM allocation breakdown (AC2)

Frozen profile (32K, MTP, vision GPU), from the server log:

| Component | Device MiB | Host-visible MiB |
|---|---|---|
| Main weights | 12,634.8 | 397.9 |
| Main KV (q8_0, 32K) | 340.0 | — |
| Main recurrent state | 188.4 (62.8 without MTP) | — |
| Main compute | 216.3 | 96.3 |
| MTP draft weights | 919.2 | 272.8 |
| MTP draft KV (f16) / compute | 64.0 / 152.0 | 80.0 |
| Vision weights / compute | 857.6 / 248.1 | — |
| **Total** | **15,620.5** | **873.8** |

The cost of each add-on depends on context: MTP adds 1,213 (16K), 1,261 (32K), 1,385 (64K) and 1,641 MiB (128K),
including the draft KV and the larger recurrent state. Vision on the GPU adds 1,106 at every context. Main KV costs
10.6 MiB per 1K tokens. Draft KV in q8_0 saves only 60 MiB at 64K (measured), with no speed change.

## 3. Profile comparison and compatibility matrix (AC3, AC4)

Free on this desktop: 15,072. Margin = free − request. The lease verdict uses the existing rule: CONTENDED at
≤ −512, AT_RISK below +512, otherwise FITS. Decode was measured with three requests each.

| Profile | Request | Margin / verdict | Measured residency | Decode prose / URI-JSON | Load s | Vision encode |
|---|---|---|---|---|---|---|
| 16K main only | 13,052 | +2,020 FITS | resident | 106.7 / 104.4 | 13.8 | — |
| 32K main only | 13,254 | +1,818 FITS | resident | 106.3 / 104.0 | 14.3 | — |
| **64K main only** | **13,658** | **+1,414 FITS** | resident | 105.5 / 103.6 | 17.2 | — |
| 128K main only | 14,466 | +606 FITS | resident | 106.3 / 104.5 | 14.5 | — |
| 16K + MTP | 14,265 | +807 FITS | resident | 109.5 / 143.2 | 17.7 | — |
| 32K + MTP | 14,515 | +557 FITS | resident | 107.1 / 139.9 | 28.3 | — |
| 64K + MTP | 15,043 | +29 AT_RISK | resident at load | 107.5 / 141.7 | 20.2 | — |
| 128K + MTP | 16,107 | −1,035 CONTENDED | **943 demoted at load** | **22.6 / 30.5** | 17.6 | — |
| 32K + vision GPU | 14,360 | +712 FITS | resident | 106.4 / 104.5 | 17.9 | 0.51 s |
| 64K + vision GPU | 14,764 | +308 AT_RISK | resident | 106.4 / 104.3 | 17.6 | 0.53 s |
| 128K + vision GPU | 15,572 | −500 AT_RISK | ~253 demoted (vision slowed) | 106.3 / 104.1 | 23.2 | 1.46 s |
| 64K + MTP + vision CPU | 15,043 | +29 AT_RISK | resident | 107.8 / 142.7 | 22.9 | 4.22 s (CPU) |
| Frozen 32K + MTP + vision GPU | 15,621 | −549 CONTENDED | ~883 demoted (vision slowed) | 107.6 / 141.1 | 20-26 | 1.39-2.02 s |

Not measured: main only + vision CPU at any context. That profile is therefore not selectable in the candidate,
because admission never runs on an estimate.

## 4. MTP: is ~1.1-1.4 GiB justified? (owner addition, AC5)

Paired test at 64K: identical prompts, alternating order A B B A, same runtime conditions
(`evidence/mtp_pair/20261017-081619_64k`):

| Work | Decode on / off | Wall on / off | Wall saving |
|---|---|---|---|
| Prose (300 words) | 107.5 / 105.3 | 4.23 / 4.25 s | 0% |
| URI decision JSON | 141.3 / 102.8 | 2.07 / 2.37 s | 13% |
| Code | 147.6 / 105.2 | 3.85 / 5.20 s | 26% |
| Office edit JSON | 153.9 / 105.1 | 1.67 / 2.25 s | 26% |
| Table extraction | 136.8 / 105.3 | 4.65 / 6.07 s | 23% |
| Reasoning, thinking on | 141.8 / 105.3 | 10.46 / 15.58 s | 33% |
| 24K-token prompt, short answer | 132.1 / 93.7 | 14.55 / 14.13 s | −3% (prefill 1,876 vs 2,028 tok/s) |

On URI's own 271-case suite (2026-10-06 frozen qualification, `ue_cand` vs `ue_cand_mtp2`), the end-to-end wall time
is 610 s with MTP and 712 s without (−14%). Decision turns take 2.22 vs 2.57 s. Scores are identical. MTP also costs
7-16% of prefill speed. MTP is lossless: every suite score in this milestone was identical with it on and off.

**Verdict:** MTP has a real but moderate benefit: 13-33% faster generation-heavy turns, about 14% end to end, nothing
on prose, slightly slower on long-prompt turns. On this 16 GB card it does not justify its residency as the default
at 64K, where it consumes the whole safety margin. Section 7 measures what happens then: a sticky −67%. It does fit
at 16-32K with a 557-807 MiB margin.

## 5. Vision and MTP: mutual exclusion and switching (owner addition, AC6, AC9)

- **Selective unloading is not supported** in llama.cpp b11425. The server DLL exposes only `/models`, `/models/load`
  and `/models/unload` (router mode: the whole model), plus `/slots` and `/lora-adapters`. There is no endpoint for
  the projector or the draft alone. Vision cannot replace MTP residency without reloading the main weights.
- **Controlled profile switch** (`evidence/switch/20261017-082155`): stop, VRAM release 3.8-3.9 s, load 16.4-17.0 s.
  Stop to ready took 39.4-39.5 s in the lab harness (census overhead included). The real Brain host restart
  measured 29.1 s to READY, including calibration (section 8).
- **KV / conversation preservation.** The conversation is always preserved: URI keeps the history, and follow-ups
  after each switch answered correctly. The KV state is not preserved. Slot save (0.3-0.5 s, 288 MB for 20K tokens)
  and restore (1.9 s) work mechanically, but on this hybrid model the restored state was reused for 0 tokens. The
  prompt was re-processed: 9.7-10.6 s for 20K tokens, about 45-49 s for a full 64K. A slot that holds image tokens
  cannot be restored into a profile without the projector (`Cannot restore media tokens without an mmproj`). The
  checkpoint-and-recovery design for this is recorded as a future Lifecycle V3.1 enhancement
  (`LIFECYCLE_V3_1_CHECKPOINT_RECOVERY_PROPOSAL.md`). It is not implemented here.
- **Vision accuracy and latency.** Suite V on 64K + vision GPU scored 0.733 (VLM 1.000, OCR path 0.467), identical to
  the frozen baseline. Image encode: 0.51-0.53 s with vision resident, 1.4-2.0 s in the frozen profile (vision
  weights non-resident), 4.2 s on the CPU.

## 6. Accuracy (AC8): no loss measured

Baseline: the frozen qualification run `ue_cand_mtp2` (2026-10-06). The comparison is case by case
(`compare_suite.py`; the output is saved as `compare_vs_ue_cand_mtp2.json` / `.txt` in each run folder). **Only the
runs below support the accuracy claims.** Each ended with rc=0, classification `COMPLETED_WITH_RESULT` and a
`summary.json`. Each was started from the repo root, without suite P.

| Suite | Frozen-equivalent control `vr1r2_ctl_frozen_dg/20261017-111219` | 64K main only `vr1r2_c64k_mtpoff/20261017-111826` | 64K + MTP `vr1r2_c64k_mtpon/20261017-113004` |
|---|---|---|---|
| D / DG (72 + 72) | 0.861 / 0.861, 0 of 144 changed | 0.861 / 0.861, 0 changed | 0.861 / 0.861, 0 changed |
| F, C, H, S, O, R, L | — | identical (1.0, 1.0, 1.0, 1.0, 1.0, 0.958, 0.933) | identical |
| RH (8 hard, capped) | — | 0.875 (rh4_rooms, rh7_dates: 0→1) | 0.625, 0 changed |
| Cases compared / changed | 144 / 0 | 249 / 2 (both RH, upward) | 249 / 0 |

`with_profile` records: `20261017-111138_r2-ctl-frozen-dg`, `20261017-111752_r2-c64k-mtpoff`,
`20261017-112928_r2-c64k-mtpon`, all rc=0 and `COMPLETED_WITH_RESULT`. The two RH changes are improvements only. The
same two flips appear between `ue_cand` and `ue_cand_mtp2` in the 2026-10-06 qualification (known run variance).

Suite P (12 cases, Phase 1 production loop) has to run from a checkout at `e8e3b652`
(`runtime_identity.BASELINE`). It ran through `with_profile` with `--cwd D:\uri-dev\uri-vram-r1-p1`. Records
`20261017-100505_p-frozen`, `20261017-100746_p-c64k-mtpoff`, `20261017-101028_p-c64k-mtpon`: rc=0, `COMPLETED_WITH_RESULT`, 12/12 each, 0 errors,
0 invalid proposer outputs. Summaries are in `evidence/suite_p/vr1_p_*`.

Long context, full 64K fill (11 checks + same-prefix follow-up), main only:
`evidence/longctx/20261017-113930/r2-lc-mtpoff-q36-64k-q8_0/longctx.json`, `COMPLETED_WITH_RESULT`, 64,093 prompt
tokens, 11/11, follow-up correct, prefill 1,437 tok/s, TTFT 44.9 s, decode at depth 81.8 tok/s, follow-up TTFT 0.92 s
(cache reuse). The earlier long-context runs `evidence/longctx/20261017-090223` (main only) and `20261017-090357`
(MTP) carry classification `STARTED`, because the script did not set a final class (audit finding 2). They completed,
with 11/11 in their records, but they are **reclassified as supporting-only**. The MTP long-context figures
(11/11, prefill 1,326 tok/s, TTFT 48.7 s, decode at depth 113.1 tok/s) come from `20261017-090357` and are
supporting-only. The script now sets `COMPLETED_WITH_RESULT`
/ `FAILED`.

Vision accuracy: suite V on 64K + vision GPU (`vr1_c64k_vis/20261017-090207`, `with_profile` `20261017-090129`,
rc=0, `COMPLETED_WITH_RESULT`): 0.733 (VLM 1.000, OCR path 0.467), identical to the baseline.

**The D/DG discrepancy (0.861 -> 0.486) is explained (finding CWD-1).** My first suite runs started `run_bench.py`
from `research/runtime_vram_r1`. Core opens `uri_workspace\capabilities_registry.json` relative to the current
working directory. From that folder the decision prompt held 2 capability summaries instead of 17: `remember_fact`,
`recall_memory`, drafting and convert were missing. This was verified offline (`real_directory().summaries()`: 2 vs
17; the prompt was 2,653 chars shorter, which matches the 590-token gap), and the independent auditor reproduced it.
Re-run from the repo root, every profile scores 0.861 / 0.861 with 0 score-changing cases. The runtime was never the
cause. CWD-1 is a latent Core fragility (any caller with another working directory silently loses capabilities). It
is reported for a separate fix and not changed here.

**Superseded runs (kept, not used as support), with the correction:**
- `vr1_c64k_mtpoff/20261017-084215` and `vr1_c64k_mtpon/20261017-085302` (`with_profile` `084140`, `085225`, FAILED
  rc=1): D/DG ran from the wrong cwd (CWD-1), and suite P crashed (`ISOLATED_INTERPRETER_REQUIRED`). In c79ae681 the
  report cited their non-D suites as support; that was incorrect under the evidence rule. They are replaced by the
  `vr1r2_*` runs above.
- `vr1_ctl_frozen_dgp`, `vr1_c64k_mtpoff_dgp`, `vr1_c64k_mtpon_dgp` (`with_profile` `093842`, `094455`, `095151`,
  FAILED rc=1, P crashed with `SOURCE_CHECKPOINT_MISMATCH`): c79ae681 cited their D/DG results. Their D/DG rows agree
  with the reruns, but they are not used as support. They are replaced by `vr1r2_*`.

## 7. Coexistence: URI UI + Chrome (AC11)

The Brain was loaded first. Then the URI UI window was opened: a canonical release build with no manifest, so it
shows its start screen and uses only 54-75 MiB. This is a GPU-consumer proxy, not a real-app run. Then an isolated
Chrome with 6 tabs (YouTube, WebGL, satellite map, GitHub, Wikipedia, docs; 549-600 MiB) was opened, and finally
both were closed. One run per profile. Your `uri_ui` preferences file was hashed before and after and was unchanged.

| Profile | Brain dedicated / non-local, desktop → +UI → +Chrome → closed | URI-JSON decode |
|---|---|---|
| 64K main only | 13,859 / 562 throughout | 103 → 101 → 100 → 104 |
| 64K + vision GPU | 14,968 / 562 throughout | 103 → 102 → 101 → 105 |
| 32K + MTP | 14,730 / 872 throughout | 135 → 137 → 137 → 137 |
| Frozen (32K + MTP + vision) | 14,981 / 1,730 throughout (vision already non-resident) | 136 → 137 → 136 → 137 |
| **64K + MTP** | 15,260 / 1,000 → **14,238 / 2,022 after Chrome, stays after close** | 134 → 138 → **44 → 45** |

64K + MTP has no headroom. An ordinary browser took 1,022 MiB from the Brain, and the slowdown persisted after
everything closed (sticky, as R1 found). The real URI app uses about 300 MiB more than the proxy (median 298 MiB
across 509 earlier canonical samples), so real margins are smaller than this table shows.

## 8. Startup and recovery: the real Brain host with a profile (AC9, AC10)

`scripts/ws_brain_host.py --profile 65536,off,0` (production host code, port 18470, the lease and the request file),
`evidence/host_live/20261017-095801_65536_off_0`:

- start: READY after 51.1 s (first full artifact hash plus load); lease `expected_vram_mib` 13,658; fit **FITS,
  +1,324 MiB** (free 14,982). The frozen config, measured by the same host on the same desktop with its own fit
  function (`evidence/frozen_fit/20261017-114127/frozen_fit.json`): CONTENDED, free 14,981.8, required 15,626, margin
  **−644.2**. The host waited with `GPU_CONTENDED`, started nothing, and exited 0. (c79ae681 said "−554" without an
  evidence file; corrected.) Calibration 106.3 tok/s; residency 13,832 /
  562, no demotion;
- restart request (recovery): back to READY in 29.1 s, release 3.8 s, calibration 105.3 tok/s;
- stop request: STOPPED in 1.0 s; host exit 0; lease FREE afterwards.

## 9. Thinking (AC7)

These are per-request settings on the running server, with no reload (verified):
- thinking off: 0 reasoning, answer "7/10";
- on with budget 768: 2,184 chars of reasoning, answer "7/10";
- on with budget 64: reasoning stopped at the budget, but the final answer was cut off mid-way ("... = 7/") with
  finish_reason `stop` (finding THINK-1).

The candidate maps the UI's Thinking Off / On to the existing turn `depth` fast / normal (normal = the qualified
768-token budget). No new capability is simulated.

## 10. Resource-aware runtime candidate and UI contract (AC10)

- `uri_operational_intelligence/runtime_profiles.py`: in-memory profiles derived from the frozen config. The frozen
  combination returns the frozen object itself. `MEASURED_MIB` holds only the measured requests above. Also
  `plan_change` (refuses to shrink the context below the live conversation without confirmation) and
  `thinking_depth`.
- `runtime_v1.expected_argv`: +3 lines (`--no-mmproj-offload` only when a derived config sets
  `vision_offload: false`).
- `scripts/ws_brain_host.py`: the lease and the contention check use the profile's measured request; `--profile`;
  `profile` in the report. With no `--profile`, behaviour is unchanged.
- Tests: `tests/oi/test_runtime_profiles.py`, 10 passed. `tests/oi` + `tests/ws`: 708 passed, 22 skipped.
- UI contract: `docs/operational_intelligence/RUNTIME_PROFILES_UI_CONTRACT.md`. Thinking = per turn. Vision and
  Context = controlled reload with a fit check. MTP is a profile property, not a UI control. The host `reconfigure`
  action is deliberately not wired yet.

## 11. Recommendation

**Daily default (candidate): Qwen3.6 Runtime v1 at 64K context, Main Brain only (MTP off, vision off).**
- It is the simplest configuration and the one with the most headroom: request 13,658, FITS with +1,414 MiB on
  today's desktop. It stayed fully resident with the URI UI and Chrome open.
- Accuracy is the same as the frozen baseline on D, DG, P, F, C, H, S, O, R and L, plus the full 64K long-context
  fill.
- Speed is 104-106 tok/s, with faster prefill than MTP profiles.
- The cost: generation-heavy turns are 13-33% slower than with MTP, and the URI suite about 14% slower end to end.

**Can 64K become the default?** Yes, for the main-only profile on this evidence, subject to independent audit, the
remaining checks in section 12 and owner approval. Not with MTP or vision resident at the same time.

**Interaction of the controls:**
- Thinking Off / On: per turn, no reload.
- Vision On: reload into 64K + vision GPU (14,764, AT_RISK +308 today, survived the UI + Chrome test once). Vision
  Off: reload back to the default. Each switch costs about 25-30 s plus re-prefill of the conversation (about 10 s
  per 20K tokens). URI keeps the history.
- Context 16K / 32K / 64K / 128K: reload with the fit check. 128K is offered main only (14,466, +606). 128K + vision
  is AT_RISK, with the vision weights partly demoted. 128K + MTP is never allowed.
- MTP: an optional, owner-enabled speed profile at 32K (14,515, +557; survived the coexistence test once). Not the
  default. 64K + MTP is rejected for daily use (sticky demotion measured).
- Frozen Runtime v1 (32K + MTP + vision) stays the verified fallback, unchanged. It starts when the lease fit allows
  it.

## 12. Limitations and what is not verified

- Coexistence and switch tests are single samples (n=1). There was no soak test.
- The UI in the coexistence test is a start-screen proxy (54-75 MiB), not the real app with a Brain session. A real
  URI app run with the 64K main-only profile (UI V2 journeys) has not been done.
- No physical owner use. The desktop composition varies: dwm 804-912 MiB during the tests.
- Main only + vision CPU is not measured, so it is not selectable. The 128K main-only long-context accuracy was not
  re-run here (the Qwen3.8 experiment measured 10/11 at 128K).
- THINK-1 (small thinking budgets can cut off the answer), CWD-1 (cwd-dependent capability registry) and RAM-1
  (other sessions' PowerShell memory) are open findings outside this milestone's scope.
- Failed or invalid runs (every one listed; none is used as support):

  | Run directory (`research/runtime_vram_r1/evidence/...`) | Class | Exact error |
  |---|---|---|
  | `with_profile/20261017-084140_suite-c64k-mtpoff` | FAILED rc=1 | suite P: `RuntimeIdentityError: ISOLATED_INTERPRETER_REQUIRED` (system Python). D/DG also from the wrong cwd (CWD-1) |
  | `with_profile/20261017-085225_suite-c64k-mtpon` | FAILED rc=1 | same as above |
  | `with_profile/20261017-093712_ctl-frozen-dgp` | FAILED | `FileNotFoundError: [WinError 2] The system cannot find the file specified` (relative `.venv` interpreter path with `cwd=`) |
  | `with_profile/20261017-093751_dgp-c64k-mtpoff` | FAILED | same as above |
  | `with_profile/20261017-093842_ctl-frozen-dgp` | FAILED rc=1 | suite P: `RuntimeIdentityError: SOURCE_CHECKPOINT_MISMATCH` (HEAD is not `e8e3b652`) |
  | `with_profile/20261017-094455_dgp-c64k-mtpoff` | FAILED rc=1 | same as above |
  | `with_profile/20261017-095151_dgp-c64k-mtpon` | FAILED rc=1 | same as above |
  | `with_profile/20261017-095934_p-frozen` | FAILED rc=1 | `ModuleNotFoundError: No module named 'test_c5_intent_discovery'` (Phase 1 overlay not yet copied) |
  | `with_profile/20261017-100019_p-c64k-mtpoff` | FAILED rc=1 | same as above |
  | `with_profile/20261017-100059_p-c64k-mtpon` | FAILED rc=1 | same as above |
  | `coexist/20261017-090542_co-c64k-vis` | FAILED | `GpuBusy: GPU_LEASE_HELD` (my duplicate chain-4 instance held the lease) |
  | `coexist/20261017-090558_co-c32k-vis` | FAILED | `RuntimeError: REFUSED_OTHER_LLAMA_SERVER_RUNNING [17028]` (the duplicate instance's server) |
  | `coexist/20261017-090614_co-c64k-mtpoff-r2` | FAILED | same as above |
  | `longctx/20261017-090223/*`, `longctx/20261017-090357/*` | STARTED (never set) | no error; reclassified as supporting-only (section 6) |
  | `suite_p/vr1_p_dryrun` | dry run | deliberate run with no Brain (`--url http://127.0.0.1:9`); expected failures |

  Queue logs: `chain5_attempt1_relpath_failed.log` and `chain6_attempt1_missing_phase1_overlay.log`.
- Probe argv differs from the frozen argv in three disclosed ways: (1) the lab port 18572 instead of 18470; (2)
  `--metrics -lv 4` appended for logging and buffer accounting; (3) model, projector and MTP paths given as their
  real NVMe locations `C:\uri-model-lab\...` instead of the frozen `D:\uri-model-lab\...` paths, which are directory
  junctions to the same files (sha256 checked on 2026-10-15, see memory `brain-model-on-ssd-junction`). All other
  flags and their order match `runtime_v1.expected_argv`. The live host check (section 8) used the exact
  production argv derivation on port 18470.
- Suite P runs only from a checkout at the Phase 1 baseline `e8e3b652`. I used my own detached worktree
  `D:\uri-dev\uri-vram-r1-p1` with a byte-identical overlay of the 187 modified/untracked files of the original
  Phase 1 research worktree (list in `evidence/suite_p/PHASE1_OVERLAY_FILES.txt`, all `cmp`-equal). The original
  worktree was not touched.

## 13. Independent review status

Round 1 (independent external reviewer, commit `c79ae681`): **REVISE**. It confirmed: the frozen diff is empty, the
frozen argv is byte-identical, `derive_config` returns the frozen object, CWD-1 reproduces, the D/DG reruns show 0
changed cases, the RH flips match the 2026-10-06 qualification, the memory figures match the evidence, there is no
silent substitution path, and the tests pass. It required seven repairs; section 14 records how each was handled.
Round 2 (re-check of the repair commit): PENDING. Integration needs independent acceptance and owner approval.
Neither has happened.

## 14. Correction log (audit round 1 -> repair)

The original text is kept in git history (`c79ae681`). Each correction is listed here instead of being overwritten
silently.

| # | Severity | Finding | Repair |
|---|---|---|---|
| 1 | HIGH | Accuracy claims cited `with_profile` runs classified FAILED (rc=1, suite P crash) | Re-ran from the repo root without P: `vr1r2_ctl_frozen_dg` (D,DG), `vr1r2_c64k_mtpoff` and `vr1r2_c64k_mtpon` (D,DG,F,C,H,S,O,R,RH,L). All rc=0, `COMPLETED_WITH_RESULT`, with `summary.json` and `compare_vs_ue_cand_mtp2.{json,txt}`. Section 6 now cites only these runs plus the completed P runs (`100505`, `100746`, `101028`) and the V run (`090129`). The old runs are listed as superseded. Result unchanged: 0 score-changing cases except the two known RH upward flips. |
| 2 | MEDIUM | `longctx.json` records had classification `STARTED` | `run_longctx.py` now sets `COMPLETED_WITH_RESULT` / `FAILED`. The 64K main-only check was re-run (`longctx/20261017-113930`, `COMPLETED_WITH_RESULT`, 11/11). The two earlier records are reclassified as supporting-only. |
| 3 | LOW | `MEASURED_MIB` frozen entry 15,626 was not a probe value | The entry is now 15,620 (probe 15,620.5, rounded half-even). The comment states that the frozen config itself still budgets with the unchanged lease constant `RUNTIME_V1_DEVICE_MIB` = 15,626. New test `test_every_measured_entry_matches_a_completed_probe` checks every entry against `evidence/probe/*/probe.json`. |
| 4 | LOW | "frozen CONTENDED −554" had no evidence file | Measured with the Brain host (`frozen_fit_record.py`, non-destructive: the host starts only when the pre-check is CONTENDED): CONTENDED, margin **−644.2** (`evidence/frozen_fit/20261017-114127`). Section 8 corrected. |
| 5 | LOW | Section 12 failed-run list incomplete; one error mislabelled | Section 12 now lists every failed run by directory with its exact error. `090558` and `090614` were `REFUSED_OTHER_LLAMA_SERVER_RUNNING [17028]`, not `GPU_LEASE_HELD`. Probe argv differences (`--metrics -lv 4`, `C:\` junction targets, lab port) are disclosed. |
| 6 | LOW | `demoted_est` counted CPU buffers as host-visible | `vlab.account` and `summarize.py` separate `Vulkan_Host` from CPU buffers (`cpu_buffers` column). p64-mtp-viscpu is now 23.4 (was −1,082.3). Frozen is now ~883 (was 858: the 24.9 MiB CLIP CPU buffer moved). 128K + vision is ~253 (was 228). Sections 1 and 3 are reworded: "consistent with the vision weights", not "equals". |
| 7 | LOW | `--profile` silently treated unknown MTP tokens as off | `ws_brain_host.parse_profile` refuses anything except `<ctx>,<vision>,<0/1/on/off/true/false>` (`PROFILE_ARG_INVALID`). New test `test_host_profile_argument_is_strict`. |
