import 'dart:async';

import 'package:flutter/material.dart';

import '../../../theme/uri_theme.dart';
import '../../companion/companion_design.dart';
import '../../companion/companion_orb.dart' show CompanionIdentity;
import '../../companion/companion_preferences.dart';
import '../../companion/companion_state.dart';
import '../../companion/effects_settings.dart';
import '../../companion/frame_clock.dart';
import '../../companion/living_companion.dart';
import '../../living_scope.dart';

class InterfaceThemePicker extends StatelessWidget {
  const InterfaceThemePicker({super.key});
  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    return DropdownButtonFormField<String>(
      key: ValueKey(
        'interface-theme-${prefs.interfaceTheme?.name ?? 'original'}',
      ),
      initialValue: prefs.interfaceTheme?.name ?? 'original',
      isExpanded: true,
      decoration: const InputDecoration(labelText: 'Interface Theme'),
      items: [
        const DropdownMenuItem(
          value: 'original',
          child: Text("Use Companion's original theme"),
        ),
        for (final theme in {
          ...installedInterfaceThemes,
          ?prefs.interfaceTheme,
        })
          DropdownMenuItem(value: theme.name, child: Text(theme.label)),
      ],
      onChanged: (key) => prefs.setInterfaceTheme(
        UriThemeChoice.values.where((t) => t.name == key).firstOrNull,
      ),
    );
  }
}

class CompanionsSection extends StatelessWidget {
  const CompanionsSection({super.key});
  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text('COMPANIONS', style: Theme.of(context).textTheme.labelLarge),
        const SizedBox(height: 12),
        ListTile(
          contentPadding: EdgeInsets.zero,
          title: const Text('Companion Design'),
          subtitle: Text(CompanionDesign.active(prefs).displayName),
          trailing: const Icon(Icons.open_in_full),
          onTap: () => Navigator.of(context).push(
            MaterialPageRoute<void>(
              builder: (_) => CompanionGallery(
                active: prefs,
                services: LivingScope.of(context),
              ),
            ),
          ),
        ),
        const InterfaceThemePicker(),
        const SizedBox(height: 8),
        const Text(
          'Companion identity and interface colours are independent. Preview changes before applying.',
        ),
      ],
    );
  }
}

/// One renderer mounted at a time. This route owns all preview resources;
/// it never borrows the active voice, task, presentation or Brain controller.
class CompanionGallery extends StatefulWidget {
  const CompanionGallery({
    super.key,
    required this.active,
    required this.services,
    this.initialDesign,
  });
  final CompanionPreferences active;
  final LivingServices services;
  final CompanionDesign? initialDesign;
  @override
  State<CompanionGallery> createState() => _CompanionGalleryState();
}

class _CompanionGalleryState extends State<CompanionGallery> {
  late final CompanionPreferences _preview;
  late CompanionDesign _design;
  final _clock = CompanionFrameClock(cap: 30);
  late final EffectsSettings _effects;
  CompanionState _state = CompanionState.idle;
  UriThemeChoice? _theme;
  double _zoom = 1;
  bool _playing = true;
  bool _large = false;

  @override
  void initState() {
    super.initState();
    _design = widget.initialDesign ?? CompanionDesign.active(widget.active);
    _preview = CompanionPreferences(
      persist: false,
      choice: widget.active.choice,
      quality: widget.active.quality,
      looks: {
        for (final c in CompanionChoice.all) c.key: widget.active.lookFor(c),
      },
    );
    _design.applyTo(_preview);
    _theme = widget.active.interfaceTheme;
    _effects = EffectsSettings(
      reducedEffects: widget.services.effects.reducedEffects,
      reducedMotion: widget.services.effects.reducedMotion,
    );
    widget.services.frameClock.visibility.addListener(_visibility);
    _visibility();
  }

  void _visibility() => _clock.setHidden(
    !widget.services.frameClock.visibility.value || !_playing,
  );
  @override
  void dispose() {
    widget.services.frameClock.visibility.removeListener(_visibility);
    _clock.dispose();
    _effects.dispose();
    _preview.dispose();
    super.dispose();
  }

  Future<void> _apply() async {
    _design.applyTo(widget.active);
    await widget.active.setInterfaceTheme(_theme);
    await widget.active.pendingWrite;
    if (mounted) Navigator.of(context).pop();
  }

  Widget _viewer(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) {
      final size = (constraints.biggest.shortestSide - 48).clamp(120.0, 480.0);
      return ClipRect(
        child: Center(
          child: Transform.scale(
            scale: _zoom,
            child: RepaintBoundary(
              child: LivingCompanion(
                key: const ValueKey('gallery-live-renderer'),
                state: _state,
                size: size,
                preserveIdentityTheme: true,
                variant: _preview.classicVariant,
                interactive: false,
                semanticsLabel:
                    '${_design.displayName} preview: ${_state.label}',
              ),
            ),
          ),
        ),
      );
    },
  );
  @override
  Widget build(BuildContext context) {
    final palette = resolveUriColors(
      _theme ?? _design.originalTheme,
      MediaQuery.platformBrightnessOf(context),
    );
    return Theme(
      data: buildUriTheme(palette),
      child: CompanionPreferencesScope(
        preferences: _preview,
        child: EffectsSettingsScope(
          settings: _effects,
          child: CompanionClockScope(
            clock: _clock,
            child: Builder(
              builder: (context) => Scaffold(
                appBar: AppBar(
                  title: const Text('Companions'),
                ),
                bottomNavigationBar: SafeArea(
                  top: false,
                  minimum: const EdgeInsets.fromLTRB(20, 8, 20, 12),
                  child: Wrap(
                    alignment: WrapAlignment.end,
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      TextButton(
                        key: const ValueKey('gallery-cancel'),
                        onPressed: () => Navigator.of(context).pop(),
                        child: const Text('Cancel'),
                      ),
                      FilledButton(
                        key: const ValueKey('gallery-apply'),
                        onPressed: _apply,
                        child: const Text('Apply'),
                      ),
                    ],
                  ),
                ),
                body: LayoutBuilder(
                  builder: (context, box) {
                    final wide =
                        box.maxWidth >= 800 &&
                        MediaQuery.textScalerOf(context).scale(14) <= 22;
                    final choices = ListView(
                      children: [
                        for (final d in CompanionDesign.installed)
                          ListTile(
                            key: ValueKey('gallery-design-${d.id}'),
                            selected: _design.id == d.id,
                            title: Text(d.displayName),
                            subtitle: Text('Original: ${d.originalThemeLabel}'),
                            trailing: _design.id == d.id
                                ? const Icon(Icons.check)
                                : null,
                            onTap: () => setState(() {
                              _design = d;
                              d.applyTo(_preview);
                            }),
                          ),
                      ],
                    );
                    final inspection = Column(
                      children: [
                        Expanded(child: _viewer(context)),
                        if (!_large)
                          Flexible(
                            child: SingleChildScrollView(
                              child: Align(
                                alignment: Alignment.topCenter,
                                child: ConstrainedBox(
                                  constraints: const BoxConstraints(
                                    maxWidth: 640,
                                  ),
                                  child: Padding(
                                    padding: const EdgeInsets.symmetric(
                                      horizontal: 20,
                                    ),
                                    child: Column(
                                      children: [
                                        Text(
                                          // Ember plays pre-rendered painted clips (EMBER-V21-INTEG R1-09).
                                          _design.choice.identity == CompanionIdentity.ember
                                              ? '${_design.displayName} · painted animated clips'
                                              : '${_design.displayName} · live procedural 2D renderer',
                                        ),
                                        const Text(
                                          'Model rotation unavailable: this renderer is not a 3D mesh.',
                                        ),
                                        const SizedBox(height: 12),
                                        Wrap(
                                          spacing: 12,
                                          runSpacing: 8,
                                          crossAxisAlignment:
                                              WrapCrossAlignment.center,
                                          children: [
                                            SizedBox(
                                              width: 320,
                                              child: DropdownButtonFormField<CompanionState>(
                                                initialValue: _state,
                                                isExpanded: true,
                                                itemHeight: null,
                                                decoration: const InputDecoration(
                                                  labelText: 'Animation preview',
                                                ),
                                                items: [
                                                  for (final s
                                                      in CompanionState.values)
                                                    DropdownMenuItem(
                                                      value: s,
                                                      child: Text(
                                                        s == CompanionState.success
                                                            ? 'Completion expression (preview)'
                                                            : s.label,
                                                      ),
                                                    ),
                                                ],
                                                onChanged: (v) =>
                                                    setState(() => _state = v!),
                                              ),
                                            ),
                                            TextButton.icon(
                                              onPressed: () => setState(() {
                                                _playing = !_playing;
                                                _effects.setReducedMotion(
                                                  !_playing ||
                                                      widget
                                                          .services
                                                          .effects
                                                          .reducedMotion,
                                                );
                                                _visibility();
                                              }),
                                              icon: Icon(
                                                _playing
                                                    ? Icons.pause
                                                    : Icons.play_arrow,
                                              ),
                                              label: Text(
                                                _playing
                                                    ? 'Pause animation'
                                                    : 'Play animation',
                                              ),
                                            ),
                                          ],
                                        ),
                                        Row(
                                          children: [
                                            const Text('Zoom'),
                                            Expanded(
                                              child: Slider(
                                                value: _zoom,
                                                min: .6,
                                                max: 1.5,
                                                label: '${(_zoom * 100).round()}%',
                                                onChanged: (v) =>
                                                    setState(() => _zoom = v),
                                              ),
                                            ),
                                          ],
                                        ),
                                        DropdownButtonFormField<String>(
                                          key: ValueKey(
                                            'gallery-theme-${_theme?.name ?? 'original'}',
                                          ),
                                          initialValue: _theme?.name ?? 'original',
                                          isExpanded: true,
                                          decoration: const InputDecoration(
                                            labelText: 'Preview interface theme',
                                          ),
                                          items: [
                                            const DropdownMenuItem(
                                              value: 'original',
                                              child: Text(
                                                "Use Companion's original theme",
                                              ),
                                            ),
                                            for (final t in {
                                              ...installedInterfaceThemes,
                                              ?_theme,
                                            })
                                              DropdownMenuItem(
                                                value: t.name,
                                                child: Text(t.label),
                                              ),
                                          ],
                                          onChanged: (v) => setState(
                                            () => _theme = UriThemeChoice.values
                                                .where((t) => t.name == v)
                                                .firstOrNull,
                                          ),
                                        ),
                                        const SizedBox(height: 12),
                                        const Text(
                                          'Animation states are simulated previews. Apply changes appearance only.',
                                        ),
                                      ],
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          ),
                        TextButton.icon(
                          onPressed: () => setState(() => _large = !_large),
                          icon: const Icon(Icons.open_in_full),
                          label: Text(
                            _large ? 'Return to gallery' : 'Larger inspection',
                          ),
                        ),
                      ],
                    );
                    if (_large) return inspection;
                    return wide
                        ? Row(
                            children: [
                              SizedBox(width: 280, child: choices),
                              const VerticalDivider(width: 1),
                              Expanded(child: inspection),
                            ],
                          )
                        : Column(
                            children: [
                              SizedBox(height: 140, child: choices),
                              Expanded(child: inspection),
                            ],
                          );
                  },
                ),
              ),
            ),
          ),
        ),
      ),
    );
  }
}
