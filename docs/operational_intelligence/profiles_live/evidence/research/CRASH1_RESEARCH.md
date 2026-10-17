# CRASH-1 research: llama-server b11425 (Vulkan, Windows) exit 0xC0000409 in live run p1b-main

Date: 2026-10-17. Read-only investigation: no llama-server started, no GPU use, no repository or tracked file modified.

## 0. Acceptance criteria (set before the analysis)

1. Every claim is labelled VERIFIED (I inspected the primary evidence myself, cited below) or HYPOTHESIS / INFERRED.
2. The exact requests the app sent around the crash are identified from source and timing, with the mapping method shown.
3. The crash window is bounded from the log, with the logger's own behaviour taken into account.
4. Each research question (1-5) gets an answer, or a statement of what is missing.
5. Hypotheses are ranked, and each has evidence for and against.
6. Upstream items carry a URL, a state, and whether and where a fix landed.
7. Experiments discriminate between the top hypotheses. Mitigations need no change to frozen Runtime v1 and no llama.cpp patch, and each has a cost estimate.
8. Source-version caveat: b11425 source was not available locally (see 1.1).

## 1. Verified facts

### 1.1 Evidence base

- Server log `D:\uri-dev\uri-profiles-live\fixtures\brain-state-p1b-main\logs\llama-server-20261017-131802.log`: 82 lines, read in full. It ends at `3.01.387.188 I slot get_availabl: id 0 | task -1 | selected slot by LRU, t_last = 179331523`. It contains no `E` line, no assert and no abort text.
- The server was spawned by `uri_operational_intelligence/runtime_v1.py::_spawn`. That function passes `stdout=log, stderr=subprocess.STDOUT`, so stdout and stderr share one file handle. VERIFIED.
- Session evidence `D:\uri-dev\uri-profiles-live\evidence\live\p1b-main\`: brain-phases.json gives FAILED `LOCAL_BRAIN_EXITED:3221226505` at host t=1792223467.185. Also read: session-final.json, observations-main.json and resource-samples.json. integrated-server.log is empty (0 bytes).
- Source: `C:\Users\cheta\Development\uri-adaptive-lab\llama.cpp-b11510` is a shallow clone: one commit, c35b667, 2026-10-08, and only tag b11510. **No b11425 tag or commit exists there, so all source statements below are about b11510.** The log message formats in the b11425 binary match b11510 exactly (`selected slot by LRU, t_last`, `processing task, is_child`, `stop: cancel task`). That is consistent with the same code paths, but it does not prove it.
- The binary is not an MSVC build. The lab log of the same binary says `build 11425 (e117148a4) with Clang 20.1.8 for Windows x86_64`. It links the Microsoft UCRT (ucrtbase.dll), so abort and fail-fast behave as they do for MSVC.
- GPU: AMD Radeon RX 7900 GRE (16368 MiB), Vulkan. Source: lab log of the same profile.

### 1.2 Timeline (server log, converted to UTC)

The server log times are relative to process start. The offset was fixed using calibration task 0 (log 0.27.0 against host calibration t=1792223310.07). The offset error is about 0.1 to 0.2 s.

| task | UTC (approx) | prompt eval | decode | slot n_tokens at release | what it was (see 1.3) |
|---|---|---|---|---|---|
| 162 | 07:50:35.6 | 744 tok, 0.69 ms/tok | 10 tok, 10.6 ms | 753 | "Hello URI" answer (prompt_n 744 matches observations) |
| 176 | 07:50:36.8 | 26 tok, **7.39 ms/tok** | 8 tok, 10.7 ms | 786 | capital-of-France answer (cache_n 753, prompt_n 26 match) |
| 187 / 326 / 339 / 497 / 658 | 07:50:39 to :60 | 145 to 3099 tok | 10.3 to 10.6 ms | 3194 to 3373 | Core seam calls in the "remember that", clarification, approval and "remember again" turns |
| **841** | 07:51:02.6 to 03.26 | 55 tok, 7.52 ms/tok | **4 tok, 36.05 ms/tok** | 844 | answer-channel stream, ended by `<<ACTION>>` (see 1.3) |
| (next) | 07:51:04.37 | none logged | none logged | none | Core proposer seam, `response_format: json_object` |

- Host saw the process exit at about 07:51:07.2 UTC, 2.8 s after the last log line; the host polls at about 0.5 s or slower. The UI turn "remember again: the fact" ended at 07:51:09.95 with `SELECTED_MODEL_UNAVAILABLE`.
- Task 841 ended **naturally**. The log shows `print_timing`, then `release` ("stop processing"), then `cancel task` 23 µs later. In b11510 a client-cancelled task is released by the CANCEL handler and prints **no** `print_timing`. The lab repro log `...\crash_repro\20261017-141437_cr-p1\server_cr-p1.log` shows that pattern 150 times, always `cancel task` first and then `release` with no timings. So in p1b-main the HTTP-side `server_response_reader::stop()` ran after the final result had been queued but before the HTTP thread consumed it, because the client had closed the stream. The CANCEL task then targets an already-idle slot. `release()` is guarded by `is_processing()` and `slot.task` was already reset, so the cancel is a no-op (server-context.cpp `release()` ~l.583, CANCEL case ~l.2797; server-queue.cpp `stop()` ~l.602).

### 1.3 What the app sent around the crash (verified from source plus timing)

- The turn "the project room code is K91015" (07:51:02.26 to 07:51:09.95) triages as `QUESTION / default_conversation`. I ran `uri_operational_intelligence.triage.triage()` on that text, read-only. That routes it to the **answer channel** (`orchestrator._answer_turn`, then `answer.answer`).
- The answer request (`answer.py` + `reasoning_policy.tier_params(FAST)`): streamed `/v1/chat/completions` with `temperature 0`, `max_tokens 900`, `chat_template_kwargs.enable_thinking=false`, and **no response_format and no grammar**. Messages are system + MEMORY_EVIDENCE + "Acknowledged." + up to 12 history turns + user text. Its 840-token prompt shares about 785 tokens with the cached 786-token entry from task 176; the prompt-cache load explains the 55 newly evaluated tokens.
- `answer.relay` calls `cancel.cancel("action_marker")` when the answer starts with `<<ACTION>>` (`answer.py` l.25 and l.262-268). The watcher thread then closes the HTTP response within 50 ms (`brain_client._stream_once`). Four decoded tokens fit `<<ACTION>>` plus end of generation; the model stopped by itself at the same moment the client closed.
- `ACTION_REQUESTED` then reroutes to `_core_turn` (`orchestrator.py` l.239-241), then Core `begin`, then the proposer through `core_provider.RuntimeV1Provider.complete`. That body is `response_format: {"type":"json_object"}` (grammar-constrained), FAST, `max_tokens 600`, run through `complete_json`. complete_json streams with deadlines first_token=60 s, idle=30 s, total=60 s, and retries once only on UNREACHABLE. **This proposer request is the one selected "by LRU" at 07:51:04.37, after which the process died.** Its failure surfaced as UNREACHABLE, then a retry, then `ProviderUnavailableError`, then `SELECTED_MODEL_UNAVAILABLE`.
- **Answer to "was the cancelled task 841 a grammar request?": No.** The grammar (json_object) request is the one after it. Earlier json_object seam calls in the same session (tasks 187, 339, 497, 658; the mapping is inferred from turn timing) decoded at a normal 10.3 to 10.5 ms/token.
- No vision or image input was sent in this journey. Every prompt is text-only, but `server_tokens.has_mtmd` is true because the projector is loaded.

### 1.4 Crash window (code reading, b11510)

- After `SLT_INF "selected slot by LRU"`, `get_available_slot()` always sets `update_cache = true` under `--slot-prompt-similarity 0` and runs, all at TRACE level and so invisible at `-lv 3`:
  1. `prompt_save()`: `llama_state_seq_get_data_ext` copies the slot state GPU to host into a `server_prompt_cache::alloc` entry. In alloc only `state_data_*.resize()` is inside `try { } catch (std::bad_alloc)`. **`states.push_back({prompt.tokens.clone(), prompt.checkpoints, ...})`, a deep copy of every checkpoint (62.8 MiB each for this model), is outside the try** (server-task.cpp l.1771-1786).
  2. `prompt_load()`: host to GPU `llama_state_seq_set_data_ext` of the best entry.
  3. `prompt_cache->update()`.
- After that comes `launch_slot_with_task()`: token validation, then `common_sampler_init` (the json_object grammar; its exceptions are caught and sent as errors), then the INFO `processing task` line.
- None of this runs under a try/catch. `process_single_task` is called from `server_queue::start_loop` and `process_new_tasks` with no handler (server-queue.cpp l.278ff; server.cpp l.555). **Any C++ exception here reaches `std::terminate`.**
- `ggml.cpp` installs `ggml_uncaught_exception` as the terminate handler. It calls `ggml_print_backtrace()`, which **is a no-op on Windows** (ggml.c l.238-242), then the previous handler, which is the UCRT default and calls `abort()`. **An uncaught exception therefore exits with 0xC0000409 and prints nothing.**
- Logging is asynchronous. `common_log` queues entries to a worker thread, which `fflush`es after each entry (common/log.cpp). `GGML_LOG_ERROR` from ggml-vulkan (device lost) goes through that queue, so it **can be lost** if the process dies microseconds later. `GGML_ABORT`/`GGML_ASSERT` use a direct `fprintf(stderr)` (ggml.c l.253-273). `ggml_vk_create_buffer_check` uses `std::cerr` directly, which is unbuffered.
- At `-lv 3` the next visible line would have been `processing task`, normally 73 to 206 ms after the LRU line in this session (lab, `-lv 4`: "prompt cache update took 98-128 ms"). The worker thread flushes within milliseconds. **So the crash most likely happened inside the prompt-cache update or launch, before `processing task`.** A crash a few milliseconds after it, with the line lost, cannot be fully excluded.

### 1.5 Host memory at the crash (resource-samples.json)

| UTC | system RAM available | llama-server RSS |
|---|---|---|
| 07:48:35 (Brain ready) | 2962 MiB | 886 MiB |
| 07:50:19 to 07:50:33 | 948, then 595, then 537 MiB | 886 |
| 07:50:40 | 698 | 1116 |
| 07:50:47 | 631 | 1396 |
| 07:50:54 | 789 | 1490 |
| **07:51:01 (3 s before crash)** | **576** | **1772** |
| 07:51:10 (after crash) | 2993 | none |

- llama-server RSS grew by about 280 MiB per Brain request in the last 25 s. This is the prompt-cache growth: each entry is state plus deep-copied checkpoints. The lab -lv 4 log shows entries of 263 MiB (75 MiB state + 3 × 62.8 MiB checkpoints).
- The p1b-main log has no `making room`, `cache size limit reached` or `failed to allocate` WRN or ERR lines, so the 2048 MiB cap was not yet reached and the cache was still growing.
- The machine has 24,501 MiB physical RAM and a commit limit of 55,498 MiB with an auto-managed pagefile (31 GB allocated). I read this now, 17:55 local. **At the time of reading, free commit was 478 MiB.** At that moment another llama-server (pid 7820, not started by me) held 16,935 MiB private bytes. A full-offload Vulkan llama-server with `--load-mode none` therefore commits about 17 GB of host memory.
- **Not available: commit charge at 07:51:04.** The resource sampler records physical "available" only.
- The lab loop never entered this regime. Its cache plateaued at **3 prompts / 791 MiB**, because its prompts are near-duplicates, and it ran without the Flutter test runner and UI.

### 1.6 Windows Error Reporting

- WER logging works on this machine. Application Error 1000 events exist for other crashes. One is llama-server.exe on 2026-09-17: faulting module ucrtbase.dll, offset 0xa527e, code 0xc0000409. That offset is the UCRT `abort` fail-fast site and is the same offset as android-cli aborts.
- **There is no Application Error event at all for the 2026-10-17 13:21 IST crash**, and no WER report or dump. Why it is missing is unverified. Possible reasons: WER could not start under commit exhaustion, or a job limit. `uri_office/jobobject.py` uses `LIMIT_DIE_ON_UNHANDLED_EXCEPTION`, but I did not verify that the Brain host runs inside such a job. The result is that the faulting module and fail-fast subcode are **unknown**.

### 1.7 Task 841 timing (question 4)

- **Prompt 7.52 ms/token is normal for a small batch.** Task 176 (26 tokens) ran at 7.39 ms/token and lab task 10 (19 tokens) at 7.90 ms/token. Small prompts are dominated by fixed per-call cost: the end-of-prompt split for checkpoint creation and checkpoint copies of 62.8 MiB each. The 0.7 to 1.6 ms/token neighbours were large prompts and are not comparable.
- **Decode 36 ms/token over 4 tokens is anomalous** (task 176: 8 tokens at 10.7 ms; lab: 9.9 ms). It was **not grammar**, because 841 had no response_format. The likely causes are discussed in hypothesis H1 and question 4.

## 2. Answers to research question 1 (what 0xC0000409 means)

- 0xC0000409 is `STATUS_STACK_BUFFER_OVERRUN`. Windows reuses it for every `__fastfail(code)`. Known sources in a UCRT-linked release binary:
  - (a) **`abort()`** uses `__fastfail(FAST_FAIL_FATAL_APP_EXIT=7)`. In release UCRT it prints nothing. It is reached by `GGML_ABORT`, `GGML_ASSERT` (which print first), and **`std::terminate`** (an uncaught C++ exception; prints nothing on Windows because the ggml backtrace is a no-op). Upstream #29579 shows a windbg trace of exactly this: `ucrtbase!abort+0x4e`, subcode 7, Qwen3.6-35B-A3B on Windows.
  - (b) a real /GS stack-cookie failure (subcode 2).
  - (c) UCRT invalid-parameter handler (subcode 5), for example a bad argument to a CRT function.
  - (d) CFG (subcode 10) or STL hardening fail-fast, if compiled in.
- **Does GGML_ABORT/GGML_ASSERT print on Windows? Yes.** `ggml_abort` does `fflush(stdout)`, then `fprintf(stderr, "file:line: msg\n")`, then backtrace (a no-op on Windows), then `abort()`. With stderr redirected to the same file it would reach the log. UCRT stderr is unbuffered by default; this comes from known UCRT behaviour and was not tested here. **Buffering is therefore not a plausible reason for a missing GGML_ASSERT message.** The common_log async queue can lose `GGML_LOG_*` and `SRV_*`/`SLT_*` lines only in the last microseconds before death.
- **Conclusion (inferred):** a silent 0xC0000409 with redirected stderr points to classes (a, uncaught exception), (b), (c) or (d), and **not** to GGML_ASSERT/GGML_ABORT and not to a Vulkan allocation failure in `create_buffer_check`, which prints through `std::cerr`. Without a dump, a, b, c and d cannot be told apart.

## 3. Hypotheses (ranked)

### H1 (most likely): host commit or memory exhaustion causes an uncaught `std::bad_alloc` in the prompt-cache save path

The model: the uncaught exception is thrown in `server_prompt_cache::alloc` → `states.push_back` (deep copy of checkpoints) or in `tokens.clone()`. It propagates to `std::terminate`, then `abort()`, then 0xC0000409 with no message.

- **For:**
  - Code verified in b11510: the deep copy is outside the bad_alloc try, and the path has no handler up to terminate.
  - The crash point is exactly this path (1.4).
  - Physical RAM available was 576 MiB 3 s before.
  - llama-server grew about 280 MiB per request.
  - The machine's commit headroom has been seen at 478 MiB with a 17 GB-private llama-server.
  - Upstream PR #27451 (OPEN, not merged) describes precisely "handle std::bad_alloc during complete cache entry construction, including states.push_back()" and the transient deep copy of checkpoint payloads.
  - Upstream #30091 / #29391: Windows bad_alloc with checkpoints. ggerganov: "Very likely that you are running out of host memory when checkpoints are being created". Another commenter traced it to *committed* memory and the pagefile size.
  - The missing WER record is consistent with a starved system (weak evidence).
  - It explains why the lab loop (cache plateau 791 MiB, no UI or test runner) and lighter runs did not crash.
- **Against or missing:**
  - Commit at 07:51:04 was not measured.
  - No dump.
  - The alloc's own `resize` (the larger single allocation, about 75 MiB) succeeded or we would have an ERR line. But the ERR could be lost if push_back then failed microseconds later.
  - Other P1 runs at a similar profile did not crash. Their memory headroom is unknown to me.

### H2: Vulkan device lost or driver fault during state GPU↔host copy (AMD driver, VRAM oversubscribed)

The model: `vk::DeviceLostError` (or another `vk::SystemError`) is thrown inside `llama_state_seq_get/set_data` and is uncaught. The `GGML_LOG_ERROR` lines are lost in the async log, so the process exits silently with 0xC0000409.

- **For:**
  - Host GPU fit was AT_RISK (margin 218 MB). llama-server had 561.8 MiB non-local (demoted to shared memory) the whole session.
  - The crash window is a large copy burst in both directions.
  - Upstream reports of AMD Vulkan driver-level 0xC0000409 crashes on Windows: #25195, #26945.
  - Memory pressure (H1) also hurts the WDDM paging of demoted allocations.
- **Against:**
  - Lab repro: the same flags with save/load on every one of 300 requests and no crash. The same non-local level was seen in other runs.
  - A device lost in decode would normally hit a caught path (iterate) with visible errors.
  - No evidence specific to the driver.

### H3: memory-safety defect in the server (prompt cache, checkpoints, mtmd token bookkeeping) or a CRT invalid-parameter fail-fast

- **For:** silent 0xC0000409 is compatible with a /GS or invalid-parameter fail-fast. With has_mtmd=true, text-only prompts take the mtmd branches of `get_common_prefix` and `keep_first`.
- **Against:** I found no out-of-bounds path for text-only prompts in b11510. All mtmd asserts require `LLAMA_TOKEN_NULL` tokens, which are absent here. 150 lab cycles were clean. Low prior.

### H4: cancel race (client close vs natural end)

- **For:** the cancel immediately precedes the crash.
- **Against:** code shows the CANCEL of an already-released task is a no-op (1.2). The lab exercised 150 real cancels, including cancel-then-immediate-request. Under H1 the cancel is incidental: the answer-then-reroute pattern simply produces two different large prompts per turn, which speeds cache growth. Low.

### H5: json_object grammar or sampler init

- **Against:** at least 4 earlier json_object seam calls in the same session worked, and sampler-init exceptions are caught and reported. Very low.

### H6: new yield-to-queue worker concurrency (`server_queue::worker_loop`, present in b11510)

- Unverified whether it exists in b11425. During a yield only METRICS and SLOT_GET tasks are processed, and the crash window has no decode in flight. Very low.

### Question 4: link between task 841's slow decode and the crash

- **Inferred:** a common cause rather than a direct link. Decode at 36 ms/token with no grammar and normal GPU residency is consistent with page-fault stalls on the host side (sampling over a 248k vocab, host compute buffer 160 MiB, pinned output) while the system had about 550 MiB available.
- A CPU fallback is not indicated: the graphs-reused count barely changed, and a backend switch would persist across tasks.
- Grammar is excluded.
- A cache miss with checkpoint restore affects prompt time, not decode, and the prompt rate was normal.

## 4. Upstream findings

| Item | Relevance | State / fix |
|---|---|---|
| PR #27451 "server : share checkpoint state and harden prompt cache OOM handling" https://github.com/ggml-org/llama.cpp/pull/27451 | Exactly H1: deep checkpoint copy in `states.push_back`, bad_alloc not handled | **OPEN, not merged** (last update 2026-09-26). b11510 still has the unprotected push_back (verified). No fixed build. |
| #30091 "llama-server crashes due to 'bad allocation' during long conversations" https://github.com/ggml-org/llama.cpp/issues/30091 | Windows, checkpoints, bad_alloc; `-cram 0` and pagefile size suggested by maintainer and users | OPEN (b11455 reported) |
| #29391 bad allocation, then GGML_ASSERT(batch.slot_batched...) https://github.com/ggml-org/llama.cpp/issues/29391 (PRs #29467, #29470) | bad_alloc in a slot on Windows | Issue OPEN; PRs #29467 and #29470 OPEN (they handle the aftermath, not the cause) |
| #29579 "0xc0000409 exit" https://github.com/ggml-org/llama.cpp/issues/29579 | Qwen3.6-35B-A3B on Windows, silent exit; windbg `ucrtbase!abort` subcode 7 | OPEN, no fix |
| #26216 prompt cache exceeds its own --cache-ram cap (vision workload) https://github.com/ggml-org/llama.cpp/issues/26216 | Host memory above the cap; mmproj + unique prompts | CLOSED 2026-07-28 (inactive; no fix identified) |
| #24265 hard hang with prompt cache + checkpoints near RAM limit (hybrid) https://github.com/ggml-org/llama.cpp/issues/24265 | Same memory regime; disabling both fixes it | CLOSED 2026-07-23 |
| #27456 router mode 0xC0000409 when a request hits a busy slot https://github.com/ggml-org/llama.cpp/issues/27456 | Windows silent 0xC0000409 near request overlap | CLOSED (stale); reporter saw no repro on b10545 |
| #25195 Vulkan transfer-queue WAW crash on amdvlk (Windows 0xc0000409) https://github.com/ggml-org/llama.cpp/issues/25195 | H2 (AMD); partial offload only | CLOSED 2026-07-17 |
| #26945 Vulkan STATUS_STACK_BUFFER_OVERRUN with qwen35moe on AMD https://github.com/ggml-org/llama.cpp/issues/26945 | H2 (AMD driver dependent) | OPEN; the reporter says a driver update changed the failure |
| #27560 Windows/Vulkan 0xC0000005 with default ctx-checkpoints https://github.com/ggml-org/llama.cpp/issues/27560 | Checkpoints on Windows/Vulkan/AMD (different code) | OPEN |

- I found no upstream report of a crash caused by the cancel itself. Searches for grammar crashes found only malformed-grammar cases: #27619, #26600.
- Searches used `gh search issues/prs` on ggml-org/llama.cpp. GitHub search coverage is not exhaustive.

## 5. Recommended experiments (cheapest first; GPU only at ordinary load)

- **E0 (no GPU; do now):**
  - Add commit metrics to the live resource sampler: `\Memory\Committed Bytes`, `\Memory\Commit Limit`, and llama-server PrivateBytes and PagefileUsage. This is a tooling change in the live harness, not Runtime v1.
  - Owner action, a system setting: enable WER LocalDumps for llama-server.exe (`HKLM\SOFTWARE\Microsoft\Windows\Windows Error Reporting\LocalDumps\llama-server.exe`, DumpType 1). The next crash then yields the faulting module and fail-fast subcode. Subcode 7 plus a `std::terminate` frame confirms H1 or H2; subcode 2 or 5 means H3.
- **E1 (discriminates H1 from H2):**
  - Run a lab server on the P1 flags plus `-lv 4`.
  - Loop **distinct** URI-shaped prompts: alternate an answer-style prompt (~800 tokens) and a seam-style json_object prompt (~3300 tokens) with a changing tail, so the prompt cache grows to its 2048 MiB cap plus about 1 GiB of slot checkpoints.
  - Arm 1: normal headroom. Arm 2: commit headroom reduced to about 1 GiB by a helper process that commits memory with VirtualAlloc MEM_COMMIT and does not touch the GPU.
  - Predictions: H1 says crash only in arm 2, with the last TRACE line inside `prompt_save` or `alloc`. H2 says crash independent of commit, with a device-lost ERR in the log when the timing allows.
  - Cost: about 10 to 20 min of ordinary GPU load per arm.
- **E2:** repeat E1 arm 2 with `--cache-ram 0`. H1 predicts no crash. Checkpoints at slot level still allocate, so a bad_alloc there would be *caught and logged* by `iterate`, as in #30091.
- **E3:** repeat E1 arm 2 without `--mmproj`. mmproj only changes the memory budget (about 860 MiB of weights plus 248 MiB compute). H1 predicts the crash moves later; no mmproj-specific cause is expected.
- **E4:** replay the p1b-main journey (J1 to J9 plus "remember again") against a lab server with `-lv 4` and the app's real Brain client while the Flutter test runner runs. Watch commit. This is the most faithful test, and also confirms the request mapping in 1.3.
- **E5 (only if E1 to E4 are negative):** a cancel-during-json_object loop: close the stream during grammar decode, then send an immediate seam request (H4 and H5).

## 6. Mitigation options (no change to frozen Runtime v1, no llama.cpp patch)

| Option | Expected effect | Cost (from this log) |
|---|---|---|
| **M1: `--cache-ram 0` on the 64K+vision profile (P1)** | Removes the unprotected save path and up to 2 GiB of host growth | Every switch between answer and seam prompts re-prefills. Seam prompt about 3,300 tokens at about 2,180 tok/s is about 1.5 s, against 0.25 to 0.29 s with cache (tasks 339/497/658). Answer prompt about 800 tokens is about 0.5 s. So about +1.2 s per seam call after an answer, roughly +1 to 3 s per action turn. Consecutive same-prefix calls still reuse the slot with checkpoints. |
| **M2: smaller `--cache-ram` (512 to 768)** | Bounds growth to about 2 entries (~260 to 400 MiB each) | Some misses on the third prompt family; much smaller than M1's cost. It does not remove the unprotected copy, only makes exhaustion less likely. |
| **M3: `--ctx-checkpoints 4` (from 16)** | Each checkpoint is 62.8 MiB, so the slot plus each cache entry shrinks by up to 0.75 GiB in the worst case | Fewer rollback points on hybrid layers, so a little more re-prefill after divergence; measure on Suite P. |
| **M4: host commit headroom (owner/system)** | Directly removes the H1 trigger | Owner decision. Options: fixed larger pagefile, or not running a second llama-server, the 4 GB PowerShell processes or similar during live runs. Free commit was 478 MiB when sampled today. |
| **M5: client/host-side memory gate** | Refuse or delay Brain calls, or warn, when commit headroom is under ~1.5 GiB; record it in evidence | Small code change in the host or worker, not in Runtime v1; no inference cost. |
| **M6: client-side auto-recovery** | On `LOCAL_BRAIN_EXITED`, offer or perform a supervised restart and fail the turn honestly (already honest today) | Restart is about 27 s load plus calibration; product decision. |
| **M7: answer-channel marker** | No effect on H1 apart from fewer distinct prompts per action turn. The cancel itself is benign per code. | Not recommended as a crash mitigation. |

- **Recommendation:** M1 (or M2+M3) for P1 together with M4/E0. Keep P1 unqualified until E1 has run.

## 7. Self-review (against section 0)

- **Repaired during review:**
  - The "slow prompt" premise was corrected: 7.5 ms/token is normal for a small batch (three data points).
  - The "cancelled grammar task" premise was corrected: 841 had no grammar; the next request did.
  - The binary is Clang, not MSVC; the UCRT semantics are unchanged.
- **Unverified and affecting confidence in the verdict:**
  1. Commit charge at crash time. H1 rests on physical RAM data, today's commit reading, code and upstream reports.
  2. No dump or WER record, so the fail-fast subcode and faulting module are unknown.
  3. b11425 source not inspected; b11510 was read instead.
  4. The task-to-turn mapping for 187 to 658 is inferred from timing. The mapping for 162, 176 and 841 is supported by exact token counts and source.
  5. Why WER did not record the crash.
- These gaps do not change the ranking, but **H1 is a hypothesis until E0/E1 produce COMPLETED_WITH_RESULT evidence.**
- Working-tree note: `D:\uri-dev\uri-runtime-profiles-integ` already had uncommitted changes in brain_health.py, runtime_profile_selection.py, run_uri_integrated_worker.py and a test, which were not made by this investigation. The files this analysis relies on (brain_client.py, answer.py, core_provider.py, orchestrator.py, reasoning_policy.py, triage.py, runtime_v1.py) are not among them.
