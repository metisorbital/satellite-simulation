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
    this.focused = false,
    this.onFocusChanged,
    this.onSelected,
    this.visibleSatelliteIds,
  });
  final Mission mission;
  final String selected;
  final double? seconds;
  final bool focused;
  final ValueChanged<bool>? onFocusChanged;
  final ValueChanged<String>? onSelected;
  final List<String>? visibleSatelliteIds;

  @override
  State<TelemetryDashboard> createState() => _TelemetryDashboardState();
}

class _TelemetryDashboardState extends State<TelemetryDashboard> {
  String _tab = 'Overview';
  int _window = 60;
  TelemetryPanel? _expanded;
  bool _focusedBeforeExpansion = false;
  final _search = TextEditingController();

  void _expand(TelemetryPanel panel) {
    _focusedBeforeExpansion = widget.focused;
    setState(() => _expanded = panel);
    widget.onFocusChanged?.call(true);
  }

  void _closeExpanded() {
    setState(() => _expanded = null);
    widget.onFocusChanged?.call(_focusedBeforeExpansion);
  }

  @override
  void dispose() {
    _search.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final mission = widget.mission;
    final status = mission.status;
    final availableIds = (status?['satellites'] as List? ?? [])
        .map((item) => (item as Map)['satellite_id'] as String)
        .toList();
    final visibleIds = widget.visibleSatelliteIds == null
        ? availableIds
        : widget.visibleSatelliteIds!.where(availableIds.contains).toList();
    final selected = visibleIds.contains(widget.selected)
        ? widget.selected
        : (visibleIds.isEmpty ? widget.selected : visibleIds.first);
    final current = mission.playback.frameAt(selected, widget.seconds);
    final received = mission.playback.history[selected] ?? <JsonMap>[];
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

    if (_expanded != null) {
      return SafeArea(
        child: Padding(
          padding: const EdgeInsets.fromLTRB(28, 16, 28, 20),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: Text(
                      '$selected · $_tab · ${_window ~/ 60} min · $connection · ${current?['source_kind'] ?? 'Awaiting source'}',
                      style: const TextStyle(
                        fontSize: 12,
                        color: telemetryMuted,
                      ),
                    ),
                  ),
                  TextButton.icon(
                    onPressed: _closeExpanded,
                    icon: const Icon(Icons.fullscreen_exit, size: 18),
                    label: const Text('Close panel'),
                  ),
                ],
              ),
              const SizedBox(height: 12),
              Expanded(
                child: TelemetryChart(
                  key: ValueKey('expanded:$selected:${_expanded!.title}'),
                  panel: _expanded!,
                  definitions: definitions,
                  frames: frames,
                  current: current,
                  windowSeconds: _window,
                  end: end,
                  expanded: true,
                ),
              ),
            ],
          ),
        ),
      );
    }

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
                  'Telemetry',
                  style: TextStyle(
                    fontSize: 26,
                    letterSpacing: -.6,
                    fontWeight: FontWeight.w700,
                  ),
                ),
                const SizedBox(height: 10),
                Wrap(
                  spacing: 13,
                  runSpacing: 8,
                  crossAxisAlignment: WrapCrossAlignment.center,
                  children: [
                    SizedBox(
                      width: 170,
                      child: DropdownButtonHideUnderline(
                        child: DropdownButton<String>(
                          value: visibleIds.contains(selected)
                              ? selected
                              : null,
                          hint: const Text('Awaiting spacecraft'),
                          isDense: true,
                          isExpanded: true,
                          dropdownColor: telemetrySurface,
                          style: const TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Colors.white,
                          ),
                          items: [
                            for (final id in visibleIds)
                              DropdownMenuItem(value: id, child: Text(id)),
                          ],
                          onChanged: visibleIds.isEmpty
                              ? null
                              : (id) {
                                  if (id != null) widget.onSelected?.call(id);
                                },
                        ),
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
                    IconButton(
                      tooltip: widget.focused
                          ? 'Exit focus mode'
                          : 'Focus dashboard',
                      onPressed: () =>
                          widget.onFocusChanged?.call(!widget.focused),
                      icon: Icon(
                        widget.focused
                            ? Icons.fullscreen_exit
                            : Icons.fullscreen,
                        size: 18,
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ],
        ),
        const SizedBox(height: 16),
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
        if (!widget.focused) const SizedBox(height: 5),
        if (!widget.focused)
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
              final columns = constraints.maxWidth >= 760 ? 2 : 1;
              final width =
                  (constraints.maxWidth - (columns - 1) * 18) / columns;
              return Wrap(
                spacing: 18,
                runSpacing: 18,
                children: [
                  for (final panel in panels)
                    SizedBox(
                      width: width,
                      height: widget.focused ? 405 : 365,
                      child: TelemetryChart(
                        key: ValueKey('$selected:${panel.title}'),
                        panel: panel,
                        definitions: definitions,
                        frames: frames,
                        current: current,
                        windowSeconds: _window,
                        end: end,
                        onExpand: () => _expand(panel),
                      ),
                    ),
                ],
              );
            },
          ),
        ],
        const SizedBox(height: 19),
        if (!widget.focused && current != null)
          Padding(
            padding: const EdgeInsets.only(bottom: 12),
            child: Text(
              'Catalog ${version ?? 'unknown'} · Endpoint mode: ${current['mode']} · Interval mode: ${current['interval_mode'] ?? 'unknown'}',
              style: const TextStyle(color: telemetryMuted, fontSize: 11),
            ),
          ),
        if (catalog != null && !widget.focused)
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
