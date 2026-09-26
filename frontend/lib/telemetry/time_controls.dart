import 'package:flutter/material.dart';
import 'panels.dart';

/// A validated UTC range or a trailing duration that follows live telemetry.
class TelemetryRangeSelection {
  const TelemetryRangeSelection(this.seconds, {this.end});
  final int seconds;
  final DateTime? end;
}

String rangeDuration(int seconds) {
  if (seconds % 3600 == 0) return '${seconds ~/ 3600} h';
  if (seconds % 60 == 0) return '${seconds ~/ 60} min';
  return '$seconds s';
}

String rangeTimestamp(DateTime time) =>
    time.toUtc().toIso8601String().substring(0, 19).replaceFirst('T', ' ');

/// Dashboard-wide time controls; these never issue simulation commands.
class TelemetryTimeControls extends StatelessWidget {
  const TelemetryTimeControls({
    super.key,
    required this.seconds,
    required this.start,
    required this.end,
    required this.epoch,
    required this.latest,
    required this.live,
    required this.loading,
    required this.onSelect,
    required this.onZoom,
    required this.onShift,
    required this.onToggleLive,
    required this.onReset,
    required this.onRefresh,
  });
  final int seconds;
  final DateTime? start, end, epoch, latest;
  final bool live, loading;
  final ValueChanged<TelemetryRangeSelection> onSelect;
  final ValueChanged<double> onZoom;
  final ValueChanged<int> onShift;
  final VoidCallback onToggleLive, onReset, onRefresh;

  Future<void> _picker(BuildContext context) async {
    final selected = await showDialog<TelemetryRangeSelection>(
      context: context,
      builder: (_) => _RangeDialog(
        seconds: seconds,
        start: start,
        end: end,
        epoch: epoch,
        latest: latest,
        live: live,
      ),
    );
    if (selected != null && context.mounted) onSelect(selected);
  }

  @override
  Widget build(BuildContext context) {
    final enabled = end != null && epoch != null && latest != null;
    Widget action(String tooltip, IconData icon, VoidCallback? callback) =>
        IconButton(
          tooltip: tooltip,
          visualDensity: VisualDensity.compact,
          onPressed: callback,
          icon: Icon(icon, size: 18),
        );
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 10),
      decoration: BoxDecoration(
        color: telemetrySurface,
        border: Border.all(color: telemetryBorder),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Wrap(
        spacing: 16,
        runSpacing: 10,
        crossAxisAlignment: WrapCrossAlignment.center,
        alignment: WrapAlignment.spaceBetween,
        children: [
          Wrap(
            spacing: 8,
            runSpacing: 8,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              OutlinedButton.icon(
                onPressed: () => _picker(context),
                icon: const Icon(Icons.schedule, size: 17),
                label: Text(
                  live ? 'Last ${rangeDuration(seconds)}' : 'Custom UTC range',
                ),
              ),
              PopupMenuButton<int>(
                tooltip: 'Quick time ranges',
                onSelected: (value) => onSelect(TelemetryRangeSelection(value)),
                itemBuilder: (_) => [
                  for (final value in [
                    60,
                    300,
                    900,
                    1800,
                    3600,
                    10800,
                    21600,
                    86400,
                  ])
                    PopupMenuItem(
                      value: value,
                      child: Text('Last ${rangeDuration(value)}'),
                    ),
                ],
                icon: const Icon(Icons.expand_more, size: 18),
              ),
              if (start != null && end != null)
                Text(
                  '${utcTime(start!, date: true)} to ${utcTime(end!, date: start!.day != end!.day)} UTC',
                  style: const TextStyle(fontSize: 11, color: telemetryMuted),
                ),
            ],
          ),
          Wrap(
            spacing: 3,
            runSpacing: 6,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              action(
                'Previous time window',
                Icons.chevron_left,
                enabled && start!.isAfter(epoch!) ? () => onShift(-1) : null,
              ),
              action(
                'Zoom in time range',
                Icons.zoom_in,
                enabled && seconds > 1 ? () => onZoom(.5) : null,
              ),
              action(
                'Zoom out time range',
                Icons.zoom_out,
                enabled && seconds < 86400 ? () => onZoom(2) : null,
              ),
              action(
                'Next time window',
                Icons.chevron_right,
                enabled && !live && end!.isBefore(latest!)
                    ? () => onShift(1)
                    : null,
              ),
              action('Reset time range', Icons.restart_alt, onReset),
              const SizedBox(width: 8),
              OutlinedButton.icon(
                onPressed: enabled ? onToggleLive : null,
                style: OutlinedButton.styleFrom(
                  foregroundColor: live ? telemetryAccent : telemetryMuted,
                ),
                icon: Icon(live ? Icons.pause : Icons.play_arrow, size: 16),
                label: Text(live ? 'Following live' : 'Follow live'),
              ),
              action(
                'Refresh selected history',
                loading || !enabled ? Icons.sync : Icons.refresh,
                loading || !enabled ? null : onRefresh,
              ),
            ],
          ),
        ],
      ),
    );
  }
}

class _RangeDialog extends StatefulWidget {
  const _RangeDialog({
    required this.seconds,
    required this.start,
    required this.end,
    required this.epoch,
    required this.latest,
    required this.live,
  });
  final int seconds;
  final DateTime? start, end, epoch, latest;
  final bool live;
  @override
  State<_RangeDialog> createState() => _RangeDialogState();
}

class _RangeDialogState extends State<_RangeDialog> {
  final _form = GlobalKey<FormState>();
  late bool _absolute = !widget.live;
  late final _minutes = TextEditingController(
    text: (widget.seconds / 60).toStringAsFixed(
      widget.seconds % 60 == 0 ? 0 : 2,
    ),
  );
  late final _from = TextEditingController(
    text: widget.start == null ? '' : rangeTimestamp(widget.start!),
  );
  late final _to = TextEditingController(
    text: widget.end == null ? '' : rangeTimestamp(widget.end!),
  );
  String? _error;

  @override
  void dispose() {
    _minutes.dispose();
    _from.dispose();
    _to.dispose();
    super.dispose();
  }

  DateTime? _parse(String value) {
    final input = value.trim();
    // Require an explicit whole-second UTC calendar timestamp, not local time.
    if (!RegExp(
      r'^\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}Z?$',
    ).hasMatch(input)) {
      return null;
    }
    final normalized = input.replaceFirst(' ', 'T').replaceAll('Z', '');
    final parsed = DateTime.tryParse('${normalized}Z');
    if (parsed == null ||
        parsed.toIso8601String().substring(0, 19) != normalized) {
      return null;
    }
    return parsed;
  }

  void _apply() {
    if (!_form.currentState!.validate()) return;
    if (!_absolute) {
      final seconds = (double.parse(_minutes.text.trim()) * 60).round();
      Navigator.pop(context, TelemetryRangeSelection(seconds));
      return;
    }
    final start = _parse(_from.text)!;
    final end = _parse(_to.text)!;
    final width = end.difference(start).inSeconds;
    if (widget.epoch == null ||
        widget.latest == null ||
        start.isBefore(widget.epoch!) ||
        end.isAfter(widget.latest!) ||
        width < 1 ||
        width > 86400) {
      setState(
        () => _error =
            'Choose 1 second to 24 hours within the committed run, with From before To.',
      );
      return;
    }
    Navigator.pop(context, TelemetryRangeSelection(width, end: end));
  }

  @override
  Widget build(BuildContext context) {
    final width = MediaQuery.sizeOf(context).width;
    return AlertDialog(
      insetPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 16),
      title: const Text('Time range'),
      content: SizedBox(
        width: (width - 32).clamp(220, 480).toDouble(),
        child: SingleChildScrollView(
          child: Form(
            key: _form,
            child: Column(
              mainAxisSize: MainAxisSize.min,
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                SegmentedButton<bool>(
                  segments: const [
                    ButtonSegment(value: false, label: Text('Relative')),
                    ButtonSegment(value: true, label: Text('Absolute UTC')),
                  ],
                  selected: {_absolute},
                  onSelectionChanged: (value) => setState(() {
                    _absolute = value.single;
                    _error = null;
                  }),
                ),
                const SizedBox(height: 20),
                if (!_absolute) ...[
                  Wrap(
                    spacing: 8,
                    runSpacing: 8,
                    children: [
                      for (final value in [
                        60,
                        300,
                        900,
                        1800,
                        3600,
                        10800,
                        21600,
                        86400,
                      ])
                        ActionChip(
                          label: Text('Last ${rangeDuration(value)}'),
                          onPressed: () => Navigator.pop(
                            context,
                            TelemetryRangeSelection(value),
                          ),
                        ),
                    ],
                  ),
                  const SizedBox(height: 20),
                  TextFormField(
                    controller: _minutes,
                    keyboardType: const TextInputType.numberWithOptions(
                      decimal: true,
                    ),
                    decoration: const InputDecoration(
                      labelText: 'Last (minutes)',
                      helperText: 'Up to 1440 minutes; decimals allowed',
                    ),
                    validator: (value) {
                      final amount = double.tryParse(value?.trim() ?? '');
                      return amount == null ||
                              !amount.isFinite ||
                              amount * 60 < 1 ||
                              amount > 1440
                          ? 'Enter a duration from 1 second to 24 hours.'
                          : null;
                    },
                    onFieldSubmitted: (_) => _apply(),
                  ),
                ] else ...[
                  for (final field in [(_from, 'From UTC'), (_to, 'To UTC')])
                    Padding(
                      padding: const EdgeInsets.only(bottom: 18),
                      child: TextFormField(
                        controller: field.$1,
                        decoration: InputDecoration(
                          labelText: field.$2,
                          hintText: 'YYYY-MM-DD HH:mm:ss',
                        ),
                        validator: (value) => _parse(value ?? '') == null
                            ? 'Use YYYY-MM-DD HH:mm:ss in UTC.'
                            : null,
                        onFieldSubmitted: (_) => _apply(),
                      ),
                    ),
                  if (widget.epoch != null && widget.latest != null)
                    Text(
                      'Available: ${rangeTimestamp(widget.epoch!)} to ${rangeTimestamp(widget.latest!)} UTC',
                      style: const TextStyle(
                        fontSize: 11,
                        color: telemetryMuted,
                      ),
                    ),
                  if (widget.epoch != null &&
                      widget.latest != null &&
                      widget.latest!.isAfter(widget.epoch!))
                    TextButton(
                      onPressed: () {
                        _from.text = rangeTimestamp(widget.epoch!);
                        _to.text = rangeTimestamp(widget.latest!);
                      },
                      child: const Text('Use entire committed run'),
                    ),
                ],
                if (_error != null)
                  Padding(
                    padding: const EdgeInsets.only(top: 12),
                    child: Text(
                      _error!,
                      style: TextStyle(
                        color: Theme.of(context).colorScheme.error,
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.pop(context),
          child: const Text('Cancel'),
        ),
        FilledButton(onPressed: _apply, child: const Text('Apply range')),
      ],
    );
  }
}
