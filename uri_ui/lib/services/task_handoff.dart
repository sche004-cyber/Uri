/// Phase 2 closure (C6 owner decision 2, the part that needs no owner decision):
/// the conversation-to-task HANDOFF value.
///
/// A handoff carries the words of a conversation message into the supervised
/// execution screen as an UNSENT DRAFT. It is deliberately inert:
///
///  * it holds text and provenance only, never an executor, an approval, a
///    digest, a ticket or any authority;
///  * opening the supervised screen with a handoff pre-fills the composer and
///    nothing else: no frame is sent, no executor is chosen, no intent is
///    confirmed and nothing is approved. The user still picks the executor,
///    presses Send, confirms the intent and approves the digest-bound card;
///  * the conversation it came from is not moved to the paired runtime.
///
/// Whether Chat itself may OFFER the handoff (a "Make this a supervised task"
/// action on the user's own message) is C6 owner decision 2 and is not wired
/// here. See docs/plans/PHASE2CLOSE_C6_CHAT_INTEGRATION.md.
class TaskHandoff {
  TaskHandoff({
    required String text,
    this.source = 'chat',
    this.conversationSessionId,
    this.messageId,
    DateTime? createdAt,
  })  : text = _bounded(text),
        createdAt = createdAt ?? DateTime.now();

  /// The user's own words, trimmed and bounded. Never the assistant's text:
  /// a reply from URI is not a user instruction.
  final String text;

  /// Where the words came from, for the provenance banner only ('chat', 'voice').
  final String source;

  /// The conversation the words came from, for the user's orientation only. The
  /// supervised screen never reuses it as its own session id.
  final String? conversationSessionId;
  final String? messageId;
  final DateTime createdAt;

  /// Same ceiling as the frozen `/ask` text field (64 KiB of characters).
  static const maxChars = 65536;

  static String _bounded(String text) {
    final t = text.trim();
    return t.length > maxChars ? t.substring(0, maxChars) : t;
  }

  bool get isEmpty => text.isEmpty;

  /// Provenance line shown above the pre-filled composer.
  String get banner => 'Draft from ${source == 'voice' ? 'voice' : 'the conversation'}. '
      'Nothing has been sent: review the words, choose an executor, then press Send.';
}
