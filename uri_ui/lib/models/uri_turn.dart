import 'attachment.dart';
import 'clarification.dart';

/// Lifecycle stage of a single Ask-URI turn.
///
/// This intentionally mirrors the shape of URI's real runtime contract
/// (see URI_MODEL_RUNTIME_CONTRACT.md): a model may only ever *propose*
/// an action; the runtime decides whether it is authorized and reports
/// execution separately. The UI never collapses "URI understood the
/// request" and "URI did the thing" into a single state.
enum TurnStage {
  understanding,
  proposalReady,
  awaitingApproval,
  awaitingClarification,
  executing,
  completed,
  cancelled,
  failed,

  /// URI understood the request but the service it would need isn't
  /// authorized yet. Distinct from [failed]: nothing went wrong, URI is
  /// just being honest that it can't proceed rather than pretending it
  /// can. See UriTurn.requiredConnectionName / requiredConnectionId.
  needsConnection,
}

/// A risk/impact hint for a proposed action, used only to drive how much
/// visual weight the approval control gets. This is a UI-side display
/// concern, not an authorization decision — the runtime remains the sole
/// authority on whether an action is actually permitted.
enum ActionImpact { routine, notable, sensitive }

/// A concrete, runtime-registered action URI is proposing to take.
///
/// Deliberately does not claim a fixed catalogue name like "Insurance
/// Renewal" — [title] and [description] are generated per-request, the
/// way a real proposal from the model/runtime contract would be.
class ProposedAction {
  const ProposedAction({
    required this.title,
    required this.description,
    required this.targetService,
    required this.impact,
  });

  final String title;
  final String description;
  final String targetService;
  final ActionImpact impact;
}

/// The outcome of an executed (approved) action, as reported back by the
/// runtime — never fabricated or assumed by the UI.
/// M16: one real, retrievable source behind a researched answer —
/// taken verbatim from what the research capability actually returned
/// (see web_search.py), never synthesised by the client.
class ResultSource {
  const ResultSource({required this.title, required this.url});

  final String title;
  final String url;
}

class ActionResult {
  const ActionResult({
    required this.summary,
    this.detail,
    this.sources = const <ResultSource>[],
    this.generatedFile,
    this.generatedFiles = const <Attachment>[],
    this.draftText,
  });

  final String summary;
  final String? detail;

  /// The actual drafted document body (e.g. draft_institutional_note/
  /// order's "note_sheet", generate_document's "content"/
  /// "document_content") - the real text, not the narrative that only
  /// talks about it. Null for any result that isn't a text draft.
  final String? draftText;

  /// Real sources behind this result, when the capability that
  /// produced it returned any (today: web research). Empty for every
  /// other kind of result — never padded.
  final List<ResultSource> sources;

  /// M19: the real file a generation capability (generate_document,
  /// draft_institutional_note/order) actually produced and stored via
  /// the backend's FileStore — tappable to open/verify via the same
  /// mechanism a user-attached file already uses. Null for every
  /// result that produced no file.
  final Attachment? generatedFile;
  final List<Attachment> generatedFiles;

  List<Attachment> get allGeneratedFiles =>
      generatedFiles.isNotEmpty ? generatedFiles : [?generatedFile];
}

/// A tentative reference binding proposed by URI that the user can accept
/// or explicitly change.
class TentativeBinding {
  const TentativeBinding({
    required this.label,
    this.candidateId,
    this.bindingId,
  });

  final String label;
  final String? candidateId;
  final String? bindingId;

  Map<String, dynamic> toJson() => {
    'label': label,
    if (candidateId != null) 'candidate_id': candidateId,
    if (bindingId != null) 'binding_id': bindingId,
  };

  factory TentativeBinding.fromJson(Map<String, dynamic> json) {
    return TentativeBinding(
      label: json['label'] as String? ?? json['text'] as String? ?? '',
      candidateId: json['candidate_id'] as String?,
      bindingId: json['binding_id'] as String?,
    );
  }
}

/// One exchange in the Ask URI conversation: the user's request plus
/// URI's evolving response as it moves through understanding, proposal,
/// approval, and execution.
class UriTurn {
  UriTurn({
    required this.id,
    required this.userText,
    required this.timestamp,
    required this.stage,
    this.understanding,
    this.proposedAction,
    this.result,
    this.failureReason,
    this.requiredConnectionId,
    this.requiredConnectionName,
    this.attachments = const <Attachment>[],
    this.servingProvider,
    this.servingModel,
    this.promptTokens,
    this.evalTokens,
    this.durationSeconds,
    this.modelCallCount,
    this.elapsedSeconds,
    this.clarification,
    this.tentativeBinding,
    this.retryMessage,
  });

  final String id;
  final String userText;
  final DateTime timestamp;
  TurnStage stage;
  String? understanding;
  ProposedAction? proposedAction;
  ActionResult? result;
  String? failureReason;

  /// INT-ARN-1: Clarification payload when [stage] is
  /// [TurnStage.awaitingClarification].
  ClarificationRequest? clarification;

  /// INT-ARN-1: Tentative binding state ("Using X · Change").
  TentativeBinding? tentativeBinding;

  /// INT-ARN-1: Server retry feedback when a previous clarification attempt
  /// was stale, expired, or rejected.
  String? retryMessage;

  /// Whichever attachments were staged in the composer at the moment
  /// this turn was sent — fixed at creation, never mutated afterwards.
  /// This is what makes an attachment "stick" to the message it was
  /// used in (like a WhatsApp chat bubble) rather than to the
  /// conversation as a whole: the backend still keeps the underlying
  /// file scoped to the session for URI to reference in later turns
  /// (see FileStore), but the composer clears once a turn is sent so
  /// the same chip never appears to be staged for a later message too.
  final List<Attachment> attachments;

  /// Set only when [stage] is [TurnStage.needsConnection] — which
  /// connection (by id, for the "connect" action, and by display name,
  /// for the message) URI would need before it could actually propose
  /// anything for this request.
  String? requiredConnectionId;
  String? requiredConnectionName;
  final String? servingProvider;
  final String? servingModel;

  /// Live UX Repair §8: real, measured per-turn metadata only - each is
  /// null (never a fabricated 0 or guess) whenever the serving provider
  /// did not actually report that field (see server.py's `_measured`,
  /// which only unwraps a UsageRecord field when its own recorded
  /// confidence is "KNOWN").
  final int? promptTokens;
  final int? evalTokens;
  final double? durationSeconds;

  /// Desktop recovery: how many model calls the backend made for this turn
  /// (0 for a deterministic turn), and the client-measured time from Send to
  /// the response arriving. Null when unknown, never guessed.
  final int? modelCallCount;
  final double? elapsedSeconds;

  UriTurn copyWith({
    String? userText,
    TurnStage? stage,
    String? understanding,
    ProposedAction? proposedAction,
    ActionResult? result,
    String? failureReason,
    String? requiredConnectionId,
    String? requiredConnectionName,
    List<Attachment>? attachments,
    String? servingProvider,
    String? servingModel,
    int? promptTokens,
    int? evalTokens,
    double? durationSeconds,
    int? modelCallCount,
    double? elapsedSeconds,
    ClarificationRequest? clarification,
    TentativeBinding? tentativeBinding,
    String? retryMessage,
  }) {
    return UriTurn(
      id: id,
      userText: userText ?? this.userText,
      timestamp: timestamp,
      stage: stage ?? this.stage,
      understanding: understanding ?? this.understanding,
      proposedAction: proposedAction ?? this.proposedAction,
      result: result ?? this.result,
      failureReason: failureReason ?? this.failureReason,
      requiredConnectionId: requiredConnectionId ?? this.requiredConnectionId,
      requiredConnectionName:
          requiredConnectionName ?? this.requiredConnectionName,
      attachments: attachments ?? this.attachments,
      servingProvider: servingProvider ?? this.servingProvider,
      servingModel: servingModel ?? this.servingModel,
      promptTokens: promptTokens ?? this.promptTokens,
      evalTokens: evalTokens ?? this.evalTokens,
      durationSeconds: durationSeconds ?? this.durationSeconds,
      modelCallCount: modelCallCount ?? this.modelCallCount,
      elapsedSeconds: elapsedSeconds ?? this.elapsedSeconds,
      clarification: clarification ?? this.clarification,
      tentativeBinding: tentativeBinding ?? this.tentativeBinding,
      retryMessage: retryMessage ?? this.retryMessage,
    );
  }

  /// Compact wire/history representation for turn metadata. Rich proposal and
  /// result objects remain parsed by the URI client because their backend
  /// shapes differ by execution stage.
  Map<String, dynamic> toJson() => {
    'id': id,
    'user_text': userText,
    'timestamp': timestamp.toIso8601String(),
    'stage': stage.name,
    'understanding': understanding,
    'failure_reason': failureReason,
    'serving_provider': servingProvider,
    'serving_model': servingModel,
    'serving_prompt_tokens': promptTokens,
    'serving_eval_tokens': evalTokens,
    'serving_duration_seconds': durationSeconds,
    'serving_call_count': modelCallCount,
    'elapsed_seconds': elapsedSeconds,
    if (clarification != null) 'clarification': clarification!.toJson(),
    if (tentativeBinding != null)
      'tentative_binding': tentativeBinding!.toJson(),
    if (retryMessage != null) 'retry_message': retryMessage,
  };

  factory UriTurn.fromJson(Map<String, dynamic> json) {
    final stageName = json['stage'] as String?;
    final parsedStage = TurnStage.values.where(
      (value) => value.name == stageName,
    );
    final clarificationJson = json['clarification'] as Map<String, dynamic>?;
    final tentativeBindingJson =
        (json['tentative_binding'] ?? json['tentative_choice'])
            as Map<String, dynamic>?;
    return UriTurn(
      id: json['id'] as String? ?? json['turn_id'] as String? ?? '',
      userText: json['user_text'] as String? ?? '',
      timestamp:
          DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.now(),
      stage: parsedStage.isEmpty ? TurnStage.completed : parsedStage.first,
      understanding: json['understanding'] as String?,
      failureReason: json['failure_reason'] as String?,
      servingProvider: json['serving_provider'] as String?,
      servingModel: json['serving_model'] as String?,
      promptTokens: json['serving_prompt_tokens'] as int?,
      evalTokens: json['serving_eval_tokens'] as int?,
      durationSeconds: (json['serving_duration_seconds'] as num?)?.toDouble(),
      modelCallCount: json['serving_call_count'] as int?,
      elapsedSeconds: (json['elapsed_seconds'] as num?)?.toDouble(),
      clarification: clarificationJson != null
          ? ClarificationRequest.fromJson(clarificationJson)
          : null,
      tentativeBinding: tentativeBindingJson != null
          ? TentativeBinding.fromJson(tentativeBindingJson)
          : null,
      retryMessage: json['retry_message'] as String?,
    );
  }
}
