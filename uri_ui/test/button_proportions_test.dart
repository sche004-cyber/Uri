import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/theme/uri_theme.dart';

void main() {
  for (final (name, palette) in [
    ('ivory', UriColors.ivoryFoundry),
    ('snow', UriColors.snowArchive),
    ('ash', UriColors.ashLimestone),
  ]) {
    testWidgets('$name actions remain readable and tappable at 200% text', (
      tester,
    ) async {
      tester.view.physicalSize = const Size(360, 640);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.resetPhysicalSize);
      addTearDown(tester.view.resetDevicePixelRatio);
      var applied = 0;
      await tester.pumpWidget(
        MaterialApp(
          theme: buildUriTheme(palette),
          home: MediaQuery(
            data: const MediaQueryData(
              size: Size(360, 640),
              textScaler: TextScaler.linear(2),
            ),
            child: Scaffold(
              body: Padding(
                padding: const EdgeInsets.all(24),
                child: Wrap(
                  spacing: 8,
                  runSpacing: 8,
                  children: [
                    FilledButton(
                      key: const ValueKey('proportions-filled'),
                      onPressed: () => applied++,
                      child: const Text('Apply appearance changes'),
                    ),
                    ElevatedButton(
                      key: const ValueKey('proportions-elevated'),
                      onPressed: () {},
                      child: const Text('Sign in'),
                    ),
                    OutlinedButton(
                      key: const ValueKey('proportions-outlined'),
                      onPressed: () {},
                      child: const Text('Test connection'),
                    ),
                    TextButton(
                      key: const ValueKey('proportions-text'),
                      onPressed: () {},
                      child: const Text('Cancel'),
                    ),
                    IconButton(
                      key: const ValueKey('proportions-icon'),
                      onPressed: () {},
                      tooltip: 'Close',
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
              ),
            ),
          ),
        ),
      );
      for (final kind in ['filled', 'elevated', 'outlined', 'text', 'icon']) {
        final button = find.byKey(ValueKey('proportions-$kind'));
        final rect = tester.getRect(button);
        expect(rect.height, greaterThanOrEqualTo(48));
        expect(rect.left, greaterThanOrEqualTo(24));
        expect(rect.right, lessThanOrEqualTo(336));
        final labels = find.descendant(of: button, matching: find.byType(Text));
        for (final label in labels.evaluate()) {
          final labelRect = tester.getRect(find.byWidget(label.widget));
          expect(labelRect.top, greaterThanOrEqualTo(rect.top));
          expect(labelRect.bottom, lessThanOrEqualTo(rect.bottom));
        }
      }
      await tester.tap(find.byKey(const ValueKey('proportions-filled')));
      expect(applied, 1);
      expect(tester.takeException(), isNull);
    });
  }
}
