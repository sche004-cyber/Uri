import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/companion_orb.dart';
import 'package:uri_ui/living/companion/companion_preferences.dart';
import 'package:uri_ui/living/companion/companion_state.dart';
import 'package:uri_ui/living/companion/companion_theme.dart';
import 'package:uri_ui/living/companion/ember_companion.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// Serves the real shipped manifest and atlases from disk, so the tests
/// exercise the files the app bundles, not a fixture.
class _DiskBundle extends CachingAssetBundle {
  int loads = 0;

  /// Atlases (not the manifest) wait for this before they are served, so a
  /// test can hold a clip "still decoding".
  Completer<void>? gate;

  /// Atlases whose load fails, as a corrupt or missing file would.
  final Set<String> broken = <String>{};

  @override
  Future<ByteData> load(String key) async {
    loads++;
    if (key.endsWith('.webp') && gate != null) await gate!.future;
    if (broken.any(key.endsWith)) throw StateError('broken asset $key');
    final bytes = File(key).readAsBytesSync();
    return ByteData.view(Uint8List.fromList(bytes).buffer);
  }
}

void main() {
  group('state mapping', () {
    test('every CompanionState has a shipped expression', () {
      for (final s in CompanionState.values) {
        expect(
          EmberClip.values,
          contains(EmberClips.forState(s)),
          reason: s.name,
        );
      }
      // Fierce is rendered for fidelity but never shipped or shown.
      expect(EmberClip.values.map((c) => c.name), isNot(contains('fierce')));
    });

    test('the table is the one documented in 02_STATE_MATRIX.md', () {
      expect(
        EmberClips.forState(CompanionState.unavailable),
        EmberClip.depleted,
      );
      expect(EmberClips.forState(CompanionState.idle), EmberClip.idle);
      expect(
        EmberClips.forState(CompanionState.listening),
        EmberClip.listening,
      );
      expect(EmberClips.forState(CompanionState.thinking), EmberClip.thinking);
      expect(EmberClips.forState(CompanionState.speaking), EmberClip.speaking);
      expect(EmberClips.forState(CompanionState.working), EmberClip.focused);
      expect(
        EmberClips.forState(CompanionState.awaitingApproval),
        EmberClip.listening,
      );
      expect(EmberClips.forState(CompanionState.success), EmberClip.joyful);
      expect(EmberClips.forState(CompanionState.error), EmberClip.concerned);
    });

    test('fading into or out of depleted is slower than other changes', () {
      final normal = EmberClips.fadeBetween(EmberClip.idle, EmberClip.thinking);
      expect(
        EmberClips.fadeBetween(EmberClip.depleted, EmberClip.idle),
        greaterThan(normal),
      );
      expect(
        EmberClips.fadeBetween(EmberClip.idle, EmberClip.depleted),
        greaterThan(normal),
      );
    });
  });

  group('identity', () {
    test('Ember is an additional choice; nothing else moved', () {
      final keys = CompanionChoice.all.map((c) => c.key).toList();
      expect(keys, ['solar', 'sakura', 'lunar', 'moonlit', 'ember', 'classic']);
      expect(
        CompanionChoice.fromKey('ember')?.identity,
        CompanionIdentity.ember,
      );
      expect(CompanionIdentity.ember.usesShader, isFalse);
      expect(CompanionIdentity.ember.label, 'Ember');
    });

    test('Ember adopts the existing warm theme, no new palette', () {
      expect(
        CompanionTheme.choiceFor(CompanionIdentity.ember),
        UriThemeChoice.solarEmber,
      );
      expect(
        identical(
          CompanionTheme.paletteFor(CompanionIdentity.ember),
          UriColors.solarEmber,
        ),
        isTrue,
      );
    });

    test('controls that cannot change Ember are not offered', () {
      final words = CompanionLookVocabulary.of(CompanionIdentity.ember);
      expect(words.particles, isNull);
      expect(words.atmosphere, isNull);
      for (final id in CompanionIdentity.values.where((i) => i.usesShader)) {
        expect(CompanionLookVocabulary.of(id).particles, isNotNull);
      }
    });
  });

  group('shipped assets', () {
    final dir = Directory(EmberManifest.assetDir);

    test('manifest lists every clip, and every atlas exists at its size', () {
      final m = EmberManifest.parse(
        File(EmberManifest.assetPath).readAsStringSync(),
      );
      expect(m.fps, 24);
      expect(m.clips.keys.toSet(), EmberClip.values.toSet());
      for (final e in m.clips.entries) {
        final f = File('${dir.path}/${e.value.file}');
        expect(f.existsSync(), isTrue, reason: e.key.name);
        expect(e.value.frames, greaterThanOrEqualTo(24), reason: e.key.name);
      }
    });

    test(
      'the manifest refuses an empty layout instead of dividing by zero',
      () {
        String m(int frames, int cols) => jsonEncode({
          'fps': 24,
          'clips': {
            'idle': {'file': 'x', 'frames': frames, 'cols': cols, 'cell': 10},
          },
        });
        expect(() => EmberManifest.parse(m(0, 4)), throwsFormatException);
        expect(() => EmberManifest.parse(m(4, 0)), throwsFormatException);
        expect(EmberManifest.parse(m(4, 2)).clips[EmberClip.idle]!.frames, 4);
      },
    );

    test('the picker thumbnail is shipped and small', () {
      final f = File(EmberManifest.thumbnailPath);
      expect(f.existsSync(), isTrue);
      expect(f.lengthSync(), lessThan(64 * 1024));
    });

    test('pubspec bundles the ember asset directory', () {
      final pub = File('pubspec.yaml').readAsStringSync();
      expect(pub, contains('${EmberManifest.assetDir}/'));
    });

    test('frame rectangles tile the atlas row-major and wrap', () {
      const info = EmberClipInfo(file: 'x', frames: 10, cols: 4, cell: 100);
      expect(info.frameRect(0), const Rect.fromLTWH(0, 0, 100, 100));
      expect(info.frameRect(5), const Rect.fromLTWH(100, 100, 100, 100));
      expect(info.frameRect(10), info.frameRect(0));
      expect(info.decodedBytes, 4 * 100 * 3 * 100 * 4);
    });

    test('the resident budget stays bounded', () {
      final m = EmberManifest.parse(
        File(EmberManifest.assetPath).readAsStringSync(),
      );
      final sizes = m.clips.values.map((c) => c.decodedBytes).toList()..sort();
      // Capacity 2 plus one pinned clip during a fade.
      final worst = sizes.reversed.take(3).fold<int>(0, (a, b) => a + b);
      expect(worst, lessThan(160 * 1024 * 1024));
      // ignore: avoid_print
      print(
        'EMBER_BUDGET worst three atlases: ${(worst / 1048576).toStringAsFixed(1)} MiB',
      );
    });
  });

  group('widget', () {
    late _DiskBundle bundle;
    late EmberLibrary lib;

    setUp(() {
      bundle = _DiskBundle();
      lib = EmberLibrary(bundle: bundle);
    });
    tearDown(() => lib.reset());

    Future<void> settleDecode(WidgetTester tester) async {
      // Image decoding completes outside the fake clock.
      for (var i = 0; i < 20; i++) {
        await tester.runAsync(
          () => Future<void>.delayed(const Duration(milliseconds: 30)),
        );
        await tester.pump(const Duration(milliseconds: 16));
      }
    }

    testWidgets('shows the fallback until the clip is decoded, then paints', (
      tester,
    ) async {
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: SizedBox(
            width: 200,
            height: 200,
            child: EmberCompanion(
              library: lib,
              fallback: const Text('fallback', key: ValueKey('fb')),
            ),
          ),
        ),
      );
      expect(find.byKey(const ValueKey('fb')), findsOneWidget);
      await settleDecode(tester);
      expect(find.byKey(const ValueKey('fb')), findsNothing);
      expect(lib.resident, contains(EmberClip.idle));
    });

    testWidgets('a state change cross-fades and evicts the old clip after', (
      tester,
    ) async {
      Widget at(CompanionState s) => Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 200,
          height: 200,
          child: EmberCompanion(library: lib, state: s),
        ),
      );
      await tester.pumpWidget(at(CompanionState.idle));
      await settleDecode(tester);
      await tester.pumpWidget(at(CompanionState.success));
      await settleDecode(tester);
      // Both are pinned while fading.
      expect(lib.pinned, containsAll([EmberClip.idle, EmberClip.joyful]));
      await tester.pump(const Duration(seconds: 2));
      await tester.pump(const Duration(milliseconds: 16));
      expect(lib.pinned, {EmberClip.joyful});
      await tester.pumpWidget(at(CompanionState.thinking));
      await settleDecode(tester);
      await tester.pump(const Duration(seconds: 2));
      await tester.pump(const Duration(milliseconds: 16));
      expect(lib.resident.length, lessThanOrEqualTo(lib.capacity));
      expect(lib.resident, contains(EmberClip.thinking));
    });

    testWidgets('unmounting the last Ember frees every atlas', (tester) async {
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: EmberCompanion(library: lib),
        ),
      );
      await settleDecode(tester);
      expect(lib.pinned, isNotEmpty);
      expect(lib.resident, isNotEmpty);
      await tester.pumpWidget(const SizedBox());
      expect(lib.pinned, isEmpty);
      expect(lib.resident, isEmpty);
      expect(lib.residentBytes, 0);
    });

    testWidgets(
      'two companions share the library; one leaving keeps the other',
      (tester) async {
        Widget two(bool both) => Directionality(
          textDirection: TextDirection.ltr,
          child: Row(
            children: [
              SizedBox(
                width: 100,
                height: 100,
                child: EmberCompanion(library: lib),
              ),
              if (both)
                SizedBox(
                  width: 100,
                  height: 100,
                  child: EmberCompanion(
                    library: lib,
                    state: CompanionState.thinking,
                  ),
                ),
            ],
          ),
        );
        await tester.pumpWidget(two(true));
        await settleDecode(tester);
        expect(lib.resident, containsAll([EmberClip.idle, EmberClip.thinking]));
        await tester.pumpWidget(two(false));
        expect(lib.pinned, {EmberClip.idle});
        expect(lib.resident, contains(EmberClip.idle));
      },
    );

    testWidgets(
      'a fade waits for the incoming clip; the old one stays visible',
      (tester) async {
        Widget at(CompanionState s) => Directionality(
          textDirection: TextDirection.ltr,
          child: SizedBox(
            width: 200,
            height: 200,
            child: EmberCompanion(
              library: lib,
              state: s,
              fallback: const Text('fallback', key: ValueKey('fb')),
            ),
          ),
        );
        await tester.pumpWidget(at(CompanionState.idle));
        await settleDecode(tester);
        bundle.gate = Completer<void>();
        await tester.pumpWidget(at(CompanionState.thinking));
        // Long past the 450 ms fade, the incoming atlas is still "decoding":
        // the idle clip must still be drawn, never the fallback.
        for (var i = 0; i < 30; i++) {
          await tester.pump(const Duration(milliseconds: 50));
        }
        expect(find.byKey(const ValueKey('fb')), findsNothing);
        expect(lib.pinned, containsAll([EmberClip.idle, EmberClip.thinking]));
        // A second change while still waiting keeps idle as the outgoing clip.
        await tester.pumpWidget(at(CompanionState.speaking));
        await tester.pump(const Duration(milliseconds: 50));
        expect(lib.pinned, containsAll([EmberClip.idle, EmberClip.speaking]));
        expect(find.byKey(const ValueKey('fb')), findsNothing);
        bundle.gate!.complete();
        await settleDecode(tester);
        for (var i = 0; i < 30; i++) {
          await tester.pump(const Duration(milliseconds: 50));
        }
        expect(lib.pinned, {EmberClip.speaking});
      },
    );

    testWidgets('between sprite frames Ember asks for no frames', (
      tester,
    ) async {
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: EmberCompanion(library: lib),
        ),
      );
      await settleDecode(tester);
      await tester.pump(const Duration(milliseconds: 16));
      await tester.pump(const Duration(milliseconds: 16));
      // A frame was shown and the next one is ~42 ms away: no frame is
      // scheduled until the wake-up timer fires.
      expect(tester.binding.hasScheduledFrame, isFalse);
      await tester.pump(const Duration(milliseconds: 60));
      await tester.pump(const Duration(milliseconds: 16));
      expect(lib.resident, contains(EmberClip.idle));
    });

    testWidgets('a clip that fails to load ends the fade on the old clip', (
      tester,
    ) async {
      Widget at(CompanionState s) => Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 200,
          height: 200,
          child: EmberCompanion(library: lib, state: s),
        ),
      );
      await tester.pumpWidget(at(CompanionState.idle));
      await settleDecode(tester);
      bundle.broken.add('thinking.webp');
      await tester.pumpWidget(at(CompanionState.thinking));
      await settleDecode(tester);
      final st = tester.state(find.byType(EmberCompanion)) as dynamic;
      expect(st.currentClip, EmberClip.idle);
      expect(lib.pinned, {EmberClip.idle});
      // Not stuck in a fade: it sleeps between sprite frames again.
      await tester.pump(const Duration(milliseconds: 16));
      await tester.pump(const Duration(milliseconds: 16));
      expect(st.sleepingBetweenFrames, isTrue);
      // A rebuild with the same (failed) state neither fades to it again nor
      // decodes it again inside the retry window (review R3-07).
      final loads = bundle.loads;
      await tester.pumpWidget(at(CompanionState.thinking));
      await settleDecode(tester);
      expect(st.currentClip, EmberClip.idle);
      expect(bundle.loads, loads);
      expect(lib.hasFailed(EmberClip.thinking), isTrue);
    });

    testWidgets(
      'a first clip that fails shows the fallback and asks for no frames',
      (tester) async {
        bundle.broken.add('idle.webp');
        await tester.pumpWidget(
          Directionality(
            textDirection: TextDirection.ltr,
            child: EmberCompanion(
              library: lib,
              fallback: const Text('fallback', key: ValueKey('fb')),
            ),
          ),
        );
        await settleDecode(tester);
        expect(find.byKey(const ValueKey('fb')), findsOneWidget);
        final st = tester.state(find.byType(EmberCompanion)) as dynamic;
        // One wake is kept for the retry window (30 s), nothing sooner.
        expect(st.sleepingBetweenFrames, isTrue);
        await tester.pump(const Duration(seconds: 1));
        expect(tester.binding.hasScheduledFrame, isFalse);
      },
    );

    for (final motion in [0.5, 1.0, 1.5]) {
      testWidgets('sprite cadence follows the motion preference ($motion)', (
        tester,
      ) async {
        await tester.pumpWidget(
          Directionality(
            textDirection: TextDirection.ltr,
            child: EmberCompanion(
              library: lib,
              look: CompanionLook(motion: motion),
            ),
          ),
        );
        await settleDecode(tester);
        final st = tester.state(find.byType(EmberCompanion)) as dynamic;
        // Drive 2 s at a 144 Hz vsync and count distinct frames shown.
        var changes = 0;
        var last = st.shownFrame as int;
        var longest = 0;
        var held = 0;
        for (var i = 0; i < 288; i++) {
          await tester.pump(const Duration(microseconds: 6944));
          final f = st.shownFrame as int;
          if (f != last) {
            changes++;
            longest = held > longest ? held : longest;
            held = 0;
            last = f;
          } else {
            held++;
          }
        }
        final expected = 2 * 24 * motion;
        expect(changes, inInclusiveRange(expected - 3, expected + 2));
        // No frame is held much longer than its period (plus one vsync).
        final periodVsyncs = 144 / (24 * motion);
        expect(longest, lessThanOrEqualTo((periodVsyncs * 1.5).ceil() + 1));
      });
    }

    testWidgets('after the retry window a failed first clip is loaded again', (
      tester,
    ) async {
      var clock = Duration.zero;
      lib.now = () => clock;
      bundle.broken.add('idle.webp');
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: EmberCompanion(
            library: lib,
            fallback: const Text('fallback', key: ValueKey('fb')),
          ),
        ),
      );
      await settleDecode(tester);
      expect(find.byKey(const ValueKey('fb')), findsOneWidget);
      expect(lib.hasFailed(EmberClip.idle), isTrue);
      // Inside the window: nothing is retried.
      final loads = bundle.loads;
      await tester.pump(const Duration(seconds: 10));
      expect(bundle.loads, loads);
      // The asset is back and the window has passed: one wake, one load.
      bundle.broken.clear();
      clock += EmberLibrary.retryAfter + const Duration(seconds: 1);
      await tester.pump(const Duration(seconds: 21));
      await settleDecode(tester);
      expect(lib.hasFailed(EmberClip.idle), isFalse);
      expect(find.byKey(const ValueKey('fb')), findsNothing);
    });

    testWidgets('a refused target is followed once it may be retried', (
      tester,
    ) async {
      var clock = Duration.zero;
      lib.now = () => clock;
      Widget at(CompanionState s) => Directionality(
        textDirection: TextDirection.ltr,
        child: SizedBox(
          width: 200,
          height: 200,
          child: EmberCompanion(library: lib, state: s),
        ),
      );
      await tester.pumpWidget(at(CompanionState.idle));
      await settleDecode(tester);
      bundle.broken.add('thinking.webp');
      await tester.pumpWidget(at(CompanionState.thinking));
      await settleDecode(tester);
      final st = tester.state(find.byType(EmberCompanion)) as dynamic;
      expect(st.currentClip, EmberClip.idle);
      // No parent rebuild: the companion re-checks on its own.
      bundle.broken.clear();
      clock += EmberLibrary.retryAfter + const Duration(seconds: 1);
      await tester.pump(const Duration(seconds: 31));
      await settleDecode(tester);
      for (var i = 0; i < 30; i++) {
        await tester.pump(const Duration(milliseconds: 50));
      }
      expect(st.currentClip, EmberClip.thinking);
    });

    testWidgets('a still Ember (picker) settles and requests nothing', (
      tester,
    ) async {
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: EmberCompanion(library: lib, still: true),
        ),
      );
      await settleDecode(tester);
      await tester.pump(const Duration(milliseconds: 16));
      expect(tester.binding.hasScheduledFrame, isFalse);
      await tester.pump(const Duration(seconds: 1));
      expect(tester.binding.hasScheduledFrame, isFalse);
    });
  });

  test('states.json ships exactly the clips the app knows', () {
    final states = jsonDecode(
      File('../companion_art/fire/states.json').readAsStringSync(),
    ) as Map<String, dynamic>;
    final clips = (states['clips'] as Map<String, dynamic>);
    final shipped = {
      for (final e in clips.entries)
        if ((e.value as Map<String, dynamic>)['ship'] != false) e.key,
    };
    expect(shipped, EmberClip.values.map((c) => c.name).toSet());
    expect(clips.keys, contains('fierce'));
  });
}
