# REA discovery report — W1, A0 and A1 planning

Date: 2026-10-10. Workspace: worktree `/home/user/uri-wt/rea`, branch `research/rea-discovery-20261010` from
canonical `ffdf534`. Nothing here is runtime code.

## 0. Acceptance criteria (set before the research)

1. URI's existing REA is located and its real state stated from primary evidence.
2. For each capability (browser/screen understanding, multimodal perception, guided learning, Flash Fill, search,
   social), at least two alternatives are compared on fit, resources, security, licence and integration cost.
3. Recommendations rest on source inspection, a small experiment or a measurement — or are labelled analytical.
4. Accepted and rejected approaches are recorded with reasons.
5. REA stays advisory: no package installed, no untrusted code run, no architecture or permission changed.

## 1. What URI's "REA" is (primary evidence)

| Fact | Evidence |
|---|---|
| In URI, REA means **"Reverse Engineer Anything"** (`morluto/rea`): an external MCP server + CLI that wraps Ghidra/IDA/JADX/Binwalk/HAR/mitmdump and a browser, for reverse-engineering binaries, firmware, apps and websites | `origin/research/m1-multiuser-app-host:docs/research/m1_multiuser_app_host/M1_REA_EVALUATION.md` §1 |
| It exists only as a **paper evaluation** on an unmerged research branch; "REA was not installed or run. No benefit has been measured" | same, §1 |
| Verdict of that evaluation: "not an M1 dependency … optional developer tool only", "no M1 benefit"; reverse-engineering private social APIs is called "inappropriate"; inspecting harness binaries/credential stores "prohibited" | same §2-3; `M1_RESEARCH_SUMMARY.md:50,105` |
| No REA code, contract, service or test exists on canonical `ffdf534`, on any `Uri` branch, or in `uri-agent` | `git grep -w REA` over every remote branch of both repositories (2026-10-10) |

**Consequence.** There is no qualified REA "research and implementation discovery" capability to use. Installing REA
would mean running `npx rea-agents setup` (an untrusted, fast-moving npm package that can execute targets) — refused
under the containment rules (and blocked by this session's harness deny rule on `npx`). As the brief directs, the
research below was done with the available bounded tools instead: web search (results cited), source inspection of
URI, package metadata already downloaded for licence checks (not executed), and two local experiments on code
written for this report. **No part of this report is "REA-assisted".**

REA's own domain (reverse engineering) is also the wrong tool for the questions asked: every question here is about
public, documented techniques, which are found by literature and documentation search, not by disassembly.

## 2. Candidate solutions and comparison

### 2.1 Browser understanding

| Approach | Fit for URI | Resources | Security | Licence / cost | Decision |
|---|---|---|---|---|---|
| **MV3 extension, `activeTab` + `scripting`, DOM + a11y snapshot with in-page redaction** (built in A0) | user-click consent per tab matches "explicit, revocable"; exact text, no OCR | ~5 ms snapshot (measured), CPU | no host permissions; page code not run by URI; needs a channel to URI (native messaging host, user-installed; only extensions in its `allowed_origins` can reach it) | platform API | **ACCEPTED** (A0); channel = owner decision |
| Chrome Side Panel UI for the extension | could show Assist inside the browser | none | side panel cannot read pages by itself | platform API | DEFERRED (UI preference; Companion already shows Assist) |
| Playwright/CDP-driven browser (server-side) | autonomous control, not observation of the user's own tab | browser binaries, separate profile | gives a model a browser; credential and session risk | Apache-2.0 | **REJECTED for Assist** (kept only as test harness) |
| browser-use (LLM browser agent) | autonomous operation — out of mandate | LLM per step | model-driven actions | MIT | **REJECTED** |

Evidence: Chrome extension documentation (native messaging, MV3 bundling rule) and W3C discussion of the
native-messaging trust model — [Chrome extensions docs](https://developer.chrome.com/docs/extensions/develop),
[W3C public-browserext thread](https://lists.w3.org/Archives/Public/public-browserext/2016May/0014.html); A0's measured
snapshot latency (`docs/assist/PERFORMANCE.md`).

### 2.2 Desktop/screen understanding

| Approach | Fit | Resources | Security | Decision |
|---|---|---|---|---|
| **Windows UI Automation tree** (`IsPassword`, ValuePattern; TextPattern for multi-line) | structured, exact, exposes password flag for redaction | CPU, ms-scale (to measure on PC) | read-only patterns only; `IsPassword` lets URI drop secrets before use | **ACCEPTED as the next adapter** (contract `uri.assist.uia.v1` exists) |
| Screenshot + **Set-of-Mark** using a11y/UIA boxes, sent to the resident Brain | best grounding in published benchmarks when combined with the tree | +~1.8 s per image turn (measured on Runtime v1), no new VRAM | needs sensitive rectangles (A0 refuses otherwise) | **ACCEPTED for A1 grounding**, on demand only |
| Screenshot-only VLM grounding | weakest in published benchmarks (OSWorld screenshot-only ≈ 5 %) | per-image cost | must black out secrets with no structure → often refused | REJECTED as primary |
| OmniParser (detector + captioner) | strong pixel-only parsing | **a second GPU model** (third-party reports 0.6-3 s/frame on large NVIDIA GPUs); URI's GPU margin is −57…+72 MB | detector reportedly YOLO-based (AGPL claim unverified) | **REJECTED** (second resident model, VRAM, licence uncertainty) |

Evidence: [OSWorld](https://arxiv.org/pdf/2404.07972), [Windows Agent Arena](https://arxiv.org/pdf/2409.08264),
[Spider2-V](https://arxiv.org/pdf/2407.10956) (SoM labels from a11y-tree boxes),
[UIA IsPassword](https://learn.microsoft.com/en-us/dotnet/api/system.windows.automation.automationelement.automationelementinformation.ispassword),
[IUIAutomationValuePattern](https://learn.microsoft.com/en-us/previous-versions/dd375268(v=vs.85)),
[OmniParser research note](https://www.microsoft.com/en-us/research/wp-content/uploads/2025/01/WEF-2025_Leave-Behind_OmniParser-for-Pure-Vision-Based-GUI-Agent.pdf),
[OmniParser V2 on Replicate](https://replicate.com/microsoft/omniparser-v2); URI staging VRAM figures.

### 2.3 Multimodal perception (model side)

| Approach | Decision | Reason |
|---|---|---|
| **Resident Runtime v1 (Qwen3.6-35B-A3B + mmproj) on demand** | **ACCEPTED** (A0) | already loaded; V suite 5/5; 1.84 s per 768 px image; no new VRAM |
| Dedicated GUI-grounding VLM (e.g. Qwen3-VL-4B fine-tunes such as KV-Ground; bbox JSON output) | DEFERRED | promising grounding scores, but a second resident model is ruled out by the freeze record unless measured benefit + owner authorisation; would need the reopening gate |
| Text-only context (DOM/UIA) instead of an image | **ACCEPTED as default** | measured: the A0 fixture's structured context is 776 characters (~194 tokens est.) vs ~605 prompt tokens and 1.84 s for one 768 px image on Runtime v1 |

Evidence: freeze record; `research/rea_discovery/context_cost.json`;
[Qwen3-VL GGUF](https://huggingface.co/Qwen/Qwen3-VL-4B-Instruct-GGUF),
[KV-Ground](https://featherless.ai/models/vocaela/KV-Ground-4B-BaseQw3vl). Whether llama.cpp's Qwen path returns
reliable `bbox_2d` JSON for screenshots was **not verified**.

### 2.4 Guided learning and Flash Fill (A1)

| Approach | Decision | Reason |
|---|---|---|
| **Deterministic programming-by-example over a small string DSL (version-space search), ambiguity surfaced** | **ACCEPTED for A1** | experiment below: 7/8 office transformations correct from ONE example, p50 61 ms, max 668 ms, CPU only |
| Microsoft PROSE SDK | REJECTED for now | .NET SDK; licence not confirmed open source in the sources found; heavy dependency for a narrow need. Its design (DSL + version-space intersection) is the technique adapted |
| LLM-only inference of field mappings | REJECTED as primary | non-deterministic, uses the single Brain slot; kept as escalation for naming steps / semantic mappings the user confirms |
| Continuous learning / fine-tuning from browsing | REJECTED | mandate forbids silent self-training |

Evidence: [PROSE/Flash Fill overview](https://learn.microsoft.com/de-de/archive/blogs/machinelearning/can-ai-generated-code-automate-tedious-elements-of-knowledge-work),
[Interactive Program Synthesis](https://arxiv.org/pdf/1703.03539); experiment §3.

### 2.5 Search and social intelligence

| Approach | Decision | Reason |
|---|---|---|
| Tavily (existing key convention), Brave, self-hosted SearXNG behind one interface | **ACCEPTED** (W1) | reuse + optional providers; explicit UNAVAILABLE |
| Mastodon REST + Bluesky public AppView via SafeFetcher | **ACCEPTED** (W1) | official, read-only, no SDK needed |
| Reverse-engineering private social APIs (REA's domain) | **REJECTED** | prohibited by the M1 evaluation and platform terms |
| trafilatura / readability / markitdown / feedparser | DEFERRED (not installed) | stdlib extraction meets fixtures; installing and running third-party code for a benchmark was not authorised in this session. Benchmark plan in §5 |

## 3. Experiments run (local, contained)

**E1 — Flash-Fill-style synthesis feasibility.** `research/rea_discovery/flashfill_spike.py` (own code), result
`flashfill_spike_result.json`. Eight office transformations (name → "Rao, A.", DD/MM/YYYY → ISO, e-mail → user,
surname upper-case, class/section code, initials, phone grouping, roll number from ID); train on 1 or 2 examples, test
on the rest.

| Examples | Correct on held-out | Ambiguous (top-5 disagree) | Time p50 / max |
|---|---|---|---|
| 1 | 7 / 8 | 2 | 61.5 ms / 624 ms |
| 2 | 7 / 8 | 2 | 61.4 ms / 668 ms |

Findings: (a) deterministic PBE is viable on CPU for this domain; (b) the failure (`phone_group`) is a DSL gap
(arbitrary character slices), so A1 needs position/slice operators; (c) ambiguity persists even when the best program
is right — A1 must show alternatives and ask, as `A1_DESIGN.md` already requires; (d) a search bug found during the
experiment (global frontier cut) was fixed by per-position pruning, the standard version-space approach — recorded
here because the first run under-reported (6/8).

**E2 — context cost.** `context_cost.json`: structured A0 context 776 characters (~194 tokens, estimated as chars/4)
vs a measured ~605 prompt tokens / 1.84 s for one 768 px image on Runtime v1 → structured-first, image on demand.

## 4. Recommendations

1. Keep A0's structured-first perception; build the extension → worker channel (native messaging) and the UIA
   adapter before any new model work.
2. For A1 grounding, use Set-of-Mark style overlays built from DOM/UIA boxes and the resident Brain, on demand only.
3. Implement A1 Smart Fill with deterministic PBE (DSL: tokens, positions, slices, case, date formats, constants),
   version-space search with per-position pruning, mandatory ambiguity display; the Brain only names steps.
4. Do not adopt OmniParser, a second VLM, browser-use, PROSE or REA now.
5. Estimated integration cost (analytical): native-messaging channel S–M; UIA adapter M (PC-only testing); PBE engine
   M (≈ 400-700 lines + fixtures); SoM overlay S.

## 5. Not done / not verified

- REA itself: not installed, not run (unavailable and unqualified; installation not authorised).
- Third-party extractors (trafilatura etc.) were not benchmarked: running downloaded code was not authorised. Proposed
  benchmark: 50 saved public pages, compare main-text F1 against hand labels and latency, in a disposable venv.
- No GPU experiment (no GPU in this container); OmniParser/Qwen3-VL figures are third-party.
- Licence claims about OmniParser's detector and PROSE are unverified.
