import 'package:flutter/material.dart';

import 'api/mission.dart';
import 'scene/playback.dart';

const _surface = Color(0xff101923);
const _border = Color(0xff26323f);
const _muted = Color(0xff94a4b7);
const _mint = Color(0xff95cfbc);

/// Reviews configured operation windows without predicting spacecraft resources.
class MissionPlanningPage extends StatelessWidget {
  const MissionPlanningPage({
    super.key,
    required this.mission,
    required this.onEdit,
    required this.onOverview,
  });

  final Mission mission;
  final VoidCallback onEdit;
  final VoidCallback onOverview;

  @override
  Widget build(BuildContext context) {
    final status = mission.status;
    final satellites = mission.editableSatellites;
    final windows =
        <({JsonMap satellite, JsonMap operation})>[
          if (!mission.isObserved)
            for (final satellite in satellites ?? <JsonMap>[])
              for (final operation in satellite['operations'] as List? ?? [])
                (
                  satellite: satellite,
                  operation: Map<String, dynamic>.from(operation as Map),
                ),
        ]..sort(
          (a, b) => (a.operation['start_s'] as num).compareTo(
            b.operation['start_s'] as num,
          ),
        );
    return LayoutBuilder(
      builder: (context, constraints) {
        final wide = constraints.maxWidth >= 950;
        return ListView(
          padding: EdgeInsets.all(constraints.maxWidth < 550 ? 20 : 32),
          children: [
            Wrap(
              alignment: WrapAlignment.spaceBetween,
              crossAxisAlignment: WrapCrossAlignment.center,
              spacing: 20,
              runSpacing: 16,
              children: [
                const Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'PLAN / REVIEW',
                      style: TextStyle(
                        color: _muted,
                        fontSize: 10,
                        letterSpacing: 1.6,
                      ),
                    ),
                    SizedBox(height: 10),
                    Text(
                      'Mission planning',
                      style: TextStyle(
                        fontSize: 28,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    SizedBox(height: 10),
                    Text(
                      'Review spacecraft operations and their configured windows.',
                      style: TextStyle(color: _muted, fontSize: 13),
                    ),
                  ],
                ),
                if (!mission.isObserved)
                  FilledButton.tonalIcon(
                    onPressed: mission.canEdit && !mission.busy ? onEdit : null,
                    icon: const Icon(Icons.edit_calendar_outlined, size: 18),
                    label: const Text('Configure operations'),
                  ),
              ],
            ),
            const SizedBox(height: 28),
            _card(
              Wrap(
                spacing: 36,
                runSpacing: 18,
                children: [
                  _fact(
                    'SOURCE',
                    mission.isObserved ? 'Observed replay' : 'Simulation',
                  ),
                  _fact('RUN STATE', '${status?['status'] ?? 'Connecting'}'),
                  _fact(
                    'CONFIGURED WINDOWS',
                    mission.isObserved ? 'Not provided' : '${windows.length}',
                  ),
                  _fact(
                    'MISSION TIME',
                    'T+ ${status?['committed_tick'] ?? 0} s',
                  ),
                ],
              ),
            ),
            const SizedBox(height: 24),
            if (mission.isObserved)
              _empty(
                Icons.satellite_alt_outlined,
                'No mission plan in this recording',
                'The recorded source provides measurements, not task intent or an operating schedule. Telemetry remains available for investigation.',
                onOverview,
                'Open replay overview',
              )
            else if (satellites == null)
              _empty(
                Icons.cloud_off_outlined,
                'Configuration is not available',
                'A connected operator session is required to read the configured operations.',
                mission.connecting ? null : () => mission.connect(),
                mission.connecting ? 'Connecting…' : 'Reconnect',
              )
            else ...[
              if (wide)
                Row(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Expanded(flex: 2, child: _windowList(windows, status)),
                    const SizedBox(width: 24),
                    Expanded(child: _context(satellites)),
                  ],
                )
              else ...[
                _windowList(windows, status),
                const SizedBox(height: 24),
                _context(satellites),
              ],
            ],
          ],
        );
      },
    );
  }

  Widget _windowList(
    List<({JsonMap satellite, JsonMap operation})> windows,
    JsonMap? status,
  ) {
    final tick = (status?['committed_tick'] as num? ?? 0).toDouble();
    final epoch = DateTime.tryParse(status?['epoch_utc'] as String? ?? '');
    return _card(
      Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          const Text(
            'Operation windows',
            style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          const Text(
            'Declared configuration · simulation seconds from the run epoch',
            style: TextStyle(color: _muted, fontSize: 12),
          ),
          const SizedBox(height: 22),
          if (windows.isEmpty)
            const Padding(
              padding: EdgeInsets.symmetric(vertical: 20),
              child: Text(
                'No scheduled windows. Each spacecraft stays in its configured initial mode.',
                style: TextStyle(color: _muted, height: 1.7),
              ),
            ),
          for (final window in windows) ...[
            _operation(window.satellite, window.operation, tick, epoch),
            if (window != windows.last)
              const Divider(height: 32, color: _border),
          ],
        ],
      ),
    );
  }

  Widget _operation(
    JsonMap satellite,
    JsonMap operation,
    double tick,
    DateTime? epoch,
  ) {
    final start = operation['start_s'] as int;
    final end = operation['end_s'] as int;
    final recurring = operation['repeat'] == 'orbit';
    final label = recurring
        ? 'Repeats every orbit'
        : tick < start
        ? 'Upcoming'
        : tick < end
        ? 'Active'
        : 'Elapsed';
    String utc(int second) => epoch == null
        ? 'UTC unavailable'
        : epoch
              .add(Duration(seconds: second))
              .toUtc()
              .toIso8601String()
              .replaceFirst('.000Z', 'Z');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Wrap(
          spacing: 12,
          runSpacing: 10,
          crossAxisAlignment: WrapCrossAlignment.center,
          children: [
            Text(
              satellite['satellite_id'] as String,
              style: const TextStyle(
                color: _mint,
                fontSize: 12,
                fontWeight: FontWeight.w600,
              ),
            ),
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
              decoration: BoxDecoration(
                color: _mint.withValues(alpha: .08),
                borderRadius: BorderRadius.circular(4),
              ),
              child: Text(
                label,
                style: const TextStyle(color: _mint, fontSize: 10),
              ),
            ),
          ],
        ),
        const SizedBox(height: 12),
        Text(
          (operation['mode'] as String).replaceAll('_', ' '),
          style: const TextStyle(fontSize: 16),
        ),
        const SizedBox(height: 10),
        Text(
          'T+ $start–$end s  ·  ${end - start} s duration',
          style: const TextStyle(fontSize: 12),
        ),
        const SizedBox(height: 7),
        Text(
          '${recurring ? 'First window: ' : ''}${utc(start)} → ${utc(end)}',
          style: const TextStyle(color: _muted, fontSize: 11, height: 1.6),
        ),
        if (recurring)
          const Padding(
            padding: EdgeInsets.only(top: 8),
            child: Text(
              'Recurrence is resolved and validated by the simulator.',
              style: TextStyle(color: _muted, fontSize: 11),
            ),
          ),
      ],
    );
  }

  Widget _context(List<JsonMap> satellites) => Column(
    children: [
      _card(
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'Between scheduled windows',
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 20),
            for (final satellite in satellites)
              Padding(
                padding: const EdgeInsets.only(bottom: 16),
                child: Wrap(
                  spacing: 12,
                  runSpacing: 4,
                  children: [
                    Text(
                      satellite['satellite_id'] as String,
                      style: const TextStyle(fontSize: 12),
                    ),
                    Text(
                      (satellite['initial_mode'] as String? ?? 'Unknown')
                          .replaceAll('_', ' '),
                      style: const TextStyle(fontSize: 12, color: _muted),
                    ),
                  ],
                ),
              ),
            const Text(
              'These modes come from the run configuration. Live mode and resources are shown in telemetry.',
              style: TextStyle(color: _muted, fontSize: 12, height: 1.7),
            ),
          ],
        ),
      ),
      const SizedBox(height: 24),
      _card(
        Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Icon(Icons.info_outline_rounded, color: _mint, size: 22),
            const SizedBox(height: 14),
            const Text(
              'Review before applying',
              style: TextStyle(fontSize: 16),
            ),
            const SizedBox(height: 12),
            Text(
              mission.canReplaceRun
                  ? 'Configuration changes create a new run. The backend validates every window and rejects overlaps.'
                  : 'The active run keeps its original plan. Stop it from Overview before saving an edited configuration as a new run.',
              style: const TextStyle(color: _muted, height: 1.7, fontSize: 12),
            ),
            const SizedBox(height: 14),
            TextButton.icon(
              onPressed: onOverview,
              icon: const Icon(Icons.arrow_back, size: 16),
              label: const Text('Open Overview'),
            ),
          ],
        ),
      ),
      const SizedBox(height: 24),
      _card(
        const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Planning coverage', style: TextStyle(fontSize: 16)),
            SizedBox(height: 14),
            Text(
              'Configured task timing is available. Target suitability, weather, resource forecasts, and automatic scheduling recommendations are not connected.',
              style: TextStyle(color: _muted, fontSize: 12, height: 1.7),
            ),
          ],
        ),
      ),
    ],
  );

  Widget _fact(String label, String value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    children: [
      Text(
        label,
        style: const TextStyle(color: _muted, fontSize: 9, letterSpacing: 1.3),
      ),
      const SizedBox(height: 9),
      Text(value, style: const TextStyle(fontSize: 16)),
    ],
  );

  Widget _card(Widget child) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(24),
    decoration: BoxDecoration(
      color: _surface,
      border: Border.all(color: _border),
      borderRadius: BorderRadius.circular(8),
    ),
    child: child,
  );

  Widget _empty(
    IconData icon,
    String title,
    String detail,
    VoidCallback? action,
    String label,
  ) => _card(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Icon(icon, color: _mint, size: 28),
        const SizedBox(height: 20),
        Text(title, style: const TextStyle(fontSize: 20)),
        const SizedBox(height: 12),
        Text(detail, style: const TextStyle(color: _muted, height: 1.7)),
        const SizedBox(height: 20),
        OutlinedButton(onPressed: action, child: Text(label)),
      ],
    ),
  );
}
