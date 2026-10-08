# URI Solar Orb — visual R&D report

Date: 2026-10-08
Branch: `phase/orb-solar-rnd` (worktree `C:\Users\cheta\Development\uri-orb-solar`)
Base: `569cf7c` (`phase/ui-living-companion`)
Status: prototypes complete, direction recommended, **not merged and not wired into the app**

---

## 1. Acceptance criteria (defined before the work)

A result is acceptable only if all of these hold:

1. At least three meaningfully different prototype directions exist, each rendered and inspected — not described.
2. Each prototype renders in real time from source that can reach production, not an offline render.
3. The orb is not clipped to a disc: corona, flares and embers occupy the space around it.
4. Palette is solar (red → orange → amber → gold → white-hot) with no muddy brown and no cyan.
5. Defects are found by inspecting rendered output, named concretely, and either fixed or disclosed.
6. Runtime cost is measured with a real GPU timer, not estimated.
7. The recommended path is validated at least as far as "the production toolchain accepts it".
8. All work is isolated from accepted/frozen URI branches.

Criteria 1–8 are met, with the limits recorded in §8.

---

## 2. Baseline (what exists today)

`phase/ui-living-companion` ships `uri_ui/shaders/orb_core.frag`, a 95-line Flutter
`FragmentProgram` with three styles, driven by `energy_orb.dart`.

Primary evidence, read directly from that branch:

- Line 68: `if (r > 1.0) { fragColor = vec4(0.0); return; }` — the shader **hard-discards
  everything outside the disc**. Flames, flares and embers outside the orb are not
  "missing"; they are structurally impossible in that shader.
- Noise is value noise over a `sin(dot())` hash (lines 26–45), which is blurry by
  construction and is the source of the foggy look.
- There is no ember layer, no corona structure and no flare geometry.
- `docs/ui_phase/references/owner_orb_reference_2026-10-08.jpg` is the **cyan/blue**
  direction. This task explicitly excludes cyan, so that reference is superseded.

Rendered baseline: `docs/ui_phase/screenshots/orb_energy_working.png` on that branch.

---

## 3. Tools: selected, rejected, and why

| Tool | Decision | Reason |
|---|---|---|
| WebGL2 / GLSL ES 3.0 prototype harness | **Built and used** | Same fragment maths as Flutter's shader, so iteration transfers 1:1. Sub-second edit→see loop. |
| Claude built-in browser pane | **Used** | Renders the harness and returns screenshots, so every judgement below was made by looking at output. |
| `EXT_disjoint_timer_query_webgl2` | **Used** | The only way to get true GPU time in-browser. |
| Flutter 3.47.2 shader toolchain | **Used** | Compiles the production `.frag`. Verified, see §7. |
| Node 24 | **Used** | Generates the Flutter `.frag` from the prototype source so the two cannot drift. |
| Blender | **Not installed** | Not installed on this machine (verified: no `blender` on PATH, no `C:\Program Files\Blender Foundation`). A ~400 MB install plus headless-render setup would produce offline path-traced stills that **cannot** transfer to a 60 fps Flutter fragment shader — none of the Cycles volumetrics, mesh lights or shader nodes have a real-time equivalent here. The browser-shader loop gives faster iteration *and* directly shippable code. If you want cinematic key art (marketing stills, a loading video) rather than a live orb, Blender becomes worth installing; say so and it is a separate task. |

No tool was blocked. The Blender decision is mine, on cost/benefit, and is reversible.

---

## 4. Techniques that made the difference

These are the specific changes that moved the result, each confirmed by looking at
rendered output:

1. **Separate temperature from brightness.** v1 drove colour and intensity from one
   value, which clipped the entire disc to flat white. Splitting them is what lets the
   palette show at all.
2. **Filmic tonemap (ACES).** Lets the core run above 1.0 and roll off to white instead
   of clipping. The single biggest lever between "premium" and "cheap".
3. **Piecewise fire ramp with a saturation floor.** As brightness falls, saturation rises
   toward red. Mixing orange toward a desaturated dark is exactly what produces muddy
   brown; this ramp cannot.
4. **Gradient noise, domain warping, curl advection.** Replaces value-noise fog with
   structure that reads as moving fluid.
5. **Directional (radial) smear.** Multi-tap max-combine along the radial axis elongates
   structures outward, so they read as tongues of flame instead of blobs.
6. **A varying effective radius.** The flame boundary varies with angle and time, so the
   outline is not a circle. This is the single biggest lever away from "glowing ball".
7. **Analytic ember field.** Grid-hashed cells, each with its own phase, size, flicker and
   lateral waver, cooling as they rise. No CPU particles, no overdraw, one draw call.
8. **Explicit arc geometry.** Parametric magnetic loops on rise-hold-decay lifecycles.
   This is the only thing in the set that reads as *intentional* rather than merely
   turbulent, and it is what makes the orb feel aware.
9. **Incommensurate periods everywhere.** Breathing, arc lifecycles and ember waver all
   use mutually irrational periods, so the ensemble never visibly repeats.

---

## 5. The four directions

Live, interactive: **https://claude.ai/artifact/QaUr8s8AjPyAGDZ9cnzpbk**
Stills: `docs/orb_solar/evidence/captures/` (1100×760 PNG, one per direction/state).

| | What it is | Strong | Weak |
|---|---|---|---|
| **A — Solar Intelligence** | Composed star core: warped mottling, fibril crests, limb darkening, clumped corona streamers, sparse embers. | Most composed; cheapest. | Silhouette stays circular, so at idle it is the closest of the four to an ordinary glowing ball. |
| **B — Ember Storm** | A single flame field whose outer boundary varies with angle and time; three parallax ember layers across the whole frame. | By far the most convincing as fire; never reads as a circle. | Turbulence without intent — energetic, not aware. Most expensive. |
| **C — Magnetic Sun** | A's photosphere plus four parametric prominence arcs anchored on the limb, with plasma knots travelling foot to foot. | The arcs are the only deliberate-looking motion in the set. | The limb itself stays circular. |
| **D — Refined** | C's arcs and photosphere plus B's silhouette breach, **gated by energy**. Idle is clean-limbed; acting erupts. | Has somewhere to go: state is legible without a label. | Core still flattens toward white at peak energy; corona can drift smoky. |

---

## 6. Measured runtime cost

GPU time per frame, `EXT_disjoint_timer_query_webgl2`, two independent repeats,
AMD Radeon RX 7900 GRE via ANGLE D3D11:

| Direction | 420×420 | 900×900 (run 1 / run 2) |
|---|---|---|
| A | 0.136 ms | 0.302 / 0.302 ms |
| B | 0.193 ms | 0.768 / 0.752 ms |
| C | 0.077 ms | 0.319 / 0.302 ms |
| **D** | 0.188 ms | **0.582 / 0.583 ms** |

A 60 fps frame is 16.6 ms, so D costs ~3.5% of budget at 900² on this GPU.

**An earlier measurement in this session was wrong and is recorded here rather than
discarded**: timing `gl.finish()` around the draw calls returned 0.000–0.007 ms, because
ANGLE/D3D11 does not block there. Those numbers measured nothing. They were replaced
with the timer-query figures above.

---

## 7. Recommended production path

**Ship D as a Flutter `FragmentShader`.** One fragment program, one `drawRect`, ten float
uniforms. The ember field is analytic in the shader, so there is no CPU particle system
and no overdraw.

Rejected alternatives: Blender-origin assets (cannot run at 60 fps, see §3); a video or
Lottie loop (fixed duration, visibly repeats, cannot respond to state); a Flutter particle
layer on top (CPU cost and overdraw for something the shader already does analytically).

Delivered and verified:

- `uri_ui/shaders/orb_solar.frag` — **generated** from the prototype source by
  `rnd/orb_solar/export_flutter_frag.mjs`, so the prototype and the shipped shader cannot
  drift. Only the header, `FlutterFragCoord()` and premultiplied-alpha output differ.
- `uri_ui/lib/living/companion/solar_orb.dart` — `SolarOrbState`, a six-parameter
  `SolarOrbParams` table, an eased state blend, a never-throwing shader cache matching the
  existing `OrbShaderCache` convention, and a `CustomPainter`.
- Registered in `uri_ui/pubspec.yaml` under `shaders:`.

Verification actually performed:

- `flutter build bundle` **succeeded**, and emitted a compiled Impeller blob:
  `build/flutter_assets/shaders/orb_solar.frag`, 359,608 bytes, magic `IPLR`.
  This proves the GLSL compiles under Flutter's own toolchain.
- `flutter analyze lib/living/companion/solar_orb.dart` → **No issues found!**

---

## 8. What is NOT verified

Stated plainly, because none of it is covered by the evidence above:

1. **The Flutter orb has never been rendered.** The shader compiles and the widget
   analyses clean, but no Flutter app was run and no frame was captured from Flutter.
   Everything visual in this report was rendered by the WebGL2 prototype. The two share
   their maths by generation, but premultiplied-alpha compositing, Impeller's own
   precision and the Dart uniform ordering are **unproven at runtime**.
2. **No widget test** exists for `SolarOrb`.
3. **Performance was measured on one discrete GPU only.** The mobile and integrated-GPU
   figures in the artifact are a 10–30× extrapolation, not a measurement. D at 900² could
   plausibly cost 6–17 ms on weak hardware, which would miss 60 fps. Mitigation (cap the
   backing resolution, drop ember layers) is designed but untested.
4. **No offline reference renders** exist, because Blender was not installed (§3).
5. Nothing is merged, and `energy_orb.dart` is untouched — the existing orb still ships.

---

## 9. Correction history

Required by the repository's evidence-integrity rules. Each entry is a conclusion reached
during this session that later evidence disproved.

| Claim | Disproved by | Actual cause |
|---|---|---|
| Reducing granule amplitude would clear the mesh/net texture on the disc. | Amplitude was cut from 0.17 → 0.013 with no visible change. | The fire ramp is steep around gold, so *any* cellular lane function shows as a web at this display size. Isolation test (`g1 = g2 = 0.5`) removed the mesh entirely and confirmed it. Worley granulation was replaced with domain-warped mottling plus ridged fibrils. |
| `gl.finish()` timing gave valid per-frame cost. | Results of 0.000–0.007 ms, physically impossible. | ANGLE/D3D11 does not block on `finish()`. Replaced with `EXT_disjoint_timer_query_webgl2`. |
| The hard grey wedges beside the orb came from the arc halo's wide, desaturated lobe. | Tightening and warming the halo left the wedges unchanged; prototype C, which has no footpoint term, was clean at the same resolution. | The footpoint-brightening term peaks exactly at the arc's angular cutoff and sat *after* the `if (g.x + g.y <= 0.0) continue;` guard, so it was clipped mid-peak along a radial line. Moved before the guard. |
| Anisotropic fibril sampling would give C's surface a sheared, magnetised look. | Rendered as regular horizontal coil banding. | Reverted to isotropic sampling; differential rotation now shows only in the large-scale bands, and the shear rate was cut from 0.55 to 0.14 because it grows with time and was smearing fine noise into lines. |

---

## 10. Next steps, in order

1. **Owner picks a direction** (A, B, C or D) from the live artifact.
2. Run the Flutter widget on Windows and capture a real frame — this closes gap §8.1 and
   is the only thing standing between "compiles" and "works".
3. Add a widget test (shader-absent fallback path, state transition, uniform count).
4. Measure on the weakest target device; add the resolution cap and an ember-layer quality
   tier if needed.
5. Remaining visual work on D: stop the core flattening toward white at peak energy, and
   warm the corona where it drifts smoky.
6. Decide whether `energy_orb.dart` adopts `SolarOrb` or is replaced by it.

---

## 11. Evidence index

| Path | What it is |
|---|---|
| `rnd/orb_solar/shaders.js` | All four prototype shaders + shared GLSL library. Source of truth. |
| `rnd/orb_solar/app.js` | WebGL2 runtime, state blending, deterministic capture hook. |
| `rnd/orb_solar/index.html` | Local 2×2 prototype harness. |
| `rnd/orb_solar/artifact/index.html` | Published presentation page. |
| `rnd/orb_solar/export_flutter_frag.mjs` | Generates the Flutter `.frag` from the prototype. |
| `rnd/orb_solar/capture_sink.py` | Loopback sink that wrote the PNG evidence. |
| `docs/orb_solar/evidence/shaders_v1.js` | First iteration, kept to show what was rejected. |
| `docs/orb_solar/evidence/shaders_v2.js` | Second iteration, kept for the same reason. |
| `docs/orb_solar/evidence/captures/*.png` | Rendered stills, 1100×760, plus two contact sheets. |
| `uri_ui/shaders/orb_solar.frag` | Generated production shader. |
| `uri_ui/lib/living/companion/solar_orb.dart` | Production widget. |
