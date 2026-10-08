import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/services/voice_event.dart';

void main() {
  final event = VoiceEvent(
    2,
    10000,
    'command',
    'Draft an office order',
    'Sending',
  );
  bool allowed({
    int now = 10500,
    int last = 1,
    bool auth = true,
    bool busy = false,
    bool muted = false,
  }) => event.mayDispatch(
    now: now,
    lastSequence: last,
    authenticated: auth,
    busy: busy,
    muted: muted,
  );
  test('fresh command passes only once through authenticated idle input', () {
    expect(allowed(), isTrue);
    expect(allowed(last: 2), isFalse);
    expect(allowed(auth: false), isFalse);
    expect(allowed(busy: true), isFalse);
    expect(allowed(muted: true), isFalse);
  });
  test('expired and future events cannot be replayed', () {
    expect(allowed(now: 16001), isFalse);
    expect(allowed(now: 9999), isFalse);
  });
  test('wake and empty text cannot dispatch', () {
    for (final invalid in [
      VoiceEvent(2, 10000, 'wake', 'hello', 'Ready'),
      VoiceEvent(2, 10000, 'command', '  ', 'Ready'),
    ]) {
      expect(
        invalid.mayDispatch(
          now: 10500,
          lastSequence: 1,
          authenticated: true,
          busy: false,
          muted: false,
        ),
        isFalse,
      );
    }
  });
  test('malformed and oversized IPC rejected', () {
    expect(VoiceEvent.parse({'sequence': '2'}), isNull);
    expect(
      VoiceEvent.parse({
        'sequence': 2,
        'timestamp': 10000,
        'kind': 'command',
        'text': 'a' * 8001,
        'state': 'Ready',
      }),
      isNull,
    );
  });
}
