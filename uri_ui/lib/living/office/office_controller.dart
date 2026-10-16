import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';

import '../a2ui/a2ui_hub.dart';
import '../a2ui/sha256.dart';
import '../integration/scheduler_client.dart' show SchedulerApiError;
import 'office_bridge.dart';
import 'office_client.dart';

/// State of the Office panel: one open workbook, its draft (from the service, the authority), the page surface,
/// and an A2UI hub that renders the service's approval card. Every change goes through the service; the page
/// only shows the workbook and reports the owner's typing.
class OfficeController extends ChangeNotifier implements OfficeRequestTarget {
  OfficeController({required this.client, required this.surface, this.keep, A2uiHub? hub, this.onTurn})
      : hub = hub ?? A2uiHub(),
        _ownsHub = hub == null {
    // O2 (plan §4.3): inside the Office workspace one region-level hub is shared, and the workspace registers the
    // office.* handlers once and hands sheet results back through [handleApprovalResult].
    if (_ownsHub) {
      this.hub.registry['office.apply_change'] = _approvalAction;
      this.hub.registry['office.reject_change'] = _approvalAction;
    }
    _sub = surface.messages.listen(_onPage);
  }

  /// O2: every conversation line is also given to the Office workspace's one conversation (plan §4.5).
  final void Function(OfficeTurn turn)? onTurn;
  final bool _ownsHub;

  final OfficeClient client;

  /// Where the open workbook and its conversation are kept when the panel is left (R1-02). Null: closing the panel
  /// closes the workbook in the service.
  final OfficeKeep? keep;
  final OfficeSurface surface;
  final A2uiHub hub;
  StreamSubscription<Map<String, dynamic>>? _sub;

  Map<String, dynamic>? view;      // service view: workbook, draft, engine, label, history_on
  bool pageReady = false;
  @override
  bool busy = false;
  String? notice;                  // last message for the owner (never cell values from the service)
  String? brainMessage;

  // The owner's typing from the page, sent to the service one at a time and in order. Never dropped: a paste sends
  // one message per cell, and the owner may type while a Brain turn or another action is running.
  final List<(String, Map<String, dynamic>)> _pageEdits = [];
  bool _sendingEdits = false;

  String? get workbookId => view?['workbook_id'] as String?;
  Map<String, dynamic> get draft => (view?['draft'] as Map?)?.cast<String, dynamic>() ?? const {};
  List<Map<String, dynamic>> get changes =>
      [for (final c in (draft['changes'] as List? ?? const [])) (c as Map).cast<String, dynamic>()];
  List<Map<String, dynamic>> get proposed => [for (final c in changes) if (c['state'] == 'proposed') c];

  /// M2: a new workbook built from source files (no file yet).
  bool get isNew => view?['engine'] == 'new';
  List<Map<String, dynamic>> get sources =>
      [for (final s in (view?['sources'] as List? ?? const [])) (s as Map).cast<String, dynamic>()];

  /// M2-D10: files without a role yet (URI does not work with the files until each has one).
  List<String> get rolesNeeded => [for (final s in sources) if (s['role'] == null) s['label'] as String];

  /// M2-D11: the working file's source id (checked or edited, shown in the sheet view), or null (a new workbook).
  String? get working => view?['working'] as String?;

  /// "build" (no working file), "check" or "edit".
  String get task => view?['task'] as String? ?? 'build';

  /// Sets one file's role. Making a file the working file makes the previous working file a reference.
  Future<void> setRole(String sid, String role) => _guard(() async {
        final wid = workbookId;
        if (wid == null) return;
        final roles = <String, String>{
          for (final s in sources)
            if (s['role'] is String) s['id'] as String: s['role'] as String,
        };
        if (role != 'reference') {
          roles.updateAll((k, v) => k != sid && v != 'reference' ? 'reference' : v);
        }
        roles[sid] = role;
        final before = working;
        await _apply(await client.setRoles(wid, roles));
        if (working != before) {
          _clearSurfaces();
          final w = sources.where((s) => s['id'] == working).map((s) => s['label']).firstOrNull;
          _say(OfficeSpeaker.notice, w == null
              ? 'No working file: URI builds a new workbook from the references.'
              : 'Working file: $w (${task == 'check' ? 'URI checks it and suggests fixes' : 'URI edits it'}). '
                  'The other files are references.');
        }
      });

  /// M2-D2: SHA-256 over the sorted (change id, change hash) pairs of every proposed change, as the service computes
  /// it (`Draft.proposed_set_sha256`, canonical JSON).
  String proposedSetSha256() {
    final pairs = [for (final c in proposed) [c['cid'] as String, c['change_sha256'] as String]]
      ..sort((a, b) => a[0].compareTo(b[0]));
    return sha256Hex(Uint8List.fromList(utf8.encode(jsonEncode(pairs))));
  }

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
        'ROLES_NEEDED' => 'First say what each file is for: the working file (check or edit) or a reference. '
            '${detail ?? ''}',
        'ONE_WORKING_FILE' => 'Only one file can be the working file at a time.',
        'SAVE_OR_DISCARD_FIRST' => 'Save or undo the changes to the current working file before switching to another.',
        'NOT_A_SHEETS_LINK' => 'Paste a link that starts with https://docs.google.com/spreadsheets/d/.',
        'BRAIN_UNAVAILABLE' => 'The local Brain is not running. Nothing was changed.',
        'CELL_NOT_EDITABLE' => 'That cell is part of a table header, shared formula or merged range and cannot be edited here.',
        'STALE_CHANGE' || 'STALE_SURFACE' || 'CHANGE_MISMATCH' => 'This changed since it was shown. Please review it again.',
        'RELOAD_REQUIRED' =>
          'The sheet\'s rows or sheets changed with the last save. The sheet was reloaded; nothing was changed by that edit.',
        _ => 'Refused: $code${detail == null || detail.isEmpty ? '' : ' ($detail)'}',
      };

  Future<void> _apply(Map<String, dynamic> v) async {
    final previous = workbookId;
    if (v['workbook_id'] != previous) {
      _forgetWorkbook();
      // The owner opened another workbook: the previous one is closed in the service (it was replaced on purpose).
      if (previous != null) unawaited(client.close(previous).then((_) {}, onError: (_) {}));
    }
    view = v;
    await _sendLoad();
  }

  Future<void> _sendLoad() async {
    final v = view;
    if (!pageReady || v == null) return;
    await surface.post({'type': 'load', 'workbook': v['workbook'], 'marks': marks(), 'formatting': savesFormatting});
  }

  /// OD-R3 / XF-1: the service saves the owner's formatting for local workbooks (not Google Sheets, not a new one).
  bool get savesFormatting => view?['engine'] == 'local';

  Future<void> _refreshDraft(Map<String, dynamic> r) async {
    final d = r['draft'];
    if (d is Map && view != null) {
      // After a save the service returns the workbook as the file now holds it; reload the grid from that, not from
      // the values as opened.
      final w = r['workbook'];
      final lv = r['layout_version'];
      view = {...view!, 'draft': d, if (w is Map) 'workbook': w, 'layout_version': ?lv};
      if (pageReady) {
        await surface.post({'type': 'load', 'workbook': view!['workbook'], 'marks': marks(),
          'formatting': savesFormatting});
      }
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
        // The grid's layout version goes with the edit: the service refuses coordinates from a grid whose rows moved.
        final lv = view?['layout_version'];
        final body = {'sheet': m['sheet'], 'cell': m['cell'], if (m.containsKey('formula')) 'formula': m['formula'] else 'value': m['value'],
          'layout_version': ?lv};
        _pageEdits.add((wid, body));
        await _sendPageEdits();
      case 'format':                                      // OD-R3: the owner's formatting, saved with the next save
        final wid = workbookId;
        if (wid == null || !savesFormatting) return;
        final lv = view?['layout_version'];
        _pageEdits.add((wid, {'sheet': m['sheet'], 'cell': m['cell'], 'style': m['style'], 'layout_version': ?lv}));
        await _sendPageEdits();
      case 'error':
        notice = switch (m['code']) {
          'STRUCTURE_CHANGE_NOT_SUPPORTED' =>
            'To insert or delete rows, ask URI (for example "insert a row above row 5"); it shows the change for '
                'you to approve. Columns, moving and sorting, and adding or renaming sheets are not available here '
                'yet. Nothing was changed.',
          // XF-1: formatting is not saved yet, so the page does not apply it (values and formulas still are).
          'FORMAT_CHANGE_NOT_SAVED' => 'Formatting (bold, colours, number formats, borders, merged cells) and '
              'column widths or row heights are not saved by this panel yet, so they were not applied. Values and '
              'formulas are kept.',
          // OD-R3: bold, italic, underline, colours, fill, number formats, alignment and wrap are saved now.
          'FORMAT_PARTLY_NOT_SAVED' => 'Bold, italic, underline, text colour, fill, number formats, alignment and '
              'wrap are saved. Font size and family, borders, merged cells and column widths or row heights are not '
              'saved by this panel yet, so those parts were not applied.',
          _ => 'The sheet view reported a problem (${m['code']}).',
        };
        notifyListeners();
    }
  }

  /// Sends queued page edits in order, independent of [busy] (the service serialises them with the draft lock, also
  /// during a Brain turn). The page is reloaded from the service once the queue is empty, so it shows every edit the
  /// service kept and none it refused.
  Future<void> _sendPageEdits() async {
    if (_sendingEdits) return;           // the running loop picks up edits added meanwhile
    _sendingEdits = true;
    Map<String, dynamic>? last;
    var refused = false;
    var reload = false;
    try {
      while (_pageEdits.isNotEmpty) {
        final (wid, body) = _pageEdits.removeAt(0);
        if (wid != workbookId) continue;   // that workbook was closed or replaced
        try {
          last = await client.edit(wid, body);
        } on SchedulerApiError catch (e) {
          refused = true;
          if (e.code == 'RELOAD_REQUIRED') reload = true;
          notice = _human(e.code, e.detail);
        } catch (e) {
          refused = true;
          notice = 'URI Office could not complete that: $e';
        }
      }
    } finally {
      _sendingEdits = false;
    }
    if (reload) {
      await _reloadView();               // the grid's layout is stale: load the sheet as it is now
    } else if (last != null) {
      await _refreshDraft(last);
    } else if (refused) {
      await _sendLoad();                 // refused: show the service's truth again
    }
    notifyListeners();
  }

  /// Asks the service to re-read a Google sheet whose layout a save changed (a POST: reading the view never changes
  /// state) and reloads the grid. Until that succeeds the service refuses edits from the old grid.
  Future<void> _reloadView() async {
    final wid = workbookId;
    if (wid == null) return;
    try {
      final v = await client.reload(wid);
      if (wid == workbookId) await _apply(v);
      if (v['reload_required'] == true) {
        notice = 'The save was applied, but the sheet could not be read again. Edits are paused until it reloads; '
            'reopen it or try again.';
      }
    } catch (_) {
      notice = 'The save was applied, but the sheet could not be read again. Reopen it before editing.';
    }
  }

  /// Shows the kept workbook again after the panel was left and reopened (R1-02): the service still holds it with
  /// its draft and any open approval card. If the service no longer has it (restarted), the keep is cleared and the
  /// owner is told; nothing is guessed.
  Future<void> resume() => _guard(() async {
        final k = keep;
        final wid = k?.workbookId;
        if (k == null || wid == null) return;
        try {
          final v = await client.view(wid);
          await _apply(v);
          conversation
            ..clear()
            ..addAll(k.conversation);
          final open = await client.surfaces(wid);
          hub.apply((open['messages'] as List?) ?? const []);
          final kept = changes.where((c) => c['state'] == 'accepted' || c['state'] == 'user').length;
          if (kept > 0) notice = 'Your unsaved changes to ${v['label'] ?? 'the workbook'} are still here.';
        } on SchedulerApiError catch (e) {
          k.clear();
          if (e.code != 'UNKNOWN_WORKBOOK') rethrow;
          notice = 'The workbook you had open is no longer open in URI Office (the service restarted). Open it again.';
        }
      });

  // ---- owner actions -----------------------------------------------------------------------------------------
  Future<void> openLocal(String path) => _guard(() async => _apply(await client.openLocal(path)));
  Future<void> openGoogle(String url) => _guard(() async => _apply(await client.openGoogle(url)));

  /// M2: a fresh workbook with the picked files as read-only sources.
  Future<void> openNew(List<String> paths) => _guard(() async {
        if (paths.isEmpty) return;
        await _apply(await client.openNew(paths));
        _say(OfficeSpeaker.notice, 'Added ${sources.map((s) => s['label']).join(', ')}. Say what each file is for: '
            'the working file (check or edit) or a reference. With only references, URI builds a new workbook. '
            'Nothing is saved until you approve it.');
      });

  /// M2: more source files for the open new workbook.
  Future<void> addSources(List<String> paths) => _guard(() async {
        final wid = workbookId;
        if (wid == null || paths.isEmpty) return;
        final before = sources.length;
        final v = await client.addSources(wid, paths);
        view = {...view!, 'sources': v['sources']};
        _say(OfficeSpeaker.notice, 'Added ${sources.skip(before).map((s) => s['label']).join(', ')}.');
      });

  /// M2-D2: accept or reject every proposed change shown, all or nothing.
  Future<void> decideAll(String decision) => _guard(() async {
        final wid = workbookId;
        if (wid == null || proposed.isEmpty) return;
        await _refreshDraft(await client.decideAll(wid, decision, draft['version'] as int, proposedSetSha256()));
      });

  @override
  bool get acceptsRequests => workbookId != null;

  /// The owner's requests and URI's replies for this workbook, shown in the companion pane. Text only: the
  /// suggested changes themselves are the change cards, never copied into this list.
  final List<OfficeTurn> conversation = [];
  static const int conversationCap = 100;

  /// Another workbook is now open (R1-01): the conversation, URI's last reply and any approval card belong to the
  /// previous one, so they are removed instead of shown next to the new workbook.
  void _forgetWorkbook() {
    conversation.clear();
    brainMessage = null;
    _clearSurfaces();
  }

  void _clearSurfaces() {
    final old = [for (final s in hub.surfaces) s.id];
    if (old.isNotEmpty) {
      hub.apply([for (final id in old) {'version': 'v0.9', 'deleteSurface': {'surfaceId': id}}]);
    }
  }

  void _say(OfficeSpeaker who, String text) {
    conversation.add(OfficeTurn(who, text));
    onTurn?.call(OfficeTurn(who, text));
    if (conversation.length > conversationCap) conversation.removeRange(0, conversation.length - conversationCap);
  }

  @override
  Future<void> instruct(String text, {String? activeSheet}) async {
    final t = text.trim();
    if (busy || t.isEmpty || workbookId == null) return;
    _say(OfficeSpeaker.owner, t);
    final missing = rolesNeeded;
    if (missing.isNotEmpty) {
      // M2-D10: the owner says what each file is for before URI works with the files.
      _say(OfficeSpeaker.notice, 'First say what each file is for (working file or reference): ${missing.join(', ')}. '
          'Nothing was sent.');
      notifyListeners();
      return;
    }
    brainMessage = null;
    final before = proposed.length;
    await _guard(() async {
      final wid = workbookId;
      if (wid == null) return;
      final r = await client.instruct(wid, t, activeSheet: activeSheet);
      brainMessage = r['message'] as String?;
      final refused = (r['refused'] as List?) ?? const [];
      if (refused.isNotEmpty) {
        // Say why, so the owner can rephrase: the code and the service's short detail of each refused op.
        final why = {
          for (final x in refused.whereType<Map>())
            '${x['code']}${(x['detail'] as String? ?? '').isEmpty ? '' : ': ${x['detail']}'}',
        };
        notice = '${refused.length} suggested change(s) were refused as unsafe or invalid (${why.join('; ')}).';
      }
      final found = (r['findings'] as List?)?.whereType<Map>().toList();
      if (found != null) {
        findings = [
          for (final f in found)
            '${f['sheet'] == null ? '' : '${f['sheet']}${f['cell'] == null ? '' : '!${f['cell']}'}: '}${f['issue']}',
        ];
      }
      final notes = (r['notes'] as Map?) ?? const {};
      final unc = notes['uncalculated'] as int? ?? 0;
      final skipped = notes['not_copied'] as int? ?? 0;
      if (unc > 0 || skipped > 0) {
        copyNote = [
          if (unc > 0) '$unc source formula cell(s) had no calculated value and were copied as empty',
          if (skipped > 0) '$skipped value(s) could not be copied as values and were left empty',
        ].join('; ');
      }
      await _refreshDraft(r);
    });
    final reply = brainMessage;
    final added = proposed.length - before;
    if (reply != null && reply.trim().isNotEmpty) {
      _say(OfficeSpeaker.uri, reply.trim());
    } else if (added > 0) {
      _say(OfficeSpeaker.uri, 'I suggested $added change${added == 1 ? '' : 's'}. Review below.');
    } else if (notice == null) {
      _say(OfficeSpeaker.uri, 'No change was suggested.');
    }
    if (notice != null) _say(OfficeSpeaker.notice, notice!);
    final f = findings;
    if (f != null) {
      _say(OfficeSpeaker.uri, f.isEmpty ? 'Check: no issues found.' : 'Check: ${f.length} issue(s) found.');
      for (final line in f.take(maxFindingLines)) {
        _say(OfficeSpeaker.uri, line);
      }
      if (f.length > maxFindingLines) _say(OfficeSpeaker.uri, 'and ${f.length - maxFindingLines} more.');
      findings = null;
    }
    final note = copyNote;
    if (note != null) _say(OfficeSpeaker.notice, '$note.');
    copyNote = null;
    notifyListeners();
  }

  /// M2-D3: what a copy from the sources could not carry over, said once after the request.
  String? copyNote;

  /// M2-D11: a check's findings ("Sheet!B4: issue"), said once after the request.
  List<String>? findings;
  static const int maxFindingLines = 30;

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
        _dropOlderCards();
        hub.apply((r['messages'] as List?) ?? const []);
      });

  Future<void> proposeShare() => _guard(() async {
        final r = await client.proposeShare(workbookId!);
        _dropOlderCards();
        hub.apply((r['messages'] as List?) ?? const []);
      });

  /// The service keeps one open approval per workbook and closes the older one when a new one is proposed; the app
  /// drops the older card too, so it never shows a card that can only be refused (live run a5: two save cards).
  void _dropOlderCards() {
    final ids = [for (final s in hub.surfaces) if (s.id.startsWith('office.$workbookId.')) s.id];
    if (ids.isNotEmpty) hub.apply([for (final id in ids) {'version': 'v0.9', 'deleteSurface': {'surfaceId': id}}]);
  }

  Future<void> editCopy() => _guard(() async => _apply(await client.editCopy(workbookId!)));

  Future<void> setHistory(bool on) => _guard(() async {
        await client.history(workbookId!, 'consent', on: on);
        view = {...view!, 'history_on': on};
      });

  Future<Map<String, dynamic>> _approvalAction(Map<String, dynamic> action) async {
    final r = await client.a2uiAction(action);
    await handleApprovalResult((r['result'] as Map).cast<String, dynamic>());
    return r;
  }

  /// The sheet part of an approval reply (save, share, new file), also used by the Office workspace's shared hub.
  Future<void> handleApprovalResult(Map<String, dynamic> result) async {
    await _refreshDraft(result);
    notice = result['status'] == 'applied'
        ? (result['created'] == true
            ? result['reopen_needed'] == true
                ? 'Created ${result['saved_to']}. It could not be opened here; open it with Open file.'
                : 'Created ${result['saved_to']}.'
            : result['saved_to'] != null
                ? 'Saved to ${result['saved_to']}.'
                : 'Applied.')
        : 'Nothing was changed.';
    final wid = workbookId;
    if (result['created'] == true && result['reopen_needed'] != true && wid != null) {
      view = await client.view(wid);       // engine is now local; sources are released
      await _sendLoad();
    }
    if (result['layout_reloaded'] == false || result['reload_required'] == true) {
      await _reloadView();               // the grid still shows the old rows: never let the owner edit it as is
    }
    notifyListeners();
  }

  @override
  void dispose() {
    _sub?.cancel();
    unawaited(surface.dispose());
    if (_ownsHub) hub.dispose();
    final wid = workbookId;
    final k = keep;
    if (k != null && wid != null) {
      k.workbookId = wid;                  // left, not closed: the draft stays in the service (R1-02)
      k.conversation = List.unmodifiable(conversation);
    } else if (wid != null) {
      unawaited(client.close(wid).then((_) {}, onError: (_) {}));
    }
    super.dispose();
  }
}
