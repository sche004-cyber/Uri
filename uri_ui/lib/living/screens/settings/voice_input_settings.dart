import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../services/live_voice_service.dart';
import '../../../theme/uri_theme.dart';
import '../../companion/companion_preferences.dart';
import '../../voice/voice_interaction.dart';

/// Live voice input settings and diagnostics (Companion Settings, Voice and
/// audio). Every row reports the voice service's own answer: readiness,
/// the microphones it can open, the Windows privacy switch, and the last
/// utterance's measured timings. Nothing here changes a Windows setting;
/// the privacy button only opens Windows Settings for the user.
class VoiceInputSettings extends StatefulWidget {
  const VoiceInputSettings({super.key, required this.controller});
  final VoiceInteractionController controller;

  @override
  State<VoiceInputSettings> createState() => _VoiceInputSettingsState();
}

class _VoiceInputSettingsState extends State<VoiceInputSettings> {
  TextEditingController? _vocabulary;

  @override
  void initState() {
    super.initState();
    // After the first frame: starting the service changes its status, which
    // other widgets listen to, and listeners must not fire during a build.
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted) _check();
    });
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    _vocabulary ??= TextEditingController(
      text: CompanionPreferences.of(context).voice.vocabulary,
    );
  }

  @override
  void dispose() {
    _vocabulary?.dispose();
    super.dispose();
  }

  Future<void> _check() async {
    final s = widget.controller.service;
    if (await s.ensureStarted()) s.refreshDevices();
  }

  @override
  Widget build(BuildContext context) {
    final c = UriColors.of(context);
    final prefs = CompanionPreferences.of(context);
    final ctl = widget.controller;
    final note = TextStyle(fontSize: 12, color: c.inkSoft);
    final label = TextStyle(
      fontSize: 13,
      fontWeight: FontWeight.w600,
      color: c.ink,
    );
    return ListenableBuilder(
      listenable: Listenable.merge([ctl, ctl.service.status, prefs]),
      builder: (context, _) {
        final st = ctl.service.status.value;
        final vp = prefs.voice;
        final statusText = switch (st.state) {
          VoiceServiceState.stopped => 'Not started',
          VoiceServiceState.starting => 'Starting…',
          VoiceServiceState.ready when st.modelLoading =>
            'Ready to listen; the speech model is still loading (the first '
                'transcript waits for it)',
          VoiceServiceState.ready =>
            'Ready: ${st.engine ?? 'local recogniser'} on the CPU'
                '${st.modelLoadMs == null ? '' : ' (model loaded in ${st.modelLoadMs} ms)'}',
          VoiceServiceState.degraded => 'Not usable: ${st.problem}',
          VoiceServiceState.unavailable => 'Unavailable: ${st.problem}',
        };
        final last = ctl.lastFinal;
        final timing = ctl.timings.isEmpty ? null : ctl.timings.last;
        return Column(
          key: const ValueKey('voice-input-settings'),
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Voice input', style: label),
            const SizedBox(height: 4),
            Row(
              children: [
                Icon(
                  st.ready
                      ? Icons.check_circle_outline_rounded
                      : Icons.error_outline_rounded,
                  size: 16,
                  color: st.ready ? c.success : c.warning,
                ),
                const SizedBox(width: 6),
                Expanded(
                  child: Text(
                    statusText,
                    key: const ValueKey('voice-input-status'),
                    style: note,
                  ),
                ),
                TextButton(
                  key: const ValueKey('voice-input-check'),
                  onPressed: _check,
                  child: const Text('Check again'),
                ),
              ],
            ),
            if (st.problemCode == 'MIC_DENIED')
              Align(
                alignment: Alignment.centerLeft,
                child: OutlinedButton.icon(
                  key: const ValueKey('voice-open-privacy'),
                  icon: const Icon(Icons.open_in_new_rounded, size: 16),
                  label: const Text('Open Windows microphone settings'),
                  onPressed: () =>
                      launchUrl(Uri.parse('ms-settings:privacy-microphone')),
                ),
              ),
            const SizedBox(height: 8),
            Row(
              children: [
                Expanded(child: Text('Microphone', style: note)),
                DropdownButton<String?>(
                  key: const ValueKey('voice-microphone'),
                  value: st.inputs.any((d) => d.name == vp.microphone)
                      ? vp.microphone
                      : null,
                  items: [
                    DropdownMenuItem<String?>(
                      value: null,
                      child: Text(
                        'Windows default'
                        '${st.inputs.where((d) => d.isDefault).map((d) => ' (${d.name})').firstOrNull ?? ''}',
                      ),
                    ),
                    for (final d in st.inputs)
                      DropdownMenuItem<String?>(
                        value: d.name,
                        child: Text(d.name),
                      ),
                  ],
                  onChanged: (v) => prefs.setVoice(vp.copyWith(microphone: v)),
                ),
              ],
            ),
            if (vp.microphone != null &&
                st.inputs.isNotEmpty &&
                !st.inputs.any((d) => d.name == vp.microphone))
              Text(
                'The chosen microphone (${vp.microphone}) is not connected; '
                'the Windows default is used until it is.',
                style: TextStyle(fontSize: 12, color: c.warning),
              ),
            const SizedBox(height: 8),
            Text('What spoken words do', style: note),
            const SizedBox(height: 6),
            SegmentedButton<VoiceInputMode>(
              key: const ValueKey('voice-mode'),
              segments: [
                const ButtonSegment(
                  value: VoiceInputMode.conversation,
                  icon: Icon(Icons.forum_outlined, size: 16),
                  label: Text('Conversation'),
                ),
                ButtonSegment(
                  value: VoiceInputMode.drafting,
                  icon: const Icon(Icons.edit_note_rounded, size: 16),
                  label: const Text('Drafting'),
                  enabled: ctl.dictationAvailable,
                ),
              ],
              selected: {
                ctl.dictationAvailable
                    ? vp.inputMode
                    : VoiceInputMode.conversation,
              },
              onSelectionChanged: (s) =>
                  prefs.setVoice(vp.copyWith(inputMode: s.first)),
            ),
            const SizedBox(height: 4),
            Text(
              ctl.dictationAvailable
                  ? (vp.inputMode == VoiceInputMode.drafting
                        ? 'Dictation becomes a draft that URI corrects; it is never sent as a request.'
                        : 'Spoken questions go to URI like typed ones; URI answers aloud.')
                  : 'Drafting by voice needs the Text Intelligence draft desk, which is not in this build.',
              key: const ValueKey('voice-mode-note'),
              style: note,
            ),
            const SizedBox(height: 8),
            TextField(
              key: const ValueKey('voice-vocabulary'),
              controller: _vocabulary,
              maxLength: 400,
              decoration: const InputDecoration(
                labelText: 'Words URI should recognise',
                hintText:
                    'Names, places, terms, e.g. Gangtok Tshering Dussehra',
                isDense: true,
              ),
              onChanged: (v) =>
                  prefs.setVoice(prefs.voice.copyWith(vocabulary: v)),
            ),
            Text(
              "Spoken names in this list are recognised more reliably. URI's own name is always expected.",
              style: note,
            ),
            SwitchListTile(
              key: const ValueKey('voice-speak-replies'),
              contentPadding: EdgeInsets.zero,
              dense: true,
              title: const Text('Speak replies'),
              subtitle: const Text(
                'URI reads its answer to a spoken question aloud, sentence by sentence.',
              ),
              value: vp.speakReplies,
              onChanged: (v) => prefs.setVoice(vp.copyWith(speakReplies: v)),
            ),
            Text(
              'Push to talk: hold the microphone button beside the composer, or hold Ctrl+Space. '
              'A short tap keeps listening until the next tap; Esc cancels. '
              'URI never listens while it speaks, and talking stops its reply.',
              style: note,
            ),
            if (last != null) ...[
              const SizedBox(height: 8),
              Text(
                'Last utterance: ${last.audioMs} ms of audio, '
                'transcribed in ${last.transcribeMs} ms'
                '${timing?['release_to_final_ms'] == null ? '' : ', ${timing!['release_to_final_ms']} ms after release'}'
                '${last.uncertain.isEmpty ? '' : '; unsure about: ${last.uncertain.join(', ')}'}.',
                key: const ValueKey('voice-last-utterance'),
                style: note,
              ),
            ],
            const SizedBox(height: 12),
          ],
        );
      },
    );
  }
}
