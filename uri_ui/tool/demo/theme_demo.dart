// Companion-driven theme demonstration.
//
// Shows what the brief actually asks for: that choosing a companion changes
// URI's whole visual environment, not just the orb. The same workspace mock is
// rendered under each identity, from the same widgets reading the same tokens
// (`UriColors.of`, `UriGlass.of`) - there is no per-theme layout and no
// per-theme widget.
//
// Interactive:
//   flutter run -d windows -t tool/demo/theme_demo.dart
// Capture a frame per identity and exit:
//   flutter run -d windows -t tool/demo/theme_demo.dart \
//     --dart-define=CAPTURE=1 --dart-define=OUT=<dir>
import 'dart:io';
import 'dart:ui' as ui;

import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/companion_theme.dart';
import 'package:uri_ui/living/widgets/glass_panel.dart';
import 'package:uri_ui/living/widgets/status_badge.dart';
import 'package:uri_ui/theme/glass_theme.dart';
import 'package:uri_ui/theme/uri_theme.dart';

const bool capture = String.fromEnvironment('CAPTURE') == '1';
const String outDir = String.fromEnvironment('OUT', defaultValue: 'captures');

final GlobalKey _boundary = GlobalKey();

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  runApp(const _DemoApp());
}

class _DemoApp extends StatefulWidget {
  const _DemoApp();
  @override
  State<_DemoApp> createState() => _DemoAppState();
}

class _DemoAppState extends State<_DemoApp> {
  final CompanionController _companion = CompanionController();
  CompanionState _state = CompanionState.thinking;

  @override
  void initState() {
    super.initState();
    _companion.addListener(_onChange);
    if (capture) _runCapture();
  }

  void _onChange() => setState(() {});

  @override
  void dispose() {
    _companion.removeListener(_onChange);
    super.dispose();
  }

  Future<void> _runCapture() async {
    final dir = Directory(outDir);
    if (!dir.existsSync()) dir.createSync(recursive: true);
    for (final id in CompanionIdentity.values) {
      await CompanionShaderCache.load(id);
      _companion.select(id);
      for (var i = 0; i < 8; i++) {
        WidgetsBinding.instance.scheduleFrame();
        await WidgetsBinding.instance.endOfFrame;
      }
      final object = _boundary.currentContext?.findRenderObject();
      if (object is! RenderRepaintBoundary) {
        stderr.writeln('CAPTURE_FAILED: ${id.name}');
        continue;
      }
      final image = await object.toImage(pixelRatio: 1.5);
      final data = await image.toByteData(format: ui.ImageByteFormat.png);
      image.dispose();
      if (data == null) {
        stderr.writeln('CAPTURE_FAILED: ${id.name}');
        continue;
      }
      final bytes = data.buffer.asUint8List();
      File('$outDir/theme_${id.name}.png').writeAsBytesSync(bytes);
      stdout.writeln('CAPTURED: theme_${id.name}.png ${bytes.length}');
    }
    stdout.writeln('THEME_CAPTURE_DONE');
    exit(0);
  }

  @override
  Widget build(BuildContext context) {
    final palette = _companion.palette;
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      // The same ThemeData builder the app already uses; only the palette
      // differs per companion.
      theme: buildUriTheme(palette),
      home: CompanionScope(
        controller: _companion,
        child: RepaintBoundary(
          key: _boundary,
          child: _Workspace(
            identity: _companion.identity,
            state: _state,
            onIdentity: _companion.select,
            onState: (s) => setState(() => _state = s),
          ),
        ),
      ),
    );
  }
}

class _Workspace extends StatelessWidget {
  const _Workspace({
    required this.identity,
    required this.state,
    required this.onIdentity,
    required this.onState,
  });

  final CompanionIdentity identity;
  final CompanionState state;
  final ValueChanged<CompanionIdentity> onIdentity;
  final ValueChanged<CompanionState> onState;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    return Scaffold(
      body: DecoratedBox(
        decoration: BoxDecoration(
          gradient: LinearGradient(
            begin: Alignment.topCenter,
            end: Alignment.bottomCenter,
            colors: <Color>[glass.ambientTop, glass.ambientBottom],
          ),
        ),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: <Widget>[
            _Sidebar(c: c, glass: glass),
            Expanded(
              child: Padding(
                padding: const EdgeInsets.all(UriSpace.lg),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: <Widget>[
                    _Header(c: c, identity: identity),
                    const SizedBox(height: UriSpace.lg),
                    Expanded(
                      child: Row(
                        crossAxisAlignment: CrossAxisAlignment.stretch,
                        children: <Widget>[
                          Expanded(flex: 5, child: _Conversation(c: c)),
                          const SizedBox(width: UriSpace.lg),
                          Expanded(
                            flex: 4,
                            child: _CompanionPane(
                              identity: identity,
                              state: state,
                              onIdentity: onIdentity,
                              onState: onState,
                            ),
                          ),
                        ],
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _Sidebar extends StatelessWidget {
  const _Sidebar({required this.c, required this.glass});
  final UriColors c;
  final UriGlass glass;

  @override
  Widget build(BuildContext context) {
    const items = <(String, IconData, bool)>[
      ('Workspace', Icons.dashboard_outlined, true),
      ('Conversation', Icons.forum_outlined, false),
      ('Memory graph', Icons.hub_outlined, false),
      ('Intelligence', Icons.insights_outlined, false),
      ('Settings', Icons.tune, false),
    ];
    return Container(
      width: 208,
      decoration: BoxDecoration(
        color: c.surface,
        border: Border(right: BorderSide(color: c.border)),
      ),
      padding: const EdgeInsets.symmetric(vertical: UriSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: <Widget>[
          Padding(
            padding: const EdgeInsets.fromLTRB(UriSpace.md, 0, UriSpace.md, UriSpace.lg),
            child: Row(
              children: <Widget>[
                Container(
                  width: 10,
                  height: 10,
                  decoration: BoxDecoration(
                    color: c.accent,
                    shape: BoxShape.circle,
                    boxShadow: <BoxShadow>[
                      BoxShadow(color: glass.glowSoft, blurRadius: 14, spreadRadius: 3),
                    ],
                  ),
                ),
                const SizedBox(width: UriSpace.sm),
                Text(
                  'URI',
                  style: TextStyle(
                    color: c.ink,
                    fontSize: 15,
                    fontWeight: FontWeight.w700,
                    letterSpacing: 1.4,
                  ),
                ),
              ],
            ),
          ),
          for (final (label, icon, active) in items)
            Padding(
              padding: const EdgeInsets.symmetric(
                horizontal: UriSpace.sm,
                vertical: 2,
              ),
              child: Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: UriSpace.sm,
                  vertical: 9,
                ),
                decoration: BoxDecoration(
                  color: active ? c.accentSoft : null,
                  borderRadius: BorderRadius.circular(UriRadius.sm),
                  border: active
                      ? Border.all(color: c.accent.withValues(alpha: 0.35))
                      : null,
                ),
                child: Row(
                  children: <Widget>[
                    Icon(icon, size: 16, color: active ? c.accentInk : c.inkFaint),
                    const SizedBox(width: UriSpace.sm),
                    Text(
                      label,
                      style: TextStyle(
                        color: active ? c.accentInk : c.inkSoft,
                        fontSize: 13,
                        fontWeight: active ? FontWeight.w600 : FontWeight.w400,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          const Spacer(),
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: UriSpace.md),
            child: Row(
              children: const <Widget>[
                StatusBadge(TruthStatus.qualified, compact: true),
                SizedBox(width: 6),
                StatusBadge(TruthStatus.simulated, compact: true),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({required this.c, required this.identity});
  final UriColors c;
  final CompanionIdentity identity;

  @override
  Widget build(BuildContext context) {
    return Row(
      crossAxisAlignment: CrossAxisAlignment.end,
      children: <Widget>[
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: <Widget>[
            Text(
              'Workspace',
              style: TextStyle(
                color: c.ink,
                fontSize: 26,
                fontWeight: FontWeight.w700,
                letterSpacing: -0.5,
              ),
            ),
            const SizedBox(height: 2),
            Text(
              '${identity.label} - ${identity.tagline}',
              style: TextStyle(color: c.inkSoft, fontSize: 13),
            ),
          ],
        ),
        const Spacer(),
        _Pill(label: 'Review', fg: c.accentInk, bg: c.accentSoft, border: c.accent),
        const SizedBox(width: UriSpace.sm),
        _Pill(label: 'Needs approval', fg: c.warning, bg: c.warningSoft, border: c.warning),
        const SizedBox(width: UriSpace.sm),
        _Pill(label: 'Blocked', fg: c.danger, bg: c.dangerSoft, border: c.danger),
      ],
    );
  }
}

class _Pill extends StatelessWidget {
  const _Pill({
    required this.label,
    required this.fg,
    required this.bg,
    required this.border,
  });
  final String label;
  final Color fg;
  final Color bg;
  final Color border;

  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 11, vertical: 6),
      decoration: BoxDecoration(
        color: bg,
        borderRadius: BorderRadius.circular(999),
        border: Border.all(color: border.withValues(alpha: 0.45)),
      ),
      child: Text(
        label,
        style: TextStyle(color: fg, fontSize: 11.5, fontWeight: FontWeight.w600),
      ),
    );
  }
}

class _Conversation extends StatelessWidget {
  const _Conversation({required this.c});
  final UriColors c;

  @override
  Widget build(BuildContext context) {
    return GlassPanel(
      padding: const EdgeInsets.all(UriSpace.lg),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: <Widget>[
          Text(
            'Conversation',
            style: TextStyle(
              color: c.ink,
              fontSize: 13,
              fontWeight: FontWeight.w700,
              letterSpacing: 0.8,
            ),
          ),
          const SizedBox(height: UriSpace.md),
          _Bubble(
            c: c,
            mine: true,
            text: 'Draft the quarterly summary from the evidence registry.',
          ),
          const SizedBox(height: UriSpace.sm),
          _Bubble(
            c: c,
            mine: false,
            text: 'Three milestone records are unverified. I can draft around '
                'them, or stop and show you which ones.',
          ),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(
              horizontal: UriSpace.md,
              vertical: 11,
            ),
            decoration: BoxDecoration(
              color: c.surfaceSunken,
              borderRadius: BorderRadius.circular(UriRadius.md),
              border: Border.all(color: c.border),
            ),
            child: Row(
              children: <Widget>[
                Expanded(
                  child: Text(
                    'Ask URI something',
                    style: TextStyle(color: c.inkFaint, fontSize: 13),
                  ),
                ),
                Icon(Icons.graphic_eq, size: 16, color: c.accent),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.c, required this.mine, required this.text});
  final UriColors c;
  final bool mine;
  final String text;

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: mine ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        constraints: const BoxConstraints(maxWidth: 380),
        padding: const EdgeInsets.symmetric(
          horizontal: UriSpace.md,
          vertical: 10,
        ),
        decoration: BoxDecoration(
          color: mine ? c.accentSoft : c.surfaceSunken,
          borderRadius: BorderRadius.circular(UriRadius.md),
          border: Border.all(color: mine ? c.accent.withValues(alpha: 0.30) : c.border),
        ),
        child: Text(
          text,
          style: TextStyle(
            color: mine ? c.accentInk : c.ink,
            fontSize: 13,
            height: 1.45,
          ),
        ),
      ),
    );
  }
}

class _CompanionPane extends StatelessWidget {
  const _CompanionPane({
    required this.identity,
    required this.state,
    required this.onIdentity,
    required this.onState,
  });

  final CompanionIdentity identity;
  final CompanionState state;
  final ValueChanged<CompanionIdentity> onIdentity;
  final ValueChanged<CompanionState> onState;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: <Widget>[
        Expanded(
          child: GlassPanel(
            padding: EdgeInsets.zero,
            child: Stack(
              children: <Widget>[
                Positioned.fill(
                  child: CompanionOrb(identity: identity, state: state),
                ),
                Positioned(
                  left: UriSpace.md,
                  bottom: UriSpace.md,
                  child: Text(
                    state.label,
                    style: TextStyle(
                      color: c.ink,
                      fontSize: 12,
                      fontWeight: FontWeight.w600,
                      letterSpacing: 0.6,
                    ),
                  ),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: UriSpace.md),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: <Widget>[
            for (final id in CompanionIdentity.values)
              _Choice(
                label: id.label,
                on: id == identity,
                c: c,
                onTap: () => onIdentity(id),
              ),
          ],
        ),
        const SizedBox(height: UriSpace.sm),
        Wrap(
          spacing: 6,
          runSpacing: 6,
          children: <Widget>[
            for (final s in CompanionState.values)
              _Choice(
                label: s.name,
                on: s == state,
                c: c,
                onTap: () => onState(s),
              ),
          ],
        ),
      ],
    );
  }
}

class _Choice extends StatelessWidget {
  const _Choice({
    required this.label,
    required this.on,
    required this.c,
    required this.onTap,
  });
  final String label;
  final bool on;
  final UriColors c;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 5),
        decoration: BoxDecoration(
          color: on ? c.accentSoft : c.surface,
          borderRadius: BorderRadius.circular(UriRadius.sm),
          border: Border.all(color: on ? c.accent : c.border),
        ),
        child: Text(
          label,
          style: TextStyle(
            color: on ? c.accentInk : c.inkSoft,
            fontSize: 11.5,
            fontWeight: on ? FontWeight.w600 : FontWeight.w400,
          ),
        ),
      ),
    );
  }
}
