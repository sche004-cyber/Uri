# URI Companion Presence — Voice Interaction and State System

**Branch** `phase/companion-voice` · **worktree** `C:\Users\cheta\Development\uri-companion-voice`
· **base** `d7a052f` (`phase/living-companions`, itself not accepted) · **date** 2026-10-09

Candidate phase. Nothing is merged, nothing is accepted, no production or
frozen file is changed, and the running app's shell (`living_shell.dart`,
`energy_orb.dart`) is not rewired. The work is a self-contained presence layer
on top of the living-companions candidate, demonstrated in its own harnesses.

Design rule followed throughout: **change the state, not the character;
change the speaker, not the visualization.**

---

## 0. Status ledger

| Item | Researched | Implemented | Verified in real Flutter frames | Measured | Live-integrated | Accepted |
|---|---|---|---|---|---|---|
| Revised state expression (listening, thinking, working, approval, error) | yes | yes | yes — run 4, metrics | yes | n/a | **no** |
| Approval attention pulse | yes | yes | yes — trough and peak frames | yes | n/a | **no** |
| Shared oval voice waveform (one shader, both speakers) | yes | yes | yes — run 4, pixel-identity check | yes | **no** | **no** |
| Level mapping (one mapping, per-stream reference) | yes | yes | yes — tests on real speech | n/a | **no** | **no** |
| Voice session state machine (barge-in, stale events, watchdog) | yes | yes | yes — tests incl. random storms | n/a | **no** | **no** |
| Transcript (user partials, URI word-synced) | yes | yes | yes — run 4 | n/a | **no** | **no** |
| Orb ↔ waveform transition, companion never remounted | yes | yes | yes — blend sequence + widget test | yes | **no** | **no** |
| Companion sized to its space (body ≈ ½ of box) | owner request | yes | yes — run 4 | yes | n/a | **no** |
| Live microphone level / live URI speech audio | yes | **no** | **no** | **no** | **no** | **no** |
| Brain-active performance | yes | n/a | n/a | **uncontrolled overlap only (§8.2); stutter found** | n/a | **no** |

"Live-integrated" is **no** for every voice item: no microphone or speaker is
opened by anything in this branch. Every voice frame and test is driven by
**genuine speech audio** (System.Speech synthesis, §4) delivered as a
**scripted session**, and is labelled SIMULATED on screen and in this report.

---

## 1. Acceptance criteria, set first

From the brief, made checkable:

1. Each identity stays recognisable in idle, listening, thinking, working,
   approval and error — measured, not only eyeballed.
2. Thinking reads as a deeper shade with subdued glow; listening as softer;
   working as steady; approval as a gentle recognisable pulse; error keeps the
   identity and shows an accessible text status.
3. No state darkens the whole image so far that identity detail is lost.
4. Exactly one waveform implementation for both speakers, with no speaker
   input at all, proven by identical pixels for identical audio.
5. The waveform follows only the stream that is speaking.
6. Equal speaking effort draws an equal waveform even though URI's synthesised
   speech is louder than a typical microphone.
7. Transcripts sit under the waveform, update without layout jumps, and URI's
   text follows playback only where real timing exists.
8. Barge-in, cancellation, audio failure, lost signal and rapid toggling never
   leave a stuck or misleading UI, and never reset the companion.
9. Existing shaders, palettes and tests show no regression.
10. Performance documented with hardware, method and conditions; nothing
    simulated presented as live.
11. No frozen, production or unrelated file changed.

---

## 2. Baseline inspected

* `d7a052f` clean; 294 tests passing at that commit (re-run in this phase as
  part of the full suite).
* `CompanionState` (9 states) and `CompanionStateSource` / `CompositeCompanionSource`
  in `lib/living/companion/` are the authoritative-state contract. Kept
  unchanged; the voice layer plugs in as one more source.
* **No voice audio interface exists on this branch.** `companion_state.dart`
  itself says listening "can only come from a mock source".
* An opt-in Windows voice adapter exists only as **uncommitted work** in the
  `_V1` checkout (`scripts/uri_voice_listener.ps1`,
  `uri_ui/lib/services/voice_event.dart`; preserved on
  `preserve/v1-harness-voice-research-20261004`). It publishes
  `status.json {state, kind, text, sequence, timestamp}`, recognises with
  System.Speech, transcribes with faster-whisper, and speaks only a fixed
  acknowledgement through SAPI. **It exposes no audio level and no reply
  speech.** It belongs to another line of work and is not imported here.
* `feature/uri-dictation` computes "a clipped RMS display level for each audio
  block" in its recorder. That is the same shape this phase consumes
  (`AudioLevel(speaker, rms, blockMs)`), so a live feed is a small adapter, not
  a redesign (§9).

---

## 3. Architecture

```
 audio owner (future: voice adapter / playback tap)         authoritative sources
   │ ListeningStarted / UserSpeechStarted / UserTranscript      (AppState, SupervisedRuntime)
   │ UriSpeechStarted / UriSpeechProgress / UriSpeechEnded              │
   │ AudioLevel(speaker, rms) / VoiceFailure / VoiceReset               │
   ▼                                                                    ▼
 VoiceSessionController ── reduceVoice (pure) ──► VoiceSession    CompanionSignal
   │  per-stream VoiceLevelMapper ─► level, flux                         │
   │  watchdog                                                           │
   └──────────────► resolvePresence(signal, session) ◄───────────────────┘
                              │ PresenceView {mode, orbState, status, notice}
                              ▼
                    CompanionPresence  (live)  /  capture harness (fixed frames)
                              │ PresenceLayout + PresenceComposition (shared)
              ┌───────────────┼───────────────────────┐
         CompanionOrb    VoiceWaveform            VoiceTranscript + PresenceStatus
     (always mounted)   (voice_waveform.frag)
```

New files, all under `uri_ui/lib/living/voice/`:

| File | Role |
|---|---|
| `voice_level.dart` | `VoiceLevelMapper` (one mapping), PCM16 RMS, envelope, WAV reader |
| `voice_session.dart` | `VoiceSignal` events, `VoiceSession`, pure `reduceVoice`, `VoiceSessionController` with watchdog, `VoiceCompanionSource` |
| `voice_waveform.dart` | `VoiceWaveform` (live), `VoiceWaveformFrame` (deterministic), painter, reduced-effects fallback |
| `voice_transcript.dart` | fixed-height transcript, `TranscriptWindow` (user tail, URI sentence) |
| `voice_script.dart` | turns real audio + timing into timed events; real-time player |
| `companion_presence.dart` | `resolvePresence`, `PresenceLayout`, `PresenceComposition`, `CompanionPresence`, `SoftDisc`, `presenceScale` |

Changed: `companion_orb.dart` (state tables regenerated; `withAttention`,
`attentionWave`, `attention` flag), `rnd/companions/registry.js` (same tables),
`pubspec.yaml` (one shader asset). New shader `shaders/voice_waveform.frag`.

Smallest-solution choices: no new package, no audio plugin, no new rendering
engine. The waveform is one ~100-line fragment shader on the same
`FragmentProgram` path the companions already use.

---

## 4. Audio fixtures — genuine speech, scripted sessions

`rnd/voice/make_fixtures.ps1` synthesises two clips with Windows
System.Speech (the engine the existing voice adapter already uses for output):

* `uri_reply` — Microsoft David, 9.0 s, 26 words.
* `user_request` — Microsoft Zira as a **stand-in for a person**, 5.9 s, 17 words.

Both are 16 kHz mono PCM16 with per-word timing from the synthesiser's own
`SpeakProgress` events. Synthesis is deterministic: regenerating produced
byte-identical WAVs (MD5 `fbcbd62f…`, `eeff6817…`). The fixtures live in
`test/fixtures/voice/`, not in app assets, so they never ship.

Finding during this work: PowerShell delivers `SpeakProgress` through an
event queue that does **not** preserve order; the first `user_request` timing
file listed "Friday" second. Each entry carries its own offsets, so the
generator now sorts by character position and `VoiceScript.wordsFromJson`
sorts defensively. A test asserts monotonic order.

---

## 5. State expression — revision 2

Tables live in one place, `rnd/companions/state_tables.py`, which writes the
Dart widget, the WebGL prototype and `state_tables.json`; a test fails if the
widget and the JSON disagree.

What changed and why (revision 1 made thinking brighter and busier than idle
and working maximally turbulent, which read as alarm):

| State | Intent | Means |
|---|---|---|
| listening | softer | lower energy, flare, particles; exposure 0.97–0.98 |
| thinking | deeper shade, subdued glow, concentrated movement | exposure 0.84–0.85, flare and particles well below idle, turbulence up, focus high |
| working | steady, controlled | energy up, turbulence low, focus high |
| awaiting approval | gentle attention pulse | calm base + runtime pulse: exposure +0.11, flare +0.16, energy +0.08 at peak, 2.8 s period, faded in/out, frozen at midpoint under reduced motion |
| error | identity preserved, clear status | moderate values, low focus; meaning carried by the icon + text + danger colour |

**Measured** on real Flutter frames (`rnd/voice/state_metrics.py`, run 4,
body = inner disc of the companion, detail = mean |Laplacian| in the body):

| Identity | listening body | thinking body | working body | approval peak body | detail range across states |
|---|---|---|---|---|---|
| Solar | 0.96 | 0.94 | 1.16 | 1.10 | 0.98–1.11 |
| Sakura | 0.94 | 0.93 | 1.19 | 1.13 | 0.96–1.00 |
| Lunar | 0.99 | 0.91 | 1.03 | 1.05 | 0.98–1.04 |
| Moonlit | 0.99 | 0.92 | 1.03 | 1.05 | 0.96–1.03 |

(all relative to idle = 1.00; idle/listening/thinking/working/approval rows)

Ordering thinking < listening < idle < working holds for all four (run 3
gave the same ordering). Body detail stays within 0.96–1.11 of idle, so no
state flattens the companion.
Correction recorded: run 2 had listening *darker* than thinking (Solar 0.94 vs
0.96), the reverse of the brief; listening now softens through energy and
flare and thinking carries the shade. Run 2's metric script also measured a
region 1.7× too large (it used the diameter as the radius); fixed before the
numbers above, and run 2 re-measured with the fix.

Limitation: Lunar's states differ least (moon albedo dominates the body); its
state reads mostly through cloud motion, which a still frame under-shows, and
through the status line. The approval pulse on Lunar peaks at +5 % body.

---

## 6. The shared voice waveform

**One component, no speaker input.** `VoiceWaveformPainter.uniformsFor` has
16 slots — size, time, level, flux, presence, motion, three theme colours —
and none for the speaker. A test pins the vector.

**Proof of identical treatment.** The capture harness plays the URI clip twice
through the full pipeline (controller → mapper → frame): once as the user's
microphone, once as URI's playback. At five moments the waveform PNGs are
**byte-identical: 5/5, in all four capture runs.** A unit test asserts identical level
and flux for every block of the clip.

**One mapping, fair across streams.** A desktop microphone typically delivers
conversational speech around −30 dBFS; the synthesised fixtures sit at a median
of −20 dBFS (measured: 90th percentile −15 dBFS). A fixed absolute mapping
would draw URI bigger for the same effort. Each stream therefore gets its own
instance of the *same* `VoiceLevelMapper`, which tracks that stream's typical
speech level with a slow (2.5 s), bounded (±10 dB) reference. A test feeds the
user clip 9 dB quieter and shows the two display levels converge within 0.12.
Bounds mean a dead or clipping input still looks quiet or loud.

**Shape.** Four mirrored, soft-filled bands under an elliptical envelope, so
loud speech fills an oval rather than a spindle; a centre line strongest in
silence; a faint glass body and rim. Frequencies are mutually irrational, a
slow travelling lobe varies where bands bulge, and onsets (flux) add ripple.
No bars, spikes, circles or glow halo. Colours are the active palette's
`accent`, `accentInk` and `ink` tokens.

**Correct source.** `AudioLevel` frames from the stream that is not speaking
are dropped by the controller (tested). Listening and user speech are one
stream (the microphone), so speech onset does not reset the level; changing
stream does, and the waveform's own 60 ms glide turns that into a smooth rise.

**Reduced motion:** no travelling phase, much slower level follower (450 ms),
pulse frozen. **Reduced effects:** no shader; a thin line whose length and
thickness follow the same level.

Iterations (all kept in `docs/companions/voice/evidence/run1..4`):
run 1 drew a thin "laser line" and the level saturated at ~0.95; run 2 moved
to an elliptical envelope and the per-stream reference; run 3 raised band gain
and enlarged the companion; run 4 added the 6 % layout margin and the thinner
reduced-effects line.

---

## 7. Voice session behaviour and recovery

`reduceVoice` is pure; every rule is tested.

* Events carry their session or utterance id; anything not current is stale
  and changes nothing.
* **Barge-in:** speech while URI talks switches to the user at once and marks
  URI's utterance interrupted; its late progress, end and even a re-sent start
  are dropped.
* URI audio that starts while the user speaks is not drawn over them.
* Opening a listener during URI speech cuts the reply off.
* Playback progress never runs backwards.
* Failure or reset ends any phase, with a notice.
* **Watchdog:** a speaking phase with no audio or progress for 4 s, or a
  listener with no speech for 15 s, ends itself with "Voice signal lost" /
  "Stopped listening: no speech heard". A crashed audio owner cannot leave a
  frozen waveform.
* 300 random storms of 60 events each hold every invariant and always reset
  cleanly.
* Widget test: ten rapid events (listen, speech, URI start, end, re-start,
  barge-in, late end, failure, start, reset) at 90 ms spacing — no exception,
  the companion element is the **same element** throughout (never remounted),
  and the UI ends in companion mode with the notice shown.

**Presence resolution:** only real speech shows the waveform; a source that
merely claims "speaking" without audio keeps the companion. Error,
unavailable and awaiting-approval win over an open listener, and **stay named
in the status line while the waveform is up** (captured: approval over URI
speech). A voice failure is a notice, not a URI error.

**Transitions:** one blend value drives everything. The companion moves and
shrinks to a mark above the oval (its clock, expression and identity carry on);
the oval and transcript fade in only after 45 % of the blend so they never sit
on top of the full-size companion. Interrupting a transition retargets from
where it is. 520 ms normally, 160 ms under reduced motion.

**Transcript:** fixed-height box, same typography for both speakers, a one-word
label ("You" / "URI"), SIMULATED tag when the session is scripted. User
partials keep the newest words visible and drop older ones at a word boundary.
URI's reply is shown a sentence at a time with heard words in `ink` and the
rest in `inkSoft`, switching sentence only when the next one's first word is
heard; without timing the reply is shown whole.

**Companion size** (owner request mid-phase: "orbs look smaller"). The shaders
draw the body at 30–38 % of their square, so rendered at the layout box the
companion looked small. It is now rendered at `0.50 / bodyRadius` of the box
(capped 1.4×), so the body spans about half its space in every identity, with
a 6 % margin and a radial `SoftDisc` mask that ends the atmosphere at the box
edge. The mask also removes the square sky that showed around the small voice
mark in run 1. Shaders untouched.

---

## 8. Performance

**Hardware and environment.** AMD Radeon RX 7900 GRE (driver
32.0.31041.1004), AMD Ryzen 9 5900X (12 cores / 24 threads), 23.9 GB RAM,
Windows 11 Pro build 26200, display 2560×1440 at 144 Hz, device pixel ratio
1.0. Flutter 3.47.2, Windows desktop, Impeller, **profile build**
(`flutter build windows --profile -t tool/demo/voice_demo.dart`).

**Method.** `rnd/voice/run_perf.ps1` launches the profile executable with the
scenario in environment variables and samples **that exact PID** (another
`uri_ui.exe` could be running) with `rnd/voice/sample_process.ps1`: process CPU
% (share of all 24 logical cores), per-process GPU 3D-engine utilisation,
whole-adapter 3D utilisation and per-process dedicated GPU memory, from the
Windows WDDM performance counters (vendor-neutral), every ~2 s. Inside the app,
`SchedulerBinding.addTimingsCallback` records every frame's build and raster
duration after a 4 s settle period; RSS every 5 s. The live `CompanionPresence`
is driven by the real-time scripted session (`VoiceScriptPlayer`, 20 ms level
blocks from the fixture audio). Scenarios: **idle** (the companion only),
**cycle** (idle → listening → user speaks → thinking → working → URI speaks →
approval → success, 35.8 s, repeating), **voice** (user and URI turns back to
back). Sizes in logical px: floating 280×380, panel 480×560, workspace 720×460.

**Brain condition.** A local Brain-class model server (`llama-server`,
Qwen3.6-35B-A3B, `-ngl 999`, port 18497) belongs to another session's
adaptive-runtime benchmark, which starts, loads and stops it on its own
schedule. **I did not start or drive a Brain myself:** a 15 GB model on the
shared 16 GB card would have disrupted that benchmark, whose results are
sensitive to exactly this kind of contention. The sampler therefore records,
every sample, any *other* process holding more than 1 GB of VRAM. The matrix
runs (11 short runs, 01:53–02:07 IST) had no GPU-resident Brain at the checks
that were logged. The final 10-minute run (02:35–02:45 IST) overlapped that session's
Brain for 85 % of its samples, which gives an **uncontrolled** Brain-active
measurement (§8.2).

Results (raw JSON and CSV in `evidence/perf/`; `python rnd/voice/summarize_perf.py`):

| run | frames | fps | build p50/p99 ms | raster p50/p90/p99/max ms | frames >16.7 ms | CPU % avg/max | GPU 3D % avg/max | adapter 3D % avg | VRAM MB avg/max | RSS MB start/end | system CPU % avg | other process >1 GB VRAM |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| cycle-lunar-floating | 5763 | 128 | 0.40/1.81 | 3.26/5.48/9.05/52.4 | 24 (0.4%) | 3.1/4.5 | 3.8/5.7 | 4.7 | 126/174 | 136/118 | not sampled | not sampled |
| cycle-lunar-panel | 10204 | 136 | 0.35/1.75 | 3.15/5.80/10.27/72.5 | 98 (1.0%) | 2.9/4.3 | 10.9/22.9 | 12.1 | 180/379 | 116/117 | not sampled | not sampled |
| cycle-lunar-workspace | 5852 | 130 | 0.35/1.54 | 2.82/5.08/8.43/69.3 | 30 (0.5%) | 2.9/4.4 | 5.8/10.3 | 6.6 | 152/294 | 106/115 | not sampled | not sampled |
| cycle-moonlit-panel | 10150 | 135 | 0.33/1.62 | 2.63/4.96/9.04/49.0 | 75 (0.7%) | 2.6/4.2 | 7.3/12.3 | 8.2 | 174/382 | 114/118 | not sampled | not sampled |
| cycle-sakura-panel | 9797 | 131 | 0.35/1.86 | 3.10/5.57/9.62/39.9 | 85 (0.9%) | 3.0/4.5 | 3.4/4.9 | 4.3 | 164/482 | 136/117 | not sampled | not sampled |
| cycle-solar-panel | 10777 | 144 | 0.22/1.29 | 1.48/4.11/7.27/46.0 | 33 (0.3%) | 1.8/3.7 | 4.4/5.8 | 5.2 | 169/450 | 113/118 | not sampled | not sampled |
| idle-lunar-panel | 5915 | 131 | 0.34/2.32 | 2.54/4.42/6.59/47.4 | 3 (0.1%) | 2.6/4.6 | 19.1/24.5 | 20.6 | 133/146 | 112/112 | not sampled | not sampled |
| idle-moonlit-panel | 5939 | 132 | 0.41/2.45 | 2.91/4.68/6.87/86.2 | 6 (0.1%) | 2.8/4.3 | 10.3/22.1 | 11.3 | 128/149 | 112/112 | not sampled | not sampled |
| idle-sakura-panel | 6490 | 144 | 0.28/2.21 | 1.86/4.46/6.81/21.1 | 2 (0.0%) | 2.0/3.1 | 5.9/8.7 | 7.2 | 140/149 | 109/110 | not sampled | not sampled |
| idle-solar-panel | 6453 | 143 | 0.12/0.60 | 0.90/1.20/1.75/47.9 | 2 (0.0%) | 0.9/2.1 | 9.8/13.4 | 11.3 | 146/146 | 114/110 | not sampled | not sampled |
| longrun-cycle-lunar-panel | 85372 | 142 | 0.28/1.51 | 1.77/4.36/9.35/54.6 | 692 (0.8%) | 2.0/4.4 | 9.2/15.0 | 14.5 | 183/478 | 136/131 | not captured | none |
| longrun2-typedbuf-cycle-lunar-panel | 85148 | 142 | 0.17/0.55 | 1.31/2.14/13.74/742.7 | 1528 (1.8%) | 1.1/2.0 | 16.8/64.2 | 23.6 | 184/457 | 111/130 | not captured | max 14.9 GB in 246/288 samples |
| voice-lunar-panel | 5779 | 128 | 0.36/1.48 | 3.46/6.29/11.14/67.0 | 93 (1.6%) | 3.2/4.3 | 4.7/11.9 | 5.5 | 167/440 | 109/115 | not sampled | not sampled |

Reading the numbers:

* Every scenario runs at 128–144 fps on the 144 Hz display (each 5 s window
  ~700–730 frames once settled). Frames over a 60 Hz budget
  (16.7 ms) are 0.0–0.1 % at idle and 0.3–1.6 % in the cycles.
* Raster p50 is 0.9–2.9 ms for the companion alone and 1.5–3.5 ms in the
  cycles; p99 is 1.8–6.9 ms idle and 7.3–11.1 ms in the cycles. At 144 Hz the
  budget is 6.9 ms, so the cycles' p99 frames exceed a 144 Hz budget but stay
  within 60 Hz.
* The slow frames cluster in the 5 s windows that contain a voice transition
  or a session start (first-use of the waveform program, text layout, the
  `SoftDisc` layer). The worst single frame per cycle run was 40–73 ms; for
  the Lunar cycle and voice runs (checked) it fell in the first 5 s window.
* CPU 0.9–3.2 % of the machine (average). Per-process GPU 3D 3–19 %; the most expensive
  steady state is the full-size Lunar companion (idle-lunar 19 %), and voice
  phases are *cheaper* than idle because the companion is drawn small.
* Dedicated VRAM 126–180 MB average, transient peaks up to 482 MB during
  transitions. RSS flat (106–136 MB).

Correction history for this section: the first matrix attempt produced no
reports because the runner passed a relative output path that the app resolved
against its own working directory; the write failed and the app did not exit.
Fixed (absolute path, and the app now exits even if the write fails). In the
second attempt the first Solar cycle run recorded no frames for 30 s (window
not presenting) and reported a misleading 86 fps; it is kept in
`evidence/perf/superseded/` and was re-run. The matrix log file was locked by
my own log watcher after the first entry, so per-run Brain checks for the
middle runs survive only as "none" at the first and last run.

### 8.2 Ten-minute runs and the Brain on the same GPU

Three 10-minute runs of the Lunar cycle (the most expensive companion) at panel
size. The first is superseded: its harness held every `FrameTiming` object and
it overlapped unlabelled foreign load (another session's GPU guard logged a
foreign `llama-server.exe` holding 12.8 GB and system CPU at 50–100 % during
that window); it showed raster stalls of 0.3–1.3 s that could not be attributed.
It is kept in `evidence/perf/superseded/`.

* **`longrun`** (no other process above 1 GB VRAM throughout): 85,372 frames,
  142 fps, raster p50 1.77 / p99 9.35 ms, 0.8 % of frames over 16.7 ms, worst
  frame 54.6 ms in the first 5 s window; no stall after start-up.
* **`longrun2`** (typed-buffer harness; Brain resident in 246 of 288 samples,
  median 14.5 GB, max 14.9 GB). Windows split by what the Brain was doing:

| Condition | 5 s windows | fps median (min) | raster p50 / p99 median ms | frames > 16.7 ms | worst frame |
|---|---|---|---|---|---|
| no Brain resident | 17 | 146 (141) | 1.22 / 3.71 | 0.03 % | 17 ms |
| Brain resident, quiet | 90 | 144 (122) | 1.32 / 2.99 | 0.28 % | 743 ms (one) |
| **Brain generating** (other processes > 25 % of the 3D engine) | 13 | **108 (100)** | **3.53 / 27.2** | **17.2 %** | 59 ms |

**Finding (AMBER): while the local Brain generates on the shared GPU, the
presence drops to ~100–108 fps and about one frame in six misses a 60 Hz
budget — visible stutter.** Resident-but-quiet costs almost nothing. The
companion's own GPU share is small (3–19 %), so this is contention for the
3D engine rather than the presence being heavy, but the presence is what the
user sees stutter. Not measured, because I did not control the Brain: whether
the presence slows the Brain's token rate. Recommended mitigation, *not
implemented* because it could not be verified under a controlled Brain load:
a quality tier that caps the companion's animation to 30 fps and renders it at
reduced resolution while URI is thinking or working (the states in which the
Brain generates), driven by the authoritative state the presence already has.
A controlled test needs coordination with the adaptive-runtime session.

**Memory.** VRAM is flat across ten minutes (first/last 10 % of samples:
175/181 MB and 166/177 MB). Process RSS grows: 111 → 130 MB in `longrun2`
(+19 MB), with the rate roughly halving after the first four minutes (111,
115, 119, 123, 123, 124, 127, 128, 128, 129 MB at one-minute steps). The
harness's own buffers account for about 1 MB of that. **Whether this plateaus
or is a slow leak is not established by a 10-minute run;** it needs a
one-hour soak with a Dart heap snapshot before acceptance (§10).



---

## 9. Integration path (not done here)

A live feed needs an audio owner to emit the events in §3. Nothing in this
branch opens a device.

* **User side:** the process that owns the microphone (the opt-in voice
  adapter, or the dictation recorder which already computes block RMS)
  publishes `AudioLevel(user, rms)` at ~50 Hz plus listening/speech/transcript
  events. The existing adapter's `status.json` maps to `ListeningStarted` /
  `UserTranscript(final)` / `VoiceFailure`, but carries **no level and no
  partials**, so as it stands the waveform would show the honest silent line.
* **URI side:** URI has no reply TTS today (the adapter speaks one fixed
  phrase). A reply path would tap its own playback buffer for
  `AudioLevel(uri, rms)` and forward word boundaries (SAPI already reports
  them, §4) as `UriSpeechProgress`.
* **Shell:** `CompanionPresence` is a drop-in for the area `living_shell.dart`
  gives the orb, but the shell still uses the accepted `EnergyOrb`; adopting
  the companions at all is an open owner decision from the previous phase.
  `UiPresentationController` is unchanged, so authorised Companion/Workspace/
  Dashboard switching is unaffected.
* **Authority:** voice stays input only. Nothing here approves, decides or
  executes; the approval status stays visible during speech.

---

## 10. What is NOT verified

1. **No live microphone and no live URI speech.** All voice evidence uses real
   synthesised speech in scripted sessions. Real-room noise, a real person's
   dynamics, device latency and recogniser partial timing are untested.
2. The "user" voice is a second synthetic voice, not a human.
3. **Brain-active performance is uncontrolled.** One 10-minute run overlapped
   another session's Brain (§8.2) and showed stutter while it generated; no
   controlled Brain load was run, the Brain's own token rate was not measured,
   and the recommended 30 fps / reduced-resolution tier is not implemented.
4. **RSS grows ~19 MB in 10 minutes** with the rate falling; plateau versus
   leak is not established (needs a one-hour soak and heap snapshot).
5. System-wide CPU was not captured (the Windows Processor counter fails on
   this machine, PDH `c0000bb8`); per-process CPU was.
6. One discrete desktop GPU only; no laptop, integrated GPU or high-DPI
   display. Device pixel ratio was 1.0.
7. Screen-reader behaviour was checked by semantics in tests, not with
   Narrator.
8. Not wired into `living_shell.dart`; Companion/Workspace consistency is
   shown by rendering the same presence at the floating, panel and workspace
   sizes, not inside the real shell.
9. No independent review has happened.

---

## 11. Evidence index

| Path | What |
|---|---|
| `docs/companions/voice/evidence/run1/` | first real captures: square sky box, thin waveform, saturated level, harness bleed |
| `docs/companions/voice/evidence/run2/` | elliptical waveform, per-stream reference, soft disc |
| `docs/companions/voice/evidence/run3/` | companion enlarged to its space |
| `docs/companions/voice/evidence/run4/` | final: 100 frames + `sheet_*.png`, `capture_log.txt` |
| `docs/companions/voice/evidence/perf/superseded/` | the invalid Solar cycle run and the first 10-minute run, kept as correction history |
| `docs/companions/voice/evidence/perf/` | per-run JSON (frame timings, RSS) and CSV (CPU, GPU 3D, dedicated VRAM), `matrix_log.txt` |
| `rnd/voice/` | fixture generator, metrics, sheets, perf runner and sampler |
| `uri_ui/test/living/voice_presence_test.dart` | 44 tests |

Evidence size policy (as in the previous phase): run 4 raw frames are kept at
capture resolution; superseded runs 1-3 raw frames were downscaled by half
after review, and their contact sheets and logs are untouched. The
byte-identity check is reported from each run's own log, taken before
downscaling.
