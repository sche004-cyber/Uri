// Independent reviews S1/S2 of the URI Office completion candidate: plain words for refusals (S1-03) and document
// wording for Word edits (S1-05). Each expectation failed before its repair.
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart';
import 'package:uri_ui/living/office/presentation_editor.dart';

void main() {
  test('a Word edit is told about the document, a presentation edit about the presentation (S1-05)', () {
    final e = SchedulerApiError('STALE_CHANGE', null);
    expect(authoringErrorMessage(e, document: true),
        'The document changed after the save card was shown. Save again to review it.');
    expect(authoringErrorMessage(e), 'The presentation changed after the save card was shown. Save again to review it.');
    expect(authoringErrorMessage(SchedulerApiError('SAVE_AS_REQUIRED', null), document: true),
        'Choose where to save the new document (Save as).');
  });
}
