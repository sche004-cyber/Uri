from pathlib import Path
p=Path('uri_ui/lib/living/presentation/companion_window_layout.dart');s=p.read_text(encoding='utf-8').replace('this.controls,','this.controls,\n    this.orbit,').replace('final Rect? controls;', 'final Rect? controls;\n  final Rect? orbit;').replace("    'buttons': [", "    'orbit': orbit == null ? null : [orbit!.left, orbit!.top, orbit!.right, orbit!.bottom],\n    'buttons': [").replace('other.controls == controls &&','other.controls == controls &&\n      other.orbit == orbit &&').replace('Object.hash(active, orb, panel, controls, Object.hashAll(buttons))','Object.hash(active, orb, panel, controls, orbit, Object.hashAll(buttons))');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/windows/runner/flutter_window.cpp');s=p.read_text(encoding='utf-8').replace('#include <algorithm>', '#include <algorithm>\n#include <cmath>\n#include <vector>')
s=s.replace('    if (call.method_name() == "facts") {', '''    if (call.method_name() == "cursor") {
      POINT pointer; GetCursorPos(&pointer); ScreenToClient(hwnd, &pointer);
      const double dpi = GetDpiForWindow(hwnd) / 96.0;
      result->Success(flutter::EncodableValue(flutter::EncodableList{
        flutter::EncodableValue(pointer.x / dpi), flutter::EncodableValue(pointer.y / dpi)})); return;
    }
    if (call.method_name() == "facts") {''')
s=s.replace('    HRGN panel = region("panel", false);', '''    // Narrow decoration regions preserve visible arcs without giving the
    // transparent ring interior a desktop hit target.
    HRGN orbit = region("orbit", true);
    if (orbit) {
      RECT b; GetRgnBox(orbit, &b); DeleteObject(orbit);
      const double cx=(b.left+b.right)/2.0, cy=(b.top+b.bottom)/2.0;
      const double r=(b.right-b.left)/2.0;
      const int stroke=std::max(1, static_cast<int>(std::ceil(scale)));
      HRGN outer=CreateEllipticRgn(b.left-stroke,b.top-stroke,b.right+stroke,b.bottom+stroke);
      HRGN inner=CreateEllipticRgn(b.left+stroke,b.top+stroke,b.right-stroke,b.bottom-stroke);
      CombineRgn(outer,outer,inner,RGN_DIFF); DeleteObject(inner);
      for (double a : {-1.38, .23, 1.78, 3.36}) {
        std::vector<POINT> points{{static_cast<LONG>(cx),static_cast<LONG>(cy)}};
        for (int n=0;n<=16;++n) {
          const double t=a+.65*n/16;
          points.push_back({static_cast<LONG>(cx+(r+4*scale)*std::cos(t)),static_cast<LONG>(cy+(r+4*scale)*std::sin(t))});
        }
        HRGN wedge=CreatePolygonRgn(points.data(),static_cast<int>(points.size()),WINDING);
        CombineRgn(wedge,wedge,outer,RGN_AND); CombineRgn(orb,orb,wedge,RGN_OR); DeleteObject(wedge);
        const int x=static_cast<int>(cx+r*std::cos(a+.23)), y=static_cast<int>(cy+r*std::sin(a+.23));
        const int d=static_cast<int>(std::ceil(2*scale));
        HRGN dot=CreateEllipticRgn(x-d,y-d,x+d,y+d); CombineRgn(orb,orb,dot,RGN_OR); DeleteObject(dot);
      }
      DeleteObject(outer);
    }
    HRGN panel = region("panel", false);''')
s=s.replace('HRGN r=CreateRoundRectRgn(v[0],v[1],v[2],v[3],static_cast<int>(16*scale),static_cast<int>(16*scale));', '''HRGN r = std::abs((v[2]-v[0])-(v[3]-v[1])) <= 1
              ? CreateEllipticRgn(v[0],v[1],v[2],v[3])
              : CreateRoundRectRgn(v[0],v[1],v[2],v[3],static_cast<int>(16*scale),static_cast<int>(16*scale));''')
p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/services/companion_window_adapter.dart');s=p.read_text(encoding='utf-8');i=s.index('  Future<void> move()');s=s[:i]+'''  /// Own-window cursor coordinates only; no global hooks or observation.
  Future<Offset?> cursorPosition() async {
    if (!Platform.isWindows) return null;
    try {
      final point = await _channel.invokeListMethod<double>('cursor');
      return point?.length == 2 ? Offset(point![0], point[1]) : null;
    } catch (_) { return null; }
  }

'''+s[i:];p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/living_scope.dart');s=p.read_text(encoding='utf-8').replace('Future<void> Function()? moveCompanionWindow;', 'Future<void> Function()? moveCompanionWindow;\n  Future<Offset?> Function()? readCompanionPointer;');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/main_v2.dart');s=p.read_text(encoding='utf-8').replace('_services.moveCompanionWindow = _window.move;', '_services.moveCompanionWindow = _window.move;\n    _services.readCompanionPointer = _window.cursorPosition;');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/screens/companion_mode_view.dart');s=p.read_text(encoding='utf-8').replace('this.onChatChanged,','this.onChatChanged,\n    this.angle = 0,\n    this.onPointerNear,').replace('final bool chatOpen;', 'final bool chatOpen;\n  final double angle;\n  final VoidCallback? onPointerNear;').replace('textScale: MediaQuery.textScalerOf(context).scale(14) / 14,','textScale: MediaQuery.textScalerOf(context).scale(14) / 14,\n              angle: widget.angle,');s=s.replace('return Stack(\n              children:', 'return MouseRegion(\n              onEnter: (_) => widget.onPointerNear?.call(),\n              onHover: (_) => widget.onPointerNear?.call(),\n              child: Listener(onPointerDown: (_) => widget.onPointerNear?.call(), child: Stack(\n              children:');s=s.replace('              ],\n            );\n          },', '              ],\n            )));\n          },');p.write_text(s,encoding='utf-8')
p=Path('uri_ui/lib/living/presentation/living_shell.dart');s=p.read_text(encoding='utf-8').replace("import 'dart:async';", "import 'dart:async';\nimport 'dart:math' as math;\nimport '../companion/frame_clock.dart';")
s=s.replace('  CompanionWindowLayout? _windowLayout;', '''  CompanionWindowLayout? _windowLayout;
  CompanionFrameClock? _orbitClock;
  double _orbitAngle = 0, _lastOrbitFrame = 0, _holdOrbitUntil = 0;
  bool _readingPointer = false;
  Rect? _orbitBounds;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final clock = LivingScope.of(context).frameClock;
    if (!identical(clock, _orbitClock)) {
      _orbitClock?.removeListener(_orbitTick);
      _orbitClock = clock..addListener(_orbitTick);
    }
  }

  void _holdOrbit() { _holdOrbitUntil = (_orbitClock?.seconds ?? 0) + 1.5; }

  void _orbitTick() {
    if (!mounted) return;
    final s = LivingScope.of(context);
    final now = s.frameClock.seconds;
    final delta = now - _lastOrbitFrame;
    if (delta < .1) return;
    _lastOrbitFrame = now;
    if (!s.visualV2 || !_panelExpanded || _chatOpen ||
        s.presentation.mode != UiPresentationMode.companion ||
        s.frameClock.hidden || s.effects.reducedMotion ||
        MediaQuery.disableAnimationsOf(context) ||
        MediaQuery.textScalerOf(context).scale(14) / 14 > 1.2 ||
        s.composerFocus.hasFocus || s.voice.session.phase != VoicePhase.off ||
        CompanionModeView.actions(s, CompanionModeView.reviewCount(s, context)).length > 4) return;
    final read = s.readCompanionPointer;
    if (read != null && !_readingPointer) {
      _readingPointer = true;
      read().then((point) {
        if (!mounted) return;
        // Missing native cursor support fails static, never evasive controls.
        if (point == null || _orbitBounds?.inflate(80).contains(point) == true) _holdOrbit();
      }).whenComplete(() => _readingPointer = false);
    }
    if (now < _holdOrbitUntil) return;
    setState(() => _orbitAngle = (_orbitAngle + math.min(delta, .15) * math.pi * 2 / 180) % (math.pi * 2));
  }''')
s=s.replace('    _bubbleTimer?.cancel();\n    super.dispose();', '    _bubbleTimer?.cancel();\n    _orbitClock?.removeListener(_orbitTick);\n    super.dispose();')
s=s.replace('            final voiceDock = VoiceDock.forMode', '''            _orbitBounds = Rect.fromCircle(center: dock.rect.center,
              radius: CompanionModeView.orbitRadius(shellSize) + CompanionModeView.buttonDiameter(shellSize) / 2);
            final voiceDock = VoiceDock.forMode''')
s=s.replace('textScale: MediaQuery.textScalerOf(context).scale(14) / 14,\n                  ).values', 'textScale: MediaQuery.textScalerOf(context).scale(14) / 14,\n                    angle: _orbitAngle,\n                  ).values')
s=s.replace('              buttons: buttonRects,', '''              buttons: buttonRects,
              orbit: _panelExpanded ? Rect.fromCircle(center: dock.rect.center, radius: CompanionModeView.orbitRadius(shellSize)) : null,''')
s=s.replace('chatOpen: _chatOpen,', 'chatOpen: _chatOpen,\n                                        angle: _orbitAngle,\n                                        onPointerNear: _holdOrbit,')
p.write_text(s,encoding='utf-8')
