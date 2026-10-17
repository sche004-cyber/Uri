// Independent reviews S1/S2 of the URI Office completion candidate: plain words for refusals (S1-03) and document
// wording for Word edits (S1-05). Each expectation failed before its repair.
import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/a2ui/a2ui_hub.dart';
import 'package:uri_ui/living/integration/scheduler_client.dart';
import 'package:uri_ui/living/office/office_controller.dart';
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

  test('save-card refusals in plain words; APPLY_FAILED claims nothing about the file (S1-03, S3-01)', () {
    for (final code in ['STRUCTURE_NOT_SUPPORTED', 'FILE_OPEN_ELSEWHERE', 'CELL_NOT_EDITABLE', 'NOTHING_TO_SAVE',
        'RELOAD_REQUIRED', 'APPLY_FAILED']) {
      final t = A2uiHub.humanRefusal(code, null);
      expect(t.contains(code), isFalse, reason: code);
      expect(t.startsWith('Refused:'), isFalse, reason: code);
    }
    expect(A2uiHub.humanRefusal('APPLY_FAILED', null), isNot(contains('left as it was')));
    expect(A2uiHub.humanRefusal('SOME_SCHEDULER_CODE', 'x'), 'Refused: SOME_SCHEDULER_CODE (x)');   // fallback kept
  });

  test('the sheet pane never shows "Refused: CODE" (S3-02)', () {
    expect(OfficeController.humanRefusal('NOTHING_TO_SAVE', null), 'There are no accepted changes to save.');
    expect(OfficeController.humanRefusal('DESTINATION_EXISTS', null),
        'A file with that name already exists. Nothing was replaced; choose another name.');
    expect(OfficeController.humanRefusal('SOMETHING_NEW', 'the sheet is busy'), 'URI could not do that: the sheet is busy.');
    expect(OfficeController.humanRefusal('SOMETHING_NEW', null), 'URI could not do that here.');
  });
}
