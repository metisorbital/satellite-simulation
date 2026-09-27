import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/metis_generated.dart';
import '../api/mission.dart';
import '../api/viewer_client.dart';

/// Holds the Metis switch, the decision, Metis's alert and each mode's run.
///
/// All numbers come from the Metis API: the forecast and proposal, then public
/// telemetry and events of the run. The viewer computes no physics.
class MetisController extends ChangeNotifier {
  MetisController(this.mission);

  final Mission mission;
  MetisBriefing? briefing;

  /// Whether the Metis switch is on. On, Metis watches the mission and the run
  /// pauses at its alert; off, the original schedule flies unwatched.
  bool metisOn = false;

  /// Latest outcome of each mode's run, keyed by `metis_off` and `metis_on`.
  final Map<String, RunOutcome> outcomes = {};
  String? error;
  bool busy = false;

  /// True when the server has no Metis demo installed; the Overview then hides Metis.
  bool unavailable = false;

  /// Whether the solar and load forecast charts are unfolded; folded by default.
  bool forecastOpen = false;
  Timer? _poll;
  String? _polling;
  bool _disposed = false;

  String get mode => metisOn ? 'metis_on' : 'metis_off';

  String? runId(String of) =>
      of == 'metis_on' ? briefing?.runs.metis_on : briefing?.runs.metis_off;

  /// Mode of the run this session is watching, if it is a Metis demo run.
  String? get activeMode {
    final current = mission.status?['run_id'];
    if (current == null) return null;
    if (current == briefing?.runs.metis_on) return 'metis_on';
    if (current == briefing?.runs.metis_off) return 'metis_off';
    return null;
  }

  RunOutcome? get outcome => outcomes[mode];

  /// The other mode's latest outcome, drawn for comparison.
  RunOutcome? get comparison => outcomes[metisOn ? 'metis_off' : 'metis_on'];

  /// Metis's alert on the shown run, once the watched mission reaches it.
  MetisAlert? get alert => metisOn ? outcome?.alert : null;

  void _notify() {
    if (!_disposed) notifyListeners();
  }

  /// Load the briefing and both modes' latest outcomes; resume polling the active run.
  Future<void> load() async {
    busy = true;
    error = null;
    _notify();
    try {
      await _refreshBriefing();
      final active = activeMode;
      if (active != null) metisOn = active == 'metis_on';
      for (final of in const ['metis_off', 'metis_on']) {
        await _refreshOutcome(of);
      }
      if (active != null) _startPolling(active);
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
      _notify();
    }
  }

  void toggleForecast() {
    forecastOpen = !forecastOpen;
    _notify();
  }

  /// Turn the Metis switch on or off; the Overview shows that mode's latest run.
  void setMetis(bool on) {
    metisOn = on;
    error = null;
    _notify();
  }

  /// Fly the original schedule from T0. With Metis on, the run pauses by
  /// itself at the alert and waits for the operator's decision.
  Future<void> fly() => metisOn
      ? _fly('metis_on', 'original', watch: true)
      : _fly('metis_off', 'original');

  /// Approve the alert's proposal; the mission continues on the Metis plan.
  Future<void> approve() async {
    final proposal = briefing?.proposal;
    if (proposal == null || busy) return;
    busy = true;
    error = null;
    _notify();
    try {
      await mission.metis(
        '/v1/metis/proposals/${proposal.proposal_id}/approve',
        body: {},
      );
    } catch (exception) {
      error = '$exception';
      busy = false;
      _notify();
      return;
    }
    busy = false;
    await _fly('metis_on', 'metis', proposalId: proposal.proposal_id);
  }

  /// Dismiss the alert; the watched mission continues its original schedule.
  Future<void> dismiss() async {
    final id = runId('metis_on');
    if (id == null || busy) return;
    busy = true;
    error = null;
    _notify();
    try {
      await mission.metis('/v1/metis/runs/$id/dismiss', body: {});
      await mission.control('resume');
      _startPolling('metis_on');
    } catch (exception) {
      error = '$exception';
    } finally {
      busy = false;
      _notify();
    }
  }

  Future<void> _fly(
    String of,
    String plan, {
    String? proposalId,
    bool watch = false,
    bool resume = true,
  }) async {
    if (busy) return;
    busy = true;
    error = null;
    _stopPolling();
    _notify();
    try {
      final launched = await mission.launchMissionRun(
        plan,
        proposalId: proposalId,
        watch: watch,
        resume: resume,
      );
      await _refreshBriefing();
      if (!launched) {
        error = mission.error ?? 'The demo run could not start.';
      } else {
        outcomes.remove(of);
        _startPolling(of);
      }
    } catch (exception) {
      error = '$exception';
    } finally {
      busy = false;
      _notify();
    }
  }

  /// Clear the approval and both modes' runs, for rehearsals.
  Future<void> reset() async {
    final proposal = briefing?.proposal;
    if (proposal == null || busy) return;
    busy = true;
    error = null;
    _notify();
    try {
      await mission.metis(
        '/v1/metis/proposals/${proposal.proposal_id}/reopen',
        body: {},
      );
      _stopPolling();
      outcomes.clear();
      metisOn = false;
      await _refreshBriefing();
    } catch (exception) {
      error = '$exception';
    } finally {
      busy = false;
      _notify();
    }
  }

  Future<void> _refreshBriefing() async {
    briefing = MetisBriefing.fromJson(
      await mission.metis('/v1/metis/briefing'),
    );
  }

  void _startPolling(String of) {
    _poll?.cancel();
    _polling = of;
    unawaited(_refreshOutcome(of));
    _poll = Timer.periodic(
      const Duration(seconds: 1),
      (_) => unawaited(_refreshOutcome(of)),
    );
  }

  Future<void> _refreshOutcome(String of) async {
    final id = runId(of);
    if (id == null || _disposed) return;
    try {
      final next = RunOutcome.fromJson(
        await mission.metis('/v1/metis/runs/$id/outcome'),
      );
      outcomes[of] = next;
      if (of == _polling &&
          (next.complete || mission.status?['run_id'] != id)) {
        _stopPolling();
      }
    } catch (exception) {
      error = '$exception';
      if (of == _polling) _stopPolling();
    }
    _notify();
  }

  void _stopPolling() {
    _poll?.cancel();
    _poll = null;
    _polling = null;
  }

  @override
  void dispose() {
    _disposed = true;
    _poll?.cancel();
    super.dispose();
  }
}
