import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../services/app_state_scope.dart';
import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../integration/oi_conversation.dart';
import '../living_scope.dart';
import '../office/office_bridge.dart' show OfficeRequestHint;
import '../presentation/presentation_controller.dart';
import '../voice/voice_controls.dart';
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
  ValueNotifier<String?>? _insert;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final insert = LivingScope.of(context).composerInsert;
    if (!identical(insert, _insert)) {
      _insert?.removeListener(_takeInsert);
      _insert = insert..addListener(_takeInsert);
    }
  }

  /// Spoken words that were not sent land here, so they are never lost.
  void _takeInsert() {
    final text = _insert?.value;
    if (text == null || text.isEmpty) return;
    _insert!.value = null;
    final current = _controller.text.trim();
    _controller.text = current.isEmpty ? text : '$current $text';
    _controller.selection = TextSelection.collapsed(
      offset: _controller.text.length,
    );
    AppStateScope.of(context).setComposerDraft(_controller.text);
  }

  @override
  void initState() {
    super.initState();
    // initState may not register an inherited dependency; read without one.
    final appState = context
        .getInheritedWidgetOfExactType<AppStateScope>()!
        .notifier!;
    _controller = TextEditingController(text: appState.composerDraft);
  }

  @override
  void dispose() {
    _insert?.removeListener(_takeInsert);
    _controller.dispose();
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
    final office = services.officeInFocus();
    if (office != null) {
      // Office focus: the request is about the sheet. It only asks URI to suggest changes; accepting and saving stay
      // buttons in the Office pane. With no workbook open nothing is sent (the text stays here).
      if (office.busy || !office.acceptsRequests) return;
      _controller.clear();
      appState.clearComposerDraft();
      await office.instruct(text);
      return;
    }
    final oi = services.oi;
    if (oi != null ? oi.busy : appState.isSendingAsk) return;
    _controller.clear();
    if (services.presentation.mode == UiPresentationMode.companion) {
      // A real question from Companion mode opens the conversation so
      // the answer has room; the orb travels with it.
      services.presentation.setMode(
        UiPresentationMode.workspace,
        focus: WorkspaceFocus.conversation,
      );
    }
    if (oi != null) {
      // Working system: the real Core/OI turn. Text is only ever a turn,
      // never a decision (approvals are buttons on the card).
      appState.clearComposerDraft();
      await oi.send(text);
      return;
    }
    await appState.ask(text);
  }

  @override
  Widget build(BuildContext context) {
    final appState = AppStateScope.of(context);
    final c = UriColors.of(context);
    final glass = UriGlass.of(context);
    final services = LivingScope.of(context);
    final OiConversation? oi = services.oi;
    final voice = services.voiceInteraction;
    return ListenableBuilder(
      listenable: Listenable.merge([
        appState,
        ?oi,
        services.officeTarget,
        ?services.officeTarget.value,
        services.presentation,
      ]),
      builder: (context, _) {
        final office = services.officeInFocus();
        final sending = office != null
            ? office.busy
            : oi != null
                ? oi.busy
                : appState.isSendingAsk;
        return GlassPanel(
          strong: true,
          blur: true,
          padding: EdgeInsets.symmetric(
            horizontal: widget.compact ? 10 : 14,
            vertical: widget.compact ? 4 : 6,
          ),
          radius: UriRadius.lg,
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Row(
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
                  if (oi != null && office == null)
                    IconButton(
                      key: const ValueKey('living-composer-transcript'),
                      tooltip: oi.transcriptMode
                          ? 'Sending as a SIMULATED transcript (no microphone). Tap to type normally.'
                          : 'Send as a simulated speech transcript (testing; no microphone)',
                      isSelected: oi.transcriptMode,
                      icon: const Icon(Icons.record_voice_over_outlined, size: 18),
                      selectedIcon: Icon(Icons.record_voice_over, size: 18, color: c.warning),
                      color: c.inkSoft,
                      onPressed: () => oi.setTranscriptMode(!oi.transcriptMode),
                    ),
                  if (oi != null && office == null)
                    IconButton(
                      key: const ValueKey('living-composer-dictation'),
                      tooltip: oi.dictationMode
                          ? 'Dictation: your words become draft text and nothing in them is carried out. Tap to give instructions again.'
                          : 'Dictate draft text (nothing you dictate is carried out)',
                      isSelected: oi.dictationMode,
                      icon: const Icon(Icons.edit_note_outlined, size: 18),
                      selectedIcon: Icon(Icons.edit_note, size: 18, color: c.warning),
                      color: c.inkSoft,
                      onPressed: () => oi.setDictationMode(!oi.dictationMode),
                    ),
                  Expanded(
                    child: CallbackShortcuts(
                      bindings: {
                        const SingleActivator(LogicalKeyboardKey.enter):
                            _submit,
                      },
                      child: TextField(
                        key: const ValueKey('living-composer-field'),
                        controller: _controller,
                        focusNode: LivingScope.of(context).composerFocus,
                        autofocus: widget.autofocus,
                        minLines: 1,
                        maxLines: widget.compact ? 3 : 5,
                        onChanged: appState.setComposerDraft,
                        style: TextStyle(color: c.ink, fontSize: 14),
                        decoration: InputDecoration(
                          hintText: office is OfficeRequestHint
                              ? (office as OfficeRequestHint).requestHint
                              : office != null
                              ? (office.acceptsRequests ? 'Ask URI to change this sheet' : 'Open a workbook first')
                              : oi != null && oi.dictationMode
                              ? 'Dictation — written as draft text, never carried out'
                              : oi != null && oi.transcriptMode
                                  ? 'Type what was said — sent as a SIMULATED transcript'
                                  : widget.hint,
                          hintStyle: TextStyle(color: c.inkFaint),
                          filled: false,
                          border: InputBorder.none,
                          enabledBorder: InputBorder.none,
                          focusedBorder: InputBorder.none,
                          contentPadding: const EdgeInsets.symmetric(
                            vertical: 10,
                          ),
                        ),
                      ),
                    ),
                  ),
                  if (voice != null) ...[
                    const SizedBox(width: 6),
                    VoiceTalkButton(controller: voice),
                  ],
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
                            sending
                                ? Icons.more_horiz
                                : Icons.arrow_upward_rounded,
                            size: 18,
                            color: sending ? c.inkFaint : c.canvas,
                          ),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
              if (voice != null) VoiceNoticeLine(controller: voice),
            ],
          ),
        );
      },
    );
  }
}
