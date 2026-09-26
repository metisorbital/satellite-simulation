import 'dart:math' as math;

typedef JsonMap = Map<String, dynamic>;

/// Return usable scalar telemetry, retaining saturation quality.
double? scalar(JsonMap? frame, String channel) {
  final reading = frame?['channels']?[channel];
  if (reading is! Map || ['invalid', 'missing'].contains(reading['quality'])) {
    return null;
  }
  final value = reading['value'];
  return value is num && value.isFinite ? value.toDouble() : null;
}

double frameSeconds(JsonMap frame, JsonMap status) =>
    DateTime.parse(
      frame['observed_at'] as String,
    ).difference(DateTime.parse(status['epoch_utc'] as String)).inMicroseconds /
    1000000;

bool isStatusOlder(JsonMap candidate, JsonMap current) =>
    candidate['committed_tick'] < current['committed_tick'] ||
    (candidate['committed_tick'] == current['committed_tick'] &&
        (candidate['status_revision'] ?? 0) <
            (current['status_revision'] ?? 0));

/// Bounded committed-only presentation clock; never predicts orbital dynamics.
class CommittedPlayback {
  JsonMap? status;
  int revision = 0;
  final Map<String, List<JsonMap>> frames = {};
  final Map<String, List<JsonMap>> history = {};
  final Map<String, int> _historyLimits = {};
  bool connected = false;

  /// Reserve the selected time window plus the committed playback lag buffer.
  void retainHistory(String satelliteId, int seconds) {
    _historyLimits
      ..clear()
      ..[satelliteId] = seconds + 41;
    for (final id in history.keys.toList()) {
      final buffer = history[id]!;
      history[id] = buffer
          .skip(math.max(0, buffer.length - (_historyLimits[id] ?? 600)))
          .toList();
    }
  }

  /// Merge committed replay without changing the live clock or orbit buffer.
  void mergeHistory(List<JsonMap> incoming) {
    final current = status;
    if (current == null) return;
    for (final satellite in current['satellites'] as List) {
      final id = satellite['satellite_id'] as String;
      final accepted = incoming.where(
        (frame) =>
            frame['stream_id'] == satellite['stream_id'] &&
            frame['sequence'] is int &&
            frame['sequence'] >= 0 &&
            frameSeconds(frame, current) <= current['committed_tick'],
      );
      if (accepted.isEmpty) continue;
      final merged = <int, JsonMap>{
        for (final frame in history[id] ?? <JsonMap>[])
          frame['sequence'] as int: frame,
        for (final frame in accepted) frame['sequence'] as int: frame,
      };
      final ordered = merged.values.toList()
        ..sort(
          (a, b) => (a['sequence'] as int).compareTo(b['sequence'] as int),
        );
      history[id] = ordered
          .skip(math.max(0, ordered.length - (_historyLimits[id] ?? 600)))
          .toList();
    }
  }

  double _anchorWall = 0, _anchorSeconds = 0, _lastAdvance = 0;
  double? _displayed;
  int _lastTick = -1;

  void ingest(JsonMap next, List<JsonMap> incoming, double now) {
    if (status?['run_id'] != next['run_id']) {
      frames.clear();
      history.clear();
      _displayed = null;
      _lastTick = -1;
    } else if (status != null && isStatusOlder(next, status!)) {
      next = status!;
    }
    status = next;
    revision++;
    mergeHistory(incoming);
    for (final satellite in next['satellites'] as List) {
      final id = satellite['satellite_id'] as String;
      final ordered = history[id] ?? <JsonMap>[];
      history.putIfAbsent(id, () => <JsonMap>[]);
      frames[id] = ordered.skip(math.max(0, ordered.length - 41)).toList();
    }
    if (next['committed_tick'] > _lastTick) {
      _lastAdvance = now;
      _lastTick = next['committed_tick'] as int;
    }
    final range = bounds;
    if (range == null) return;
    _anchorWall = now;
    _anchorSeconds = math.max(range.$1, range.$2 - speed * .35);
    _displayed ??= _anchorSeconds;
    if (next['status'] != 'running') _displayed = range.$2;
  }

  double get speed {
    final effective = (status?['effective_speed'] as num?)?.toDouble() ?? 0;
    return math.max(
      0,
      effective > 0
          ? effective
          : (status?['requested_speed'] as num? ?? 90).toDouble(),
    );
  }

  (double, double)? get bounds {
    if (status == null || (status!['satellites'] as List).isEmpty) return null;
    var start = 0.0;
    var end = (status!['committed_tick'] as num).toDouble();
    // Source gaps advance the replay clock without repeating the last reading.
    if (status!['source_kind'] == 'observed') {
      return end < 0 ? null : (0, end);
    }
    for (final satellite in status!['satellites'] as List) {
      final buffer = frames[satellite['satellite_id']];
      if (buffer == null || buffer.isEmpty) return null;
      start = math.max(start, frameSeconds(buffer.first, status!));
      end = math.min(end, frameSeconds(buffer.last, status!));
    }
    return end < start ? null : (start, end);
  }

  bool isStale(double now) =>
      !connected ||
      (status?['status'] == 'running' && now - _lastAdvance > 1500);

  double? time(double now) {
    final range = bounds;
    if (range == null) return null;
    if (status!['status'] != 'running') return _displayed = range.$2;
    if (isStale(now)) return _displayed;
    final proposed =
        _anchorSeconds + math.max(0, now - _anchorWall) / 1000 * speed;
    return _displayed = math.min(
      range.$2,
      math.max(range.$1, math.max(_displayed ?? range.$1, proposed)),
    );
  }

  JsonMap? frameAt(String id, double? seconds) {
    if (seconds == null || status == null) return null;
    final cadence = (status?['nominal_cadence_s'] as num?)?.toDouble() ?? 1;
    for (final frame in (frames[id] ?? <JsonMap>[]).reversed) {
      final lag = seconds - frameSeconds(frame, status!);
      final withinSample = status?['source_kind'] == 'observed'
          ? lag < cadence
          : lag <= cadence + 1e-7;
      if (lag >= -1e-7 && withinSample) return frame;
    }
    return null;
  }
}
