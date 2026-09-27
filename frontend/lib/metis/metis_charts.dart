import 'dart:math' as math;

import 'package:fl_chart/fl_chart.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';

import '../api/metis_generated.dart' as metis;

const metisSurface = Color(0xff081426);
const metisBorder = Color(0xff1a315e);
const metisMuted = Color(0xff8da4d8);
const metisText = Color(0xffe3ebff);
const originalColor = Color(0xffF7C873);
const metisColor = Color(0xffA8E6B5);
const medianColor = Color(0xff8FD3FF);
const nominalColor = Color(0xff7089bf);
const thresholdColor = Color(0xffff8a80);
const actualColor = Color(0xffe3ebff);
const _eclipse = Color(0x14ffffff);

/// One drawn line with its legend entry.
class ChartSeries {
  const ChartSeries(
    this.name,
    this.color,
    this.spots, {
    this.dash,
    this.width = 2,
    this.legend = true,
  });

  final String name;
  final Color color;
  final List<FlSpot> spots;
  final List<int>? dash;
  final double width;
  final bool legend;
}

/// Step spots for per-bin values starting at [starts], each [width] minutes long.
List<FlSpot> stepSpots(
  List<double> starts,
  double width,
  List<double> values,
) => [
  for (var i = 0; i < starts.length; i++) ...[
    FlSpot(starts[i], values[i]),
    FlSpot(starts[i] + width, values[i]),
  ],
];

/// Spots for a minute series.
List<FlSpot> seriesSpots(metis.MinuteSeries series) => [
  for (var i = 0; i < series.minute.length; i++)
    FlSpot(series.minute[i], series.value[i]),
];

String minuteLabel(double minute) =>
    minute == 0 ? 'T0' : '${minute > 0 ? '+' : '−'}${minute.abs().round()}';

/// A mission-time line chart with eclipse shading, an optional band and markers.
class MissionLineChart extends StatelessWidget {
  const MissionLineChart({
    super.key,
    required this.title,
    required this.unit,
    required this.series,
    required this.eclipses,
    this.band,
    this.threshold,
    this.markers = const [],
    this.playhead,
    this.minY,
    this.note,
    this.height = 230,
  });

  final String title;
  final String unit;
  final List<ChartSeries> series;
  final List<metis.MissionInterval> eclipses;

  /// Indices of the lower and upper series whose gap is shaded.
  final (int, int)? band;
  final double? threshold;
  final List<(double, String)> markers;
  final double? playhead;
  final double? minY;
  final String? note;
  final double height;

  static const minX = -15.0, maxX = 180.0;

  @override
  Widget build(BuildContext context) => LayoutBuilder(
    builder: (context, constraints) => _chart(constraints.maxWidth < 460),
  );

  Widget _chart(bool compact) {
    var low = double.infinity, high = double.negativeInfinity;
    for (final item in series) {
      for (final spot in item.spots) {
        if (spot.x < minX || spot.x > maxX || spot.isNull()) continue;
        low = math.min(low, spot.y);
        high = math.max(high, spot.y);
      }
    }
    if (threshold != null) {
      low = math.min(low, threshold!);
      high = math.max(high, threshold!);
    }
    if (!low.isFinite) (low, high) = (0, 1);
    final pad = math.max((high - low) * .08, .5);
    final bottom = minY ?? low - pad, top = high + pad;
    final bars = [
      for (final item in series)
        LineChartBarData(
          spots: item.spots,
          color: item.color,
          barWidth: item.width,
          dashArray: item.dash,
          dotData: const FlDotData(show: false),
          isCurved: false,
        ),
    ];
    final data = LineChartData(
      minX: minX,
      maxX: maxX,
      minY: bottom,
      maxY: top,
      clipData: const FlClipData.all(),
      lineBarsData: bars,
      betweenBarsData: band == null
          ? const []
          : [
              BetweenBarsData(
                fromIndex: band!.$1,
                toIndex: band!.$2,
                color: series[band!.$1].color.withValues(alpha: .18),
              ),
            ],
      rangeAnnotations: RangeAnnotations(
        verticalRangeAnnotations: [
          for (final eclipse in eclipses)
            VerticalRangeAnnotation(
              x1: math.max(minX, eclipse.start_min),
              x2: math.min(maxX, eclipse.end_min),
              color: _eclipse,
            ),
        ],
      ),
      extraLinesData: ExtraLinesData(
        horizontalLines: [
          if (threshold != null)
            HorizontalLine(
              y: threshold!,
              color: thresholdColor,
              strokeWidth: 1.2,
              dashArray: const [6, 4],
              label: HorizontalLineLabel(
                show: true,
                alignment: Alignment.topRight,
                style: const TextStyle(fontSize: 10, color: thresholdColor),
                labelResolver: (_) => 'Protected reserve',
              ),
            ),
        ],
        verticalLines: [
          VerticalLine(
            x: 0,
            color: metisMuted.withValues(alpha: .6),
            strokeWidth: 1,
          ),
          for (final (x, text) in markers)
            VerticalLine(
              x: x,
              color: metisMuted.withValues(alpha: .5),
              strokeWidth: 1,
              dashArray: const [3, 3],
              label: VerticalLineLabel(
                show: text.isNotEmpty && !compact,
                // Label left of the line when the next labeled marker is close or near the right edge.
                alignment:
                    markers.any(
                          (m) => m.$2.isNotEmpty && m.$1 > x && m.$1 - x < 15,
                        ) ||
                        x > 150
                    ? Alignment.topLeft
                    : Alignment.topRight,
                style: const TextStyle(fontSize: 9, color: metisMuted),
                labelResolver: (_) => text,
              ),
            ),
          if (playhead != null)
            VerticalLine(x: playhead!, color: actualColor, strokeWidth: 1.4),
        ],
      ),
      borderData: FlBorderData(show: false),
      gridData: FlGridData(
        drawVerticalLine: false,
        getDrawingHorizontalLine: (_) =>
            FlLine(color: metisBorder, strokeWidth: .7),
      ),
      lineTouchData: LineTouchData(
        touchTooltipData: LineTouchTooltipData(
          getTooltipColor: (_) => metisSurface,
          fitInsideHorizontally: true,
          fitInsideVertically: true,
          getTooltipItems: (spots) => [
            for (final spot in spots)
              LineTooltipItem(
                '${series[spot.barIndex].name}: ${spot.y.toStringAsFixed(2)} $unit'
                '${spot == spots.first ? '  (${minuteLabel(spot.x)} min)' : ''}',
                TextStyle(color: series[spot.barIndex].color, fontSize: 11),
              ),
          ],
        ),
      ),
      titlesData: FlTitlesData(
        topTitles: const AxisTitles(sideTitles: SideTitles(showTitles: false)),
        rightTitles: const AxisTitles(
          sideTitles: SideTitles(showTitles: false),
        ),
        leftTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 40,
            minIncluded: false,
            maxIncluded: false,
            getTitlesWidget: (value, meta) => SideTitleWidget(
              meta: meta,
              child: Text(
                value.toStringAsFixed(value.abs() < 10 ? 1 : 0),
                style: const TextStyle(fontSize: 9, color: metisMuted),
              ),
            ),
          ),
        ),
        bottomTitles: AxisTitles(
          sideTitles: SideTitles(
            showTitles: true,
            reservedSize: 24,
            interval: 30,
            getTitlesWidget: (value, meta) => SideTitleWidget(
              meta: meta,
              child: Text(
                value % 30 == 0 ? minuteLabel(value) : '',
                style: const TextStyle(fontSize: 9, color: metisMuted),
              ),
            ),
          ),
        ),
      ),
    );
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        if (title.isNotEmpty) ...[
          Text(
            title,
            style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 6),
        ],
        Wrap(
          spacing: 14,
          runSpacing: 4,
          children: [
            for (final item in series.where((s) => s.legend))
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  CustomPaint(
                    size: const Size(22, 8),
                    painter: _Swatch(item.color, item.dash != null),
                  ),
                  const SizedBox(width: 6),
                  Flexible(
                    child: Text(
                      item.name,
                      style: const TextStyle(fontSize: 11, color: metisMuted),
                    ),
                  ),
                ],
              ),
            if (band != null)
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  Container(
                    width: 22,
                    height: 8,
                    color: series[band!.$1].color.withValues(alpha: .25),
                  ),
                  const SizedBox(width: 6),
                  const Flexible(
                    child: Text(
                      'Low to high case (10th–90th percentile)',
                      style: TextStyle(fontSize: 11, color: metisMuted),
                    ),
                  ),
                ],
              ),
          ],
        ),
        const SizedBox(height: 8),
        SizedBox(
          height: height,
          child: LineChart(data, duration: Duration.zero),
        ),
        if (note != null) ...[
          const SizedBox(height: 6),
          Text(note!, style: const TextStyle(fontSize: 11, color: metisMuted)),
        ],
      ],
    );
  }
}

class _Swatch extends CustomPainter {
  const _Swatch(this.color, this.dashed);
  final Color color;
  final bool dashed;

  @override
  void paint(Canvas canvas, Size size) {
    final paint = Paint()
      ..color = color
      ..strokeWidth = 2;
    final y = size.height / 2;
    if (!dashed) {
      canvas.drawLine(Offset(0, y), Offset(size.width, y), paint);
      return;
    }
    for (var x = 0.0; x < size.width; x += 7) {
      canvas.drawLine(
        Offset(x, y),
        Offset(math.min(size.width, x + 4), y),
        paint,
      );
    }
  }

  @override
  bool shouldRepaint(_Swatch old) => old.color != color || old.dashed != dashed;
}

/// Task timeline with one lane per plan; tasks the satellite skipped are crossed out.
class TaskTimeline extends StatelessWidget {
  const TaskTimeline({
    super.key,
    required this.mission,
    required this.metisBatchStart,
    this.lanes = const ['original', 'metis'],
    this.active,
    this.skipped = const {},
    this.playhead,
  });

  final metis.MissionBrief mission;
  final double metisBatchStart;

  /// Plans shown, from `original` and `metis`.
  final List<String> lanes;

  /// Plan being flown or shown; its lane is emphasized.
  final String? active;

  /// Task IDs skipped by the satellite in each plan's latest run.
  final Map<String, Set<String>> skipped;
  final double? playhead;

  @override
  Widget build(BuildContext context) => SizedBox(
    height: 58 + 42.0 * lanes.length,
    child: CustomPaint(
      size: Size.infinite,
      painter: _TimelinePainter(
        mission,
        metisBatchStart,
        lanes,
        active,
        skipped,
        playhead,
        MediaQuery.textScalerOf(context),
      ),
    ),
  );
}

class _TimelinePainter extends CustomPainter {
  _TimelinePainter(
    this.mission,
    this.metisStart,
    this.lanes,
    this.active,
    this.skipped,
    this.playhead,
    this.textScaler,
  );

  final metis.MissionBrief mission;
  final double metisStart;
  final List<String> lanes;
  final String? active;
  final Map<String, Set<String>> skipped;
  final double? playhead;
  final TextScaler textScaler;

  static const right = 12.0, minX = -15.0, maxX = 180.0;

  void _text(
    Canvas canvas,
    String text,
    Offset at, {
    Color color = metisMuted,
    double size = 10,
    TextAlign align = TextAlign.left,
    FontWeight weight = FontWeight.normal,
  }) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: TextStyle(
          color: color,
          fontSize: size,
          fontFamily: 'MetisSans',
          fontWeight: weight,
        ),
      ),
      textDirection: TextDirection.ltr,
      textAlign: align,
      textScaler: textScaler,
    )..layout();
    final dx = align == TextAlign.center ? at.dx - painter.width / 2 : at.dx;
    painter.paint(canvas, Offset(dx, at.dy));
  }

  @override
  void paint(Canvas canvas, Size size) {
    final compact = size.width < 600;
    final left = compact ? 64.0 : 118.0;
    double x(double minute) =>
        left + (minute - minX) / (maxX - minX) * (size.width - left - right);
    final original = mission.tasks.firstWhere((t) => t.movable).start_min;
    final rows = [
      for (final plan in lanes)
        plan == 'metis'
            ? ('metis', 'Metis plan', metisColor, metisStart)
            : ('original', 'Original schedule', originalColor, original),
    ];
    const laneTop = 10.0, laneHeight = 30.0, gap = 12.0;
    final chartBottom =
        laneTop + rows.length * laneHeight + (rows.length - 1) * gap;
    for (final eclipse in mission.eclipses) {
      final a = x(math.max(minX, eclipse.start_min)),
          b = x(math.min(maxX, eclipse.end_min));
      canvas.drawRect(
        Rect.fromLTRB(a, 0, b, chartBottom),
        Paint()..color = _eclipse,
      );
    }
    for (var lane = 0; lane < rows.length; lane++) {
      final (plan, name, color, batchStart) = rows[lane];
      final emphasized = active == null || active == plan;
      final top = laneTop + lane * (laneHeight + gap);
      _text(
        canvas,
        compact ? name.split(' ').first : name,
        Offset(0, top + 8),
        color: emphasized ? color : color.withValues(alpha: .5),
        size: compact ? 10 : 11,
        weight: active == plan ? FontWeight.w700 : FontWeight.normal,
      );
      canvas.drawRRect(
        RRect.fromRectAndRadius(
          Rect.fromLTRB(left, top + 12, size.width - right, top + 18),
          const Radius.circular(3),
        ),
        Paint()..color = metisBorder,
      );
      for (final task in mission.tasks) {
        final start = task.movable ? batchStart : task.start_min;
        final end = start + task.end_min - task.start_min;
        final base = task.movable
            ? color
            : (task.task_id == 'downlink'
                  ? medianColor
                  : const Color(0xff5d84ff));
        final rect = Rect.fromLTRB(
          x(start),
          top + 6,
          math.max(x(end), x(start) + 3),
          top + 24,
        );
        final wasSkipped = skipped[plan]?.contains(task.task_id) ?? false;
        final block = RRect.fromRectAndRadius(rect, const Radius.circular(3));
        if (wasSkipped) {
          canvas.drawRRect(
            block,
            Paint()
              ..color = thresholdColor
              ..style = PaintingStyle.stroke
              ..strokeWidth = 1.4,
          );
          final cross = Paint()
            ..color = thresholdColor
            ..strokeWidth = 1.6;
          final c = rect.center;
          canvas.drawLine(
            c + const Offset(-6, -6),
            c + const Offset(6, 6),
            cross,
          );
          canvas.drawLine(
            c + const Offset(-6, 6),
            c + const Offset(6, -6),
            cross,
          );
          if (!compact) {
            _text(
              canvas,
              'Skipped',
              Offset(rect.left, top - 8),
              color: thresholdColor,
              size: 9,
            );
          }
        } else {
          canvas.drawRRect(
            block,
            Paint()..color = emphasized ? base : base.withValues(alpha: .45),
          );
        }
        if (task.movable) {
          _text(
            canvas,
            'Batch ${minuteLabel(start)}',
            Offset(rect.left, top - 8),
            color: color,
            size: 9,
          );
        }
      }
    }
    final deadlines = [
      (
        mission.delivery_deadline_min,
        'Briefing +${mission.delivery_deadline_min.round()}',
      ),
      (
        mission.batch_deadline_min,
        'Batch deadline +${mission.batch_deadline_min.round()}',
      ),
    ];
    final dash = Paint()
      ..color = metisMuted
      ..strokeWidth = 1;
    for (final (minute, text) in deadlines) {
      for (var y = 0.0; y < chartBottom; y += 6) {
        canvas.drawLine(Offset(x(minute), y), Offset(x(minute), y + 3), dash);
      }
      if (!compact) {
        _text(
          canvas,
          text,
          Offset(x(minute), chartBottom + 2),
          size: 9,
          align: TextAlign.center,
        );
      }
    }
    for (final minute
        in compact
            ? [0.0, 60.0, 120.0, 180.0]
            : [0.0, 30.0, 60.0, 90.0, 120.0, 150.0, 180.0]) {
      _text(
        canvas,
        minuteLabel(minute),
        Offset(x(minute), chartBottom + 16),
        size: 9,
        align: TextAlign.center,
      );
    }
    _text(
      canvas,
      compact
          ? 'Dashed: +120 briefing, +165 batch deadline'
          : 'Blue: capture +90 · Light blue: downlink +100 to +103 · Shaded: eclipse',
      Offset(left, chartBottom + 32),
      size: 9,
    );
    canvas.drawLine(
      Offset(x(0), 0),
      Offset(x(0), chartBottom),
      Paint()
        ..color = metisMuted
        ..strokeWidth = 1,
    );
    if (playhead != null) {
      canvas.drawLine(
        Offset(x(playhead!), 0),
        Offset(x(playhead!), chartBottom),
        Paint()
          ..color = actualColor
          ..strokeWidth = 1.6,
      );
    }
  }

  @override
  bool shouldRepaint(_TimelinePainter old) =>
      old.metisStart != metisStart ||
      old.playhead != playhead ||
      old.mission != mission ||
      old.active != active ||
      old.textScaler != textScaler ||
      !listEquals(old.lanes, lanes) ||
      old.skipped.toString() != skipped.toString();
}
