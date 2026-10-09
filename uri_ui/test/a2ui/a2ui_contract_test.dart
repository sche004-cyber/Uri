import 'dart:convert';
import 'dart:io';
import 'dart:typed_data';

import 'package:flutter_test/flutter_test.dart';
import 'package:uri_ui/living/a2ui/a2ui_contract.dart';
import 'package:uri_ui/living/a2ui/sha256.dart';

/// A-AC1: the renderer's validator agrees with the producer's on every shared
/// case (`tests/a2ui/fixtures/contract_cases.json`, written by the Python
/// validator).
void main() {
  final cases = jsonDecode(
    File('../tests/a2ui/fixtures/contract_cases.json').readAsStringSync(),
  ) as List;

  test('shared contract cases: same first error code as Python', () {
    expect(cases.length, greaterThanOrEqualTo(39));
    final mismatches = <String>[];
    for (final c in cases.cast<Map>()) {
      final errs = <A2uiError>[];
      for (final m in c['messages'] as List) {
        errs.addAll(validateMessage(m, jsonEncode));
      }
      final got = errs.isEmpty ? 'valid' : errs.first.code;
      if (got != c['expect']) {
        mismatches.add('${c['name']}: got $got want ${c['expect']}');
      }
    }
    expect(mismatches, isEmpty);
  });

  test('the real scheduler surfaces validate in the renderer', () {
    final s = jsonDecode(
      File('../tests/a2ui/fixtures/surfaces.json').readAsStringSync(),
    ) as Map;
    for (final key in ['proposal', 'revised', 'calendar']) {
      for (final m in (s[key] as Map)['messages'] as List) {
        expect(validateMessage(m, jsonEncode), isEmpty, reason: key);
      }
    }
  });

  test('typed context values', () {
    expect(a2uiTyped('time', '09:30'), isTrue);
    expect(a2uiTyped('time', '24:00'), isFalse);
    expect(a2uiTyped('keys', ['diwali', 'holi']), isTrue);
    expect(a2uiTyped('keys', ['../x']), isFalse);
    expect(a2uiTyped('enum:1|2|3|5|7', '2'), isTrue);
    expect(a2uiTyped('enum:1|2|3|5|7', '30'), isFalse);
    expect(a2uiTyped('date?', ''), isTrue);
    expect(a2uiTyped('str', ''), isFalse);
  });

  test('sha256 matches the standard vectors', () {
    expect(
      sha256Hex(Uint8List(0)),
      'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855',
    );
    expect(
      sha256Hex(Uint8List.fromList(utf8.encode('abc'))),
      'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad',
    );
    expect(
      sha256Hex(
        Uint8List.fromList(
          utf8.encode(
            'abcdbcdecdefdefgefghfghighijhijkijkljklmklmnlmnomnopnopq',
          ),
        ),
      ),
      '248d6a61d20638b8e5c026930c3e6039a33ce45964ff2167f6ecedd419db06c1',
    );
    final million = Uint8List(1000000)..fillRange(0, 1000000, 0x61);
    expect(
      sha256Hex(million),
      'cdc76e5c9914fb9281a1c7e284d73e67f1809a48a497200e046d39ccc7112cd0',
    );
  });
}
