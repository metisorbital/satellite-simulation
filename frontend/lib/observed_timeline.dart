import 'package:flutter/material.dart';

import 'api/mission.dart';
import 'telemetry/panels.dart';

/// Selects an original source time without reading or inventing future telemetry.
class ObservedTimeline extends StatefulWidget {
  const ObservedTimeline({super.key, required this.mission});

  final Mission mission;

  @override
  State<ObservedTimeline> createState() => _ObservedTimelineState();
}

class _ObservedTimelineState extends State<ObservedTimeline> {
  String? _runId;
  int? _draft;
  bool _applying = false;
  String? _notice;

  Future<void> _apply(int target, DateTime epoch) async {
    final mission = widget.mission;
    setState(() {
      _applying = true;
      _notice = null;
    });
    final positioned = await mission.seekObserved(target);
    if (!mounted) return;
    setState(() {
      _applying = false;
      // A failed snapshot can still install the new run; retain this draft.
      _runId = mission.status?['run_id'] as String?;
      if (positioned) {
        final actual = mission.status!['playback_start_s'] as int? ?? 0;
        _draft = null;
        _notice = actual > target
            ? 'No measurement at the requested time. Moved forward to '
                  '${utcTime(epoch.add(Duration(seconds: actual)), date: true)}. '
                  'Press Start run to begin here.'
            : 'Position ready. Press Start run to begin here.';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    final mission = widget.mission;
    final run = mission.status;
    if (!mission.isObserved || run == null) return const SizedBox.shrink();
    final runId = run['run_id'] as String;
    if (_runId != runId && !_applying) {
      _runId = runId;
      _draft = null;
      _notice = null;
    }
    final epoch = DateTime.parse(run['epoch_utc'] as String).toUtc();
    final duration = run['duration_s'] as int;
    final committed = run['committed_tick'] as int? ?? -1;
    final current = committed >= 0
        ? committed
        : run['playback_start_s'] as int? ?? 0;
    final target = (_draft ?? current).clamp(0, duration);
    final enabled = mission.canControl && !mission.busy && !_applying;
    String timestamp(int seconds) =>
        utcTime(epoch.add(Duration(seconds: seconds)), date: true);

    void choose(int value) => setState(() {
      _draft = value;
      _notice = null;
    });
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 8),
      color: telemetrySurface,
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 18,
            runSpacing: 3,
            children: [
              Text(
                'Replay: ${timestamp(current)}',
                style: const TextStyle(fontSize: 10, color: telemetryAccent),
              ),
              Text(
                'Target: ${timestamp(target)}',
                style: const TextStyle(fontSize: 10),
              ),
            ],
          ),
          Row(
            children: [
              IconButton(
                tooltip: 'First sample',
                onPressed: enabled ? () => choose(0) : null,
                icon: const Icon(Icons.first_page, size: 18),
              ),
              Expanded(
                child: Slider(
                  value: target.toDouble(),
                  max: duration.toDouble(),
                  label: timestamp(target),
                  semanticFormatterCallback: (value) =>
                      timestamp(value.round()),
                  onChangeStart: enabled
                      ? (value) => choose(value.round())
                      : null,
                  onChanged: enabled ? (value) => choose(value.round()) : null,
                ),
              ),
              IconButton(
                tooltip: 'Last sample',
                onPressed: enabled ? () => choose(duration) : null,
                icon: const Icon(Icons.last_page, size: 18),
              ),
              TextButton(
                onPressed: enabled && _draft != null
                    ? () => _apply(target, epoch)
                    : null,
                child: Text(_applying ? 'Positioning…' : 'Apply position'),
              ),
              if (_draft != null)
                IconButton(
                  tooltip: 'Cancel position',
                  onPressed: enabled
                      ? () => setState(() => _draft = null)
                      : null,
                  icon: const Icon(Icons.close, size: 16),
                ),
            ],
          ),
          Text(
            '${timestamp(0)} → ${timestamp(duration)}',
            style: const TextStyle(fontSize: 9, color: telemetryMuted),
          ),
          const SizedBox(height: 3),
          Text(
            _notice ??
                'Apply stops replay; press Start run afterward. Gaps move to the next measurement.',
            style: TextStyle(
              fontSize: 9,
              color: _notice == null ? telemetryMuted : telemetryAccent,
            ),
          ),
        ],
      ),
    );
  }
}
