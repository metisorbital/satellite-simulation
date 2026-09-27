import 'package:flutter/material.dart';

import '../api/metis_generated.dart' as metis;
import '../api/mission.dart';
import 'metis_charts.dart';
import 'metis_controller.dart';

const _imageAsset = 'assets/images/wildfire-camp-fire-landsat8.jpg';
const _imageAspect = 1400 / 933;
const _imageCredit =
    'Illustrative product: NASA Earth Observatory image by Joshua Stevens, using Landsat 8 '
    'data from the U.S. Geological Survey (Camp Fire, California, 8 November 2018). The '
    'simulator models energy and timing, not imaging.';

/// Metis in the Overview, above the globe: the request, the Metis switch, and
/// the plan to fly, with the proposal and forecast when Metis is on.
class MetisBar extends StatelessWidget {
  const MetisBar({super.key, required this.controller, required this.onLaunch});

  final MetisController controller;

  /// Runs a launch, such as flying a plan, then brings the results into view.
  final Future<void> Function(Future<void> Function() launch) onLaunch;

  @override
  Widget build(BuildContext context) => _scaled(
    context,
    ListenableBuilder(
      listenable: Listenable.merge([controller, controller.mission]),
      builder: (context, _) {
        final briefing = controller.briefing;
        if (controller.unavailable) return const SizedBox.shrink();
        final view = _MetisView(controller, onLaunch);
        if (briefing == null) {
          return Padding(
            padding: const EdgeInsets.fromLTRB(22, 16, 22, 0),
            child: controller.error != null
                ? view._problem(controller.error!)
                : const LinearProgressIndicator(minHeight: 2),
          );
        }
        return LayoutBuilder(
          builder: (context, constraints) {
            final wide = constraints.maxWidth >= 740;
            return Padding(
              padding: const EdgeInsets.fromLTRB(22, 18, 22, 18),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.stretch,
                children: [
                  view._header(briefing),
                  const SizedBox(height: 16),
                  view._switch(),
                  const SizedBox(height: 14),
                  if (controller.error != null) ...[
                    view._problem(controller.error!),
                    const SizedBox(height: 14),
                  ],
                  if (controller.alert case final alert?) ...[
                    view._alert(briefing, alert),
                    const SizedBox(height: 16),
                    view._forecasts(briefing, wide),
                    if (alert.state != 'pending') ...[
                      const SizedBox(height: 16),
                      view._flyRow(),
                    ],
                  ] else
                    view._flyRow(),
                ],
              ),
            );
          },
        );
      },
    ),
  );
}

/// Metis text is set a little larger than the rest of the Overview.
Widget _scaled(BuildContext context, Widget child) => MediaQuery(
  data: MediaQuery.of(
    context,
  ).copyWith(textScaler: const TextScaler.linear(1.15)),
  child: child,
);

/// Metis in the Overview, below the globe: energy margin, the wildfire image,
/// verdicts and the task timeline of the plan being shown.
class MetisResults extends StatelessWidget {
  const MetisResults({super.key, required this.controller});

  final MetisController controller;

  @override
  Widget build(BuildContext context) => _scaled(
    context,
    ListenableBuilder(
      listenable: controller,
      builder: (context, _) {
        final briefing = controller.briefing;
        if (controller.unavailable || briefing == null) {
          return const SizedBox.shrink();
        }
        final view = _MetisView(controller, (launch) => launch());
        return LayoutBuilder(
          builder: (context, constraints) => Padding(
            padding: const EdgeInsets.fromLTRB(22, 18, 22, 18),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: [
                view._run(briefing, constraints.maxWidth >= 740),
                const SizedBox(height: 12),
                Text(
                  controller.metisOn
                      ? '${briefing.forecast.source} Forecast made at ${briefing.forecast.decision_time_source}, '
                            'mapped to mission −15; the run pauses at +60, before the batch starts, for Metis\'s '
                            'alert, which does not re-forecast. Everything measured is simulator physics '
                            'through public telemetry and events.'
                      : 'Metis is off: the mission flies its original schedule with no forecast. Everything '
                            'shown is simulator physics through public telemetry and events.',
                  style: const TextStyle(fontSize: 11, color: metisMuted),
                ),
              ],
            ),
          ),
        );
      },
    ),
  );
}

class _MetisView {
  _MetisView(this.controller, this.onLaunch);

  final MetisController controller;
  final Future<void> Function(Future<void> Function() launch) onLaunch;

  Mission get mission => controller.mission;

  Widget _header(metis.MetisBriefing briefing) {
    final mission = briefing.mission;
    final t0 = DateTime.tryParse(mission.t0_utc);
    String hhmm(DateTime? t) => t == null
        ? '—'
        : '${t.toUtc().hour.toString().padLeft(2, '0')}:${t.toUtc().minute.toString().padLeft(2, '0')}';
    final decision = t0?.add(Duration(minutes: mission.decision_min.round()));
    final outcome = controller.outcome;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        const Text(
          'METIS / WILDFIRE OBSERVATION',
          style: TextStyle(color: metisMuted, fontSize: 10, letterSpacing: 1.6),
        ),
        const SizedBox(height: 8),
        Text(
          mission.title,
          style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 8),
        Text(
          mission.request,
          style: const TextStyle(color: metisMuted, fontSize: 13),
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 34,
          runSpacing: 12,
          children: [
            _fact(
              'REQUEST ARRIVED',
              '${hhmm(decision)} UTC · T0 ${minuteLabel(mission.decision_min)} min',
            ),
            _fact('MISSION T0', '${hhmm(t0)} UTC'),
            _fact(
              'IMAGE NEEDED BY',
              'Briefing ${minuteLabel(mission.delivery_deadline_min)} min',
            ),
            if (mission.environment_source != null)
              _fact('SIMULATED CONDITIONS', mission.environment_source!),
            _fact(
              'RUN',
              outcome == null
                  ? 'Not flown'
                  : outcome.complete
                  ? 'Complete'
                  : controller.alert?.state == 'pending'
                  ? 'Held at ${minuteLabel(outcome.committed_min)} min for your decision'
                  : controller.activeMode == controller.mode
                  ? 'Playing · ${minuteLabel(outcome.committed_min)} min'
                        '${controller.metisOn && controller.alert == null ? ' · Metis watching' : ''}'
                  : 'Stopped at ${minuteLabel(outcome.committed_min)} min',
            ),
          ],
        ),
      ],
    );
  }

  Widget _switch() {
    final busy = controller.busy || mission.busy;
    return Wrap(
      spacing: 18,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        SegmentedButton<bool>(
          segments: const [
            ButtonSegment(value: false, label: Text('Metis OFF')),
            ButtonSegment(
              value: true,
              label: Text('Metis ON'),
              icon: Icon(Icons.auto_awesome, size: 16),
            ),
          ],
          selected: {controller.metisOn},
          showSelectedIcon: false,
          onSelectionChanged: busy ? null : (s) => controller.setMetis(s.first),
        ),
        Text(
          controller.metisOn
              ? 'Metis watches the power budget and alerts you when a change is needed.'
              : 'The mission flies its original schedule, with no power forecast.',
          style: const TextStyle(color: metisMuted, fontSize: 12),
        ),
      ],
    );
  }

  Widget _flyRow() {
    final busy = controller.busy || mission.busy;
    return Wrap(
      spacing: 12,
      runSpacing: 10,
      crossAxisAlignment: WrapCrossAlignment.center,
      children: [
        FilledButton.icon(
          onPressed: busy ? null : () => onLaunch(controller.fly),
          icon: const Icon(Icons.rocket_launch_outlined, size: 18),
          label: Text(controller.outcome == null ? 'Fly mission' : 'Fly again'),
        ),
        if (controller.outcomes.isNotEmpty)
          OutlinedButton.icon(
            onPressed: busy ? null : controller.reset,
            icon: const Icon(Icons.replay, size: 16),
            label: const Text('Reset rehearsal'),
          ),
        if (busy) _spinner(),
      ],
    );
  }

  Widget _alert(metis.MetisBriefing briefing, metis.MetisAlert alert) {
    final p = briefing.proposal;
    final busy = controller.busy || mission.busy;
    final at = minuteLabel(alert.raised_at_min);
    if (alert.state != 'pending') {
      final approved = alert.state == 'approved';
      return _card(
        Row(
          children: [
            Icon(
              approved ? Icons.check_circle : Icons.do_not_disturb_on_outlined,
              color: approved ? metisColor : originalColor,
              size: 20,
            ),
            const SizedBox(width: 10),
            Flexible(
              child: Text(
                approved
                    ? 'Metis alert at $at approved by ${alert.decided_by}: the batch moved from '
                          '${minuteLabel(p.from_start_min)} to ${minuteLabel(p.to_start_min)}.'
                    : 'Metis alert at $at dismissed by ${alert.decided_by}: the original schedule continues.',
                style: const TextStyle(fontSize: 14),
              ),
            ),
          ],
        ),
      );
    }
    final alternatives = p.alternatives
        .map(
          (a) =>
              '${a.planner} ${a.start_min == null ? 'no slot' : minuteLabel(a.start_min!)}',
        )
        .join(' · ');
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.all(18),
      decoration: BoxDecoration(
        color: originalColor.withValues(alpha: .07),
        border: Border.all(
          color: originalColor.withValues(alpha: .7),
          width: 1.4,
        ),
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              const Icon(
                Icons.warning_amber_rounded,
                color: originalColor,
                size: 20,
              ),
              const SizedBox(width: 8),
              Text(
                'METIS ALERT · $at',
                style: const TextStyle(
                  color: originalColor,
                  fontSize: 11,
                  letterSpacing: 1.6,
                  fontWeight: FontWeight.w600,
                ),
              ),
            ],
          ),
          const SizedBox(height: 8),
          Text(
            'Move the routine compute batch from ${minuteLabel(p.from_start_min)} to ${minuteLabel(p.to_start_min)}?',
            style: const TextStyle(fontSize: 22, fontWeight: FontWeight.w600),
          ),
          const SizedBox(height: 10),
          Text(p.rationale, style: const TextStyle(fontSize: 13, height: 1.45)),
          const SizedBox(height: 14),
          Wrap(
            spacing: 34,
            runSpacing: 12,
            children: [
              _fact(
                'ORIGINAL ENTERS RESERVE',
                p.original_crossing_min == null
                    ? 'Never'
                    : '+${p.original_crossing_min!.toStringAsFixed(1)} min',
              ),
              _fact(
                'MARGIN AT DOWNLINK, ORIGINAL VS METIS',
                '${p.original_downlink_start_wh.toStringAsFixed(2)} vs ${p.proposed_downlink_start_wh.toStringAsFixed(2)} Wh',
              ),
              _fact(
                'LOWEST MARGIN, METIS PLAN',
                '${p.proposed_min_wh.toStringAsFixed(2)} Wh',
              ),
            ],
          ),
          const SizedBox(height: 10),
          Text(
            'Other planner inputs would choose: $alternatives',
            style: const TextStyle(fontSize: 11, color: metisMuted),
          ),
          const SizedBox(height: 16),
          Wrap(
            spacing: 12,
            runSpacing: 10,
            crossAxisAlignment: WrapCrossAlignment.center,
            children: [
              FilledButton.icon(
                onPressed: busy ? null : () => onLaunch(controller.approve),
                icon: const Icon(Icons.check_circle_outline, size: 18),
                label: const Text('Approve and uplink'),
              ),
              OutlinedButton.icon(
                onPressed: busy ? null : controller.dismiss,
                icon: const Icon(Icons.close, size: 16),
                label: const Text('Dismiss'),
              ),
              Text(
                'The run is held at $at until you decide; the batch starts at ${minuteLabel(p.from_start_min)}.',
                style: const TextStyle(fontSize: 12, color: metisMuted),
              ),
              if (busy) _spinner(),
            ],
          ),
        ],
      ),
    );
  }

  Widget _forecasts(metis.MetisBriefing briefing, bool wide) {
    final f = briefing.forecast;
    final eclipses = briefing.mission.eclipses;
    final measured = controller.outcomes['metis_on'];
    Widget chart(
      String title,
      metis.ForecastBand band, {
      bool solar = false,
    }) => MissionLineChart(
      title: title,
      unit: 'W',
      eclipses: eclipses,
      band: (0, 1),
      minY: 0,
      series: [
        ChartSeries(
          'Low case',
          medianColor,
          stepSpots(f.bin_start_min, f.bin_minutes, band.p10),
          width: 0.6,
          legend: false,
        ),
        ChartSeries(
          'High case',
          medianColor,
          stepSpots(f.bin_start_min, f.bin_minutes, band.p90),
          width: 0.6,
          legend: false,
        ),
        ChartSeries(
          'Model median',
          medianColor,
          stepSpots(f.bin_start_min, f.bin_minutes, band.p50),
        ),
        ChartSeries(
          'Cautious (Metis plans with this)',
          metisColor,
          stepSpots(f.bin_start_min, f.bin_minutes, band.cautious),
          dash: const [5, 3],
        ),
        ChartSeries(
          'Nominal assumption',
          nominalColor,
          stepSpots(f.bin_start_min, f.bin_minutes, band.nominal),
          dash: const [2, 3],
          width: 1.4,
        ),
        if (solar && measured != null && measured.solar_w.minute.isNotEmpty)
          ChartSeries(
            'Measured in the simulator',
            actualColor,
            seriesSpots(measured.solar_w),
            width: 1.4,
          ),
      ],
      note: solar
          ? 'Forecast made at mission −15 for this spacecraft, per 5 minutes. Zero in eclipse.'
          : 'Housekeeping only; each task adds its own load.',
    );
    final open = controller.forecastOpen;
    final header = InkWell(
      onTap: controller.toggleForecast,
      borderRadius: BorderRadius.circular(4),
      child: Row(
        children: [
          Icon(
            open ? Icons.expand_less : Icons.expand_more,
            size: 20,
            color: metisMuted,
          ),
          const SizedBox(width: 8),
          const Flexible(
            child: Text(
              'Metis forecast: solar supply and essential load',
              style: TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
            ),
          ),
          if (!open) ...[
            const SizedBox(width: 10),
            const Flexible(
              child: Text(
                'Low-to-high band and the cautious input Metis plans with',
                overflow: TextOverflow.ellipsis,
                style: TextStyle(fontSize: 11, color: metisMuted),
              ),
            ),
          ],
        ],
      ),
    );
    if (!open) return _card(header);
    final solar = chart('Solar supply forecast', f.solar_w, solar: true);
    final load = chart('Essential load forecast', f.essential_w);
    return _card(
      Column(
        crossAxisAlignment: CrossAxisAlignment.stretch,
        children: [
          header,
          const SizedBox(height: 14),
          if (wide)
            Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Expanded(child: solar),
                const SizedBox(width: 24),
                Expanded(child: load),
              ],
            )
          else ...[
            solar,
            const SizedBox(height: 20),
            load,
          ],
        ],
      ),
    );
  }

  Widget _run(metis.MetisBriefing briefing, bool wide) {
    final outcome = controller.outcome;
    final margin = _card(_margin(briefing));
    final image = _card(_image(briefing, outcome));
    return Column(
      children: [
        if (wide)
          Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Expanded(flex: 3, child: margin),
              const SizedBox(width: 16),
              Expanded(flex: 2, child: image),
            ],
          )
        else ...[
          image,
          const SizedBox(height: 16),
          margin,
        ],
        if (outcome != null) ...[
          const SizedBox(height: 16),
          _verdicts(outcome, wide),
        ],
        const SizedBox(height: 16),
        _card(
          TaskTimeline(
            mission: briefing.mission,
            metisBatchStart: briefing.proposal.to_start_min,
            lanes: controller.alert != null
                ? const ['original', 'metis']
                : const ['original'],
            active: outcome?.plan ?? 'original',
            skipped: {
              for (final run in [?controller.comparison, ?outcome])
                run.plan: {
                  if (run.capture == 'skipped') 'thermal_capture',
                  if (run.batch == 'skipped') 'compute_batch',
                  if (run.downlink == 'skipped') 'downlink',
                },
            },
            playhead: outcome?.committed_min,
          ),
        ),
      ],
    );
  }

  Widget _margin(metis.MetisBriefing briefing) {
    final p = briefing.proposal;
    final on = controller.alert != null;
    final outcome = controller.outcome, other = controller.comparison;
    Color tone(String plan) => plan == 'metis' ? metisColor : originalColor;
    String label(metis.RunOutcome run) => !run.metis_on
        ? 'Metis OFF'
        : run.alert?.state == 'dismissed'
        ? 'Metis ON, alert dismissed'
        : 'Metis ON';
    final series = [
      if (on) ...[
        ChartSeries(
          'Original, Metis forecast',
          originalColor.withValues(alpha: outcome != null ? .4 : 1),
          seriesSpots(p.original_margin),
          dash: const [5, 3],
          width: outcome != null ? 1.1 : 2,
        ),
        ChartSeries(
          'Metis plan, forecast',
          metisColor.withValues(alpha: outcome != null ? .4 : 1),
          seriesSpots(p.proposed_margin),
          dash: const [5, 3],
          width: outcome != null ? 1.1 : 2,
        ),
      ],
      if (other != null && other.margin.minute.isNotEmpty)
        ChartSeries(
          '${label(other)}, last run',
          tone(other.plan).withValues(alpha: .45),
          seriesSpots(other.margin),
          width: 1.4,
        ),
      if (outcome != null && outcome.margin.minute.isNotEmpty)
        ChartSeries(
          '${label(outcome)}, measured',
          tone(outcome.plan),
          seriesSpots(outcome.margin),
        ),
    ];
    if (series.isEmpty) {
      return const SizedBox(
        height: 300,
        child: Center(
          child: Text(
            'Fly the mission to watch the battery margin.',
            style: TextStyle(color: metisMuted, fontSize: 13),
          ),
        ),
      );
    }
    return MissionLineChart(
      title: 'Battery energy above the protected reserve',
      unit: 'Wh',
      eclipses: briefing.mission.eclipses,
      threshold: 0,
      height: 260,
      playhead: outcome?.committed_min,
      markers: const [
        (90, 'Capture'),
        (100, 'Downlink'),
        (103, ''),
        (120, 'Briefing'),
        (165, 'Batch due'),
      ],
      series: series,
      note: outcome != null
          ? 'Measured in the simulator from public battery telemetry. Below zero the battery is inside '
                'its reserve and the satellite skips any task due. Shaded: eclipse.'
          : 'Metis forecast at −15. Below zero the plan would need energy from the protected reserve. '
                'Shaded: eclipse.',
    );
  }

  Widget _image(metis.MetisBriefing briefing, metis.RunOutcome? outcome) {
    final deadline = briefing.mission.delivery_deadline_min;
    String pct(double? v) =>
        v == null ? '—' : '${(v * 100).toStringAsFixed(1)}%';
    final (title, detail, tone) = switch (outcome) {
      null => (
        'Wildfire image',
        'The image appears here once it reaches the ground.',
        metisMuted,
      ),
      _ when outcome.delivered_at_min != null => (
        'Delivered at ${minuteLabel(outcome.delivered_at_min!)}',
        '${(deadline - outcome.delivered_at_min!).round()} minutes before the '
            '${minuteLabel(deadline)} briefing.',
        metisColor,
      ),
      _ when outcome.downlink == 'skipped' => (
        'Image not delivered',
        'The downlink was due at +100, but the battery was inside its protected reserve '
            '(${pct(outcome.downlink_start_soc)} charge, limit ${pct(outcome.limit_soc)}), so the '
            'satellite skipped it. The image is still on board and misses the '
            '${minuteLabel(deadline)} briefing.',
        thresholdColor,
      ),
      _ when outcome.capture == 'skipped' => (
        'No image captured',
        'The capture at +90 was skipped: the battery was inside its protected reserve.',
        thresholdColor,
      ),
      _ when outcome.downlink == 'running' => (
        'Receiving image · ${(outcome.downlink_progress * 100).round()}%',
        'Downlink +100 to +103.',
        medianColor,
      ),
      _ when outcome.capture == 'done' => (
        'Image captured at +90, stored on board',
        'Waiting for the +100 downlink.',
        medianColor,
      ),
      _ when outcome.capture == 'running' => (
        'Capturing',
        'Thermal capture +90 to +91.5.',
        medianColor,
      ),
      _ => (
        'Waiting for the capture at +90',
        'The image appears here once it reaches the ground.',
        metisMuted,
      ),
    };
    final progress = outcome == null
        ? 0.0
        : outcome.delivered_at_min != null
        ? 1.0
        : outcome.downlink == 'running' && outcome.capture == 'done'
        ? outcome.downlink_progress
        : 0.0;
    final failed =
        outcome != null &&
        (outcome.downlink == 'skipped' || outcome.capture == 'skipped');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(
          title,
          style: TextStyle(
            color: tone,
            fontSize: 16,
            fontWeight: FontWeight.w600,
          ),
        ),
        const SizedBox(height: 4),
        Text(detail, style: const TextStyle(fontSize: 12, height: 1.4)),
        const SizedBox(height: 12),
        AspectRatio(
          aspectRatio: _imageAspect,
          child: ClipRRect(
            borderRadius: BorderRadius.circular(6),
            child: LayoutBuilder(
              builder: (context, box) => Stack(
                fit: StackFit.expand,
                children: [
                  Container(
                    decoration: BoxDecoration(
                      color: const Color(0xff050b16),
                      border: Border.all(
                        color: failed
                            ? thresholdColor.withValues(alpha: .5)
                            : metisBorder,
                      ),
                      borderRadius: BorderRadius.circular(6),
                    ),
                    child: progress == 0
                        ? Icon(
                            failed
                                ? Icons.cloud_off_outlined
                                : Icons.satellite_alt_outlined,
                            size: 40,
                            color: failed
                                ? thresholdColor.withValues(alpha: .7)
                                : metisBorder,
                          )
                        : null,
                  ),
                  if (progress > 0)
                    // The downlink lasts about 1.5 s at demo speed; ease between
                    // polled progress values so the image visibly sweeps in.
                    TweenAnimationBuilder<double>(
                      tween: Tween(end: progress),
                      duration: const Duration(milliseconds: 1400),
                      curve: Curves.easeOut,
                      builder: (context, shown, _) => Stack(
                        fit: StackFit.expand,
                        children: [
                          ClipRect(
                            clipper: _TopFraction(shown),
                            child: Image.asset(_imageAsset, fit: BoxFit.cover),
                          ),
                          if (shown < .999)
                            Positioned(
                              top: box.maxHeight * shown - 1,
                              left: 0,
                              right: 0,
                              child: Container(height: 2, color: medianColor),
                            ),
                        ],
                      ),
                    ),
                ],
              ),
            ),
          ),
        ),
        if (progress > 0) ...[
          const SizedBox(height: 8),
          const Text(
            _imageCredit,
            style: TextStyle(fontSize: 10, color: metisMuted, height: 1.4),
          ),
        ],
      ],
    );
  }

  Widget _verdicts(metis.RunOutcome outcome, bool wide) {
    final batchEnd = outcome.batch_start_min + 16;
    Widget verdict(String label, String state, String text) {
      final (icon, tone) = switch (state) {
        'good' => (Icons.check_circle, metisColor),
        'bad' => (Icons.cancel, thresholdColor),
        'live' => (Icons.timelapse, medianColor),
        _ => (Icons.hourglass_empty, metisMuted),
      };
      return Row(
        mainAxisSize: MainAxisSize.min,
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Icon(icon, size: 18, color: tone),
          const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text(
                  label,
                  style: const TextStyle(
                    color: metisMuted,
                    fontSize: 9,
                    letterSpacing: 1.4,
                  ),
                ),
                const SizedBox(height: 3),
                Text(
                  text,
                  style: TextStyle(
                    color: tone,
                    fontSize: 14,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ],
            ),
          ),
        ],
      );
    }

    String task(String state, String done) => switch (state) {
      'done' => done,
      'running' => 'Running',
      'skipped' => 'Skipped',
      _ => 'Pending',
    };
    String tone(String state) => switch (state) {
      'done' => 'good',
      'running' => 'live',
      'skipped' => 'bad',
      _ => 'wait',
    };
    final low = outcome.min_wh == null
        ? ''
        : ' · lowest ${outcome.min_wh!.toStringAsFixed(2)} Wh';
    final items = [
      verdict(
        'WILDFIRE IMAGE',
        outcome.delivered_at_min != null
            ? 'good'
            : outcome.downlink == 'skipped' || outcome.capture == 'skipped'
            ? 'bad'
            : outcome.downlink == 'running'
            ? 'live'
            : 'wait',
        outcome.delivered_at_min != null
            ? 'Delivered at ${minuteLabel(outcome.delivered_at_min!)}'
            : outcome.downlink == 'skipped' || outcome.capture == 'skipped'
            ? 'Not delivered'
            : outcome.downlink == 'running'
            ? 'Receiving'
            : 'Pending',
      ),
      verdict(
        'COMPUTE BATCH ${minuteLabel(outcome.batch_start_min)} TO ${minuteLabel(batchEnd)}',
        tone(outcome.batch),
        task(outcome.batch, 'Done'),
      ),
      verdict(
        'BATTERY RESERVE',
        outcome.first_negative_min != null
            ? 'bad'
            : outcome.complete
            ? 'good'
            : 'live',
        outcome.first_negative_min != null
            ? 'Entered at +${outcome.first_negative_min!.toStringAsFixed(1)}$low'
            : '${outcome.complete ? 'Kept' : 'Intact so far'}$low',
      ),
    ];
    return _card(
      Wrap(
        spacing: 40,
        runSpacing: 14,
        children: [
          for (final item in items)
            ConstrainedBox(
              constraints: BoxConstraints(maxWidth: wide ? 360 : 520),
              child: item,
            ),
        ],
      ),
    );
  }

  Widget _spinner() => const SizedBox(
    width: 18,
    height: 18,
    child: CircularProgressIndicator(strokeWidth: 2),
  );

  Widget _fact(String label, String value) => Column(
    crossAxisAlignment: CrossAxisAlignment.start,
    mainAxisSize: MainAxisSize.min,
    children: [
      Text(
        label,
        style: const TextStyle(
          color: metisMuted,
          fontSize: 9,
          letterSpacing: 1.4,
        ),
      ),
      const SizedBox(height: 4),
      Text(
        value,
        style: const TextStyle(fontSize: 14, fontWeight: FontWeight.w600),
      ),
    ],
  );

  Widget _card(Widget child) => Container(
    width: double.infinity,
    padding: const EdgeInsets.all(18),
    decoration: BoxDecoration(
      color: metisSurface,
      border: Border.all(color: metisBorder),
      borderRadius: BorderRadius.circular(8),
    ),
    child: child,
  );

  Widget _problem(String message) => Container(
    padding: const EdgeInsets.all(14),
    decoration: BoxDecoration(
      color: thresholdColor.withValues(alpha: .08),
      border: Border.all(color: thresholdColor.withValues(alpha: .4)),
      borderRadius: BorderRadius.circular(6),
    ),
    child: Text(
      message,
      style: const TextStyle(color: thresholdColor, fontSize: 12),
    ),
  );
}

/// Clips to the top [fraction] of the child, for the image arriving line by line.
class _TopFraction extends CustomClipper<Rect> {
  _TopFraction(this.fraction);

  final double fraction;

  @override
  Rect getClip(Size size) =>
      Rect.fromLTWH(0, 0, size.width, size.height * fraction.clamp(0, 1));

  @override
  bool shouldReclip(_TopFraction old) => old.fraction != fraction;
}
