import 'package:flutter/material.dart';

import 'scene/playback.dart';

const _surface = Color(0xff081426);
const _border = Color(0xff1a315e);
const _muted = Color(0xff8da4d8);
const _mint = Color(0xff5d84ff);

/// A concise summary of committed spacecraft measurements beside the Earth.
class OverviewInspector extends StatelessWidget {
  const OverviewInspector({
    super.key,
    required this.descriptor,
    required this.frame,
    required this.onTelemetry,
    this.observed = false,
  });

  final JsonMap? descriptor;
  final JsonMap? frame;
  final VoidCallback onTelemetry;
  final bool observed;

  String _value(String channel, String unit, {double scale = 1}) {
    final value = scalar(frame, channel);
    return value == null
        ? 'Unavailable'
        : '${(value * scale).toStringAsFixed(1)} $unit';
  }

  Widget _measurement(String label, String value) => Padding(
    padding: const EdgeInsets.symmetric(vertical: 14),
    child: Row(
      children: [
        Expanded(
          child: Text(
            label,
            style: const TextStyle(color: _muted, fontSize: 12),
          ),
        ),
        const SizedBox(width: 10),
        Text(value, style: const TextStyle(fontSize: 13)),
      ],
    ),
  );

  @override
  Widget build(BuildContext context) {
    final soc = scalar(frame, 'eps.battery_soc');
    final busVoltage = scalar(frame, 'eps.bus_voltage_v');
    final battery = scalar(frame, 'eps.battery_power_w');
    final light = scalar(frame, 'environment.illumination_fraction');
    final illumination = light == null
        ? observed
              ? 'Unavailable'
              : 'Awaiting sample'
        : light <= .001
        ? 'In eclipse'
        : light >= .999
        ? 'Sunlit'
        : 'Penumbra';
    return Container(
      decoration: const BoxDecoration(
        color: _surface,
        border: Border(left: BorderSide(color: _border)),
      ),
      child: ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            'SELECTED SPACECRAFT',
            style: TextStyle(color: _muted, fontSize: 9, letterSpacing: 1.5),
          ),
          const SizedBox(height: 19),
          Text(
            descriptor?['satellite_id'] as String? ?? 'Awaiting spacecraft',
            style: const TextStyle(fontSize: 22),
          ),
          const SizedBox(height: 6),
          Text(
            descriptor?['name'] as String? ?? 'Mission telemetry',
            style: const TextStyle(fontSize: 12, color: _muted),
          ),
          const SizedBox(height: 20),
          Row(
            children: [
              const Icon(Icons.satellite_alt_outlined, size: 16, color: _mint),
              const SizedBox(width: 9),
              Expanded(
                child: Text(
                  (frame?['mode'] as String? ??
                          (observed
                              ? 'Operating mode unavailable'
                              : 'Awaiting measurements'))
                      .replaceAll('_', ' '),
                  style: const TextStyle(color: _mint, fontSize: 12),
                ),
              ),
            ],
          ),
          const Divider(height: 43, color: _border),
          Text(
            observed ? 'Spacecraft bus voltage' : 'Battery state of charge',
            style: const TextStyle(color: _muted, fontSize: 12),
          ),
          const SizedBox(height: 16),
          Text(
            observed
                ? busVoltage == null
                      ? '—'
                      : '${busVoltage.toStringAsFixed(2)} V'
                : soc == null
                ? '—'
                : '${(soc * 100).toStringAsFixed(1)}%',
            style: const TextStyle(fontSize: 36, color: _mint),
          ),
          const SizedBox(height: 15),
          if (!observed && soc != null)
            LinearProgressIndicator(
              value: soc.clamp(0, 1),
              minHeight: 4,
              backgroundColor: _border,
              color: _mint,
            ),
          const SizedBox(height: 12),
          Text(
            observed
                ? 'Recorded source measurement'
                : battery == null
                ? 'No valid power measurement'
                : battery < -.01
                ? 'Charging'
                : battery > .01
                ? 'Discharging'
                : 'Balanced',
            style: const TextStyle(color: _muted, fontSize: 11),
          ),
          const SizedBox(height: 22),
          _measurement('Solar generation', _value('eps.solar_power_w', 'W')),
          if (observed)
            _measurement('Bus current', _value('eps.bus_current_a', 'A'))
          else
            _measurement('Requested load', _value('eps.load_requested_w', 'W')),
          _measurement('Supplied load', _value('eps.load_served_w', 'W')),
          if (observed) ...[
            _measurement(
              'Battery 1 voltage',
              _value('eps.battery_1_voltage_v', 'V'),
            ),
            _measurement(
              'Battery 2 voltage',
              _value('eps.battery_2_voltage_v', 'V'),
            ),
            _measurement('Battery state of charge', 'Unavailable'),
          ] else
            _measurement('Battery power', _value('eps.battery_power_w', 'W')),
          const Divider(height: 28, color: _border),
          _measurement('Illumination', illumination),
          _measurement(
            'Altitude',
            _value('orbit.altitude_m', 'km', scale: .001),
          ),
          const SizedBox(height: 20),
          OutlinedButton.icon(
            onPressed: onTelemetry,
            icon: const Icon(Icons.open_in_full, size: 15),
            label: const Text('Open telemetry', style: TextStyle(fontSize: 12)),
          ),
          const SizedBox(height: 23),
          Text(
            frame == null
                ? 'Waiting for a committed sample.'
                : 'Sample UTC\n${frame!['observed_at']}\nSequence ${frame!['sequence']}',
            style: const TextStyle(color: _muted, fontSize: 10, height: 1.7),
          ),
        ],
      ),
    );
  }
}
