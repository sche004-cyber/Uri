// Ember transparency contract (owner directive "Ember V2.1 - URI UI V2
// compatibility"): Ember itself must render with genuine alpha, so a
// transparent, borderless companion window can show it without any host
// mask. Each shipped clip is painted by the real EmberCompanion and
// EmberPainter, from the real bundled atlases, onto a transparent layer with
// no SoftDisc or other host decoration, and the pixels are checked:
//   1. the outer band of the square is fully transparent (no rectangle,
//      no visible boundary);
//   2. outside the central circle nothing is more than half opaque (no
//      opaque backdrop; atmosphere may be translucent);
//   3. at most a quarter of the square is opaque (the character, not a
//      background).
import 'dart:io';
import 'dart:math' as math;
import 'dart:typed_data';
import 'dart:ui' as ui;

import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/companion/ember_companion.dart';

class _DiskBundle extends CachingAssetBundle {
  @override
  Future<ByteData> load(String key) async {
    final bytes = File(key).readAsBytesSync();
    return ByteData.view(Uint8List.fromList(bytes).buffer);
  }
}

/// Pixel statistics of one rendered square (alpha only).
class AlphaStats {
  AlphaStats(Uint8List rgba, int side) {
    final c = (side - 1) / 2;
    final band = math.max(2, (side * 0.02).round());
    var opaque = 0;
    for (var y = 0; y < side; y++) {
      for (var x = 0; x < side; x++) {
        final a = rgba[(y * side + x) * 4 + 3];
        if (a >= 250) opaque++;
        final edge = math.min(math.min(x, side - 1 - x), math.min(y, side - 1 - y));
        if (edge < band) borderMax = math.max(borderMax, a);
        final r = math.sqrt((x - c) * (x - c) + (y - c) * (y - c)) / side;
        if (r > 0.45) ringMax = math.max(ringMax, a);
      }
    }
    opaqueFraction = opaque / (side * side);
  }

  int borderMax = 0;
  int ringMax = 0;
  late final double opaqueFraction;

  @override
  String toString() =>
      'border max $borderMax, ring max $ringMax, opaque ${(opaqueFraction * 100).toStringAsFixed(1)} %';
}

void main() {
  const side = 320.0;
  late EmberLibrary lib;
  setUp(() => lib = EmberLibrary(bundle: _DiskBundle()));
  tearDown(() => lib.reset());

  for (final clip in EmberClip.values) {
    testWidgets('$clip renders with genuine alpha (no opaque backdrop)', (tester) async {
      final key = GlobalKey();
      await tester.pumpWidget(
        Directionality(
          textDirection: TextDirection.ltr,
          child: Center(
            child: RepaintBoundary(
              key: key,
              child: SizedBox(
                width: side,
                height: side,
                child: EmberCompanion(library: lib, clip: clip, still: true),
              ),
            ),
          ),
        ),
      );
      for (var i = 0; i < 40; i++) {
        await tester.runAsync(() => Future<void>.delayed(const Duration(milliseconds: 30)));
        await tester.pump(const Duration(milliseconds: 16));
      }
      final boundary = key.currentContext!.findRenderObject()! as RenderRepaintBoundary;
      final bytes = await tester.runAsync(() async {
        final image = await boundary.toImage();
        final data = await image.toByteData(format: ui.ImageByteFormat.rawRgba);
        image.dispose();
        return data!.buffer.asUint8List();
      });
      final stats = AlphaStats(bytes!, side.toInt());
      // The square must actually contain Ember (a blank image would pass).
      expect(stats.opaqueFraction, greaterThan(0.005), reason: 'nothing painted: $stats');
      expect(stats.borderMax, lessThanOrEqualTo(2), reason: '$clip: $stats');
      expect(stats.ringMax, lessThanOrEqualTo(128), reason: '$clip: $stats');
      expect(stats.opaqueFraction, lessThanOrEqualTo(0.25), reason: '$clip: $stats');
    });
  }
}
