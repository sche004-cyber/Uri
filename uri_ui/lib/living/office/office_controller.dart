import 'dart:async';

import 'package:flutter/foundation.dart';

import '../a2ui/a2ui_hub.dart';
import '../integration/scheduler_client.dart' show SchedulerApiError;
import 'office_bridge.dart';
import 'office_client.dart';

/// State of the Office panel: one open workbook, its draft (from the service, the authority), the page surface,
/// and an A2UI hub that renders the service's approval card. Every change goes through the service; the page
/// only shows the workbook and reports the owner's typing.
class OfficeController extends ChangeNotifier {
  OfficeController({required this.client, required this.surface}) {
    hub.registry['office.apply_change'] = _approvalAction;
    hub.registry['office.reject_change'] = _approvalAction;
    _sub = surface.messages.listen(_onPage);
  }

  final OfficeClient client;
  final OfficeSurface surface;
  final A2uiHub hub = A2uiHub();
  StreamSubscription<Map<String, dynamic>>? _sub;

  Map<String, dynamic>? view;      // service view: workbook, draft, engine, label, history_on
  bool pageReady = false;
  bool busy = false;
  String? notice;                  // last message for the owner (never cell values from the service)
  String? brainMessage;

  String? get workbookId => view?['workbook_id'] as String?;
  Map<String, dynamic> get draft => (view?['draft'] as Map?)?.cast<String, dynamic>() ?? const {};
  List<Map<String, dynamic>> get changes =>
      [for (final c in (draft['changes'] as List? ?? const [])) (c as Map).cast<String, dynamic>()];
  List<Map<String, dynamic>> get proposed => [for (final c in changes) if (c['state'] == 'proposed') c];

  /// Marks the page shows: the latest live change per cell.
  List<Map<String, dynamic>> marks() {
    final latest = <String, Map<String, dynamic>>{};
    for (final c in changes) {
      if (c['kind'] != 'cell') continue;
      final state = c['state'];
      if (state != 'proposed' && state != 'accepted' && state != 'user') continue;
      latest['${c['sheet']}!${c['cell']}'] = {'sheet': c['sheet'], 'cell': c['cell'], 'state': state, 'after': c['after']};
    }
    return latest.values.toList();
  }

  Future<void> _guard(Future<void> Function() fn) async {
    if (busy) return;
    busy = true;
    notice = null;
    notifyListeners();
    try {
      await fn();
    } on SchedulerApiError catch (e) {
      notice = _human(e.code, e.detail);
    } on OfficeSurfaceError catch (e) {
      notice = 'The sheet view could not start ($e).';
    } catch (e) {
      notice = 'URI Office could not complete that: $e';
    } finally {
      busy = false;
      notifyListeners();
    }
  }

  String _human(String code, String? detail) => switch (code) {
        'PATH_REFUSED' => 'That file cannot be used here (${detail ?? ''}).',
        'TARGET_CHANGED' => 'The file changed outside URI since it was opened. Reload it or save as a new file.',
        'FILE_OPEN_ELSEWHERE' => 'The file is open in Excel. Close it there first.',
        'PERMISSION_NOT_GRANTED' =>
          'Editing this Google Sheet in place needs a Google permission the owner has not granted. Use "Edit a copy".',
        'GOOGLE_NOT_CONNECTED' => 'URI\'s Google connection is not set up or has expired.',
        'NOT_A_SHEETS_LINK' => 'Paste a link that starts with https://docs.google.com/spreadsheets/d/.',
        'BRAIN_UNAVAILABLE' => 'The local Brain is not running. Nothing was changed.',
        'CELL_NOT_EDITABLE' => 'That cell is part of a table header, shared formula or merged range and cannot be edited here.',
        'STALE_CHANGE' || 'STALE_SURFACE' || 'CHANGE_MISMATCH' => 'This changed since it was shown. Please review it again.',
        _ => 'Refused: $code${detail == null || detail.isEmpty ? '' : ' ($detail)'}',
      };

  Future<void> _apply(Map<String, dynamic> v) async {
    view = v;
    await _sendLoad();
  }

  Future<void> _sendLoad() async {
    final v = view;
    if (!pageReady || v == null) return;
    await surface.post({'type': 'load', 'workbook': v['workbook'], 'marks': marks()});
  }

  Future<void> _refreshDraft(Map<String, dynamic> r) async {
    final d = r['draft'];
    if (d is Map && view != null) {
      view = {...view!, 'draft': d};
      if (pageReady) await surface.post({'type': 'load', 'workbook': view!['workbook'], 'marks': marks()});
    }
  }

  // ---- page --------------------------------------------------------------------------------------------------
  Future<void> _onPage(Map<String, dynamic> m) async {
    switch (m['type']) {
      case 'ready':
        pageReady = true;
        await _sendLoad();
        notifyListeners();
      case 'edit':
        final wid = workbookId;
        if (wid == null) return;
        final body = {'sheet': m['sheet'], 'cell': m['cell'], if (m.containsKey('formula')) 'formula': m['formula'] else 'value': m['value']};
        await _guard(() async => _refreshDraft(await client.edit(wid, body)));
        if (notice != null) await _sendLoad();   // refused: show the service's truth again
      case 'error':
        notice = 'The sheet view reported a problem (${m['code']}).';
        notifyListeners();
    }
  }

  // ---- owner actions -----------------------------------------------------------------------------------------
  Future<void> openLocal(String path) => _guard(() async => _apply(await client.openLocal(path)));
  Future<void> openGoogle(String url) => _guard(() async => _apply(await client.openGoogle(url)));

  Future<void> instruct(String text, {String? activeSheet}) => _guard(() async {
        final wid = workbookId;
        if (wid == null) return;
        final r = await client.instruct(wid, text, activeSheet: activeSheet);
        brainMessage = r['message'] as String?;
        final refused = (r['refused'] as List?) ?? const [];
        if (refused.isNotEmpty) notice = '${refused.length} suggested change(s) were refused as unsafe or invalid.';
        await _refreshDraft(r);
      });

  Future<void> decide(Map<String, dynamic> change, String decision, {String reason = ''}) => _guard(() async {
        final wid = workbookId;
        if (wid == null) return;
        await _refreshDraft(await client.decide(wid, change['cid'] as String, decision,
            change['change_sha256'] as String, reason: reason));
      });

  Future<void> undo() => _guard(() async => _refreshDraft(await client.undo(workbookId!)));
  Future<void> redo() => _guard(() async => _refreshDraft(await client.redo(workbookId!)));

  Future<void> proposeSave({String? saveAsPath}) => _guard(() async {
        final r = await client.proposeSave(workbookId!, saveAsPath: saveAsPath);
        hub.apply((r['messages'] as List?) ?? const []);
      });

  Future<void> proposeShare() => _guard(() async {
        final r = await client.proposeShare(workbookId!);
        hub.apply((r['messages'] as List?) ?? const []);
      });

  Future<void> editCopy() => _guard(() async => _apply(await client.editCopy(workbookId!)));

  Future<void> setHistory(bool on) => _guard(() async {
        await client.history(workbookId!, 'consent', on: on);
        view = {...view!, 'history_on': on};
      });

  Future<Map<String, dynamic>> _approvalAction(Map<String, dynamic> action) async {
    final r = await client.a2uiAction(action);
    final result = (r['result'] as Map).cast<String, dynamic>();
    await _refreshDraft(result);
    notice = result['status'] == 'applied'
        ? (result['saved_to'] != null ? 'Saved to ${result['saved_to']}.' : 'Applied.')
        : 'Nothing was changed.';
    notifyListeners();
    return r;
  }

  @override
  void dispose() {
    _sub?.cancel();
    unawaited(surface.dispose());
    hub.dispose();
    final wid = workbookId;
    if (wid != null) unawaited(client.close(wid).then((_) {}, onError: (_) {}));
    super.dispose();
  }
}
