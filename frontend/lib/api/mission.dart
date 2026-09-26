import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:flutter/foundation.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../scene/playback.dart';
import 'generated.dart';
import 'shift_log_generated.dart';
import 'viewer_client.dart';

/// Owns session, committed snapshots, reconnects, and guarded run controls.
class Mission extends ChangeNotifier {
  Mission({ViewerClient? client, this.onSessionExpired})
    : _client = client ?? ViewerClient();

  final ViewerClient _client;
  final VoidCallback? onSessionExpired;
  bool _closed = false;
  String _lastToken = '';
  String? _operatorUserId;
  String get csrfToken => _lastToken;
  String? get operatorUserId => _operatorUserId;
  bool get canUseShiftLog =>
      !_closed && _operatorUserId != null && _token.isNotEmpty;
  final Map<String, String> _shiftRetryKeys = {};
  final CommittedPlayback playback = CommittedPlayback();
  final Stopwatch clock = Stopwatch()..start();
  JsonMap? trajectory;
  List<JsonMap>? editableSatellites;
  List<JsonMap> datasets = const [];
  bool datasetsLoading = false;
  String? datasetsError;
  bool get isObserved => status?['data_source'] == 'satellitecots';
  String get dataSource => status?['data_source'] as String? ?? 'physics';
  JsonMap? get dataset => datasets
      .where((item) => item['dataset_id'] == status?['dataset_id'])
      .firstOrNull;
  final Map<String, JsonMap> catalogs = {};
  final Set<String> _pendingCatalogs = {};
  final Map<String, String> _catalogErrors = {};
  bool get catalogLoading => _pendingCatalogs.isNotEmpty;
  String? get catalogError => _catalogErrors.values.firstOrNull;
  String? error;
  bool busy = false;
  bool connecting = false;
  bool get canControl => _token.isNotEmpty && _allowedActions.isNotEmpty;
  bool get canEdit => canControl && editableSatellites != null;
  bool get canReplaceRun =>
      canControl && !{'running', 'paused'}.contains(status?['status']);
  bool canPerform(String action) =>
      _token.isNotEmpty && _allowedActions.contains(action);
  String _token = '';
  Set<String> _allowedActions = {};
  bool _publicDemoSession = false;
  String? _terminalRunId;
  int _demoRefreshAttempts = 0;
  int _generation = 0, _backoff = 1000, _nextTrajectory = 0;
  Timer? _reconnect;
  Timer? _demoRefresh;
  WebSocketChannel? _socket;
  JsonMap? get status => playback.status;
  double get now => clock.elapsedMicroseconds / 1000;

  void _clearSession() {
    _token = '';
    _allowedActions = {};
  }

  void _scheduleDemoRefresh(JsonMap run) {
    final id = run['run_id'] as String;
    final terminal = const {
      'completed',
      'stopped',
      'failed',
      'aborted',
    }.contains(run['status']);
    if (_terminalRunId != id || !terminal) {
      _demoRefresh?.cancel();
      _demoRefresh = null;
      _terminalRunId = terminal ? id : null;
      _demoRefreshAttempts = 0;
    }
    if (!_publicDemoSession ||
        !terminal ||
        connecting ||
        _demoRefresh != null ||
        _demoRefreshAttempts >= 6) {
      return;
    }
    final delay =
        min(12000, 1500 * (1 << _demoRefreshAttempts)) +
        Random.secure().nextInt(1200);
    _demoRefresh = Timer(Duration(milliseconds: delay), () {
      _demoRefresh = null;
      if (!_publicDemoSession || status?['run_id'] != id || connecting) return;
      _demoRefreshAttempts++;
      unawaited(connect());
    });
  }

  Future<JsonMap> _request(
    String path, {
    JsonMap? body,
    String? idempotencyKey,
  }) async {
    final generation = _generation;
    try {
      return await _client.request(
        path,
        body: body,
        csrfToken: _token,
        idempotencyKey: idempotencyKey,
      );
    } on ViewerRequestException catch (exception) {
      if (exception.statusCode == 401 &&
          !_closed &&
          generation == _generation) {
        suspend();
        onSessionExpired?.call();
      }
      rethrow;
    }
  }

  bool _current(int generation, String id) =>
      !_closed && _generation == generation && status?['run_id'] == id;

  void _ingest(JsonMap next, List<dynamic> incoming) {
    final previousRun = status?['run_id'];
    playback.ingest(
      next,
      incoming.map((f) => Map<String, dynamic>.from(f as Map)).toList(),
      now,
    );
    if (previousRun != status?['run_id']) {
      _resetTelemetryHistory();
      _pendingCatalogs.clear();
      _catalogErrors.clear();
    }
    for (final frames in playback.frames.values) {
      final version = frames.lastOrNull?['catalog_version'];
      if (version is String && !_catalogErrors.containsKey(version)) {
        unawaited(loadCatalog(version));
      }
    }
    _scheduleDemoRefresh(next);
    notifyListeners();
    final committed = next['committed_tick'] as int;
    final observed = next['source_kind'] == 'observed';
    final position = observed
        ? max(committed, next['playback_start_s'] as int? ?? 0)
        : committed;
    if (position >= _nextTrajectory &&
        (position < next['duration_s'] || observed && trajectory == null)) {
      _loadTrajectory(_generation, next);
    }
  }

  /// Discover imported observed datasets available in this database.
  Future<void> loadDatasets() async {
    if (_closed || datasetsLoading) return;
    final generation = _generation;
    datasetsLoading = true;
    datasetsError = null;
    notifyListeners();
    try {
      final response = DatasetList.fromJson(await _request('/v1/datasets'));
      if (_closed || generation != _generation) return;
      datasets = response.items.map((item) => item.toJson()).toList();
    } catch (exception) {
      if (!_closed && generation == _generation) {
        datasetsError = 'Observed datasets unavailable: $exception';
      }
    } finally {
      if (!_closed && generation == _generation) {
        datasetsLoading = false;
        notifyListeners();
      }
    }
  }

  /// Load public metadata for a received catalog version, or retry a failure.
  Future<void> loadCatalog(String version) async {
    final id = status?['run_id'] as String?;
    if (_closed ||
        id == null ||
        version.isEmpty ||
        catalogs.containsKey(version) ||
        _pendingCatalogs.contains(version)) {
      return;
    }
    final generation = _generation;
    _pendingCatalogs.add(version);
    _catalogErrors.remove(version);
    notifyListeners();
    try {
      final catalog = await _request(
        '/v1/catalog?version=${Uri.encodeQueryComponent(version)}',
      );
      if (!_current(generation, id)) return;
      if (catalog['catalog_version'] != version ||
          catalog['channels'] is! List) {
        throw const FormatException('Unexpected telemetry catalog response.');
      }
      catalogs[version] = catalog;
    } catch (exception) {
      if (_current(generation, id)) {
        _catalogErrors[version] = 'Catalog $version unavailable: $exception';
      }
    } finally {
      if (_current(generation, id)) {
        _pendingCatalogs.remove(version);
        notifyListeners();
      }
    }
  }

  String? _historySatellite;
  int _historySeconds = 60;
  DateTime? _historyEnd;
  List<JsonMap> _pinnedHistory = const [];
  int _historyRequest = 0;
  bool historyLoading = false;
  String? historyError;

  /// Return live history or the selected fixed range without copying each frame.
  List<JsonMap> telemetryHistory(String satelliteId, {DateTime? end}) {
    if (end == null) return playback.history[satelliteId] ?? const [];
    return satelliteId == _historySatellite && end == _historyEnd
        ? _pinnedHistory
        : const [];
  }

  void _resetTelemetryHistory() {
    _historyRequest++;
    _historySatellite = null;
    _historyEnd = null;
    _pinnedHistory = const [];
    historyLoading = false;
    historyError = null;
  }

  /// Invalidate in-flight replay when the dashboard changes its selection.
  void cancelTelemetryHistory() {
    _resetTelemetryHistory();
    if (!_closed) notifyListeners();
  }

  /// Fill an inclusive committed window without changing live playback.
  ///
  /// With [end], retain a separate fixed UTC range while new samples arrive.
  /// Otherwise refill the rolling live history, including its playback lag.
  Future<void> loadTelemetryHistory(
    String satelliteId,
    int seconds, {
    DateTime? end,
  }) async {
    final selectedEnd = end?.toUtc();
    final selectedSeconds = seconds.clamp(1, 86400);
    final sameRange =
        _historySatellite == satelliteId &&
        _historyEnd == selectedEnd &&
        _historySeconds == selectedSeconds;
    final request = ++_historyRequest;
    _historySatellite = satelliteId;
    _historySeconds = selectedSeconds;
    _historyEnd = selectedEnd;
    if (!sameRange || selectedEnd == null) _pinnedHistory = const [];
    historyLoading = false;
    historyError = null;
    final run = status;
    if (_closed) return;
    if (run == null) {
      notifyListeners();
      return;
    }
    if (selectedEnd == null) {
      playback.retainHistory(satelliteId, selectedSeconds);
    }
    final generation = _generation;
    final id = run['run_id'] as String;
    final satellite = (run['satellites'] as List)
        .cast<Map>()
        .where((item) => item['satellite_id'] == satelliteId)
        .firstOrNull;
    if (satellite == null) {
      notifyListeners();
      return;
    }
    final stream = Uri.encodeQueryComponent(satellite['stream_id'] as String);
    final committed = run['committed_tick'] as int;
    final epoch = DateTime.parse(run['epoch_utc'] as String);
    final endSeconds = selectedEnd == null
        ? committed.toDouble()
        : selectedEnd.difference(epoch).inMicroseconds / 1000000;
    if (selectedEnd != null && (endSeconds < 0 || endSeconds > committed)) {
      _pinnedHistory = const [];
      historyError = 'Choose a time range within committed run history.';
      notifyListeners();
      return;
    }
    final observed = run['source_kind'] == 'observed';
    final startSeconds = max(
      0.0,
      endSeconds - selectedSeconds - (selectedEnd == null ? 40 : 0),
    );
    // Observed sample indices are dense even when source UTC has gaps.
    final lastSequence = observed
        ? run['committed_sequence'] as int? ?? -1
        : endSeconds.floor();
    final firstSequence = observed ? 0 : startSeconds.ceil();
    bool active() => _current(generation, id) && request == _historyRequest;
    final pinnedFrames = <int, JsonMap>{};
    historyLoading = true;
    notifyListeners();
    try {
      var first = firstSequence;
      while (first <= lastSequence) {
        final last = observed ? lastSequence : min(lastSequence, first + 1999);
        final query = Uri(
          queryParameters: {
            'stream_id': satellite['stream_id'] as String,
            'from_sequence': '$first',
            'through_sequence': '$last',
            'limit': '2000',
            if (observed) ...{
              'from_observed_at': epoch
                  .add(Duration(microseconds: (startSeconds * 1000000).ceil()))
                  .toUtc()
                  .toIso8601String(),
              'through_observed_at': epoch
                  .add(Duration(microseconds: (endSeconds * 1000000).floor()))
                  .toUtc()
                  .toIso8601String(),
            },
          },
        ).query;
        final page = await _request(
          observed
              ? '/v1/telemetry?$query'
              : '/v1/telemetry?stream_id=$stream&from_sequence=$first&through_sequence=$last&limit=2000',
        );
        if (!active()) return;
        final items = (page['items'] as List)
            .map((item) => Map<String, dynamic>.from(item as Map))
            .toList();
        if ((!observed && page['has_more'] == true) ||
            items.any(
              (frame) =>
                  frame['stream_id'] != satellite['stream_id'] ||
                  frame['sequence'] is! int ||
                  (frame['sequence'] as int) < first ||
                  (frame['sequence'] as int) > last ||
                  frameSeconds(frame, run) < startSeconds ||
                  frameSeconds(frame, run) > endSeconds,
            )) {
          throw const FormatException(
            'History response does not match the selected window.',
          );
        }
        if (selectedEnd == null) {
          playback.mergeHistory(items);
          notifyListeners();
        } else {
          for (final frame in items) {
            pinnedFrames[frame['sequence'] as int] = frame;
          }
        }
        if (observed) {
          if (page['has_more'] != true) break;
          if (items.isEmpty || (items.last['sequence'] as int) < first) {
            throw const FormatException('History pagination did not advance.');
          }
          first = (items.last['sequence'] as int) + 1;
        } else {
          first = last + 1;
        }
      }
      if (active() && selectedEnd != null) {
        final ordered = pinnedFrames.values.toList()
          ..sort(
            (a, b) => (a['sequence'] as int).compareTo(b['sequence'] as int),
          );
        _pinnedHistory = List<JsonMap>.unmodifiable(ordered);
      }
    } catch (exception) {
      if (active()) historyError = 'History unavailable: $exception';
    } finally {
      if (active()) {
        historyLoading = false;
        notifyListeners();
      }
    }
  }

  Future<void> _snapshot(
    int generation,
    String id, [
    JsonMap? acknowledged,
  ]) async {
    final snapshot = Snapshot.fromJson(
      await _request('/v1/runs/$id/snapshot?history=41'),
    ).toJson();
    if (!_current(generation, id) || snapshot['status']['run_id'] != id) return;
    final next = Map<String, dynamic>.from(snapshot['status'] as Map);
    _ingest(
      acknowledged != null && isStatusOlder(next, acknowledged)
          ? acknowledged
          : next,
      snapshot['frames'] as List,
    );
    if (_historySatellite != null) {
      unawaited(
        loadTelemetryHistory(
          _historySatellite!,
          _historySeconds,
          end: _historyEnd,
        ),
      );
    }
  }

  Future<void> _loadTrajectory(int generation, JsonMap run) async {
    final position = max(
      0,
      max(run['committed_tick'] as int, run['playback_start_s'] as int? ?? 0),
    );
    final from = max(0, position - (isObserved ? 40 : 0));
    _nextTrajectory = (position ~/ 1800 + 1) * 1800;
    try {
      final path = Trajectory.fromJson(
        await _request(
          '/v1/runs/${run['run_id']}/trajectory?from=$from&to=${min(run['duration_s'] as int, from + 3600)}&step_s=20',
        ),
      ).toJson();
      if (_current(generation, run['run_id'] as String) &&
          path['run_id'] == run['run_id']) {
        trajectory = path;
        notifyListeners();
      }
    } catch (exception) {
      if (_current(generation, run['run_id'] as String) && trajectory == null) {
        _nextTrajectory = 0;
        error = 'Orbit preview unavailable: $exception';
        notifyListeners();
      }
    }
  }

  Future<void> connect({JsonMap? initial}) async {
    if (_closed || connecting) return;
    connecting = true;
    final generation = ++_generation;
    _historyRequest++;
    historyLoading = false;
    historyError = null;
    _pendingCatalogs.clear();
    datasetsLoading = false;
    _reconnect?.cancel();
    _demoRefresh?.cancel();
    _demoRefresh = null;
    _socket?.sink.close();
    playback.connected = false;
    _clearSession();
    trajectory = null;
    _nextTrajectory = 0;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final bootstrap = ViewerBootstrap.fromJson(
        initial ?? await _request('/v1/viewer/session'),
      ).toJson();
      if (generation != _generation) return;
      final operatorId = (bootstrap['operator'] as Map?)?['user_id'] as String?;
      if (_operatorUserId != null && operatorId != _operatorUserId) {
        suspend();
        onSessionExpired?.call();
        return;
      }
      _operatorUserId = operatorId;
      _token = bootstrap['csrf_token'] as String;
      _lastToken = _token;
      _allowedActions = (bootstrap['allowed_actions'] as List<dynamic>)
          .cast<String>()
          .toSet();
      _publicDemoSession = _allowedActions.isEmpty;
      _ingest(Map<String, dynamic>.from(bootstrap['run'] as Map), []);
      final id = status!['run_id'] as String;
      await _snapshot(generation, id);
      if (!_current(generation, id)) return;
      unawaited(loadDatasets());
      try {
        final configuration = await _request('/v1/viewer/configuration');
        if (_current(generation, id)) {
          editableSatellites = (configuration['satellites'] as List)
              .map((item) => Map<String, dynamic>.from(item as Map))
              .toList();
        }
      } catch (_) {
        if (_current(generation, id)) editableSatellites = null;
      }
      if (_current(generation, id)) _openSocket(generation, id);
    } catch (exception) {
      if (generation == _generation) error = '$exception';
    } finally {
      if (generation == _generation) {
        connecting = false;
        busy = false;
        if (status != null) _scheduleDemoRefresh(status!);
        notifyListeners();
      }
    }
  }

  void _openSocket(int generation, String id) {
    if (!_current(generation, id)) return;
    final uri = Uri.base
        .resolve('/v1/runs/$id/visual')
        .replace(scheme: Uri.base.scheme == 'https' ? 'wss' : 'ws');
    final channel = WebSocketChannel.connect(uri);
    _socket = channel;
    channel.ready
        .then((_) {
          if (!_current(generation, id)) return;
          playback.connected = true;
          _backoff = 1000;
          error = null;
          notifyListeners();
        })
        .catchError((Object _) {});
    channel.stream.listen(
      (data) {
        if (!_current(generation, id) || data is! String) return;
        try {
          final message = VisualMessage.fromJson(
            jsonDecode(data) as JsonMap,
          ).toJson();
          if (message['visual_schema_version'] != 'visual.v1' ||
              message['run_id'] != id) {
            return;
          }
          if (message['type'] == 'resync_required') {
            _snapshot(generation, id).catchError((Object e) {
              if (_current(generation, id)) {
                error = '$e';
                notifyListeners();
              }
            });
          } else if (message['type'] == 'error') {
            playback.connected = false;
            _clearSession();
            error = message['message'] as String? ?? 'Simulation stream error';
            notifyListeners();
          } else if (message['status'] != null &&
              message['status']['run_id'] == id) {
            _ingest(
              Map<String, dynamic>.from(message['status'] as Map),
              message['frames'] as List,
            );
          }
        } catch (_) {
          /* Malformed envelopes never reach committed state. */
        }
      },
      onError: (Object _) {},
      onDone: () {
        if (!_current(generation, id)) return;
        playback.connected = false;
        if ([1008, 4401, 4403].contains(channel.closeCode)) {
          suspend();
          onSessionExpired?.call();
          return;
        } else {
          _reconnect = Timer(Duration(milliseconds: _backoff), () async {
            try {
              await _snapshot(generation, id);
            } catch (_) {}
            _openSocket(generation, id);
          });
          _backoff = min(10000, _backoff * 2);
        }
        notifyListeners();
      },
    );
  }

  Future<void> control(String action, [int? speed]) async {
    if (busy || status == null || !canPerform(action)) return;
    final generation = _generation, id = status!['run_id'] as String;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final acknowledged = PublicRunStatus.fromJson(
        await _request(
          '/v1/runs/$id/control',
          body: {'action': action, 'speed': ?speed},
        ),
      ).toJson();
      if (_current(generation, id) && acknowledged['run_id'] == id) {
        await _snapshot(generation, id, acknowledged);
      }
    } catch (exception) {
      if (_current(generation, id)) error = '$exception';
    } finally {
      if (_current(generation, id)) {
        busy = false;
        notifyListeners();
      }
    }
  }

  /// Read only the authenticated operator's persisted shift records.
  Future<List<ShiftLog>> shiftLogs(String runId) async {
    if (!canUseShiftLog) throw StateError('Sign in to read your shift log.');
    final generation = _generation;
    final userId = _operatorUserId;
    final response = await _request('/v1/runs/$runId/shift-logs');
    if (!_current(generation, runId) || _operatorUserId != userId) {
      throw StateError('The session or run changed while loading shift logs.');
    }
    return ShiftLogList.fromJson(response).items;
  }

  /// Preserve the identity of an unchanged write when its outcome is uncertain.
  Future<void> writeShiftLog(
    String runId,
    String resource,
    JsonMap body,
  ) async {
    if (!canUseShiftLog || status?['run_id'] != runId) {
      throw StateError('This run is no longer active in your session.');
    }
    final path = '/v1/runs/$runId/shift-logs/$resource';
    final intent = '$path:${jsonEncode(body)}';
    final key = _shiftRetryKeys.putIfAbsent(
      intent,
      () =>
          '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(0x7fffffff)}',
    );
    await _request(path, body: body, idempotencyKey: key);
    _shiftRetryKeys.remove(intent);
  }

  /// Save a new run and report whether the editor can close successfully.
  Future<bool> replaceSatellites(List<JsonMap> satellites) async {
    if (_closed || busy || !canEdit || !canReplaceRun) return false;
    final generation = _generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final replacement = await _request(
        '/v1/viewer/configuration',
        body: {'satellites': satellites},
      );
      if (_closed || generation != _generation) return false;
      busy = false;
      await connect(initial: replacement);
      // The POST already committed; a refresh error must not invite a second save.
      return !_closed;
    } catch (exception) {
      if (_closed || generation != _generation) return false;
      error = '$exception';
      busy = false;
      notifyListeners();
      return false;
    }
  }

  /// Create an unstarted run for the selected producer without mixing sources.
  Future<void> selectSource(String source, {String? datasetId}) async {
    if (_closed || busy || !canReplaceRun) return;
    if (source == dataSource &&
        (source == 'physics' || datasetId == status?['dataset_id'])) {
      return;
    }
    final generation = _generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await _request(
        '/v1/viewer/source',
        body: {'data_source': source, 'dataset_id': ?datasetId},
      );
      if (_closed || generation != _generation) return;
      busy = false;
      await connect();
    } catch (exception) {
      if (_closed || generation != _generation) return;
      error = '$exception';
      busy = false;
      notifyListeners();
    }
  }

  /// Prepare a new recorded playback; starting it remains an explicit action.
  Future<bool> seekObserved(int elapsedSeconds) async {
    if (_closed || busy || !canControl || !isObserved) return false;
    final duration = status!['duration_s'] as int;
    if (elapsedSeconds < 0 || elapsedSeconds > duration) return false;
    final generation = _generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      final bootstrap = await _client.seek(elapsedSeconds, csrfToken: _token);
      if (_closed || generation != _generation) return false;
      await connect(initial: bootstrap);
      return !_closed &&
          _generation == generation + 1 &&
          error == null &&
          !connecting &&
          isObserved &&
          status?['run_id'] == (bootstrap['run'] as Map)['run_id'];
    } catch (exception) {
      if (_closed || generation != _generation) return false;
      if (exception is ViewerRequestException && exception.statusCode == 401) {
        suspend();
        onSessionExpired?.call();
        return false;
      }
      error = '$exception';
      busy = false;
      notifyListeners();
      return false;
    }
  }

  Future<void> reset() async {
    if (_closed || busy || !canReplaceRun) return;
    final generation = _generation;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await _request('/v1/viewer/reset', body: {});
      if (_closed || generation != _generation) return;
      busy = false;
      await connect();
    } catch (exception) {
      if (_closed || generation != _generation) return;
      error = '$exception';
      busy = false;
      notifyListeners();
    }
  }

  /// Stop transport and invalidate pending results before leaving the workspace.
  void suspend() {
    if (_closed) return;
    _closed = true;
    _generation++;
    _resetTelemetryHistory();
    _reconnect?.cancel();
    _demoRefresh?.cancel();
    _socket?.sink.close();
    _client.close();
    clock.stop();
    _clearSession();
    playback.connected = false;
    playback.status = null;
    playback.frames.clear();
    playback.history.clear();
    editableSatellites = null;
    trajectory = null;
    catalogs.clear();
    _pendingCatalogs.clear();
    _catalogErrors.clear();
    notifyListeners();
  }

  @override
  void dispose() {
    suspend();
    super.dispose();
  }
}
