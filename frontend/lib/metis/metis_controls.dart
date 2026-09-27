import 'package:flutter/material.dart';

import 'metis_charts.dart';
import 'metis_controller.dart';

/// The durable mission watch setting and its source-clock alert hint.
class MetisControls extends StatelessWidget {
  const MetisControls({super.key, required this.controller});

  final MetisController controller;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: Listenable.merge([controller, controller.mission]),
    builder: (context, _) {
      final brief = controller.briefing;
      if (brief == null) {
        return const SizedBox.shrink();
      }
      final time = DateTime.tryParse(brief.alert_at_utc ?? '')?.toUtc();
      final clock = time == null
          ? brief.alert_at_utc ?? 'Time unavailable'
          : '${time.hour.toString().padLeft(2, '0')}:'
                '${time.minute.toString().padLeft(2, '0')} UTC';
      final at = brief.alert_at_min == null
          ? clock
          : 'T${minuteLabel(brief.alert_at_min!)} min · $clock';
      return Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Wrap(
            spacing: 16,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              SegmentedButton<bool>(
                segments: const [
                  ButtonSegment(value: false, label: Text('Metis OFF')),
                  ButtonSegment(value: true, label: Text('Metis ON')),
                ],
                selected: {controller.metisOn},
                showSelectedIcon: false,
                onSelectionChanged: controller.canSetMetis
                    ? (values) => controller.setMetis(values.single)
                    : null,
                style: SegmentedButton.styleFrom(
                  selectedBackgroundColor: const Color(0xff0e2862),
                  selectedForegroundColor: metisText,
                  foregroundColor: metisMuted,
                  textStyle: const TextStyle(fontSize: 12),
                  visualDensity: VisualDensity.compact,
                ),
              ),
              Text(
                !controller.missionAvailable
                    ? 'Load the wildfire mission to enable Metis controls.'
                    : controller.metisOn
                    ? 'Metis monitors the mission for a planning alert.'
                    : 'Original schedule · no Metis alert or review pause.',
                style: const TextStyle(color: metisMuted, fontSize: 12),
              ),
            ],
          ),
          const SizedBox(height: 9),
          if (!controller.missionAvailable) ...[
            Text(
              'Mission start: ${brief.mission.t0_utc.replaceAll('T', ' ').replaceAll('Z', ' UTC')}',
              style: const TextStyle(color: metisText, fontSize: 12),
            ),
            const SizedBox(height: 7),
            FilledButton.icon(
              onPressed: controller.canLoadMission
                  ? controller.loadMission
                  : null,
              icon: const Icon(Icons.my_location, size: 16),
              label: const Text('Load wildfire mission'),
            ),
            if (!controller.canLoadMission)
              const Text(
                'Stop the run and select recorded BUPT-1 data to load this mission.',
                style: TextStyle(color: metisMuted, fontSize: 11),
              ),
          ] else
            Text(
              controller.alertRaised
                  ? 'Alert raised at $at. Review the recommendation in Investigations.'
                  : controller.metisOn
                  ? 'Expected alert: $at. The run pauses there for your decision.'
                  : 'Enable Metis before $at to receive the planning alert.',
              style: const TextStyle(
                color: metisText,
                fontSize: 12,
                height: 1.4,
              ),
            ),
          if (controller.missionAvailable &&
              controller.metisControlHint != null) ...[
            const SizedBox(height: 5),
            Text(
              controller.metisControlHint!,
              style: const TextStyle(color: metisMuted, fontSize: 11),
            ),
          ],
          if (controller.error case final error?) ...[
            const SizedBox(height: 7),
            Text(
              error,
              style: const TextStyle(color: thresholdColor, fontSize: 11),
            ),
          ],
        ],
      );
    },
  );
}
