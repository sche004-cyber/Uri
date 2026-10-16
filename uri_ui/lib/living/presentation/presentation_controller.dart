import 'package:flutter/foundation.dart';

/// The forms of the one companion. Assist (docs/assist) is the fourth form:
/// opening it observes nothing; it only offers to share one scope.
enum UiPresentationMode { companion, workspace, dashboard, assist }

extension UiPresentationModeLabel on UiPresentationMode {
  String get label => switch (this) {
    UiPresentationMode.companion => 'Companion',
    UiPresentationMode.workspace => 'Workspace',
    UiPresentationMode.dashboard => 'Dashboard',
    UiPresentationMode.assist => 'Assist',
  };
}

/// Where a mode change came from. Kept so the UI can tell the user when
/// URI (a command) moved the presentation rather than they did.
enum UiCommandOrigin { user, localCommand, brain }

/// The restricted vocabulary URI may use to steer its own presentation.
///
/// Deliberately tiny: a mode, and an optional focus hint inside the
/// Workspace. A command can never send text, approve, pick an executor,
/// change a setting, or dismiss an approval card. Anything else the
/// Brain wants shown must go through the Core's own typed protocol.
sealed class UiCommand {
  const UiCommand();
}

class ShowModeCommand extends UiCommand {
  const ShowModeCommand(this.mode, {this.focus, this.officeView});
  final UiPresentationMode mode;

  /// Workspace region to bring forward, e.g. `tasks`, `documents`,
  /// `intelligence`. Ignored by other modes and by unknown values.
  final WorkspaceFocus? focus;

  /// O2: the view inside the Office region (refinement 9). A view only; it never opens a file or acts on one.
  final OfficeView? officeView;

  @override
  String toString() =>
      'ShowModeCommand(${mode.name}, focus: ${focus?.name}${officeView == null ? '' : ', office: ${officeView!.name}'})';
}

enum WorkspaceFocus { conversation, tasks, documents, office, intelligence, settings }

/// O2 (plan §4.4): the closed set of views inside the Office region. `documents` is also where the retired
/// Documents rail item leads.
enum OfficeView { home, recent, documents, spreadsheets, presentations, pdfs, templates, workflows }

const _officeViewWords = {
  'home': OfficeView.home,
  'recent': OfficeView.recent,
  'documents': OfficeView.documents,
  'docs': OfficeView.documents,
  'spreadsheets': OfficeView.spreadsheets,
  'sheets': OfficeView.spreadsheets,
  'workbooks': OfficeView.spreadsheets,
  'presentations': OfficeView.presentations,
  'slides': OfficeView.presentations,
  'pdfs': OfficeView.pdfs,
  'pdf': OfficeView.pdfs,
  'templates': OfficeView.templates,
  'workflows': OfficeView.workflows,
};

/// Parses the demo phrases the brief asks for, from local text only.
///
/// Grammar (case-insensitive, surrounding whitespace ignored):
///
///     uri dashboard            -> ShowModeCommand(dashboard)
///     uri workspace            -> ShowModeCommand(workspace)
///     uri assist               -> ShowModeCommand(assist)
///     uri companion | uri minimize | uri orb -> ShowModeCommand(companion)
///     uri tasks | uri documents | uri intelligence | uri settings
///                              -> ShowModeCommand(workspace, focus: ...)
///
/// Anything else returns null and is treated as ordinary chat, so a
/// sentence like "show me the dashboard numbers" is never hijacked.
UiCommand? parseLocalUiCommand(String text) {
  final t = text.trim().toLowerCase().replaceAll(RegExp(r'\s+'), ' ');
  if (!t.startsWith('uri ')) return null;
  final word = t.substring(4).replaceAll(RegExp(r'[.!,]+$'), '').trim();
  // O2: "uri office" and "uri office <view>" (plan §4.4).
  if (word == 'office') {
    return const ShowModeCommand(UiPresentationMode.workspace, focus: WorkspaceFocus.office,
        officeView: OfficeView.home);
  }
  if (word.startsWith('office ')) {
    final v = _officeViewWords[word.substring(7).trim()];
    return v == null
        ? null
        : ShowModeCommand(UiPresentationMode.workspace, focus: WorkspaceFocus.office, officeView: v);
  }
  return switch (word) {
    'dashboard' ||
    'overview' => const ShowModeCommand(UiPresentationMode.dashboard),
    'workspace' ||
    'work' => const ShowModeCommand(UiPresentationMode.workspace),
    'assist' => const ShowModeCommand(UiPresentationMode.assist),
    'companion' ||
    'minimize' ||
    'orb' ||
    'minimise' => const ShowModeCommand(UiPresentationMode.companion),
    'tasks' => const ShowModeCommand(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.tasks,
    ),
    'documents' || 'docs' => const ShowModeCommand(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.documents,
      officeView: OfficeView.documents,
    ),
    'intelligence' || 'brain' => const ShowModeCommand(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.intelligence,
    ),
    'settings' => const ShowModeCommand(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.settings,
    ),
    'chat' || 'conversation' => const ShowModeCommand(
      UiPresentationMode.workspace,
      focus: WorkspaceFocus.conversation,
    ),
    _ => null,
  };
}

/// Single owner of "which form is URI in right now".
///
/// The user always keeps manual control: [setMode] from a user gesture
/// is applied immediately and unconditionally. A command ([apply]) is
/// also applied, but it is recorded in [lastCommandOrigin] / [history]
/// so the shell can show "URI switched to Dashboard" and the user can
/// step back. Commands are rate-limited to one per [commandCooldown] so
/// a chatty source cannot thrash the presentation.
class UiPresentationController extends ChangeNotifier {
  UiPresentationController({
    UiPresentationMode initialMode = UiPresentationMode.companion,
    this.commandCooldown = const Duration(milliseconds: 600),
    DateTime Function()? clock,
  }) : _mode = initialMode,
       _clock = clock ?? DateTime.now;

  final Duration commandCooldown;
  final DateTime Function() _clock;

  UiPresentationMode _mode;
  WorkspaceFocus _focus = WorkspaceFocus.conversation;
  UiCommandOrigin _lastOrigin = UiCommandOrigin.user;
  DateTime? _lastCommandAt;
  final List<UiPresentationMode> _history = [];
  OfficeView _officeView = OfficeView.home;
  final List<OfficeView> _officeHistory = [];

  /// O2: the view inside the Office region, and its own Back history (plan §4.4, review F3/N6).
  OfficeView get officeView => _officeView;
  List<OfficeView> get officeHistory => List.unmodifiable(_officeHistory);

  /// User gesture inside the Office region. Always honoured.
  void setOfficeView(OfficeView view) {
    if (view == _officeView) return;
    _officeHistory.add(_officeView);
    if (_officeHistory.length > 20) _officeHistory.removeAt(0);
    _officeView = view;
    notifyListeners();
  }

  /// Back inside the Office region; false when there is no earlier Office view.
  bool officeBack() {
    if (_officeHistory.isEmpty) return false;
    _officeView = _officeHistory.removeLast();
    notifyListeners();
    return true;
  }

  UiPresentationMode get mode => _mode;
  WorkspaceFocus get focus => _focus;
  UiCommandOrigin get lastCommandOrigin => _lastOrigin;

  /// Previous modes, most recent last; lets "back" return to where the
  /// user was before a command moved them.
  List<UiPresentationMode> get history => List.unmodifiable(_history);

  /// User gesture. Always honoured.
  void setMode(UiPresentationMode mode, {WorkspaceFocus? focus}) {
    _transition(mode, focus, UiCommandOrigin.user);
  }

  void setFocus(WorkspaceFocus focus) {
    if (_focus == focus) return;
    _focus = focus;
    notifyListeners();
  }

  /// Command from URI (local parser today; Brain adapter later).
  /// Returns false when refused (cooldown) so the caller can tell.
  bool apply(
    UiCommand command, {
    UiCommandOrigin origin = UiCommandOrigin.localCommand,
  }) {
    final now = _clock();
    final last = _lastCommandAt;
    if (last != null && now.difference(last) < commandCooldown) return false;
    _lastCommandAt = now;
    switch (command) {
      case ShowModeCommand(:final mode, :final focus, :final officeView):
        _transition(mode, focus, origin);
        if (officeView != null && officeView != _officeView) {
          _officeHistory.add(_officeView);
          if (_officeHistory.length > 20) _officeHistory.removeAt(0);
          _officeView = officeView;
          notifyListeners();
        }
        return true;
    }
  }

  /// Returns to the mode before the last transition, if any.
  bool back() {
    if (_history.isEmpty) return false;
    final previous = _history.removeLast();
    _mode = previous;
    _lastOrigin = UiCommandOrigin.user;
    notifyListeners();
    return true;
  }

  void _transition(
    UiPresentationMode mode,
    WorkspaceFocus? focus,
    UiCommandOrigin origin,
  ) {
    var changed = false;
    if (focus != null && focus != _focus) {
      _focus = focus;
      changed = true;
    }
    if (mode != _mode) {
      _history.add(_mode);
      if (_history.length > 20) _history.removeAt(0);
      _mode = mode;
      changed = true;
    }
    if (origin != _lastOrigin) {
      _lastOrigin = origin;
      changed = true;
    }
    if (changed) notifyListeners();
  }
}
