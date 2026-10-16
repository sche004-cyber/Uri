import 'dart:convert';

import 'a2ui_contract.dart';
import 'a2ui_hub.dart';
import 'sha256.dart';

enum CompanionUiAction {
  chat,
  review,
  voiceStart,
  voiceFinish,
  voiceCancel,
  workspace,
  dashboard,
  collapse,
}

/// Local, ephemeral A2UI producer. It has no runtime, scheduler or network
/// authority. Runtime hubs reject this separate catalog and its actions.
class CompanionActions {
  CompanionActions(this.invoke) {
    for (final action in CompanionUiAction.values) {
      hub.registry['companion.${action.name}'] = (message) async {
        final current = hub.surface(surfaceId);
        final context = message['context'] as Map?;
        if (current == null ||
            context?['surface_digest'] != current.digest ||
            !_visible.contains(action)) {
          throw StateError('STALE_COMPANION_ACTION');
        }
        await invoke(action);
        return {'messages': <Object>[]};
      };
    }
  }
  static const surfaceId = 'companion-controls';
  static const labels = {
    CompanionUiAction.chat: 'Chat',
    CompanionUiAction.review: 'Review',
    CompanionUiAction.voiceStart: 'Voice',
    CompanionUiAction.voiceFinish: 'Finish',
    CompanionUiAction.voiceCancel: 'Cancel',
    CompanionUiAction.workspace: 'Workspace',
    CompanionUiAction.dashboard: 'Dashboard',
    CompanionUiAction.collapse: 'Collapse',
  };
  static const policy = A2uiPolicy(
    catalogId: 'uri:a2ui/companion-local/v1',
    actions: {
      'companion.chat': {},
      'companion.review': {},
      'companion.voiceStart': {},
      'companion.voiceFinish': {},
      'companion.voiceCancel': {},
      'companion.workspace': {},
      'companion.dashboard': {},
      'companion.collapse': {},
    },
  );
  final Future<void> Function(CompanionUiAction) invoke;
  final hub = A2uiHub(policy: policy);
  List<CompanionUiAction> _visible = [];
  int _revision = 0;
  void project(List<CompanionUiAction> visible) {
    if (jsonEncode(visible.map((a) => a.name).toList()) ==
        jsonEncode(_visible.map((a) => a.name).toList())) {
      return;
    }
    _visible = List.unmodifiable(visible);
    final digest = sha256Hex(
      utf8.encode('${++_revision}:${visible.map((a) => a.name).join(',')}'),
    );
    hub.apply([
      {
        'version': a2uiVersion,
        'createSurface': {
          'surfaceId': surfaceId,
          'catalogId': policy.catalogId,
          'theme': {'placement': 'companion'},
        },
      },
      {
        'version': a2uiVersion,
        'updateComponents': {
          'surfaceId': surfaceId,
          'components': [
            {
              'id': 'root',
              'component': 'Row',
              'gap': 'none',
              'children': visible.map((a) => a.name).toList(),
            },
            for (final a in visible)
              {
                'id': a.name,
                'component': 'Button',
                'label': labels[a],
                'variant': 'secondary',
                'action': {
                  'event': {
                    'name': 'companion.${a.name}',
                    'context': <String, Object?>{},
                  },
                },
              },
          ],
        },
      },
      {
        'version': a2uiVersion,
        'updateDataModel': {
          'surfaceId': surfaceId,
          'path': '/',
          'value': {
            'bound': {
              'surface': {
                'digest': digest,
                'title': 'Companion controls',
                'kind': 'local_navigation',
                'revision': _revision,
              },
            },
          },
        },
      },
    ]);
  }

  void dispose() => hub.dispose();
}
