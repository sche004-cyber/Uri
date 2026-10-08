import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../services/app_state_scope.dart';
import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../living_scope.dart';
import '../presentation/presentation_controller.dart';
import 'glass_panel.dart';

/// The living UI's composer.
///
/// Why not reuse [UriCommandDock] directly: the Hybrid dock sends every
/// submission straight to `AppState.ask`, and this phase needs one
/// interception point for the local presentation commands ("URI
/// dashboard"). Everything that touches the conversation still goes
/// through the same `AppState.ask` (draft, attachments, model override),
/// so Compact/Workspace guarantees are unchanged; the only new behaviour
/// is: a recognised command moves the presentation and is never sent as
/// chat.
class LivingComposer extends StatefulWidget {
  const LivingComposer({
    super.key,
    this.filePicker,
    this.compact = false,
    this.autofocus = false,
    this.hint = 'Ask URI, or say "URI dashboard"',
  });

  final FilePickerFn? filePicker;
  final bool compact;
  final bool autofocus;
  final String hint;

  @override
  State<LivingComposer> createState() => _LivingComposerState();
}

class _LivingComposerState extends State<LivingComposer> {
  late final TextEditingController _controller;
  final _focus = FocusNode();

  @override
  void initState() {
    super.initState();
    // initState may not register an inherited dependency; read without one.
    final appState = context.getInheritedWidgetOfExactType<AppStateScope>()!.notifier!;
    _controller = TextEditingController(text: appState.composerDraft);
  }

  @override
  void dispose() {
    _controller.dispose();
    _focus.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    final text = _controller.text.trim();
    if (text.isEmpty) return;
    final services = LivingScope.of(context);
    final appState = AppStateScope.of(context);
    final command = parseLocalUiCommand(text);
    if (command != null) {
      services.presentation.apply(command);
      _controller.clear();
      appState.clearComposerDraft();
      return;
    }
    if (appState.isSendingAsk) return;
    _controller.clear();
    if (services.presentation.mode == UiPresentationMode.companion) {
      // A real question from Companion mode opens the conversation so
      // the answer has room; the orb travels with it.
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.conversation,
      );
    }
    await appState.ask(text);
  }

  @override
  Widget build(BuildContext context) {
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    return ListenableBuilder(
      listenable: appState,
      builder: (context, _) {
        final sending = appState.isSendingAsk;
        return GlassPanel(
          strong: true,
          padding: EdgeInsets.symmetric(
            horizontal: widget.compact ? 10 : 14,
            vertical: widget.compact ? 4 : 6,
          ),
          radius: UriRadius.lg,
          child: Row(
            children: [
              if (widget.filePicker != null)
                IconButton(
                  tooltip: 'Attach a file',
                  icon: const Icon(Icons.attach_file_rounded, size: 18),
                  color: c.inkSoft,
                  onPressed: () async {
                    final picked = await widget.filePicker!();
                    if (picked == null || !context.mounted) return;
                    await appState.attachFile(
                      filename: picked.name,
                      bytes: picked.bytes,
                    );
                  },
                ),
              Expanded(
                child: CallbackShortcuts(
                  bindings: {
                    const SingleActivator(LogicalKeyboardKey.enter): _submit,
                  },
                  child: TextField(
                    key: const ValueKey('living-composer-field'),
                    controller: _controller,
                    focusNode: _focus,
                    autofocus: widget.autofocus,
                    minLines: 1,
                    maxLines: widget.compact ? 3 : 5,
                    onChanged: appState.setComposerDraft,
                    style: TextStyle(color: c.ink, fontSize: 14),
                    decoration: InputDecoration(
                      hintText: widget.hint,
                      hintStyle: TextStyle(color: c.inkFaint),
                      filled: false,
                      border: InputBorder.none,
                      enabledBorder: InputBorder.none,
                      focusedBorder: InputBorder.none,
                      contentPadding: const EdgeInsets.symmetric(vertical: 10),
                    ),
                  ),
                ),
              ),
              const SizedBox(width: 6),
              Tooltip(
                message: sending ? 'URI is thinking' : 'Send',
                child: Material(
                  color: sending ? glass.fill : glass.glow,
                  shape: const CircleBorder(),
                  child: InkWell(
                    key: const ValueKey('living-composer-send'),
                    customBorder: const CircleBorder(),
                    onTap: sending ? null : _submit,
                    child: SizedBox(
                      width: 34,
                      height: 34,
                      child: Icon(
                        sending ? Icons.more_horiz : Icons.arrow_upward_rounded,
                        size: 18,
                        color: sending ? c.inkFaint : c.canvas,
                      ),
                    ),
                  ),
                ),
              ),
            ],
          ),
        );
      },
    );
  }
}
