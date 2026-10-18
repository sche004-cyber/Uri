import 'dart:async';
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:shared_preferences/shared_preferences.dart';

import 'package:uri_ui/living/integration/brain_quick_controls.dart';
import 'package:uri_ui/living/integration/oi_conversation.dart';
import 'package:uri_ui/living/integration/oi_widgets.dart';
import 'package:uri_ui/services/integrated_runtime.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// BRAIN-QUICK-CONTROLS: Thinking / Vision / Context controls, image turns and
/// truthful readiness, against a scripted worker.
class _Runtime implements IntegratedRuntime {
  final commands = <Map<String, dynamic>>[];
  final _events = StreamController<Map<String, dynamic>>.broadcast();
  String brainState = 'READY';
  String readiness = 'READY';
  Map<String, dynamic> active = {'id': 'c32k-visgpu-mtpoff', 'vision': true, 'context': 32768, 'speed': false};
  bool visionLive = true;
  bool pending = false;
  Map<String, dynamic>? switching;
  String? refuseSet;
  int turns = 0;

  static const options = [
    {'id': 'c32k-visgpu-mtpoff', 'vision': true, 'context': 32768, 'speed': false, 'tight': false},
    {'id': 'c64k-visgpu-mtpoff', 'vision': true, 'context': 65536, 'speed': false, 'tight': true},
    {'id': 'c16k-visoff-mtpoff', 'vision': false, 'context': 16384, 'speed': false, 'tight': false},
    {'id': 'c32k-visoff-mtpoff', 'vision': false, 'context': 32768, 'speed': false, 'tight': false},
    {'id': 'c64k-visoff-mtpoff', 'vision': false, 'context': 65536, 'speed': false, 'tight': false},
    {'id': 'c128k-visoff-mtpoff', 'vision': false, 'context': 131072, 'speed': false, 'tight': false},
    {'id': 'c16k-visoff-mtpon', 'vision': false, 'context': 16384, 'speed': true, 'tight': false},
    {'id': 'c32k-visoff-mtpon', 'vision': false, 'context': 32768, 'speed': true, 'tight': false},
  ];

  Map<String, dynamic> get profile => {
        'active': active,
        'vision_live': visionLive,
        'switching': switching,
        'pending_request': pending,
        'choice': active,
      };

  @override
  Stream<Map<String, dynamic>> get events => _events.stream;

  @override
  bool get closed => false;

  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    commands.add(command);
    switch (command['command']) {
      case 'brain_status':
        return {'state': brainState, 'model_id': 'qwen-test'};
      case 'brain_health':
        return {'state': readiness == 'READY' ? 'READY' : 'RECOVERING', 'readiness': readiness, 'profile': profile};
      case 'brain_catalog':
        return {'rows': [], 'fallback': 'none'};
      case 'brain_profile_get':
        return {'offer': {'options': options}, 'state': profile};
      case 'brain_profile_set':
        if (refuseSet != null) {
          final code = refuseSet!;
          if (command['confirm_shrink'] == true) {
            refuseSet = null;
          } else {
            throw IntegratedRuntimeException(code);
          }
        }
        pending = true;
        return {'requested': 'reconfigure'};
      case 'oi_turn':
        return {'turn_id': 't${++turns}', 'accepted': true};
      default:
        return {'ok': true};
    }
  }

  @override
  Future<void> close() async => _events.close();

  @override
  dynamic noSuchMethod(Invocation invocation) => super.noSuchMethod(invocation);
}

Widget _host(Widget child) => MaterialApp(
      theme: buildUriTheme(resolveUriColors(UriThemeChoice.obsidianCyan, Brightness.dark)),
      home: Scaffold(body: child),
    );

Future<OiConversation> _ready(_Runtime rt) async {
  final conv = OiConversation(rt);
  await conv.refreshStatus();
  return conv;
}

Widget _bar(OiConversation conv) => _host(ListenableBuilder(
      listenable: conv,
      builder: (_, _) => OiBrainBar(conversation: conv),
    ));

final _png = Uint8List.fromList([0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A, 0, 0, 0, 0]);

void main() {
  setUp(() => SharedPreferences.setMockInitialValues({}));

  test('Thinking Off / On / Auto is the per-turn depth, remembered, and never a Brain request', () async {
    final rt = _Runtime();
    final conv = await _ready(rt);
    conv.setDepth(OiDepth.fast);
    await conv.send('hello');
    expect(rt.commands.where((c) => c['command'] == 'oi_turn').single['depth'], 'fast');
    expect(rt.commands.any((c) => c['command'] == 'brain_profile_set' || c['command'] == 'brain_restart'), isFalse);
    await Future<void>.delayed(Duration.zero);
    final prefs = await SharedPreferences.getInstance();
    expect(prefs.getString(OiConversation.thinkingPrefKey), 'fast');
    // a returning user gets the remembered choice; "deep" is never remembered
    final again = OiConversation(_Runtime());
    await Future<void>.delayed(const Duration(milliseconds: 10));
    expect(again.depth, OiDepth.fast);
    again.setDepth(OiDepth.deep);
    await Future<void>.delayed(Duration.zero);
    expect(prefs.getString(OiConversation.thinkingPrefKey), 'fast');
  });

  testWidgets('chips show what runs; Vision toggle asks first and keeps the context', (tester) async {
    final rt = _Runtime();
    final conv = await tester.runAsync(() => _ready(rt));
    await tester.pumpWidget(_bar(conv!));
    expect(find.text('Thinking: Auto'), findsOneWidget);
    expect(find.text('Vision: On'), findsOneWidget);
    expect(find.text('Context: 32K'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('oi-qc-vision')));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('oi-qc-confirm')), findsOneWidget);
    expect(find.textContaining('about 30 seconds'), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('oi-qc-confirm-yes')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 20)));
    await tester.pumpAndSettle();
    final set = rt.commands.where((c) => c['command'] == 'brain_profile_set').single;
    expect(set, {'command': 'brain_profile_set', 'vision': false, 'context': 32768, 'speed': false});
    // the request is pending: no READY, no green dot, controls locked
    expect(find.textContaining('switching'), findsWidgets);
    expect(find.text('Vision: switching…'), findsOneWidget);
    expect(find.textContaining('· ready'), findsNothing);
  });

  testWidgets('cancel sends nothing', (tester) async {
    final rt = _Runtime();
    final conv = await tester.runAsync(() => _ready(rt));
    await tester.pumpWidget(_bar(conv!));
    await tester.tap(find.byKey(const ValueKey('oi-qc-vision')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(rt.commands.where((c) => c['command'] == 'brain_profile_set'), isEmpty);
  });

  testWidgets('Vision configured but not live is never shown as On', (tester) async {
    final rt = _Runtime()..visionLive = false;
    final conv = await tester.runAsync(() => _ready(rt));
    await tester.pumpWidget(_bar(conv!));
    expect(find.text('Vision: On'), findsNothing);
    expect(find.text('Vision: starting…'), findsOneWidget);
    expect(conv.attachImage(OiImage(name: 'a.png', mime: 'image/png', bytes: _png)), 'VISION_OFF');
  });

  testWidgets('a smaller context than the conversation asks again before it switches', (tester) async {
    final rt = _Runtime()
      ..active = {'id': 'c64k-visoff-mtpoff', 'vision': false, 'context': 65536, 'speed': false}
      ..visionLive = false
      ..refuseSet = 'CONTEXT_SMALLER_THAN_CONVERSATION';
    final conv = await tester.runAsync(() => _ready(rt));
    await tester.pumpWidget(_bar(conv!));
    await tester.tap(find.byKey(const ValueKey('oi-qc-context-menu')));
    await tester.pumpAndSettle();
    expect(find.text('128K'), findsOneWidget);
    expect(find.text('16K'), findsOneWidget);
    await tester.tap(find.text('16K'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('oi-qc-confirm-yes')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 20)));
    await tester.pumpAndSettle();
    expect(find.byKey(const ValueKey('oi-qc-shrink')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('oi-qc-shrink-yes')));
    await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 20)));
    await tester.pumpAndSettle();
    final sets = rt.commands.where((c) => c['command'] == 'brain_profile_set').toList();
    expect(sets.length, 2);
    expect(sets.last['confirm_shrink'], true);
    expect(sets.last['context'], 16384);
  });

  testWidgets('context menu with Vision on offers only measured vision contexts and marks tight ones', (tester) async {
    final rt = _Runtime();
    final conv = await tester.runAsync(() => _ready(rt));
    await tester.pumpWidget(_bar(conv!));
    await tester.tap(find.byKey(const ValueKey('oi-qc-context-menu')));
    await tester.pumpAndSettle();
    expect(find.text('32K'), findsOneWidget);
    expect(find.text('64K · tight on GPU memory'), findsOneWidget);
    expect(find.text('128K'), findsNothing);
    expect(find.text('16K'), findsNothing);
  });

  test('an image goes with the next typed turn, is shown by name and is not resent', () async {
    final rt = _Runtime();
    final conv = await _ready(rt);
    expect(conv.attachImage(OiImage(name: 'cat.png', mime: 'image/png', bytes: _png)), isNull);
    await conv.send('What is this?');
    final turn = rt.commands.where((c) => c['command'] == 'oi_turn').single;
    expect((turn['images'] as List).single, {'name': 'cat.png', 'mime': 'image/png', 'data': 'iVBORw0KGgoAAAAA'});
    expect(conv.messages.first.images, ['cat.png']);
    expect(conv.pendingImages, isEmpty);
    expect(conv.attachImage(OiImage(name: 'a.png', mime: 'image/png', bytes: _png)), isNull);
    expect(conv.attachImage(OiImage(name: 'b.png', mime: 'image/png', bytes: _png)), isNull);
    expect(conv.attachImage(OiImage(name: 'c.png', mime: 'image/png', bytes: _png)), 'IMAGES_INVALID');
    expect(conv.attachImage(OiImage(name: 'd.png', mime: 'image/png',
        bytes: Uint8List(OiConversation.maxImageBytes))), 'IMAGES_INVALID');
  });

  test('images never ride on dictation or a transcript', () async {
    final rt = _Runtime();
    final conv = await _ready(rt);
    conv.attachImage(OiImage(name: 'cat.png', mime: 'image/png', bytes: _png));
    conv.setDictationMode(true);
    await conv.send('note this down');
    expect(rt.commands.where((c) => c['command'] == 'oi_turn').single.containsKey('images'), isFalse);
    expect(conv.pendingImages.length, 1);
  });

  test('a stale READY is re-read when health readiness changes (truthful readiness)', () async {
    final rt = _Runtime();
    final conv = await _ready(rt);
    expect(conv.brainStatus['state'], 'READY');
    rt
      ..readiness = 'STARTING'
      ..brainState = 'STARTING';
    await conv.refreshHealth();
    expect(conv.brainStatus['state'], 'STARTING');
    expect(conv.brainReady, isFalse);
  });

  testWidgets('speed boost is offered only with Vision off at a measured context', (tester) async {
    final rt = _Runtime();
    final conv = await tester.runAsync(() => _ready(rt));
    await tester.pumpWidget(_host(ListenableBuilder(
      listenable: conv!,
      builder: (_, _) => OiSpeedBoostTile(conversation: conv),
    )));
    expect(tester.widget<SwitchListTile>(find.byKey(const ValueKey('ws-speed-boost'))).onChanged, isNull);
    rt
      ..active = {'id': 'c32k-visoff-mtpoff', 'vision': false, 'context': 32768, 'speed': false}
      ..visionLive = false;
    await tester.runAsync(() => conv.refreshHealth());
    await tester.pump();
    expect(tester.widget<SwitchListTile>(find.byKey(const ValueKey('ws-speed-boost'))).onChanged, isNotNull);
    rt.active = {'id': 'c128k-visoff-mtpoff', 'vision': false, 'context': 131072, 'speed': false};
    await tester.runAsync(() => conv.refreshHealth());
    await tester.pump();
    expect(tester.widget<SwitchListTile>(find.byKey(const ValueKey('ws-speed-boost'))).onChanged, isNull);
  });

  test('without quick-controls support the bar keeps only Thinking', () async {
    final conv = OiConversation(_LegacyRuntime());
    await conv.refreshStatus();
    expect(conv.profileOffer, isEmpty);
    expect(conv.lastError, isNull);
  });

  test('image file types and scaling keep small files unchanged', () async {
    expect(oiImageMime('Photo.JPG'), 'image/jpeg');
    expect(oiImageMime('scan.tiff'), isNull);
    final img = await prepareOiImage('a.png', _png);
    expect(img!.bytes, _png);
  });
}

class _LegacyRuntime extends _Runtime {
  @override
  Future<Map<String, dynamic>> call(Map<String, dynamic> command) async {
    if (command['command'] == 'brain_profile_get') throw IntegratedRuntimeException('COMMAND_SCHEMA');
    final r = await super.call(command);
    if (command['command'] == 'brain_health') r.remove('profile');
    return r;
  }
}
