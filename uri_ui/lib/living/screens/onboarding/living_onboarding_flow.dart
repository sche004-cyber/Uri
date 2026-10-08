import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../models/user_preferences.dart';
import '../../../services/app_state_scope.dart';
import '../../../services/uri_client.dart';
import '../../../theme/glass_theme.dart';
import '../../../theme/uri_theme.dart';
import '../../companion/companion_state.dart';
import '../../companion/energy_orb.dart';
import '../../living_app.dart';
import '../../living_scope.dart';
import '../../widgets/glass_panel.dart';
import '../../widgets/status_badge.dart';
import '../workspace_mode_view.dart' show HarnessRow, PermissionRow;

/// Guided first-run setup, eight steps, one glass card, the orb above
/// it previewing the state each step talks about.
///
/// Honesty: every control that is backed by a real UI-side preference
/// (approval boundary, focus areas, theme, effects) writes that
/// preference. Every status that comes from a mock source is badged
/// Simulated. The flow never performs or proxies a login and never
/// reads credentials; it shows the owner the exact action required.
class LivingOnboardingFlow extends StatefulWidget {
  const LivingOnboardingFlow({super.key, required this.onFinished});
  final Future<void> Function() onFinished;

  static const stepTitles = [
    'What URI is',
    'Connect',
    'Harness',
    'Brain',
    'Permissions',
    'Sign-in & qualification',
    'Your workspace',
    'Ready?',
  ];

  @override
  State<LivingOnboardingFlow> createState() => _LivingOnboardingFlowState();
}

class _LivingOnboardingFlowState extends State<LivingOnboardingFlow> {
  int _step = 0;
  CompanionState _preview = CompanionState.idle;
  ConnectionCheckResult? _connection;
  bool _checking = false;
  late Future<List<ProviderEntry>> _providers;
  final Set<String> _focusAreas = {};
  late final TextEditingController _address;

  static const _focusOptions = [
    'Email & correspondence',
    'Document drafting',
    'Spreadsheets & records',
    'Research',
    'Approvals & compliance',
  ];

  @override
  void initState() {
    super.initState();
    final s = context.getInheritedWidgetOfExactType<AppStateScope>()!.notifier!;
    _providers = s.listProviders();
    _address = TextEditingController(text: s.baseUrl);
    _focusAreas.addAll(s.preferences.focusAreas);
  }

  @override
  void dispose() {
    _address.dispose();
    super.dispose();
  }

  CompanionState _previewFor(int step) => switch (step) {
        0 => _preview,
        1 => CompanionState.thinking,
        2 => CompanionState.working,
        3 => CompanionState.idle,
        4 => CompanionState.awaitingApproval,
        5 => CompanionState.error,
        6 => CompanionState.listening,
        _ => CompanionState.success,
      };

  void _go(int delta) {
    setState(() => _step = (_step + delta).clamp(0, LivingOnboardingFlow.stepTitles.length - 1));
  }

  Future<void> _finish() async {
    final s = AppStateScope.of(context);
    await s.updatePreferences(s.preferences.copyWith(
      focusAreas: _focusAreas.toList(),
      completedOnboarding: true,
    ));
    await widget.onFinished();
  }

  Future<void> _testConnection() async {
    final s = AppStateScope.of(context);
    setState(() => _checking = true);
    final ok = await s.checkConnection(addressOverride: _address.text.trim());
    if (!mounted) return;
    setState(() {
      _checking = false;
      _connection = ok
          ? const ConnectionCheckResult.reachable()
          : ConnectionCheckResult.unreachable(s.lastConnectionErrorDetail);
    });
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    final services = LivingScope.of(context);
    final last = _step == LivingOnboardingFlow.stepTitles.length - 1;
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: AmbientBackground(
        lightAt: const Alignment(0, -0.8),
        child: Center(
          child: ConstrainedBox(
            constraints: const BoxConstraints(maxWidth: 760),
            child: Padding(
              padding: const EdgeInsets.all(UriSpace.md),
              child: Column(
                children: [
                  const SizedBox(height: 8),
                  EnergyOrb(
                    key: const ValueKey('onboarding-orb'),
                    state: _previewFor(_step),
                    size: 150,
                  ),
                  const SizedBox(height: 6),
                  Text(_previewFor(_step).label, style: TextStyle(fontSize: 12.5, color: c.inkSoft)),
                  const SizedBox(height: 12),
                  _StepDots(count: LivingOnboardingFlow.stepTitles.length, index: _step),
                  const SizedBox(height: 12),
                  Expanded(
                    child: GlassPanel(
                      padding: const EdgeInsets.all(UriSpace.lg),
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Row(
                            children: [
                              Expanded(
                                child: Text(
                                  LivingOnboardingFlow.stepTitles[_step],
                                  key: const ValueKey('onboarding-step-title'),
                                  style: TextStyle(fontSize: 20, fontWeight: FontWeight.w700, color: c.ink),
                                ),
                              ),
                              Text('${_step + 1} / ${LivingOnboardingFlow.stepTitles.length}',
                                  style: TextStyle(fontSize: 12, color: c.inkFaint)),
                            ],
                          ),
                          const SizedBox(height: 12),
                          Expanded(
                            child: SingleChildScrollView(
                              child: AnimatedSwitcher(
                                duration: UriMotion.fast,
                                child: KeyedSubtree(
                                  key: ValueKey(_step),
                                  child: _buildStep(context, services),
                                ),
                              ),
                            ),
                          ),
                          const SizedBox(height: 12),
                          Row(
                            children: [
                              TextButton(
                                key: const ValueKey('onboarding-skip'),
                                onPressed: _finish,
                                child: const Text('Skip setup'),
                              ),
                              const Spacer(),
                              if (_step > 0)
                                OutlinedButton(
                                  key: const ValueKey('onboarding-back'),
                                  onPressed: () => _go(-1),
                                  child: const Text('Back'),
                                ),
                              const SizedBox(width: 8),
                              FilledButton(
                                key: const ValueKey('onboarding-next'),
                                style: FilledButton.styleFrom(backgroundColor: glass.glow, foregroundColor: c.canvas),
                                onPressed: last ? _finish : () => _go(1),
                                child: Text(last ? 'Start using URI' : 'Next'),
                              ),
                            ],
                          ),
                        ],
                      ),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildStep(BuildContext context, LivingServices services) {
    final s = AppStateScope.of(context);
    final c = UriColors.of(context);
    final body = TextStyle(fontSize: 13.5, color: c.inkSoft, height: 1.5);
    switch (_step) {
      case 0:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'URI is a personal AI companion and work environment. It understands what you ask, proposes what it would do, and acts only after you approve. It has one form, the orb, that lives in three places:',
              style: body,
            ),
            const SizedBox(height: 10),
            _Bullet('Companion', 'a small floating orb for quick questions.'),
            _Bullet('Workspace', 'conversation, tasks, documents and settings side by side.'),
            _Bullet('Dashboard', 'what URI can do, is doing, and is made of.'),
            const SizedBox(height: 12),
            Text('Tap a state to see how the orb shows it:', style: body),
            const SizedBox(height: 6),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final st in CompanionState.values)
                  ChoiceChip(
                    key: ValueKey('preview-${st.name}'),
                    label: Text(st.label),
                    selected: _preview == st,
                    onSelected: (_) => setState(() => _preview = st),
                  ),
              ],
            ),
            const SizedBox(height: 8),
            Row(
              children: [
                const StatusBadge.simulated(compact: true),
                const SizedBox(width: 6),
                Expanded(child: Text('Listening and Speaking have no source in this build; they are previews.', style: TextStyle(fontSize: 11.5, color: c.inkFaint))),
              ],
            ),
          ],
        );
      case 1:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('This client talks to a URI server. On this PC that is the local server; a phone needs the PC\'s address.', style: body),
            const SizedBox(height: 10),
            TextField(
              key: const ValueKey('onboarding-address'),
              controller: _address,
              decoration: const InputDecoration(labelText: 'URI server address'),
            ),
            const SizedBox(height: 10),
            Row(
              children: [
                OutlinedButton(
                  key: const ValueKey('onboarding-test-connection'),
                  onPressed: _checking ? null : _testConnection,
                  child: Text(_checking ? 'Checking…' : 'Test connection'),
                ),
                const SizedBox(width: 10),
                if (_connection != null)
                  StatusBadge(
                    services.appDataIsMock
                        ? TruthStatus.simulated
                        : (_connection!.reachable ? TruthStatus.configured : TruthStatus.unavailable),
                    compact: true,
                  ),
                if (_connection != null) ...[
                  const SizedBox(width: 8),
                  Expanded(
                    child: Text(
                      _connection!.reachable
                          ? (services.appDataIsMock ? 'Mock client answered; no real server was contacted.' : 'Server reachable.')
                          : (_connection!.detail ?? 'Not reachable'),
                      style: TextStyle(fontSize: 12, color: c.inkSoft),
                    ),
                  ),
                ],
              ],
            ),
          ],
        );
      case 2:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('A harness is an external agent URI can hand qualified work to. Only a qualified, signed-in harness can be selected; the required action for the others is shown as reported.', style: body),
            const SizedBox(height: 10),
            for (final h in services.readiness.harnesses) HarnessRow(fact: h),
          ],
        );
      case 3:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('The Brain is the model URI thinks with. A local Brain keeps everything on this machine; an external provider needs a key you add in Settings.', style: body),
            const SizedBox(height: 10),
            FutureBuilder<List<ProviderEntry>>(
              future: _providers,
              builder: (context, snap) {
                final list = snap.data ?? const <ProviderEntry>[];
                if (list.isEmpty) return Text('No providers reported.', style: body);
                return ListenableBuilder(
                  listenable: s,
                  builder: (context, _) => Column(
                    children: [
                      for (final p in list)
                        RadioListTile<String>(
                          key: ValueKey('brain-${p.providerId}'),
                          value: p.providerId,
                          // ignore: deprecated_member_use
                          groupValue: s.activeBrain?.providerId,
                          // ignore: deprecated_member_use
                          onChanged: p.configured && p.available
                              ? (v) => s.setActiveBrain(p.providerId)
                              : null,
                          dense: true,
                          contentPadding: EdgeInsets.zero,
                          title: Text(p.displayName, style: TextStyle(fontSize: 13, color: c.ink)),
                          subtitle: Text(
                            '${p.adapter == 'ollama' ? 'Local' : 'External'} · ${p.configured ? (p.available ? 'available' : 'configured, not reachable') : 'needs a key'}',
                            style: TextStyle(fontSize: 11.5, color: c.inkFaint),
                          ),
                          secondary: services.appDataIsMock ? const StatusBadge.simulated(compact: true) : null,
                        ),
                    ],
                  ),
                );
              },
            ),
          ],
        );
      case 4:
        return ListenableBuilder(
          listenable: s,
          builder: (context, _) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('URI proposes; you decide. Choose how often it should ask. Typed or spoken words never approve anything; only the Approve button does.', style: body),
              const SizedBox(height: 8),
              for (final level in AutonomyLevel.values)
                RadioListTile<AutonomyLevel>(
                  key: ValueKey('autonomy-${level.name}'),
                  value: level,
                  // ignore: deprecated_member_use
                  groupValue: s.preferences.autonomyLevel,
                  // ignore: deprecated_member_use
                  onChanged: (v) => s.updatePreferences(s.preferences.copyWith(autonomyLevel: v)),
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  title: Text(
                    level == AutonomyLevel.askEveryTime
                        ? 'Ask me before every action'
                        : 'Auto-approve routine actions, ask for the rest',
                    style: TextStyle(fontSize: 13, color: c.ink),
                  ),
                ),
              const SizedBox(height: 8),
              for (final p in services.readiness.permissions) PermissionRow(fact: p),
            ],
          ),
        );
      case 5:
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('URI never signs in for you and never reads your credentials. Each harness reports its own sign-in and qualification state; when something is required, the exact action is shown.', style: body),
            const SizedBox(height: 10),
            Table(
              columnWidths: const {0: FlexColumnWidth(2), 1: FlexColumnWidth(1.2), 2: FlexColumnWidth(1.4), 3: IntrinsicColumnWidth()},
              children: [
                TableRow(children: [
                  for (final h in ['Harness', 'Sign-in', 'Qualification', ''])
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 4),
                      child: Text(h, style: TextStyle(fontSize: 11, fontWeight: FontWeight.w700, color: c.inkFaint)),
                    ),
                ]),
                for (final h in services.readiness.harnesses)
                  TableRow(children: [
                    Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(h.displayName, style: TextStyle(fontSize: 13, color: c.ink))),
                    Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(h.authState, style: TextStyle(fontSize: 12, color: c.inkSoft))),
                    Padding(padding: const EdgeInsets.symmetric(vertical: 6), child: Text(h.qualification, style: TextStyle(fontSize: 12, color: c.inkSoft))),
                    Padding(
                      padding: const EdgeInsets.symmetric(vertical: 6),
                      child: StatusBadge(h.simulated ? TruthStatus.simulated : h.truth, compact: true),
                    ),
                  ]),
              ],
            ),
          ],
        );
      case 6:
        final themeCtl = LivingThemeController.maybeOf(context);
        return Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('What will you mostly use URI for? This shapes what it looks for first.', style: body),
            const SizedBox(height: 8),
            Wrap(
              spacing: 6,
              runSpacing: 6,
              children: [
                for (final f in _focusOptions)
                  FilterChip(
                    key: ValueKey('focus-$f'),
                    label: Text(f),
                    selected: _focusAreas.contains(f),
                    onSelected: (v) => setState(() => v ? _focusAreas.add(f) : _focusAreas.remove(f)),
                  ),
              ],
            ),
            const SizedBox(height: 14),
            Text('Appearance', style: TextStyle(fontSize: 13, fontWeight: FontWeight.w600, color: c.ink)),
            const SizedBox(height: 6),
            if (themeCtl != null)
              Wrap(
                spacing: 6,
                runSpacing: 6,
                children: [
                  for (final t in UriThemeChoice.values)
                    if (t != UriThemeChoice.system)
                      ChoiceChip(
                        avatar: CircleAvatar(backgroundColor: t.swatch, radius: 6),
                        label: Text(t.label),
                        selected: themeCtl.current == t,
                        onSelected: (_) => themeCtl.setTheme(t),
                      ),
                ],
              ),
            ListenableBuilder(
              listenable: services.effects,
              builder: (context, _) => SwitchListTile(
                key: const ValueKey('onboarding-reduced-effects'),
                dense: true,
                contentPadding: EdgeInsets.zero,
                title: Text('Reduced visual effects', style: TextStyle(fontSize: 13, color: c.ink)),
                subtitle: Text('Turn off the shader, blur and glow. Good for older GPUs or remote desktops.', style: TextStyle(fontSize: 11.5, color: c.inkFaint)),
                value: services.effects.reducedEffects,
                onChanged: (v) async {
                  services.effects.setReducedEffects(v);
                  final prefs = await SharedPreferences.getInstance();
                  await prefs.setBool(LivingPrefs.reducedEffects, v);
                },
              ),
            ),
          ],
        );
      default:
        return ListenableBuilder(
          listenable: services.readiness,
          builder: (context, _) => Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text('Readiness, as currently known. Anything marked Simulated comes from the mock and will be re-checked against the real server when URI is connected.', style: body),
              const SizedBox(height: 10),
              for (final ch in services.readiness.checks)
                Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: Row(
                    children: [
                      Icon(
                        switch (ch.status) {
                          TruthStatus.qualified || TruthStatus.configured => Icons.check_circle_rounded,
                          TruthStatus.unavailable => Icons.cancel_rounded,
                          _ => Icons.help_outline_rounded,
                        },
                        size: 16,
                        color: switch (ch.status) {
                          TruthStatus.qualified || TruthStatus.configured => c.success,
                          TruthStatus.unavailable => c.danger,
                          _ => c.warning,
                        },
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            Text(ch.label, style: TextStyle(fontSize: 13, color: c.ink)),
                            if (ch.detail != null)
                              Text(ch.detail!, style: TextStyle(fontSize: 11.5, color: c.inkFaint)),
                          ],
                        ),
                      ),
                      StatusBadge(ch.status, compact: true),
                    ],
                  ),
                ),
              const SizedBox(height: 8),
              OutlinedButton.icon(
                onPressed: services.readiness.refresh,
                icon: const Icon(Icons.refresh_rounded, size: 16),
                label: const Text('Re-check'),
              ),
            ],
          ),
        );
    }
  }
}

class _Bullet extends StatelessWidget {
  const _Bullet(this.title, this.text);
  final String title;
  final String text;
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(Icons.circle, size: 6, color: c.accent),
          const SizedBox(width: 10),
          Expanded(
            child: RichText(
              text: TextSpan(
                style: TextStyle(fontSize: 13.5, color: c.inkSoft, height: 1.5),
                children: [
                  TextSpan(text: '$title: ', style: TextStyle(fontWeight: FontWeight.w600, color: c.ink)),
                  TextSpan(text: text),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

class _StepDots extends StatelessWidget {
  const _StepDots({required this.count, required this.index});
  final int count;
  final int index;
  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        for (var i = 0; i < count; i++)
          AnimatedContainer(
            duration: UriMotion.fast,
            margin: const EdgeInsets.symmetric(horizontal: 3),
            width: i == index ? 18 : 6,
            height: 6,
            decoration: BoxDecoration(
              color: i <= index ? c.accent : c.border,
              borderRadius: BorderRadius.circular(3),
            ),
          ),
      ],
    );
  }
}
