import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/metis_generated.dart';
import '../api/mission.dart';
import '../api/viewer_client.dart';

/// Loads the server-owned mission record for the current recorded run.
class MetisController extends ChangeNotifier {
  MetisController(this.mission) {
    mission.addListener(_missionChanged);
    _poll = Timer.periodic(
      const Duration(seconds: 1),
      (_) => unawaited(load()),
    );
  }

  final Mission mission;
  MetisBriefing? briefing;
  String? error;
  bool busy = false;
  bool unavailable = false;
  bool _disposed = false;
  bool _savingPreference = false;
  bool _approving = false;
  String? _approvalCaseId;
  Map<String, dynamic>? _approvalBody;
  Future<void>? _loadRequest;
  String? _runId;
  late final Timer _poll;
  RunOutcome? outcome;
  bool forecastOpen = false;

  MissionState? get missionState => briefing?.mission_state;
  bool get missionAvailable => briefing?.mission_available ?? false;
  String? get unavailableReason => briefing?.unavailable_reason;
  String? get caseId => missionState?.case_id;
  String get state => missionState?.status ?? 'not_started';
  bool get hasMission => missionState != null;
  bool get metisOn => briefing?.metis_enabled ?? true;
  bool get alertRaised => caseId != null;
  bool get savingPreference => _savingPreference;

  bool get canLoadMission =>
      !missionAvailable &&
      briefing != null &&
      mission.isObserved &&
      mission.canReplaceRun &&
      !mission.busy &&
      (mission.status?['satellites'] as List? ?? const []).any(
        (satellite) => satellite['satellite_id'] == 'BUPT-1',
      );

  /// Position the existing recorded source at the saved mission origin.
  Future<void> loadMission() async {
    if (!canLoadMission) return;
    final origin = DateTime.tryParse(briefing!.mission.t0_utc);
    final epoch = DateTime.tryParse(
      mission.status?['epoch_utc'] as String? ?? '',
    );
    if (origin == null || epoch == null) return;
    if (await mission.seekObserved(origin.difference(epoch).inSeconds)) {
      await _loadRequest;
      await load();
    }
  }

  /// Apply the linked saved proposal through the standard audited case API.
  Future<void> approveAlert(String requestedCaseId) async {
    if (_approving) throw StateError('Approval is already being saved.');
    _approving = true;
    try {
      await load();
      final current = briefing;
      final requestedRun = mission.status?['run_id'];
      final retry = _approvalCaseId == requestedCaseId && _approvalBody != null;
      if (_disposed ||
          current == null ||
          caseId != requestedCaseId ||
          (state != 'awaiting_decision' &&
              !(retry &&
                  state == 'approved' &&
                  missionState?.plan == 'metis'))) {
        throw StateError('This alert changed. Review the investigation.');
      }
      final record = await mission.readCase(requestedCaseId);
      if (_disposed ||
          requestedRun != mission.status?['run_id'] ||
          record.run_id != requestedRun) {
        throw StateError('The mission changed. Review the investigation.');
      }
      _approvalCaseId = requestedCaseId;
      _approvalBody ??= {
        'revision': record.revision,
        'decision': 'approved',
        'reason':
            'Approved the saved preventive plan from the critical alert: '
            'reschedule the routine batch and preserve wildfire capture and downlink.',
        'mission_proposal_id': current.proposal.proposal_id,
      };
      await mission.updateCase(requestedCaseId, 'decision', _approvalBody!);
      _approvalCaseId = null;
      _approvalBody = null;
      await load();
    } on ViewerRequestException catch (exception) {
      if (exception.statusCode == 409) {
        _approvalCaseId = null;
        _approvalBody = null;
      }
      rethrow;
    } finally {
      _approving = false;
    }
  }

  double get missionMinute {
    final epoch = DateTime.tryParse(
      mission.status?['epoch_utc'] as String? ?? '',
    );
    final start = DateTime.tryParse(briefing?.mission.t0_utc ?? '');
    final tick = mission.status?['committed_tick'] as num?;
    if (epoch == null || start == null || tick == null || tick < 0) return 0;
    return ((epoch.difference(start).inSeconds + tick) / 60)
        .clamp(0, briefing?.mission.duration_min ?? 180)
        .toDouble();
  }

  bool get canSetMetis =>
      missionAvailable &&
      mission.canControl &&
      !busy &&
      !_savingPreference &&
      !mission.busy &&
      !alertRaised &&
      const ['created', 'paused'].contains(mission.status?['status']) &&
      missionMinute < (briefing?.alert_at_min ?? 0);

  String? get metisControlHint {
    if (_savingPreference) return 'Saving Metis setting…';
    if (alertRaised) return 'Review the existing alert in Investigations.';
    if (mission.status?['status'] == 'running') {
      return 'Pause the run to change Metis before the alert time.';
    }
    if (!const ['created', 'paused'].contains(mission.status?['status'])) {
      return 'Choose Metis for a new mission before starting the run.';
    }
    if (missionMinute >= (briefing?.alert_at_min ?? 0)) {
      return 'This run has already passed the scheduled alert time.';
    }
    return null;
  }

  void toggleForecast() {
    forecastOpen = !forecastOpen;
    notifyListeners();
  }

  /// Persist whether Metis watches this mission before its decision point.
  Future<void> setMetis(bool enabled) async {
    if (!canSetMetis || enabled == metisOn) return;
    final requestedRun = mission.status?['run_id'];
    _savingPreference = true;
    error = null;
    notifyListeners();
    try {
      await _loadRequest;
      if (_disposed || requestedRun != mission.status?['run_id']) return;
      await mission.metis('/v1/metis/preference', body: {'enabled': enabled});
    } catch (exception) {
      error = '$exception';
    } finally {
      _savingPreference = false;
      if (!_disposed) notifyListeners();
    }
    if (error == null) await load();
  }

  void _missionChanged() {
    final current = mission.status?['run_id'] as String?;
    if (current == _runId || _disposed) return;
    _runId = current;
    _approvalCaseId = null;
    _approvalBody = null;
    briefing = null;
    outcome = null;
    notifyListeners();
    unawaited(load());
  }

  /// Refresh the saved forecast and mission state for the operator's run.
  Future<void> load() {
    if (_disposed || _savingPreference || mission.status == null) {
      return Future<void>.value();
    }
    return _loadRequest ??= _refresh().whenComplete(() => _loadRequest = null);
  }

  Future<void> _refresh() async {
    busy = briefing == null;
    if (busy) notifyListeners();
    final requestedRun = mission.status?['run_id'];
    try {
      final body = await mission.metis('/v1/metis/briefing');
      if (_disposed || requestedRun != mission.status?['run_id']) return;
      briefing = MetisBriefing.fromJson(body);
      if (briefing?.mission_state != null &&
          (mission.status?['committed_tick'] as num? ?? -1) >= 0) {
        final result = await mission.metis(
          '/v1/metis/runs/$requestedRun/outcome',
        );
        if (_disposed || requestedRun != mission.status?['run_id']) return;
        outcome = RunOutcome.fromJson(result);
      } else {
        outcome = null;
      }
      error = null;
      unavailable = false;
    } on ViewerRequestException catch (exception) {
      if (exception.statusCode == 404) {
        unavailable = true;
      } else {
        error = '$exception';
      }
    } catch (exception) {
      error = '$exception';
    } finally {
      busy = false;
      if (!_disposed) notifyListeners();
    }
  }

  @override
  void dispose() {
    _disposed = true;
    _poll.cancel();
    mission.removeListener(_missionChanged);
    super.dispose();
  }
}
