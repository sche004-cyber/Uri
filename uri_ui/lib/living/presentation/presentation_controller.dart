import 'package:flutter/foundation.dart';

/// The three forms of the one companion.
enum UiPresentationMode { companion, workspace, dashboard }

extension UiPresentationModeLabel on UiPresentationMode {
  String get label => switch (this) {
    UiPresentationMode.companion => 'Companion',
    UiPresentationMode.workspace => 'Workspace',
    UiPresentationMode.dashboard => 'Dashboard',
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
  const ShowModeCommand(this.mode, {this.focus});
  final UiPresentationMode mode;

  /// Workspace region to bring forward, e.g. `tasks`, `documents`,
  /// `intelligence`. Ignored by other modes and by unknown values.
  final WorkspaceFocus? focus;

  @override
  String toString() => 'ShowModeCommand(${mode.name}, focus: ${focus?.name})';
}

enum WorkspaceFocus { conversation, tasks, documents, intelligence, settings }

/// Parses the demo phrases the brief asks for, from local text only.
///
/// Grammar (case-insensitive, surrounding whitespace ignored):
///
///     uri dashboard            -> ShowModeCommand(dashboard)
///     uri workspace            -> ShowModeCommand(workspace)
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
  return switch (word) {
    'dashboard' ||
    'overview' => const ShowModeCommand(UiPresentationMode.dashboard),
    'workspace' ||
    'work' => const ShowModeCommand(UiPresentationMode.workspace),
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
      case ShowModeCommand(:final mode, :final focus):
        _transition(mode, focus, origin);
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
