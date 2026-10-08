import 'dart:async';

import 'package:flutter/foundation.dart';

import '../companion/companion_state.dart';
import '../companion/companion_sources.dart';

/// PROPOSED adapter contract (see `docs/ui_phase/UI_INTERFACE_CONTRACTS.md`
/// section 3): the Workspace's view of office work URI is doing.
///
/// Nothing in the baseline backend serves this shape yet. The real
/// sources that would feed it exist by name only: `GET /tasks` (pending
/// approvals, already on `AppState.tasks`), the supervised execution
/// register (`execution_list`/`execution_status`) and a future
/// documents capability. Until an adapter is accepted, the only
/// implementation is [MockWorkSimulator], which flags every item
/// `simulated: true`.
enum WorkItemKind { letter, spreadsheet, document, email, research, other }

enum WorkItemState { queued, working, awaitingApproval, completed, failed, cancelled }

extension WorkItemStateLabel on WorkItemState {
  String get label => switch (this) {
        WorkItemState.queued => 'Queued',
        WorkItemState.working => 'In progress',
        WorkItemState.awaitingApproval => 'Needs approval',
        WorkItemState.completed => 'Completed',
        WorkItemState.failed => 'Failed',
        WorkItemState.cancelled => 'Cancelled',
      };

  bool get isTerminal =>
      this == WorkItemState.completed ||
      this == WorkItemState.failed ||
      this == WorkItemState.cancelled;
}

@immutable
class WorkItem {
  const WorkItem({
    required this.id,
    required this.title,
    required this.kind,
    required this.state,
    required this.createdAt,
    this.progress,
    this.detail,
    this.outputName,
    this.approvalSummary,
    this.simulated = true,
  });

  final String id;
  final String title;
  final WorkItemKind kind;
  final WorkItemState state;
  final DateTime createdAt;

  /// 0..1 while working, when the executor reports it.
  final double? progress;
  final String? detail;

  /// Name of the produced file/draft when completed.
  final String? outputName;

  /// What the user is asked to approve, when [state] is awaitingApproval.
  final String? approvalSummary;
  final bool simulated;

  WorkItem copyWith({
    WorkItemState? state,
    double? progress,
    String? detail,
    String? outputName,
    String? approvalSummary,
  }) {
    return WorkItem(
      id: id,
      title: title,
      kind: kind,
      state: state ?? this.state,
      createdAt: createdAt,
      progress: progress ?? this.progress,
      detail: detail ?? this.detail,
      outputName: outputName ?? this.outputName,
      approvalSummary: approvalSummary ?? this.approvalSummary,
      simulated: simulated,
    );
  }
}

@immutable
class WorkDocument {
  const WorkDocument({
    required this.id,
    required this.name,
    required this.kind,
    required this.modifiedAt,
    this.simulated = true,
  });
  final String id;
  final String name;
  final WorkItemKind kind;
  final DateTime modifiedAt;
  final bool simulated;
}

abstract class WorkItemSource extends ChangeNotifier {
  List<WorkItem> get items;
  List<WorkDocument> get documents;
  bool get isSimulated;

  /// Creates a new piece of work from a template/request. Returns the id.
  String create({required String title, required WorkItemKind kind});

  /// Structured decisions only. Typed text never approves.
  void approve(String id);
  void cancel(String id);
}

/// Scripted office-work lifecycle so the Workspace, Dashboard and Orb
/// have something truthful-about-being-fake to show without a server:
/// queued -> working (progress ticks) -> awaiting approval -> completed.
///
/// Drives a [MockCompanionSource] so the orb mirrors the work: working
/// while an item progresses, awaitingApproval while one waits, success
/// briefly after approval.
class MockWorkSimulator extends WorkItemSource {
  MockWorkSimulator({
    MockCompanionSource? companion,
    this.stepInterval = const Duration(milliseconds: 420),
    this.successHold = const Duration(seconds: 3),
    DateTime Function()? clock,
    bool seed = true,
  })  : companion = companion ?? MockCompanionSource(),
        _clock = clock ?? DateTime.now {
    if (seed) _seed();
  }

  final MockCompanionSource companion;
  final Duration stepInterval;
  final Duration successHold;
  final DateTime Function() _clock;
  final List<WorkItem> _items = [];
  final List<WorkDocument> _documents = [];
  final Map<String, Timer> _timers = {};
  Timer? _successTimer;
  int _counter = 0;

  @override
  bool get isSimulated => true;

  @override
  List<WorkItem> get items => List.unmodifiable(_items);

  @override
  List<WorkDocument> get documents => List.unmodifiable(_documents);

  WorkItem? get active => _items.cast<WorkItem?>().firstWhere(
        (i) => i!.state == WorkItemState.working || i.state == WorkItemState.queued,
        orElse: () => null,
      );

  WorkItem? get awaiting => _items.cast<WorkItem?>().firstWhere(
        (i) => i!.state == WorkItemState.awaitingApproval,
        orElse: () => null,
      );

  void _seed() {
    final now = _clock();
    _documents.addAll([
      WorkDocument(
          id: 'doc-1',
          name: 'Tender reply, Gangtok office.docx',
          kind: WorkItemKind.letter,
          modifiedAt: now.subtract(const Duration(hours: 3))),
      WorkDocument(
          id: 'doc-2',
          name: 'Q3 expenses.xlsx',
          kind: WorkItemKind.spreadsheet,
          modifiedAt: now.subtract(const Duration(days: 1))),
      WorkDocument(
          id: 'doc-3',
          name: 'Vendor comparison notes.md',
          kind: WorkItemKind.document,
          modifiedAt: now.subtract(const Duration(days: 2))),
    ]);
    _items.add(WorkItem(
      id: 'w-seed-1',
      title: 'Summarise unread supplier emails',
      kind: WorkItemKind.email,
      state: WorkItemState.completed,
      createdAt: now.subtract(const Duration(minutes: 40)),
      outputName: 'Supplier summary.md',
      detail: 'Completed 40 minutes ago',
    ));
  }

  @override
  String create({required String title, required WorkItemKind kind}) {
    final id = 'w-${++_counter}';
    _items.insert(
      0,
      WorkItem(
        id: id,
        title: title,
        kind: kind,
        state: WorkItemState.queued,
        createdAt: _clock(),
        progress: 0,
        detail: 'Queued',
      ),
    );
    notifyListeners();
    _schedule(id, () => _startWorking(id));
    return id;
  }

  void _schedule(String id, void Function() fn) {
    _timers[id]?.cancel();
    _timers[id] = Timer(stepInterval, fn);
  }

  void _update(String id, WorkItem Function(WorkItem) f) {
    final i = _items.indexWhere((w) => w.id == id);
    if (i < 0) return;
    _items[i] = f(_items[i]);
    notifyListeners();
  }

  WorkItem? _get(String id) {
    final i = _items.indexWhere((w) => w.id == id);
    return i < 0 ? null : _items[i];
  }

  void _startWorking(String id) {
    final item = _get(id);
    if (item == null || item.state != WorkItemState.queued) return;
    _update(id, (w) => w.copyWith(
          state: WorkItemState.working,
          progress: 0.05,
          detail: 'Drafting ${w.kind.name}',
        ));
    _pushCompanion();
    _schedule(id, () => _tick(id));
  }

  void _tick(String id) {
    final item = _get(id);
    if (item == null || item.state != WorkItemState.working) return;
    final next = ((item.progress ?? 0) + 0.23).clamp(0.0, 1.0);
    if (next >= 1.0) {
      _update(id, (w) => w.copyWith(
            state: WorkItemState.awaitingApproval,
            progress: 1,
            detail: 'Draft ready',
            approvalSummary: 'Save "${_outputNameFor(w)}" to your documents',
          ));
      _pushCompanion();
      return;
    }
    _update(id, (w) => w.copyWith(progress: next));
    _pushCompanion();
    _schedule(id, () => _tick(id));
  }

  String _outputNameFor(WorkItem w) {
    final ext = switch (w.kind) {
      WorkItemKind.letter || WorkItemKind.document => 'docx',
      WorkItemKind.spreadsheet => 'xlsx',
      WorkItemKind.email => 'eml',
      WorkItemKind.research || WorkItemKind.other => 'md',
    };
    return '${w.title}.$ext';
  }

  @override
  void approve(String id) {
    final item = _get(id);
    if (item == null || item.state != WorkItemState.awaitingApproval) return;
    final name = _outputNameFor(item);
    _update(id, (w) => w.copyWith(
          state: WorkItemState.completed,
          detail: 'Saved',
          outputName: name,
        ));
    _documents.insert(
      0,
      WorkDocument(id: 'doc-$id', name: name, kind: item.kind, modifiedAt: _clock()),
    );
    companion.emit(CompanionState.success, detail: 'Saved $name');
    _successTimer?.cancel();
    _successTimer = Timer(successHold, _pushCompanion);
    notifyListeners();
  }

  @override
  void cancel(String id) {
    final item = _get(id);
    if (item == null || item.state.isTerminal) return;
    _timers.remove(id)?.cancel();
    _update(id, (w) => w.copyWith(state: WorkItemState.cancelled, detail: 'Cancelled'));
    _pushCompanion();
  }

  /// Derive the orb signal from the work list, by priority.
  void _pushCompanion() {
    if (_successTimer?.isActive ?? false) return; // let the bloom finish
    final waiting = awaiting;
    if (waiting != null) {
      companion.emit(CompanionState.awaitingApproval, detail: waiting.approvalSummary);
      return;
    }
    final running = active;
    if (running != null) {
      companion.emit(
        CompanionState.working,
        detail: running.detail ?? running.title,
        progress: running.progress,
      );
      return;
    }
    companion.clear();
  }

  @override
  void dispose() {
    for (final t in _timers.values) {
      t.cancel();
    }
    _timers.clear();
    _successTimer?.cancel();
    super.dispose();
  }
}
