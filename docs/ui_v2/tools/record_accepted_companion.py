from pathlib import Path
import json
r=Path('.'); d=r/'docs/ui_v2'
p=d/'tools/record_working_state.py';s=p.read_text(encoding='utf-8').replace("'baseline':git('rev-parse','HEAD')", "'baseline':'1b5423bc15fd7e5da9161c862cf839925da9f2eb'").replace("'candidate_committed':False", "'candidate_committed':True, 'candidate_commit':'See git HEAD and external lifecycle receipt; local snapshot only'").replace("'PROPOSED: HTML motion preview only'", "'IMPLEMENTED candidate: existing paced clock, 180s orbit; proximity/focus/chat/reduced-motion pause; native behavior NOT VERIFIED'").replace("'Three proposed options; selection pending'", "'OWNER APPROVED 2026-10-13: Detached chat, reference evidence/reference/companion-approved.jpg'").replace("'NOT RUN on current changing candidate'", "'Fresh exact-commit lifecycle review pending; unavailable reviewer must not imply acceptance'").replace('faded etched steel inlay','faded unframed steel engraving');p.write_text(s,encoding='utf-8')
p=d/'00_PLAN_AND_ACCEPTANCE_CRITERIA.md';s=p.read_text(encoding='utf-8').replace('Chat opens the shared Workspace conversation until the owner selects a compact disclosure option.', 'Owner selected Detached chat on 2026-10-13: Chat toggles a compact conversation using the same AppState/OI and LivingComposer; closing it retains the draft and turn.').replace('Status: implementation in progress; no independent acceptance, integration or deployment.', 'Status: isolated implementation candidate; owner approved the visual reference, not this implementation. No independent acceptance, integration or deployment.');p.write_text(s,encoding='utf-8')
p=d/'COMPANION_OPTIONS.md';s=p.read_text(encoding='utf-8').replace('Status: proposed visual directions, awaiting selection.', 'Status: owner selected **Detached chat** on 2026-10-13; exact reference: [approved image](evidence/reference/companion-approved.jpg). Other directions are historical alternatives.');a=s.index('## Implementation state');s=s[:a]+'''## Implemented candidate

The approved detached chat now uses the same AppState or OI conversation and LivingComposer as Workspace. Chat toggles disclosure; closing it preserves the draft and conversation. Review navigates to the existing task review, with no automatic decision. Voice actions are generated only when the existing service supports them. Dashboard stays available. Idle listening draws short marks; actual RMS level drives bar height. This is a level visualization, not a frequency spectrum.

Floating controls now use circular icon-and-label buttons. Sparse brass arcs follow the approved image. Normal-size controls orbit once in 180 seconds, labels upright, on the existing Companion frame clock with geometry updates capped at 10Hz. The existing Solar renderer/shaders are unchanged. Proximity within 80 logical pixels of the orbit bounds, pointer interactions, open chat, composer focus, active voice, reduced motion and large text stop orbital travel. Departure holds it for 1.5 seconds. Hidden windows suspend the shared clock. At large text or more than four contextual actions, stationary readable controls replace orbiting circles.

Windows gets only own-window cursor coordinates; no global hook, desktop screenshot or microphone observation is added. The native region combines the actual Companion ellipse, circular buttons, narrow arc strokes, waveform region and the visible chat rectangle. Transparent gaps are excluded from the region. Native compositing/cross-application click-through and multi-DPI/monitor behavior remain NOT VERIFIED.

## Isolation and launch

Worktree: `C:\\Users\\cheta\\Development\\uri-ui-v2`; branch: `ui/companion-v2-visual-qualification`. Accepted base: `1b5423bc15fd7e5da9161c862cf839925da9f2eb`. A local candidate snapshot is separate from independent acceptance. No merge, push, deployment or live-server replacement.

From `uri_ui`:

```powershell
# Explicit offline fixture preview, no real authentication demonstration.
flutter run -d windows --no-pub -t lib/main_v2_preview.dart
# Real bootstrap/authentication entry. No owner-server live testing was done.
flutter run -d windows --no-pub -t lib/main_v2.dart
```

The offline entry does not open a microphone or fabricate voice availability; its Voice action is absent until a supported service exists. Capture fixtures separately exercise all three approved controls, with audio events injected and labelled simulated. Wake phrase “oii URI” is unsupported by the accepted voice baseline.

See [current evidence](CURRENT_UI_EVIDENCE.md), [visual comparison](companion-review.html) and [qualification details](VISUAL_QUALIFICATION.md). Full implementation verdict: **NOT READY — BLOCKERS**: native/runtime qualification, formal independent acceptance and visual discrepancy disposition remain outstanding. Owner approval of the supplied image resolves the design choice; it does not silently qualify code.
''';p.write_text(s,encoding='utf-8')
(d/'CURRENT_UI_EVIDENCE.md').write_text('''# Current isolated UI evidence — 13 October 2026

Accepted canonical development base: `1b5423bc15fd7e5da9161c862cf839925da9f2eb`, rechecked from `uri-repo/integration/git-sync-20261008`. Candidate branch: `ui/companion-v2-visual-qualification`; worktree `C:/Users/cheta/Development/uri-ui-v2`. Source repositories and other dirty worktrees were left unchanged.

| Surface | Implemented candidate | Automated evidence | Native/live evidence | Integration / deployment |
|---|---|---|---|---|
| Existing Companions | Eleven actual procedural 2D designs: four Living identities and seven Classic variants; existing shader/renderers preserved | Identity/theme, gallery and state tests; individual renderer captures | No true 3D rotation support | None / none |
| Themes | Exact Ivory Foundry, Snow Archive, Ash & Limestone; original-theme following or explicit independent interface theme | Contrast, combinations, legacy/fallback and persistence tests | Three actual engine dashboards/login captures | None / none |
| Companion | Approved detached chat; circular contextual local-A2UI actions; original single/double click recognition and local acknowledgement | Service submission once, no automatic listening, draft retention, double-click suppression | Transparent RGBA engine export; desktop compositor NOT VERIFIED | None / none |
| Native overlay | Frameless, separate bounds restoration, ellipse/button/arc/chat union, monitor work-area clamp, own-window cursor proximity | DTO/adapter tests and 96-DPI native region inspection in capture log | Cross-application clicking, multiple monitors and DPI changes NOT VERIFIED | None / none |
| Conversation | Shared AppState/OI and LivingComposer; compact classic bubbles; OI streamed/errors retained; review remains explicit | Shared-service fixture send/close/navigation tests and existing OI worker tests | No live Brain/auth/server/microphone exercised | None / none |
| Motion | 180-second button orbit, upright labels; existing paced clock; proximity/open-chat/focus/voice/reduced-motion suspension | Full-circle geometry samples and widget pause tests; 360x560/440x680 at 200% text | GPU/VRAM/native motion performance NOT MEASURED | None / none |
| Login/bootstrap | URI typography without logo; existing APIs, password obscuring, duplicate guard and form validation | Form/error callback tests; three themed engine captures; real entry build | No owner login, credentials or sessions used | None / none |
| Dashboard | Actual Solar, six functional panels, brass conduits, all preserved navigation and bottom-right faded engraving | Responsive tests; three themes and target-size engine exports | Owner comparison supplied; new code not visually accepted | None / none |

Current capture folder: `evidence/accepted-companion/`, authoritative `capture_log.txt` and `result.json`. Older folders are iteration history. The harness uses the real Windows Flutter engine with fixture-only data and `RenderRepaintBoundary.toImage`, not desktop compositor screenshots. Voice events are injected; no private conversations/audio are used.

Analysis, full-suite logs and exact results are in `WORKING_STATE.json`, `analyze_accepted_companion.txt` and `regression_accepted_companion.jsonl`. A unit/widget test is not independent acceptance or deployment evidence. Frozen-path delta against the accepted base remains zero; the historical frozen checker already reports two unchanged baseline deviations (120/121 checkpoint hashes match, not 121/121).

Missing/unverified: wake phrase detection, live native transparency/hit testing, device/audio/auth/runtime journeys, DPI/multiple monitors, performance measurement and fresh exact-commit independent acceptance. No API, privilege, Core/security or production change was introduced.
''',encoding='utf-8')
(d/'VISUAL_QUALIFICATION.md').write_text('''# Visual qualification — isolated candidate

The owner approved [Detached chat](evidence/reference/companion-approved.jpg) on 13 October 2026. This supersedes the pending-chat choice. Dashboard authority remains [the supplied image](evidence/reference/owner-current.jpg) plus the three approved theme captures in `evidence/reference/`.

Current images are `evidence/accepted-companion/`; earlier folders preserve iterations. Compare [Companion](companion-review.html) and [dashboard](dashboard-review.html). All Flutter images are actual Windows engine RGBA exports with simulated data, not native desktop-compositor screenshots.

## Repairs against the references

- Replaced rectangular text actions with circular, upright icon/label controls; measured labels and kept keyboard/large-text fallback.
- Adjusted sparse orbital arcs to the five reference sectors; retained the real Solar renderer.
- Detached conversation opens below the waveform, with a close action, short bubbles and the shared service composer. It retains draft/conversation state and does not approve actions.
- Added paced audio-level bars below the Companion; silence remains short marks. Listening/speaking states come from the existing voice controller.
- Implemented slow motion and pointer/chat/focus/voice/reduced-motion holds; native hit regions follow the same button geometry.
- Removed the puppy background, plate outline and caption. The bottom-right engraving is theme-toned, unframed, alpha-cut and faded, with space reserved so the composer stays usable. Original source is preserved; generative background removal reconstructed some linework. Exact prompt is in `evidence/portrait/EDIT_PROMPT.md`.

## Remaining visual differences

| Severity | Difference / disposition |
|---|---|
| Medium | Reference is 828x1280; native Companion is 440x680 or constrained 360x560. Buttons/14px labels and conversation area are larger proportionally for readability and interaction. Exact scaled typography has not been claimed. |
| Medium | The reference sun is a generated visual. Actual procedural Solar is reused, so phase/filament/halo texture differs. No replacement model or renderer was added. |
| Medium | Real offline/error/review/streaming text can require scrolling. The reference contains only two short sample messages. |
| Medium | The deliberately stronger artwork fade changes engraving linework and contrast; dashboard artwork regional SSIM was 0.494 in the prior capture. |
| Unverified | Native compositing, cross-app clicking, multiple DPI/monitors, native motion and GPU/VRAM cost require future qualification. |

Dashboard comparison: `tools/compare_owner_reference.py` computed an eight-region mean luminance SSIM of approximately 0.889, with seven layout regions 0.928–0.970. This exceeds an 0.80 screenshot-comparison checkpoint only; it is not a literal design-accuracy percentage or acceptance. Full bounds, hashes and artwork discrepancy are retained in `evidence/engraving-final/reference_comparison.json`. The Companion reference has different physical dimensions and renderer texture; no unsupported claim of 80% native fidelity is made.

## Verification boundary

Full source gate logs and capture success are recorded separately. Fixtures test single/double click, one submit, no implicit microphone opening, independent identity/theme, gallery isolation, 200% text, full orbit clearance and pause behavior. Native 96-DPI region inspection is recorded in the capture log. These do not prove desktop click-through or live backend/device behavior. The reviewer must be fresh and pinned to the final candidate SHA. No merge, push, production integration or deployment is authorized.

**Full implementation verdict: NOT READY — BLOCKERS.** The visual reference is approved; the code still requires independent/native/runtime qualification and disposition of the stated visual differences. The isolated preview and comparison images are available for review.

Skills used: existing Flutter widget-test guidance, Anthropic `frontend-design`, Vercel `web-design-guidelines` and built-in imagegen. The installed button/design skills are local at `C:/Users/cheta/.codex/skills/`. No new runtime package or shader dependency was added.
''',encoding='utf-8')
(d/'companion-review.html').write_text('''<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>URI — approved Companion comparison</title><style>body{margin:0;background:#f5f4ef;color:#292a27;font:15px system-ui}header{padding:24px;max-width:1200px;margin:auto}h1{font-size:24px;margin:0 0 12px}main{display:flex;flex-wrap:wrap;gap:24px;padding:0 24px 32px;justify-content:center}figure{margin:0;flex:0 1 440px}figcaption{padding:12px 0;font-weight:600}img{display:block;width:100%;height:auto}.capture{background:#72726f}p{max-width:1000px;line-height:1.5}button{font:inherit;padding:10px 16px;min-height:44px;background:#fffefa;color:#292a27;border:1px solid #858674;border-radius:8px}button:focus-visible{outline:3px solid #776541;outline-offset:3px}.controls{display:flex;gap:8px;flex-wrap:wrap}a{color:#665331}</style><header><h1>Approved Detached chat → isolated Flutter</h1><p>Left: owner-approved reference. Right: actual Flutter Solar and shared chat with fixture data. The gray on the right is the comparison page behind the transparent PNG; it is not a Companion window background.</p><div class="controls"><button data-image="companion-listening">Listening + chat</button><button data-image="companion-detached-chat">Chat, voice idle</button><button data-image="companion-action-launcher">Floating actions</button><button data-image="companion-borderless-canvas">Collapsed</button><button data-image="companion-floating-360">360 × 560</button></div><p>Native size and readable controls differ proportionally from the tall reference. Runtime/device/native compositing qualification is outstanding. <a href="VISUAL_QUALIFICATION.md">Evidence and differences</a> · <a href="dashboard-review.html">Dashboard / three themes</a></p></header><main><figure><figcaption>Approved reference · 828 × 1280</figcaption><img src="evidence/reference/companion-approved.jpg" alt="Owner approved Solar Companion with Chat, Dashboard, Voice, waveform and detached conversation"></figure><figure><figcaption id="caption">Flutter · Listening + chat · 440 × 680 · fixtures</figcaption><img class="capture" id="actual" src="evidence/accepted-companion/companion-listening.png" alt="Actual isolated Flutter Companion capture"></figure></main><script>for(const button of document.querySelectorAll('button'))button.addEventListener('click',()=>{document.querySelector('#actual').src='evidence/accepted-companion/'+button.dataset.image+'.png';document.querySelector('#caption').textContent='Flutter · '+button.textContent+' · fixtures';});</script></html>''',encoding='utf-8')
# no integration under any condition
cfg=json.loads(Path('docs/dev_workflow/lifecycle/TEMPLATE.json').read_text(encoding='utf-8'))
cfg.update(milestone='URI-UI-V2-visual-qualification-20261013',repo=str(Path('.').resolve()),canonical_url='https://github.com/sche004-cyber/Uri',candidate={'branch':'ui/companion-v2-visual-qualification','worktree':str(Path('.').resolve())},state_dir='C:/Users/cheta/Development/uri-ui-v2-lifecycle-20261013',acceptance_criteria_file='docs/ui_v2/00_PLAN_AND_ACCEPTANCE_CRITERIA.md',review_focus=['Preserve auth/runtime/approval boundaries and existing Companion renderer','Shared detached chat, circular A2UI controls, theme independence and native motion','Validate truthful source and screenshot evidence; no integration/deployment'],permitted_paths=['uri_ui/**','docs/ui_v2/**'],gates=[{'id':'flutter','kind':'flutter','cwd':'uri_ui','cmd':['C:/Users/cheta/flutter/bin/flutter.bat','test','--no-pub'],'timeout_s':3600},{'id':'analysis','kind':'command','cwd':'uri_ui','cmd':['C:/Users/cheta/flutter/bin/flutter.bat','analyze','--no-pub','--no-fatal-infos'],'timeout_s':600},{'id':'frozen','kind':'command','cmd':['{python}','scripts/ws_frozen_check.py'],'timeout_s':600}],reviewer={'provider':'claude_cli','timeout_s':180},implementer={'provider':'claude_cli','timeout_s':180},integration={'mode':'none','authorized':False})
cfg['baseline']['expect']='1b5423bc15fd7e5da9161c862cf839925da9f2eb';cfg['regression_runners']=[{'suffix':'_test.dart','cwd':'uri_ui','cmd':['C:/Users/cheta/flutter/bin/flutter.bat','test','--no-pub']}]
(d/'lifecycle.json').write_text(json.dumps(cfg,indent=2),encoding='utf-8')
