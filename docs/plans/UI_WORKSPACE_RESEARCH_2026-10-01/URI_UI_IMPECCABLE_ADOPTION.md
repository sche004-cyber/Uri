# Impeccable adoption for URI Flutter

Researched 2026-10-01. **No installation, launcher execution, hook activation, runtime download or dependency modification performed.** Proposal is project-local, opt-in and subordinate to URI's accepted design/authority rules.

## Verified upstream and version boundaries

Inspected upstream tree SHA: `c74755d920985f7a92cef691ca970ba95f90126e`. Its `package.json` says npm package **4.1.0**, skill metadata says **4.4.0**, platform engine optional dependencies say **0.1.9**. Treat these as distinct versions; do not assume installing npm 4.1.0 reproduces the entire source tree or latest remotely fetched skill bundle. Pin and record the actual bundle, engine and skill hashes in the future adoption trial. [Package manifest](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/package.json), [skill](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/.agents/skills/impeccable/SKILL.md).

Impeccable supplies agent design guidance and commands plus a binary engine and browser features. It supports Codex and Antigravity distributions. Upstream setup creates product context separately from visual design context; URI should derive these from governing evidence, not create a competing product constitution. [README](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/README.md).

URI already has `.agents/skills/impeccable-design/SKILL.md`: an advisory-only adaptation with palette, spacing, edge-state and motion rules. That skill explicitly installs no binaries/hooks. The upstream tool is a separate, more powerful integration; naming overlap is not proof it is already installed. Continue the advisory workflow while recovery is active. The User-selected Combined URI Experience preserves all three presentations within the approved Hybrid shell; use this guidance for bounded improvements to existing Flutter components, with native tests and actual Windows screenshots as specified in [UI-S1](URI_UI_FIRST_SLICE_PLAN.md).

## What supports Flutter, and what does not

| Need | Actual command/playbook | URI strategy and support limit |
|---|---|---|
| Product initialization | `init`; `shape` for planning | Capture audience, task scene, constraints and evidence in a sandbox trial; root PRODUCT/DESIGN writes require the future approved docs scope. Do not run init against active work today |
| Design critique | `critique` | Agent reasoning on actual Flutter screenshots and source; supply fixture/theme/window context. Native GUI access is not created by this command |
| Technical native audit | `audit.native.md` | Explicitly lists Flutter source inspection; covers labels/scaling/theme/performance. Platform routing is iOS/Android/adaptive, not a dedicated Windows audit. Translate to Windows Narrator, DPI, keyboard, focus and lifecycle checks; no mobile-score-as-Windows-compliance claim |
| Layout/usability/copy | `layout`, `clarify`, `distill`, `harden` | Reusable design advice; future implementer translates changes to Flutter within bounded scope. They are not Flutter plugin commands |
| Consistency/design system | `document`, `extract`, `polish`, `typeset`, `colorize` | Can guide source/token extraction. URI's four themes and current identity win; no automatic font/theme replacement or wholesale component rewrite |
| Onboarding | `onboard` | Review real bootstrap/login/Brain flow and truthful unavailable states; do not synthesize working providers |
| Performance/motion | `optimize`, `animate`, `adapt` | Guidance complements DevTools/profile measurements, Flutter text-scale/reduced-motion and native window tests. No measured speedup without captures |
| Browser live iteration | `live`, `generate` | Browser elements, HTML/CSS and HMR/static HTML. Not direct Windows Flutter widget/window editing or native screenshot automation |
| Deterministic detector | CLI detector / browser extension | Browser/web evidence. Native audit explicitly excludes `impeccable detect`. Do not interpret a zero-result scan over Dart as native validation |

The command names above are present in the inspected [skill Commands table](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/.agents/skills/impeccable/SKILL.md). There is no need to invent a “Flutter audit” CLI or claim a Windows plugin. Native source review is explicitly supported as an agent playbook, while browser instrumentation is a different feature. [Native audit](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/.agents/skills/impeccable/reference/audit.native.md), [browser live playbook](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/.agents/skills/impeccable/reference/live.md).

Browser concepts may be used as disposable planning artifacts, never deployed as URI or used to claim Flutter acceptance. Current assignment's schematic directions need no browser engine.

## Installation, dependency and hook review

The npm package is a Node shim around platform engine binaries; its manifest requires Node ≥22.18.0. Optional platform packages or a pinned cache supply the engine; otherwise the shim/Windows launcher can fetch a release binary. The Windows launcher includes checksum-sidecar verification for downloads, cache/PATH probing and fallback behavior. A checksum does not establish that the code/bundle is appropriate for URI. [npm shim](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/cli/bin/cli.js), [Windows launcher](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/.agents/skills/impeccable/scripts/impeccable.cmd).

Installer code exposes **`--scope=project`**, **`--providers=codex`**, **`--no-hooks`**, and `--force`. It can fetch/extract a skill bundle and copy engine/provider artifacts. Review what it actually downloaded; pinning npm alone is insufficient. Start without force or hooks. Native hooks are not necessary for source/screenshot advice. [Installer commands](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/crates/skills/src/commands.rs), [engine acquisition](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/crates/skills/src/engine_binary.rs).

The inspected Codex manifest has PostToolUse on `Edit|Write|apply_patch` (5-second timeout) and Stop (30-second timeout), with Windows command variants. Its checked-in paths refer to `.codex/skills/impeccable`; the Codex skill distribution lives under `.agents/skills`. Installer rewriting/merge behavior must be validated on Windows rather than blindly copying that manifest. Existing unrelated hooks must survive unchanged. [Manifest](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/.codex/hooks.json), [hook manifest handling](https://github.com/pbakaus/impeccable/blob/c74755d920985f7a92cef691ca970ba95f90126e/crates/skills/src/hook_manifest.rs).

Source review covered installer entry/options and hook merge/download mechanisms; it was **not an exhaustive security audit of the Rust engine, all transitive dependencies, downloaded bundle or release binaries**. No installed-Windows compatibility test was performed. Remaining review checklist belongs to a later bounded adoption task:

1. Use a disposable project directory outside active production trees. Inspect release identity, archive paths, checksums/signatures, licenses, npm lifecycle scripts, platform optional packages and executable provenance before running anything.
2. Snapshot existing project skill/config/hooks; inventory proposed writes, network hosts and cache paths. Do not copy user credential/config content into trial logs.
3. Inspect `bundle.rs`, signature logic, provider copying, launcher and hook behavior for that pinned release. Confirm PRODUCT/DESIGN and `.impeccable` writes, no unrelated file replacement, no agent/dependency activation beyond chosen provider.
4. Trial skill-only project install, record exact generated files, binary/bundle hashes and network activity. Confirm no global harness changes. Remove by restoring the trial snapshot; do not remove URI's pre-existing advisory skill.
5. Provide a Flutter source/screenshot fixture and compare useful findings against known defects. Count false positives and unknowns. Failure to detect Dart/native issues disqualifies automated gates, not advisory design reasoning.
6. Hooks stay off until separately reviewed and specifically useful. If adopted, inspect actual Windows command paths and allow the host's normal trust process; review update diffs before trusting changed definitions. Do not enable automatically during recovery.

Candidate future trial command, **not executed** (only after release/bundle review):

```powershell
npx impeccable@4.1.0 install --providers=codex --scope=project --no-hooks
```

This demonstrates verified installer flags, not a reproducible pinned-bundle recipe. A reviewed vendored bundle/engine with immutable hashes is preferable for reproducibility if the installer fetches moving assets. Installation for Antigravity needs its provider-specific trial and write inventory too; Codex's successful trial would not establish Antigravity compatibility.

## Native Flutter complement and repeatable workflow

For each accepted UI batch: collect product/backend evidence → choose reference structure → inspect real native screenshot/semantic tree → run bounded advisory critique/audit → implement assigned changes → validate once across the full affected matrix → repair concrete findings → independently review and live-accept. Reports state source-only versus observed findings. No numeric design score is assigned without the required observations.

| Validation layer | Purpose | URI acceptance evidence |
|---|---|---|
| Widget/client tests | State rendering, callbacks, malformed/error/empty response, focus/semantics, text scale | Extend existing `chat_lifecycle_test`, `compact_overlay_test`, `http_uri_client_test`, `attachment_ui_test`, theme/provider/history tests; mocks explicitly labeled |
| Goldens/screenshots | Stable layout at actual theme/size/scale with deterministic fixtures | Four-theme captures of compact/workspace/approval/error/long-file states; baseline OS/font/DPI/render engine identified; no reference-app screenshot substituted |
| Flutter integration tests | Real app widgets and client under Windows | Plan `integration_test` harness separately: dependency currently absent. Test same-session transition and real fixture task; production registry/approval paths preserved |
| Windows interaction | OS frame, picker, external viewer, minimize/focus, DPI, concurrent launch, owned shutdown | Native test/manual observation with action recording; plugin-free widget tests cannot prove these |
| Accessibility | Semantics/labels/contrast, complete keyboard tasks, assistive behavior | Flutter accessibility guideline checks plus actual Narrator, visible focus, 200% scaling, four themes, reduced-motion observations |
| Performance | Startup, frame costs, long history and artifact load | Profile build + Flutter DevTools/frame measurements and backend event timing; separate UI performance from model latency |
| Canonical task acceptance | User request to grounded result/decision through real runtime | Real discovery/validation/approval/execution/verifier/feedback trace and native result review; no model-text completion |

Flutter's integration-test documentation describes the test mechanism; it does not make OS-level plugin behavior or arbitrary native windows covered automatically. Its accessibility guideline API can check aspects such as labels/targets/contrast, complementing manual assistive testing. [Flutter integration testing](https://docs.flutter.dev/testing/integration-tests), [Flutter accessibility testing](https://docs.flutter.dev/ui/accessibility/accessibility-testing).

Adoption recommendation: retain URI's advisory skill now; later trial upstream native/source guidance locally with hooks disabled. Do not add the browser live pipeline as a prerequisite to shipping the Flutter workspace.
