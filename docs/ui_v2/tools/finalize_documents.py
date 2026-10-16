"""Refresh final evidence pointers without changing source or image assets."""
from pathlib import Path
import hashlib
import json
import subprocess

repo = Path(__file__).resolve().parents[3]
d = repo / 'docs/ui_v2'
base = '1b5423bc15fd7e5da9161c862cf839925da9f2eb'
companion = json.loads((d/'evidence/final/companion_comparison.json').read_text())
dashboard = json.loads((d/'evidence/final/dashboard_comparison.json').read_text())
cm, dm = companion['mean_ssim'], dashboard['mean_ssim']
for name in ['CURRENT_UI_EVIDENCE.md', 'dashboard-review.html']:
    p = d/name
    s = p.read_text(encoding='utf-8-sig').replace('evidence/delivery/', 'evidence/final/')
    s = s.replace('analyze_final_framing.txt', 'analyze_final.txt')
    s = s.replace('regression_delivery.jsonl', 'regression_final.jsonl')
    p.write_text(s, encoding='utf-8')
p = d/'companion-review.html'
p.write_text(p.read_text(encoding='utf-8-sig').replace('0.633;', f'{cm:.3f};'), encoding='utf-8')
p = d/'COMPANION_THEME_SPEC.md'
p.write_text(p.read_text(encoding='utf-8').replace(
    'The V2 explicit selector presents the three approved choices;',
    'The V2 explicit selector includes the three approved choices and compatible legacy themes;'), encoding='utf-8')
p = d/'INTERACTION_ACCESSIBILITY_PERFORMANCE.md'
s = p.read_text(encoding='utf-8').replace(
    'Normal controls are 80px circular icon-and-label targets with 14px labels.',
    'Native compact controls are 80px circular icon-and-label targets with 14px labels; the 828x1280 reference-size layout uses approximately 99px circles with larger proportional icons.')
s += '\nEscape closes the detached conversation first, then collapses floating controls. It preserves the shared draft and never cancels a runtime task or speech session. From other modes it retains the existing Companion navigation shortcut.\n'
p.write_text(s, encoding='utf-8')
p = d/'00_PLAN_AND_ACCEPTANCE_CRITERIA.md'
s = p.read_text(encoding='utf-8').replace(
    'Orbital motion is currently demonstrated in an explicitly simulated HTML preview; native implementation is not yet qualified.',
    'Orbital motion is implemented in Flutter on the existing clock and also demonstrated by the historical simulated HTML preview; native behavior is not yet qualified.')
s = s.replace('Explore three chat disclosure alternatives before selecting one.',
              'Three chat alternatives were explored; the owner selected Detached chat on 2026-10-13.')
p.write_text(s, encoding='utf-8')
(d/'VISUAL_QUALIFICATION.md').write_text(f'''# Visual qualification — isolated candidate

The owner approved [Detached chat](evidence/reference/companion-approved.jpg) on 13 October 2026. Dashboard authority is [the supplied image](evidence/reference/owner-current.jpg) plus the three approved theme studies. Approval applies to those references, not this new code.

Current captures: `evidence/final/`. [Companion side-by-side](companion-review.html) · [dashboard / three themes](dashboard-review.html). These are actual Windows Flutter engine RGBA exports with fixtures, not desktop-compositor screenshots. The comparison-page gray is outside the application. No private conversations, credentials or microphone recordings were used.

## Reference repairs and remaining differences

Circular floating actions now have proportional icons, upright labels and sparse visible brass arcs. The actual Solar renderer remains central. Voice level bars sit below the complete orbital path; detached shared chat sits below them. Chat close/Escape preserve drafts; no decorative interaction authorizes work. The dashboard retains six conduit-linked destinations and a background-free, unframed, faded engraving at bottom right. No logo or new renderer was introduced.

| Severity | Difference / qualification |
|---|---|
| Medium | The generated sun reference and actual procedural Solar have different filament, corona, hue and phase details. Existing shader/rendering identity was preserved. |
| Medium | Compact 440x680 and 360x560 adaptations retain 80px controls and readable labels; they are larger proportionally than a downscaled reference. The matching 828x1280 layout is also captured. |
| Medium | Actual chat font, bubble padding, composer spacing and icons still differ. Long/streaming/error/review content needs scrolling beyond the two-line sample. |
| Medium | The requested stronger artwork fade changes linework and contrast; generative background removal reconstructed some linework. Original source and exact edit prompt are preserved. |
| Unverified | Native compositor, cross-application hit testing, movement, DPI/monitors, hardware audio, real auth/runtime and GPU/VRAM/frame cost. |

## Reproducible screenshot checkpoint

`tools/compare_final_references.py` reads the original reference and current capture without modifying either image. It computes equal-weight local luminance SSIM over six Companion regions and eight dashboard regions. Transparent Companion pixels are composited over comparison gray only in memory. The Companion comparison uses the exact reference viewport, 828x1280. The dashboard reference is resampled from 1280x889 to 1440x1000. Bounds and SHA256 values are in the JSON reports.

- Dashboard: **{dm:.3f}**, exceeding the 0.80 screenshot checkpoint ([report](evidence/final/dashboard_comparison.json)).
- Companion: **{cm:.3f}**, **below 0.80** ([report](evidence/final/companion_comparison.json)).

This metric is not a literal percentage of design accuracy or visual acceptance. The owner's requested 80% Companion fidelity is **not established**. Earlier 440x680 comparison measured 0.419; older reports remain iteration history. Improving geometric resemblance must not replace the approved working Companion with an imitation.

## Verification and verdict

`regression_final.jsonl`, `analyze_final.txt`, `build_real_final.txt`, `build_preview_final.txt` and `WORKING_STATE.json` record available gates. Capture `result.json` reports success, with fixture-only data and desktop_compositing_verified=false. Native region inspection at 96 DPI reports cornerHit=false for collapsed/expanded layouts; this does not prove clicking through into unrelated apps.

**NOT READY — BLOCKERS.** The Companion screenshot checkpoint, native/live/performance qualification and fresh exact-commit independent acceptance remain outstanding. The isolated preview is available for owner inspection. No push, merge, production integration or deployment occurred.

Skills applied: Flutter widget-test guidance; installed Anthropic frontend-design and Vercel web-design-guidelines; imagegen for the requested cutout; repository uri-development-lifecycle for exact-commit review. No new runtime renderer/package dependency was added.
''', encoding='utf-8')
(d/'DISCOVERY_REPORT.md').write_text(f'''# Discovery report — actual Companion baseline

Canonical independently accepted development pin: `{base}`, remote `uri-repo`, branch `integration/git-sync-20261008`; rechecked on 2026-10-13. The original uri-agent checkout is an older dirty line. Work is confined to `C:/Users/cheta/Development/uri-ui-v2`, branch `ui/companion-v2-visual-qualification`. Office M2 and experimental Harness/Console overlays are separate candidates and were not integrated.

## Existing renderer inventory

| Identity / actual display name | Existing implementation |
|---|---|
| Solar | companion_solar.frag |
| Sakura | companion_sakura.frag |
| Lunar | companion_lunar.frag |
| Moonlit Blossom | companion_moonlit.frag |
| Fluid Plasma | EnergyOrb / nebula |
| Aurora Vortex | EnergyOrb / halo |
| Particle Intelligence | EnergyOrb / swarm |
| Holographic Atmosphere | EnergyOrb / glass |
| Sun / Flow | EnergyOrb / flow |
| Neural Filaments | EnergyOrb / mesh |
| Electric Core | EnergyOrb / energy |

Source: `uri_ui/lib/living/companion/companion_orb.dart`, `energy_orb.dart`, `living_companion.dart`, `companion_preferences.dart`, existing shader assets and frame clock. Discovery found eleven renderable designs across two historical families, rather than relying on the owner-reported approximate count. A catalog adapter exposes them as one Companion system. No shader or EnergyOrb renderer was changed; Solar gets presentation-only framing in compact mode. The actual procedural designs are not rotatable 3D objects.

Shared state projection supports unavailable, idle, listening, thinking, speaking, working, awaitingApproval, success and error. Existing expression parameters/shader uniforms, quality/frame-rate controls, reduced effects and hidden-window suspension remain the baseline. Some source comments say voice is mock-only; later call paths through LiveVoiceService/VoiceInteractionController supersede those historical comments. No live device verification was performed.

Owner-reported native transparency/speech behavior was checked against the pin. The inspected accepted adapter primarily resized windows and exposed local poke/text acknowledgement. Candidate transparency/frameless hit regions and optional local acknowledgement speech were added in isolated UI/native code; this is not evidence that all reported desktop behavior was already verified in the accepted pin. Existing single/double-tap arbitration and shared conversation/presentation controllers were reused.

Classic HTTP, paired/supervised worker, integrated OI runtime, scheduler and Office dependencies remain distinct. No runtime API, authority or grant was added. Login/bootstrap/session handling stays behind real gates. The optional worker entry requires an explicitly isolated manifest; it was not launched. The offline preview is fixture-only and cannot demonstrate successful authentication or real execution.

The 35-ID inventory and matrix bound current traceability. They do not assert an exhaustive legacy control/unreachable-route audit. Existing screens remain accessible; Office and experimental Console functionality is not labelled integrated. Frozen UI/Core/security paths have zero candidate delta against the accepted pin. The historical frozen checkpoint already fails in the accepted baseline: 120/121 hashes match, with server.py drift and two historical protected-path deviations. No checker was weakened.

See DESIGN_SOURCE_INVENTORY.json, COMPANION_THEME_SPEC.md and CURRENT_UI_EVIDENCE.md for exact references and separate implemented/tested/recorded/integration/deployment status.
''', encoding='utf-8')
(d/'HANDOFF.md').write_text(f'''# URI UI V2 — isolated review handoff

**NOT READY — BLOCKERS.** The owner-approved reference is implemented as an isolated candidate, not independently accepted or integrated. Companion screenshot similarity is {cm:.3f} against the 0.80 checkpoint; dashboard is {dm:.3f}. Native desktop/device/live runtime/performance qualification remains unverified. Reviewer availability/status is recorded by the external lifecycle receipt, never inferred from unit tests.

Worktree: `C:/Users/cheta/Development/uri-ui-v2`  
Branch: `ui/companion-v2-visual-qualification`  
Accepted base: `{base}`  
Exact local snapshot: run `git rev-parse HEAD` in this worktree; the external lifecycle report pins that SHA. No canonical push, merge or deployment is authorized.

## Review evidence

- [Companion comparison](companion-review.html): actual Solar, floating Chat/Dashboard/Voice, waveform and detached shared conversation. Smaller native layouts also included.
- [Dashboard comparison](dashboard-review.html): all three approved palettes, six linked destinations and faded artwork.
- [Visual differences and gate boundaries](VISUAL_QUALIFICATION.md), [current functionality](CURRENT_UI_EVIDENCE.md), [discovery](DISCOVERY_REPORT.md), [coverage](FUNCTIONAL_COVERAGE_MATRIX.md), [inventory](SCREEN_AND_FUNCTION_INVENTORY.md), [machine ledger](FUNCTIONALITY_LEDGER.json).
- `evidence/final/`: actual engine exports for all eleven Gallery designs, login/themes, dashboard/responsive layouts and Companion states; fixture-only data. `result.json` and `capture_log.txt` record capture and 96-DPI native-region facts.
- `WORKING_STATE.json`, `regression_final.jsonl`, `analyze_final.txt`, real/preview build logs and `frozen_candidate_delta.json` record available checks. Five suite skips and three baseline analysis infos are explicit.

## Launch later

Use this worktree only. Do not launch or replace an owner server. The debug executable currently contains the offline preview; rebuilding another entry replaces that local binary only.

```powershell
Set-Location C:\\Users\\cheta\\Development\\uri-ui-v2\\uri_ui
& C:\\Users\\cheta\\flutter\\bin\\flutter.bat run -d windows --no-pub -t lib/main_v2_preview.dart
```

The offline entry starts on Dashboard, uses simulated service data and isolated in-memory preferences, opens no microphone and offers no unavailable Voice action. It is for visual inspection, not authentication/execution proof. Use Settings → Companions for the live isolated renderer viewer; Apply/Cancel control preference changes. Click the Companion to reveal controls; Chat toggles detached chat; double click opens Dashboard. Escape closes chat first and then floating controls. Motion stops near the pointer, on chat/focus/voice, reduced motion and hidden windows.

For a separately prepared test service/account, the real bootstrap/auth entry is `lib/main_v2.dart`. It preserves authentication; no owner login or active server was used here. `lib/main_v2_integrated.dart` is an optional test-worker entry requiring URI_V2_CLIENT_MANIFEST under this worktree/work/ui_v2; no worker was spawned and no runtime qualification is claimed. Wake phrase detection is unsupported by the inspected baseline.

Read-only HTML comparisons: `python docs/ui_v2/tools/serve_options.py` from the worktree, then `http://127.0.0.1:8137/companion-review.html`. An existing preview server may already occupy that port; reuse it. This serves documentation only and starts no URI backend.

External lifecycle evidence: `C:/Users/cheta/Development/uri-ui-v2-lifecycle-20261013/REPORT.html` and receipt/state files. The fresh reviewer must be available and exact-commit evidence valid before any claim of independent acceptance. No integration step belongs to this task.
''', encoding='utf-8')
source = json.loads((d/'DESIGN_SOURCE_INVENTORY.json').read_text(encoding='utf-8'))
source['current_capture'] = 'evidence/final'
source['comparison_reports'] = ['evidence/final/companion_comparison.json', 'evidence/final/dashboard_comparison.json']
(d/'DESIGN_SOURCE_INVENTORY.json').write_text(json.dumps(source, indent=2), encoding='utf-8')
rows = []
for line in (d/'SCREEN_AND_FUNCTION_INVENTORY.md').read_text(encoding='utf-8').splitlines():
    if line.startswith('| UI-'):
        v = [x.strip() for x in line.strip('|').split('|')]
        rows.append(dict(zip(['id', 'entry_controls', 'source', 'dependency', 'implementation', 'acceptance_scenario'], v)))
(d/'FUNCTIONALITY_LEDGER.json').write_text(json.dumps({
    'baseline': base, 'revision': 'local candidate Git HEAD / external lifecycle receipt',
    'scope': '35 major implementation surfaces; exhaustive legacy per-control audit incomplete',
    'test_evidence': 'FUNCTIONAL_COVERAGE_MATRIX.md and raw gate logs',
    'recorded_verification': 'CURRENT_UI_EVIDENCE.md and evidence/final',
    'independently_accepted': False, 'integration': 'none', 'deployment': 'none', 'rows': rows,
}, indent=2), encoding='utf-8')
# Candidate delta is checked against the accepted pin, distinct from historical drift.
import sys
sys.path.insert(0, str(repo))
from scripts.ws_frozen_check import PROTECTED
changed = subprocess.check_output(['git', '-C', str(repo), 'diff', '--name-only', base], text=True).splitlines()
changed += subprocess.check_output(['git', '-C', str(repo), 'ls-files', '--others', '--exclude-standard'], text=True).splitlines()
hits = [p for p in changed if p.startswith(PROTECTED) or p in PROTECTED]
(d/'frozen_candidate_delta.json').write_text(json.dumps({'baseline': base, 'new_protected_changes': hits, 'ok': not hits}, indent=2), encoding='utf-8')
print(json.dumps({'ledger_rows': len(rows), 'companion_ssim': cm, 'dashboard_ssim': dm, 'protected_delta': hits}))
