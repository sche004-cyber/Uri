import 'dart:async';

import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../services/app_state.dart';

class GoogleSetupCard extends StatefulWidget {
  const GoogleSetupCard({
    super.key,
    required this.state,
    required this.onConfigure,
    this.openUrl,
  });

  final AppState state;
  final VoidCallback onConfigure;

  /// Opens a URL in the system browser. Injectable for tests; defaults to
  /// url_launcher in external-application mode.
  final Future<bool> Function(Uri uri)? openUrl;

  @override
  State<GoogleSetupCard> createState() => _GoogleSetupCardState();
}

class _GoogleSetupCardState extends State<GoogleSetupCard> {
  Timer? _timer;
  String? _message;
  bool _busy = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _refresh());
  }

  @override
  void dispose() {
    _timer?.cancel();
    super.dispose();
  }

  Future<void> _refresh() async {
    if (_busy) return;
    _busy = true;
    try {
      await widget.state.loadGoogleSetup();
      if (widget.state.googleSetup['pending'] == true && _timer == null) {
        _timer = Timer.periodic(const Duration(seconds: 3), (_) => _refresh());
      } else if (widget.state.googleSetup['pending'] != true) {
        _timer?.cancel();
        _timer = null;
      }
      final steps = widget.state.googleSetup['steps'];
      if (steps is List &&
          steps.any(
            (step) =>
                step is Map &&
                step['id'] == 'signed_in' &&
                step['status'] == 'ready',
          )) {
        await widget.state.loadConnections();
      }
      if (mounted) setState(() => _message = null);
    } catch (error) {
      if (mounted)
        setState(
          () => _message = 'Could not check Google setup. Refresh to retry.',
        );
    } finally {
      _busy = false;
    }
  }

  Future<void> _open(String? url) async {
    final uri = Uri.tryParse(url ?? '');
    if (uri == null ||
        uri.scheme != 'https' ||
        !await (widget.openUrl ??
                (u) => launchUrl(u, mode: LaunchMode.externalApplication))(uri)) {
      if (mounted) setState(() => _message = 'Could not open the Google page.');
    }
  }

  Future<void> _signIn() async {
    try {
      final detail = await widget.state.authorizeConnection('gmail');
      if (widget.state.googleAuthUrl != null) {
        await _open(widget.state.googleAuthUrl);
      } else if (mounted) {
        setState(() => _message = detail);
      }
      await _refresh();
    } catch (_) {
      if (mounted) setState(() => _message = 'Could not start Google sign-in.');
    }
  }

  Future<void> _cancel() async {
    try {
      await widget.state.cancelGoogleSignIn();
      await _refresh();
    } catch (_) {
      if (mounted)
        setState(() => _message = 'Could not cancel Google sign-in.');
    }
  }

  @override
  Widget build(BuildContext context) {
    final setup = widget.state.googleSetup;
    final steps = (setup['steps'] as List?) ?? const [];
    final actionSteps = steps.whereType<Map>().where(
      (step) => step['status'] == 'action_required',
    );
    final next = actionSteps.isEmpty ? null : actionSteps.first;
    final pending = setup['pending'] == true;
    final authUrl = widget.state.googleAuthUrl;
    return Card(
      margin: const EdgeInsets.only(bottom: 16),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(
              'Set up Google',
              style: Theme.of(context).textTheme.titleMedium,
            ),
            const SizedBox(height: 8),
            for (final raw in steps)
              if (raw is Map)
                ListTile(
                  dense: true,
                  contentPadding: EdgeInsets.zero,
                  leading: Icon(
                    raw['status'] == 'ready'
                        ? Icons.check_circle
                        : raw['status'] == 'action_required'
                        ? Icons.error_outline
                        : Icons.help_outline,
                  ),
                  title: Text(_label(raw['id'] as String? ?? '')),
                  subtitle: Text(raw['message'] as String? ?? ''),
                  trailing: TextButton(
                    onPressed: raw['help_url'] is String
                        ? () => _open(raw['help_url'] as String)
                        : null,
                    child: const Text('Help'),
                  ),
                ),
            if (setup['last_error'] is String)
              Text(setup['last_error'] as String),
            if (next != null) Text('Next: ${next['message']}'),
            if (_message != null) Text(_message!),
            Wrap(
              spacing: 8,
              children: [
                FilledButton(
                  onPressed: _signIn,
                  child: const Text('Sign in with Google'),
                ),
                if (pending && authUrl != null)
                  OutlinedButton(
                    onPressed: () => _open(authUrl),
                    child: const Text('Open sign-in page again'),
                  ),
                if (pending)
                  TextButton(
                    onPressed: _cancel,
                    child: const Text('Cancel sign-in'),
                  ),
                TextButton(
                  onPressed: _refresh,
                  child: const Text('Refresh setup'),
                ),
                TextButton(
                  onPressed: widget.onConfigure,
                  child: const Text('Configure Credentials'),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  String _label(String id) => switch (id) {
    'client_secret' => 'Google OAuth credentials',
    'signed_in' => 'Google sign-in',
    'gmail_api' => 'Gmail API',
    'drive_api' => 'Drive API',
    'sheets_api' => 'Sheets API (optional)',
    'docs_api' => 'Docs API (optional)',
    'slides_api' => 'Slides API (optional)',
    'forms_api' => 'Forms API (optional)',
    _ => id,
  };
}
