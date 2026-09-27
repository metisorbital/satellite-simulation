import 'package:flutter/material.dart';

import '../api/metis_generated.dart' as metis;
import 'metis_charts.dart';
import 'metis_controller.dart';

const _imageAsset = 'assets/images/wildfire-camp-fire-landsat8.jpg';

/// Small Overview entry point for the operator's saved mission record.
class MetisSummary extends StatelessWidget {
  const MetisSummary({
    super.key,
    required this.controller,
    required this.onOpen,
  });

  final MetisController controller;
  final VoidCallback onOpen;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) {
      if (controller.unavailable) return const SizedBox.shrink();
      final brief = controller.briefing;
      if (brief == null) return const SizedBox.shrink();
      final runStatus = controller.mission.status?['status'] as String?;
      final phase = runStatus == 'created'
          ? 'mission ready'
          : controller.state == 'awaiting_decision'
          ? 'awaiting decision'
          : runStatus ?? 'mission ready';
      return Padding(
        padding: const EdgeInsets.fromLTRB(20, 14, 20, 10),
        child: Material(
          color: metisSurface,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(8),
            side: const BorderSide(color: metisBorder),
          ),
          child: InkWell(
            onTap: onOpen,
            borderRadius: BorderRadius.circular(8),
            child: Padding(
              padding: const EdgeInsets.symmetric(horizontal: 18, vertical: 14),
              child: Row(
                children: [
                  const Icon(
                    Icons.local_fire_department_outlined,
                    color: originalColor,
                    size: 23,
                  ),
                  const SizedBox(width: 14),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          brief.mission.title,
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: metisText,
                            fontWeight: FontWeight.w600,
                          ),
                        ),
                        const SizedBox(height: 3),
                        Text(
                          controller.hasMission
                              ? 'BUPT-1 · $phase · Metis ${controller.metisOn ? 'ON' : 'OFF'}'
                              : !controller.missionAvailable
                              ? 'Saved forecast unavailable for this source'
                              : 'BUPT-1 recorded replay · mission ready when run starts',
                          maxLines: 1,
                          overflow: TextOverflow.ellipsis,
                          style: const TextStyle(
                            color: metisMuted,
                            fontSize: 11,
                          ),
                        ),
                      ],
                    ),
                  ),
                  const SizedBox(width: 10),
                  const Text(
                    'Open Missions',
                    style: TextStyle(color: metisText, fontSize: 11),
                  ),
                  const SizedBox(width: 4),
                  const Icon(Icons.chevron_right, color: metisText, size: 19),
                ],
              ),
            ),
          ),
        ),
      );
    },
  );
}

/// Below-globe context for the recorded mission and its original schedule.
///
/// Saved forecasts and shifted schedules stay hidden until the server creates
/// the linked operator case, so the overview cannot imply an alert early.
class MetisOverviewPanels extends StatelessWidget {
  /// Creates the below-globe Metis panels.
  const MetisOverviewPanels({
    super.key,
    required this.controller,
    this.controls,
    this.onOpenMissions,
    this.onInvestigation,
  });

  /// Controller that supplies the saved mission and case state.
  final MetisController controller;

  /// Persisted Metis On/Off controls supplied by the integration layer.
  final Widget? controls;

  /// Opens the detailed Missions surface.
  final VoidCallback? onOpenMissions;

  /// Opens the linked investigation once the preventive alert is raised.
  final VoidCallback? onInvestigation;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) {
      final brief = controller.briefing;
      if (controller.unavailable || brief == null) {
        return const SizedBox.shrink();
      }
      final alertRaised = controller.caseId != null;
      return Padding(
        padding: const EdgeInsets.fromLTRB(20, 0, 20, 20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            _card(
              Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      const Expanded(
                        child: Text(
                          'WILDFIRE RESPONSE MISSION',
                          style: TextStyle(
                            color: metisMuted,
                            fontSize: 10,
                            fontWeight: FontWeight.w700,
                            letterSpacing: 1.2,
                          ),
                        ),
                      ),
                      if (onOpenMissions != null)
                        TextButton(
                          onPressed: onOpenMissions,
                          child: const Text('Open Missions'),
                        ),
                    ],
                  ),
                  const SizedBox(height: 4),
                  const Text(
                    'Uploaded mission',
                    style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                  ),
                  const SizedBox(height: 8),
                  const Text(
                    'Capture is planned for T+90–91.5, followed by image downlink at T+100–103.',
                    style: TextStyle(
                      color: metisMuted,
                      fontSize: 11,
                      height: 1.45,
                    ),
                  ),
                  if (controls != null) ...[
                    const SizedBox(height: 12),
                    controls!,
                  ],
                  const SizedBox(height: 16),
                  TaskTimeline(
                    mission: brief.mission,
                    metisBatchStart: brief.proposal.to_start_min,
                    lanes: alertRaised
                        ? const ['original', 'metis']
                        : const ['original'],
                    active:
                        alertRaised && controller.missionState?.plan == 'metis'
                        ? 'metis'
                        : 'original',
                  ),
                  const SizedBox(height: 16),
                  _SplitMissionProgress(
                    briefing: brief,
                    outcome: controller.outcome,
                    metisEnabled: controller.metisOn,
                    alertRaised: alertRaised,
                  ),
                ],
              ),
            ),
            const SizedBox(height: 16),
            _EnergyMarginProjection(
              briefing: brief,
              outcome: controller.outcome,
              playhead: controller.missionMinute,
              showComparison: alertRaised,
            ),
            if (alertRaised) ...[
              const SizedBox(height: 16),
              _ForecastProjection(
                briefing: brief,
                playhead: controller.missionMinute,
              ),
              const SizedBox(height: 16),
              _ProposalProjection(briefing: brief),
              if (onInvestigation != null) ...[
                const SizedBox(height: 12),
                OutlinedButton.icon(
                  onPressed: onInvestigation,
                  icon: const Icon(Icons.open_in_new, size: 16),
                  label: const Text('Review preventive warning'),
                ),
              ],
            ],
          ],
        ),
      );
    },
  );
}

/// Full mission intent, saved forecast, proposal, and observable replay status.
class MetisMissionDetail extends StatelessWidget {
  const MetisMissionDetail({
    super.key,
    required this.controller,
    required this.onInvestigation,
    this.controls,
  });

  final MetisController controller;
  final VoidCallback onInvestigation;

  /// Persisted Metis On/Off controls supplied by the integration layer.
  final Widget? controls;

  @override
  Widget build(BuildContext context) => ListenableBuilder(
    listenable: controller,
    builder: (context, _) {
      final brief = controller.briefing;
      if (brief == null) {
        return Center(
          child: Text(
            controller.error ?? 'Loading mission details…',
            style: const TextStyle(color: metisMuted),
          ),
        );
      }
      final mission = brief.mission;
      final proposal = brief.proposal;
      final state = controller.missionState;
      final status = controller.state.replaceAll('_', ' ');
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Text(
            'MISSIONS / WILDFIRE OBSERVATION',
            style: TextStyle(
              color: metisMuted,
              fontSize: 10,
              letterSpacing: 1.4,
            ),
          ),
          const SizedBox(height: 10),
          Text(
            mission.title,
            style: const TextStyle(fontSize: 26, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 8),
          Text(
            mission.request,
            style: const TextStyle(
              color: metisMuted,
              fontSize: 13,
              height: 1.5,
            ),
          ),
          const SizedBox(height: 16),
          if (controls != null) ...[controls!, const SizedBox(height: 16)],
          _card(
            Wrap(
              spacing: 30,
              runSpacing: 14,
              children: [
                _fact('SPACECRAFT', state?.satellite_id ?? 'BUPT-1'),
                _fact('SOURCE', 'Recorded BUPT-1 power telemetry'),
                _fact('MISSION T0', mission.t0_utc),
                _fact(
                  'STATE',
                  controller.mission.status?['status'] as String? ?? status,
                ),
                _fact(
                  'DELIVERY WINDOW',
                  minuteLabel(mission.delivery_deadline_min),
                ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          if (controller.caseId != null) ...[
            _ForecastProjection(
              briefing: brief,
              playhead: controller.missionMinute,
            ),
            const SizedBox(height: 16),
            _ProposalProjection(briefing: brief),
          ],
          const SizedBox(height: 16),
          _card(
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  controller.caseId == null
                      ? 'Mission status'
                      : 'Operator decision',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                Text(
                  state == null
                      ? controller.missionAvailable
                            ? 'Press Start run in Overview to replay the recorded source and attach this mission.'
                            : controller.unavailableReason ??
                                  'This saved forecast requires the source-aligned BUPT-1 replay.'
                      : controller.caseId != null
                      ? 'A Metis forecast raised a case. Review evidence and decide in Investigations.'
                      : state.status == 'interrupted'
                      ? 'This replay ended before the forecast alert. Start a new source-aligned run to review the mission again.'
                      : controller.metisOn
                      ? 'No alert has been raised. The uploaded mission remains on its original schedule.'
                      : 'Metis is off. The uploaded mission follows its original schedule.',
                  style: const TextStyle(
                    color: metisMuted,
                    fontSize: 12,
                    height: 1.5,
                  ),
                ),
                if (controller.caseId != null) ...[
                  const SizedBox(height: 12),
                  OutlinedButton.icon(
                    onPressed: onInvestigation,
                    icon: const Icon(Icons.open_in_new, size: 16),
                    label: const Text('Review investigation'),
                  ),
                ],
              ],
            ),
          ),
          const SizedBox(height: 16),
          _card(
            Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                const Text(
                  'Mission schedule',
                  style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
                ),
                const SizedBox(height: 8),
                const Text(
                  'Task windows describe intent. The recording does not verify command execution or image delivery.',
                  style: TextStyle(color: metisMuted, fontSize: 11),
                ),
                const SizedBox(height: 18),
                TaskTimeline(
                  mission: mission,
                  metisBatchStart: proposal.to_start_min,
                  lanes: controller.caseId == null
                      ? const ['original']
                      : const ['original', 'metis'],
                  active: controller.caseId != null && state?.plan == 'metis'
                      ? 'metis'
                      : 'original',
                ),
                const SizedBox(height: 14),
                for (final task in mission.tasks)
                  Padding(
                    padding: const EdgeInsets.symmetric(vertical: 5),
                    child: Text(
                      '${task.name} · ${minuteLabel(task.start_min)} to ${minuteLabel(task.end_min)}'
                      '${task.added_load_w > 0 ? ' · planned +${task.added_load_w.toStringAsFixed(0)} W' : ''}',
                      style: const TextStyle(fontSize: 12),
                    ),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 16),
          _card(
            _SplitMissionProgress(
              briefing: brief,
              outcome: controller.outcome,
              metisEnabled: controller.metisOn,
              alertRaised: controller.caseId != null,
            ),
          ),
        ],
      );
    },
  );
}

class _EnergyMarginProjection extends StatelessWidget {
  const _EnergyMarginProjection({
    required this.briefing,
    required this.outcome,
    required this.playhead,
    required this.showComparison,
  });

  final metis.MetisBriefing briefing;
  final metis.RunOutcome? outcome;
  final double? playhead;
  final bool showComparison;

  @override
  Widget build(BuildContext context) => _card(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          'ENERGY MARGIN · DEMO PROJECTION',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Text(
          showComparison
              ? 'Original and preventive plans are shown beside the committed demo trace.'
              : 'The committed demo trace appears after Start.',
          style: TextStyle(color: metisMuted, fontSize: 11, height: 1.45),
        ),
        const SizedBox(height: 14),
        if (outcome == null || outcome!.margin.minute.isEmpty)
          const Text(
            'Start run to populate the committed energy-margin trace.',
            style: TextStyle(color: metisMuted, fontSize: 12),
          )
        else
          MissionLineChart(
            title: '',
            unit: 'Wh',
            eclipses: briefing.mission.eclipses,
            threshold: outcome!.threshold_wh,
            playhead: playhead,
            markers: const [(90.0, 'Capture'), (100.0, 'Downlink')],
            series: [
              ChartSeries(
                'Committed demo trace',
                actualColor,
                seriesSpots(outcome!.margin),
              ),
              if (showComparison)
                ChartSeries(
                  'Original plan',
                  originalColor,
                  seriesSpots(briefing.proposal.original_margin),
                  dash: const [6, 4],
                ),
              if (showComparison)
                ChartSeries(
                  'Preventive plan',
                  metisColor,
                  seriesSpots(briefing.proposal.proposed_margin),
                  dash: const [3, 3],
                ),
            ],
            note:
                'Demo projection; white marker is the committed replay position.',
          ),
      ],
    ),
  );
}

/// Shows the recorded-replay demo's modeled capture and downlink progression.
class _SplitMissionProgress extends StatelessWidget {
  const _SplitMissionProgress({
    required this.briefing,
    required this.outcome,
    required this.metisEnabled,
    required this.alertRaised,
  });

  final metis.MetisBriefing briefing;
  final metis.RunOutcome? outcome;
  final bool metisEnabled;
  final bool alertRaised;

  @override
  Widget build(BuildContext context) {
    final lanes = outcome?.comparison ?? const <metis.MissionLaneOutcome>[];
    final original = lanes.where((lane) => lane.plan == 'original').firstOrNull;
    final preventive = lanes.where((lane) => lane.plan == 'metis').firstOrNull;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'DEMO MISSION · IMAGE DOWNLINK',
          style: TextStyle(
            color: metisMuted,
            fontSize: 10,
            fontWeight: FontWeight.w700,
            letterSpacing: 1.2,
          ),
        ),
        const SizedBox(height: 8),
        if (!metisEnabled)
          _MissionLaneCard(
            title: 'METIS OFF · ROUTINE PLAN',
            lane: original,
            emptyBatch: 'T+70 · scheduled',
            showBatchStart: true,
            emptyMessage:
                'Original batch +70 · capture +90 · downlink +100–103',
          )
        else
          _MissionLaneCard(
            title: 'METIS ON · PREVENTIVE PLAN',
            lane: preventive,
            emptyBatch: alertRaised
                ? 'T+122 · awaiting approval'
                : 'Available after preventive alert',
            showBatchStart: alertRaised,
            emptyMessage:
                'Waiting for preventive review and standard approval.',
          ),
        const SizedBox(height: 8),
        const Text(
          'Demo projection · task and image states are modeled from the saved mission plan.',
          style: TextStyle(color: metisMuted, fontSize: 10, height: 1.4),
        ),
        const SizedBox(height: 4),
        const Text(
          'Illustrative image: NASA Earth Observatory / USGS Landsat 8, Camp Fire, 2018.',
          style: TextStyle(color: metisMuted, fontSize: 10, height: 1.4),
        ),
      ],
    );
  }
}

class _MissionLaneCard extends StatelessWidget {
  const _MissionLaneCard({
    required this.title,
    required this.lane,
    required this.emptyMessage,
    required this.emptyBatch,
    required this.showBatchStart,
  });

  final String title;
  final metis.MissionLaneOutcome? lane;
  final String emptyMessage;
  final String emptyBatch;
  final bool showBatchStart;

  @override
  Widget build(BuildContext context) {
    final progress = (lane?.downlink_progress ?? 0).clamp(0.0, 1.0);
    final delivered = lane?.delivered_at_min != null;
    final receiving = lane?.downlink == 'running';
    final reveal = delivered
        ? 1.0
        : receiving
        ? progress.clamp(.03, .98)
        : 0.0;
    final state = lane == null
        ? emptyMessage
        : lane!.execution_status == 'inactive'
        ? lane!.label
        : lane!.execution_status == 'awaiting_approval'
        ? 'Waiting for preventive review and standard approval.'
        : lane!.downlink == 'skipped'
        ? 'Downlink blocked before radio activation · no usable image.'
        : delivered
        ? 'Delivered +103 · response enabled.'
        : receiving
        ? 'Transmitting image · ${(progress * 100).round()}%'
        : lane!.capture == 'done'
        ? 'Image onboard · scheduled for downlink.'
        : lane!.capture == 'running'
        ? 'Capturing image.'
        : 'Scheduled.';
    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        border: Border.all(color: metisBorder),
        borderRadius: BorderRadius.circular(6),
        color: metisSurface,
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  title,
                  style: const TextStyle(
                    fontSize: 11,
                    fontWeight: FontWeight.w700,
                  ),
                ),
              ),
              if (lane != null)
                _LaneTag(label: lane!.execution_status.replaceAll('_', ' ')),
            ],
          ),
          const SizedBox(height: 7),
          Text(
            state,
            style: const TextStyle(
              color: metisMuted,
              fontSize: 11,
              height: 1.35,
            ),
          ),
          if (lane != null) ...[
            const SizedBox(height: 4),
            Text(
              lane!.label,
              style: const TextStyle(color: metisMuted, fontSize: 10),
            ),
          ],
          const SizedBox(height: 10),
          ClipRRect(
            borderRadius: BorderRadius.circular(4),
            child: SizedBox(
              height: 112,
              width: double.infinity,
              child: Stack(
                children: [
                  const ColoredBox(color: Color(0xff040d1a)),
                  if (reveal > 0)
                    TweenAnimationBuilder<double>(
                      tween: Tween<double>(begin: 0, end: reveal),
                      duration: const Duration(milliseconds: 350),
                      builder: (context, value, child) =>
                          ClipRect(clipper: _ImageReveal(value), child: child),
                      child: Image.asset(
                        _imageAsset,
                        fit: BoxFit.cover,
                        width: double.infinity,
                      ),
                    ),
                  if (lane?.downlink == 'skipped')
                    const Center(
                      child: Column(
                        mainAxisSize: MainAxisSize.min,
                        children: [
                          Icon(
                            Icons.error_outline_rounded,
                            color: Color(0xffff5268),
                            size: 30,
                          ),
                          SizedBox(height: 8),
                          Text(
                            'Downlink failed',
                            style: TextStyle(
                              color: Color(0xffff5268),
                              fontSize: 14,
                              fontWeight: FontWeight.w700,
                            ),
                          ),
                        ],
                      ),
                    )
                  else if (reveal == 0)
                    Center(
                      child: Text(
                        lane?.execution_status == 'awaiting_approval'
                            ? 'AWAITING APPROVAL'
                            : lane?.capture == 'running'
                            ? 'AWAITING CAPTURE'
                            : 'AWAITING TRANSMISSION',
                        textAlign: TextAlign.center,
                        style: const TextStyle(
                          color: metisText,
                          fontSize: 10,
                          fontWeight: FontWeight.w700,
                          letterSpacing: 1,
                        ),
                      ),
                    ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 10),
          Wrap(
            spacing: 14,
            runSpacing: 6,
            children: [
              _fact(
                'BATCH',
                lane == null || !showBatchStart
                    ? emptyBatch
                    : '${minuteLabel(lane!.batch_start_min)} · ${lane!.batch}',
              ),
              _fact('CAPTURE', lane?.capture ?? 'T+90'),
              _fact('DOWNLINK', lane?.downlink ?? 'T+100–103'),
            ],
          ),
          if (receiving && !delivered) ...[
            const SizedBox(height: 9),
            LinearProgressIndicator(value: progress, minHeight: 4),
          ],
        ],
      ),
    );
  }
}

class _LaneTag extends StatelessWidget {
  const _LaneTag({required this.label});

  final String label;

  @override
  Widget build(BuildContext context) => Container(
    padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 3),
    decoration: BoxDecoration(
      color: metisBorder,
      borderRadius: BorderRadius.circular(3),
    ),
    child: Text(
      label.toUpperCase(),
      style: const TextStyle(
        color: metisText,
        fontSize: 8,
        fontWeight: FontWeight.w700,
        letterSpacing: .7,
      ),
    ),
  );
}

class _ImageReveal extends CustomClipper<Rect> {
  const _ImageReveal(this.fraction);

  final double fraction;

  @override
  Rect getClip(Size size) =>
      Rect.fromLTWH(0, 0, size.width, size.height * fraction);

  @override
  bool shouldReclip(_ImageReveal oldClipper) => oldClipper.fraction != fraction;
}

class _ForecastProjection extends StatelessWidget {
  const _ForecastProjection({required this.briefing, required this.playhead});

  final metis.MetisBriefing briefing;
  final double? playhead;

  @override
  Widget build(BuildContext context) => _card(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'METIS PREVENTIVE ANALYSIS',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Text(
          'Origin ${briefing.forecast.decision_time_source} · ${briefing.forecast.source}. This fixed model projection does not re-forecast during the replay.',
          style: const TextStyle(color: metisMuted, fontSize: 11, height: 1.45),
        ),
        const SizedBox(height: 16),
        MissionLineChart(
          title: 'Solar supply projection',
          unit: 'W',
          eclipses: briefing.mission.eclipses,
          playhead: playhead,
          series: _bandSeries(
            briefing.forecast.bin_start_min,
            briefing.forecast.bin_minutes,
            briefing.forecast.solar_w,
          ),
        ),
        const SizedBox(height: 16),
        MissionLineChart(
          title: 'Essential load projection',
          unit: 'W',
          eclipses: briefing.mission.eclipses,
          playhead: playhead,
          series: _bandSeries(
            briefing.forecast.bin_start_min,
            briefing.forecast.bin_minutes,
            briefing.forecast.essential_w,
          ),
        ),
      ],
    ),
  );
}

List<ChartSeries> _bandSeries(
  List<double> starts,
  double width,
  metis.ForecastBand band,
) => [
  ChartSeries('P10', originalColor, stepSpots(starts, width, band.p10)),
  ChartSeries('P50', medianColor, stepSpots(starts, width, band.p50)),
  ChartSeries('P90', metisColor, stepSpots(starts, width, band.p90)),
];

class _ProposalProjection extends StatelessWidget {
  const _ProposalProjection({required this.briefing});

  final metis.MetisBriefing briefing;

  @override
  Widget build(BuildContext context) => _card(
    Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'RECOMMENDED SHIFT · CASE-LINKED',
          style: TextStyle(fontSize: 18, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Text(
          'Move the routine batch from T+70 to T+122 to protect the T+90 capture and T+100 downlink. ${briefing.proposal.rationale}',
          style: const TextStyle(color: metisMuted, fontSize: 12, height: 1.45),
        ),
        const SizedBox(height: 14),
        TaskTimeline(
          mission: briefing.mission,
          metisBatchStart: briefing.proposal.to_start_min,
          lanes: const ['original', 'metis'],
        ),
        const SizedBox(height: 14),
        Wrap(
          spacing: 30,
          runSpacing: 14,
          children: [
            _fact(
              'ROUTINE BATCH',
              '${minuteLabel(briefing.proposal.from_start_min)} → ${minuteLabel(briefing.proposal.to_start_min)}',
            ),
            _fact(
              'PROJECTED ORIGINAL MARGIN',
              '${briefing.proposal.original_downlink_start_wh.toStringAsFixed(2)} Wh',
            ),
            _fact(
              'PROJECTED PROPOSED MARGIN',
              '${briefing.proposal.proposed_downlink_start_wh.toStringAsFixed(2)} Wh',
            ),
          ],
        ),
      ],
    ),
  );
}

Widget _fact(String name, String value) => Column(
  crossAxisAlignment: CrossAxisAlignment.start,
  mainAxisSize: MainAxisSize.min,
  children: [
    Text(
      name,
      style: const TextStyle(
        color: metisMuted,
        fontSize: 9,
        letterSpacing: 1.2,
      ),
    ),
    const SizedBox(height: 5),
    Text(value, style: const TextStyle(color: metisText, fontSize: 13)),
  ],
);

Widget _card(Widget child) => Container(
  width: double.infinity,
  padding: const EdgeInsets.all(20),
  decoration: BoxDecoration(
    color: metisSurface,
    border: Border.all(color: metisBorder),
    borderRadius: BorderRadius.circular(8),
  ),
  child: child,
);
