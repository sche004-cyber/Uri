@Tags(['a2ui-live'])
library;

import 'dart:convert';
import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/a2ui/a2ui_dock.dart';
import 'package:uri_ui/living/a2ui/a2ui_hub.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart';
import 'package:uri_ui/theme/uri_theme.dart';

/// PROCESS-LEVEL A2UI journeys: the real renderer and hub against a REAL
/// scheduler service process (fixture executor = synthetic stand-in, labelled
/// FIXTURE; not Claude). Driven by `scripts/a2ui_live_check.py`, which starts
/// and restarts the service and passes:
///   URI_A2UI_LIVE=1, URI_SCHEDULER_STATE, URI_A2UI_PHASE (a|b),
///   URI_A2UI_HANDOFF (file: the worker interpreter's handoff for the owner's
///   sentence), URI_A2UI_OUT (file: results and timings written here).
/// Skipped unless URI_A2UI_LIVE=1.
void main() {
  final env = Platform.environment;
  final live = env['URI_A2UI_LIVE'] == '1';
  final phase = env['URI_A2UI_PHASE'] ?? 'a';
  final out = <String, dynamic>{'phase': phase, 'steps': <Map<String, dynamic>>[]};
  void step(String name, [Map<String, dynamic>? data]) =>
      (out['steps'] as List).add({'t': DateTime.now().toUtc().toIso8601String(), 'step': name, ...?data});

  Widget app(Widget child) => MaterialApp(
    theme: buildUriTheme(resolveUriColors(UriThemeChoice.obsidianCyan, Brightness.dark)),
    home: Scaffold(body: SingleChildScrollView(child: child)),
  );

  Future<void> settle(WidgetTester t, [int ms = 300]) async {
    await t.runAsync(() => Future<void>.delayed(Duration(milliseconds: ms)));
    await t.pump();
  }

  Future<void> tap(WidgetTester t, String key) async {
    final f = find.byKey(ValueKey(key));
    await t.ensureVisible(f);
    await t.tap(f);
    await settle(t, 600);
  }

  tearDownAll(() {
    final p = env['URI_A2UI_OUT'];
    if (p != null) File(p).writeAsStringSync(const JsonEncoder.withIndent(' ').convert(out));
  });

  testWidgets('A2UI live journey phase $phase', (t) async {
    t.view.physicalSize = const Size(1300, 3200);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    final client = SchedulerClient.fromEnvironment()!;
    final hub = A2uiHub(scheduler: client);
    await t.pumpWidget(app(A2uiDock(hub: hub, showCalendarEntry: true)));

    if (phase == 'a') {
      // 1. The owner's sentence, interpreted by the worker, becomes a proposal surface.
      final handoff = jsonDecode(File(env['URI_A2UI_HANDOFF']!).readAsStringSync()) as Map<String, dynamic>;
      await t.runAsync(() => hub.handoff(handoff));
      await t.pump();
      expect(hub.notices, isEmpty);
      final sid = hub.surfaces.single.id;
      step('proposal_rendered', {'surface': sid, 'digest': hub.surface(sid)!.digest});
      expect(find.text('Festival greeting GIFs: proposed schedule'), findsOneWidget);
      // 2. The owner narrows the selection to Diwali + Holi and picks 08:30 (inputs stay local).
      for (final k in List<String>.from(hub.surface(sid)!.read('/draft/selection') as List)) {
        if (k != 'diwali' && k != 'holi') await tap(t, 'a2ui.$sid.picker.$k');
      }
      hub.input(sid, '/draft/time', '08:30');
      // 3. Confirming an un-proposed draft is refused by the scheduler and shown.
      await tap(t, 'a2ui.$sid.confirm');
      expect(hub.errors[sid], contains('Update proposal'));
      step('draft_confirm_refused', {'error': hub.errors[sid]});
      // 4. Update proposal -> new revision; then leave it open for the restart.
      final before = hub.surface(sid)!.digest;
      await tap(t, 'a2ui.$sid.revise');
      expect(hub.surface(sid)!.revision, 2);
      expect(hub.surface(sid)!.digest, isNot(before));
      step('revised', {'revision': 2, 'digest': hub.surface(sid)!.digest,
                       'proposal_sha256': hub.surface(sid)!.read('/bound/proposal_sha256')});
      out['surface'] = sid;
      out['stale_digest'] = before;
      // 5. Artifact review (a FIXTURE artifact the driver produced before this phase).
      await t.runAsync(hub.refresh);
      await t.pump();
      final review = hub.surfaces.where((s) => s.kind == 'artifact_review').toList();
      expect(review, hasLength(1));
      final rid = review.single.id;
      await settle(t, 1500);                                  // image bytes fetched and SHA-256 checked
      expect(find.byKey(ValueKey('a2ui.$rid.image')), findsOneWidget);
      expect(find.byKey(ValueKey('a2ui.$rid.image.refused')), findsNothing);
      expect(find.text('Synthetic fixture output'), findsOneWidget);
      step('review_rendered', {'surface': rid, 'artifact_sha256': review.single.read('/bound/artifact_sha256')});
      await tap(t, 'a2ui.$rid.approve');
      expect(hub.surface(rid), isNull);
      step('artifact_approved', {'surface': rid});
      // 6. Calendar review: dispute a record.
      await t.runAsync(hub.openCalendar);
      await t.pump();
      hub.input('calendar-review', '/draft/record', 'karva_chauth:2026');
      await t.ensureVisible(find.byKey(const ValueKey('a2ui.calendar-review.note')));
      await t.enterText(find.byKey(const ValueKey('a2ui.calendar-review.note')), 'live check: disputed');
      await tap(t, 'a2ui.calendar-review.dispute');
      expect(hub.errors['calendar-review'], isNull);
      step('calendar_disputed', {'record': 'karva_chauth:2026'});
    } else {
      // Phase b: after a scheduler restart, the open proposal is re-rendered from the stored record.
      final sid = env['URI_A2UI_SURFACE']!;
      await t.runAsync(hub.refresh);
      await t.pump();
      final s = hub.surface(sid);
      expect(s, isNotNull);
      expect(s!.revision, 2);
      expect(s.read('/draft/selection'), unorderedEquals(['diwali', 'holi']));
      step('rerendered_after_restart', {'digest': s.digest});
      // A forged action carrying the pre-revision digest is refused by the scheduler.
      Object? refusal;
      try {
        await t.runAsync(() => client.a2uiAction({
          'name': 'scheduler.confirm_proposal', 'surfaceId': sid, 'sourceComponentId': 'confirm',
          'context': {'surface_digest': env['URI_A2UI_STALE'], 'proposal_sha256': s.read('/bound/proposal_sha256'),
                      'selection': s.read('/draft/selection'), 'time': '08:30', 'offset_days': '2'},
        }));
      } on SchedulerApiError catch (e) {
        refusal = e.code;
      }
      expect(refusal, 'STALE_SURFACE');
      step('stale_digest_refused', {'code': refusal});
      await tap(t, 'a2ui.$sid.confirm');
      expect(hub.errors[sid], isNull);
      expect(hub.surface(sid)!.kind, 'schedule_status');
      expect(find.text('Festival GIF schedule is active'), findsOneWidget);
      step('confirmed', {'harness_badge': (hub.surface(sid)!.byId['harness'] ?? const {})['text']});
    }
    out['timings'] = hub.timings;
    out['notices'] = hub.notices;
  }, skip: !live);
}
