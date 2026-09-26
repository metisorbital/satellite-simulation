// Generated from Pydantic v2 contracts. Do not edit by hand.
// dart format off
// Regenerate: uv run python scripts/generate_contracts.py
// ignore_for_file: non_constant_identifier_names, unnecessary_non_null_assertion, prefer_null_aware_operators, use_null_aware_elements

/// Accept a bounded narrative without client-controlled attribution.
class AddShiftLogEntryRequest {
  const AddShiftLogEntryRequest({
    required this.kind,
    required this.text,
  });

  final String kind;
  final String text;

  factory AddShiftLogEntryRequest.fromJson(Map<String, dynamic> json) => AddShiftLogEntryRequest(
    kind: json['kind'] as String,
    text: json['text'] as String,
  );

  Map<String, dynamic> toJson() => {
    'kind': kind,
    'text': text,
  };
}

/// An operator's editable draft or frozen submitted shift record.
class ShiftLog {
  const ShiftLog({
    required this.shift_id,
    required this.run_id,
    required this.user_id,
    required this.status,
    required this.summary,
    required this.created_at,
    required this.updated_at,
    required this.submitted_at,
    required this.entries,
  });

  final String shift_id;
  final String run_id;
  final String user_id;
  final String status;
  final String summary;
  final String created_at;
  final String updated_at;
  final String? submitted_at;
  final List<ShiftLogEntry> entries;

  factory ShiftLog.fromJson(Map<String, dynamic> json) => ShiftLog(
    shift_id: json['shift_id'] as String,
    run_id: json['run_id'] as String,
    user_id: json['user_id'] as String,
    status: json['status'] as String,
    summary: json['summary'] as String,
    created_at: json['created_at'] as String,
    updated_at: json['updated_at'] as String,
    submitted_at: json['submitted_at'] == null ? null : json['submitted_at'] as String,
    entries: (json['entries'] as List).map((item) => ShiftLogEntry.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'shift_id': shift_id,
    'run_id': run_id,
    'user_id': user_id,
    'status': status,
    'summary': summary,
    'created_at': created_at,
    'updated_at': updated_at,
    'submitted_at': submitted_at == null ? null : submitted_at!,
    'entries': entries.map((item) => item.toJson()).toList(),
  };
}

/// An immutable entry attributed to exactly one registered operator.
class ShiftLogEntry {
  const ShiftLogEntry({
    required this.entry_id,
    required this.shift_id,
    required this.user_id,
    required this.kind,
    required this.text,
    required this.details,
    required this.created_at,
  });

  final String entry_id;
  final String shift_id;
  final String user_id;
  final String kind;
  final String text;
  final ShiftLogEntryDetails details;
  final String created_at;

  factory ShiftLogEntry.fromJson(Map<String, dynamic> json) => ShiftLogEntry(
    entry_id: json['entry_id'] as String,
    shift_id: json['shift_id'] as String,
    user_id: json['user_id'] as String,
    kind: json['kind'] as String,
    text: json['text'] as String,
    details: ShiftLogEntryDetails.fromJson(Map<String, dynamic>.from(json['details'] as Map)),
    created_at: json['created_at'] as String,
  );

  Map<String, dynamic> toJson() => {
    'entry_id': entry_id,
    'shift_id': shift_id,
    'user_id': user_id,
    'kind': kind,
    'text': text,
    'details': details.toJson(),
    'created_at': created_at,
  };
}

/// Describe an automatically recorded successful simulator control.
class ShiftLogEntryDetails {
  const ShiftLogEntryDetails({
    required this.action,
    required this.speed,
    required this.committed_tick,
    required this.status,
  });

  final String? action;
  final int? speed;
  final int? committed_tick;
  final String? status;

  factory ShiftLogEntryDetails.fromJson(Map<String, dynamic> json) => ShiftLogEntryDetails(
    action: json['action'] == null ? null : json['action'] as String,
    speed: json['speed'] == null ? null : json['speed'] as int,
    committed_tick: json['committed_tick'] == null ? null : json['committed_tick'] as int,
    status: json['status'] == null ? null : json['status'] as String,
  );

  Map<String, dynamic> toJson() => {
    'action': action == null ? null : action!,
    'speed': speed == null ? null : speed!,
    'committed_tick': committed_tick == null ? null : committed_tick!,
    'status': status == null ? null : status!,
  };
}

/// Return retained shifts belonging to the current run and operator.
class ShiftLogList {
  const ShiftLogList({
    required this.items,
  });

  final List<ShiftLog> items;

  factory ShiftLogList.fromJson(Map<String, dynamic> json) => ShiftLogList(
    items: (json['items'] as List).map((item) => ShiftLog.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'items': items.map((item) => item.toJson()).toList(),
  };
}

/// Accept an empty submission command without identity or state claims.
class SubmitShiftLogRequest {
  const SubmitShiftLogRequest();


  factory SubmitShiftLogRequest.fromJson(Map<String, dynamic> json) => SubmitShiftLogRequest(
  );

  Map<String, dynamic> toJson() => {
  };
}

/// Replace a draft's handover summary.
class UpdateShiftLogSummaryRequest {
  const UpdateShiftLogSummaryRequest({
    required this.summary,
  });

  final String summary;

  factory UpdateShiftLogSummaryRequest.fromJson(Map<String, dynamic> json) => UpdateShiftLogSummaryRequest(
    summary: json['summary'] as String,
  );

  Map<String, dynamic> toJson() => {
    'summary': summary,
  };
}
