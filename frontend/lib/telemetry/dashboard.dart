import 'dart:math' as math;
import 'package:flutter/material.dart';
import '../api/mission.dart';
import '../scene/playback.dart';
import 'chart.dart';
import 'panels.dart';
import 'dashboard_widgets.dart';
import 'time_controls.dart';
import 'layout.dart';

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
  int _window = 3600;
  int _presetWindow = 3600;
  DateTime? _fixedEnd;
  String? _runId;
  final _layout = TelemetryLayout.load();
  List<JsonMap>? _filteredSource;
  DateTime? _filteredStart, _filteredEnd;
  List<JsonMap> _filteredFrames = const [];
  JsonMap? _catalogSource;
  Map<String, JsonMap> _definitions = {};

  Map<String, JsonMap> _catalogDefinitions(JsonMap? catalog) {
    if (!identical(catalog, _catalogSource)) {
      _catalogSource = catalog;
      _definitions = {
        for (final raw in catalog?['channels'] as List? ?? [])
          (raw as Map)['channel_id'] as String: Map<String, dynamic>.from(raw),
      };
    }
    return _definitions;
  }

  TelemetryPanel? _expanded;
  bool _focusedBeforeExpansion = false;
  final _search = TextEditingController();

  String? _historyKey;

  @override
  void initState() {
    super.initState();
    _scheduleHistory();
  }

  @override
  void didUpdateWidget(covariant TelemetryDashboard oldWidget) {
    super.didUpdateWidget(oldWidget);
    _scheduleHistory();
  }

  String get _selectedId {
    final configured = (widget.mission.status?['satellites'] as List? ?? [])
        .map((item) => item['satellite_id'] as String)
        .toList();
    final visible = widget.visibleSatelliteIds == null
        ? configured
        : configured.where(widget.visibleSatelliteIds!.contains).toList();
    return visible.contains(widget.selected)
        ? widget.selected
        : visible.firstOrNull ?? '';
  }

  DateTime? get _epoch => widget.mission.status == null
      ? null
      : DateTime.parse(widget.mission.status!['epoch_utc'] as String);
  DateTime? get _latest =>
      _epoch == null || (widget.mission.status!['committed_tick'] as int) < 0
      ? null
      : _epoch!.add(
          Duration(seconds: widget.mission.status!['committed_tick'] as int),
        );
  DateTime? get _rangeEnd =>
      _fixedEnd ??
      (_epoch == null || widget.seconds == null
          ? null
          : _epoch!.add(Duration(seconds: widget.seconds!.floor())));
  DateTime? get _rangeStart {
    final end = _rangeEnd;
    if (end == null || _epoch == null) return null;
    final start = end.subtract(Duration(seconds: _window));
    return start.isBefore(_epoch!) ? _epoch : start;
  }

  void _scheduleHistory() {
    final mission = widget.mission;
    final runId = mission.status?['run_id'] as String?;
    if (_runId != runId) {
      _runId = runId;
      _fixedEnd = null;
      _historyKey = null;
    }
    final selected = _selectedId;
    final key = '$runId:$selected:$_window:$_fixedEnd';
    if (runId == null || key == _historyKey) return;
    _historyKey = key;
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (mounted && key == _historyKey) {
        mission.cancelTelemetryHistory();
        if (selected.isNotEmpty) {
          mission.loadTelemetryHistory(selected, _window, end: _fixedEnd);
        }
      }
    });
  }

  void _setSelection(TelemetryRangeSelection selection) {
    setState(() {
      _window = selection.seconds;
      _fixedEnd = selection.end;
      if (selection.end == null) _presetWindow = selection.seconds;
    });
    _scheduleHistory();
  }

  void _selectRange(DateTime start, DateTime end) {
    if (_epoch == null || _latest == null || !_latest!.isAfter(_epoch!)) return;
    final available = _latest!.difference(_epoch!).inSeconds;
    final width = end
        .difference(start)
        .inSeconds
        .clamp(1, math.min(86400, available))
        .toInt();
    final last = end
        .difference(_epoch!)
        .inSeconds
        .clamp(width, available)
        .toInt();
    _setSelection(
      TelemetryRangeSelection(width, end: _epoch!.add(Duration(seconds: last))),
    );
  }

  void _zoomRange(double factor) {
    final start = _rangeStart, end = _rangeEnd;
    if (start == null || end == null) return;
    final width = math.max(
      1,
      (end.difference(start).inSeconds * factor).round(),
    );
    final center = start.add(
      Duration(seconds: end.difference(start).inSeconds ~/ 2),
    );
    final nextStart = center.subtract(Duration(seconds: width ~/ 2));
    _selectRange(nextStart, nextStart.add(Duration(seconds: width)));
  }

  void _shiftRange(int direction) {
    final start = _rangeStart, end = _rangeEnd;
    if (start == null || end == null) return;
    final shift = Duration(
      seconds: math.max(1, end.difference(start).inSeconds ~/ 2) * direction,
    );
    _selectRange(start.add(shift), end.add(shift));
  }

  void _resetRange() => _setSelection(TelemetryRangeSelection(_presetWindow));
  void _refreshHistory() =>
      widget.mission.loadTelemetryHistory(_selectedId, _window, end: _fixedEnd);

  List<JsonMap> _framesInRange(
    List<JsonMap> source,
    DateTime? start,
    DateTime? end,
  ) {
    if (identical(source, _filteredSource) &&
        start == _filteredStart &&
        end == _filteredEnd) {
      return _filteredFrames;
    }
    _filteredSource = source;
    _filteredStart = start;
    _filteredEnd = end;
    return _filteredFrames = start == null || end == null
        ? const []
        : source
              .where((frame) {
                final time = sampleTime(frame);
                return !time.isBefore(start) && !time.isAfter(end);
              })
              .toList(growable: false);
  }

  Future<void> _editPanels() async {
    if (await editTelemetryLayout(
          context,
          _layout,
          _tab,
          telemetryPanels[_tab]!,
        ) &&
        mounted) {
      setState(() {});
    }
  }

  Widget _panelMenu(TelemetryPanel panel) => PopupMenuButton<String>(
    tooltip: 'Panel layout: ${panel.title}',
    onSelected: (value) => setState(() {
      if (value == 'width') _layout.setWide(panel, !_layout.isWide(panel));
      if (value == 'height') _layout.setTall(panel, !_layout.isTall(panel));
      _layout.save();
    }),
    itemBuilder: (_) => [
      PopupMenuItem(
        value: 'width',
        child: Text(
          _layout.isWide(panel) ? 'Standard width' : 'Full row width',
        ),
      ),
      PopupMenuItem(
        value: 'height',
        child: Text(_layout.isTall(panel) ? 'Standard height' : 'Tall panel'),
      ),
    ],
    icon: const Icon(Icons.more_vert, size: 17, color: telemetryMuted),
  );

  Widget _timeControls(DateTime? start, DateTime? end) => TelemetryTimeControls(
    seconds: _window,
    start: start,
    end: end,
    epoch: _epoch,
    latest: _latest,
    live: _fixedEnd == null,
    loading: widget.mission.historyLoading,
    onSelect: _setSelection,
    onZoom: _zoomRange,
    onShift: _shiftRange,
    onToggleLive: () {
      if (_fixedEnd == null && end != null) {
        _selectRange(end.subtract(Duration(seconds: _window)), end);
      } else {
        _setSelection(TelemetryRangeSelection(_window));
      }
    },
    onReset: _resetRange,
    onRefresh: _refreshHistory,
  );

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
    final selected = _selectedId;
    final liveCurrent = mission.playback.frameAt(selected, widget.seconds);
    final received = mission.telemetryHistory(selected, end: _fixedEnd);
    final end = _rangeEnd;
    final start = _rangeStart;
    final chartWindow = start == null || end == null
        ? _window
        : math.max(1, end.difference(start).inSeconds);
    final frames = _framesInRange(received, start, end);
    final current = _fixedEnd == null ? liveCurrent : frames.lastOrNull;
    final sourceKind = (current ?? liveCurrent)?['source_kind'];
    final sourceLabel = sourceKind == 'observed'
        ? 'OBSERVED'
        : sourceKind == 'synthetic'
        ? 'SYNTHETIC'
        : 'AWAITING SOURCE';
    final version =
        (current ??
                liveCurrent ??
                (received.isEmpty ? null : received.last))?['catalog_version']
            as String?;
    final catalog = mission.catalogs[version];
    final definitions = _catalogDefinitions(catalog);
    final query = _search.text.trim().toLowerCase();
    final panels = _layout
        .visiblePanels(_tab, telemetryPanels[_tab]!)
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
                      '$selected · $_tab · ${rangeDuration(chartWindow)} · ${_fixedEnd == null ? 'Live' : 'Historical'} · $connection · $sourceLabel',
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
              _timeControls(start, end),
              if (mission.historyLoading)
                const LinearProgressIndicator(minHeight: 2),
              if (mission.historyError != null)
                Text(
                  mission.historyError!,
                  style: const TextStyle(color: telemetryMuted, fontSize: 11),
                ),
              const SizedBox(height: 12),
              Expanded(
                child: TelemetryChart(
                  key: ValueKey('expanded:$selected:${_expanded!.title}'),
                  panel: _expanded!,
                  definitions: definitions,
                  frames: frames,
                  current: current,
                  windowSeconds: chartWindow,
                  end: end,
                  expanded: true,
                  onRangeSelected: _selectRange,
                  onResetRange: _resetRange,
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
                      _fixedEnd == null ? 'LIVE RANGE' : 'HISTORICAL RANGE',
                      color: _fixedEnd == null
                          ? telemetryAccent
                          : const Color(0xffffc568),
                    ),
                    TelemetryBadge(sourceLabel),
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
        _timeControls(start, end),
        const SizedBox(height: 12),
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
            OutlinedButton.icon(
              onPressed: _editPanels,
              icon: const Icon(Icons.dashboard_customize_outlined, size: 17),
              label: const Text('Edit panels'),
            ),
          ],
        ),
        const SizedBox(height: 10),
        Text(
          frames.isEmpty
              ? 'No samples in the selected time range.'
              : '${frames.length} received samples · ${coverage}s of ${chartWindow}s displayed · '
                    '${utcTime(sampleTime(frames.first))}–${utcTime(sampleTime(frames.last))} UTC'
                    '${gaps > 0 ? ' · $gaps sequence gaps' : ''}',
          style: const TextStyle(fontSize: 10, color: telemetryMuted),
        ),
        if (mission.historyLoading)
          const Padding(
            padding: EdgeInsets.only(top: 6),
            child: Text(
              'Loading selected history…',
              style: TextStyle(fontSize: 10, color: telemetryMuted),
            ),
          ),
        if (mission.historyError != null)
          Row(
            children: [
              Expanded(
                child: Text(
                  mission.historyError!,
                  style: const TextStyle(fontSize: 10, color: telemetryMuted),
                ),
              ),
              TextButton(
                onPressed: () => mission.loadTelemetryHistory(
                  selected,
                  _window,
                  end: _fixedEnd,
                ),
                child: const Text('Retry history'),
              ),
            ],
          ),
        if (!widget.focused) const SizedBox(height: 5),
        if (!widget.focused)
          const Text(
            'Drag across a chart to zoom all panels. Missing readings stay blank; diamonds mark saturated samples.',
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
            text: query.isEmpty
                ? 'No panels are visible. Use Edit panels to restore them.'
                : 'No panels match “${_search.text}” in $_tab. Clear the filter or choose another subsystem.',
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
              final columns = math.min(
                _layout.columns,
                math.max(1, (constraints.maxWidth / 440).floor()),
              );
              final width =
                  (constraints.maxWidth - (columns - 1) * 18) / columns;
              return Wrap(
                spacing: 18,
                runSpacing: 18,
                children: [
                  for (final panel in panels)
                    SizedBox(
                      width: _layout.isWide(panel)
                          ? constraints.maxWidth
                          : width,
                      height: _layout.isTall(panel)
                          ? 540
                          : (widget.focused ? 425 : 390),
                      child: TelemetryChart(
                        key: ValueKey('$selected:${panel.title}'),
                        panel: panel,
                        definitions: definitions,
                        frames: frames,
                        current: current,
                        windowSeconds: chartWindow,
                        end: end,
                        onExpand: () => _expand(panel),
                        onRangeSelected: _selectRange,
                        onResetRange: _resetRange,
                        headerActions: _panelMenu(panel),
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
