import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../../services/app_state_scope.dart';
import '../../services/file_picker_service.dart';
import '../../theme/glass_theme.dart';
import '../../theme/uri_theme.dart';
import '../integration/brain_quick_controls.dart';
import '../integration/oi_conversation.dart';
import '../living_scope.dart';
import '../office/office_bridge.dart' show OfficeRequestHint;
import '../presentation/presentation_controller.dart';
import '../testing_tools.dart';
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
    this.minimal = false,
    this.floating = false,
    this.hint = 'Ask URI, or say "URI dashboard"',
  });

  final FilePickerFn? filePicker;
  final bool compact;
  final bool autofocus;
  final bool minimal;
  final bool floating;
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
    // UIV2-F1: judged where the user typed, before the mode switch below.
    final draftInView = services.presentation.draftInView;
    if (services.presentation.mode == UiPresentationMode.dashboard ||
        (!services.visualV2 &&
            services.presentation.mode == UiPresentationMode.companion)) {
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
      await oi.send(text, draftInView: draftInView);
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
    // Codex integration review R1-01: the Office controller is claimed after the composer's first build, so the
    // merged listenable is rebuilt whenever the target changes (outer builder) and then also follows that
    // controller's own changes (busy, request hint).
    return ListenableBuilder(
      listenable: services.officeTarget,
      builder: (context, _) => ListenableBuilder(
      listenable: Listenable.merge([
        appState,
        ?oi,
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
        final presentation = LivingScope.of(context).presentation;
        // UIV2-F1: the draft target applies to the conversation, not to an Office request.
        final draft = office == null ? oi?.draft : null;
        final content = Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            // UIV2-F1: while a draft is open the Workspace composer shows where
            // the message goes; one tap switches it to the conversation, where
            // nothing can change the draft.
            if (oi != null && draft != null && !widget.minimal && presentation.draftInView)
              Align(
                alignment: Alignment.centerLeft,
                child: Padding(
                  padding: const EdgeInsets.only(bottom: 4),
                  child: Tooltip(
                    message: oi.draftTarget
                        ? 'Messages are instructions for the open draft. Tap to talk to URI without changing it.'
                        : 'Messages go to the conversation and never change the draft. Tap to edit the draft again.',
                    child: ActionChip(
                      key: const ValueKey('composer-draft-target'),
                      visualDensity: VisualDensity.compact,
                      avatar: Icon(
                        oi.draftTarget ? Icons.edit_note_rounded : Icons.chat_bubble_outline_rounded,
                        size: 16,
                        color: oi.draftTarget ? c.accent : c.inkSoft,
                      ),
                      label: Text(
                        oi.draftTarget ? 'To: ${draft.docType} draft' : 'To: conversation',
                        style: TextStyle(fontSize: 12, color: c.ink),
                      ),
                      onPressed: () => oi.setDraftTarget(!oi.draftTarget),
                    ),
                  ),
                ),
              ),
            // UIV2-F3: the row never overflows while the window shrinks into
            // Companion: optional buttons step aside on narrow widths.
            LayoutBuilder(builder: (context, box) {
            final w = box.maxWidth;
            // an active testing mode keeps its toggle even when narrow, so it can be switched off (C1-06)
            final testing = oi != null && !widget.minimal && UriTestingTools.enabled &&
                (w >= 420 || oi.transcriptMode || oi.dictationMode);
            return Row(
              children: [
                if (widget.filePicker != null && w >= 260)
                  IconButton(
                    tooltip: 'Attach a file',
                    icon: const Icon(Icons.attach_file_rounded, size: 18),
                    color: c.inkSoft,
                    onPressed: () async {
                      final picked = await widget.filePicker!();
                      if (picked == null || !context.mounted) return;
                      if (oi != null && services.officeInFocus() == null && oiImageMime(picked.name) != null) {
                        // BRAIN-QUICK-CONTROLS: on the working system an image goes to the Brain (Vision On). With
                        // the Office pane in focus the attach path is unchanged (review R1-04): an Office request
                        // never carries the conversation's pictures.
                        await attachOiImage(context, oi, picked.name, picked.bytes);
                        return;
                      }
                      await appState.attachFile(
                        filename: picked.name,
                        bytes: picked.bytes,
                      );
                    },
                  ),
                if (testing && office == null)
                  IconButton(
                    key: const ValueKey('living-composer-transcript'),
                    tooltip: oi.transcriptMode
                        ? 'Sending as a SIMULATED transcript (no microphone). Tap to type normally.'
                        : 'Send as a simulated speech transcript (testing; no microphone)',
                    isSelected: oi.transcriptMode,
                    icon: const Icon(
                      Icons.record_voice_over_outlined,
                      size: 18,
                    ),
                    selectedIcon: Icon(
                      Icons.record_voice_over,
                      size: 18,
                      color: c.warning,
                    ),
                    color: c.inkSoft,
                    onPressed: () => oi.setTranscriptMode(!oi.transcriptMode),
                  ),
                if (testing && office == null)
                  IconButton(
                    key: const ValueKey('living-composer-dictation'),
                    tooltip: oi.dictationMode
                        ? 'Dictation: your words become draft text and nothing in them is carried out. Tap to give instructions again.'
                        : 'Dictate draft text (nothing you dictate is carried out)',
                    isSelected: oi.dictationMode,
                    icon: const Icon(Icons.edit_note_outlined, size: 18),
                    selectedIcon: Icon(
                      Icons.edit_note,
                      size: 18,
                      color: c.warning,
                    ),
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
                        isDense: widget.floating,
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
                        filled: widget.floating,
                        fillColor: widget.floating ? c.surfaceSunken : null,
                        border: widget.floating
                            ? OutlineInputBorder(
                                borderRadius: BorderRadius.circular(24),
                                borderSide: BorderSide.none,
                              )
                            : InputBorder.none,
                        enabledBorder: widget.floating
                            ? OutlineInputBorder(
                                borderRadius: BorderRadius.circular(24),
                                borderSide: BorderSide.none,
                              )
                            : InputBorder.none,
                        focusedBorder: widget.floating
                            ? OutlineInputBorder(
                                borderRadius: BorderRadius.circular(24),
                                borderSide: BorderSide(
                                  color: c.accent,
                                  width: 1.5,
                                ),
                              )
                            : UnderlineInputBorder(
                                borderSide: BorderSide(
                                  color: c.accent,
                                  width: 1.5,
                                ),
                              ),
                        contentPadding: EdgeInsets.symmetric(
                          horizontal: widget.floating ? 12 : 0,
                          vertical: widget.floating ? 8 : 10,
                        ),
                      ),
                    ),
                  ),
                ),
                if (voice != null && !widget.minimal && w >= 200) ...[
                  const SizedBox(width: 6),
                  VoiceTalkButton(controller: voice),
                ],
                const SizedBox(width: 6),
                Tooltip(
                  message: sending ? 'URI is thinking' : 'Send',
                  child: Material(
                    color: widget.floating
                        ? Colors.transparent
                        : sending
                        ? glass.fill
                        : glass.glow,
                    shape: const CircleBorder(),
                    child: InkWell(
                      key: const ValueKey('living-composer-send'),
                      customBorder: const CircleBorder(),
                      onTap: sending ? null : _submit,
                      child: SizedBox(
                        width: 44,
                        height: 44,
                        child: Icon(
                          sending
                              ? Icons.more_horiz
                              : widget.floating
                              ? Icons.send_rounded
                              : Icons.arrow_upward_rounded,
                          size: 18,
                          color: sending
                              ? c.inkFaint
                              : widget.floating
                              ? c.accent
                              : c.canvas,
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            );
            }),
            if (voice != null && !widget.minimal)
              VoiceNoticeLine(controller: voice),
          ],
        );
        final padding = EdgeInsets.symmetric(
          horizontal: widget.floating ? 12 : widget.compact ? 10 : 14,
          vertical: widget.compact ? 4 : 6,
        );
        if (widget.floating) {
          return Padding(padding: padding, child: content);
        }
        return GlassPanel(
          borderless: widget.minimal,
          strong: true,
          blur: true,
          padding: padding,
          radius: UriRadius.lg,
          child: content,
        );
      },
      ),
    );
  }
}
