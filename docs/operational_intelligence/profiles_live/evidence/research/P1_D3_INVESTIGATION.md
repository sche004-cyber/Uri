# P1 D3 investigation: host commit, pagefile, GPU residency and contention (CRASH-1, DEMOTE-P1)

Date 2026-10-18 (owner decision D3). Read-only. I started and stopped no process, server or GPU workload. I did not
touch the GPU lease or `D:\uri-dev\uri-vram-r1-yield`, and I changed no setting. This file is the only output.
Windows queries used: CIM (`Win32_PageFileUsage`, `Win32_PageFileSetting`, `Win32_ComputerSystem`,
`Win32_OperatingSystem`), `Get-Volume`, `Get-PhysicalDisk`, `Get-WinEvent` (System, Application,
Resource-Exhaustion-Detector/Resolver, WerKernel), registry reads (WER key, Memory Management key, and their last-write
times).

Labels: **VERIFIED** means I inspected the source myself in this session, and the source is named.
**HYPOTHESIS** means inferred or unverified. "Earlier research" means CRASH1_RESEARCH.md or DEMOTION_RESEARCH.md; where
I rely on one of them without re-checking, I say so.

Times: the PC is on India Standard Time (UTC+05:30) (VERIFIED, `[TimeZoneInfo]::Local`). CRASH-1 happened at
**2026-10-17 13:21:07 IST = 07:51:07 UTC** (VERIFIED: `evidence\live\p1b-main\brain-phases.json` FAILED
`LOCAL_BRAIN_EXITED:3221226505` at t=213.49 s; the file was written 13:21:07; the last resource sample with the server
alive is 07:51:01 UTC and the first without it is 07:51:10 UTC in `resource-samples.json`).

## 0. Acceptance criteria (written before the analysis)

| id | criterion |
|---|---|
| C1 | Each of the four questions gets an answer, every statement is labelled, and every VERIFIED item names its source. |
| C2 | The pagefile and commit state now is read from Windows. Commit at the crash is bounded only by evidence. If it cannot be measured, the report says so. |
| C3 | Every Windows log that could confirm or refute commit exhaustion or name a faulting module is queried for the crash window. Its coverage, retention and blind spots are checked, so that a missing event is not read as negative evidence without proof. |
| C4 | "P1-specific" is tested against the code path, the configs and the other profiles' soak data. The crash and the demotion are treated separately. |
| C5 | Each mitigation lists its evidence (with n), its cost and who must act. A mitigation that addresses the demotion is not presented as a crash fix. |
| C6 | The next experiment says what it discriminates between, and states its predictions before it runs. |
| C7 | Contradictions with earlier research are recorded as corrections. |

## 1. Findings

### 1.1 Pagefile and commit configuration now (Q1, part 1)

- **VERIFIED** (`Win32_ComputerSystem`): `AutomaticManagedPagefile = True`. No `Win32_PageFileSetting` instance
  exists, which is consistent with a system-managed pagefile. The registry value `PagingFiles = ?:\pagefile.sys`
  (automatic) and `ExistingPageFiles = \??\D:\pagefile.sys`.
- **VERIFIED** (`Win32_PageFileUsage`):
  - one pagefile, `D:\pagefile.sys`, **AllocatedBaseSize 27,648 MB**;
  - current usage 379 MB, peak 397 MB;
  - created at boot, 2026-10-18 08:27:05.
- **VERIFIED** (`Get-PhysicalDisk`, `Get-Partition`): D: is on disk 0, which is a **Seagate ST1000DM010 SATA HDD**.
  C: is on the Lexar NVMe SSD. So the pagefile is on the spinning disk.
- **VERIFIED** (`Get-Volume`): free space is 451 GB on D: and 49.8 GB on C:.
- **VERIFIED** (`Win32_OperatingSystem`, read 12:19 IST, 2026-10-18):

  | value | KB | MiB |
  |---|---|---|
  | TotalVisibleMemorySize | 25,088,864 | 24,501 (physical RAM) |
  | TotalVirtualMemorySize = commit limit | 53,400,416 | 52,149 (RAM + 27,648 MiB pagefile) |
  | FreeVirtualMemory | 39,695,972 | about 38,766 free commit now |
  | FreePhysicalMemory | 13,199,916 | about 12,890 |

  No Brain was loaded at that moment; I checked only that my own queries did not start one.
- **VERIFIED** (three readings from different sources): the commit limit changes with the pagefile size.

  | when | commit limit | source |
  |---|---|---|
  | 2026-10-17 17:55 IST | 55,498 MiB (pagefile about 31 GB) | CRASH1_RESEARCH §1.5 |
  | 2026-10-17 20:19 IST | 58,197 MiB | `evidence\ram1_snapshot.json` |
  | 2026-10-18, after reboot | 52,149 MiB | this session |

  **So the system-managed pagefile grew by about 2.7 GB during the evening of 2026-10-17, and the reboot reset it to
  27.6 GB.**
- **VERIFIED** (System log, Event 6013 at 12:00 on 10-17, uptime 183,957 s): the boot before the crash was 2026-10-15
  about 08:54. **HYPOTHESIS**: the pagefile at 13:21 on 10-17 was between the post-boot base and the 31 GB seen at
  17:55, which gives a **commit limit of roughly 52 to 55.5 GB at the crash**. The value at 13:21 was not recorded.
- **VERIFIED** (System log, "Application Popup" Id 26, all retained history): the "Virtual Memory Minimum Too Low"
  popup appears exactly twice.
  - **2026-09-17 20:50:41**. Three minutes later, at 20:53:52, a llama-server.exe (LM Studio Vulkan build) logged
    Application Error 1000: ucrtbase.dll, exception 0xc0000409, offset 0xa527e, which is the UCRT abort fail-fast
    site.
  - **2026-10-15 15:50:45**.

  The popup text says: "Windows is increasing the size of your virtual memory paging file. During this process,
  memory requests for some applications may be denied."
  - **VERIFIED**: real commit-limit exhaustion has happened on this PC, the latest two days before CRASH-1.
  - **HYPOTHESIS**: the 09-17 pair is a precedent for "commit exhaustion, then llama-server 0xC0000409". The two
    events are three minutes apart; that is correlation only (n=1, a different llama.cpp build).

### 1.2 Was commit exhaustion plausible at the crash? (Q1, part 2)

- **VERIFIED**: commit was not measured during p1b-main. `resource-samples.json` records `ram_available_mib`, the
  adapter totals and process RSS only.
- **VERIFIED** (`resource-samples.json`, 64 samples about every 7 s):
  - Available physical RAM was 5,465 MiB at session start. It fell to 2,962 when the Brain became READY (07:48:35),
    to 948 at 07:50:19, and then stayed at **537 to 789 MiB from 07:50:26 to 07:51:01**. It returned to 2,993 MiB at
    07:51:10, after the crash.
  - The fall at 07:50:19 (2,421 to 948) came with no growth in llama-server RSS (886) or uri_ui RSS (338). So about
    1.5 GB was taken by a process that is not sampled (**HYPOTHESIS**: the Flutter test runner or another session's
    process).
  - llama-server RSS grew 886 → 1,116 → 1,396 → 1,490 → 1,772 MiB in the last 25 s, which is the prompt-cache growth
    found in the earlier research.
- **VERIFIED** (soak samples, `evidence\soak\*\soak.json`, `host_mem`), on the same day as the crash:
  - In `soak-p3` (10-17, about 18:33 to 19:33 IST), free commit was **386 MiB at t=0** and 544 to 756 MiB in the
    first 13 minutes, with **3,639 to 6,959 MiB of physical RAM available**. So on 10-17 commit, not physical RAM, was
    the scarce resource.
  - CRASH1_RESEARCH read 478 MiB of free commit at 17:55 (not re-checked).
  - `ram1_snapshot.json` shows 4,239 MiB free at 20:19. That snapshot also shows two PowerShell processes at
    4,012 and 3,991 MiB private, started 10-16 23:01 and 10-16 07:14. Both were therefore already running at the
    crash time, 10-17 13:21 (**VERIFIED** from their start times). Their private size at 13:21 is unknown.
  - On 2026-10-18 `soak-p2-e` and `soak-p3-e` had 20,841 to 24,809 MiB free commit (after the reboot cleared the
    stale processes).
- **VERIFIED** (ram1_snapshot and CRASH1 §1.5): a resident llama-server holds about **17 GB of private (committed)
  memory** with a working set of only about 2.8 GB (pid 8180: 17,400 private and 2,777 working set; pid 7820:
  16,935).
- **HYPOTHESIS (numeric match, not proven)**: most of that 17 GB is commit that Windows charges for the GPU
  allocations themselves. P1 dedicated plus non-local is 14,985 + 562 = 15,546 MiB; adding about 1.8 GB of RSS and
  host buffers gives about 17.3 GB. That matches the private-byte readings. If this is right, every Brain profile
  commits about the size of its VRAM request on top of its RAM use. P1 then commits the most of the non-frozen
  profiles; P2 is about 1.1 GB less. The frozen profile is larger still.
- **Answer to Q1**:
  - It is **plausible, but not verified**, that commit was exhausted at 07:51:04.
  - For: on the same day free commit was seen at 386 and 478 MiB. The two 4 GB stale PowerShell processes were alive
    at the crash. Physical availability in the last 45 s before the crash (537 to 789 MiB) was much lower than in any
    soak-p3 sample (at least 3,639 MiB), so the system was under more total load than at the 386 MiB reading. The
    pagefile was system-managed and grows only on demand. Windows says that during growth "memory requests for some
    applications may be denied", and that happened on this PC on 09-17 and 10-15.
  - What would verify it: commit charge and commit limit sampled at the crash. That does not exist.

### 1.3 Windows events at the crash (Q2)

Window queried: 2026-10-17 12:30 to 14:00 IST, plus all retained history where noted.

| source | result | what the result means |
|---|---|---|
| Application log, Application Error 1000/1001/1002/1005/1026 | **none in the window** (VERIFIED) | The faulting module is **not identified**. |
| System log, all events 13:15 to 13:30 | **none** (VERIFIED); the nearest events are 12:23 (Windows Update) and 20:11 | No TDR (Display 4101), no popup 26, no 2004 near the crash. |
| System 2004 (Resource-Exhaustion-Detector) | **none in all retained history** (log retained from 2026-07-07; VERIFIED) | It did not fire even on 10-15, when popup 26 proves exhaustion. **Its absence is not evidence against exhaustion.** |
| Resource-Exhaustion-Detector/Resolver Operational logs | last Resolver notification 10-15 14:59:38; **none on 10-17** (VERIFIED). The Detector's last start was 10-15 14:59:38, and it logged no stop before the unclean shutdown | Same blind spot: no Resolver event followed the 10-15 15:50 popup. Not usable as negative evidence. |
| System "Application Popup" 26 on 10-17 | **none** (VERIFIED) | The pagefile still grew about 2.7 GB on 10-17 (§1.1). So growth can happen without a logged popup, and the missing popup does not exclude a commit-limit hit. **HYPOTHESIS**: the popup is logged only on some growth paths. |
| WerKernel/Operational (live kernel dumps) | latest entries 2026-09-23 (WATCHDOG, AMD_WATCHDOG, AMD_REPORT_UM); **none in October** (VERIFIED; log retained from 2025-06) | **No GPU watchdog or driver live dump at the crash.** This is weak evidence against a driver timeout/TDR form of hypothesis H2. A Vulkan device-lost error without a TDR is not excluded. |
| WER report events (provider "Windows Error Reporting") | **none in the whole retained Application log** (from 2026-05-22; VERIFIED) | WER reports are not logged on this PC at all. |
| WER registry `HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting` | **`Disabled = 1`** (VERIFIED). No `LocalDumps` key. No policy key. The key was last written 2026-10-18 08:27:26 (boot), so when `Disabled` was set is unknown | See below. |
| Unclean shutdown | Kernel-Power 41 at the 2026-10-18 08:27 boot (VERIFIED). The last System event was 10-17 20:11 and the last Application event 10-17 23:xx | Happened about 7 to 10 h after CRASH-1. No link is shown. **HYPOTHESIS**: unrelated host instability (earlier power-loss history in memory notes). |

- **VERIFIED**: Application Error 1000 events kept being logged while WER was apparently disabled. There are 23
  of them from 10-13 to 10-16 (uri_ui, dart, soffice, powershell, msiexec), and the last is 10-16 18:55. So
  `Disabled = 1` does not by itself explain why no event exists for CRASH-1. The precondition is HYPOTHESIS: that
  the setting was already in place then. There have been no WER-provider events since May, which fits a setting
  that has been in place a long time.
- **VERIFIED** (2026-09-17 event): a llama-server fail-fast 0xc0000409 *is* normally logged as Application Error
  1000 on this PC.
- **VERIFIED** (source, `uri_supervisor\winproc.py` lines 267 and 296 in the current working tree): the job that
  holds the URI-spawned llama-server sets only `KILL_ON_JOB_CLOSE`, and not `DIE_ON_UNHANDLED_EXCEPTION`. So
  the job that holds llama-server does not explain the missing event either. The p1b-main run used source head
  fa0a70e6 (`session-start.json`). I did not diff winproc.py against that commit.
- **HYPOTHESIS**: why there is no 1000 event for CRASH-1. Candidates:
  - (a) WerFault could not start or could not write under commit exhaustion. This fits H1, but it is unproven.
  - (b) An inherited error mode such as `SEM_NOGPFAULTERRORBOX` from the launching chain. I found no `SetErrorMode`
    in the runtime, supervisor, core or scripts Python sources, but did not check the Flutter or dart parents.
  - (c) Something else.
  - URI-spawned llama-server crashes have never produced a 1000 event, but n=1, so this is not a pattern.
- **Answer to Q2**:
  - **No Windows event confirms or refutes commit exhaustion at 13:21, and no event names the faulting module.**
  - The detectors that should flag exhaustion (2004, the RDR Resolver, popup 26) are shown to be blind on this PC.
    Each missed at least one verified exhaustion or pagefile growth.
  - The WER channel produced nothing.
  - The only usable negatives: there was no GPU live kernel dump and no System event of any kind in the crash
    window.

### 1.4 Is the crash, or the demotion, P1-specific? (Q3)

**The crash and the demotion are separate events.**

- **VERIFIED** (`resource-samples.json`): during p1b-main the Brain stayed fully resident up to the last sample
  before the crash. llama-server non-local was 561.8 MiB, the baseline, in every sample, and dedicated was 14,940
  to 15,009 MiB. Adapter total was at most 15,865 MiB, about 500 MiB free.
- **VERIFIED** (same file): the only GPU consumers sampled were dwm.exe and uri_ui.exe. No browser appears.
- **VERIFIED** (`soak-p1\soak.json`): in soak-p1 the demotion did not crash the server (120/120 turns HTTP 200, host
  not exited).
- So **CRASH-1 happened without demotion, and DEMOTE-P1 happened without a crash.**

**CRASH-1: no evidence that it is P1-specific.**

- **VERIFIED** (`uri_operational_intelligence\runtime_v1.py::expected_argv` lines 76-90): every profile and the
  frozen configuration are launched with the same base argv, including `--load-mode` and
  `--cache-ram <cache_ram_mib>`. Profiles change ctx, vision placement and MTP.
- **VERIFIED** (`D:\uri-dev\bqc-compat-check\model_lab\integration\local_brain.json`, a copy of the frozen-shape
  config): `cache_ram_mib 2048`, and extra_args `--ctx-checkpoints 16`, `--checkpoint-min-step 512`,
  `--slot-prompt-similarity 0`. `runtime_profiles.py` line 111 only strips the MTP args from extra_args.
  - **HYPOTHESIS**: that copy equals the canonical frozen config. I did not diff it.
- So the prompt-cache save path that the leading hypothesis H1 names is **common to P1, P2, P3 and the frozen
  configuration** (VERIFIED for argv; the code path itself comes from CRASH1_RESEARCH's b11510 reading).
- **HYPOTHESIS**: entry size does not depend on the profile. Prompt-cache entry size depends on the tokens held and
  on the recurrent-state checkpoints (62.8 MiB each), not on the context size. So per-request host growth (about
  280 MiB per request in p1b-main, VERIFIED from the RSS series) is about the same for every profile. MTP adds draft
  state.
- **HYPOTHESIS**: the only P1-related factor found is that P1 has the largest VRAM request of the candidate
  profiles. If GPU allocations are charged to commit (§1.2), P1 leaves about 1.1 GB less commit headroom than P2 and
  about 0.4 GB less than P3. The frozen profile leaves less still. That changes how *likely* exhaustion is, not the
  mechanism.
- **VERIFIED**: low commit by itself did not crash P3. soak-p3 ran 120/120 turns at 386 to 756 MiB free commit early
  in the run.
  - That is not a test of the crash path: soak turns are short near-duplicate prompts. **HYPOTHESIS**: the prompt
    cache plateaus, as in the lab loop at 3 entries / 791 MiB.
  - The commit limit was also probably growing at that time, since free commit rose to 5,107 MiB.
- **Answer**: CRASH-1 is n=1, on P1. No mechanism found is unique to P1. The suspected path and the commit pressure
  apply equally to P2, P3 and the frozen configuration under the same host conditions. **Treat CRASH-1 as a risk to
  every profile.** This agrees with `remaining_limitations` in UI_QUALIFICATION_RUNTIME_PROFILES.json.

**DEMOTE-P1: depends on margin, not on P1 as such.**

- **VERIFIED** (soak JSON summaries):

  | soak | profile | admission | under the same Chrome protocol |
  |---|---|---|---|
  | soak-p1 | P1 | AT_RISK, +218 | demoted 1,021.7 MiB; decode min 20.5 |
  | soak-p2 | P2 | FITS, +1,258 | max non-local 561.8 (baseline) |
  | soak-p3 | P3 | AT_RISK on a heavier desktop: others 1,533, dwm 1,053 | max non-local 497.8 (baseline); decode min 94.3 |
  | soak-p2-e | P2 | FITS | baseline |
  | soak-p3-e | P3 | FITS | baseline |

- Earlier research (not re-checked): 64K+MTP (+29) and the frozen profile (−549) demoted.
- **Answer**: demotion is a property of small VRAM headroom with a browser. Any profile whose actual free VRAM falls
  under one Chrome burst is exposed, the frozen profile included. P1 is the most exposed qualified-candidate profile
  because its margin is the smallest.
- **HYPOTHESIS**: P3's soak-p3 survival on a heavier desktop at AT_RISK shows that the about 400 MiB smaller request
  was enough there. n=1 per desktop.
- **HYPOTHESIS**: how demotion and commit interact. A demoted allocation is already backed in system memory. If GPU
  memory is commit-charged, demotion needs no new commit, but it needs about 1 GiB of *physical* pages. With the
  pagefile on an HDD, physical pressure during a demotion would add paging stalls. soak-p1 has no host_mem samples,
  so this cannot be checked for DEMOTE-P1.

### 1.5 Task 841's slow decode, revisited

- **VERIFIED** (crash log): task 841 decoded 4 tokens at 36.05 ms each, against about 10.6 ms for the earlier tasks.
  Available RAM was 576 MiB at the nearest sample.
- **HYPOTHESIS** (it strengthens CRASH1's "common cause" reading): with a system-managed pagefile on a **SATA HDD**
  (VERIFIED) and about 550 MiB of physical RAM available, hard page faults on host-side buffers (sampling, the
  pinned output, the Vulkan_Host compute buffer) would cost milliseconds each. That fits a decode slowdown with no
  GPU demotion (non-local was at baseline, VERIFIED). Not measured: hard-fault counters.

## 2. Mitigations (Q4)

| # | mitigation | addresses | evidence (n) | cost | who acts |
|---|---|---|---|---|---|
| M1 | **Set a fixed pagefile instead of system-managed**, for example initial = maximum = 40,960 to 49,152 MB on D:. That gives a commit limit of about 64 to 72 GB from boot, with no grow-on-demand window. | CRASH-1 under H1, all profiles | VERIFIED: commit was the scarce resource on 10-17 (soak-p3 386 MiB free with ≥3.6 GB physical available; 478 and 4,239 readings); auto-growth seen (52 → 55.5 → 58.2 GB); two exhaustion popups on 09-17 and 10-15 whose text says requests may be denied during growth. HYPOTHESIS: this prevents the bad_alloc. | Disk space only (D: has 451 GB free). A commit reservation causes no I/O unless pages are actually written. A reboot is needed. C: has only 49.8 GB free, so D: is the realistic location; the HDD speed matters only for real paging. | **Owner** (system setting). I changed nothing. |
| M2 | **Before live runs and soaks, close stale heavy processes from other sessions** (the 2 × about 4 GB private PowerShell processes, idle Claude/Codex CLIs, a second llama-server) | CRASH-1 (commit) and physical pressure | VERIFIED: ram1_snapshot (2 PowerShell processes at about 4.0 GB private each, 6 Claude processes at 0.6 to 1.4 GB); free commit was over 20 GB after the reboot that cleared them (soak-p2-e, soak-p3-e) | None | Owner or operator |
| M3 | **Record commit in every live run**: `\Memory\Committed Bytes`, `\Memory\Commit Limit`, and llama-server PrivateBytes/PagefileUsage in the p1b-style resource sampler, not only in soaks; plus a warning or delay gate when free commit < about 1.5 GiB | Makes the next crash diagnosable; avoids starting a Brain call into exhaustion | VERIFIED gap: p1b-main had no commit data | Small harness/host change; no change to Runtime v1 | Developer |
| M4 | **Smaller `--cache-ram` (512 to 768) and/or `--ctx-checkpoints 4` on the non-frozen profiles** | Reduces host growth of about 280 MiB per request (VERIFIED from the RSS series) and the bad_alloc exposure | CRASH1 §6 (M1 to M3 there); upstream #30091 and #27451 (from earlier research, not re-checked) | +0.5 to 1.5 s re-prefill on some action turns (CRASH1 estimate) | Developer; profile flags only |
| M5 | **Owner: enable crash dumps** (`LocalDumps\llama-server.exe`, DumpType 1). Note that **WER is `Disabled = 1` on this PC** (VERIFIED). **HYPOTHESIS**: LocalDumps may not be honoured while WER is disabled. Check with the owner's chosen setting before relying on it. | Identifies the faulting module and fail-fast subcode at the next crash | VERIFIED: no dump or record exists for CRASH-1 | System setting | **Owner** |
| M6 | **Vision on CPU at 64K (`--no-mmproj-offload`)** | **DEMOTE-P1 only** (−1,106 MiB VRAM, P2-sized request) | Earlier research: the P2 soak at the same request size did not demote (n=1 bound, n=2 total); the exact profile is unmeasured | Image encode 4.2 to 5.0 s instead of 0.5 s; +0.84 GB host RAM | Developer (measurement M3 in DEMOTION_RESEARCH) |
| M7 | **Close or limit the browser / other GPU apps while P1 runs; prefer P3 or P2 when a browser is in use** | DEMOTE-P1 | VERIFIED: soak-p1 recovered 180 to 210 s after Chrome closed; P2 and P3 soaks did not demote | User-facing advice | Owner / UI |

- **HYPOTHESIS**: M6 is **not a crash mitigation**. Moving the projector to the CPU moves about 0.86 GB of weights and
  compute buffers into host memory. Under the commit-charging hypothesis, total commit stays about the same, and
  physical pressure increases.
- **HYPOTHESIS**: M1 and M2 are cheap and backed by evidence for the commit side. M4 also cuts growth, but costs some
  latency. None of them is a confirmed root-cause fix until the experiment below runs.

## 3. Experiment that would confirm the root cause (Q4)

**E0b (no new GPU load; run during the next ordinary qualification run).** At READY and during a journey, sample
llama-server PrivateBytes, system Committed Bytes and Commit Limit every 2 s for P1, P2 and P3.

- Predictions, written before the run, under the commit-charging hypothesis:
  - private bytes ≈ dedicated + non-local + RSS for each profile;
  - P1 − P2 ≈ 1.1 GB;
  - P1 − P3 ≈ 0.4 GB.
- If private bytes are about 17 GB for all three, the hypothesis is refuted, and the 17 GB comes from host buffers
  instead (for example `--load-mode none` staging).

**E1′ (the decisive test; GPU at ordinary load, inside the lease; about 15 to 25 min per arm).** CRASH1 §5 E1, run on
**P2 instead of P1**, so that it also answers Q3.

- Setup: a lab server on the P2 flags with `-lv 4`. Loop distinct answer-style (~800 tokens) and seam-style
  json_object (~3,300 tokens) prompts so that the prompt cache grows to its cap.
- Arm A: normal commit headroom.
- Arm B: a helper commits memory (VirtualAlloc MEM_COMMIT, no GPU use) until free commit is about 1 GiB, with a
  **fixed** pagefile so the limit cannot grow during the test.
- Record commit every 1 s, and set up dumps (M5) if the owner allows.

| outcome | reading |
|---|---|
| H1 + not P1-specific | Arm B crashes with 0xC0000409; the last TRACE line is inside `prompt_save`/alloc; a dump (if any) shows subcode 7 under `std::terminate`. Arm A does not crash. |
| H1 but P1-specific | P2 survives arm B. Then repeat on P1. |
| H2 (driver) | The crash does not depend on commit, possibly with a device-lost ERR line. |
| Follow-up | E2 (arm B + `--cache-ram 0`) should then not crash under H1, which separately validates mitigation M4. |

- Cost: about 1 GPU hour for E1′ A+B plus E2.
- The commit-starvation helper is a deliberate host stress. It needs the owner's approval because it can affect
  other sessions on the PC.

## 4. Corrections to earlier records (C7)

- **Correction**: CRASH1_RESEARCH §1.6 said "WER logging works on this machine", based on the 09-17 Application
  Error 1000.
  - Now VERIFIED: Application Error 1000 works, but **WER itself is `Disabled = 1`**, and no WER-provider report event
    exists in the retained Application log since 2026-05-22.
  - The CRASH1 statement stands as history. It is accurate for event 1000 only.
- **Addition**: CRASH1 §1.5 gave "commit limit 55,498 MiB with an auto-managed pagefile (31 GB allocated)" as if it
  were fixed. VERIFIED now: the limit moved (55,498 → 58,197 on 10-17; 52,149 after the 10-18 reboot). The pagefile is
  on an HDD.
- **Addition to UI_QUALIFICATION_RUNTIME_PROFILES.json** `remaining_limitations` ("no Windows log ... because the
  terminate handler prints only on Linux/macOS"): the absence of an Application Error event is *not* explained by the
  terminate handler. A fail-fast normally produces event 1000 on this PC (09-17 precedent). Why it is missing is
  unverified (§1.3).

## 5. Self-review against C1 to C7

| id | status |
|---|---|
| C1 | Met. Q1 §1.1-1.2, Q2 §1.3, Q3 §1.4, Q4 §2-3. Each item is labelled. |
| C2 | Met. Current configuration is read. Commit at the crash is **not measurable** and is bounded only as HYPOTHESIS (limit about 52 to 55.5 GB; free commit unknown). |
| C3 | Met. Six log sources were queried. The blind spot of each detector is shown against a verified exhaustion or growth event. |
| C4 | Met. The crash and the demotion are separated with sample data. The shared argv is verified in source. The P1-specific factor is reduced to headroom. |
| C5 | Met. M6 is explicitly marked as not a crash fix. Owner actions are marked. |
| C6 | Met. Predictions are written before the run, and P2 is used so the test answers Q3. |
| C7 | Met. Three corrections or additions are recorded. |

Gaps found in review and repaired:

1. A first draft treated the missing popup 26 on 10-17 as weak evidence against exhaustion. The repaired text shows
   the pagefile grew on 10-17 without a popup, so that inference was removed.
2. A first draft attributed the missing event 1000 to `WER Disabled`. The repaired text shows that event 1000 kept
   being logged on 10-13 to 10-16 under the (apparently) same setting.

Not verified, and whether it affects a verdict:

| item | effect |
|---|---|
| Commit charge at 13:21:04 | Keeps H1 a hypothesis; does not change the mitigation ranking. |
| Whether GPU allocations are commit-charged (§1.2) | Affects only the "P1 leaves the least headroom" refinement, not the "not P1-specific" verdict. |
| When `WER Disabled = 1` was set, and whether LocalDumps works while it is set | Affects M5's usefulness. |
| Whether the bqc-compat-check `local_brain.json` equals the canonical frozen config | Low; the argv code is common anyway. |
| winproc.py at fa0a70e6 compared with the working tree | Low. |
| Cause of the 10-18 unclean shutdown | Not linked to CRASH-1; no verdict depends on it. |
| The b11425 source | Not inspected; all code-path statements come from the earlier b11510 reading. |
