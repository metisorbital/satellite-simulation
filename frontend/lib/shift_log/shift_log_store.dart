import 'package:flutter/foundation.dart';

import '../api/mission.dart';
import '../api/shift_log_generated.dart';
import '../api/viewer_client.dart';
import '../scene/playback.dart';

/// The labels used by the public shift-log entry kinds.
const shiftLogKinds = <String, String>{
  'note': 'Note',
  'decision': 'Decision',
  'action': 'Action',
  'unresolved_issue': 'Unresolved issue',
  'event': 'Event',
};

/// Owns one authenticated run's shift-log state and durable writes.
///
/// The store is independent of the page layout. Both the full page and the
/// legacy dialog use the same write and invalidation behavior.
class ShiftLogStore extends ChangeNotifier {
  /// Creates a store scoped to [runId] and the current authenticated operator.
  ShiftLogStore({
    required this.mission,
    required this.runId,
    required this.operatorName,
  }) : _userId = mission.operatorUserId {
    mission.addListener(_sessionChanged);
  }

  /// The mission model supplying the authenticated API session.
  final Mission mission;

  /// The run whose records are being edited.
  final String runId;

  /// The display name used for the current operator's entries.
  final String operatorName;

  final String? _userId;
  List<ShiftLog> _logs = const [];
  String _kind = 'note';
  String _entryText = '';
  String _summaryText = '';
  String? _error;
  String? _orphanedSummary;
  bool _busy = true;
  bool _loaded = false;
  bool _uncertainWrite = false;
  String? _uncertainResource;
  JsonMap? _uncertainBody;
  bool _uncertainClearEntry = false;
  bool _uncertainResetSummary = false;
  bool _invalidated = false;
  bool _disposed = false;

  /// Shared submitted handovers and this operator's current-run draft.
  List<ShiftLog> get logs => List.unmodifiable(_logs);

  /// The currently selected entry kind.
  String get kind => _kind;

  /// Text in the entry composer.
  String get entryText => _entryText;

  /// Text in the draft summary composer.
  String get summaryText => _summaryText;

  /// Latest load or write failure, if any.
  String? get error => _error;

  /// Whether a request is currently loading or writing.
  bool get busy => _busy;

  /// Whether at least one successful read has completed.
  bool get loaded => _loaded;

  /// Whether a write outcome is unknown and must be retried unchanged.
  bool get uncertainWrite => _uncertainWrite;

  /// Summary text preserved when a draft changed while it was being edited.
  String? get orphanedSummary => _orphanedSummary;

  /// Whether the mission session still permits this store to operate.
  bool get validSession =>
      !_disposed &&
      !_invalidated &&
      mission.canUseShiftLog &&
      mission.operatorUserId == _userId &&
      mission.status?['run_id'] == runId;

  /// Whether [log] is the current operator's editable draft for this run.
  bool isPersonalDraft(ShiftLog log) =>
      log.status == 'draft' &&
      log.run_id == runId &&
      _userId != null &&
      log.user_id == _userId;

  /// The current operator's editable draft for this run, if one exists.
  ShiftLog? get draft => _logs.where(isPersonalDraft).firstOrNull;

  /// Whether closing would discard text or an unconfirmed write.
  bool get hasUnsavedChanges =>
      _entryText.trim().isNotEmpty ||
      summaryChanged ||
      _orphanedSummary != null ||
      _uncertainWrite;

  /// Whether the draft summary differs from the last saved value.
  bool get summaryChanged => _summaryText != (draft?.summary ?? '');

  /// Whether a user mutation can be started immediately.
  bool get canWrite => _loaded && !_busy && validSession && !_uncertainWrite;

  /// Change the entry kind without changing the persisted record.
  void setKind(String value) {
    if (!shiftLogKinds.containsKey(value) || _kind == value) return;
    _kind = value;
    notifyListeners();
  }

  /// Change the entry draft text without writing it remotely.
  void setEntryText(String value) {
    if (_entryText == value) return;
    _entryText = value;
    notifyListeners();
  }

  /// Change the handover summary without writing it remotely.
  void setSummaryText(String value) {
    if (_summaryText == value) return;
    _summaryText = value;
    notifyListeners();
  }

  /// Remove the composer text after the operator dismisses the warning.
  void dismissOrphanedSummary() {
    if (_orphanedSummary == null) return;
    _orphanedSummary = null;
    notifyListeners();
  }

  /// Load all retained records, preserving an unchanged in-progress summary.
  Future<void> load() async {
    if (!validSession) return;
    _busy = true;
    _error = null;
    notifyListeners();
    try {
      await _refresh();
    } catch (error) {
      if (validSession) {
        _error = 'Could not load shift logs: $error';
        notifyListeners();
      }
    } finally {
      if (validSession) {
        _busy = false;
        notifyListeners();
      }
    }
  }

  /// Retry a failed read or recover the list after an acknowledged write.
  Future<void> reload() => load();

  /// Add the current entry, using the mission model's idempotent retry key.
  Future<void> addEntry() async {
    final text = _entryText.trim();
    if (!canWrite || text.isEmpty) return;
    await _write(
      'entries',
      AddShiftLogEntryRequest(kind: _kind, text: text).toJson(),
      clearEntry: true,
    );
  }

  /// Persist the current draft summary.
  Future<void> saveSummary() async {
    final currentDraft = draft;
    if (!canWrite || currentDraft == null || !summaryChanged) return;
    await _write(
      '${currentDraft.shift_id}/summary',
      UpdateShiftLogSummaryRequest(summary: _summaryText).toJson(),
      resetSummary: true,
    );
  }

  /// Freeze the current draft after its summary has been saved.
  Future<void> submit() async {
    final currentDraft = draft;
    if (!canWrite ||
        currentDraft == null ||
        summaryChanged ||
        _entryText.trim().isNotEmpty) {
      return;
    }
    await _write(
      '${currentDraft.shift_id}/submit',
      const SubmitShiftLogRequest().toJson(),
      resetSummary: true,
    );
  }

  /// Retry an unconfirmed request with the exact same idempotent body.
  Future<void> retryUncertainWrite() async {
    final resource = _uncertainResource;
    final body = _uncertainBody;
    if (_busy || !_uncertainWrite || resource == null || body == null) return;
    await _write(
      resource,
      body,
      clearEntry: _uncertainClearEntry,
      resetSummary: _uncertainResetSummary,
      retry: true,
    );
  }

  /// Human-readable operator attribution for a saved record.
  String author(String userId) =>
      userId == mission.operatorUserId ? operatorName : userId;

  /// Format an API timestamp for the operator timeline.
  String timestamp(String value) {
    final parsed = DateTime.tryParse(value);
    return parsed == null
        ? value
        : '${parsed.toUtc().toIso8601String().replaceFirst('T', ' ').split('.').first} UTC';
  }

  Future<void> _refresh({bool resetSummary = false}) async {
    final records = await mission.shiftLogs(runId);
    if (!validSession) return;
    final currentDraft = draft;
    final nextDraft = records.where(isPersonalDraft).firstOrNull;
    final changedDraft = currentDraft?.shift_id != nextDraft?.shift_id;
    final hadEdits = !resetSummary && summaryChanged;
    final keepSummary = hadEdits && !changedDraft;
    if (hadEdits && changedDraft) _orphanedSummary = _summaryText;
    _logs = records;
    _loaded = true;
    if (!keepSummary) _summaryText = nextDraft?.summary ?? '';
    notifyListeners();
  }

  Future<void> _write(
    String resource,
    JsonMap body, {
    bool clearEntry = false,
    bool resetSummary = false,
    bool retry = false,
  }) async {
    final retryAllowed =
        retry &&
        _uncertainWrite &&
        resource == _uncertainResource &&
        _uncertainBody != null;
    if ((!canWrite && !retryAllowed) || !validSession) return;
    _busy = true;
    _error = null;
    notifyListeners();
    var saved = false;
    try {
      await mission.writeShiftLog(runId, resource, body);
      saved = true;
      if (!validSession) return;
      _uncertainWrite = false;
      _uncertainResource = null;
      _uncertainBody = null;
      _uncertainClearEntry = false;
      _uncertainResetSummary = false;
      if (clearEntry) _entryText = '';
      await _refresh(resetSummary: resetSummary);
    } on ViewerRequestException catch (error) {
      if (validSession) {
        _uncertainWrite = false;
        _uncertainResource = null;
        _uncertainBody = null;
        _uncertainClearEntry = false;
        _uncertainResetSummary = false;
        if (error.statusCode == 409) {
          _loaded = false;
          _error =
              'This shift record changed before the save completed. Reload before continuing.';
        } else {
          _error = 'Could not save this change: $error';
        }
        notifyListeners();
      }
    } catch (error) {
      if (validSession) {
        _uncertainWrite = !saved;
        if (!saved) {
          _uncertainResource = resource;
          _uncertainBody = Map<String, dynamic>.from(body);
          _uncertainClearEntry = clearEntry;
          _uncertainResetSummary = resetSummary;
        }
        if (saved) _loaded = false;
        _error = saved
            ? 'Saved, but the list could not refresh. Reload before continuing: $error'
            : 'Could not confirm the change. Retry unchanged to avoid duplicates: $error';
        notifyListeners();
      }
    } finally {
      if (validSession) {
        _busy = false;
        notifyListeners();
      }
    }
  }

  void _sessionChanged() {
    if (_disposed || _invalidated || validSession) return;
    _invalidated = true;
    _logs = const [];
    _loaded = false;
    _entryText = '';
    _summaryText = '';
    notifyListeners();
  }

  @override
  void dispose() {
    _disposed = true;
    mission.removeListener(_sessionChanged);
    super.dispose();
  }
}
