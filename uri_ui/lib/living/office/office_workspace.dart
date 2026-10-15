import 'dart:async';

import 'package:flutter/material.dart';
import 'package:flutter/scheduler.dart';
import 'package:flutter/services.dart';

import '../../theme/uri_theme.dart';
import '../living_scope.dart';
import '../presentation/presentation_controller.dart';
import 'document_controller.dart';
import 'office_bridge.dart';
import 'office_client.dart';
import 'office_companion_pane.dart';
import 'office_home.dart';
import 'office_nav_pane.dart';
import 'office_panel.dart';
import 'office_print_view.dart';
import 'office_status_strip.dart';
import 'page_preview.dart';

/// The B1 Office workspace (approved 2026-10-15, docs/design_library/approved/office_workspace_2026-10-15.md):
/// LEFT files, recent work and goal groups; CENTRE the workbench (Home, lists, the Excel sheet, document pages, a
/// task); RIGHT the persistent URI pane. Panes resize between their limits and collapse; below 1280 px the left
/// pane becomes an icon strip, below 1000 px the URI pane becomes a side sheet, below 720 px one view at a time.
class OfficeWorkspace extends StatefulWidget {
  const OfficeWorkspace({super.key, required this.environment, this.clientFactory = OfficeClient.discover});

  final OfficeEnvironment? environment;
  final OfficeClient? Function() clientFactory;

  @override
  State<OfficeWorkspace> createState() => _OfficeWorkspaceState();
}

class _OfficeWorkspaceState extends State<OfficeWorkspace> {
  OfficeWorkspaceController? _c;
  String? _startError;
  bool _starting = false;                      // the app is starting the Office service (first use of Office)
  bool _sheetOpen = false;                     // the sheet view stays mounted offstage once opened (plan §4.2, F13)
  bool _sideSheet = false;                     // < 1000 px: the URI pane as a side sheet
  final _composerFocus = FocusNode(debugLabel: 'office-composer');
  ValueNotifier<OfficeRequestTarget?>? _target;
  bool _scoped = false;

  bool _sheetModeNow = false;                  // the layout's last side-sheet decision, for the keyboard handler

  @override
  void initState() {
    super.initState();
    HardwareKeyboard.instance.addHandler(_onKey);
    unawaited(_start());
  }

  /// Ctrl+Shift+B, Ctrl+Shift+J and Ctrl+K work wherever the keyboard focus is while Office is shown (real-app run
  /// 2026-10-15: they only worked when the focus happened to be inside the workspace, which a click on a button or
  /// the page does not give).
  bool _onKey(KeyEvent e) {
    final c = _c;
    if (c == null || !mounted || e is! KeyDownEvent) return false;
    final kb = HardwareKeyboard.instance;
    if (!kb.isControlPressed || kb.isAltPressed || kb.isMetaPressed) return false;
    if (kb.isShiftPressed && e.logicalKey == LogicalKeyboardKey.keyB) {
      c.toggleLeft();
      return true;
    }
    if (kb.isShiftPressed && e.logicalKey == LogicalKeyboardKey.keyJ) {
      if (_sheetModeNow) {
        setState(() => _sideSheet = !_sideSheet);
      } else {
        c.toggleRight();
      }
      return true;
    }
    if (!kb.isShiftPressed && e.logicalKey == LogicalKeyboardKey.keyK) {
      // In the app the URI pane holds the shared living composer (its focus node is the scope's); in tests and
      // without a scope it is the plain composer (real-app run r2: Ctrl+K focused a node no field used).
      final focus = LivingScope.maybeOf(context)?.composerFocus ?? _composerFocus;
      if (_sheetModeNow && !_sideSheet) {
        setState(() => _sideSheet = true);
        WidgetsBinding.instance.addPostFrameCallback((_) => focus.requestFocus());
      } else {
        if (c.prefs.rightCollapsed) c.toggleRight();
        WidgetsBinding.instance.addPostFrameCallback((_) => focus.requestFocus());
        focus.requestFocus();
      }
      return true;
    }
    return false;
  }

  Future<void> _start() async {
    final services = context.getInheritedWidgetOfExactType<LivingScope>()?.services;
    final kept = services?.officeWorkspace;
    if (kept is OfficeWorkspaceController) {
      setState(() => _c = kept);                // the region was left and is shown again: same state (U5)
      _claim();
      return;
    }
    var client = widget.clientFactory();
    if (client != null && !await client.reachable()) client = null;   // left behind by a service that has ended
    if (!mounted) return;
    final start = widget.environment?.startService;
    if (client == null && start != null) {
      // Office is started on demand: the first visit starts the service (and its engine check) here.
      setState(() {
        _starting = true;
        _startError = null;
      });
      final problem = await start();
      if (problem == null) {
        for (var i = 0; i < 120 && mounted && client == null; i++) {
          final found = widget.clientFactory();
          if (found != null && await found.reachable()) {
            client = found;
          } else {
            await Future<void>.delayed(const Duration(milliseconds: 500));
          }
        }
      }
      if (!mounted) return;
      setState(() => _starting = false);
      if (client == null) {
        setState(() => _startError = problem ??
            'URI Office did not start. Try again. If it keeps failing, close URI and open it again.');
        return;
      }
    }
    if (client == null) {
      setState(() => _startError = 'The URI Office service is not running. Start URI Office, then open this again.');
      return;
    }
    final c = OfficeWorkspaceController(client: client, presentation: services?.presentation,
        environment: widget.environment);
    services?.officeWorkspace = c;
    setState(() => _c = c);
    _claim();
    await c.start();
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final scope = LivingScope.maybeOf(context);
    _scoped = scope != null;
    final t = scope?.officeTarget;
    if (!identical(t, _target)) {
      _release();
      _target = t;
      _claim();
    }
  }

  // UI-NOTIFY-1 (real-app runs r7 and r1b): the target notifier was changed from didChangeDependencies (during build)
  // and from dispose (tree locked), so its listeners were marked dirty at a forbidden time and Flutter raised
  // assertions. A change during those phases now waits for the end of the frame; the identity checks keep a deferred
  // change from undoing a newer claim by another Office view.
  static void _whenSafe(VoidCallback change) {
    final b = SchedulerBinding.instance;
    if (b.schedulerPhase == SchedulerPhase.idle || b.schedulerPhase == SchedulerPhase.postFrameCallbacks) {
      change();
      return;
    }
    b.addPostFrameCallback((_) => change());
    b.ensureVisualUpdate();
  }

  void _claim() {
    final t = _target, c = _c;
    if (c == null || t == null) return;
    _whenSafe(() {
      if (mounted && identical(_target, t) && identical(_c, c)) t.value = c;
    });
  }

  void _release() {
    final t = _target, c = _c;
    if (t == null || c == null) return;
    _whenSafe(() {
      if (identical(t.value, c)) t.value = null;
    });
  }

  @override
  void dispose() {
    HardwareKeyboard.instance.removeHandler(_onKey);
    _release();
    _composerFocus.dispose();
    // The controller is kept in the living scope (documents, workflows and the conversation survive leaving the
    // region). Without a scope (widget tests) it is disposed here.
    if (!_scoped) _c?.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (_starting) {
      return const Center(
        key: ValueKey('office-starting'),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          CircularProgressIndicator(),
          SizedBox(height: 16),
          Text('Starting URI Office…', style: TextStyle(fontWeight: FontWeight.w600)),
          SizedBox(height: 6),
          Text('This takes a few seconds the first time.'),
        ]),
      );
    }
    if (_startError != null) {
      return Center(child: Padding(padding: const EdgeInsets.all(24),
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            Text(_startError!, key: const ValueKey('office-start-error'), textAlign: TextAlign.center),
            if (widget.environment?.startService != null) ...[
              const SizedBox(height: 12),
              FilledButton(key: const ValueKey('office-start-retry'), onPressed: () => unawaited(_start()),
                  child: const Text('Try again')),
            ],
          ])));
    }
    final c = _c;
    if (c == null) return const Center(child: CircularProgressIndicator());
    return ListenableBuilder(
      listenable: Listenable.merge([c, c.hub, c.conversation]),
      builder: (context, _) => LayoutBuilder(builder: (context, box) => _layout(context, c, box.maxWidth)),
    );
  }

  Widget _layout(BuildContext context, OfficeWorkspaceController c, double width) {
    final colors = UriColors.of(context);
    if (c.contractMismatch) {
      return const Center(child: Text('The Office service and the app are different versions; restart URI.',
          key: ValueKey('office-contract-mismatch')));
    }
    final narrow = width < 720;
    final sheetMode = width < 1000;
    final iconStrip = width < 1280 || c.prefs.leftCollapsed;
    final rightHidden = sheetMode || c.prefs.rightCollapsed;
    if (c.centre == OfficeCentre.sheet) _sheetOpen = true;

    final centre = _centre(context, c);
    final left = narrow && c.centre != OfficeCentre.home && c.centre != OfficeCentre.list
        ? null
        : SizedBox(
            width: iconStrip ? 56 : c.prefs.leftWidth,
            child: OfficeNavPane(controller: c, compact: iconStrip, environment: widget.environment,
                onOpenSheet: _openSheet),
          );
    final right = rightHidden || c.centre == OfficeCentre.sheet
        ? null
        : SizedBox(width: c.prefs.rightWidth, child: OfficeCompanionPane(controller: c, composerFocus: _composerFocus));

    final body = Row(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        ?left,
        if (left != null && !iconStrip)
          _ResizeHandle(key: const ValueKey('office-resize-left'), onDrag: (dx) => c.setLeftWidth(c.prefs.leftWidth + dx),
              onEnd: c.saveLayout),
        Expanded(child: centre),
        if (right != null)
          _ResizeHandle(key: const ValueKey('office-resize-right'),
              onDrag: (dx) => c.setRightWidth(c.prefs.rightWidth - dx), onEnd: c.saveLayout),
        ?right,
      ],
    );

    final waiting = c.waitingCards;
    _sheetModeNow = sheetMode;
    return Shortcuts(
      // Ctrl+K, Ctrl+Shift+B and Ctrl+Shift+J are handled by [_onKey] wherever the focus is.
      shortcuts: const {
        SingleActivator(LogicalKeyboardKey.escape): _EscapeIntent(),
      },
      child: Actions(
        actions: {
          _FocusComposerIntent: CallbackAction<_FocusComposerIntent>(onInvoke: (_) {
            _composerFocus.requestFocus();
            return null;
          }),
          _ToggleLeftIntent: CallbackAction<_ToggleLeftIntent>(onInvoke: (_) {
            c.toggleLeft();
            return null;
          }),
          _ToggleRightIntent: CallbackAction<_ToggleRightIntent>(onInvoke: (_) {
            if (sheetMode) {
              setState(() => _sideSheet = !_sideSheet);
            } else {
              c.toggleRight();
            }
            return null;
          }),
          _EscapeIntent: CallbackAction<_EscapeIntent>(onInvoke: (_) {
            if (c.hint != null) c.dismissHint();
            return null;
          }),
        },
        child: Focus(
          autofocus: true,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              _header(context, c, sheetMode, waiting),
              Expanded(
                child: Stack(children: [
                  Positioned.fill(child: body),
                  // The URI pane as a side sheet under 1000 px. It opens by itself when a card needs the owner.
                  if (sheetMode && c.centre != OfficeCentre.sheet && (_sideSheet || waiting > 0))
                    Positioned(
                      top: 0,
                      bottom: 0,
                      right: 0,
                      width: (width * 0.9).clamp(280.0, 420.0),
                      child: Material(
                        key: const ValueKey('office-side-sheet'),
                        elevation: 8,
                        color: colors.canvas,
                        child: OfficeCompanionPane(controller: c, composerFocus: _composerFocus,
                            onClose: () => setState(() => _sideSheet = false)),
                      ),
                    ),
                ]),
              ),
              OfficeStatusStrip(controller: c, wrap: narrow),
            ],
          ),
        ),
      ),
    );
  }

  void _openSheet() {
    _c?.showSheet();
  }

  Widget _header(BuildContext context, OfficeWorkspaceController c, bool sheetMode, int waiting) {
    final colors = UriColors.of(context);
    final canBack = c.centre != OfficeCentre.home;
    return Padding(
      padding: const EdgeInsets.fromLTRB(UriSpace.sm, UriSpace.xs, UriSpace.sm, UriSpace.xs),
      child: Row(children: [
        IconButton(
          key: const ValueKey('office-back'),
          tooltip: 'Back',
          onPressed: canBack ? c.back : null,
          icon: const Icon(Icons.arrow_back_rounded, size: 18),
        ),
        Expanded(
          child: Text(
            _title(c),
            key: const ValueKey('office-view-title'),
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(fontWeight: FontWeight.w600),
          ),
        ),
        if (c.centre == OfficeCentre.document || c.centre == OfficeCentre.sheet) ..._docControls(context, c),
        IconButton(
          key: const ValueKey('office-toggle-left'),
          tooltip: 'Show or hide files (Ctrl+Shift+B)',
          onPressed: c.toggleLeft,
          icon: const Icon(Icons.view_sidebar_outlined, size: 18),
        ),
        Badge(
          isLabelVisible: waiting > 0 && (sheetMode || c.prefs.rightCollapsed),
          label: Text('$waiting', key: const ValueKey('office-waiting-badge')),
          backgroundColor: colors.accent,
          child: IconButton(
            key: const ValueKey('office-toggle-uri'),
            tooltip: 'Show or hide URI (Ctrl+Shift+J)',
            onPressed: () => sheetMode ? setState(() => _sideSheet = !_sideSheet) : c.toggleRight(),
            icon: Icon(Icons.blur_on_rounded, size: 18, color: colors.accent),
          ),
        ),
      ]),
    );
  }

  /// Save as PDF and Print in the document controls (A1 §A3, owner instruction): shown only when the capability is
  /// available; Print stays hidden until O2P qualifies.
  List<Widget> _docControls(BuildContext context, OfficeWorkspaceController c) {
    final d = c.documents[c.activeDocument];
    final convertible = (c.centre == OfficeCentre.sheet && c.sheet?.workbookId != null) ||
        (c.centre == OfficeCentre.document && d != null && d.kind != 'pdf');
    return [
      if (convertible && c.available('save_as_pdf'))
        Tooltip(
          message: c.saveAsPdfBlockedReason ?? 'Make a PDF copy. URI shows a plan first; your file is not changed.',
          child: TextButton.icon(
            key: const ValueKey('office-save-as-pdf'),
            onPressed: c.busy || !c.ready('save_as_pdf') ? null : c.saveAsPdf,
            icon: const Icon(Icons.picture_as_pdf_outlined, size: 18),
            label: const Text('Save as PDF'),
          ),
        ),
      if (c.available('print_document'))
        TextButton.icon(
          key: const ValueKey('office-print'),
          onPressed: c.busy || c.centre == OfficeCentre.sheet ? null : c.startPrint,
          icon: const Icon(Icons.print_outlined, size: 18),
          label: const Text('Print'),
        ),
    ];
  }

  String _title(OfficeWorkspaceController c) => switch (c.centre) {
        OfficeCentre.home => 'Office',
        OfficeCentre.list => switch (c.view) {
            OfficeView.recent => 'Recent',
            OfficeView.documents => 'Documents',
            OfficeView.spreadsheets => 'Spreadsheets',
            OfficeView.presentations => 'Presentations',
            OfficeView.pdfs => 'PDFs',
            OfficeView.templates => 'Templates',
            OfficeView.workflows => 'Tasks',
            OfficeView.home => 'Office',
          },
        OfficeCentre.sheet => 'Spreadsheet',
        OfficeCentre.document => c.documents[c.activeDocument]?.name ?? 'Document',
        OfficeCentre.workflow => 'Task',
        OfficeCentre.print => 'Print',
        OfficeCentre.devices => 'Printers',
      };

  Widget _centre(BuildContext context, OfficeWorkspaceController c) {
    final env = widget.environment;
    final visibleSheet = c.centre == OfficeCentre.sheet;
    return Stack(children: [
      // The sheet stays mounted offstage while another view is shown, so its WebView2, draft and undo stack survive
      // (plan §4.2, AC-O2-17). Offstage widgets get no pointer or keyboard input (AC-O2-21).
      if (_sheetOpen || visibleSheet)
        Offstage(
          offstage: !visibleSheet,
          child: TickerMode(
            enabled: visibleSheet,
            child: ExcludeFocus(
              excluding: !visibleSheet,
              child: OfficeRegion(
                key: const ValueKey('office-sheet-region'),
                environment: env,
                clientFactory: () => c.client,
                hub: c.hub,
                onController: (sc) {
                  c.sheet = sc;
                  sc.addListener(c.sheetChanged);      // the composer hint and Save as PDF follow the sheet
                },
                onTurn: (t) => c.conversation.say(t.speaker, t.text, c.targetLabel),
              ),
            ),
          ),
        ),
      if (!visibleSheet)
        Positioned.fill(
          child: switch (c.centre) {
            OfficeCentre.home => OfficeHome(controller: c, environment: env, onOpenSheet: _openSheet),
            OfficeCentre.list => OfficeFileList(controller: c, environment: env, onOpenSheet: _openSheet),
            OfficeCentre.document => PagePreview(key: ValueKey('office-preview-${c.activeDocument}'), controller: c),
            OfficeCentre.workflow => OfficeWorkflowView(controller: c),
            OfficeCentre.print => OfficePrintView(controller: c),
            OfficeCentre.devices => OfficePrintersView(controller: c),
            OfficeCentre.sheet => const SizedBox.shrink(),
          },
        ),
    ]);
  }
}

class _FocusComposerIntent extends Intent {
  const _FocusComposerIntent();
}

class _ToggleLeftIntent extends Intent {
  const _ToggleLeftIntent();
}

class _ToggleRightIntent extends Intent {
  const _ToggleRightIntent();
}

class _EscapeIntent extends Intent {
  const _EscapeIntent();
}

/// A vertical drag handle between panes (own widget; no new package).
class _ResizeHandle extends StatelessWidget {
  const _ResizeHandle({super.key, required this.onDrag, required this.onEnd});
  final void Function(double dx) onDrag;
  final VoidCallback onEnd;

  @override
  Widget build(BuildContext context) {
    final colors = UriColors.of(context);
    return Semantics(
      label: 'Resize pane',
      child: MouseRegion(
        cursor: SystemMouseCursors.resizeColumn,
        child: GestureDetector(
          behavior: HitTestBehavior.opaque,
          onHorizontalDragUpdate: (d) => onDrag(d.delta.dx),
          onHorizontalDragEnd: (_) => onEnd(),
          child: SizedBox(width: 6, child: Center(child: Container(width: 1, color: colors.border))),
        ),
      ),
    );
  }
}
