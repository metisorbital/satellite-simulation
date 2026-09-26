import 'dart:math' as math;
import 'dart:convert';
import 'package:flutter/material.dart';
import 'package:pointer_interceptor/pointer_interceptor.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/scheduler.dart';
import 'api/mission.dart';
import 'auth/operator_gate.dart';
import 'scene/globe.dart';
import 'scene/playback.dart';

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
  double? seconds;
  @override
  void initState() {
    super.initState();
    mission = Mission(onSessionExpired: widget.onSessionExpired);
    mission.addListener(refresh);
    mission.connect(initial: widget.bootstrap);
    ticker = Ticker((_) => refresh())..start();
  }

  void refresh() {
    if (!mounted) return;
    setState(() {
      final satellites = mission.status?['satellites'] as List? ?? [];
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

  @override
  Widget build(BuildContext context) {
    final status = mission.status;
    final satellites = status?['satellites'] as List? ?? [];
    final frame = mission.playback.frameAt(selected, seconds);
    final descriptor =
        satellites.where((s) => s['satellite_id'] == selected).firstOrNull
            as JsonMap?;
    final utc = status == null || seconds == null
        ? null
        : DateTime.parse(status['epoch_utc'] as String)
              .add(Duration(milliseconds: (seconds! * 1000).round()))
              .toIso8601String();
    return Scaffold(
      body: LayoutBuilder(
        builder: (context, constraints) {
          final desktop = constraints.maxWidth >= 1050;
          final dashboard = Row(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              if (desktop) rail(),
              if (desktop) SizedBox(width: 238, child: sidebar(satellites)),
              Expanded(
                child: Column(
                  children: [
                    header(status, desktop),
                    operatorBar(),
                    toolbar(status, utc, desktop),
                    if (mission.error != null)
                      Container(
                        padding: const EdgeInsets.symmetric(
                          horizontal: 24,
                          vertical: 6,
                        ),
                        color: const Color(0xff2b211d),
                        child: Row(
                          children: [
                            const Icon(
                              Icons.info_outline,
                              size: 15,
                              color: gold,
                            ),
                            const SizedBox(width: 10),
                            Expanded(
                              child: txt(
                                mission.error!,
                                color: const Color(0xffe0b99d),
                                size: 11,
                              ),
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
                    if (!desktop)
                      Container(
                        height: 44,
                        padding: const EdgeInsets.symmetric(horizontal: 18),
                        decoration: const BoxDecoration(
                          border: Border(bottom: BorderSide(color: line)),
                        ),
                        child: DropdownButtonHideUnderline(
                          child: DropdownButton<String>(
                            isExpanded: true,
                            value: selected.isEmpty ? null : selected,
                            hint: txt('Connecting to mission…'),
                            dropdownColor: panel,
                            items: [
                              for (final s in satellites)
                                DropdownMenuItem(
                                  value: s['satellite_id'] as String,
                                  child: PointerInterceptor(
                                    child: SizedBox(
                                      height: 48,
                                      child: Align(
                                        alignment: Alignment.centerLeft,
                                        child: txt(
                                          '${s['satellite_id']} · ${s['name']}',
                                        ),
                                      ),
                                    ),
                                  ),
                                ),
                            ],
                            onChanged: (id) {
                              if (id != null) setState(() => selected = id);
                            },
                          ),
                        ),
                      ),
                    Expanded(
                      child: Row(
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
                                Focus(
                                  focusNode: historyFocus,
                                  child: historyPanel(),
                                ),
                              ],
                            ),
                          ),
                          if (desktop)
                            SizedBox(
                              width: 286,
                              child: telemetry(descriptor, frame),
                            ),
                        ],
                      ),
                    ),
                    if (!desktop)
                      SizedBox(
                        height: 720,
                        child: telemetry(descriptor, frame),
                      ),
                    footer(status, desktop),
                  ],
                ),
              ),
            ],
          );
          return desktop
              ? dashboard
              : SingleChildScrollView(
                  child: SizedBox(
                    height: math.max(constraints.maxHeight, 1540),
                    child: dashboard,
                  ),
                );
        },
      ),
    );
  }

  Widget rail() => Container(
    width: 66,
    decoration: const BoxDecoration(
      color: background,
      border: Border(right: BorderSide(color: line)),
    ),
    child: Column(
      children: [
        const SizedBox(height: 22),
        Container(
          width: 36,
          height: 36,
          decoration: BoxDecoration(
            color: const Color(0xff10202b),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Image.asset(
            'assets/images/metis-mark.png',
            width: 35,
            height: 35,
          ),
        ),
        const SizedBox(height: 40),
        railIcon(Icons.public, 'Orbital overview', active: true),
        const SizedBox(height: 16),
        railIcon(
          Icons.show_chart,
          'Measurement history',
          action: historyFocus.requestFocus,
        ),
        const SizedBox(height: 16),
        railIcon(
          Icons.layers_outlined,
          'View simulation model information',
          action: showInfo,
        ),
        const Spacer(),
        railIcon(
          Icons.help_outline,
          'Help and model limitations',
          action: showInfo,
        ),
        const SizedBox(height: 20),
        Container(
          width: 31,
          height: 31,
          decoration: BoxDecoration(
            shape: BoxShape.circle,
            color: const Color(0xff15252b),
            border: Border.all(color: const Color(0xff2a4147)),
          ),
          alignment: Alignment.center,
          child: txt('M', size: 11, color: const Color(0xffb3ccce)),
        ),
        const SizedBox(height: 20),
      ],
    ),
  );
  Widget railIcon(
    IconData icon,
    String label, {
    bool active = false,
    VoidCallback? action,
  }) => Container(
    width: 42,
    height: 42,
    decoration: BoxDecoration(
      color: active ? const Color(0xff192b36) : Colors.transparent,
      borderRadius: BorderRadius.circular(9),
      border: Border.all(
        color: active ? const Color(0xff2c4555) : Colors.transparent,
      ),
    ),
    child: IconButton(
      tooltip: label,
      onPressed: action ?? () {},
      icon: Icon(
        icon,
        size: 21,
        color: active ? const Color(0xffa7cbd9) : muted,
      ),
    ),
  );

  Widget sidebar(List<dynamic> satellites) => Container(
    decoration: const BoxDecoration(
      color: panel,
      border: Border(right: BorderSide(color: line)),
    ),
    padding: const EdgeInsets.symmetric(horizontal: 18),
    child: Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const SizedBox(height: 28),
        Row(
          children: [
            txt('metis', size: 26, weight: FontWeight.w700),
            const SizedBox(width: 12),
            label('O R B I T A L', size: 8),
          ],
        ),
        const SizedBox(height: 30),
        Container(
          padding: const EdgeInsets.all(12),
          decoration: box(color: const Color(0xff101c28)),
          child: Row(
            children: [
              Container(
                width: 28,
                height: 30,
                decoration: box(
                  color: const Color(0xff1b2e39),
                  border: Colors.transparent,
                ),
                child: const Icon(
                  Icons.hub_outlined,
                  color: Color(0xff9fc4d2),
                  size: 18,
                ),
              ),
              const SizedBox(width: 10),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    txt('LEO power mission', size: 11),
                    const SizedBox(height: 3),
                    txt('Simulation workspace', color: muted, size: 9),
                  ],
                ),
              ),
              const Icon(Icons.expand_more, size: 14, color: muted),
            ],
          ),
        ),
        const SizedBox(height: 34),
        label('MISSION WORKSPACE'),
        const SizedBox(height: 16),
        Container(
          height: 39,
          padding: const EdgeInsets.symmetric(horizontal: 12),
          decoration: box(
            color: const Color(0xff1b2d37),
            border: Colors.transparent,
          ),
          child: Row(
            children: [
              const Icon(Icons.public, size: 16, color: Color(0xffa8cbd6)),
              const SizedBox(width: 10),
              Expanded(
                child: txt(
                  'Orbital overview',
                  size: 11,
                  color: const Color(0xffb9d2dc),
                ),
              ),
              txt('01', size: 8, color: muted),
            ],
          ),
        ),
        SizedBox(
          height: 42,
          child: Row(
            children: [
              const SizedBox(width: 12),
              const Icon(Icons.show_chart, size: 17, color: muted),
              const SizedBox(width: 10),
              txt('Measurement history', size: 11, color: muted),
            ],
          ),
        ),
        divider(22),
        Row(
          children: [
            Expanded(child: label('CONSTELLATION')),
            if (mission.canEdit)
              IconButton(
                tooltip: 'Edit constellation',
                onPressed: mission.busy ? null : showConstellationEditor,
                icon: const Icon(Icons.edit_outlined, size: 16),
              ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 4),
              decoration: box(
                color: const Color(0xff1a2732),
                border: Colors.transparent,
              ),
              child: txt('${satellites.length}', size: 8, color: muted),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Expanded(
          child: ListView(
            padding: EdgeInsets.zero,
            children: [
              for (final satellite in satellites)
                satelliteCard(satellite as JsonMap),
            ],
          ),
        ),
        Row(
          children: [
            dot(gold, 4),
            const SizedBox(width: 8),
            label('SYNTHETIC MISSION', color: gold, size: 8),
          ],
        ),
        const SizedBox(height: 14),
        txt(
          'Explore how orbit and sunlight\nshape spacecraft power.',
          size: 10,
          color: muted,
          height: 1.9,
        ),
        Align(
          alignment: Alignment.centerLeft,
          child: TextButton(
            onPressed: showInfo,
            style: TextButton.styleFrom(
              padding: EdgeInsets.zero,
              foregroundColor: const Color(0xffa6c3d0),
            ),
            child: const Text(
              'About this simulation',
              style: TextStyle(fontSize: 10),
            ),
          ),
        ),
        divider(10),
        Row(
          children: [
            Icon(
              mission.playback.connected ? Icons.wifi : Icons.wifi_off,
              size: 12,
              color: mint,
            ),
            const SizedBox(width: 8),
            txt(
              mission.playback.connected
                  ? 'Local stream connected'
                  : 'Stream disconnected',
              size: 9,
              color: muted,
            ),
          ],
        ),
        const SizedBox(height: 20),
      ],
    ),
  );
  Widget satelliteCard(JsonMap satellite) {
    final id = satellite['satellite_id'] as String;
    final frame = mission.playback.frameAt(id, seconds);
    final soc = scalar(frame, 'eps.battery_soc');
    final color = Color(
      int.parse('ff${(satellite['color'] as String).substring(1)}', radix: 16),
    );
    return Container(
      margin: const EdgeInsets.only(bottom: 9),
      decoration: box(
        color: selected == id
            ? const Color(0xff172a34)
            : const Color(0xff101d27),
        border: selected == id ? const Color(0xff375364) : Colors.transparent,
      ),
      child: ListTile(
        selected: selected == id,
        dense: true,
        minVerticalPadding: 12,
        contentPadding: const EdgeInsets.symmetric(horizontal: 12),
        title: Row(
          children: [
            Icon(Icons.satellite_alt, size: 15, color: color),
            const SizedBox(width: 10),
            Expanded(child: txt(id, size: 11, spacing: .8)),
            dot(color, 4),
          ],
        ),
        subtitle: Padding(
          padding: const EdgeInsets.only(top: 10),
          child: Column(
            children: [
              Row(
                children: [
                  Expanded(
                    child: txt(environment(frame), size: 9, color: muted),
                  ),
                  txt(
                    '${reading(soc == null ? null : soc * 100, 0)}% SOC',
                    size: 9,
                    color: muted,
                  ),
                ],
              ),
              const SizedBox(height: 9),
              meter(soc ?? 0, color, 2),
            ],
          ),
        ),
        onTap: () => setState(() => selected = id),
      ),
    );
  }

  Widget operatorBar() {
    final operator = widget.bootstrap['operator'] as Map;
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 3),
      decoration: const BoxDecoration(
        color: panel,
        border: Border(bottom: BorderSide(color: line)),
      ),
      child: Row(
        children: [
          const Icon(Icons.person_outline, size: 16, color: mint),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              '${operator['display_name']} · ${operator['login']}',
              overflow: TextOverflow.ellipsis,
              style: const TextStyle(color: textColor, fontSize: 11),
            ),
          ),
          Tooltip(
            message: mission.busy
                ? 'Wait for the current mission request to finish'
                : 'Log out and end this demo run',
            child: TextButton.icon(
              onPressed: mission.busy
                  ? null
                  : () {
                      final token = mission.csrfToken.isNotEmpty
                          ? mission.csrfToken
                          : widget.bootstrap['csrf_token'] as String;
                      mission.suspend();
                      widget.onLogout(token);
                    },
              icon: const Icon(Icons.logout, size: 15),
              label: const Text('Log out'),
            ),
          ),
        ],
      ),
    );
  }

  Widget header(JsonMap? status, bool desktop) => Container(
    height: 65,
    padding: EdgeInsets.symmetric(horizontal: desktop ? 28 : 18),
    decoration: const BoxDecoration(
      color: Color(0xff0b141e),
      border: Border(bottom: BorderSide(color: line)),
    ),
    child: Row(
      children: [
        txt(
          desktop ? 'Mission control' : 'metis',
          size: desktop ? 10 : 18,
          color: desktop ? muted : textColor,
          weight: desktop ? FontWeight.w400 : FontWeight.w700,
        ),
        if (desktop) ...[
          SizedBox(width: desktop ? 18 : 9),
          txt('/', color: line),
          SizedBox(width: desktop ? 18 : 9),
          txt('Orbital overview', size: 10),
        ],
        const Spacer(),
        badge('SYNTHETIC', gold),
        SizedBox(width: desktop ? 18 : 9),
        Container(width: 1, height: 18, color: line),
        SizedBox(width: desktop ? 18 : 9),
        dot(status?['status'] == 'running' ? mint : muted, 4),
        const SizedBox(width: 7),
        txt(
          status?['status'] as String? ?? 'Connecting',
          size: 10,
          color: const Color(0xffaab8c7),
        ),
        if (desktop) ...[
          SizedBox(width: desktop ? 18 : 9),
          badge(
            status == null
                ? 'CONNECTING'
                : mission.canControl
                ? 'CONTROL'
                : 'PUBLIC DEMO',
            muted,
          ),
        ] else
          IconButton(
            tooltip: 'Model & credits',
            onPressed: showInfo,
            icon: const Icon(Icons.info_outline, size: 16, color: muted),
          ),
      ],
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
              if (!desktop && mission.canEdit)
                IconButton(
                  tooltip: 'Edit constellation',
                  onPressed: mission.busy ? null : showConstellationEditor,
                  icon: const Icon(Icons.edit_outlined, size: 18),
                ),
            ],
          )
        : status == null
        ? const SizedBox.shrink()
        : badge('VIEW ONLY', muted);
    final title = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        label('METIS / EARTH ORBIT', size: 8),
        const SizedBox(height: 10),
        Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            Semantics(
              header: true,
              child: txt(
                'Orbital overview',
                size: 23,
                weight: FontWeight.w500,
                spacing: -.7,
              ),
            ),
            const SizedBox(width: 10),
            dot(const Color(0xff4e7183), 4),
          ],
        ),
      ],
    );
    final clock = Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      mainAxisSize: MainAxisSize.min,
      children: [
        label('SIMULATION UTC', size: 8),
        const SizedBox(height: 8),
        txt(clockTime(utc), size: 17, spacing: 3),
        const SizedBox(height: 3),
        txt(utc?.substring(0, 10) ?? '—', size: 8, color: muted, spacing: 1.5),
      ],
    );
    return Container(
      padding: EdgeInsets.symmetric(
        horizontal: desktop ? 28 : 18,
        vertical: desktop ? 24 : 15,
      ),
      decoration: const BoxDecoration(
        color: Color(0xff0c151f),
        border: Border(bottom: BorderSide(color: line)),
      ),
      child: desktop
          ? Row(
              children: [
                Expanded(child: title),
                clock,
                const SizedBox(width: 30),
                controls,
              ],
            )
          : Column(
              children: [
                Row(
                  children: [
                    Expanded(child: title),
                    clock,
                  ],
                ),
                const SizedBox(height: 15),
                Align(
                  alignment: Alignment.centerLeft,
                  child: SingleChildScrollView(
                    scrollDirection: Axis.horizontal,
                    child: controls,
                  ),
                ),
              ],
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
                      const SizedBox(width: 30),
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
              bottom: desktop ? 99 : 63,
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
              bottom: desktop ? (roomy ? 37 : 74) : 10,
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
                      const SizedBox(width: 10),
                      txt('|', size: 8, color: muted),
                      const SizedBox(width: 8),
                      txt('${reading(lag)} s behind', size: 7, color: muted),
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

  Widget telemetry(JsonMap? descriptor, JsonMap? frame) {
    final soc = scalar(frame, 'eps.battery_soc'),
        battery = scalar(frame, 'eps.battery_power_w'),
        solar = scalar(frame, 'eps.solar_power_w'),
        load = scalar(frame, 'eps.load_requested_w'),
        light = scalar(frame, 'environment.illumination_fraction');
    final maxPower = math.max(
      1.0,
      math.max(solar ?? 0, math.max(load ?? 0, (battery ?? 0).abs())),
    );
    final color = descriptor == null
        ? mint
        : Color(
            int.parse(
              'ff${(descriptor['color'] as String).substring(1)}',
              radix: 16,
            ),
          );
    Widget row(String title, String value, {Color valueColor = textColor}) =>
        Padding(
          padding: const EdgeInsets.symmetric(vertical: 6),
          child: Row(
            children: [
              Expanded(child: txt(title, size: 9, color: muted)),
              txt(value, size: 9, color: valueColor, spacing: .4),
            ],
          ),
        );
    return Container(
      decoration: const BoxDecoration(
        color: Color(0xff0e1a24),
        border: Border(left: BorderSide(color: line)),
      ),
      child: ListView(
        padding: const EdgeInsets.all(20),
        children: [
          Row(
            children: [
              Expanded(child: label('SPACECRAFT DETAIL', size: 7)),
              const Icon(Icons.sensors, size: 14, color: muted),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            children: [
              Icon(Icons.satellite_alt_outlined, size: 31, color: color),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    txt(
                      descriptor?['satellite_id'] as String? ??
                          'Select a satellite',
                      size: 15,
                      spacing: .5,
                    ),
                    const SizedBox(height: 5),
                    txt(
                      descriptor?['name'] as String? ?? 'Mission telemetry',
                      size: 10,
                      color: muted,
                    ),
                  ],
                ),
              ),
              const Icon(Icons.expand_more, size: 14, color: muted),
            ],
          ),
          const SizedBox(height: 15),
          Row(
            children: [
              dot(mint, 4),
              const SizedBox(width: 7),
              txt(
                (frame?['mode'] as String? ?? 'Awaiting measurements')
                    .replaceAll('_', ' '),
                size: 9,
                color: const Color(0xffa5bdb7),
              ),
              const SizedBox(width: 12),
              badge('LEO', muted),
            ],
          ),
          divider(13),
          Row(
            children: [
              const Icon(Icons.battery_4_bar_outlined, size: 13, color: muted),
              const SizedBox(width: 7),
              Expanded(child: txt('Battery state', size: 10, color: muted)),
              txt(
                battery == null
                    ? '—'
                    : battery < -.01
                    ? 'Charging'
                    : battery > .01
                    ? 'Discharging'
                    : 'Balanced',
                size: 9,
                color: battery != null && battery < 0 ? mint : muted,
              ),
            ],
          ),
          const SizedBox(height: 14),
          Row(
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              txt(
                reading(soc == null ? null : soc * 100),
                size: 31,
                spacing: 2,
              ),
              Padding(
                padding: const EdgeInsets.only(bottom: 4),
                child: txt('%', size: 14, color: muted),
              ),
            ],
          ),
          const SizedBox(height: 15),
          Semantics(
            label: 'Battery state of charge',
            value: '${reading(soc == null ? null : soc * 100)}%',
            child: Row(
              children: [
                for (var i = 0; i < 12; i++)
                  Expanded(
                    child: Container(
                      height: 6,
                      margin: EdgeInsets.only(right: i == 11 ? 0 : 3),
                      color: (soc ?? 0) * 12 > i
                          ? mint
                          : const Color(0xff253a45),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 9),
          Row(
            children: [
              Expanded(
                child: txt(
                  '${reading(scalar(frame, 'eps.battery_energy_wh'))} Wh stored',
                  size: 7,
                  color: muted,
                ),
              ),
              txt(
                '${reading(descriptor?['capacity_wh'] as num?, 0)} Wh capacity',
                size: 7,
                color: muted,
              ),
            ],
          ),
          divider(13),
          Row(
            children: [
              const Icon(Icons.bolt_outlined, size: 15, color: muted),
              const SizedBox(width: 7),
              Expanded(child: txt('Power balance', size: 10, color: muted)),
              label('WATTS', size: 6),
            ],
          ),
          const SizedBox(height: 15),
          txt('Solar generation', size: 8, color: muted),
          const SizedBox(height: 7),
          Row(
            children: [
              Expanded(
                child: txt(
                  '${reading(solar)} W',
                  size: 24,
                  color: const Color(0xffdfcda2),
                  spacing: 2,
                ),
              ),
              const Icon(Icons.wb_sunny_outlined, size: 22, color: gold),
            ],
          ),
          const SizedBox(height: 14),
          for (final item in [
            ('Solar', solar, gold),
            ('Requested load', load, const Color(0xff899daf)),
            (
              battery != null && battery < 0 ? 'To battery' : 'From battery',
              battery?.abs(),
              mint,
            ),
          ])
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6),
              child: Row(
                children: [
                  SizedBox(
                    width: 87,
                    child: txt(item.$1, size: 8, color: muted),
                  ),
                  Expanded(child: meter((item.$2 ?? 0) / maxPower, item.$3, 3)),
                  SizedBox(
                    width: 40,
                    child: Align(
                      alignment: Alignment.centerRight,
                      child: txt(
                        reading(item.$2, 0),
                        size: 8,
                        color: const Color(0xffb4c3ce),
                      ),
                    ),
                  ),
                ],
              ),
            ),
          const SizedBox(height: 9),
          row(
            'Load served',
            '${reading(scalar(frame, 'eps.load_served_w'))} W',
          ),
          row(
            'Curtailed / unmet',
            '${reading(scalar(frame, 'eps.curtailed_power_w'))} / ${reading(scalar(frame, 'eps.unserved_power_w'))} W',
          ),
          const SizedBox(height: 5),
          txt(
            frame?['sample_window_s'] == 0
                ? 'Initial instantaneous allocation'
                : '${frame?['sample_window_s'] ?? 1} s mean · ${frame?['interval_mode'] ?? 'unknown'}',
            size: 7,
            color: muted,
          ),
          divider(13),
          Row(
            children: [
              const Icon(Icons.wb_sunny_outlined, size: 14, color: muted),
              const SizedBox(width: 7),
              Expanded(child: txt('Illumination', size: 10, color: muted)),
              txt(environment(frame), size: 9, color: gold),
            ],
          ),
          const SizedBox(height: 12),
          meter(light ?? 0, gold, 3),
          const SizedBox(height: 9),
          Row(
            children: [
              Expanded(child: txt('Visible solar disk', size: 7, color: muted)),
              txt(
                '${reading(light == null ? null : light * 100)}%',
                size: 7,
                color: muted,
              ),
            ],
          ),
          divider(13),
          Row(
            children: [
              Expanded(child: txt('Position', size: 9, color: muted)),
              label('EARTH FIXED', size: 6),
            ],
          ),
          const SizedBox(height: 12),
          Row(
            children: [
              for (final item in [
                (
                  'Altitude',
                  '${reading(scalar(frame, 'orbit.altitude_m') == null ? null : scalar(frame, 'orbit.altitude_m')! / 1000)} km',
                ),
                (
                  'Latitude',
                  '${reading(scalar(frame, 'orbit.latitude_deg'), 2)}°',
                ),
                (
                  'Longitude',
                  '${reading(scalar(frame, 'orbit.longitude_deg'), 2)}°',
                ),
              ])
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      txt(item.$1, size: 7, color: muted),
                      const SizedBox(height: 8),
                      txt(item.$2, size: 9, spacing: .4),
                    ],
                  ),
                ),
            ],
          ),
          divider(18),
          txt(
            'Sample ${frame?['observed_at'] ?? '—'}\n#${frame?['sequence'] ?? '—'}',
            size: 7,
            color: muted,
            height: 1.8,
          ),
        ],
      ),
    );
  }

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
              Expanded(child: txt(selected, size: 8, color: muted)),
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
                  width: 126,
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
                        size: 7,
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
                            size: 6,
                            color: muted,
                          ),
                          const Spacer(),
                          txt(
                            'Actual committed samples · UTC',
                            size: 6,
                            color: muted,
                          ),
                          const Spacer(),
                          txt(
                            samples.isEmpty
                                ? '—'
                                : clockTime(
                                    samples.last['observed_at'] as String,
                                  ),
                            size: 6,
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
