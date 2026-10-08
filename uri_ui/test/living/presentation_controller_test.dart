import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/presentation/presentation_controller.dart';

void main() {
  group('parseLocalUiCommand', () {
    test('recognises the brief\'s demo phrases, case/space insensitive', () {
      expect(parseLocalUiCommand('URI dashboard'), isA<ShowModeCommand>());
      expect(
        (parseLocalUiCommand('  uri   Dashboard. ') as ShowModeCommand).mode,
        UiPresentationMode.dashboard,
      );
      expect(
        (parseLocalUiCommand('URI workspace') as ShowModeCommand).mode,
        UiPresentationMode.workspace,
      );
      expect(
        (parseLocalUiCommand('uri companion') as ShowModeCommand).mode,
        UiPresentationMode.companion,
      );
      expect(
        (parseLocalUiCommand('uri minimize') as ShowModeCommand).mode,
        UiPresentationMode.companion,
      );
      final tasks = parseLocalUiCommand('URI tasks') as ShowModeCommand;
      expect(tasks.mode, UiPresentationMode.workspace);
      expect(tasks.focus, WorkspaceFocus.tasks);
    });

    test('never hijacks ordinary chat that mentions a mode', () {
      expect(parseLocalUiCommand('show me the dashboard numbers'), isNull);
      expect(parseLocalUiCommand('uri dashboard please open it'), isNull);
      expect(parseLocalUiCommand('dashboard'), isNull);
      expect(parseLocalUiCommand(''), isNull);
      expect(parseLocalUiCommand('URI, draft a letter'), isNull);
    });
  });

  group('UiPresentationController', () {
    test('user setMode is always honoured and recorded as user origin', () {
      final c = UiPresentationController();
      var notified = 0;
      c.addListener(() => notified++);
      c.setMode(UiPresentationMode.dashboard);
      expect(c.mode, UiPresentationMode.dashboard);
      expect(c.lastCommandOrigin, UiCommandOrigin.user);
      expect(notified, 1);
      c.setMode(UiPresentationMode.dashboard); // no-op
      expect(notified, 1);
    });

    test(
      'a command moves the mode, records its origin, and respects the cooldown',
      () {
        var now = DateTime(2026, 10, 8, 12);
        final c = UiPresentationController(
          commandCooldown: const Duration(seconds: 1),
          clock: () => now,
        );
        expect(
          c.apply(const ShowModeCommand(UiPresentationMode.dashboard)),
          isTrue,
        );
        expect(c.mode, UiPresentationMode.dashboard);
        expect(c.lastCommandOrigin, UiCommandOrigin.localCommand);
        // Second command inside the cooldown is refused.
        expect(
          c.apply(const ShowModeCommand(UiPresentationMode.workspace)),
          isFalse,
        );
        expect(c.mode, UiPresentationMode.dashboard);
        now = now.add(const Duration(seconds: 2));
        expect(
          c.apply(
            const ShowModeCommand(
              UiPresentationMode.workspace,
              focus: WorkspaceFocus.documents,
            ),
          ),
          isTrue,
        );
        expect(c.mode, UiPresentationMode.workspace);
        expect(c.focus, WorkspaceFocus.documents);
      },
    );

    test('back returns to the previous mode and hands control to the user', () {
      final c = UiPresentationController();
      c.apply(const ShowModeCommand(UiPresentationMode.dashboard));
      expect(c.history, [UiPresentationMode.companion]);
      expect(c.back(), isTrue);
      expect(c.mode, UiPresentationMode.companion);
      expect(c.lastCommandOrigin, UiCommandOrigin.user);
      expect(c.back(), isFalse);
    });

    test('the command vocabulary is only a mode and a focus (sealed)', () {
      // Compile-time guarantee: the only UiCommand subtype is ShowModeCommand.
      const UiCommand cmd = ShowModeCommand(UiPresentationMode.companion);
      final described = switch (cmd) {
        ShowModeCommand(:final mode) => mode.name,
      };
      expect(described, 'companion');
    });
  });
}
