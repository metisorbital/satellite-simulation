import 'package:flutter_test/flutter_test.dart';
import 'package:metis_orbital_viewer/scene/playback.dart';

JsonMap status({
  String run = 'one',
  String state = 'running',
  int tick = 10,
  int revision = 1,
}) => {
  'run_id': run,
  'status': state,
  'committed_tick': tick,
  'status_revision': revision,
  'epoch_utc': '2026-01-01T00:00:00Z',
  'requested_speed': 20,
  'effective_speed': 20,
  'satellites': [
    {'satellite_id': 'SAT-1', 'stream_id': 'stream'},
  ],
};
JsonMap frame(int tick) => {
  'stream_id': 'stream',
  'sequence': tick,
  'observed_at': DateTime.utc(
    2026,
  ).add(Duration(seconds: tick)).toIso8601String(),
  'channels': {
    'eps.battery_soc': {'quality': 'valid', 'value': .8},
  },
};
void main() {
  test('clock clamps to committed samples and freezes stale data', () {
    final p = CommittedPlayback()..connected = true;
    p.ingest(status(), List.generate(11, frame), 0);
    expect(p.time(500), 10);
    expect(p.time(2000), 10);
    expect(p.isStale(2000), isTrue);
  });
  test('pause drains clock and old acknowledgments cannot regress status', () {
    final p = CommittedPlayback()..connected = true;
    p.ingest(status(state: 'paused', revision: 2), List.generate(11, frame), 0);
    p.ingest(status(revision: 1), [], 100);
    expect(p.status!['status'], 'paused');
    expect(p.time(100), 10);
  });
  test(
    'run change clears samples and never paints previous spacecraft state',
    () {
      final p = CommittedPlayback();
      p.ingest(status(), List.generate(11, frame), 0);
      p.ingest(status(run: 'two', tick: -1), [], 1);
      expect(p.bounds, isNull);
      expect(p.frameAt('SAT-1', 10), isNull);
    },
  );
  test('future samples rejected and buffers bounded', () {
    final p = CommittedPlayback();
    p.ingest(status(tick: 1000), List.generate(1002, frame), 0);
    expect(p.frames['SAT-1']!.length, 41);
    expect(p.history['SAT-1']!.length, 600);
    expect(p.frames['SAT-1']!.last['sequence'], 1000);
  });
  test('invalid scalars remain unavailable', () {
    expect(
      scalar({
        'channels': {
          'x': {'quality': 'invalid', 'value': 9},
        },
      }, 'x'),
      isNull,
    );
    expect(
      scalar({
        'channels': {
          'x': {'quality': 'saturated', 'value': 9},
        },
      }, 'x'),
      9,
    );
  });
  test('all spacecraft share the intersection of committed buffers', () {
    final p = CommittedPlayback()..connected = true;
    final next = status();
    (next['satellites'] as List).add({
      'satellite_id': 'SAT-2',
      'stream_id': 'second',
    });
    p.ingest(next, List.generate(11, frame), 0);
    expect(p.bounds, isNull);
    p.ingest(next, [
      for (var i = 4; i <= 8; i++) {...frame(i), 'stream_id': 'second'},
    ], 1);
    expect(p.bounds, (4.0, 8.0));
    expect(p.time(500), 8);
  });
  test('disconnect freezes at the previously displayed time', () {
    final p = CommittedPlayback()..connected = true;
    p.ingest(status(), List.generate(11, frame), 0);
    final before = p.time(100);
    p.connected = false;
    expect(p.time(300), before);
  });
  test('sample lookup never crosses a telemetry gap', () {
    final p = CommittedPlayback();
    p.ingest(status(state: 'paused'), [frame(0), frame(10)], 0);
    expect(p.frameAt('SAT-1', 5), isNull);
    expect(p.frameAt('SAT-1', 10)!['sequence'], 10);
  });
  test('older snapshot cannot roll back a newer committed tick', () {
    final p = CommittedPlayback();
    p.ingest(status(tick: 10), List.generate(11, frame), 0);
    p.ingest(status(tick: 5, revision: 99), List.generate(6, frame), 10);
    expect(p.status!['committed_tick'], 10);
    expect(p.frames['SAT-1']!.length, 11);
  });
  test('wrong-stream samples cannot enter a spacecraft buffer', () {
    final p = CommittedPlayback();
    p.ingest(status(), [
      {...frame(10), 'stream_id': 'unrelated'},
    ], 0);
    expect(p.bounds, isNull);
    expect(p.history['SAT-1'], isEmpty);
  });
}
