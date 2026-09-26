import 'package:flutter/material.dart';
import '../api/mission.dart';
import '../scene/playback.dart';
import 'chart.dart';
import 'panels.dart';
import 'dashboard_widgets.dart';

/// Catalog-driven spacecraft telemetry, synchronized with mission playback.
class TelemetryDashboard extends StatefulWidget {
  const TelemetryDashboard({
    super.key,
    required this.mission,
    required this.selected,
    required this.seconds,
  });
  final Mission mission;
  final String selected;
  final double? seconds;

  @override
  State<TelemetryDashboard> createState() => _TelemetryDashboardState();
}

class _TelemetryDashboardState extends State<TelemetryDashboard> {
  String _tab = 'Overview';
  int _window = 60;
  final _search = TextEditingController();

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mission = widget.mission;
    final status = mission.status;
    final current = mission.playback.frameAt(widget.selected, widget.seconds);
    final received = mission.playback.history[widget.selected] ?? <JsonMap>[];
    final eligible = status == null || widget.seconds == null
        ? <JsonMap>[]
        : received
              .where(
                (frame) =>
                    frameSeconds(frame, status) <= widget.seconds! + 1e-7,
              )
              .toList();
    final end = eligible.isEmpty ? null : sampleTime(eligible.last);
    final frames = end == null
        ? <JsonMap>[]
        : eligible
              .where(
                (frame) => !sampleTime(
                  frame,
                ).isBefore(end.subtract(Duration(seconds: _window))),
              )
              .toList();
    final version =
        (current ??
                (received.isEmpty ? null : received.last))?['catalog_version']
            as String?;
    final catalog = mission.catalogs[version];
    final definitions = <String, JsonMap>{
      for (final raw in catalog?['channels'] as List? ?? [])
        (raw as Map)['channel_id'] as String: Map<String, dynamic>.from(raw),
    };
    final modeled = definitions.values
        .where((item) => item['availability'] != 'unavailable')
        .length;
    final unavailable = definitions.length - modeled;
    final query = _search.text.trim().toLowerCase();
    final panels = telemetryPanels[_tab]!
        .where(
          (panel) =>
              query.isEmpty ||
              panel.title.toLowerCase().contains(query) ||
              panel.channels.any(
                (id) =>
                    id.toLowerCase().contains(query) ||
                    channelLabel(id).toLowerCase().contains(query),
              ),
        )
        .toList();
    final gaps = frames.isEmpty
        ? 0
        : (frames.last['sequence'] as int) -
              (frames.first['sequence'] as int) +
              1 -
              frames.length;
    final coverage = frames.length < 2
        ? 0
        : sampleTime(
            frames.last,
          ).difference(sampleTime(frames.first)).inSeconds;
    final stale = mission.playback.isStale(mission.now);
    final runState = status?['status'] as String? ?? 'waiting';
    final connection = !mission.playback.connected
        ? 'Disconnected'
        : stale
        ? 'Stale stream'
        : runState == 'running'
        ? 'Receiving'
        : telemetryTitleCase(runState);

    return ListView(
      padding: const EdgeInsets.fromLTRB(22, 22, 22, 26),
      children: [
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          runSpacing: 14,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'SPACECRAFT TELEMETRY',
                  style: TextStyle(
                    fontSize: 10,
                    letterSpacing: 2.1,
                    color: telemetryAccent,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 7),
                Wrap(
                  spacing: 13,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    Text(
                      widget.selected.isEmpty
                          ? 'Awaiting spacecraft'
                          : widget.selected,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: const TextStyle(
                        fontSize: 26,
                        fontWeight: FontWeight.w700,
                        letterSpacing: -.6,
                      ),
                    ),
                    TelemetryBadge(
                      connection,
                      color: stale ? const Color(0xffffc568) : telemetryAccent,
                    ),
                  ],
                ),
                const SizedBox(height: 6),
                Text(
                  current == null
                      ? 'Waiting for a committed sample at the displayed time'
                      : '${utcTime(sampleTime(current), date: true)}  ·  Sequence ${current['sequence']}',
                  style: const TextStyle(fontSize: 11, color: telemetryMuted),
                ),
              ],
            ),
            Column(
              crossAxisAlignment: CrossAxisAlignment.end,
              children: [
                Wrap(
                  spacing: 7,
                  runSpacing: 7,
                  children: [
                    TelemetryBadge(
                      current?['source_kind'] == 'observed'
                          ? 'OBSERVED'
                          : current?['source_kind'] == 'synthetic'
                          ? 'SYNTHETIC'
                          : 'AWAITING SOURCE',
                    ),
                    if (version != null) TelemetryBadge(version),
                    if (current != null)
                      TelemetryBadge(
                        'Endpoint: ${telemetryTitleCase(current['mode'] as String)}',
                      ),
                    if (current != null &&
                        current['interval_mode'] != current['mode'])
                      TelemetryBadge(
                        'Interval: ${current['interval_mode'] == null ? 'Unknown' : telemetryTitleCase(current['interval_mode'] as String)}',
                      ),
                  ],
                ),
                const SizedBox(height: 9),
                Text(
                  catalog == null
                      ? version == null
                            ? 'Awaiting the first channel catalog'
                            : mission.catalogLoading
                            ? 'Loading channel definitions'
                            : 'Channel definitions unavailable'
                      : '$modeled modeled channels  ·  $unavailable unavailable  ·  1 Hz simulated UTC',
                  style: const TextStyle(fontSize: 10, color: telemetryMuted),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 21),
        if (catalog != null) ...[
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth >= 1000
                  ? 4
                  : constraints.maxWidth >= 540
                  ? 2
                  : 1;
              return Wrap(
                spacing: 12,
                runSpacing: 12,
                children: [
                  for (final item in const [
                    (
                      'Battery state of charge',
                      'eps.battery_soc',
                      Icons.battery_5_bar_outlined,
                    ),
                    (
                      'Solar generation',
                      'eps.solar_power_w',
                      Icons.wb_sunny_outlined,
                    ),
                    (
                      'Payload images',
                      'payload.image_count',
                      Icons.photo_camera_outlined,
                    ),
                    (
                      'Geodetic altitude',
                      'orbit.altitude_m',
                      Icons.public_outlined,
                    ),
                  ])
                    SizedBox(
                      width:
                          (constraints.maxWidth - (columns - 1) * 12) / columns,
                      child: TelemetryMetric(
                        title: item.$1,
                        channel: item.$2,
                        icon: item.$3,
                        definition: definitions[item.$2],
                        frame: current,
                      ),
                    ),
                ],
              );
            },
          ),
          const SizedBox(height: 20),
        ],
        Container(
          decoration: const BoxDecoration(
            border: Border(bottom: BorderSide(color: telemetryBorder)),
          ),
          child: SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: Row(
              children: [
                for (final tab in telemetryTabs)
                  Padding(
                    padding: const EdgeInsets.only(right: 7),
                    child: TextButton(
                      onPressed: () => setState(() => _tab = tab),
                      style: TextButton.styleFrom(
                        foregroundColor: _tab == tab
                            ? telemetryAccent
                            : telemetryMuted,
                        backgroundColor: _tab == tab
                            ? telemetryAccent.withValues(alpha: .08)
                            : Colors.transparent,
                        padding: const EdgeInsets.symmetric(
                          horizontal: 16,
                          vertical: 18,
                        ),
                        shape: const RoundedRectangleBorder(
                          borderRadius: BorderRadius.vertical(
                            top: Radius.circular(6),
                          ),
                        ),
                      ),
                      child: Text(
                        tab,
                        style: TextStyle(
                          fontSize: 12,
                          fontWeight: _tab == tab
                              ? FontWeight.w700
                              : FontWeight.w400,
                        ),
                      ),
                    ),
                  ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 15),
        Wrap(
          alignment: WrapAlignment.spaceBetween,
          spacing: 18,
          runSpacing: 12,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            SizedBox(
              width: 285,
              height: 38,
              child: TextField(
                controller: _search,
                onChanged: (_) => setState(() {}),
                style: const TextStyle(fontSize: 12),
                decoration: InputDecoration(
                  hintText: 'Filter panels or channel IDs',
                  hintStyle: const TextStyle(
                    color: telemetryMuted,
                    fontSize: 11,
                  ),
                  prefixIcon: const Icon(
                    Icons.search,
                    size: 18,
                    color: telemetryMuted,
                  ),
                  suffixIcon: query.isEmpty
                      ? null
                      : IconButton(
                          tooltip: 'Clear filter',
                          onPressed: () => setState(_search.clear),
                          icon: const Icon(Icons.close, size: 15),
                        ),
                  filled: true,
                  fillColor: telemetrySurface,
                  contentPadding: const EdgeInsets.symmetric(horizontal: 10),
                  enabledBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: const BorderSide(color: telemetryBorder),
                  ),
                  focusedBorder: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(6),
                    borderSide: const BorderSide(color: telemetryAccent),
                  ),
                ),
              ),
            ),
            Wrap(
              spacing: 12,
              runSpacing: 8,
              crossAxisAlignment: WrapCrossAlignment.center,
              children: [
                const Text(
                  'Buffered window',
                  style: TextStyle(fontSize: 11, color: telemetryMuted),
                ),
                SegmentedButton<int>(
                  segments: const [
                    ButtonSegment(value: 60, label: Text('1 min')),
                    ButtonSegment(value: 300, label: Text('5 min')),
                    ButtonSegment(value: 600, label: Text('10 min')),
                  ],
                  selected: {_window},
                  showSelectedIcon: false,
                  onSelectionChanged: (value) =>
                      setState(() => _window = value.single),
                  style: SegmentedButton.styleFrom(
                    visualDensity: VisualDensity.compact,
                    textStyle: const TextStyle(fontSize: 11),
                    selectedForegroundColor: telemetryAccent,
                    selectedBackgroundColor: telemetryAccent.withValues(
                      alpha: .1,
                    ),
                  ),
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          frames.isEmpty
              ? 'No received samples at the displayed time.'
              : '${frames.length} received samples · ${coverage}s of ${_window}s window · '
                    '${utcTime(sampleTime(frames.first))}–${utcTime(sampleTime(frames.last))} UTC'
                    '${gaps > 0 ? ' · $gaps sequence gaps' : ''}',
          style: const TextStyle(fontSize: 10, color: telemetryMuted),
        ),
        const SizedBox(height: 5),
        const Text(
          'History builds as samples arrive (up to 600 per spacecraft). Gaps remain blank; diamonds mark saturated readings.',
          style: TextStyle(fontSize: 10, color: telemetryMuted, height: 1.5),
        ),
        const SizedBox(height: 17),
        if (catalog == null)
          TelemetryCatalogState(
            loading: mission.catalogLoading,
            version: version,
            error: mission.catalogError,
            retry: version == null ? null : () => mission.loadCatalog(version),
          )
        else if (panels.isEmpty)
          TelemetryNotice(
            icon: Icons.search_off,
            text:
                'No panels match “${_search.text}” in $_tab. Clear the filter or choose another subsystem.',
          )
        else ...[
          if (_tab == 'Space weather')
            const Padding(
              padding: EdgeInsets.only(bottom: 14),
              child: TelemetryNotice(
                icon: Icons.cloud_off_outlined,
                text:
                    'External space weather is not modeled. These source-dashboard families are explicitly unavailable; the body magnetic field uses a separate ideal dipole model.',
              ),
            ),
          if (_tab == 'ADCS')
            const Padding(
              padding: EdgeInsets.only(bottom: 14),
              child: TelemetryNotice(
                icon: Icons.explore_outlined,
                text:
                    'Ideal prescribed LVLH attitude. Zero pointing error is a model assumption; actuator dynamics and star-tracker measurements are not solved.',
              ),
            ),
          LayoutBuilder(
            builder: (context, constraints) {
              final columns = constraints.maxWidth >= 1250
                  ? 3
                  : constraints.maxWidth >= 760
                  ? 2
                  : 1;
              final width =
                  (constraints.maxWidth - (columns - 1) * 13) / columns;
              return Wrap(
                spacing: 13,
                runSpacing: 13,
                children: [
                  for (final panel in panels)
                    SizedBox(
                      width: width,
                      height: 294,
                      child: TelemetryChart(
                        key: ValueKey('${widget.selected}:${panel.title}'),
                        panel: panel,
                        definitions: definitions,
                        frames: frames,
                        current: current,
                        windowSeconds: _window,
                        end: end,
                      ),
                    ),
                ],
              );
            },
          ),
        ],
        const SizedBox(height: 19),
        if (catalog != null)
          TelemetryChannelInventory(
            definitions: definitions,
            frame: current,
            query: query,
          ),
        const SizedBox(height: 16),
        TelemetryNotice(
          icon: Icons.science_outlined,
          text: version == 'spacecraft.v1'
              ? 'Synthetic physical-model telemetry, not a replay of the reference CSVs. Electrical rails, three thermal nodes, powered acquisition, and ideal attitude are approximations; no real-spacecraft calibration or inferred health score is shown.'
              : 'Synthetic physical-model telemetry. This catalog supplies orbit, environment, and ideal energy-store measurements. Spacecraft subsystem panels require a spacecraft.v1 run.',
        ),
      ],
    );
  }
}
