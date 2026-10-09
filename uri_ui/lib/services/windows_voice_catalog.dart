import 'dart:async';
import 'dart:convert';
import 'dart:io' show Platform, Process;
import 'dart:typed_data' show BytesBuilder;

import 'package:flutter/services.dart' show rootBundle;

import '../living/companion/companion_preferences.dart';
import '../living/voice/voice_catalog.dart';

/// [VoiceCatalog] over the speech engines built into Windows.
///
/// Runs the bundled `assets/voice/voice_engine.ps1` in a separate PowerShell
/// process with `-EncodedCommand`; every input (voice name, rate, text)
/// travels in environment variables, never on a command line, so a voice
/// name cannot become script. Listing is read-only. Previews play through
/// the default output device and can be stopped. Nothing is downloaded and
/// no system setting is changed.
class WindowsVoiceCatalog implements VoiceCatalog {
  WindowsVoiceCatalog({this.timeout = const Duration(seconds: 25)});

  static const String scriptAsset = 'assets/voice/voice_engine.ps1';
  static const String sampleText = "Hello. I'm URI, and this is how I sound.";

  final Duration timeout;
  String? _encoded;
  Process? _preview;
  final Set<Process> _stopped = <Process>{};

  Future<String> _command() async {
    if (_encoded != null) return _encoded!;
    final script = await rootBundle.loadString(scriptAsset);
    final units = script.codeUnits; // UTF-16 code units
    final bytes = BytesBuilder();
    for (final u in units) {
      bytes.add([u & 0xFF, u >> 8]);
    }
    return _encoded = base64.encode(bytes.toBytes());
  }

  List<String> _args(String encoded) => <String>[
    '-NoProfile',
    '-NonInteractive',
    '-ExecutionPolicy',
    'Bypass',
    '-EncodedCommand',
    encoded,
  ];

  @override
  Future<VoiceListing> list() async {
    if (!Platform.isWindows) {
      return const UnavailableVoiceCatalog().list();
    }
    try {
      final process = await Process.start(
        'powershell.exe',
        _args(await _command()),
        environment: const {'URI_VOICE_VERB': 'list'},
      );
      final out = process.stdout.transform(utf8.decoder).join();
      final err = process.stderr.transform(utf8.decoder).join();
      final code = await process.exitCode.timeout(
        timeout,
        onTimeout: () {
          // A hung engine must not leave a PowerShell behind.
          process.kill();
          return -1;
        },
      );
      if (code == -1) {
        return const VoiceListing(
          voices: <VoiceInfo>[],
          unavailableReason: 'Listing voices timed out.',
        );
      }
      if (code != 0) {
        return VoiceListing(
          voices: const <VoiceInfo>[],
          unavailableReason: 'The Windows speech engines did not respond.',
          engineErrors: [(await err).trim()],
        );
      }
      return parseListing(await out);
    } catch (e) {
      return VoiceListing(
        voices: const <VoiceInfo>[],
        unavailableReason: 'Could not start the speech engine bridge: $e',
      );
    }
  }

  /// Parses the bridge's JSON. Rows it cannot read are skipped, never
  /// invented.
  static VoiceListing parseListing(String json) {
    final voices = <VoiceInfo>[];
    final errors = <String>[];
    Object? data;
    try {
      data = jsonDecode(json.trim());
    } catch (_) {
      return const VoiceListing(
        voices: <VoiceInfo>[],
        unavailableReason: 'The speech engine bridge returned unreadable data.',
      );
    }
    final rows = data is List ? data : (data is Map ? [data] : const []);
    for (final row in rows) {
      if (row is! Map) continue;
      final engine = VoiceEngineInfo.fromKey(row['engine'] as String?);
      final name = row['name'];
      if (engine == null) continue;
      if (row['error'] != null) {
        errors.add('${engine.label}: ${row['error']}');
        continue;
      }
      if (name is! String || name.isEmpty) continue;
      final enabled = row['enabled'] != false;
      voices.add(
        VoiceInfo(
          engine: engine,
          name: name,
          culture: (row['culture'] as String?) ?? '',
          gender: row['gender'] as String?,
          usable: enabled,
          reason: enabled ? null : 'Disabled in Windows speech settings',
          capabilities: VoiceCapabilities.measuredWindows,
        ),
      );
    }
    return VoiceListing(voices: voices, engineErrors: errors);
  }

  @override
  Future<void> preview(VoiceInfo voice, VoicePreferences prefs) async {
    if (!Platform.isWindows) {
      throw const VoicePreviewError('Previews need Windows speech engines.');
    }
    await stopPreview();
    final process = await Process.start(
      'powershell.exe',
      _args(await _command()),
      environment: <String, String>{
        'URI_VOICE_VERB': 'speak',
        'URI_VOICE_ENGINE': voice.engine.key,
        'URI_VOICE_NAME': voice.name,
        'URI_VOICE_RATE': '${prefs.rate}',
        'URI_VOICE_PITCH': '${prefs.pitch}',
        'URI_VOICE_VOLUME': '${prefs.volume}',
        'URI_VOICE_TEXT': sampleText,
      },
    );
    _preview = process;
    final err = StringBuffer();
    final errDone = process.stderr
        .transform(utf8.decoder)
        .listen(err.write)
        .asFuture<void>();
    unawaited(process.stdout.drain<void>());
    final code = await process.exitCode.timeout(
      timeout,
      onTimeout: () {
        process.kill();
        return -1;
      },
    );
    await errDone.catchError((_) {});
    if (identical(_preview, process)) _preview = null;
    final stopped = _stopped.remove(process);
    if (code != 0 && code != -1 && !stopped) {
      final text = err.toString().trim();
      throw VoicePreviewError(
        text.isEmpty
            ? 'The preview failed (exit $code).'
            : text.split('\n').first,
      );
    }
  }

  @override
  Future<void> stopPreview() async {
    final p = _preview;
    _preview = null;
    if (p != null) {
      _stopped.add(p);
      p.kill();
    }
  }
}
