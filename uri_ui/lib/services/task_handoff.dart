/// Phase 2 conversation-to-task HANDOFF value (C6 owner decision 2: Option B,
/// accepted by the owner 2026-10-08).
///
/// A handoff carries the words of the user's OWN conversation message into the
/// supervised execution screen as an UNSENT DRAFT. It is deliberately inert:
///
///  * it holds text and provenance only, never an executor, an approval, a
///    digest, a ticket or any authority;
///  * opening the supervised screen with a handoff pre-fills the composer and
///    nothing else: no frame is sent, no executor is chosen, no intent is
///    confirmed and nothing is approved. The user still picks the executor,
///    presses Send, confirms the intent and approves the digest-bound card;
///  * the conversation it came from is not moved to the paired runtime, and the
///    conversation turn is untouched (its own approval, if any, stays there);
///  * it lives in memory only: an app restart never resurrects a draft.
///
/// See docs/plans/PHASE2CLOSE_C6_CHAT_INTEGRATION.md.
class TaskHandoff {
  TaskHandoff({
    required String text,
    this.source = 'chat',
    this.conversationSessionId,
    this.messageId,
    DateTime? createdAt,
  })  : original = text,
        text = text.trim(),
        createdAt = createdAt ?? DateTime.now();

  /// Exactly what the user wrote.
  final String original;

  /// The user's own words with surrounding whitespace removed. Never the
  /// assistant's text: a reply from URI is not a user instruction. Never cut:
  /// a message over [maxChars] is refused as a whole ([tooLong]), not shortened.
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

  bool get isEmpty => text.isEmpty;

  /// Longer than the worker accepts: the whole handoff is refused, nothing is
  /// silently truncated (the user's words are never altered).
  bool get tooLong => text.length > maxChars;

  /// Usable as a draft: non-empty and within the ceiling.
  bool get usable => !isEmpty && !tooLong;

  String get _origin => source == 'voice' ? 'voice' : 'the conversation';

  /// Provenance line shown above the pre-filled composer.
  String get banner => 'Draft from $_origin. Nothing has been sent and nothing will run '
      'until you approve a proposal here. The conversation turn is separate and unchanged.';

  /// Shown instead of a draft when the message cannot be handed off whole.
  String get refusal => 'This message is too long to hand off (${text.length} characters, '
      'limit $maxChars). Nothing was copied; shorten it here or in the conversation.';
}
