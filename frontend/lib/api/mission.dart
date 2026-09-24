import 'dart:async';
import 'dart:convert';
import 'dart:math';
import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;
import 'package:web_socket_channel/web_socket_channel.dart';
import '../scene/playback.dart';
import 'generated.dart';

/// Owns session, committed snapshots, reconnects, and guarded run controls.
class Mission extends ChangeNotifier {
  final CommittedPlayback playback = CommittedPlayback();
  final Stopwatch clock = Stopwatch()..start();
  JsonMap? trajectory;
  List<JsonMap>? editableSatellites;
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

  Future<JsonMap> _request(String path, {JsonMap? body}) async {
    final uri = Uri.base.resolve(path);
    final response = body == null
        ? await http.get(uri)
        : await http.post(
            uri,
            headers: {
              'Content-Type': 'application/json',
              'X-CSRF-Token': _token,
              'Idempotency-Key':
                  '${DateTime.now().microsecondsSinceEpoch}-${Random.secure().nextInt(0x7fffffff)}',
            },
            body: jsonEncode(body),
          );
    final decoded = jsonDecode(response.body);
    if (response.statusCode >= 400) {
      final detail = decoded is Map ? decoded['detail'] : null;
      throw Exception(
        decoded is Map && decoded['message'] is String
            ? decoded['message']
            : detail is String
            ? detail
            : detail is Map
            ? detail['message']
            : 'Request failed (${response.statusCode})',
      );
    }
    return Map<String, dynamic>.from(decoded as Map);
  }

  bool _current(int generation, String id) =>
      _generation == generation && status?['run_id'] == id;

  void _ingest(JsonMap next, List<dynamic> incoming) {
    playback.ingest(
      next,
      incoming.map((f) => Map<String, dynamic>.from(f as Map)).toList(),
      now,
    );
    _scheduleDemoRefresh(next);
    notifyListeners();
    if (next['committed_tick'] >= _nextTrajectory &&
        next['committed_tick'] < next['duration_s']) {
      _loadTrajectory(_generation, next);
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
  }

  Future<void> _loadTrajectory(int generation, JsonMap run) async {
    final from = max(0, run['committed_tick'] as int);
    _nextTrajectory = (from ~/ 1800 + 1) * 1800;
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

  Future<void> connect() async {
    if (connecting) return;
    connecting = true;
    final generation = ++_generation;
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
        await _request('/v1/viewer/bootstrap'),
      ).toJson();
      if (generation != _generation) return;
      _token = bootstrap['csrf_token'] as String;
      _allowedActions = (bootstrap['allowed_actions'] as List<dynamic>)
          .cast<String>()
          .toSet();
      _publicDemoSession = _allowedActions.isEmpty;
      _ingest(Map<String, dynamic>.from(bootstrap['run'] as Map), []);
      final id = status!['run_id'] as String;
      await _snapshot(generation, id);
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
          _clearSession();
          error = 'Mission session expired. Reconnect to continue.';
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

  Future<void> replaceSatellites(List<JsonMap> satellites) async {
    if (busy || !canEdit || !canReplaceRun) return;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await _request(
        '/v1/viewer/configuration',
        body: {'satellites': satellites},
      );
      busy = false;
      await connect();
    } catch (exception) {
      error = '$exception';
      busy = false;
      notifyListeners();
    }
  }

  Future<void> reset() async {
    if (busy || !canReplaceRun) return;
    busy = true;
    error = null;
    notifyListeners();
    try {
      await _request('/v1/viewer/reset', body: {});
      busy = false;
      await connect();
    } catch (exception) {
      error = '$exception';
      busy = false;
      notifyListeners();
    }
  }

  @override
  void dispose() {
    _generation++;
    _reconnect?.cancel();
    _demoRefresh?.cancel();
    _socket?.sink.close();
    super.dispose();
  }
}
