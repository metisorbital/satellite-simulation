import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/material.dart';

import '../scene/playback.dart';
import 'panels.dart';

/// Catalog-backed telemetry with one shared UTC range and quality-aware lines.
class TelemetryChart extends StatefulWidget {
  const TelemetryChart({
    super.key,
    required this.panel,
    required this.definitions,
    required this.frames,
    required this.current,
    required this.windowSeconds,
    required this.end,
    this.expanded = false,
    this.onExpand,
    this.onRangeSelected,
    this.onResetRange,
    this.headerActions,
    this.observed = false,
    this.nominalCadenceSeconds = 1,
  });
  final TelemetryPanel panel;
  final Map<String, JsonMap> definitions;
  final List<JsonMap> frames;
  final JsonMap? current;
  final int windowSeconds;
  final DateTime? end;
  final bool expanded;
  final VoidCallback? onExpand;
  final void Function(DateTime start, DateTime end)? onRangeSelected;
  final VoidCallback? onResetRange;
  final Widget? headerActions;
  final bool observed;
  final double nominalCadenceSeconds;

  @override
  State<TelemetryChart> createState() => _TelemetryChartState();
}

class _TelemetryChartState extends State<TelemetryChart> {
  static const _leftAxis = 54.0;
  static const _bottomAxis = 27.0;
  final Set<String> _hidden = {};
  double? _hoverFraction;
  double? _dragStart;
  double? _dragEnd;
  DateTime? _dragRangeEnd;
  int? _dragRangeSeconds;
  JsonMap? _dragCurrent;

  DateTime? get _rangeEnd => _dragRangeEnd ?? widget.end;
  int get _rangeSeconds => _dragRangeSeconds ?? widget.windowSeconds;
  DateTime? _resetEnd;
  int? _resetSeconds;
  late _ChartGeometry _geometry;
  LineChartData? _cachedChartData;
  double? _cachedChartWidth;
  String? _cachedVisibleSeries;

  @override
  void initState() {
    super.initState();
    _rebuildGeometry();
  }

  @override
  void didUpdateWidget(TelemetryChart oldWidget) {
    super.didUpdateWidget(oldWidget);
    // Keep axes, points and selection aligned while the live clock advances.
    if (_dragRangeEnd != null) return;
    if (!identical(oldWidget.frames, widget.frames) ||
        oldWidget.end != widget.end ||
        oldWidget.windowSeconds != widget.windowSeconds ||
        oldWidget.observed != widget.observed ||
        oldWidget.nominalCadenceSeconds != widget.nominalCadenceSeconds ||
        oldWidget.panel != widget.panel ||
        !identical(oldWidget.definitions, widget.definitions)) {
      _rebuildGeometry();
    }
  }

  void _rebuildGeometry() {
    _geometry = _ChartGeometry(
      panelSeries(widget.panel, widget.definitions),
      widget.frames,
      widget.end,
      widget.windowSeconds,
      widget.observed ? widget.nominalCadenceSeconds : null,
    );
    _invalidateChartData();
  }

  void _invalidateChartData() {
    _cachedChartData = null;
    _cachedChartWidth = null;
    _cachedVisibleSeries = null;
  }

  String _key(TelemetrySeries item) => '${item.channel}:${item.component}';

  DateTime _instant(double fraction) => _rangeEnd!.subtract(
    Duration(milliseconds: (_rangeSeconds * 1000 * (1 - fraction)).round()),
  );

  void _select(double start, double end) {
    if (_rangeEnd == null || widget.onRangeSelected == null) return;
    _resetEnd ??= _rangeEnd;
    _resetSeconds ??= _rangeSeconds;
    widget.onRangeSelected!(_instant(start), _instant(end));
  }

  void _clearDrag() => setState(() {
    _dragStart = null;
    _dragEnd = null;
    _dragRangeEnd = null;
    _dragRangeSeconds = null;
    _dragCurrent = null;
    _hoverFraction = null;
    _rebuildGeometry();
  });

  void _zoom(double factor) => _select(.5 - factor / 2, .5 + factor / 2);

  void _reset() {
    if (widget.onResetRange != null) {
      widget.onResetRange!();
    } else if (_resetEnd != null && _resetSeconds != null) {
      widget.onRangeSelected?.call(
        _resetEnd!.subtract(Duration(seconds: _resetSeconds!)),
        _resetEnd!,
      );
    }
    _resetEnd = null;
    _resetSeconds = null;
  }

  void _toggleSeries(TelemetrySeries item) => setState(() {
    final key = _key(item);
    if (!_hidden.remove(key)) _hidden.add(key);
    _invalidateChartData();
  });

  JsonMap? _inspected() {
    if (_hoverFraction == null) {
      return _dragRangeEnd == null ? widget.current : _dragCurrent;
    }
    if (_rangeEnd == null || _geometry.frames.isEmpty) return null;
    final target = _instant(_hoverFraction!).millisecondsSinceEpoch;
    var lo = 0;
    var hi = _geometry.times.length;
    while (lo < hi) {
      final mid = (lo + hi) ~/ 2;
      if (_geometry.times[mid] < target) {
        lo = mid + 1;
      } else {
        hi = mid;
      }
    }
    var index = math.min(lo, _geometry.times.length - 1);
    if (index > 0 &&
        (target - _geometry.times[index - 1]).abs() <
            (target - _geometry.times[index]).abs()) {
      index--;
    }
    final cadence = widget.observed
        ? widget.nominalCadenceSeconds
        : _geometry.series.isEmpty
        ? 1.0
        : (_geometry.series.first.definition['cadence_s'] as num).toDouble();
    if ((_geometry.times[index] - target).abs() > cadence * 1500) return null;
    return _geometry.frames[index];
  }

  @override
  Widget build(BuildContext context) {
    final series = _geometry.series;
    final visible = series
        .where((item) => !_hidden.contains(_key(item)))
        .toList();
    final inspected = _inspected();
    final unsupported = widget.panel.channels
        .where(
          (id) =>
              widget.definitions[id] == null ||
              widget.definitions[id]!['availability'] == 'unavailable',
        )
        .toList();
    final explanation = widget.panel.channels
        .map((id) {
          final definition = widget.definitions[id];
          return definition == null
              ? '$id\nNot included in this catalog.'
              : '$id · ${definition['unit']}\n${definition['description']}\n'
                    '${definition['sampling_semantics']} · ${definition['cadence_s']} s cadence'
                    '${definition['coordinate_frame'] == null ? '' : ' · ${definition['coordinate_frame']}'}';
        })
        .join('\n\n');
    final interactive = widget.onRangeSelected != null && widget.end != null;
    return Container(
      decoration: BoxDecoration(
        color: telemetrySurface,
        border: Border.all(color: telemetryBorder),
        borderRadius: BorderRadius.circular(8),
      ),
      padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  widget.panel.title,
                  style: const TextStyle(
                    fontSize: 13,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              Tooltip(
                message: explanation,
                child: const Padding(
                  padding: EdgeInsets.symmetric(horizontal: 5),
                  child: Icon(
                    Icons.info_outline,
                    size: 15,
                    color: telemetryMuted,
                  ),
                ),
              ),
              if (widget.headerActions != null) widget.headerActions!,
              if (widget.onExpand != null)
                _action(
                  Icons.open_in_full,
                  'Expand ${widget.panel.title}',
                  widget.onExpand,
                ),
            ],
          ),
          if (series.isEmpty)
            Expanded(
              child: _Unavailable(
                channels: unsupported,
                definitions: widget.definitions,
                observed: widget.observed,
              ),
            )
          else ...[
            Row(
              children: [
                Text(
                  series.first.unit == '1'
                      ? 'Dimensionless'
                      : series.first.unit,
                  style: const TextStyle(fontSize: 10, color: telemetryMuted),
                ),
                const Spacer(),
                if (interactive) ...[
                  _action(Icons.add, 'Zoom in · all panels', () => _zoom(.5)),
                  _action(
                    Icons.remove,
                    'Zoom out · all panels',
                    () => _zoom(2),
                  ),
                  _action(
                    Icons.restart_alt,
                    'Reset time range · all panels',
                    _reset,
                  ),
                ],
              ],
            ),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final plotWidth = math.max(
                    1.0,
                    constraints.maxWidth - _leftAxis - 8,
                  );
                  double fraction(double x) =>
                      ((x - _leftAxis) / plotWidth).clamp(0.0, 1.0);
                  final plotHeight = math.max(
                    0.0,
                    constraints.maxHeight - _bottomAxis - 8,
                  );
                  return MouseRegion(
                    cursor: interactive
                        ? SystemMouseCursors.precise
                        : MouseCursor.defer,
                    onHover: (event) => setState(
                      () => _hoverFraction = fraction(event.localPosition.dx),
                    ),
                    onExit: (_) => setState(() => _hoverFraction = null),
                    child: GestureDetector(
                      behavior: HitTestBehavior.opaque,
                      onHorizontalDragStart: interactive
                          ? (details) => setState(() {
                              _dragRangeEnd = widget.end;
                              _dragRangeSeconds = widget.windowSeconds;
                              _dragCurrent = widget.current;
                              _dragStart = fraction(details.localPosition.dx);
                              _dragEnd = _dragStart;
                            })
                          : null,
                      onHorizontalDragUpdate: interactive
                          ? (details) => setState(() {
                              _dragEnd = fraction(details.localPosition.dx);
                            })
                          : null,
                      onHorizontalDragCancel: _clearDrag,
                      onHorizontalDragEnd: interactive
                          ? (_) {
                              final start = math.min(
                                _dragStart ?? 0,
                                _dragEnd ?? 0,
                              );
                              final end = math.max(
                                _dragStart ?? 0,
                                _dragEnd ?? 0,
                              );
                              if ((end - start) * plotWidth >= 8 &&
                                  (end - start) * _rangeSeconds >= 1) {
                                _select(start, end);
                              }
                              _clearDrag();
                            }
                          : null,
                      child: Stack(
                        children: [
                          Positioned.fill(
                            child: Padding(
                              padding: const EdgeInsets.only(top: 8, right: 8),
                              child: RepaintBoundary(
                                child: LineChart(
                                  _chartData(visible, plotWidth),
                                  duration: Duration.zero,
                                ),
                              ),
                            ),
                          ),
                          if (_hoverFraction != null)
                            Positioned(
                              left: _leftAxis + plotWidth * _hoverFraction!,
                              top: 8,
                              height: plotHeight,
                              child: IgnorePointer(
                                child: Container(
                                  width: 1,
                                  color: Colors.white.withValues(alpha: .35),
                                ),
                              ),
                            ),
                          if (_dragStart != null && _dragEnd != null)
                            Positioned(
                              left:
                                  _leftAxis +
                                  plotWidth * math.min(_dragStart!, _dragEnd!),
                              top: 8,
                              width:
                                  plotWidth * (_dragEnd! - _dragStart!).abs(),
                              height: plotHeight,
                              child: IgnorePointer(
                                child: Container(
                                  decoration: BoxDecoration(
                                    color: telemetryAccent.withValues(
                                      alpha: .16,
                                    ),
                                    border: Border.all(
                                      color: telemetryAccent.withValues(
                                        alpha: .7,
                                      ),
                                    ),
                                  ),
                                ),
                              ),
                            ),
                          if (_hoverFraction != null && _dragStart == null)
                            Positioned(
                              left: _hoverFraction! > .5 ? _leftAxis + 6 : null,
                              right: _hoverFraction! <= .5 ? 12 : null,
                              top: 12,
                              width: math.min(225, plotWidth - 12),
                              child: IgnorePointer(
                                child: Container(
                                  padding: const EdgeInsets.all(8),
                                  decoration: BoxDecoration(
                                    color: const Color(
                                      0xff080e16,
                                    ).withValues(alpha: .96),
                                    border: Border.all(color: telemetryBorder),
                                    borderRadius: BorderRadius.circular(4),
                                  ),
                                  child: Column(
                                    crossAxisAlignment:
                                        CrossAxisAlignment.start,
                                    children: [
                                      Text(
                                        inspected == null
                                            ? 'No sample here'
                                            : utcTime(
                                                sampleTime(inspected),
                                                date: true,
                                              ),
                                        style: const TextStyle(
                                          fontSize: 9,
                                          color: telemetryMuted,
                                        ),
                                      ),
                                      if (inspected != null) ...[
                                        const SizedBox(height: 5),
                                        for (final item in visible)
                                          Padding(
                                            padding: const EdgeInsets.symmetric(
                                              vertical: 2,
                                            ),
                                            child: Text(
                                              '${item.name}  ${item.display(inspected)} ${item.unit} · ${item.quality(inspected)}',
                                              maxLines: 2,
                                              overflow: TextOverflow.ellipsis,
                                              style: TextStyle(
                                                fontSize: 10,
                                                color: item.color,
                                              ),
                                            ),
                                          ),
                                      ],
                                    ],
                                  ),
                                ),
                              ),
                            ),
                          if (visible.isEmpty ||
                              !visible.any(
                                (item) => _geometry.values[item]!.low.isFinite,
                              ))
                            Positioned.fill(
                              child: IgnorePointer(
                                child: Center(
                                  child: Text(
                                    visible.isEmpty
                                        ? 'Select a series below'
                                        : 'No valid measurements in this window',
                                    style: const TextStyle(
                                      fontSize: 11,
                                      color: telemetryMuted,
                                    ),
                                    textAlign: TextAlign.center,
                                  ),
                                ),
                              ),
                            ),
                        ],
                      ),
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 5),
            Text(
              inspected == null
                  ? (_hoverFraction == null
                        ? 'Awaiting sample'
                        : 'No sample here')
                  : '${utcTime(sampleTime(inspected), date: true)}${_hoverFraction == null ? '' : ' · inspected'}',
              maxLines: 1,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(fontSize: 10, color: telemetryMuted),
            ),
            const SizedBox(height: 6),
            Wrap(
              spacing: 12,
              runSpacing: 5,
              children: [
                for (final item in series)
                  Tooltip(
                    message:
                        '${item.channel} · ${item.unit} · ${item.quality(inspected)}\n'
                        'Window min ${formatTelemetry(_geometry.values[item]!.low)} · max ${formatTelemetry(_geometry.values[item]!.high)}\n'
                        'Click to show or hide',
                    child: InkWell(
                      borderRadius: BorderRadius.circular(3),
                      onTap: () => _toggleSeries(item),
                      child: Padding(
                        padding: const EdgeInsets.symmetric(vertical: 3),
                        child: Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Container(
                              width: 7,
                              height: 7,
                              decoration: BoxDecoration(
                                color: _hidden.contains(_key(item))
                                    ? telemetryMuted.withValues(alpha: .35)
                                    : item.color,
                                shape: BoxShape.circle,
                              ),
                            ),
                            const SizedBox(width: 5),
                            Text(
                              '${item.name}  ',
                              style: TextStyle(
                                fontSize: 10,
                                color: telemetryMuted,
                                decoration: _hidden.contains(_key(item))
                                    ? TextDecoration.lineThrough
                                    : null,
                              ),
                            ),
                            Text(
                              item.display(inspected),
                              style: TextStyle(
                                fontSize: 10,
                                color: item.quality(inspected) == 'valid'
                                    ? Colors.white
                                    : const Color(0xffffc568),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ),
                  ),
              ],
            ),
            if (unsupported.isNotEmpty)
              Text(
                '${unsupported.length} channels unavailable',
                style: const TextStyle(fontSize: 10, color: telemetryMuted),
              ),
          ],
          if (widget.panel.note != null && !widget.observed)
            Padding(
              padding: const EdgeInsets.only(top: 7),
              child: Text(
                widget.panel.note!,
                maxLines: 2,
                overflow: TextOverflow.ellipsis,
                style: const TextStyle(
                  fontSize: 10,
                  color: telemetryMuted,
                  height: 1.35,
                ),
              ),
            ),
        ],
      ),
    );
  }

  Widget _action(IconData icon, String tooltip, VoidCallback? action) =>
      IconButton(
        tooltip: tooltip,
        constraints: const BoxConstraints.tightFor(width: 28, height: 28),
        padding: EdgeInsets.zero,
        visualDensity: VisualDensity.compact,
        onPressed: action,
        icon: Icon(icon, size: 15, color: telemetryMuted),
      );

  LineChartData _chartData(List<TelemetrySeries> visible, double width) {
    final visibleSeries = visible.map(_key).join('|');
    if (_cachedChartData != null &&
        _cachedChartWidth == width &&
        _cachedVisibleSeries == visibleSeries) {
      return _cachedChartData!;
    }
    var low = double.infinity;
    var high = double.negativeInfinity;
    final bars = <LineChartBarData>[];
    for (final item in visible) {
      final data = _geometry.values[item]!;
      low = math.min(low, data.low);
      high = math.max(high, data.high);
      if (data.spots.isNotEmpty) {
        bars.add(
          LineChartBarData(
            spots: data.spots,
            color: item.color,
            barWidth: 1.6,
            isCurved: false,
            preventCurveOverShooting: true,
            dotData: FlDotData(
              checkToShowDot: (spot, bar) => data.endpoints.contains(spot),
              getDotPainter: (_, _, _, _) => FlDotCirclePainter(
                radius: 1.6,
                color: item.color,
                strokeWidth: 0,
              ),
            ),
          ),
        );
      }
      if (data.saturated.isNotEmpty) {
        bars.add(
          LineChartBarData(
            spots: data.saturated,
            color: item.color,
            barWidth: 0,
            dotData: FlDotData(
              getDotPainter: (_, _, _, _) => _DiamondPainter(item.color),
            ),
          ),
        );
      }
    }
    if (!low.isFinite || !high.isFinite) {
      low = 0;
      high = 1;
    }
    final padding = high == low
        ? math.max(high.abs() * .06, .01)
        : (high - low) * .08;
    low -= padding;
    high += padding;
    final chartData = LineChartData(
      minX: 0,
      maxX: _rangeSeconds.toDouble(),
      minY: low,
      maxY: high,
      lineBarsData: bars,
      lineTouchData: const LineTouchData(enabled: false),
      clipData: const FlClipData.all(),
      borderData: FlBorderData(show: false),
      gridData: FlGridData(
        drawVerticalLine: false,
        horizontalInterval: (high - low) / 3,
        getDrawingHorizontalLine: (_) =>
            FlLine(color: telemetryBorder, strokeWidth: .7),
      ),
      titlesData: FlTitlesData(
        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        rightTitles: const AxisTitles(
          sideTitles: SideTitles(showTitles: false),
        ),
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: _leftAxis,
            interval: (high - low) / 3,
            minIncluded: false,
            maxIncluded: false,
            getTitlesWidget: (value, meta) => SideTitleWidget(
              meta: meta,
              space: 7,
              child: Text(
                formatTelemetry(value),
                style: const TextStyle(fontSize: 9, color: telemetryMuted),
              ),
            ),
          ),
        ),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: _bottomAxis,
            interval: _rangeSeconds / (width > 600 ? 4 : 2),
            getTitlesWidget: (value, meta) => SideTitleWidget(
              meta: meta,
              space: 8,
              fitInside: SideTitleFitInsideData.fromTitleMeta(
                meta,
                distanceFromEdge: 0,
              ),
              child: Text(
                _rangeEnd == null
                    ? '—'
                    : utcTime(_instant(value / _rangeSeconds)),
                style: const TextStyle(fontSize: 9, color: telemetryMuted),
              ),
            ),
          ),
        ),
      ),
    );
    _cachedChartData = chartData;
    _cachedChartWidth = width;
    _cachedVisibleSeries = visibleSeries;
    return chartData;
  }
}

/// Prepares drawing points once per data/range update, never on hover.
class _ChartGeometry {
  _ChartGeometry(
    this.series,
    List<JsonMap> source,
    DateTime? end,
    int seconds,
    double? observedCadenceSeconds,
  ) {
    for (final item in series) {
      values[item] = _SeriesGeometry();
    }
    if (end == null) return;
    final startMs = end.millisecondsSinceEpoch - seconds * 1000;
    final endMs = end.millisecondsSinceEpoch;
    final received = <({JsonMap frame, int time})>[];
    for (final frame in source) {
      final time = sampleTime(frame).millisecondsSinceEpoch;
      if (time >= startMs && time <= endMs) {
        received.add((frame: frame, time: time));
      }
    }
    received.sort((left, right) {
      final chronological = left.time.compareTo(right.time);
      if (chronological != 0) return chronological;
      return (left.frame['sequence'] as int).compareTo(
        right.frame['sequence'] as int,
      );
    });
    frames.addAll(received.map((entry) => entry.frame));
    times.addAll(received.map((entry) => entry.time));
    for (final item in series) {
      final data = values[item]!;
      var run = <FlSpot>[];
      JsonMap? previous;
      int? previousTime;
      final cadenceMs =
          (observedCadenceSeconds ??
              (item.definition['cadence_s'] as num).toDouble()) *
          1500;
      void flush() {
        if (run.isEmpty) return;
        if (data.spots.isNotEmpty) data.spots.add(FlSpot.nullSpot);
        data.endpoints.addAll([run.first, run.last]);
        data.spots.addAll(_reduce(run, seconds));
        run = [];
      }

      for (var i = 0; i < frames.length; i++) {
        final frame = frames[i];
        final value = item.value(frame);
        final quality = item.quality(frame);
        final contiguous =
            previous != null &&
            (frame['sequence'] as int) == (previous['sequence'] as int) + 1 &&
            times[i] - previousTime! <= cadenceMs;
        if (!contiguous || value == null || quality == 'saturated') flush();
        if (value != null) {
          data.low = math.min(data.low, value);
          data.high = math.max(data.high, value);
          final spot = FlSpot((times[i] - startMs) / 1000, value);
          if (quality == 'saturated') {
            data.saturated.add(spot);
          } else {
            run.add(spot);
          }
        }
        previous = quality == 'valid' && value != null ? frame : null;
        previousTime = times[i];
      }
      flush();
      data.saturated = _reduce(data.saturated, seconds);
    }
  }
  final List<TelemetrySeries> series;
  final List<JsonMap> frames = [];
  final List<int> times = [];
  final Map<TelemetrySeries, _SeriesGeometry> values = {};
}

class _SeriesGeometry {
  final List<FlSpot> spots = [];
  final Set<FlSpot> endpoints = {};
  List<FlSpot> saturated = [];
  double low = double.infinity;
  double high = double.negativeInfinity;
}

/// Retains first, last and both extrema per time bucket, within each valid run.
/// Null/invalid/sequence gaps are split before reduction and cannot be bridged.
List<FlSpot> _reduce(List<FlSpot> points, int seconds) {
  if (points.length <= 1600) return points;
  final result = <FlSpot>[];
  final bucketWidth = seconds / 400;
  var cursor = 0;
  while (cursor < points.length) {
    final first = cursor;
    final bucket = (points[cursor].x / bucketWidth).floor();
    var minimum = cursor;
    var maximum = cursor;
    while (cursor < points.length &&
        (points[cursor].x / bucketWidth).floor() == bucket) {
      if (points[cursor].y < points[minimum].y) minimum = cursor;
      if (points[cursor].y > points[maximum].y) maximum = cursor;
      cursor++;
    }
    final indices = {first, minimum, maximum, cursor - 1}.toList()..sort();
    result.addAll(indices.map((index) => points[index]));
  }
  return result;
}

class _DiamondPainter extends FlDotPainter {
  const _DiamondPainter(this.color);
  final Color color;
  @override
  Color get mainColor => color;
  @override
  Size getSize(FlSpot spot) => const Size(7, 7);
  @override
  void draw(Canvas canvas, FlSpot spot, Offset offsetInCanvas) {
    final x = offsetInCanvas.dx;
    final y = offsetInCanvas.dy;
    canvas.drawPath(
      Path()
        ..moveTo(x, y - 3.5)
        ..lineTo(x + 3.5, y)
        ..lineTo(x, y + 3.5)
        ..lineTo(x - 3.5, y)
        ..close(),
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.3,
    );
  }

  @override
  FlDotPainter lerp(FlDotPainter a, FlDotPainter b, double t) => this;
  @override
  List<Object?> get props => [color];
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({
    required this.channels,
    required this.definitions,
    required this.observed,
  });
  final List<String> channels;
  final Map<String, JsonMap> definitions;
  final bool observed;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      const Icon(Icons.sensors_off_outlined, size: 23, color: telemetryMuted),
      const SizedBox(height: 12),
      Text(
        observed ? 'Not recorded' : 'Not modeled',
        style: const TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 9),
      for (final id in channels)
        Padding(
          padding: const EdgeInsets.only(bottom: 7),
          child: Text(
            '${channelLabel(id)} · ${definitions[id]?['description'] ?? (observed ? 'Not provided by the recorded dataset.' : 'Not included in this spacecraft catalog.')}',
            maxLines: channels.length > 1 ? 2 : 4,
            overflow: TextOverflow.ellipsis,
            style: const TextStyle(
              fontSize: 11,
              color: telemetryMuted,
              height: 1.4,
            ),
          ),
        ),
      const Text(
        'Unavailable is not a zero reading.',
        style: TextStyle(fontSize: 10, color: telemetryMuted),
      ),
    ],
  );
}
