import 'dart:math' as math;
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/scheduler.dart';

import 'api/mission.dart';
import 'auth/operator_gate.dart';
import 'mission_shell.dart';
import 'overview_inspector.dart';
import 'scene/globe.dart';
import 'scene/playback.dart';
import 'telemetry/dashboard.dart';
import 'shift_log/shift_log_dialog.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();
  SemanticsBinding.instance.ensureSemantics();
  runApp(const MetisApp());
}

/// Flutter mission control shell; all physical values come from the backend.
class MetisApp extends StatelessWidget {
  const MetisApp({super.key});
  @override
  Widget build(BuildContext context) => MaterialApp(
    title: 'Metis Orbital',
    debugShowCheckedModeBanner: false,
    theme:
        ThemeData(
          brightness: Brightness.dark,
          useMaterial3: true,
          fontFamily: 'MetisSans',
        ).copyWith(
          scaffoldBackgroundColor: background,
          dialogTheme: DialogThemeData(
            backgroundColor: panel,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(9),
              side: const BorderSide(color: line),
            ),
          ),
          colorScheme: ColorScheme.fromSeed(
            seedColor: const Color(0xff8ccab9),
            brightness: Brightness.dark,
          ),
        ),
    home: OperatorGate(
      missionBuilder: (context, bootstrap, logout, expired) => MissionPage(
        bootstrap: bootstrap,
        onLogout: logout,
        onSessionExpired: expired,
      ),
    ),
  );
}

String reading(num? value, [int digits = 1]) =>
    value == null ? '—' : value.toStringAsFixed(digits);
String environment(JsonMap? frame) {
  final value = scalar(frame, 'environment.illumination_fraction');
  return value == null
      ? 'Awaiting sample'
      : value <= .001
      ? 'In eclipse'
      : value >= .999
      ? 'Sunlit'
      : 'Penumbra';
}

class MissionPage extends StatefulWidget {
  const MissionPage({
    super.key,
    required this.bootstrap,
    required this.onLogout,
    required this.onSessionExpired,
  });
  final JsonMap bootstrap;
  final Future<void> Function(String csrfToken) onLogout;
  final VoidCallback onSessionExpired;
  @override
  State<MissionPage> createState() => _MissionPageState();
}

class _MissionPageState extends State<MissionPage> {
  late final Mission mission;
  Ticker? ticker;
  final historyFocus = FocusNode(debugLabel: "Measurement history");
  String selected = '', chart = 'eps.battery_soc';
  bool telemetryVisible = false;
  bool telemetryFocused = false;
  final Set<String> hiddenSatellites = {};
  int lastDashboardSecond = -1;
  double? seconds;
  @override
  void initState() {
    super.initState();
    mission = Mission(onSessionExpired: widget.onSessionExpired);
    mission.addListener(refresh);
    mission.connect(initial: widget.bootstrap);
    ticker = Ticker((_) {
      final second = mission.clock.elapsed.inSeconds;
      if (!telemetryVisible || second != lastDashboardSecond) {
        lastDashboardSecond = second;
        refresh();
      }
    })..start();
  }

  void refresh() {
    if (!mounted) return;
    setState(() {
      final configured = mission.status?['satellites'] as List? ?? [];
      if (configured.isNotEmpty && visibleSatellites.isEmpty) {
        hiddenSatellites.remove(configured.first['satellite_id']);
      }
      final satellites = visibleSatellites;
      if (!satellites.any((s) => s['satellite_id'] == selected)) {
        selected = satellites.isEmpty
            ? ''
            : satellites.first['satellite_id'] as String;
      }
      seconds = mission.playback.time(mission.now);
    });
  }

  @override
  void dispose() {
    ticker?.dispose();
    historyFocus.dispose();
    mission.removeListener(refresh);
    mission.dispose();
    super.dispose();
  }

  void showInfo() => showDialog<void>(
    context: context,
    builder: (context) => PointerInterceptor(
      child: SizedBox.expand(
        child: AlertDialog(
          title: const Text('Simulation model & credits'),
          content: const SizedBox(
            width: 520,
            child: SingleChildScrollView(
              child: Text(
                'Deterministic synthetic mission: backend J2 gravity, Earth-fixed positions, solar-disk eclipse geometry, ideal Sun-tracking panels, and bounded battery energy.\n\n'
                'This is an engineering simulation, not a flight-certified model. Visual lighting is approximate; measured eclipse and power come from the backend. Symbols are enlarged. The predicted orbit contains positions only, never future power or health.\n\n'
                'Drag to rotate · Scroll to zoom\n\nEarth texture: three.js contributors (MIT). Rendering: CesiumJS (Apache 2.0). Imagery and rendering assets are bundled locally.',
              ),
            ),
          ),
          actions: [
            TextButton(
              onPressed: () {
                globeCommand('metis-earth', 'reset');
                Navigator.pop(context);
              },
              child: const Text('Reset Earth view'),
            ),
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Close'),
            ),
          ],
        ),
      ),
    ),
  );

  Future<void> showConstellationEditor() async {
    final source = mission.editableSatellites;
    if (source == null) return;
    final draft = (jsonDecode(jsonEncode(source)) as List)
        .map((item) => Map<String, dynamic>.from(item as Map))
        .toList();
    Map<String, TextEditingController> makeControllers(JsonMap satellite) {
      final orbit = satellite['orbit'] as Map<String, dynamic>;
      final power = satellite['power'] as Map<String, dynamic>?;
      final values = <String, dynamic>{
        'satellite_id': satellite['satellite_id'],
        'name': satellite['name'],
        'color': (satellite['visual'] as Map)['color'],
        for (final key in [
          'a_m',
          'e',
          'i_deg',
          'raan_deg',
          'argp_deg',
          'true_anomaly_deg',
        ])
          key: orbit[key],
        if (power != null) ...{
          for (final key in [
            'panel_area_m2',
            'panel_efficiency',
            'battery_capacity_wh',
            'battery_initial_soc',
          ])
            key: power[key],
          for (final key in ['nominal', 'payload_active', 'safe'])
            key: (power['loads_w'] as Map)[key],
        },
      };
      return values.map(
        (key, value) => MapEntry(key, TextEditingController(text: '$value')),
      );
    }

    final controllers = draft.map(makeControllers).toList();
    final allocatedControllers = <TextEditingController>[
      for (final item in controllers) ...item.values,
    ];
    const numericKeys = [
      'a_m',
      'e',
      'i_deg',
      'raan_deg',
      'argp_deg',
      'true_anomaly_deg',
      'panel_area_m2',
      'panel_efficiency',
      'battery_capacity_wh',
      'battery_initial_soc',
      'nominal',
      'payload_active',
      'safe',
    ];
    bool syncDraft() {
      for (var index = 0; index < draft.length; index++) {
        final controls = controllers[index];
        final satellite = draft[index];
        final id = controls['satellite_id']!.text.trim();
        final name = controls['name']!.text.trim();
        final color = controls['color']!.text.trim();
        if (!RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(id) ||
            name.isEmpty ||
            !RegExp(r'^#[0-9A-Fa-f]{6}$').hasMatch(color) ||
            numericKeys
                .where(controls.containsKey)
                .any((key) => double.tryParse(controls[key]!.text) == null)) {
          return false;
        }
        satellite['satellite_id'] = id;
        satellite['name'] = name;
        (satellite['visual'] as Map<String, dynamic>)['color'] = color;
        final orbit = satellite['orbit'] as Map<String, dynamic>;
        for (final key in [
          'a_m',
          'e',
          'i_deg',
          'raan_deg',
          'argp_deg',
          'true_anomaly_deg',
        ]) {
          orbit[key] = double.parse(controls[key]!.text);
        }
        final power = satellite['power'] as Map<String, dynamic>?;
        if (power != null) {
          for (final key in [
            'panel_area_m2',
            'panel_efficiency',
            'battery_capacity_wh',
            'battery_initial_soc',
          ]) {
            power[key] = double.parse(controls[key]!.text);
          }
          final loads = power['loads_w'] as Map<String, dynamic>;
          for (final key in ['nominal', 'payload_active', 'safe']) {
            loads[key] = double.parse(controls[key]!.text);
          }
        }
      }
      return true;
    }

    final formKey = GlobalKey<FormState>();
    var selectedIndex = 0;
    String? issue;
    final route = DialogRoute<void>(
      context: context,
      builder: (dialogContext) => StatefulBuilder(
        builder: (context, update) {
          final satellite = draft[selectedIndex];
          final orbit = satellite['orbit'] as Map<String, dynamic>;
          final power = satellite['power'] as Map<String, dynamic>?;
          Widget field(
            String title,
            String key,
            Map<String, dynamic> target, {
            bool numeric = false,
          }) => TextFormField(
            key: ValueKey('$selectedIndex-$key'),
            controller: controllers[selectedIndex][key],
            decoration: InputDecoration(labelText: title, isDense: true),
            keyboardType: numeric
                ? const TextInputType.numberWithOptions(
                    decimal: true,
                    signed: true,
                  )
                : TextInputType.text,
            validator: (value) {
              if (value == null || value.trim().isEmpty) return 'Required';
              if (numeric && double.tryParse(value) == null) {
                return 'Enter a number';
              }
              if (key == 'satellite_id' &&
                  !RegExp(r'^[A-Za-z0-9_-]{1,64}$').hasMatch(value)) {
                return 'Use 1–64 letters, numbers, _ or -';
              }
              if (key == 'color' &&
                  !RegExp(r'^#[0-9A-Fa-f]{6}$').hasMatch(value)) {
                return 'Use a six-digit color, such as #8FD3FF';
              }
              return null;
            },
          );
          return PointerInterceptor(
            child: AlertDialog(
              title: const Text('Edit constellation'),
              content: SizedBox(
                width: 620,
                height: 520,
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    Text(
                      mission.canReplaceRun
                          ? 'Saving creates a new run and clears scheduled mode changes. The current run remains in history.'
                          : 'Stop this run before saving constellation changes.',
                      style: TextStyle(fontSize: 12, color: muted),
                    ),
                    const SizedBox(height: 12),
                    Row(
                      children: [
                        Expanded(
                          child: DropdownButton<int>(
                            isExpanded: true,
                            value: selectedIndex,
                            items: [
                              for (var i = 0; i < draft.length; i++)
                                DropdownMenuItem(
                                  value: i,
                                  child: Text(
                                    '${draft[i]['satellite_id']} · ${draft[i]['name']}',
                                  ),
                                ),
                            ],
                            onChanged: (index) {
                              if (index != null) {
                                update(() {
                                  selectedIndex = index;
                                  issue = null;
                                });
                              }
                            },
                          ),
                        ),
                        IconButton(
                          tooltip: 'Add satellite',
                          onPressed: draft.length >= 10
                              ? null
                              : () => update(() {
                                  final copy = Map<String, dynamic>.from(
                                    jsonDecode(jsonEncode(draft[selectedIndex]))
                                        as Map,
                                  );
                                  var number = 1;
                                  while (draft.any(
                                    (item) =>
                                        item['satellite_id'] == 'METIS-$number',
                                  )) {
                                    number++;
                                  }
                                  copy['satellite_id'] = 'METIS-$number';
                                  copy['name'] = 'Metis $number';
                                  copy['operations'] = [];
                                  draft.add(copy);
                                  final created = makeControllers(copy);
                                  controllers.add(created);
                                  allocatedControllers.addAll(created.values);
                                  selectedIndex = draft.length - 1;
                                  issue = null;
                                }),
                          icon: const Icon(Icons.add),
                        ),
                        IconButton(
                          tooltip: 'Remove satellite',
                          onPressed: draft.length <= 1
                              ? null
                              : () => update(() {
                                  draft.removeAt(selectedIndex);
                                  controllers.removeAt(selectedIndex);
                                  selectedIndex = selectedIndex.clamp(
                                    0,
                                    draft.length - 1,
                                  );
                                  issue = null;
                                }),
                          icon: const Icon(Icons.delete_outline),
                        ),
                      ],
                    ),
                    Expanded(
                      child: SingleChildScrollView(
                        child: Form(
                          key: formKey,
                          child: Column(
                            children: [
                              field('Satellite ID', 'satellite_id', satellite),
                              field('Name', 'name', satellite),
                              field(
                                'Marker color',
                                'color',
                                satellite['visual'] as Map<String, dynamic>,
                              ),
                              DropdownButtonFormField<String>(
                                key: ValueKey('$selectedIndex-initial_mode'),
                                initialValue:
                                    satellite['initial_mode'] as String,
                                decoration: const InputDecoration(
                                  labelText: 'Initial mode',
                                ),
                                items: [
                                  for (final mode in [
                                    'nominal',
                                    'payload_active',
                                    'safe',
                                  ])
                                    DropdownMenuItem(
                                      value: mode,
                                      child: Text(mode.replaceAll('_', ' ')),
                                    ),
                                ],
                                onChanged: (mode) {
                                  if (mode != null) {
                                    satellite['initial_mode'] = mode;
                                  }
                                },
                              ),
                              const SizedBox(height: 14),
                              const Align(
                                alignment: Alignment.centerLeft,
                                child: Text(
                                  'ORBIT',
                                  style: TextStyle(color: muted, fontSize: 11),
                                ),
                              ),
                              for (final entry in [
                                ('Semi-major axis (m)', 'a_m'),
                                ('Eccentricity', 'e'),
                                ('Inclination (deg)', 'i_deg'),
                                ('RAAN (deg)', 'raan_deg'),
                                ('Argument of periapsis (deg)', 'argp_deg'),
                                ('True anomaly (deg)', 'true_anomaly_deg'),
                              ])
                                field(entry.$1, entry.$2, orbit, numeric: true),
                              if (power != null) ...[
                                const SizedBox(height: 16),
                                const Align(
                                  alignment: Alignment.centerLeft,
                                  child: Text(
                                    'POWER SYSTEM',
                                    style: TextStyle(
                                      color: muted,
                                      fontSize: 11,
                                    ),
                                  ),
                                ),
                                field(
                                  'Panel area (m²)',
                                  'panel_area_m2',
                                  power,
                                  numeric: true,
                                ),
                                field(
                                  'Panel efficiency',
                                  'panel_efficiency',
                                  power,
                                  numeric: true,
                                ),
                                field(
                                  'Battery capacity (Wh)',
                                  'battery_capacity_wh',
                                  power,
                                  numeric: true,
                                ),
                                field(
                                  'Initial battery charge (0–1)',
                                  'battery_initial_soc',
                                  power,
                                  numeric: true,
                                ),
                                for (final entry in [
                                  ('Nominal load (W)', 'nominal'),
                                  ('Payload active load (W)', 'payload_active'),
                                  ('Safe load (W)', 'safe'),
                                ])
                                  field(
                                    entry.$1,
                                    entry.$2,
                                    power['loads_w'] as Map<String, dynamic>,
                                    numeric: true,
                                  ),
                              ],
                            ],
                          ),
                        ),
                      ),
                    ),
                    if (issue != null)
                      Padding(
                        padding: const EdgeInsets.only(top: 8),
                        child: Text(
                          issue!,
                          style: const TextStyle(color: gold, fontSize: 11),
                        ),
                      ),
                  ],
                ),
              ),
              actions: [
                TextButton(
                  onPressed: () => Navigator.pop(dialogContext),
                  child: const Text('Cancel'),
                ),
                FilledButton(
                  onPressed: mission.canReplaceRun
                      ? () {
                          if (!(formKey.currentState?.validate() ?? false)) {
                            return;
                          }
                          if (!syncDraft()) {
                            update(
                              () => issue =
                                  'Check all satellite fields before saving.',
                            );
                            return;
                          }
                          final ids = draft
                              .map((item) => item['satellite_id'])
                              .toList();
                          if (ids.toSet().length != ids.length) {
                            update(
                              () => issue = 'Satellite IDs must be unique.',
                            );
                            return;
                          }
                          for (final satellite in draft) {
                            satellite['operations'] = <dynamic>[];
                          }
                          Navigator.pop(dialogContext);
                          mission.replaceSatellites(draft);
                        }
                      : null,
                  child: const Text('Save as new run'),
                ),
              ],
            ),
          );
        },
      ),
    );
    await Navigator.of(context, rootNavigator: true).push(route);
    await route.completed;
    for (final controller in allocatedControllers) {
      controller.dispose();
    }
  }

  List<JsonMap> get visibleSatellites => [
    for (final raw in mission.status?['satellites'] as List? ?? [])
      if (!hiddenSatellites.contains(raw['satellite_id']))
        Map<String, dynamic>.from(raw as Map),
  ];

  void navigate(bool telemetry) => setState(() {
    telemetryVisible = telemetry;
    telemetryFocused = false;
  });

  void logout() {
    if (mission.busy) return;
    final token = mission.csrfToken.isNotEmpty
        ? mission.csrfToken
        : widget.bootstrap['csrf_token'] as String;
    mission.suspend();
    widget.onLogout(token);
  }

  void showShiftLog() {
    final runId = mission.status?['run_id'] as String?;
    if (!mission.canUseShiftLog || runId == null) return;
    showDialog<void>(
      context: context,
      barrierDismissible: false,
      builder: (_) => ShiftLogDialog(
        mission: mission,
        runId: runId,
        operatorName:
            (widget.bootstrap['operator'] as Map)['display_name'] as String,
      ),
    );
  }

  Future<void> showSettings() async {
    final edit = await showDialog<bool>(
      context: context,
      builder: (dialogContext) => PointerInterceptor(
        child: StatefulBuilder(
          builder: (context, update) => ListenableBuilder(
            listenable: mission,
            builder: (context, _) {
              final satellites = mission.status?['satellites'] as List? ?? [];
              return AlertDialog(
                title: Row(
                  children: [
                    const Expanded(child: Text('Mission settings')),
                    IconButton(
                      tooltip: 'Close settings',
                      onPressed: () => Navigator.pop(dialogContext, false),
                      icon: const Icon(Icons.close),
                    ),
                  ],
                ),
                content: SizedBox(
                  width: 430,
                  child: SingleChildScrollView(
                    child: Column(
                      mainAxisSize: MainAxisSize.min,
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        const Text(
                          'Constellation',
                          style: TextStyle(fontSize: 17),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Choose spacecraft shown on the Earth view and telemetry dashboard. Hidden spacecraft continue simulating.',
                          style: TextStyle(
                            color: muted,
                            fontSize: 12,
                            height: 1.6,
                          ),
                        ),
                        const SizedBox(height: 18),
                        for (final raw in satellites)
                          SwitchListTile(
                            contentPadding: EdgeInsets.zero,
                            title: Text(raw['satellite_id'] as String),
                            subtitle: Text(raw['name'] as String),
                            value: !hiddenSatellites.contains(
                              raw['satellite_id'],
                            ),
                            onChanged:
                                !hiddenSatellites.contains(
                                      raw['satellite_id'],
                                    ) &&
                                    visibleSatellites.length == 1
                                ? null
                                : (visible) {
                                    setState(() {
                                      final id = raw['satellite_id'] as String;
                                      if (visible) {
                                        hiddenSatellites.remove(id);
                                      } else {
                                        hiddenSatellites.add(id);
                                      }
                                      if (hiddenSatellites.contains(selected)) {
                                        selected =
                                            visibleSatellites
                                                    .first['satellite_id']
                                                as String;
                                      }
                                    });
                                    update(() {});
                                  },
                          ),
                        const Divider(height: 32),
                        const Text(
                          'Simulation configuration',
                          style: TextStyle(fontSize: 17),
                        ),
                        const SizedBox(height: 10),
                        const Text(
                          'Add or edit spacecraft in a new run. An active run keeps its original configuration.',
                          style: TextStyle(
                            color: muted,
                            fontSize: 12,
                            height: 1.6,
                          ),
                        ),
                        const SizedBox(height: 18),
                        FilledButton.tonalIcon(
                          onPressed: mission.canEdit && !mission.busy
                              ? () => Navigator.pop(dialogContext, true)
                              : null,
                          icon: const Icon(Icons.edit_outlined, size: 17),
                          label: const Text('Edit constellation'),
                        ),
                        if (!mission.canReplaceRun)
                          const Padding(
                            padding: EdgeInsets.only(top: 12),
                            child: Text(
                              'Stop the run before saving configuration changes.',
                              style: TextStyle(fontSize: 11, color: gold),
                            ),
                          ),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
      ),
    );
    if (edit == true && mounted) await showConstellationEditor();
  }

  @override
  Widget build(BuildContext context) {
    final status = mission.status;
    final satellites = visibleSatellites;
    final frame = mission.playback.frameAt(selected, seconds);
    final descriptor = satellites
        .where((s) => s['satellite_id'] == selected)
        .firstOrNull;
    final utc = status == null || seconds == null
        ? null
        : DateTime.parse(status['epoch_utc'] as String)
              .add(Duration(milliseconds: (seconds! * 1000).round()))
              .toIso8601String();
    final operator = widget.bootstrap['operator'] as Map;
    final focused = telemetryVisible && telemetryFocused;
    final stale = mission.playback.isStale(mission.now);
    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 1150;
          final compact = constraints.maxWidth < 900;
          final body = Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (!focused)
                SizedBox(
                  width: compact ? 64 : 220,
                  child: MissionSidebar(
                    telemetrySelected: telemetryVisible,
                    onOverview: () => navigate(false),
                    onTelemetry: () => navigate(true),
                    onSettings: showSettings,
                    onInfo: showInfo,
                    onLogout: logout,
                    onShiftLog: mission.canUseShiftLog && status != null
                        ? showShiftLog
                        : null,
                    operatorName: operator['display_name'] as String,
                    operatorLogin: operator['login'] as String,
                    busy: mission.busy,
                    connected: mission.playback.connected && !stale,
                    runLabel: status?['status'] as String? ?? 'Connecting',
                    compact: compact,
                  ),
                ),
              Expanded(
                child: Column(
                  children: [
                    if (!focused)
                      MissionHeader(
                        telemetrySelected: telemetryVisible,
                        runState: status?['status'] as String? ?? 'Connecting',
                        connectionLabel: !mission.playback.connected
                            ? 'Disconnected'
                            : stale
                            ? 'Stream delayed'
                            : 'Stream connected',
                        utc: utc == null
                            ? 'Awaiting sample'
                            : '${clockTime(utc)} UTC',
                        connected: mission.playback.connected && !stale,
                        compact: compact,
                      ),
                    if (!telemetryVisible) toolbar(status, utc, desktop),
                    if (mission.error != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 22,
                          vertical: 6,
                        ),
                        color: const Color(0xff2b211d),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.info_outline,
                              size: 16,
                              color: gold,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: txt(mission.error!, color: gold, size: 11),
                            ),
                            TextButton(
                              onPressed: mission.connecting
                                  ? null
                                  : mission.connect,
                              child: const Text('Reconnect'),
                            ),
                          ],
                        ),
                      ),
                    Expanded(
                      child: telemetryVisible
                          ? TelemetryDashboard(
                              mission: mission,
                              selected: selected,
                              seconds: seconds,
                              focused: telemetryFocused,
                              onFocusChanged: (value) =>
                                  setState(() => telemetryFocused = value),
                              onSelected: (id) => setState(() => selected = id),
                              visibleSatelliteIds: [
                                for (final satellite in satellites)
                                  satellite['satellite_id'] as String,
                              ],
                            )
                          : Row(
                              crossAxisAlignment: CrossAxisAlignment.stretch,
                              children: [
                                Expanded(
                                  child: Column(
                                    children: [
                                      Expanded(
                                        child: orbitStage(
                                          status,
                                          frame,
                                          satellites.length,
                                          desktop,
                                        ),
                                      ),
                                      if (!compact)
                                        Focus(
                                          focusNode: historyFocus,
                                          child: historyPanel(),
                                        )
                                      else
                                        Padding(
                                          padding: const EdgeInsets.all(12),
                                          child: OutlinedButton.icon(
                                            onPressed: () => navigate(true),
                                            icon: const Icon(
                                              Icons.show_chart,
                                              size: 17,
                                            ),
                                            label: const Text(
                                              'Open spacecraft telemetry',
                                            ),
                                          ),
                                        ),
                                    ],
                                  ),
                                ),
                                if (desktop)
                                  SizedBox(
                                    width: 280,
                                    child: telemetry(descriptor, frame),
                                  ),
                              ],
                            ),
                    ),
                    if (!telemetryVisible) footer(status, desktop),
                  ],
                ),
              ),
            ],
          );
          return body;
        },
      ),
    );
  }

  Widget spacecraftSelector() => DropdownButtonHideUnderline(
    child: DropdownButton<String>(
      value: visibleSatellites.any((s) => s['satellite_id'] == selected)
          ? selected
          : null,
      hint: txt('Awaiting spacecraft', size: 12),
      dropdownColor: panel,
      borderRadius: BorderRadius.circular(6),
      items: [
        for (final satellite in visibleSatellites)
          DropdownMenuItem(
            value: satellite['satellite_id'] as String,
            child: PointerInterceptor(
              child: Text(
                satellite['satellite_id'] as String,
                style: const TextStyle(fontSize: 12, color: textColor),
              ),
            ),
          ),
      ],
      onChanged: (id) {
        if (id != null) setState(() => selected = id);
      },
    ),
  );

  Widget toolbar(JsonMap? status, String? utc, bool desktop) {
    final active = status?['status'] == 'running';
    final starting =
        status?['status'] == 'created' || status?['committed_tick'] == -1;
    final primaryAction = active
        ? 'pause'
        : starting
        ? 'start'
        : 'resume';
    final disabled =
        status == null ||
        mission.busy ||
        [
          'completed',
          'stopped',
          'failed',
          'aborted',
        ].contains(status['status']);
    final controls = mission.canControl
        ? Row(
            mainAxisSize: MainAxisSize.min,
            children: [
              SizedBox(
                height: 34,
                child: FilledButton.icon(
                  onPressed: disabled || !mission.canPerform(primaryAction)
                      ? null
                      : () => mission.control(primaryAction),
                  style: FilledButton.styleFrom(
                    backgroundColor: const Color(0xffa9d5cb),
                    foregroundColor: const Color(0xff122a2e),
                    disabledBackgroundColor: const Color(0xff263b42),
                    disabledForegroundColor: muted,
                    padding: const EdgeInsets.symmetric(horizontal: 13),
                    shape: RoundedRectangleBorder(
                      borderRadius: BorderRadius.circular(4),
                    ),
                    textStyle: const TextStyle(
                      fontSize: 10,
                      fontWeight: FontWeight.w700,
                    ),
                  ),
                  icon: Icon(active ? Icons.pause : Icons.play_arrow, size: 14),
                  label: Text(
                    mission.busy
                        ? 'Applying…'
                        : active
                        ? 'Pause'
                        : starting
                        ? 'Start run'
                        : 'Resume',
                  ),
                ),
              ),
              if (mission.canPerform('set_speed')) ...[
                const SizedBox(width: 10),
                Container(
                  height: 34,
                  padding: const EdgeInsets.all(3),
                  decoration: box(color: const Color(0xff0c1721)),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final speed in [1, 5, 20])
                        ChoiceChip(
                          label: Text('$speed×'),
                          selected: status?['requested_speed'] == speed,
                          onSelected: disabled
                              ? null
                              : (_) => mission.control('set_speed', speed),
                          showCheckmark: false,
                          visualDensity: const VisualDensity(
                            horizontal: -4,
                            vertical: -4,
                          ),
                          materialTapTargetSize:
                              MaterialTapTargetSize.shrinkWrap,
                          padding: const EdgeInsets.symmetric(horizontal: 3),
                          labelPadding: const EdgeInsets.symmetric(
                            horizontal: 5,
                          ),
                          backgroundColor: Colors.transparent,
                          selectedColor: const Color(0xff2c4551),
                          disabledColor: Colors.transparent,
                          side: BorderSide.none,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(2),
                          ),
                          labelStyle: TextStyle(
                            fontSize: 10,
                            color: status?['requested_speed'] == speed
                                ? textColor
                                : muted,
                          ),
                        ),
                    ],
                  ),
                ),
              ],
              if (mission.canPerform('stop')) ...[
                const SizedBox(width: 10),
                Container(
                  width: 34,
                  height: 34,
                  decoration: box(),
                  child: IconButton(
                    tooltip: 'Stop simulation',
                    padding: EdgeInsets.zero,
                    onPressed: disabled || starting
                        ? null
                        : () => mission.control('stop'),
                    icon: const Icon(Icons.crop_square, size: 14),
                    color: const Color(0xffa3b8c7),
                  ),
                ),
              ],
              const SizedBox(width: 10),
              IconButton(
                tooltip: 'Reset simulation with a new run',
                onPressed: mission.busy || !mission.canReplaceRun
                    ? null
                    : mission.reset,
                icon: const Icon(Icons.restart_alt, size: 19),
              ),
            ],
          )
        : status == null
        ? const SizedBox.shrink()
        : badge('VIEW ONLY', muted);

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 24, vertical: 18),
      decoration: const BoxDecoration(
        color: background,
        border: Border(bottom: BorderSide(color: line)),
      ),
      child: LayoutBuilder(
        builder: (context, constraints) {
          final heading = Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              Semantics(
                header: true,
                child: txt(
                  'Mission overview',
                  size: 24,
                  weight: FontWeight.w500,
                  spacing: -.6,
                ),
              ),
              const SizedBox(height: 8),
              Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  txt('Spacecraft', size: 11, color: muted),
                  const SizedBox(width: 14),
                  spacecraftSelector(),
                ],
              ),
            ],
          );
          if (constraints.maxWidth >= 750) {
            return Row(
              children: [
                Expanded(child: heading),
                controls,
              ],
            );
          }
          return Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              heading,
              const SizedBox(height: 12),
              SingleChildScrollView(
                scrollDirection: Axis.horizontal,
                child: controls,
              ),
            ],
          );
        },
      ),
    );
  }

  Widget orbitStage(JsonMap? status, JsonMap? frame, int count, bool desktop) {
    final stale = mission.playback.isStale(mission.now) && status != null;
    final message = stale
        ? 'Data stale · view frozen'
        : status?['status'] == 'running'
        ? 'Live simulation'
        : '${status?['status'] ?? 'Establishing mission link'} · committed state';
    final lag = status == null || seconds == null
        ? null
        : math.max(0, (status['committed_tick'] as num) - seconds!);
    return LayoutBuilder(
      builder: (context, constraints) {
        final roomy = constraints.maxWidth >= 650;
        return Stack(
          children: [
            Positioned.fill(
              child: Semantics(
                label: 'Interactive Earth and satellite orbit view',
                child: Globe(
                  playback: mission.playback,
                  seconds: seconds,
                  selected: selected,
                  trajectory: mission.trajectory,
                  hiddenSatelliteIds: hiddenSatellites.toSet(),
                  onSelect: (id) => setState(() => selected = id),
                ),
              ),
            ),
            Positioned(
              left: 26,
              top: 26,
              child: IgnorePointer(
                child: Container(
                  padding: roomy
                      ? EdgeInsets.zero
                      : const EdgeInsets.symmetric(
                          horizontal: 12,
                          vertical: 10,
                        ),
                  decoration: roomy
                      ? null
                      : BoxDecoration(
                          color: panel.withValues(alpha: .88),
                          border: Border.all(color: line.withValues(alpha: .8)),
                          borderRadius: BorderRadius.circular(5),
                        ),
                  child: Row(
                    children: [
                      Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          label('SPACECRAFT', size: 7),
                          const SizedBox(height: 10),
                          Row(
                            children: [
                              txt(
                                count.toString().padLeft(2, '0'),
                                size: 18,
                                spacing: 2,
                              ),
                              const SizedBox(width: 8),
                              txt('in constellation', size: 8, color: muted),
                            ],
                          ),
                        ],
                      ),
                      if (constraints.maxWidth >= 410)
                        const SizedBox(width: 30),
                      if (constraints.maxWidth >= 410)
                        Column(
                          crossAxisAlignment: CrossAxisAlignment.start,
                          children: [
                            label('SELECTED ALTITUDE', size: 7),
                            const SizedBox(height: 10),
                            txt(
                              '${reading(scalar(frame, 'orbit.altitude_m') == null ? null : scalar(frame, 'orbit.altitude_m')! / 1000)} km',
                              size: 17,
                              spacing: 1.5,
                            ),
                          ],
                        ),
                    ],
                  ),
                ),
              ),
            ),
            if (desktop)
              Positioned(
                right: 22,
                top: 24,
                child: IgnorePointer(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.end,
                    children: [
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 10,
                          vertical: 7,
                        ),
                        decoration: box(color: const Color(0xe6111e29)),
                        child: Row(
                          children: [
                            const Icon(Icons.public, size: 12, color: muted),
                            const SizedBox(width: 6),
                            txt(
                              'Earth fixed',
                              size: 9,
                              color: const Color(0xff9db2c1),
                            ),
                          ],
                        ),
                      ),
                      const SizedBox(height: 10),
                      label('J2 ORBIT MODEL', size: 6),
                    ],
                  ),
                ),
              ),
            Positioned(
              right: 22,
              bottom: desktop ? 99 : 110,
              child: PointerInterceptor(
                child: Container(
                  width: 38,
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  decoration: box(
                    color: const Color(0xed111e28),
                    border: const Color(0xff304956),
                  ),
                  child: Column(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      for (final item in [
                        ('in', Icons.add, 'Zoom in'),
                        ('out', Icons.remove, 'Zoom out'),
                        (
                          'follow',
                          Icons.gps_fixed,
                          'Follow selected satellite',
                        ),
                        ('reset', Icons.fullscreen, 'Reset Earth view'),
                      ])
                        SizedBox(
                          height: 33,
                          child: IconButton(
                            tooltip: item.$3,
                            padding: EdgeInsets.zero,
                            onPressed: () =>
                                globeCommand('metis-earth', item.$1),
                            icon: Icon(
                              item.$2,
                              size: 18,
                              color: const Color(0xff93acb9),
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
            ),
            Positioned(
              left: 24,
              bottom: 37,
              child: IgnorePointer(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Container(
                          width: 16,
                          height: 1,
                          color: const Color(0xff8fbbc9),
                        ),
                        const SizedBox(width: 7),
                        txt(
                          'Predicted orbit',
                          size: 8,
                          color: const Color(0xffa1b6c4),
                        ),
                        const SizedBox(width: 12),
                        txt('·  Symbols enlarged', size: 8, color: muted),
                      ],
                    ),
                    const SizedBox(height: 7),
                    txt(
                      'Approximate visual lighting · WGS84 Earth',
                      size: 7,
                      color: muted,
                    ),
                  ],
                ),
              ),
            ),
            Positioned(
              right: 22,
              bottom: desktop && roomy ? 37 : 74,
              child: IgnorePointer(
                child: Container(
                  padding: const EdgeInsets.symmetric(
                    horizontal: 9,
                    vertical: 7,
                  ),
                  decoration: box(
                    color: const Color(0xe60e1b23),
                    border: const Color(0xff29454c),
                  ),
                  child: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      dot(stale ? gold : mint, 4),
                      const SizedBox(width: 6),
                      txt(message, size: 8, color: const Color(0xffa0c9c2)),
                      if (roomy) ...[
                        const SizedBox(width: 10),
                        txt('|', size: 8, color: muted),
                        const SizedBox(width: 8),
                        txt('${reading(lag)} s behind', size: 7, color: muted),
                      ],
                    ],
                  ),
                ),
              ),
            ),
          ],
        );
      },
    );
  }

  Widget telemetry(JsonMap? descriptor, JsonMap? frame) => OverviewInspector(
    descriptor: descriptor,
    frame: frame,
    onTelemetry: () => navigate(true),
  );

  Widget historyPanel() {
    final status = mission.status;
    final samples = (mission.playback.history[selected] ?? <JsonMap>[])
        .where(
          (f) =>
              status != null &&
              seconds != null &&
              frameSeconds(f, status) <= seconds!,
        )
        .toList();
    final soc = chart == 'eps.battery_soc';
    final value = samples.isEmpty ? null : scalar(samples.last, chart);
    return Container(
      height: 142,
      padding: const EdgeInsets.fromLTRB(24, 14, 24, 16),
      decoration: const BoxDecoration(
        color: Color(0xff0c1822),
        border: Border(top: BorderSide(color: line)),
      ),
      child: Column(
        children: [
          Row(
            children: [
              const Icon(Icons.show_chart, size: 14, color: muted),
              const SizedBox(width: 8),
              txt('Power history', size: 11),
              const SizedBox(width: 10),
              txt('|', size: 10, color: line),
              const SizedBox(width: 10),
              Expanded(child: txt(selected, size: 10, color: muted)),
              Container(
                height: 25,
                padding: const EdgeInsets.all(2),
                decoration: box(color: const Color(0xff101f29)),
                child: Row(
                  children: [
                    for (final item in [
                      ('Battery SOC', 'eps.battery_soc'),
                      ('Solar power', 'eps.solar_power_w'),
                    ])
                      TextButton(
                        onPressed: () => setState(() => chart = item.$2),
                        style: TextButton.styleFrom(
                          minimumSize: Size.zero,
                          padding: const EdgeInsets.symmetric(horizontal: 9),
                          backgroundColor: chart == item.$2
                              ? const Color(0xff2a414a)
                              : Colors.transparent,
                          foregroundColor: chart == item.$2
                              ? const Color(0xffbbd2d6)
                              : muted,
                          shape: RoundedRectangleBorder(
                            borderRadius: BorderRadius.circular(2),
                          ),
                        ),
                        child: Text(
                          item.$1,
                          style: const TextStyle(fontSize: 8),
                        ),
                      ),
                  ],
                ),
              ),
            ],
          ),
          const SizedBox(height: 16),
          Expanded(
            child: Row(
              children: [
                SizedBox(
                  width: 155,
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      txt(
                        '${reading(value == null ? null : value * (soc ? 100 : 1))} ${soc ? '%' : 'W'}',
                        size: 22,
                        color: soc ? mint : gold,
                        spacing: 1.7,
                      ),
                      const SizedBox(height: 5),
                      txt(
                        soc
                            ? 'Measured state of charge'
                            : 'Measured generation',
                        size: 10,
                        color: muted,
                      ),
                    ],
                  ),
                ),
                Expanded(
                  child: Column(
                    children: [
                      Expanded(
                        child: Semantics(
                          label: '$selected measured $chart history',
                          child: CustomPaint(
                            painter: HistoryPainter(
                              samples.map((f) => scalar(f, chart)).toList(),
                              soc,
                            ),
                            size: Size.infinite,
                          ),
                        ),
                      ),
                      const SizedBox(height: 7),
                      Row(
                        children: [
                          txt(
                            samples.isEmpty
                                ? '—'
                                : clockTime(
                                    samples.first['observed_at'] as String,
                                  ),
                            size: 9,
                            color: muted,
                          ),
                          const Spacer(),
                          txt(
                            'Actual committed samples · UTC',
                            size: 9,
                            color: muted,
                          ),
                          const Spacer(),
                          txt(
                            samples.isEmpty
                                ? '—'
                                : clockTime(
                                    samples.last['observed_at'] as String,
                                  ),
                            size: 9,
                            color: muted,
                          ),
                        ],
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    );
  }

  Widget footer(JsonMap? status, bool desktop) => Container(
    height: 30,
    padding: const EdgeInsets.symmetric(horizontal: 20),
    decoration: const BoxDecoration(
      color: Color(0xff0d1a24),
      border: Border(top: BorderSide(color: line)),
    ),
    child: Row(
      children: [
        const Icon(Icons.sensors, size: 11, color: muted),
        const SizedBox(width: 7),
        Expanded(
          child: txt(
            '${status?['frame_count'] ?? 0} committed frames',
            size: 7,
            color: muted,
          ),
        ),
        txt('T+ ${reading(seconds)} s', size: 7, color: muted),
        const Spacer(),
        txt(
          'Effective ${reading(status?['effective_speed'] as num?)}×  ·  1 Hz telemetry',
          size: 7,
          color: muted,
        ),
        if (desktop) ...[
          const Spacer(),
          txt(
            'Scene ${reading(globeDiagnostics()['fps'] as num?, 0)} FPS',
            size: 7,
            color: muted,
          ),
          const Spacer(),
          TextButton(
            onPressed: showInfo,
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              minimumSize: Size.zero,
            ),
            child: Row(
              children: [
                const Icon(Icons.info_outline, size: 10, color: muted),
                const SizedBox(width: 7),
                txt('Model & credits', size: 7, color: muted),
              ],
            ),
          ),
        ],
      ],
    ),
  );
}

const background = Color(0xff070d15),
    panel = Color(0xff0d151f),
    line = Color(0xff202a36),
    muted = Color(0xff718297),
    mint = Color(0xff95cfbc),
    gold = Color(0xffc7b985),
    textColor = Color(0xffd4dfe8);
Widget txt(
  String text, {
  double size = 12,
  Color color = textColor,
  FontWeight weight = FontWeight.w400,
  double spacing = 0,
  double? height,
}) => Text(
  text,
  style: TextStyle(
    fontSize: size,
    color: color,
    fontWeight: weight,
    letterSpacing: spacing,
    height: height,
  ),
);
Widget label(String text, {double size = 8, Color color = muted}) =>
    txt(text, size: size, color: color, spacing: 1.9);
Widget dot(Color color, double size) => Container(
  width: size,
  height: size,
  decoration: BoxDecoration(color: color, shape: BoxShape.circle),
);
Widget divider(double margin) => Padding(
  padding: EdgeInsets.symmetric(vertical: margin),
  child: const Divider(color: line, height: 1, thickness: 1),
);
BoxDecoration box({Color color = Colors.transparent, Color border = line}) =>
    BoxDecoration(
      color: color,
      border: Border.all(color: border),
      borderRadius: BorderRadius.circular(5),
    );
Widget badge(String text, Color color) => Container(
  padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
  decoration: BoxDecoration(
    color: color.withValues(alpha: .06),
    border: Border.all(color: color.withValues(alpha: .3)),
    borderRadius: BorderRadius.circular(3),
  ),
  child: txt(text, size: 7, color: color, spacing: 1.4),
);
Widget meter(double value, Color color, double height) => LayoutBuilder(
  builder: (context, constraints) => Stack(
    children: [
      Container(height: height, color: const Color(0xff263944)),
      Container(
        height: height,
        width: constraints.maxWidth * value.clamp(0, 1),
        color: color,
      ),
    ],
  ),
);
String clockTime(String? utc) => utc == null
    ? '—'
    : DateTime.parse(utc).toUtc().toIso8601String().substring(11, 19);

/// Plots only committed samples, with a quiet grid and no gap interpolation.
class HistoryPainter extends CustomPainter {
  HistoryPainter(this.values, this.soc);
  final List<double?> values;
  final bool soc;
  @override
  void paint(Canvas canvas, Size size) {
    final grid = Paint()
      ..color = line
      ..strokeWidth = .7;
    for (var row = 0; row < 4; row++) {
      for (var x = 0.0; x < size.width; x += 9) {
        canvas.drawLine(
          Offset(x, size.height * row / 3),
          Offset(math.min(x + 3, size.width), size.height * row / 3),
          grid,
        );
      }
    }
    if (values.length < 2) return;
    final maximum = soc
        ? 1.0
        : math.max(1.0, values.whereType<double>().fold(0.0, math.max));
    final color = soc ? mint : gold;
    final path = Path();
    var started = false;
    for (var i = 0; i < values.length; i++) {
      final value = values[i];
      if (value == null) {
        started = false;
        continue;
      }
      final x = i / (values.length - 1) * size.width,
          y = size.height * (1 - value / maximum);
      if (started) {
        path.lineTo(x, y);
      } else {
        path.moveTo(x, y);
        started = true;
      }
    }
    canvas.drawPath(
      path,
      Paint()
        ..color = color.withValues(alpha: .12)
        ..style = PaintingStyle.stroke
        ..strokeWidth = 8
        ..maskFilter = const MaskFilter.blur(BlurStyle.normal, 4),
    );
    canvas.drawPath(
      path,
      Paint()
        ..color = color
        ..style = PaintingStyle.stroke
        ..strokeWidth = 1.3,
    );
  }

  @override
  bool shouldRepaint(HistoryPainter oldDelegate) => true;
}
