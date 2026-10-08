import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart';
import 'package:uri_ui/living/screens/scheduler/scheduler_view.dart';
import 'package:uri_ui/theme/uri_theme.dart';

// 1x1 two-frame GIF (valid header) so Image.memory has real bytes.
final _gif = base64Decode(
  'R0lGODlhAQABAIAAAP///wAAACH5BAAAAAAALAAAAAABAAEAAAICRAEAOw==',
);

Map<String, dynamic> _overview({bool pending = true}) => {
  'now_utc': '2026-10-09T00:00:00+00:00',
  'harness': {'available': false, 'code': 'NOT_AUTHENTICATED', 'mode': 'LIVE'},
  'upcoming': [
    {
      'occ_id': 2,
      'title': 'Festival GIF',
      'state': 'SCHEDULED',
      'due_local': '2026-11-06T09:00+05:30',
      'meta': {'festival': 'Diwali (Deepavali)', 'festival_date': '2026-11-08'},
    },
  ],
  'errors': [],
  'pending_approvals': pending
      ? [
          {
            'occ_id': 1,
            'title': 'Festival GIF',
            'meta': {'festival': 'Diwali (Deepavali)', 'festival_date': '2026-11-08'},
            'candidates': [
              {
                'artifact_id': 7,
                'version': 2,
                'sha256': 'ab' * 32,
                'path': r'C:\state\outputs\occ_1\diwali_v2.gif',
                'bytes': 1234,
                'concept': '# Rows of light\nDiyas over a rangoli.',
                'info': {
                  'mode': 'FIXTURE',
                  'quality': {
                    'animated_gif': true,
                    'text_legible': true,
                    'loop_seamless': true,
                    'within_size_budget': true,
                  },
                  'gif_checks': {'n_frames': 48},
                },
              },
            ],
          },
        ]
      : [],
  'approved': [],
  'recent_executions': [],
  'jobs': [],
  'paused_jobs': [],
};

void main() {
  late List<http.Request> posts;

  SchedulerClient client() {
    posts = [];
    return SchedulerClient(
      baseUrl: 'http://127.0.0.1:1',
      token: 't',
      principal: 'owner',
      client: MockClient((req) async {
        expect(req.headers['Authorization'], 'Bearer t');
        if (req.method == 'GET' && req.url.path == '/overview') {
          return http.Response(jsonEncode(_overview()), 200);
        }
        if (req.method == 'GET' && req.url.path == '/artifacts/7/file') {
          return http.Response.bytes(_gif, 200);
        }
        posts.add(req);
        if (req.url.path == '/jobs/propose-festivals') {
          return http.Response(
            jsonEncode({
              'job_id': 'job_1',
              'proposal_sha256': 'cd' * 32,
              'interpretation': '2 calendar days before each selected event',
              'upcoming': [
                {
                  'festival': 'Diwali (Deepavali)',
                  'festival_date': '2026-11-08',
                  'due_local': '2026-11-06T09:00+05:30',
                  'source': {'verification': 'secondary_transcription_of_official_om'},
                },
              ],
              'excluded': [
                {'festival_key': 'losoong_namsoong', 'date': '2026-12-09', 'status': 'unverified'},
              ],
              'notes': ['No result is ever posted.'],
            }),
            200,
          );
        }
        return http.Response('{}', 200);
      }),
    );
  }

  Widget host(SchedulerClient c) => MaterialApp(
    theme: buildUriTheme(
      resolveUriColors(UriThemeChoice.obsidianCyan, Brightness.dark),
    ),
    home: SchedulerView(client: c),
  );

  testWidgets('review card shows preview, truth label and binds approval to sha256', (t) async {
    t.view.physicalSize = const Size(1400, 1600);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    await t.pumpWidget(host(client()));
    await t.pumpAndSettle();
    expect(find.textContaining('Claude harness unavailable: NOT_AUTHENTICATED'), findsOneWidget);
    expect(find.textContaining('no other or paid provider'), findsOneWidget);
    expect(find.textContaining('FIXTURE: made by the synthetic stand-in'), findsOneWidget);
    expect(find.byKey(const Key('scheduler.gif.7')), findsOneWidget);
    expect(find.textContaining('Publish'), findsNothing);
    await t.tap(find.byKey(const Key('scheduler.approve.7')));
    await t.pumpAndSettle();
    final body = jsonDecode(posts.single.body) as Map;
    expect(posts.single.url.path, '/artifacts/7/review');
    expect(body['action'], 'approve');
    expect(body['sha256'], 'ab' * 32);
  });

  testWidgets('refine asks for an instruction and sends it', (t) async {
    t.view.physicalSize = const Size(1400, 1600);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    await t.pumpWidget(host(client()));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('scheduler.refine.7')));
    await t.pumpAndSettle();
    await t.enterText(find.byKey(const Key('scheduler.instruction')), 'More floral energy');
    await t.tap(find.text('Send'));
    await t.pumpAndSettle();
    final body = jsonDecode(posts.single.body) as Map;
    expect(body['action'], 'refine');
    expect(body['instruction'], 'More floral energy');
  });

  testWidgets('festival setup shows dates and sources before activation', (t) async {
    t.view.physicalSize = const Size(1400, 1600);
    t.view.devicePixelRatio = 1;
    addTearDown(t.view.reset);
    await t.pumpWidget(host(client()));
    await t.pumpAndSettle();
    await t.tap(find.byKey(const Key('scheduler.setupFestivals')));
    await t.pumpAndSettle();
    expect(find.textContaining('2026-11-08 → GIF 2026-11-06T09:00'), findsOneWidget);
    expect(find.textContaining('losoong_namsoong 2026-12-09 (unverified)'), findsOneWidget);
    expect(posts.map((p) => p.url.path), ['/jobs/propose-festivals']);
    await t.tap(find.byKey(const Key('scheduler.confirmProposal')));
    await t.pumpAndSettle();
    expect(posts.last.url.path, '/jobs/job_1/confirm');
    expect((jsonDecode(posts.last.body) as Map)['proposal_sha256'], 'cd' * 32);
  });
}
