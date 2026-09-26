import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../scene/playback.dart';
import 'panels.dart';

String telemetryTitleCase(String value) => value
    .split('_')
    .map(
      (word) =>
          word.isEmpty ? word : '${word[0].toUpperCase()}${word.substring(1)}',
    )
    .join(' ');

class TelemetryBadge extends StatelessWidget {
  const TelemetryBadge(this.text, {super.key, this.color = telemetryMuted});
  final String text;
  final Color color;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 9, vertical: 5),
    decoration: BoxDecoration(
      color: color.withValues(alpha: .08),
      border: Border.all(color: color.withValues(alpha: .2)),
      borderRadius: BorderRadius.circular(5),
    ),
    child: Text(
      text,
      style: TextStyle(fontSize: 9, fontWeight: FontWeight.w700, color: color),
    ),
  );
}

class TelemetryMetric extends StatelessWidget {
  const TelemetryMetric({
    super.key,
    required this.title,
    required this.channel,
    required this.icon,
    required this.definition,
    required this.frame,
  });
  final String title, channel;
  final IconData icon;
  final JsonMap? definition, frame;
  @override
  Widget build(BuildContext context) {
    final series = definition == null
        ? null
        : TelemetrySeries(channel, definition!, telemetryAccent);
    final raw = series?.value(frame);
    // Display-unit conversions only; charts retain the catalog's canonical units.
    final percentage =
        channel == 'eps.battery_soc' && definition?['unit'] == '1';
    final kilometres =
        channel == 'orbit.altitude_m' && definition?['unit'] == 'm';
    final imageCount =
        channel == 'payload.image_count' && definition?['unit'] == '1';
    final displayValue = raw == null
        ? '—'
        : percentage
        ? (raw * 100).toStringAsFixed(1)
        : kilometres
        ? (raw / 1000).toStringAsFixed(2)
        : imageCount
        ? raw.toStringAsFixed(0)
        : formatTelemetry(raw);
    final displayUnit = percentage
        ? '%'
        : kilometres
        ? 'km'
        : imageCount
        ? 'images'
        : definition?['unit'] as String? ?? '';
    return Container(
      padding: const EdgeInsets.all(15),
      decoration: BoxDecoration(
        color: telemetrySurface,
        border: Border.all(color: telemetryBorder),
        borderRadius: BorderRadius.circular(9),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(fontSize: 11, color: telemetryMuted),
                ),
              ),
              Icon(icon, size: 17, color: telemetryAccent),
            ],
          ),
          const SizedBox(height: 11),
          Row(
            crossAxisAlignment: CrossAxisAlignment.baseline,
            textBaseline: TextBaseline.alphabetic,
            children: [
              Text(
                displayValue,
                style: const TextStyle(
                  fontSize: 29,
                  fontWeight: FontWeight.w700,
                  letterSpacing: -.8,
                ),
              ),
              const SizedBox(width: 8),
              Text(
                displayUnit,
                style: const TextStyle(fontSize: 10, color: telemetryMuted),
              ),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            series == null
                ? 'Not in this catalog'
                : series.quality(frame) == 'valid'
                ? (definition!['sampling_semantics'] == 'interval_mean'
                      ? ((frame?['sample_window_s']) == 0
                            ? 'Initial instantaneous allocation'
                            : 'Interval mean · ${frame?['sample_window_s']} s')
                      : 'Endpoint measurement')
                : telemetryTitleCase(series.quality(frame)),
            style: TextStyle(
              fontSize: 10,
              color: series?.quality(frame) == 'saturated'
                  ? const Color(0xffffc568)
                  : telemetryMuted,
            ),
          ),
        ],
      ),
    );
  }
}

class TelemetryNotice extends StatelessWidget {
  const TelemetryNotice({super.key, required this.icon, required this.text});
  final IconData icon;
  final String text;
  @override
  Widget build(BuildContext context) => Row(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Icon(icon, size: 16, color: telemetryMuted),
      const SizedBox(width: 9),
      Expanded(
        child: Text(
          text,
          style: const TextStyle(
            fontSize: 11,
            color: telemetryMuted,
            height: 1.5,
          ),
        ),
      ),
    ],
  );
}

class TelemetryCatalogState extends StatelessWidget {
  const TelemetryCatalogState({
    super.key,
    required this.loading,
    required this.version,
    required this.error,
    required this.retry,
  });
  final bool loading;
  final String? version, error;
  final VoidCallback? retry;
  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(vertical: 45, horizontal: 24),
    decoration: BoxDecoration(
      color: telemetrySurface,
      borderRadius: BorderRadius.circular(8),
    ),
    child: Column(
      children: [
        if (loading)
          const SizedBox(
            width: 22,
            height: 22,
            child: CircularProgressIndicator(strokeWidth: 2),
          )
        else
          const Icon(Icons.sensors_outlined, color: telemetryMuted),
        const SizedBox(height: 14),
        Text(
          version == null
              ? 'Awaiting the first committed telemetry frame'
              : loading
              ? 'Loading $version definitions'
              : 'Channel definitions unavailable',
          style: const TextStyle(fontSize: 14),
        ),
        const SizedBox(height: 8),
        const Text(
          'Units, coordinate frames, and availability are read from the stream’s versioned catalog.',
          textAlign: TextAlign.center,
          style: TextStyle(fontSize: 11, color: telemetryMuted),
        ),
        if (error != null && !loading)
          Padding(
            padding: const EdgeInsets.only(top: 9),
            child: Text(
              error!,
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 11, color: telemetryMuted),
            ),
          ),
        if (retry != null && !loading)
          Padding(
            padding: const EdgeInsets.only(top: 12),
            child: OutlinedButton.icon(
              onPressed: retry,
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Retry catalog'),
            ),
          ),
      ],
    ),
  );
}

class TelemetryChannelInventory extends StatelessWidget {
  const TelemetryChannelInventory({
    super.key,
    required this.definitions,
    required this.frame,
    required this.query,
  });
  final Map<String, JsonMap> definitions;
  final JsonMap? frame;
  final String query;

  String value(String id, JsonMap definition) {
    if (definition['availability'] == 'unavailable') return 'Not modeled';
    if (frame == null) return 'Waiting';
    final reading = (frame!['channels'] as Map)[id];
    if (reading is! Map) return 'Unsupported';
    final quality = reading['quality'] as String;
    if (quality != 'valid' && quality != 'saturated') {
      return telemetryTitleCase(quality);
    }
    final raw = reading['value'];
    final result = raw is num
        ? formatTelemetry(raw)
        : raw is List
        ? '[${raw.map((entry) => entry is num ? formatTelemetry(entry) : '—').join(', ')}]'
        : '$raw';
    return '$result${quality == 'saturated' ? ' · saturated' : ''}';
  }

  @override
  Widget build(BuildContext context) {
    final entries = definitions.entries
        .where(
          (item) =>
              query.isEmpty ||
              item.key.contains(query) ||
              channelLabel(item.key).toLowerCase().contains(query),
        )
        .toList();
    return Container(
      decoration: BoxDecoration(
        border: Border.all(color: telemetryBorder),
        borderRadius: BorderRadius.circular(8),
      ),
      child: ExpansionTile(
        shape: const Border(),
        collapsedShape: const Border(),
        title: Text(
          'Channel catalog · ${entries.length} channels',
          style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w700),
        ),
        subtitle: const Text(
          'Current values, quality, units, and coordinate frames',
          style: TextStyle(fontSize: 10, color: telemetryMuted),
        ),
        childrenPadding: const EdgeInsets.fromLTRB(15, 0, 15, 12),
        children: [
          for (final entry in entries)
            Tooltip(
              message: entry.value['description'] as String,
              child: Container(
                padding: const EdgeInsets.symmetric(vertical: 10),
                decoration: const BoxDecoration(
                  border: Border(top: BorderSide(color: telemetryBorder)),
                ),
                child: LayoutBuilder(
                  builder: (context, constraints) {
                    final label = Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(entry.key, style: const TextStyle(fontSize: 11)),
                        const SizedBox(height: 4),
                        Text(
                          '${entry.value['unit']} · ${entry.value['sampling_semantics']}'
                          '${entry.value['coordinate_frame'] == null ? '' : ' · ${entry.value['coordinate_frame']}'}',
                          style: const TextStyle(
                            fontSize: 10,
                            color: telemetryMuted,
                          ),
                        ),
                      ],
                    );
                    final reading = Text(
                      value(entry.key, entry.value),
                      style: TextStyle(
                        fontSize: 11,
                        color: entry.value['availability'] == 'unavailable'
                            ? telemetryMuted
                            : telemetryAccent,
                      ),
                    );
                    return constraints.maxWidth < 600
                        ? Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              label,
                              const SizedBox(height: 7),
                              reading,
                            ],
                          )
                        : Row(
                            children: [
                              Expanded(child: label),
                              SizedBox(
                                width: math.min(340, constraints.maxWidth * .4),
                                child: Align(
                                  alignment: Alignment.centerRight,
                                  child: reading,
                                ),
                              ),
                            ],
                          );
                  },
                ),
              ),
            ),
        ],
      ),
    );
  }
}
