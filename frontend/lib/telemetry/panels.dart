import 'package:flutter/material.dart';
import '../scene/playback.dart';

const telemetrySurface = Color(0xff101923);
const telemetryBorder = Color(0xff25313e);
const telemetryMuted = Color(0xff96a7b8);
const telemetryAccent = Color(0xff89d5c1);
const telemetryColors = <Color>[
  Color(0xff81c9a4),
  Color(0xffffc568),
  Color(0xff72aff7),
  Color(0xffdc94dd),
  Color(0xfff58c82),
  Color(0xff70d8df),
];

/// Presentation grouping only; units and measurement semantics come from catalog.
class TelemetryPanel {
  const TelemetryPanel(this.title, this.channels, {this.note});
  final String title;
  final List<String> channels;
  final String? note;
}

const telemetryTabs = <String>[
  'Overview',
  'EPS',
  'Flight computer',
  'Payload',
  'ADCS',
  'Space weather',
];

const powerPanel = TelemetryPanel('Power balance', [
  'eps.solar_power_w',
  'eps.load_requested_w',
  'eps.load_served_w',
  'eps.battery_power_w',
], note: 'Battery power: positive discharge, negative charge.');
const temperaturePanel = TelemetryPanel(
  'Thermal nodes',
  [
    'eps.battery_temperature_c',
    'fc.mcu_temperature_c',
    'payload.electronics_temperature_c',
  ],
  note:
      'Three modeled isothermal nodes; individual component hot spots are not resolved.',
);
const currentPanel = TelemetryPanel(
  'Battery current flow',
  ['eps.battery_current_in_a', 'eps.battery_current_out_a'],
  note:
      'IN and OUT are separate nonnegative currents at the ideal energy-store terminal.',
);
const voltagePanel = TelemetryPanel(
  'Regulated rail voltages',
  ['eps.battery_voltage_v', 'eps.solar_voltage_v', 'eps.bus_voltage_v'],
  note:
      'Equivalent branches; no voltage sag, switching, or per-converter model.',
);
const attitudePanel = TelemetryPanel(
  'Knowledge quaternion',
  ['adcs.attitude_quaternion'],
  note:
      'Hamilton [w,x,y,z], active body-to-GCRS rotation. Components are not an attitude average.',
);

const telemetryPanels = <String, List<TelemetryPanel>>{
  'Overview': [
    powerPanel,
    TelemetryPanel('Battery state of charge', ['eps.battery_soc']),
    temperaturePanel,
    currentPanel,
    voltagePanel,
    attitudePanel,
  ],
  'EPS': [
    powerPanel,
    currentPanel,
    voltagePanel,
    TelemetryPanel('Solar & load bus currents', [
      'eps.solar_current_a',
      'eps.bus_current_a',
    ]),
    TelemetryPanel('Battery state of charge', ['eps.battery_soc']),
    TelemetryPanel('Stored battery energy', ['eps.battery_energy_wh']),
    TelemetryPanel('Power allocation limits', [
      'eps.curtailed_power_w',
      'eps.unserved_power_w',
    ]),
    TelemetryPanel('Battery temperature', ['eps.battery_temperature_c']),
    TelemetryPanel('Illumination & panel incidence', [
      'environment.illumination_fraction',
      'environment.panel_incidence_cosine',
    ]),
    TelemetryPanel('Ground-station watchdog', ['eps.watchdog_remaining_s']),
  ],
  'Flight computer': [
    TelemetryPanel('Avionics uptime', ['fc.uptime_s']),
    TelemetryPanel('MCU temperature', ['fc.mcu_temperature_c']),
    TelemetryPanel('Geodetic altitude', ['orbit.altitude_m']),
    TelemetryPanel('Latitude & longitude', [
      'orbit.latitude_deg',
      'orbit.longitude_deg',
    ]),
    TelemetryPanel('Earth-fixed position', ['orbit.position_itrf_m']),
    TelemetryPanel('Earth-fixed velocity', ['orbit.velocity_itrf_m_s']),
    TelemetryPanel('Inertial position', ['orbit.position_gcrs_m']),
    TelemetryPanel('Inertial velocity', ['orbit.velocity_gcrs_m_s']),
    TelemetryPanel('GNSS receiver', [
      'fc.gnss_satellites_in_view',
      'fc.gnss_satellites_tracked',
      'fc.gnss_fix_quality',
    ]),
  ],
  'Payload': [
    TelemetryPanel('Payload power', ['payload.power_w']),
    TelemetryPanel('Electronics temperature', [
      'payload.electronics_temperature_c',
    ]),
    TelemetryPanel('Payload uptime', ['payload.uptime_s']),
    TelemetryPanel('Acquisition gate', [
      'payload.acquisition_active',
    ], note: 'Modeled 0/1 acquisition gate; not a mission camera-status code.'),
    TelemetryPanel('Completed images', ['payload.image_count']),
    TelemetryPanel('Storage occupancy', ['payload.storage_fraction']),
    TelemetryPanel('Stored acquisition bytes', [
      'payload.storage_used_bytes',
    ], note: 'No downlink, compression, file deletion, or dual-camera model.'),
  ],
  'ADCS': [
    attitudePanel,
    TelemetryPanel(
      'Target quaternion',
      ['adcs.target_quaternion'],
      note:
          'Hamilton [w,x,y,z], active body-to-GCRS rotation; ideal prescribed LVLH target.',
    ),
    TelemetryPanel('Body angular velocity', ['adcs.angular_velocity_rad_s']),
    TelemetryPanel(
      'Sun direction in body axes',
      ['adcs.sun_vector_body'],
      note:
          'Geometric unit direction, including eclipse; not an optical detection.',
    ),
    TelemetryPanel(
      'Magnetic field in body axes',
      ['adcs.magnetic_field_body_t'],
      note:
          'Centered aligned dipole; no tilt, multipoles, or space-weather contribution.',
    ),
    TelemetryPanel(
      'Prescribed pointing error',
      ['adcs.off_nadir_angle_deg', 'adcs.control_error_deg'],
      note:
          'Zero by ideal nadir-pointing assumption, not demonstrated controller performance.',
    ),
    TelemetryPanel('Reaction-wheel speed', ['adcs.reaction_wheel_speed_rpm']),
    TelemetryPanel('Reaction-wheel pressure', [
      'adcs.reaction_wheel_pressure_pa',
    ]),
    TelemetryPanel('Demanded actuator torque', ['adcs.demanded_torque_nm']),
    TelemetryPanel('Controller & star tracker', [
      'adcs.controller_mode',
      'adcs.star_tracker_quality',
    ]),
  ],
  'Space weather': [
    TelemetryPanel('Geomagnetic activity', ['space_weather.kp_index']),
    TelemetryPanel('Integral solar proton flux', ['space_weather.proton_flux']),
    TelemetryPanel('Solar X-ray flux', ['space_weather.x_ray_flux']),
  ],
};

const channelLabels = <String, String>{
  'eps.solar_power_w': 'Solar generation',
  'eps.load_requested_w': 'Requested load',
  'eps.load_served_w': 'Served load',
  'eps.battery_power_w': 'Battery power',
  'eps.battery_soc': 'State of charge',
  'eps.battery_energy_wh': 'Battery energy',
  'eps.curtailed_power_w': 'Curtailed power',
  'eps.unserved_power_w': 'Unserved power',
  'eps.battery_current_in_a': 'IN · charging',
  'eps.battery_current_out_a': 'OUT · discharging',
  'eps.battery_voltage_v': 'Battery terminal',
  'eps.solar_voltage_v': 'Solar branch',
  'eps.bus_voltage_v': 'Load bus',
  'eps.solar_current_a': 'Solar current',
  'eps.bus_current_a': 'Bus current',
  'eps.battery_temperature_c': 'Battery',
  'fc.mcu_temperature_c': 'Avionics',
  'payload.electronics_temperature_c': 'Payload',
  'environment.illumination_fraction': 'Illumination',
  'environment.panel_incidence_cosine': 'Panel incidence cosine',
  'orbit.latitude_deg': 'Latitude',
  'orbit.longitude_deg': 'Longitude',
  'adcs.off_nadir_angle_deg': 'Off-nadir angle',
  'adcs.control_error_deg': 'Control error',
};

String channelLabel(String id) =>
    channelLabels[id] ?? id.split('.').last.replaceAll('_', ' ');

String formatTelemetry(num? value) {
  if (value == null || !value.isFinite) return '—';
  if (value == 0) return '0';
  final absolute = value.abs();
  if (absolute >= 1e6 || absolute < .001) return value.toStringAsExponential(2);
  if (absolute >= 1000) return value.toStringAsFixed(0);
  if (absolute >= 100) return value.toStringAsFixed(1);
  if (absolute >= 1) return value.toStringAsFixed(2);
  return value.toStringAsFixed(3);
}

String utcTime(DateTime instant, {bool date = false}) {
  final iso = instant.toUtc().toIso8601String();
  return date
      ? '${iso.substring(0, 10)} ${iso.substring(11, 19)} UTC'
      : iso.substring(11, 19);
}

DateTime sampleTime(JsonMap frame) =>
    DateTime.parse(frame['observed_at'] as String).toUtc();

/// A catalog-backed scalar or vector component, with explicit sample quality.
class TelemetrySeries {
  const TelemetrySeries(
    this.channel,
    this.definition,
    this.color, {
    this.component,
  });
  final String channel;
  final JsonMap definition;
  final Color color;
  final int? component;

  String get unit => definition['unit'] as String;
  String get name {
    if (component == null) return channelLabel(channel);
    final labels = definition['coordinate_frame'] == 'body_to_GCRS_wxyz'
        ? const ['w', 'x', 'y', 'z']
        : definition['value_type'] == 'vector[3]'
        ? const ['x', 'y', 'z']
        : const ['1', '2', '3', '4'];
    return labels[component!];
  }

  String quality(JsonMap? frame) {
    if (definition['availability'] == 'unavailable') return 'unavailable';
    if (frame == null) return 'waiting';
    final reading = (frame['channels'] as Map?)?[channel];
    return reading is Map
        ? reading['quality'] as String? ?? 'missing'
        : 'unsupported';
  }

  double? value(JsonMap? frame) {
    if (!const ['valid', 'saturated'].contains(quality(frame))) return null;
    final reading = (frame!['channels'] as Map)[channel] as Map;
    final raw = reading['value'];
    final number = component == null
        ? raw
        : raw is List && component! < raw.length
        ? raw[component!]
        : null;
    return number is num && number.isFinite ? number.toDouble() : null;
  }

  String display(JsonMap? frame) {
    final state = quality(frame);
    final number = value(frame);
    if (number == null) return state == 'valid' ? 'Invalid value' : state;
    return '${formatTelemetry(number)}${state == 'saturated' ? ' · saturated' : ''}';
  }
}

List<TelemetrySeries> panelSeries(
  TelemetryPanel panel,
  Map<String, JsonMap> definitions,
) {
  final result = <TelemetrySeries>[];
  for (final id in panel.channels) {
    final definition = definitions[id];
    if (definition == null || definition['availability'] == 'unavailable') {
      continue;
    }
    final shape = definition['value_type'];
    if (shape == 'string') continue;
    final count = shape == 'vector[4]'
        ? 4
        : shape == 'vector[3]'
        ? 3
        : 1;
    for (var index = 0; index < count; index++) {
      result.add(
        TelemetrySeries(
          id,
          definition,
          telemetryColors[result.length % telemetryColors.length],
          component: count == 1 ? null : index,
        ),
      );
    }
  }
  return result;
}
