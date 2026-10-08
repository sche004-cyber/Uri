import 'dart:io' show Platform;

import 'package:flutter/material.dart';

import '../models/uri_turn.dart';
import '../screens/tasks/supervised_execution_screen.dart';
import '../services/supervised_runtime.dart';
import '../services/task_handoff.dart';

/// C6 owner decision 2, Option B (accepted by the owner 2026-10-08): on the
/// user's OWN message in Chat, "Make this a supervised task" opens the
/// supervised execution screen with those words as an UNSENT draft.
///
/// Boundaries (each covered by a widget test):
///  * shown only when this installation opted in to the supervised profile,
///    and only for a non-empty user message (never URI's reply);
///  * hidden while the conversation turn itself is still being understood,
///    awaiting its own approval or executing: one request must not be in two
///    approval paths at once;
///  * tapping sends nothing to `/ask` and nothing to the worker; it only
///    navigates with a [TaskHandoff]. Executor choice, Send, confirmation and the
///    digest-bound approval all stay on the supervised screen;
///  * Back returns to the conversation unchanged.
class SupervisedHandoffAction extends StatelessWidget {
  const SupervisedHandoffAction({
    super.key,
    required this.turn,
    this.configured,
    this.runtimeOverride,
    this.conversationSessionId,
  });

  final UriTurn turn;

  /// Tests override the opt-in probe; production checks the manifest + file.
  final bool? configured;
  final SupervisedRuntime? runtimeOverride;
  final String? conversationSessionId;

  static bool? _probe;

  /// The opt-in probe reads two small files; it is evaluated once per process
  /// (the same rule as the Tasks entry: no opt-in, nothing shown).
  static bool get _optedIn =>
      _probe ??= SupervisedWorkerRuntime.optInConfigured(Platform.environment['URI_CLIENT_MANIFEST']);

  static const _inFlight = {TurnStage.understanding, TurnStage.proposalReady, TurnStage.awaitingApproval, TurnStage.executing};

  @override
  Widget build(BuildContext context) {
    final on = configured ?? _optedIn;
    final words = turn.userText;
    if (!on || words.trim().isEmpty || _inFlight.contains(turn.stage)) {
      return SizedBox.shrink(key: Key('chat-handoff-absent-${turn.id}'));
    }
    final handoff = TaskHandoff(text: words, source: 'chat', messageId: turn.id, conversationSessionId: conversationSessionId);
    return Align(
      alignment: Alignment.centerRight,
      child: TextButton.icon(
        key: Key('chat-handoff-${turn.id}'),
        icon: const Icon(Icons.assignment_turned_in_outlined, size: 18),
        label: Text(handoff.tooLong ? 'Too long to make a supervised task' : 'Make this a supervised task'),
        onPressed: handoff.tooLong
            ? null
            : () => SupervisedExecutionEntry.open(context, runtimeOverride: runtimeOverride, draft: handoff),
      ),
    );
  }
}
