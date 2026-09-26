import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../scene/playback.dart';
import 'panels.dart';

/// Compact multiseries chart of received, committed samples, without resampling.
class TelemetryChart extends StatefulWidget {
  const TelemetryChart({
    super.key,
    required this.panel,
    required this.definitions,
    required this.frames,
    required this.current,
    required this.windowSeconds,
    required this.end,
  });
  final TelemetryPanel panel;
  final Map<String, JsonMap> definitions;
  final List<JsonMap> frames;
  final JsonMap? current;
  final int windowSeconds;
  final DateTime? end;

  @override
  State<TelemetryChart> createState() => _TelemetryChartState();
}

class _TelemetryChartState extends State<TelemetryChart> {
  double? _hoverFraction;

  @override
  Widget build(BuildContext context) {
    final series = panelSeries(widget.panel, widget.definitions);
    final unsupported = widget.panel.channels
        .where(
          (id) =>
              widget.definitions[id] == null ||
              widget.definitions[id]!['availability'] == 'unavailable',
        )
        .toList();
    final unit = series.isEmpty ? null : series.first.unit;
    final frames = widget.frames;
    JsonMap? hovered;
    if (_hoverFraction != null && frames.isNotEmpty && widget.end != null) {
      final target =
          widget.end!.millisecondsSinceEpoch -
          widget.windowSeconds * 1000 * (1 - _hoverFraction!);
      var distance = double.infinity;
      for (final frame in frames) {
        final delta = (sampleTime(frame).millisecondsSinceEpoch - target).abs();
        if (delta < distance) {
          hovered = frame;
          distance = delta;
        }
      }
      // Do not imply a reading at the cursor across unreceived history.
      if (distance > math.max(1500, widget.windowSeconds * 1000 * .018)) {
        hovered = null;
      }
    }
    final inspected = _hoverFraction == null ? widget.current : hovered;
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
    return Container(
      decoration: BoxDecoration(
        color: telemetrySurface,
        border: Border.all(color: telemetryBorder),
        borderRadius: BorderRadius.circular(9),
      ),
      padding: const EdgeInsets.fromLTRB(15, 13, 15, 12),
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
                  padding: EdgeInsets.only(left: 8),
                  child: Icon(
                    Icons.info_outline,
                    size: 15,
                    color: telemetryMuted,
                  ),
                ),
              ),
            ],
          ),
          const SizedBox(height: 7),
          if (series.isEmpty)
            Expanded(
              child: _Unavailable(
                channels: unsupported,
                definitions: widget.definitions,
              ),
            )
          else ...[
            Row(
              children: [
                Text(
                  unit == '1' ? '1 · dimensionless' : unit!,
                  style: const TextStyle(fontSize: 10, color: telemetryMuted),
                ),
                const Spacer(),
                Text(
                  inspected == null
                      ? (_hoverFraction == null
                            ? 'Awaiting sample'
                            : 'No sample here')
                      : '${utcTime(sampleTime(inspected))} UTC${_hoverFraction == null ? '' : ' · inspected'}',
                  style: const TextStyle(fontSize: 10, color: telemetryMuted),
                ),
              ],
            ),
            const SizedBox(height: 5),
            Expanded(
              child: LayoutBuilder(
                builder: (context, constraints) {
                  final hasValues = frames.any(
                    (frame) => series.any((item) => item.value(frame) != null),
                  );
                  return MouseRegion(
                    onHover: (event) => setState(
                      () => _hoverFraction =
                          ((event.localPosition.dx - 50) /
                                  math.max(1, constraints.maxWidth - 58))
                              .clamp(0.0, 1.0),
                    ),
                    onExit: (_) => setState(() => _hoverFraction = null),
                    child: Stack(
                      children: [
                        Positioned.fill(
                          child: RepaintBoundary(
                            child: CustomPaint(
                              painter: _TelemetryPainter(
                                series: series,
                                frames: frames,
                                end: widget.end,
                                windowSeconds: widget.windowSeconds,
                                hovered: hovered,
                              ),
                            ),
                          ),
                        ),
                        if (!hasValues)
                          const Positioned.fill(
                            child: Center(
                              child: Text(
                                'No valid measurements in this window',
                                style: TextStyle(
                                  fontSize: 11,
                                  color: telemetryMuted,
                                ),
                                textAlign: TextAlign.center,
                              ),
                            ),
                          ),
                      ],
                    ),
                  );
                },
              ),
            ),
            const SizedBox(height: 8),
            Wrap(
              spacing: 15,
              runSpacing: 5,
              children: [
                for (final item in series)
                  Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Container(
                        width: 7,
                        height: 7,
                        decoration: BoxDecoration(
                          color: item.color,
                          shape: BoxShape.circle,
                        ),
                      ),
                      const SizedBox(width: 5),
                      Text(
                        '${item.name}  ',
                        style: const TextStyle(
                          fontSize: 10,
                          color: telemetryMuted,
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
              ],
            ),
            if (unsupported.isNotEmpty)
              Padding(
                padding: const EdgeInsets.only(top: 5),
                child: Text(
                  '${unsupported.length} channels unavailable',
                  style: const TextStyle(fontSize: 10, color: telemetryMuted),
                ),
              ),
          ],
          if (widget.panel.note != null) ...[
            const SizedBox(height: 9),
            Text(
              widget.panel.note!,
              maxLines: 2,
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(
                fontSize: 10,
                color: telemetryMuted,
                height: 1.35,
              ),
            ),
          ],
        ],
      ),
    );
  }
}

class _Unavailable extends StatelessWidget {
  const _Unavailable({required this.channels, required this.definitions});
  final List<String> channels;
  final Map<String, JsonMap> definitions;

  @override
  Widget build(BuildContext context) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisAlignment: MainAxisAlignment.center,
    children: [
      const Icon(Icons.sensors_off_outlined, size: 23, color: telemetryMuted),
      const SizedBox(height: 12),
      const Text(
        'Not modeled',
        style: TextStyle(fontSize: 15, fontWeight: FontWeight.w700),
      ),
      const SizedBox(height: 9),
      for (final id in channels)
        Padding(
          padding: const EdgeInsets.only(bottom: 7),
          child: Text(
            '${channelLabel(id)} · ${definitions[id]?['description'] ?? 'Not included in this spacecraft catalog.'}',
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

class _TelemetryPainter extends CustomPainter {
  _TelemetryPainter({
    required this.series,
    required this.frames,
    required this.end,
    required this.windowSeconds,
    required this.hovered,
  });
  final List<TelemetrySeries> series;
  final List<JsonMap> frames;
  final DateTime? end;
  final int windowSeconds;
  final JsonMap? hovered;

  void label(Canvas canvas, String text, Offset at, {bool right = false}) {
    final painter = TextPainter(
      text: TextSpan(
        text: text,
        style: const TextStyle(
          color: telemetryMuted,
          fontSize: 9,
          fontFamily: 'MetisSans',
        ),
      ),
      textDirection: TextDirection.ltr,
    )..layout();
    painter.paint(canvas, Offset(right ? at.dx - painter.width : at.dx, at.dy));
  }

  @override
  void paint(Canvas canvas, Size size) {
    if (size.width < 65 || size.height < 45) return;
    final plot = Rect.fromLTRB(50, 9, size.width - 8, size.height - 23);
    final values = [
      for (final frame in frames)
        for (final item in series)
          if (item.value(frame) != null) item.value(frame)!,
    ];
    var low = values.isEmpty ? 0.0 : values.reduce(math.min);
    var high = values.isEmpty ? 1.0 : values.reduce(math.max);
    final padding = high == low
        ? math.max(high.abs() * .06, .01)
        : (high - low) * .08;
    low -= padding;
    high += padding;
    final grid = Paint()
      ..color = telemetryBorder.withValues(alpha: .72)
      ..strokeWidth = .7;
    for (var index = 0; index <= 3; index++) {
      final y = plot.top + plot.height * index / 3;
      canvas.drawLine(Offset(plot.left, y), Offset(plot.right, y), grid);
      if (values.isNotEmpty) {
        label(
          canvas,
          formatTelemetry(high - (high - low) * index / 3),
          Offset(plot.left - 7, y - 5),
          right: true,
        );
      }
    }
    if (end == null) return;
    final startMs = end!.millisecondsSinceEpoch - windowSeconds * 1000;
    double x(JsonMap frame) =>
        plot.left +
        (sampleTime(frame).millisecondsSinceEpoch - startMs) /
            (windowSeconds * 1000) *
            plot.width;
    double y(double value) =>
        plot.bottom - (value - low) / (high - low) * plot.height;
    for (var index = 0; index <= 2; index++) {
      final instant = DateTime.fromMillisecondsSinceEpoch(
        startMs + (windowSeconds * 1000 * index / 2).round(),
        isUtc: true,
      );
      label(
        canvas,
        utcTime(instant),
        Offset(plot.left + plot.width * index / 2, size.height - 14),
        right: index == 2,
      );
    }
    canvas.save();
    canvas.clipRect(plot.inflate(2));
    for (final item in series) {
      final paint = Paint()
        ..color = item.color
        ..strokeWidth = 1.55
        ..style = PaintingStyle.stroke;
      JsonMap? previous;
      Offset? previousPoint;
      final cadence = (item.definition['cadence_s'] as num).toDouble();
      for (final frame in frames) {
        final value = item.value(frame);
        final quality = item.quality(frame);
        if (value == null) {
          previous = null;
          previousPoint = null;
          continue;
        }
        final point = Offset(x(frame), y(value));
        if (quality == 'saturated') {
          final diamond = Path()
            ..moveTo(point.dx, point.dy - 3)
            ..lineTo(point.dx + 3, point.dy)
            ..lineTo(point.dx, point.dy + 3)
            ..lineTo(point.dx - 3, point.dy)
            ..close();
          canvas.drawPath(diamond, paint);
          previous = null;
          previousPoint = null;
          continue;
        }
        final contiguous =
            previous != null &&
            (frame['sequence'] as int) == (previous['sequence'] as int) + 1 &&
            sampleTime(frame).difference(sampleTime(previous)).inMilliseconds <=
                cadence * 1500;
        if (contiguous && previousPoint != null) {
          canvas.drawLine(previousPoint, point, paint);
        }
        // Retain isolated samples instead of erasing a one-point window.
        if (!contiguous || identical(frame, frames.last)) {
          canvas.drawCircle(point, 1.8, Paint()..color = item.color);
        }
        previous = frame;
        previousPoint = point;
      }
    }
    if (hovered != null) {
      canvas.drawLine(
        Offset(x(hovered!), plot.top),
        Offset(x(hovered!), plot.bottom),
        Paint()
          ..color = Colors.white.withValues(alpha: .45)
          ..strokeWidth = 1,
      );
      for (final item in series) {
        final value = item.value(hovered);
        if (value != null) {
          canvas.drawCircle(
            Offset(x(hovered!), y(value)),
            3,
            Paint()..color = item.color,
          );
        }
      }
    }
    canvas.restore();
  }

  @override
  bool shouldRepaint(covariant _TelemetryPainter oldDelegate) => true;
}
