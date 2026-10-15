import 'package:flutter/foundation.dart';

import 'office_bridge.dart';

/// One line of the Office region's conversation, with the target it was about (plan §4.5, U5).
class OfficeLine {
  const OfficeLine(this.speaker, this.text, this.target, {this.chips = const []});
  final OfficeSpeaker speaker;
  final String text;

  /// What the line was about, for the label shown with it: "Home", "Sheet · budget.xlsx", "PDF · notice.pdf".
  final String target;

  /// Follow-up or clarification chips: (label, intent id). At most four.
  final List<(String, String)> chips;
}

/// The Office region's one conversation store (plan §4.3 `office_conversation.dart`). It keeps every line across
/// Home, sheet and document views for the app session. It is never written to disk and holds no document content:
/// only what the owner typed or said and URI's fixed replies. Sheet lines arrive from the sheet controller through
/// `OfficeController.onTurn`.
class OfficeConversation extends ChangeNotifier {
  static const int cap = 200;
  final List<OfficeLine> _lines = [];
  final Set<String> _dismissedChips = {};

  List<OfficeLine> get lines => List.unmodifiable(_lines);

  /// The last [n] owner lines as plain text (sent with a request; plan §4.5).
  List<String> ownerTurns([int n = 6]) {
    final out = [for (final l in _lines) if (l.speaker == OfficeSpeaker.owner) l.text];
    return out.length > n ? out.sublist(out.length - n) : out;
  }

  void add(OfficeLine line) {
    _lines.add(line);
    if (_lines.length > cap) _lines.removeRange(0, _lines.length - cap);
    notifyListeners();
  }

  void say(OfficeSpeaker who, String text, String target, {List<(String, String)> chips = const []}) =>
      add(OfficeLine(who, text, target, chips: chips.take(4).toList()));

  /// U17: a dismissed chip does not come back for that output.
  bool chipDismissed(String key) => _dismissedChips.contains(key);
  void dismissChip(String key) {
    _dismissedChips.add(key);
    notifyListeners();
  }
}
