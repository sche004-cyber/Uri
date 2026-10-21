# URI UI development guide: controls, glow and typography

Established by UI-CONTROLS-TYPO-20261018 (branch `milestone/ui-controls-typography-20261018`). It records the
conventions every future URI Flutter change should follow. It is an enhancement guide for the existing interface, not
a redesign: layouts, themes, companions and architecture stay as they are.

## 1. Typography

**One UI family.** URI uses the Windows system UI font, **Segoe UI**, everywhere (`UriType.family`). Code uses
**Consolas** (`UriType.mono`). Both are Windows system fonts: no font package, no bundled font file. Do not add a
`fontFamily:` string literal anywhere in `uri_ui/lib`; a test (`test/living/ui_controls_typography_test.dart`)
fails if you do.

**One scale.** Every size comes from `UriType` in `lib/theme/uri_theme.dart`:

| Token | px | Use |
|-------|----|-----|
| `micro` | 10 | dense badges and footers only |
| `caption` | 11 | meta lines, notices, timestamps |
| `label` | 12 | chips, quick controls, small labels |
| `body` | 13 | compact body text, menus, lists, dialog body |
| `bodyLarge` | 14 | default reading text (`bodyMedium` role), inputs, buttons |
| `title` | 15 | card and section titles |
| `titleLarge` | 17 | dialog titles, panel headings |
| `heading` | 20 | page headings |
| `headline` | 24 | large headings, metrics |
| `headlineLarge` | 28 | hero metrics |
| `display` | 34 | display headings |
| `hero` | 48 | the URI wordmark |

Rules:
- Prefer a theme role (`Theme.of(context).textTheme.bodyMedium` ...) and `copyWith` the colour. Every role in
  `buildUriTheme` carries the family explicitly; never replace a role with a bare `TextStyle` (it would drop the family
  and fall back silently).
- When a literal size is needed, write `fontSize: UriType.<token>`, never a number. The test above fails on a numeric
  `fontSize:` outside the theme. Exceptions: the classic dashboard board, excluded by scope, not frozen (`reference_dashboard.dart`,
  `dashboard_manifest.dart`: board units of a scaled 1024x682 canvas) and the protected `settings_shell.dart`.
- Weights: 400 body, 500 labels, 600 titles and emphasis, 700 headings and metrics, 300 only for the wordmark and the
  large greeting.
- Letter spacing 0 except the theme's uppercase `labelSmall` (0.4) and display headings (negative, set by the theme).

## 2. Push-to-enable controls

Use the widgets in `lib/living/integration/qc_toggle.dart`:

- **`QcToggle`** for an on/off feature: one click enables, the next disables. Optional `status` (a short qualifier
  such as `Auto` or `starting`) and `trailing` (a small menu caret for rarely used extra choices).
- **`QcSegmented`** for mutually exclusive values (e.g. context size). Never model a selection as several toggles.

States (`QcVisual`) and how they look:

| State | Look |
|-------|------|
| off | transparent fill, border token, `inkSoft` text |
| hover | 6 % ink tint, stronger border (pointer only, while interactive) |
| pressed | 12 % ink tint |
| on (enabled) | `accentSoft` fill, `accent` border, `accentInk` text, **one static accent glow** (`QcStyle.glow`) |
| loading | spinner instead of the icon, half-accent border, no glow, not interactive |
| error | `danger` border and icon, no glow |
| disabled | `onPressed: null`; faint text; the tooltip says **why** |

Rules:
- **Truth first.** The `visual` comes from verified runtime state, never from the click. For Brain profile controls
  that is `brain_health.controls.active` (set only after the worker verified the running server). A click asks
  (confirmation, request); the worker's report decides what glows.
- **Glow budget.** One `BoxShadow` (accent at 42 %, blur 12; 55 % and blur 14 on hover) per enabled control, no looping animation; the only animation
  is a 140 ms transition on a state change. Do not add shaders, blur filters or repeating animations to controls.
- **Disabled with a reason.** A control that cannot act stays visible with `onPressed: null` and a tooltip that names
  the reason (unqualified profile, Brain host not running, Assist holds vision, URI is answering).
- **Coupled settings are stated.** When one control's choice changes another setting (Vision off => 64K), the tooltip
  and the confirmation both say so.
- **Reloading controls confirm first** with `QcSwitchDialog`-style dialogs and show a loading state while the switch
  runs; failure outcomes appear in the notice line in the warning or danger tone.
- Keys: `qc-<control>` for the control, `qc-<control>-<value>` for a segment or menu item (tests and live drivers rely
  on them).

## 3. Dialogs

- Constrain the content to a readable width (`maxWidth: 460`); the title uses `titleLarge` (17, w600).
- Order: one-line summary, a "what changes" block (`surfaceSunken`, from -> to rows), then facts with leading icons,
  then actions.
- Actions: secondary `TextButton` (Cancel) on the left, primary `FilledButton` (verb + object, e.g. "Switch Brain") on
  the right.

## 4. Verification checklist for a UI change

1. Widget tests for every state the change introduces, including "does not glow before verified".
2. `flutter analyze` with 0 errors and the typography test green.
3. A live Windows run through the production `main()` (see `docs/ui/controls_typography_20261018/evidence/live_harness`)
   with screenshots of each surface touched.
