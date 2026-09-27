// Generated from Pydantic v2 contracts. Do not edit by hand.
// dart format off
// Regenerate: uv run python scripts/generate_contracts.py
// ignore_for_file: non_constant_identifier_names, unnecessary_non_null_assertion, prefer_null_aware_operators, use_null_aware_elements

/// Replace the assessment fields at an expected case revision.
class AssessmentCaseRequest {
  const AssessmentCaseRequest({
    required this.revision,
    required this.assessment,
    required this.missing_information,
  });

  final int revision;
  final String assessment;
  final String missing_information;

  factory AssessmentCaseRequest.fromJson(Map<String, dynamic> json) => AssessmentCaseRequest(
    revision: json['revision'] as int,
    assessment: json['assessment'] as String,
    missing_information: json['missing_information'] as String,
  );

  Map<String, dynamic> toJson() => {
    'revision': revision,
    'assessment': assessment,
    'missing_information': missing_information,
  };
}

/// Capture the current committed public sample for an expected revision.
class CaptureCaseEvidenceRequest {
  const CaptureCaseEvidenceRequest({
    required this.revision,
  });

  final int revision;

  factory CaptureCaseEvidenceRequest.fromJson(Map<String, dynamic> json) => CaptureCaseEvidenceRequest(
    revision: json['revision'] as int,
  );

  Map<String, dynamic> toJson() => {
    'revision': revision,
  };
}

/// Append-only audit activity attributed to the authenticated operator.
class CaseActivity {
  const CaseActivity({
    required this.activity_id,
    required this.case_id,
    required this.user_id,
    required this.kind,
    required this.text,
    required this.created_at,
    required this.evidence,
  });

  final String activity_id;
  final String case_id;
  final String user_id;
  final String kind;
  final String text;
  final String created_at;
  final CaseEvidence? evidence;

  factory CaseActivity.fromJson(Map<String, dynamic> json) => CaseActivity(
    activity_id: json['activity_id'] as String,
    case_id: json['case_id'] as String,
    user_id: json['user_id'] as String,
    kind: json['kind'] as String,
    text: json['text'] as String,
    created_at: json['created_at'] as String,
    evidence: json['evidence'] == null ? null : CaseEvidence.fromJson(Map<String, dynamic>.from(json['evidence'] as Map)),
  );

  Map<String, dynamic> toJson() => {
    'activity_id': activity_id,
    'case_id': case_id,
    'user_id': user_id,
    'kind': kind,
    'text': text,
    'created_at': created_at,
    'evidence': evidence == null ? null : evidence!.toJson(),
  };
}

/// Server-captured snapshot of exactly one committed public frame.
class CaseEvidence {
  const CaseEvidence({
    required this.source_id,
    required this.stream_id,
    required this.satellite_id,
    required this.payload_hash,
    required this.sequence,
    required this.observed_at,
    required this.emitted_at,
    required this.committed_at,
    required this.captured_at,
    required this.catalog_version,
    required this.source_kind,
    required this.time_domain,
    required this.readings,
  });

  final String source_id;
  final String stream_id;
  final String satellite_id;
  final String payload_hash;
  final int sequence;
  final String observed_at;
  final String emitted_at;
  final String committed_at;
  final String captured_at;
  final String catalog_version;
  final String source_kind;
  final String time_domain;
  final List<CaseEvidenceReading> readings;

  factory CaseEvidence.fromJson(Map<String, dynamic> json) => CaseEvidence(
    source_id: json['source_id'] as String,
    stream_id: json['stream_id'] as String,
    satellite_id: json['satellite_id'] as String,
    payload_hash: json['payload_hash'] as String,
    sequence: json['sequence'] as int,
    observed_at: json['observed_at'] as String,
    emitted_at: json['emitted_at'] as String,
    committed_at: json['committed_at'] as String,
    captured_at: json['captured_at'] as String,
    catalog_version: json['catalog_version'] as String,
    source_kind: json['source_kind'] as String,
    time_domain: json['time_domain'] as String,
    readings: (json['readings'] as List).map((item) => CaseEvidenceReading.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'source_id': source_id,
    'stream_id': stream_id,
    'satellite_id': satellite_id,
    'payload_hash': payload_hash,
    'sequence': sequence,
    'observed_at': observed_at,
    'emitted_at': emitted_at,
    'committed_at': committed_at,
    'captured_at': captured_at,
    'catalog_version': catalog_version,
    'source_kind': source_kind,
    'time_domain': time_domain,
    'readings': readings.map((item) => item.toJson()).toList(),
  };
}

/// One typed reading rendered from an immutable public channel catalog.
class CaseEvidenceReading {
  const CaseEvidenceReading({
    required this.channel_id,
    required this.value_text,
    required this.quality,
    required this.unit,
  });

  final String channel_id;
  final String value_text;
  final String quality;
  final String unit;

  factory CaseEvidenceReading.fromJson(Map<String, dynamic> json) => CaseEvidenceReading(
    channel_id: json['channel_id'] as String,
    value_text: json['value_text'] as String,
    quality: json['quality'] as String,
    unit: json['unit'] as String,
  );

  Map<String, dynamic> toJson() => {
    'channel_id': channel_id,
    'value_text': value_text,
    'quality': quality,
    'unit': unit,
  };
}

/// Bounded private case list for the authenticated named operator.
class CaseList {
  const CaseList({
    required this.items,
    required this.total,
    required this.has_more,
  });

  final List<CaseSummary> items;
  final int total;
  final bool has_more;

  factory CaseList.fromJson(Map<String, dynamic> json) => CaseList(
    items: (json['items'] as List).map((item) => CaseSummary.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    total: json['total'] as int,
    has_more: json['has_more'] as bool,
  );

  Map<String, dynamic> toJson() => {
    'items': items.map((item) => item.toJson()).toList(),
    'total': total,
    'has_more': has_more,
  };
}

/// Private operator case with revision-controlled workflow state.
class CaseRecord {
  const CaseRecord({
    required this.case_id,
    required this.run_id,
    required this.user_id,
    required this.satellite_id,
    required this.title,
    required this.summary,
    required this.priority,
    required this.status,
    required this.assessment,
    required this.missing_information,
    required this.recommendation,
    required this.expected_effect,
    required this.tradeoffs,
    required this.decision,
    required this.decision_reason,
    required this.outcome,
    required this.outcome_notes,
    required this.revision,
    required this.created_at,
    required this.updated_at,
    required this.evidence,
    required this.activities,
    required this.activity_count,
    required this.activities_truncated,
  });

  final String case_id;
  final String run_id;
  final String user_id;
  final String satellite_id;
  final String title;
  final String summary;
  final String priority;
  final String status;
  final String assessment;
  final String missing_information;
  final String recommendation;
  final String expected_effect;
  final String tradeoffs;
  final String decision;
  final String decision_reason;
  final String outcome;
  final String outcome_notes;
  final int revision;
  final String created_at;
  final String updated_at;
  final CaseEvidence? evidence;
  final List<CaseActivity> activities;
  final int activity_count;
  final bool activities_truncated;

  factory CaseRecord.fromJson(Map<String, dynamic> json) => CaseRecord(
    case_id: json['case_id'] as String,
    run_id: json['run_id'] as String,
    user_id: json['user_id'] as String,
    satellite_id: json['satellite_id'] as String,
    title: json['title'] as String,
    summary: json['summary'] as String,
    priority: json['priority'] as String,
    status: json['status'] as String,
    assessment: json['assessment'] as String,
    missing_information: json['missing_information'] as String,
    recommendation: json['recommendation'] as String,
    expected_effect: json['expected_effect'] as String,
    tradeoffs: json['tradeoffs'] as String,
    decision: json['decision'] as String,
    decision_reason: json['decision_reason'] as String,
    outcome: json['outcome'] as String,
    outcome_notes: json['outcome_notes'] as String,
    revision: json['revision'] as int,
    created_at: json['created_at'] as String,
    updated_at: json['updated_at'] as String,
    evidence: json['evidence'] == null ? null : CaseEvidence.fromJson(Map<String, dynamic>.from(json['evidence'] as Map)),
    activities: (json['activities'] as List).map((item) => CaseActivity.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    activity_count: json['activity_count'] as int,
    activities_truncated: json['activities_truncated'] as bool,
  );

  Map<String, dynamic> toJson() => {
    'case_id': case_id,
    'run_id': run_id,
    'user_id': user_id,
    'satellite_id': satellite_id,
    'title': title,
    'summary': summary,
    'priority': priority,
    'status': status,
    'assessment': assessment,
    'missing_information': missing_information,
    'recommendation': recommendation,
    'expected_effect': expected_effect,
    'tradeoffs': tradeoffs,
    'decision': decision,
    'decision_reason': decision_reason,
    'outcome': outcome,
    'outcome_notes': outcome_notes,
    'revision': revision,
    'created_at': created_at,
    'updated_at': updated_at,
    'evidence': evidence == null ? null : evidence!.toJson(),
    'activities': activities.map((item) => item.toJson()).toList(),
    'activity_count': activity_count,
    'activities_truncated': activities_truncated,
  };
}

/// Lightweight private case projection for bounded historical lists.
class CaseSummary {
  const CaseSummary({
    required this.case_id,
    required this.run_id,
    required this.user_id,
    required this.satellite_id,
    required this.title,
    required this.summary,
    required this.priority,
    required this.status,
    required this.decision,
    required this.outcome,
    required this.revision,
    required this.created_at,
    required this.updated_at,
  });

  final String case_id;
  final String run_id;
  final String user_id;
  final String satellite_id;
  final String title;
  final String summary;
  final String priority;
  final String status;
  final String decision;
  final String outcome;
  final int revision;
  final String created_at;
  final String updated_at;

  factory CaseSummary.fromJson(Map<String, dynamic> json) => CaseSummary(
    case_id: json['case_id'] as String,
    run_id: json['run_id'] as String,
    user_id: json['user_id'] as String,
    satellite_id: json['satellite_id'] as String,
    title: json['title'] as String,
    summary: json['summary'] as String,
    priority: json['priority'] as String,
    status: json['status'] as String,
    decision: json['decision'] as String,
    outcome: json['outcome'] as String,
    revision: json['revision'] as int,
    created_at: json['created_at'] as String,
    updated_at: json['updated_at'] as String,
  );

  Map<String, dynamic> toJson() => {
    'case_id': case_id,
    'run_id': run_id,
    'user_id': user_id,
    'satellite_id': satellite_id,
    'title': title,
    'summary': summary,
    'priority': priority,
    'status': status,
    'decision': decision,
    'outcome': outcome,
    'revision': revision,
    'created_at': created_at,
    'updated_at': updated_at,
  };
}

/// Create an operator case for one satellite in the current owned run.
class CreateCaseRequest {
  const CreateCaseRequest({
    required this.satellite_id,
    required this.title,
    required this.summary,
    required this.priority,
    this.sequence,
  });

  final String satellite_id;
  final String title;
  final String summary;
  final String priority;
  final int? sequence;

  factory CreateCaseRequest.fromJson(Map<String, dynamic> json) => CreateCaseRequest(
    satellite_id: json['satellite_id'] as String,
    title: json['title'] as String,
    summary: json['summary'] as String,
    priority: json['priority'] as String,
    sequence: json['sequence'] == null ? null : json['sequence'] as int,
  );

  Map<String, dynamic> toJson() => {
    'satellite_id': satellite_id,
    'title': title,
    'summary': summary,
    'priority': priority,
    if (sequence != null) 'sequence': sequence == null ? null : sequence!,
  };
}

/// Record a human decision at an expected case revision.
class DecisionCaseRequest {
  const DecisionCaseRequest({
    required this.revision,
    required this.decision,
    required this.reason,
    this.revised_recommendation,
    this.mission_proposal_id,
  });

  final int revision;
  final String decision;
  final String reason;
  final String? revised_recommendation;
  final String? mission_proposal_id;

  factory DecisionCaseRequest.fromJson(Map<String, dynamic> json) => DecisionCaseRequest(
    revision: json['revision'] as int,
    decision: json['decision'] as String,
    reason: json['reason'] as String,
    revised_recommendation: json['revised_recommendation'] == null ? null : json['revised_recommendation'] as String,
    mission_proposal_id: json['mission_proposal_id'] == null ? null : json['mission_proposal_id'] as String,
  );

  Map<String, dynamic> toJson() => {
    'revision': revision,
    'decision': decision,
    'reason': reason,
    if (revised_recommendation != null) 'revised_recommendation': revised_recommendation == null ? null : revised_recommendation!,
    if (mission_proposal_id != null) 'mission_proposal_id': mission_proposal_id == null ? null : mission_proposal_id!,
  };
}

/// Record a later observation outcome, optionally closing the case.
class OutcomeCaseRequest {
  const OutcomeCaseRequest({
    required this.revision,
    required this.outcome,
    required this.outcome_notes,
    required this.close_case,
  });

  final int revision;
  final String outcome;
  final String outcome_notes;
  final bool close_case;

  factory OutcomeCaseRequest.fromJson(Map<String, dynamic> json) => OutcomeCaseRequest(
    revision: json['revision'] as int,
    outcome: json['outcome'] as String,
    outcome_notes: json['outcome_notes'] as String,
    close_case: json['close_case'] as bool,
  );

  Map<String, dynamic> toJson() => {
    'revision': revision,
    'outcome': outcome,
    'outcome_notes': outcome_notes,
    'close_case': close_case,
  };
}

/// Replace an operator-authored recommendation at an expected revision.
class RecommendationCaseRequest {
  const RecommendationCaseRequest({
    required this.revision,
    required this.recommendation,
    required this.expected_effect,
    required this.tradeoffs,
  });

  final int revision;
  final String recommendation;
  final String expected_effect;
  final String tradeoffs;

  factory RecommendationCaseRequest.fromJson(Map<String, dynamic> json) => RecommendationCaseRequest(
    revision: json['revision'] as int,
    recommendation: json['recommendation'] as String,
    expected_effect: json['expected_effect'] as String,
    tradeoffs: json['tradeoffs'] as String,
  );

  Map<String, dynamic> toJson() => {
    'revision': revision,
    'recommendation': recommendation,
    'expected_effect': expected_effect,
    'tradeoffs': tradeoffs,
  };
}
