/// Voice is input to the authenticated canonical conversation, never approval.
class VoiceEvent {
  VoiceEvent(this.sequence, this.timestamp, this.kind, this.text, this.state);
  final int sequence;
  final int timestamp;
  final String kind;
  final String text;
  final String state;

  static VoiceEvent? parse(Object? value) {
    if (value is! Map<String, dynamic>) return null;
    final sequence = value['sequence'];
    final timestamp = value['timestamp'];
    final kind = value['kind'];
    final text = value['text'];
    final state = value['state'];
    if (sequence is! int ||
        timestamp is! int ||
        kind is! String ||
        text is! String ||
        state is! String ||
        text.length > 8000) {
      return null;
    }
    return VoiceEvent(sequence, timestamp, kind, text, state);
  }

  bool mayDispatch({
    required int now,
    required int lastSequence,
    required bool authenticated,
    required bool busy,
    required bool muted,
  }) {
    final age = now - timestamp;
    return kind == 'command' &&
        text.trim().isNotEmpty &&
        sequence > lastSequence &&
        age >= 0 &&
        age <= 6000 &&
        authenticated &&
        !busy &&
        !muted;
  }
}
