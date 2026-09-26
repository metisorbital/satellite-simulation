import 'dart:async';

import 'package:flutter/foundation.dart';

import '../api/mission.dart';
import '../api/notifications_generated.dart';

export '../api/notifications_generated.dart' show OperatorNotification;

/// Loads server-derived workspace alerts and records explicit acknowledgements.
class NotificationController extends ChangeNotifier {
  NotificationController(this._mission) {
    _identity = _currentIdentity;
    _mission.addListener(_missionChanged);
    _poll = Timer.periodic(
      const Duration(seconds: 5),
      (_) => unawaited(refresh()),
    );
  }

  final Mission _mission;
  List<OperatorNotification> items = const [];
  int unreadCount = 0;
  bool loading = false;
  bool loaded = false;
  String? error;
  bool _disposed = false;
  bool _mutationPending = false;
  int _generation = 0;
  late String _identity;
  late final Timer _poll;

  String get _currentIdentity =>
      '${_mission.operatorUserId ?? ''}/${_mission.status?['run_id'] ?? ''}';

  void _missionChanged() {
    if (_disposed || _identity == _currentIdentity) return;
    _identity = _currentIdentity;
    _generation++;
    items = const [];
    unreadCount = 0;
    loaded = false;
    error = null;
    loading = false;
    _mutationPending = false;
    notifyListeners();
    unawaited(refresh());
  }

  Future<void> refresh() async {
    if (!_mission.canUseShiftLog || loading || _mutationPending || _disposed) {
      return;
    }
    final generation = _generation;
    loading = true;
    notifyListeners();
    try {
      final response = await _mission.notifications();
      if (_disposed || generation != _generation) return;
      items = response.items;
      unreadCount = response.unread_count;
      loaded = true;
      error = null;
    } catch (_) {
      if (!_disposed && generation == _generation) {
        error = 'Current warnings could not be loaded. Retry from this page.';
      }
    } finally {
      if (!_disposed && generation == _generation) {
        loading = false;
        notifyListeners();
      }
    }
  }

  List<OperatorNotification> warningsFor(String satelliteId) => items
      .where(
        (item) =>
            item.category == 'warning' && item.satellite_id == satelliteId,
      )
      .toList();

  Future<void> markRead(OperatorNotification item) async {
    if (!item.unread || _disposed || _mutationPending) return;
    // Any in-flight GET belongs to an earlier generation and must never put its
    // older unread projection back after this acknowledgement succeeds.
    final generation = ++_generation;
    _mutationPending = true;
    loading = false;
    notifyListeners();
    try {
      final response = await _mission.markNotificationRead(
        item.key,
        item.version,
      );
      if (_disposed || generation != _generation) return;
      items = response.items;
      unreadCount = response.unread_count;
      loaded = true;
      error = null;
      notifyListeners();
    } catch (_) {
      if (!_disposed && generation == _generation) {
        error = 'Could not mark this notification as viewed. Retry the action.';
        notifyListeners();
      }
    } finally {
      if (!_disposed && generation == _generation) _mutationPending = false;
    }
  }

  Future<void> markCaseRead(String caseId, int revision) => markRead(
    OperatorNotification(
      key: 'case:$caseId',
      version: revision,
      category: 'case',
      satellite_id: '',
      title: '',
      summary: '',
      unread: true,
    ),
  );

  @override
  void dispose() {
    _disposed = true;
    _generation++;
    _poll.cancel();
    _mission.removeListener(_missionChanged);
    super.dispose();
  }
}
