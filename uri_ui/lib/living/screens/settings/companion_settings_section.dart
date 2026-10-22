import 'package:flutter/material.dart';

import '../../../theme/uri_theme.dart';
import '../../companion/companion_orb.dart';
import '../../companion/companion_preferences.dart';
import '../../companion/companion_state.dart';
import '../../companion/ember_companion.dart' show EmberManifest;
import '../../companion/energy_orb.dart';
import '../../companion/frame_clock.dart';
import '../../living_app.dart' show LivingThemeController;
import '../../living_scope.dart';
import '../../voice/companion_presence.dart' show SoftDisc, presenceScale;
import '../../voice/voice_catalog.dart';
import '../../widgets/status_badge.dart';
import 'voice_input_settings.dart';
import 'companion_gallery.dart';

/// Companion Settings: which companion, how it looks, how it is rendered,
/// and how URI sounds.
///
/// The page takes its colours from the theme like every living screen, and
/// the theme comes from the selected companion, so choosing Sakura re-themes
/// this page as it is being used. Every control here changes something real
/// or says plainly that it is unavailable and why; none is decorative.
class CompanionSettingsSection extends StatelessWidget {
  const CompanionSettingsSection({super.key});

  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    if (LivingScope.of(context).visualV2) {
      return Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const CompanionsSection(),
          const SizedBox(height: 24),
          if (!prefs.choice.isClassic) _LivingAppearance(choice: prefs.choice),
          const SizedBox(height: 24),
          const _PerformanceSettings(),
          const SizedBox(height: 24),
          const _VoiceSettings(),
        ],
      );
    }
    return Column(
      key: const ValueKey('companion-settings'),
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Eyebrow('Companion'),
        const SizedBox(height: 10),
        const _CompanionPicker(),
        const SizedBox(height: UriSpace.lg),
        if (prefs.choice.isClassic)
          const _ClassicAppearance()
        else
          _LivingAppearance(choice: prefs.choice),
        const SizedBox(height: UriSpace.lg),
        const _PerformanceSettings(),
        const SizedBox(height: UriSpace.lg),
        const _VoiceSettings(),
      ],
    );
  }
}

TextStyle _label(BuildContext context) =>
    TextStyle(fontSize: UriType.body, color: UriColors.of(context).ink);

TextStyle _note(BuildContext context) =>
    TextStyle(fontSize: UriType.label, color: UriColors.of(context).inkFaint);

/// A setting that exists but cannot be used here, with the reason.
class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.title, required this.reason, super.key});
  final String title;
  final String reason;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Semantics(
      label: '$title: unavailable. $reason',
      excludeSemantics: true,
      child: Padding(
        padding: const EdgeInsets.symmetric(vertical: 6),
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(Icons.block_rounded, size: 15, color: c.inkFaint),
            const SizedBox(width: 8),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(title, style: TextStyle(fontSize: UriType.body, color: c.inkSoft)),
                  const SizedBox(height: 2),
                  Text(reason, style: _note(context)),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Companion picker
// ---------------------------------------------------------------------------

class _CompanionPicker extends StatelessWidget {
  const _CompanionPicker();

  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    final c = UriColors.of(context);
    final theme = prefs.choice.identity == null
        ? 'your Appearance choice below'
        : CompanionPreferences.themeFor(
            prefs.choice,
            UriThemeChoice.graphite,
          ).label;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            for (final choice in CompanionChoice.all)
              _CompanionCard(
                choice: choice,
                selected: prefs.choice == choice,
                onTap: () => prefs.select(choice),
              ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          'Theme: $theme. The companion sets the colours of the whole app.',
          key: const ValueKey('companion-theme-line'),
          style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
        ),
      ],
    );
  }
}

class _CompanionCard extends StatelessWidget {
  const _CompanionCard({
    required this.choice,
    required this.selected,
    required this.onTap,
  });

  final CompanionChoice choice;
  final bool selected;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final id = choice.identity;
    return Semantics(
      button: true,
      selected: selected,
      label: '${choice.label}. ${choice.tagline}',
      excludeSemantics: true,
      child: Material(
        color: selected ? c.accentSoft : c.surfaceSunken.withValues(alpha: 0.6),
        shape: RoundedRectangleBorder(
          borderRadius: BorderRadius.circular(UriRadius.md),
          side: BorderSide(
            color: selected ? c.accent : c.border,
            width: selected ? 1.5 : 1,
          ),
        ),
        clipBehavior: Clip.antiAlias,
        child: InkWell(
          key: ValueKey('companion-choice-${choice.key}'),
          onTap: onTap,
          child: SizedBox(
            width: 128,
            child: Padding(
              padding: const EdgeInsets.fromLTRB(10, 10, 10, 10),
              child: Column(
                children: [
                  SizedBox(
                    width: 64,
                    height: 64,
                    child: id == null
                        ? const EnergyOrb(
                            state: CompanionState.idle,
                            size: 64,
                            animate: false,
                            interactive: false,
                          )
                        : _StillCompanion(identity: id, size: 64),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    choice.label,
                    textAlign: TextAlign.center,
                    style: TextStyle(
                      fontSize: UriType.body,
                      fontWeight: FontWeight.w600,
                      color: c.ink,
                    ),
                  ),
                  const SizedBox(height: 2),
                  Text(
                    choice.tagline,
                    textAlign: TextAlign.center,
                    maxLines: 2,
                    style: TextStyle(fontSize: UriType.caption, color: c.inkSoft),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}

/// One still frame of a living companion: a picker thumbnail that costs one
/// shader pass, not a continuous animation per card.
class _StillCompanion extends StatelessWidget {
  const _StillCompanion({required this.identity, required this.size});
  final CompanionIdentity identity;
  final double size;

  @override
  Widget build(BuildContext context) {
    final scale = presenceScale(identity);
    if (!identity.usesShader) {
      // Ember is drawn from rendered clips; its tile is one small still frame
      // shipped for this purpose, not a decoded animation atlas.
      return Image.asset(
        EmberManifest.thumbnailPath,
        key: const ValueKey('companion-still-ember'),
        width: size * scale,
        height: size * scale,
        fit: BoxFit.contain,
        filterQuality: FilterQuality.medium,
        semanticLabel: identity.label,
      );
    }
    return OverflowBox(
      maxWidth: size * scale,
      maxHeight: size * scale,
      child: SizedBox(
        width: size * scale,
        height: size * scale,
        child: SoftDisc(
          outer: 1 / scale,
          child: CompanionOrbFrame(
            identity: identity,
            params: CompanionParams.of(identity, CompanionState.idle),
            seconds: 7,
          ),
        ),
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Appearance
// ---------------------------------------------------------------------------

class _LivingAppearance extends StatelessWidget {
  const _LivingAppearance({required this.choice});
  final CompanionChoice choice;

  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    final id = choice.identity!;
    final look = prefs.lookFor(choice);
    final words = CompanionLookVocabulary.of(id);
    void set(CompanionLook next) => prefs.setLook(choice, next);
    String pct(double v) => '${(v * 100).round()} %';
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Eyebrow(
          'Appearance · ${id.label}',
          trailing: look.isStandard
              ? null
              : TextButton(
                  key: const ValueKey('look-reset'),
                  onPressed: () => set(CompanionLook.standard),
                  child: const Text('Reset to designed look'),
                ),
        ),
        const SizedBox(height: 4),
        Text('Kept separately for each companion.', style: _note(context)),
        _LookSlider(
          keyName: 'size',
          label: 'Size',
          value: look.size,
          min: CompanionLook.sizeMin,
          max: CompanionLook.sizeMax,
          display: pct(look.size),
          onChanged: (v) => set(look.copyWith(size: v)),
        ),
        if (words.particles case final label?)
          _LookSlider(
            keyName: 'particles',
            label: label,
            value: look.particles,
            min: CompanionLook.particlesMin,
            max: CompanionLook.particlesMax,
            display: pct(look.particles),
            onChanged: (v) => set(look.copyWith(particles: v)),
          ),
        _LookSlider(
          keyName: 'glow',
          label: 'Glow',
          value: look.glow,
          min: CompanionLook.glowMin,
          max: CompanionLook.glowMax,
          display: pct(look.glow),
          onChanged: (v) => set(look.copyWith(glow: v)),
        ),
        if (words.atmosphere case final label?)
          _LookSlider(
            keyName: 'atmosphere',
            label: label,
            value: look.atmosphere,
            min: CompanionLook.atmosphereMin,
            max: CompanionLook.atmosphereMax,
            display: pct(look.atmosphere),
            onChanged: (v) => set(look.copyWith(atmosphere: v)),
          ),
        _LookSlider(
          keyName: 'motion',
          label: 'Animation intensity',
          value: look.motion,
          min: CompanionLook.motionMin,
          max: CompanionLook.motionMax,
          display: pct(look.motion),
          onChanged: (v) => set(look.copyWith(motion: v)),
        ),
        const SizedBox(height: 8),
        const _WaveformSwitch(),
      ],
    );
  }
}

class _LookSlider extends StatelessWidget {
  const _LookSlider({
    required this.keyName,
    required this.label,
    required this.value,
    required this.min,
    required this.max,
    required this.display,
    required this.onChanged,
  });

  final String keyName;
  final String label;
  final double value;
  final double min;
  final double max;
  final String display;
  final ValueChanged<double> onChanged;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Row(
      children: [
        SizedBox(width: 150, child: Text(label, style: _label(context))),
        Expanded(
          child: Slider(
            key: ValueKey('look-$keyName'),
            value: value.clamp(min, max),
            min: min,
            max: max,
            label: display,
            semanticFormatterCallback: (_) => '$label $display',
            onChanged: onChanged,
          ),
        ),
        SizedBox(
          width: 48,
          child: Text(
            display,
            textAlign: TextAlign.right,
            style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
          ),
        ),
      ],
    );
  }
}

class _WaveformSwitch extends StatelessWidget {
  const _WaveformSwitch();

  @override
  Widget build(BuildContext context) {
    final prefs = CompanionPreferences.of(context);
    return SwitchListTile(
      key: const ValueKey('voice-waveform-switch'),
      dense: true,
      contentPadding: EdgeInsets.zero,
      title: Text('Voice waveform', style: _label(context)),
      subtitle: Text(
        'The flowing oval under the transcript while you or URI speak. '
        'Off keeps the transcript and the companion\'s listening and speaking '
        'states. It responds the same to you and to URI either way.',
        style: _note(context),
      ),
      value: prefs.voice.waveform,
      onChanged: (v) => prefs.setVoice(prefs.voice.copyWith(waveform: v)),
    );
  }
}

/// The accepted classic orb keeps its own controls: style, palette and the
/// free choice of app theme.
class _ClassicAppearance extends StatelessWidget {
  const _ClassicAppearance();

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final themeCtl = LivingThemeController.maybeOf(context);
    return ListenableBuilder(
      listenable: Listenable.merge([services.orbVariant, services.orbPalette]),
      builder: (context, _) => Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Eyebrow('Orb style'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              for (final v in OrbVariant.values)
                ChoiceChip(
                  key: ValueKey('orb-variant-${v.name}'),
                  label: Text(v.label),
                  selected: services.orbVariant.value == v,
                  onSelected: (_) => services.orbVariant.value = v,
                ),
            ],
          ),
          const SizedBox(height: UriSpace.md),
          const Eyebrow('Orb palette'),
          const SizedBox(height: 8),
          Wrap(
            spacing: 8,
            runSpacing: 8,
            children: [
              ChoiceChip(
                key: const ValueKey('orb-palette-default'),
                label: const Text('Style default'),
                selected: services.orbPalette.value == null,
                onSelected: (_) => services.orbPalette.value = null,
              ),
              for (final p in OrbPalette.values)
                ChoiceChip(
                  key: ValueKey('orb-palette-${p.name}'),
                  avatar: SizedBox(
                    width: 18,
                    height: 10,
                    child: Row(
                      children: [
                        for (final h in p.hues.take(3))
                          Expanded(child: ColoredBox(color: h)),
                      ],
                    ),
                  ),
                  label: Text(p.label),
                  selected: services.orbPalette.value == p,
                  onSelected: (_) => services.orbPalette.value = p,
                ),
            ],
          ),
          const SizedBox(height: UriSpace.md),
          const Eyebrow('Appearance'),
          const SizedBox(height: 8),
          if (themeCtl != null)
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                for (final t in UriThemeChoice.values)
                  if (t != UriThemeChoice.system &&
                      t != UriThemeChoice.ivoryFoundry &&
                      t != UriThemeChoice.snowArchive &&
                      t != UriThemeChoice.ashLimestone)
                    ChoiceChip(
                      key: ValueKey('theme-${t.name}'),
                      avatar: CircleAvatar(
                        backgroundColor: t.swatch,
                        radius: 6,
                      ),
                      label: Text(t.label),
                      selected: themeCtl.current == t,
                      onSelected: (_) => themeCtl.setTheme(t),
                    ),
              ],
            ),
          const SizedBox(height: 8),
          Text(
            'Size, particle, glow, atmosphere and animation controls belong to '
            'the living companions; the classic orb is shaped by its style.',
            style: _note(context),
          ),
          const SizedBox(height: 4),
          const _WaveformSwitch(),
        ],
      ),
    );
  }
}

// ---------------------------------------------------------------------------
// Performance
// ---------------------------------------------------------------------------

class _PerformanceSettings extends StatelessWidget {
  const _PerformanceSettings();

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final prefs = CompanionPreferences.of(context);
    final governor = services.frameGovernor;
    final c = UriColors.of(context);
    return ListenableBuilder(
      listenable: Listenable.merge([governor, services.effects]),
      builder: (context, _) {
        final hz = governor.displayHz;
        final living = !prefs.choice.isClassic;
        // Render quality scales a shader's pixel work; Ember plays rendered
        // clips, so the choice would do nothing for it.
        final shaded = prefs.choice.identity?.usesShader ?? false;
        return Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            const Eyebrow('Performance'),
            const SizedBox(height: 8),
            Text('Frame rate', style: _label(context)),
            const SizedBox(height: 6),
            if (!living)
              const _Unavailable(
                key: ValueKey('fps-unavailable'),
                title: 'Frame rate',
                reason:
                    'The classic orb runs its own animation at the display '
                    'rate; frame-rate control applies to the living companions.',
              )
            else
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final m in FrameRateMode.values)
                    Tooltip(
                      message: m.supportedBy(hz)
                          ? (m == FrameRateMode.adaptive
                                ? 'Starts at the display rate and steps down only '
                                      'while frames run late'
                                : 'Requests ${m.label}; the hardware may not '
                                      'deliver every frame')
                          : 'This display refreshes at ${hz.round()} Hz',
                      child: ChoiceChip(
                        key: ValueKey('fps-${m.name}'),
                        label: Text(
                          m == FrameRateMode.adaptive
                              ? 'Adaptive (recommended)'
                              : m.label,
                        ),
                        selected: prefs.frameRate == m,
                        onSelected: m.supportedBy(hz)
                            ? (_) => prefs.setFrameRate(m)
                            : null,
                      ),
                    ),
                ],
              ),
            const SizedBox(height: 6),
            Text(
              _rateNote(governor, prefs),
              key: const ValueKey('fps-note'),
              style: _note(context),
            ),
            const SizedBox(height: UriSpace.md),
            Text('Render quality', style: _label(context)),
            const SizedBox(height: 6),
            if (shaded)
              Wrap(
                spacing: 8,
                runSpacing: 8,
                children: [
                  for (final q in RenderQuality.values)
                    Tooltip(
                      message: q.detail,
                      child: ChoiceChip(
                        key: ValueKey('quality-${q.name}'),
                        label: Text(q.label),
                        selected: prefs.quality == q,
                        onSelected: (_) => prefs.setQuality(q),
                      ),
                    ),
                ],
              )
            else if (living)
              const _Unavailable(
                key: ValueKey('quality-unavailable'),
                title: 'Render quality',
                reason:
                    'Ember plays animation rendered in advance, not a shader; '
                    'render quality applies to the shader companions.',
              )
            else
              const _Unavailable(
                key: ValueKey('quality-unavailable'),
                title: 'Render quality',
                reason:
                    'The classic orb is drawn with vector paths, not a shader; '
                    'render quality applies to the living companions.',
              ),
            if (shaded) ...[
              const SizedBox(height: 6),
              Text(
                '${prefs.quality.detail}. Lower quality computes fewer pixels '
                'and is softer in the finest embers and petals.',
                style: _note(context),
              ),
            ],
            const SizedBox(height: UriSpace.sm),
            SwitchListTile(
              key: const ValueKey('stats-overlay-switch'),
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('Performance statistics', style: _label(context)),
              subtitle: Text(
                'Measured frame rate, frame times and quality, in a corner.',
                style: _note(context),
              ),
              value: prefs.statsOverlay,
              onChanged: prefs.setStatsOverlay,
            ),
            SwitchListTile(
              key: const ValueKey('reduced-effects-switch'),
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('Reduced visual effects', style: _label(context)),
              subtitle: Text(
                'No shader, blur or glow. Every state stays readable.',
                style: _note(context),
              ),
              value: services.effects.reducedEffects,
              onChanged: (v) => services.effects.setReducedEffects(v),
            ),
            SwitchListTile(
              dense: true,
              contentPadding: EdgeInsets.zero,
              title: Text('Reduced motion', style: _label(context)),
              subtitle: Text(
                'The companion holds still; state shows by colour and label.',
                style: TextStyle(fontSize: UriType.label, color: c.inkFaint),
              ),
              value: services.effects.reducedMotion,
              onChanged: (v) => services.effects.setReducedMotion(v),
            ),
          ],
        );
      },
    );
  }

  static String _rateNote(
    CompanionFrameGovernor g,
    CompanionPreferences prefs,
  ) {
    final hz = g.displayHz.round();
    final target = g.effectiveCap.round();
    if (prefs.frameRate == FrameRateMode.adaptive) {
      return 'Display $hz Hz. Adaptive is currently targeting $target FPS.';
    }
    final fixed = prefs.frameRate.fixedFps!.round();
    final uneven = hz % fixed != 0 && fixed < hz;
    return 'Display $hz Hz. A fixed rate is a request, not a guarantee.'
        '${uneven ? ' $fixed does not divide $hz, so frames alternate between '
                  'two refresh intervals.' : ''}';
  }
}

// ---------------------------------------------------------------------------
// Voice and audio
// ---------------------------------------------------------------------------

class _VoiceSettings extends StatefulWidget {
  const _VoiceSettings();

  @override
  State<_VoiceSettings> createState() => _VoiceSettingsState();
}

class _VoiceSettingsState extends State<_VoiceSettings> {
  Future<VoiceListing>? _listing;
  String? _previewing;
  String? _previewError;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _listing ??= LivingScope.of(context).voiceCatalog.list();
  }

  @override
  void dispose() {
    if (_previewing != null) {
      // Leaving the page stops a preview rather than letting it talk on.
      _catalog?.stopPreview();
    }
    super.dispose();
  }

  VoiceCatalog? _catalog;

  Future<void> _preview(VoiceInfo v, VoicePreferences p) async {
    final catalog = _catalog = LivingScope.of(context).voiceCatalog;
    if (_previewing == v.id) {
      await catalog.stopPreview();
      if (mounted) setState(() => _previewing = null);
      return;
    }
    setState(() {
      _previewing = v.id;
      _previewError = null;
    });
    try {
      await catalog.preview(v, p);
    } on VoicePreviewError catch (e) {
      if (mounted) setState(() => _previewError = e.message);
    } catch (e) {
      if (mounted) setState(() => _previewError = '$e');
    }
    if (mounted && _previewing == v.id) setState(() => _previewing = null);
  }

  @override
  Widget build(BuildContext context) {
    final services = LivingScope.of(context);
    final prefs = CompanionPreferences.of(context);
    final c = UriColors.of(context);
    final adapter = services.voiceAdapter;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Eyebrow('Voice and audio'),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: Text(
                adapter == null
                    ? 'URI does not listen or speak in this build yet: no voice '
                          'service is connected. These choices apply to the '
                          'previews now and to URI\'s voice when it is.'
                    : 'Voice service: ${adapter.name}.',
                key: const ValueKey('voice-service-line'),
                style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
              ),
            ),
            if (adapter?.simulated ?? false) ...[
              const SizedBox(width: 8),
              const StatusBadge.simulated(compact: true),
            ],
          ],
        ),
        const SizedBox(height: 10),
        if (services.voiceInteraction != null)
          VoiceInputSettings(controller: services.voiceInteraction!),
        FutureBuilder<VoiceListing>(
          future: _listing,
          builder: (context, snap) {
            if (!snap.hasData) {
              return Padding(
                padding: const EdgeInsets.symmetric(vertical: 8),
                child: Text(
                  'Looking for installed voices…',
                  style: _note(context),
                ),
              );
            }
            return _voiceBody(context, snap.data!, prefs);
          },
        ),
      ],
    );
  }

  Widget _voiceBody(
    BuildContext context,
    VoiceListing listing,
    CompanionPreferences prefs,
  ) {
    final c = UriColors.of(context);
    final vp = prefs.voice;
    if (listing.voices.isEmpty) {
      return _Unavailable(
        key: const ValueKey('voices-unavailable'),
        title: 'Voices',
        reason:
            listing.unavailableReason ??
            'No installed voice was found. Windows voices are added in '
                'Windows Settings, Time & language, Speech.',
      );
    }
    final langs = listing.languages;
    final shown = [
      for (final v in listing.voices)
        if (vp.language == null || v.culture == vp.language) v,
    ];
    final usable = [
      for (final v in listing.voices)
        if (v.usable) v,
    ];
    final selected =
        usable.where((v) => v.id == vp.voiceId).firstOrNull ??
        usable.firstOrNull;
    final caps = selected?.capabilities ?? const VoiceCapabilities();
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (langs.length > 1) ...[
          Text('Language', style: _label(context)),
          const SizedBox(height: 6),
          Wrap(
            spacing: 8,
            children: [
              ChoiceChip(
                label: const Text('All'),
                selected: vp.language == null,
                onSelected: (_) => prefs.setVoice(vp.copyWith(language: null)),
              ),
              for (final l in langs)
                ChoiceChip(
                  key: ValueKey('voice-lang-$l'),
                  label: Text(l),
                  selected: vp.language == l,
                  onSelected: (_) => prefs.setVoice(vp.copyWith(language: l)),
                ),
            ],
          ),
          const SizedBox(height: 8),
        ] else
          Text(
            'Language: ${langs.isEmpty ? 'unknown' : langs.single} (the only '
            'language of the installed voices).',
            key: const ValueKey('voice-language-line'),
            style: _note(context),
          ),
        const SizedBox(height: 4),
        for (final engine in VoiceEngine.values)
          if (shown.any((v) => v.engine == engine)) ...[
            Padding(
              padding: const EdgeInsets.only(top: 8, bottom: 2),
              child: Text(
                engine.label,
                style: TextStyle(
                  fontSize: UriType.label,
                  fontWeight: FontWeight.w600,
                  color: c.inkSoft,
                ),
              ),
            ),
            for (final v in shown.where((v) => v.engine == engine))
              _VoiceRow(
                voice: v,
                selected: selected?.id == v.id,
                previewing: _previewing == v.id,
                onSelect: v.usable
                    ? () => prefs.setVoice(vp.copyWith(voiceId: v.id))
                    : null,
                onPreview: v.usable ? () => _preview(v, prefs.voice) : null,
              ),
          ],
        for (final e in listing.engineErrors)
          Padding(
            padding: const EdgeInsets.only(top: 4),
            child: Text(e, style: TextStyle(fontSize: UriType.label, color: c.warning)),
          ),
        if (_previewError != null)
          Padding(
            padding: const EdgeInsets.only(top: 6),
            child: Text(
              'Preview failed: $_previewError',
              key: const ValueKey('voice-preview-error'),
              style: TextStyle(fontSize: UriType.label, color: c.danger),
            ),
          ),
        const SizedBox(height: 10),
        _IntSlider(
          keyName: 'volume',
          label: 'Speaker volume',
          enabled: caps.volume,
          value: vp.volume,
          min: 0,
          max: 100,
          display: '${vp.volume} %',
          onChanged: (v) => prefs.setVoice(vp.copyWith(volume: v)),
        ),
        _IntSlider(
          keyName: 'rate',
          label: 'Speech speed',
          enabled: caps.rate,
          value: vp.rate,
          min: -10,
          max: 10,
          display: vp.rate == 0
              ? 'Normal'
              : (vp.rate > 0 ? '+${vp.rate}' : '${vp.rate}'),
          onChanged: (v) => prefs.setVoice(vp.copyWith(rate: v)),
        ),
        _IntSlider(
          keyName: 'pitch',
          label: 'Pitch',
          enabled: caps.pitch,
          value: vp.pitch,
          min: -10,
          max: 10,
          display: vp.pitch == 0
              ? 'Natural'
              : (vp.pitch > 0 ? '+${vp.pitch}' : '${vp.pitch}'),
          onChanged: (v) => prefs.setVoice(vp.copyWith(pitch: v)),
        ),
        if (!caps.style)
          const _Unavailable(
            key: ValueKey('voice-style-unavailable'),
            title: 'Tone and speaking style',
            reason: 'None of the installed voices offers speaking styles.',
          ),
        _Unavailable(
          key: const ValueKey('mic-gain-unavailable'),
          title: 'Microphone input gain',
          reason: LivingScope.of(context).voiceInteraction == null
              ? 'URI does not capture microphone audio in this build. Windows '
                    'sets the microphone level in Sound settings.'
              : 'URI records at the level Windows sets; change it in Windows '
                    'Sound settings.',
        ),
      ],
    );
  }
}

class _VoiceRow extends StatelessWidget {
  const _VoiceRow({
    required this.voice,
    required this.selected,
    required this.previewing,
    required this.onSelect,
    required this.onPreview,
  });

  final VoiceInfo voice;
  final bool selected;
  final bool previewing;
  final VoidCallback? onSelect;
  final VoidCallback? onPreview;

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final detail = [
      voice.culture,
      if (voice.gender != null && voice.gender!.isNotEmpty) voice.gender!,
      if (!voice.usable) voice.reason ?? 'Unavailable',
    ].join(' · ');
    return ListTile(
      key: ValueKey('voice-row-${voice.id}'),
      dense: true,
      contentPadding: EdgeInsets.zero,
      enabled: voice.usable,
      onTap: onSelect,
      leading: Icon(
        selected ? Icons.radio_button_checked : Icons.radio_button_unchecked,
        size: 18,
        color: voice.usable ? c.accent : c.inkFaint,
      ),
      title: Text(
        voice.name,
        style: TextStyle(
          fontSize: UriType.body,
          color: voice.usable ? c.ink : c.inkFaint,
        ),
      ),
      subtitle: Text(
        detail,
        style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
      ),
      trailing: onPreview == null
          ? null
          : TextButton.icon(
              key: ValueKey('voice-preview-${voice.id}'),
              onPressed: onPreview,
              icon: Icon(
                previewing ? Icons.stop_rounded : Icons.play_arrow_rounded,
                size: 16,
              ),
              label: Text(previewing ? 'Stop' : 'Preview'),
            ),
    );
  }
}

class _IntSlider extends StatelessWidget {
  const _IntSlider({
    required this.keyName,
    required this.label,
    required this.enabled,
    required this.value,
    required this.min,
    required this.max,
    required this.display,
    required this.onChanged,
  });

  final String keyName;
  final String label;
  final bool enabled;
  final int value;
  final int min;
  final int max;
  final String display;
  final ValueChanged<int> onChanged;

  @override
  Widget build(BuildContext context) {
    if (!enabled) {
      return _Unavailable(
        key: ValueKey('voice-$keyName-unavailable'),
        title: label,
        reason: 'Not supported by the selected voice.',
      );
    }
    final c = UriColors.of(context);
    return Row(
      children: [
        SizedBox(width: 150, child: Text(label, style: _label(context))),
        Expanded(
          child: Slider(
            key: ValueKey('voice-$keyName'),
            value: value.toDouble(),
            min: min.toDouble(),
            max: max.toDouble(),
            divisions: max - min,
            label: display,
            semanticFormatterCallback: (_) => '$label $display',
            onChanged: (v) => onChanged(v.round()),
          ),
        ),
        SizedBox(
          width: 56,
          child: Text(
            display,
            textAlign: TextAlign.right,
            style: TextStyle(fontSize: UriType.label, color: c.inkSoft),
          ),
        ),
      ],
    );
  }
}
