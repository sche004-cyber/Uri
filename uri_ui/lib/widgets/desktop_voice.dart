import 'dart:async';
import 'dart:convert';
import 'dart:io';
import 'dart:math';

import 'package:flutter/material.dart';
import 'package:window_manager/window_manager.dart';

import '../services/app_state.dart';
import '../services/voice_event.dart';

/// Opt-in Windows input adapter. No authentication, execution or provider owner.
class DesktopVoice extends StatefulWidget {
  const DesktopVoice({
    super.key,
    required this.script,
    required this.appState,
    required this.child,
  });
  final String script;
  final AppState appState;
  final Widget child;
  @override
  State<DesktopVoice> createState() => _DesktopVoiceState();
}

class _DesktopVoiceState extends State<DesktopVoice> {
  Process? _listener;
  Timer? _timer;
  Directory? _directory;
  bool _muted = false, _polling = false;
  int _sequence = 0;
  String _status = 'Starting voice', _test = '';

  @override
  void initState() {
    super.initState();
    unawaited(_start());
  }

  Future<void> _start() async {
    try {
      final local = Platform.environment['LOCALAPPDATA'];
      if (local == null || !await File(widget.script).exists()) {
        throw const FileSystemException('Voice script unavailable');
      }
      final nonce = List.generate(
        16,
        (_) => Random.secure().nextInt(256),
      ).map((byte) => byte.toRadixString(16).padLeft(2, '0')).join();
      _directory = Directory('$local\\URI\\voice\\$nonce');
      _listener = await Process.start('powershell.exe', [
        '-NoProfile',
        '-WindowStyle',
        'Hidden',
        '-File',
        widget.script,
        '-StateDirectory',
        _directory!.path,
        '-ParentProcessId',
        '$pid',
      ]);
      _listener!.stdout.drain<void>();
      _listener!.stderr.drain<void>();
      unawaited(
        _listener!.exitCode.then((code) {
          if (mounted) {
            setState(() => _status = 'Voice listener stopped ($code)');
          }
          _timer?.cancel();
        }),
      );
      if (!mounted) {
        _listener!.kill();
        return;
      }
      _timer = Timer.periodic(
        const Duration(milliseconds: 400),
        (_) => _poll(),
      );
    } catch (_) {
      if (mounted) {
        setState(
          () => _status =
              'Voice unavailable; check Windows speech and microphone settings',
        );
      }
    }
  }

  Future<void> _poll() async {
    if (_polling || _directory == null) return;
    _polling = true;
    try {
      final statusFile = File('${_directory!.path}\\status.json');
      // The listener creates and ACL-protects the directory before this file.
      if (!await statusFile.exists()) return;
      final now = DateTime.now().millisecondsSinceEpoch;
      final control = File('${_directory!.path}\\control.tmp');
      await control.writeAsString(
        jsonEncode({
          'ready':
              widget.appState.isAuthenticated && !widget.appState.isSendingAsk,
          'muted': _muted,
          'test': _test,
          'timestamp': now,
        }),
      );
      await control.rename('${_directory!.path}\\control.json');
      final event = VoiceEvent.parse(
        jsonDecode(await statusFile.readAsString()),
      );
      if (event == null || !mounted) return;
      final oldSequence = _sequence;
      if (event.sequence <= oldSequence) return;
      _sequence = event.sequence; // consume even when rejected; never replay.
      setState(() => _status = event.state);
      final age = now - event.timestamp;
      if (age < 0 || age > 6000 || _muted) return;
      if (event.kind == 'wake' || event.kind == 'command') {
        await windowManager.restore();
        await windowManager.show();
        await windowManager.focus();
        widget.appState.requestVoiceConversation();
      }
      if (event.mayDispatch(
        now: now,
        lastSequence: oldSequence,
        authenticated: widget.appState.isAuthenticated,
        busy: widget.appState.isSendingAsk,
        muted: _muted,
      )) {
        // Do not block heartbeat while the existing Brain/runtime processes.
        unawaited(_send(event.text));
      }
    } catch (_) {
      // Atomic file replacement may overlap a read; retry on next tick.
    } finally {
      _polling = false;
    }
  }

  Future<void> _send(String text) async {
    try {
      await widget.appState.ask(text);
    } catch (_) {
      if (mounted) {
        setState(() => _status = 'Instruction failed; use Chat to review');
      }
    }
  }

  @override
  void dispose() {
    _timer?.cancel();
    _listener?.kill();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) => Column(
    children: [
      Expanded(child: widget.child),
      Material(
        child: SafeArea(
          top: false,
          child: Padding(
            padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
            child: Row(
              children: [
                Icon(_muted ? Icons.mic_off : Icons.mic_none, size: 18),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    _muted ? 'Microphone muted' : _status,
                    maxLines: 2,
                    overflow: TextOverflow.ellipsis,
                  ),
                ),
                TextButton(
                  onPressed: () => setState(() => _muted = !_muted),
                  child: Text(_muted ? 'Unmute' : 'Mute'),
                ),
                TextButton(
                  onPressed: _muted
                      ? null
                      : () => setState(() {
                          _test = DateTime.now().microsecondsSinceEpoch
                              .toString();
                        }),
                  child: const Text('Test listening'),
                ),
              ],
            ),
          ),
        ),
      ),
    ],
  );
}
