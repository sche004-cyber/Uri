from pathlib import Path
p=Path('uri_ui/lib/living/presentation/living_shell.dart');s=p.read_text(encoding='utf-8');a=s.index('  @override\n  void didChangeDependencies()',s.index('class _LivingShellState'));b=s.index('  void _holdOrbit()',a);s=s[:a]+'''  bool _orbitListening = false;
  void _configureOrbit(LivingServices services, bool enabled) {
    final clock = services.frameClock;
    if (!identical(clock, _orbitClock)) {
      if (_orbitListening) _orbitClock?.removeListener(_orbitTick);
      _orbitListening = false;
      _orbitClock = clock;
    }
    if (enabled == _orbitListening) return;
    _orbitListening = enabled;
    if (enabled) { clock.addListener(_orbitTick); }
    else { clock.removeListener(_orbitTick); }
  }

'''+s[b:];s=s.replace('        services.presentation,','        services.presentation,\n        services.effects,',1);s=s.replace('            final shellSize = Size(constraints.maxWidth, constraints.maxHeight);','''            final shellSize = Size(constraints.maxWidth, constraints.maxHeight);
            _configureOrbit(services, services.visualV2 && _panelExpanded && !_chatOpen &&
              mode == UiPresentationMode.companion && !services.effects.reducedMotion &&
              !MediaQuery.disableAnimationsOf(context) && MediaQuery.textScalerOf(context).scale(14) / 14 <= 1.2);''');p.write_text(s,encoding='utf-8')
