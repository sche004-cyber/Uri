// M33.3-R S12: fixture-backed reference-clarification card model.
//
// Mirrors the frozen S1 contract projection (ClarificationContract +
// template wording) and the S1 ClarificationResponse payload. Options carry
// grounded candidate IDs; a click emits the candidate_id and the
// candidate-set fingerprint, never the display label. Not connected to the
// production clarification core (S13).

enum ClarificationKind { chooseOne, confirmOne, chooseAttribute, freeInputOnly }

ClarificationKind _kindFrom(String value) {
  switch (value) {
    case 'CHOOSE_ONE':
      return ClarificationKind.chooseOne;
    case 'CONFIRM_ONE':
      return ClarificationKind.confirmOne;
    case 'CHOOSE_ATTRIBUTE':
      return ClarificationKind.chooseAttribute;
    case 'FREE_INPUT_ONLY':
      return ClarificationKind.freeInputOnly;
  }
  throw FormatException('unknown clarification kind: $value');
}

String _kindToString(ClarificationKind kind) {
  switch (kind) {
    case ClarificationKind.chooseOne:
      return 'CHOOSE_ONE';
    case ClarificationKind.confirmOne:
      return 'CONFIRM_ONE';
    case ClarificationKind.chooseAttribute:
      return 'CHOOSE_ATTRIBUTE';
    case ClarificationKind.freeInputOnly:
      return 'FREE_INPUT_ONLY';
  }
}

class ClarificationCandidateOption {
  const ClarificationCandidateOption({
    required this.optionKey,
    required this.candidateId,
    required this.label,
    required this.rank,
  });

  factory ClarificationCandidateOption.fromJson(Map<String, dynamic> json) =>
      ClarificationCandidateOption(
        optionKey: json['option_key'] as String? ?? '',
        candidateId: json['candidate_id'] as String? ?? '',
        label: json['label'] as String? ?? '',
        rank: (json['rank'] as num?)?.toInt() ?? 0,
      );

  Map<String, dynamic> toJson() => {
    'option_key': optionKey,
    'candidate_id': candidateId,
    'label': label,
    'rank': rank,
  };

  final String optionKey;
  final String candidateId;
  final String label;
  final int rank;
}

class ClarificationAttributeFilter {
  const ClarificationAttributeFilter({
    required this.optionKey,
    required this.axis,
    required this.value,
    required this.label,
    required this.memberCount,
  });

  factory ClarificationAttributeFilter.fromJson(Map<String, dynamic> json) =>
      ClarificationAttributeFilter(
        optionKey: json['option_key'] as String? ?? '',
        axis: json['axis'] as String? ?? '',
        value: json['value'] as String? ?? '',
        label: json['label'] as String? ?? '',
        memberCount: (json['member_count'] as num?)?.toInt() ?? 0,
      );

  Map<String, dynamic> toJson() => {
    'option_key': optionKey,
    'axis': axis,
    'value': value,
    'label': label,
    'member_count': memberCount,
  };

  final String optionKey;
  final String axis;
  final String value;
  final String label;
  final int memberCount;
}

class ClarificationRequest {
  const ClarificationRequest({
    required this.ambiguityId,
    required this.traceId,
    required this.kind,
    required this.question,
    required this.options,
    required this.attributeAxis,
    required this.attributeFilters,
    required this.overflowCount,
    required this.escapeLabel,
    required this.candidateSetFingerprint,
    this.expiresAt,
  });

  factory ClarificationRequest.fromJson(Map<String, dynamic> json) {
    final rawOptions = (json['options'] as List? ?? const []);
    final options = rawOptions
        .map((o) => ClarificationCandidateOption.fromJson(o as Map<String, dynamic>))
        .toList(growable: false)
      ..sort((a, b) => a.rank.compareTo(b.rank));
    final rawFilters = (json['attribute_filters'] as List? ?? const []);
    final request = ClarificationRequest(
      ambiguityId: json['ambiguity_id'] as String? ?? '',
      traceId: json['trace_id'] as String? ?? '',
      kind: _kindFrom(json['kind'] as String),
      question: json['question'] as String? ?? '',
      options: options,
      attributeAxis: json['attribute_axis'] as String?,
      attributeFilters: rawFilters
          .map((f) => ClarificationAttributeFilter.fromJson(f as Map<String, dynamic>))
          .toList(growable: false),
      overflowCount: (json['overflow_count'] as num?)?.toInt() ?? 0,
      escapeLabel: json['escape_label'] as String? ?? 'None of these / Enter something else',
      candidateSetFingerprint: json['candidate_set_fingerprint'] as String? ?? '',
      expiresAt: json['expires_at'] as String?,
    );
    request._validate();
    return request;
  }

  Map<String, dynamic> toJson() => {
    'ambiguity_id': ambiguityId,
    'trace_id': traceId,
    'kind': _kindToString(kind),
    'question': question,
    'options': options.map((o) => o.toJson()).toList(),
    'attribute_axis': attributeAxis,
    'attribute_filters': attributeFilters.map((f) => f.toJson()).toList(),
    'overflow_count': overflowCount,
    'escape_label': escapeLabel,
    'candidate_set_fingerprint': candidateSetFingerprint,
    if (expiresAt != null) 'expires_at': expiresAt,
  };

  /// Frozen S1 display cap (MAX_OPTIONS).
  static const int maxOptions = 5;

  final String ambiguityId;
  final String traceId;
  final ClarificationKind kind;
  final String question;
  final List<ClarificationCandidateOption> options;
  final String? attributeAxis;
  final List<ClarificationAttributeFilter> attributeFilters;
  final int overflowCount;
  final String escapeLabel;
  final String candidateSetFingerprint;
  final String? expiresAt;

  void _validate() {
    // Fail closed on a malformed card rather than rendering padded or
    // ungrounded choices.
    if (options.length > maxOptions || attributeFilters.length > maxOptions) {
      throw const FormatException('more options than the S1 display cap');
    }
    final keys = <String>{};
    for (final o in options) {
      if (o.candidateId.isEmpty || !o.optionKey.startsWith('s') || !keys.add(o.optionKey)) {
        throw const FormatException('candidate option is not grounded');
      }
    }
    for (final f in attributeFilters) {
      if (!f.optionKey.startsWith('a') || !keys.add(f.optionKey)) {
        throw const FormatException('attribute option is not in the a* namespace');
      }
    }
    final expectsCandidates =
        kind == ClarificationKind.chooseOne || kind == ClarificationKind.confirmOne;
    if (expectsCandidates && options.isEmpty) {
      throw const FormatException('candidate clarification without options');
    }
    if (kind == ClarificationKind.confirmOne && options.length != 1) {
      throw const FormatException('CONFIRM_ONE must carry exactly one option');
    }
    if (kind == ClarificationKind.chooseAttribute &&
        (attributeFilters.isEmpty || options.isNotEmpty)) {
      throw const FormatException('attribute clarification must carry only a* options');
    }
    if (kind == ClarificationKind.freeInputOnly &&
        (options.isNotEmpty || attributeFilters.isNotEmpty)) {
      throw const FormatException('free-input clarification carries no options');
    }
  }
}

enum ClarificationResponseKind { candidate, attribute, freeInput }

/// The typed payload a user action emits (S1 ClarificationResponse fields).
class ClarificationResponsePayload {
  const ClarificationResponsePayload._({
    required this.ambiguityId,
    required this.kind,
    this.candidateId,
    this.optionKey,
    this.candidateSetFingerprint,
    this.text,
  });

  factory ClarificationResponsePayload.candidate(
    ClarificationRequest request,
    ClarificationCandidateOption option,
  ) =>
      ClarificationResponsePayload._(
        ambiguityId: request.ambiguityId,
        kind: ClarificationResponseKind.candidate,
        candidateId: option.candidateId,
        candidateSetFingerprint: request.candidateSetFingerprint,
      );

  factory ClarificationResponsePayload.attribute(
    ClarificationRequest request,
    ClarificationAttributeFilter filter,
  ) =>
      ClarificationResponsePayload._(
        ambiguityId: request.ambiguityId,
        kind: ClarificationResponseKind.attribute,
        optionKey: filter.optionKey,
        candidateSetFingerprint: request.candidateSetFingerprint,
      );

  factory ClarificationResponsePayload.freeInput(ClarificationRequest request, String text) =>
      ClarificationResponsePayload._(
        ambiguityId: request.ambiguityId,
        kind: ClarificationResponseKind.freeInput,
        text: text,
      );

  factory ClarificationResponsePayload.fromJson(Map<String, dynamic> json) {
    final responseKindStr = json['response_kind'] as String? ?? '';
    final ambiguityId = json['ambiguity_id'] as String? ?? '';
    final candidateId = json['candidate_id'] as String?;
    final optionKey = json['option_key'] as String?;
    final fingerprint = json['candidate_set_fingerprint'] as String?;
    final text = json['text'] as String?;

    switch (responseKindStr) {
      case 'CANDIDATE':
        return ClarificationResponsePayload._(
          ambiguityId: ambiguityId,
          kind: ClarificationResponseKind.candidate,
          candidateId: candidateId,
          candidateSetFingerprint: fingerprint,
        );
      case 'ATTRIBUTE':
        return ClarificationResponsePayload._(
          ambiguityId: ambiguityId,
          kind: ClarificationResponseKind.attribute,
          optionKey: optionKey,
          candidateSetFingerprint: fingerprint,
        );
      case 'FREE_INPUT':
      default:
        return ClarificationResponsePayload._(
          ambiguityId: ambiguityId,
          kind: ClarificationResponseKind.freeInput,
          text: text,
        );
    }
  }

  final String ambiguityId;
  final ClarificationResponseKind kind;
  final String? candidateId;
  final String? optionKey;
  final String? candidateSetFingerprint;
  final String? text;

  Map<String, dynamic> toJson() {
    switch (kind) {
      case ClarificationResponseKind.candidate:
        return {
          'ambiguity_id': ambiguityId,
          'response_kind': 'CANDIDATE',
          'candidate_id': candidateId,
          'candidate_set_fingerprint': candidateSetFingerprint,
        };
      case ClarificationResponseKind.attribute:
        return {
          'ambiguity_id': ambiguityId,
          'response_kind': 'ATTRIBUTE',
          'option_key': optionKey,
          'candidate_set_fingerprint': candidateSetFingerprint,
        };
      case ClarificationResponseKind.freeInput:
        return {'ambiguity_id': ambiguityId, 'response_kind': 'FREE_INPUT', 'text': text};
    }
  }
}
