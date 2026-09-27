// Generated from Pydantic v2 contracts. Do not edit by hand.
// dart format off
// Regenerate: uv run python scripts/generate_contracts.py
// ignore_for_file: non_constant_identifier_names, unnecessary_non_null_assertion, prefer_null_aware_operators, use_null_aware_elements

/// Slot another planner input would choose.
class Alternative {
  const Alternative({
    required this.planner,
    required this.start_min,
    required this.status,
  });

  final String planner;
  final double? start_min;
  final String status;

  factory Alternative.fromJson(Map<String, dynamic> json) => Alternative(
    planner: json['planner'] as String,
    start_min: json['start_min'] == null ? null : (json['start_min'] as num).toDouble(),
    status: json['status'] as String,
  );

  Map<String, dynamic> toJson() => {
    'planner': planner,
    'start_min': start_min == null ? null : start_min!,
    'status': status,
  };
}

/// The operator's approval window before T0.
class ApprovalWindow {
  const ApprovalWindow({
    required this.state,
    required this.opened_at,
    required this.closes_at,
    required this.remaining_s,
    required this.approved_by,
    required this.approved_at,
  });

  final String state;
  final String opened_at;
  final String closes_at;
  final double remaining_s;
  final String? approved_by;
  final String? approved_at;

  factory ApprovalWindow.fromJson(Map<String, dynamic> json) => ApprovalWindow(
    state: json['state'] as String,
    opened_at: json['opened_at'] as String,
    closes_at: json['closes_at'] as String,
    remaining_s: (json['remaining_s'] as num).toDouble(),
    approved_by: json['approved_by'] == null ? null : json['approved_by'] as String,
    approved_at: json['approved_at'] == null ? null : json['approved_at'] as String,
  );

  Map<String, dynamic> toJson() => {
    'state': state,
    'opened_at': opened_at,
    'closes_at': closes_at,
    'remaining_s': remaining_s,
    'approved_by': approved_by == null ? null : approved_by!,
    'approved_at': approved_at == null ? null : approved_at!,
  };
}

/// An approved proposal and the task windows the Metis plan flies.
class ApprovedPlan {
  const ApprovedPlan({
    required this.proposal_id,
    required this.approved_by,
    required this.approved_at,
    required this.tasks,
  });

  final String proposal_id;
  final String approved_by;
  final String approved_at;
  final List<TaskWindow> tasks;

  factory ApprovedPlan.fromJson(Map<String, dynamic> json) => ApprovedPlan(
    proposal_id: json['proposal_id'] as String,
    approved_by: json['approved_by'] as String,
    approved_at: json['approved_at'] as String,
    tasks: (json['tasks'] as List).map((item) => TaskWindow.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'proposal_id': proposal_id,
    'approved_by': approved_by,
    'approved_at': approved_at,
    'tasks': tasks.map((item) => item.toJson()).toList(),
  };
}

/// Per-5-minute forecast in mission watts.
class ForecastBand {
  const ForecastBand({
    required this.p10,
    required this.p50,
    required this.p90,
    required this.cautious,
    required this.nominal,
  });

  final List<double> p10;
  final List<double> p50;
  final List<double> p90;
  final List<double> cautious;
  final List<double> nominal;

  factory ForecastBand.fromJson(Map<String, dynamic> json) => ForecastBand(
    p10: (json['p10'] as List).map((item) => (item as num).toDouble()).toList(),
    p50: (json['p50'] as List).map((item) => (item as num).toDouble()).toList(),
    p90: (json['p90'] as List).map((item) => (item as num).toDouble()).toList(),
    cautious: (json['cautious'] as List).map((item) => (item as num).toDouble()).toList(),
    nominal: (json['nominal'] as List).map((item) => (item as num).toDouble()).toList(),
  );

  Map<String, dynamic> toJson() => {
    'p10': p10.map((item) => item).toList(),
    'p50': p50.map((item) => item).toList(),
    'p90': p90.map((item) => item).toList(),
    'cautious': cautious.map((item) => item).toList(),
    'nominal': nominal.map((item) => item).toList(),
  };
}

/// Metis's alert on a run it watches, and the operator's decision.
class MetisAlert {
  const MetisAlert({
    required this.state,
    required this.raised_at_min,
    required this.decided_by,
  });

  final String state;
  final double raised_at_min;
  final String? decided_by;

  factory MetisAlert.fromJson(Map<String, dynamic> json) => MetisAlert(
    state: json['state'] as String,
    raised_at_min: (json['raised_at_min'] as num).toDouble(),
    decided_by: json['decided_by'] == null ? null : json['decided_by'] as String,
  );

  Map<String, dynamic> toJson() => {
    'state': state,
    'raised_at_min': raised_at_min,
    'decided_by': decided_by == null ? null : decided_by!,
  };
}

/// Everything the Metis view shows before a run.
class MetisBriefing {
  const MetisBriefing({
    required this.mission,
    required this.forecast,
    required this.proposal,
    required this.window,
    required this.runs,
  });

  final MissionBrief mission;
  final MetisForecast forecast;
  final MetisProposal proposal;
  final ApprovalWindow window;
  final PlanRuns runs;

  factory MetisBriefing.fromJson(Map<String, dynamic> json) => MetisBriefing(
    mission: MissionBrief.fromJson(Map<String, dynamic>.from(json['mission'] as Map)),
    forecast: MetisForecast.fromJson(Map<String, dynamic>.from(json['forecast'] as Map)),
    proposal: MetisProposal.fromJson(Map<String, dynamic>.from(json['proposal'] as Map)),
    window: ApprovalWindow.fromJson(Map<String, dynamic>.from(json['window'] as Map)),
    runs: PlanRuns.fromJson(Map<String, dynamic>.from(json['runs'] as Map)),
  );

  Map<String, dynamic> toJson() => {
    'mission': mission.toJson(),
    'forecast': forecast.toJson(),
    'proposal': proposal.toJson(),
    'window': window.toJson(),
    'runs': runs.toJson(),
  };
}

/// Forecast made at the decision time.
class MetisForecast {
  const MetisForecast({
    required this.source,
    required this.decision_time_source,
    required this.trained_through,
    required this.caution_lambda,
    required this.bin_minutes,
    required this.bin_start_min,
    required this.solar_w,
    required this.essential_w,
  });

  final String source;
  final String decision_time_source;
  final String trained_through;
  final double caution_lambda;
  final double bin_minutes;
  final List<double> bin_start_min;
  final ForecastBand solar_w;
  final ForecastBand essential_w;

  factory MetisForecast.fromJson(Map<String, dynamic> json) => MetisForecast(
    source: json['source'] as String,
    decision_time_source: json['decision_time_source'] as String,
    trained_through: json['trained_through'] as String,
    caution_lambda: (json['caution_lambda'] as num).toDouble(),
    bin_minutes: (json['bin_minutes'] as num).toDouble(),
    bin_start_min: (json['bin_start_min'] as List).map((item) => (item as num).toDouble()).toList(),
    solar_w: ForecastBand.fromJson(Map<String, dynamic>.from(json['solar_w'] as Map)),
    essential_w: ForecastBand.fromJson(Map<String, dynamic>.from(json['essential_w'] as Map)),
  );

  Map<String, dynamic> toJson() => {
    'source': source,
    'decision_time_source': decision_time_source,
    'trained_through': trained_through,
    'caution_lambda': caution_lambda,
    'bin_minutes': bin_minutes,
    'bin_start_min': bin_start_min.map((item) => item).toList(),
    'solar_w': solar_w.toJson(),
    'essential_w': essential_w.toJson(),
  };
}

/// The proposed schedule change.
class MetisProposal {
  const MetisProposal({
    required this.proposal_id,
    required this.task_id,
    required this.from_start_min,
    required this.to_start_min,
    required this.status,
    required this.rationale,
    required this.original_crossing_min,
    required this.original_downlink_start_wh,
    required this.proposed_downlink_start_wh,
    required this.proposed_min_wh,
    required this.original_margin,
    required this.proposed_margin,
    required this.alternatives,
  });

  final String proposal_id;
  final String task_id;
  final double from_start_min;
  final double to_start_min;
  final String status;
  final String rationale;
  final double? original_crossing_min;
  final double original_downlink_start_wh;
  final double proposed_downlink_start_wh;
  final double proposed_min_wh;
  final MinuteSeries original_margin;
  final MinuteSeries proposed_margin;
  final List<Alternative> alternatives;

  factory MetisProposal.fromJson(Map<String, dynamic> json) => MetisProposal(
    proposal_id: json['proposal_id'] as String,
    task_id: json['task_id'] as String,
    from_start_min: (json['from_start_min'] as num).toDouble(),
    to_start_min: (json['to_start_min'] as num).toDouble(),
    status: json['status'] as String,
    rationale: json['rationale'] as String,
    original_crossing_min: json['original_crossing_min'] == null ? null : (json['original_crossing_min'] as num).toDouble(),
    original_downlink_start_wh: (json['original_downlink_start_wh'] as num).toDouble(),
    proposed_downlink_start_wh: (json['proposed_downlink_start_wh'] as num).toDouble(),
    proposed_min_wh: (json['proposed_min_wh'] as num).toDouble(),
    original_margin: MinuteSeries.fromJson(Map<String, dynamic>.from(json['original_margin'] as Map)),
    proposed_margin: MinuteSeries.fromJson(Map<String, dynamic>.from(json['proposed_margin'] as Map)),
    alternatives: (json['alternatives'] as List).map((item) => Alternative.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'proposal_id': proposal_id,
    'task_id': task_id,
    'from_start_min': from_start_min,
    'to_start_min': to_start_min,
    'status': status,
    'rationale': rationale,
    'original_crossing_min': original_crossing_min == null ? null : original_crossing_min!,
    'original_downlink_start_wh': original_downlink_start_wh,
    'proposed_downlink_start_wh': proposed_downlink_start_wh,
    'proposed_min_wh': proposed_min_wh,
    'original_margin': original_margin.toJson(),
    'proposed_margin': proposed_margin.toJson(),
    'alternatives': alternatives.map((item) => item.toJson()).toList(),
  };
}

/// Values at mission minutes.
class MinuteSeries {
  const MinuteSeries({
    required this.minute,
    required this.value,
  });

  final List<double> minute;
  final List<double> value;

  factory MinuteSeries.fromJson(Map<String, dynamic> json) => MinuteSeries(
    minute: (json['minute'] as List).map((item) => (item as num).toDouble()).toList(),
    value: (json['value'] as List).map((item) => (item as num).toDouble()).toList(),
  );

  Map<String, dynamic> toJson() => {
    'minute': minute.map((item) => item).toList(),
    'value': value.map((item) => item).toList(),
  };
}

/// The emergency request and the assumed mission.
class MissionBrief {
  const MissionBrief({
    required this.title,
    required this.request,
    required this.t0_utc,
    required this.decision_min,
    required this.duration_min,
    required this.tasks,
    required this.eclipses,
    required this.delivery_deadline_min,
    required this.batch_deadline_min,
    required this.reserve_wh,
    required this.environment_source,
  });

  final String title;
  final String request;
  final String t0_utc;
  final double decision_min;
  final double duration_min;
  final List<MissionTask> tasks;
  final List<MissionInterval> eclipses;
  final double delivery_deadline_min;
  final double batch_deadline_min;
  final double reserve_wh;
  final String? environment_source;

  factory MissionBrief.fromJson(Map<String, dynamic> json) => MissionBrief(
    title: json['title'] as String,
    request: json['request'] as String,
    t0_utc: json['t0_utc'] as String,
    decision_min: (json['decision_min'] as num).toDouble(),
    duration_min: (json['duration_min'] as num).toDouble(),
    tasks: (json['tasks'] as List).map((item) => MissionTask.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    eclipses: (json['eclipses'] as List).map((item) => MissionInterval.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    delivery_deadline_min: (json['delivery_deadline_min'] as num).toDouble(),
    batch_deadline_min: (json['batch_deadline_min'] as num).toDouble(),
    reserve_wh: (json['reserve_wh'] as num).toDouble(),
    environment_source: json['environment_source'] == null ? null : json['environment_source'] as String,
  );

  Map<String, dynamic> toJson() => {
    'title': title,
    'request': request,
    't0_utc': t0_utc,
    'decision_min': decision_min,
    'duration_min': duration_min,
    'tasks': tasks.map((item) => item.toJson()).toList(),
    'eclipses': eclipses.map((item) => item.toJson()).toList(),
    'delivery_deadline_min': delivery_deadline_min,
    'batch_deadline_min': batch_deadline_min,
    'reserve_wh': reserve_wh,
    'environment_source': environment_source == null ? null : environment_source!,
  };
}

/// A mission-minute interval, such as an eclipse.
class MissionInterval {
  const MissionInterval({
    required this.start_min,
    required this.end_min,
  });

  final double start_min;
  final double end_min;

  factory MissionInterval.fromJson(Map<String, dynamic> json) => MissionInterval(
    start_min: (json['start_min'] as num).toDouble(),
    end_min: (json['end_min'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'start_min': start_min,
    'end_min': end_min,
  };
}

/// One scheduled task of the original plan.
class MissionTask {
  const MissionTask({
    required this.task_id,
    required this.name,
    required this.start_min,
    required this.end_min,
    required this.added_load_w,
    required this.movable,
  });

  final String task_id;
  final String name;
  final double start_min;
  final double end_min;
  final double added_load_w;
  final bool movable;

  factory MissionTask.fromJson(Map<String, dynamic> json) => MissionTask(
    task_id: json['task_id'] as String,
    name: json['name'] as String,
    start_min: (json['start_min'] as num).toDouble(),
    end_min: (json['end_min'] as num).toDouble(),
    added_load_w: (json['added_load_w'] as num).toDouble(),
    movable: json['movable'] as bool,
  );

  Map<String, dynamic> toJson() => {
    'task_id': task_id,
    'name': name,
    'start_min': start_min,
    'end_min': end_min,
    'added_load_w': added_load_w,
    'movable': movable,
  };
}

/// The operator's latest demo run with Metis off and with Metis on.
class PlanRuns {
  const PlanRuns({
    required this.metis_off,
    required this.metis_on,
  });

  final String? metis_off;
  final String? metis_on;

  factory PlanRuns.fromJson(Map<String, dynamic> json) => PlanRuns(
    metis_off: json['metis_off'] == null ? null : json['metis_off'] as String,
    metis_on: json['metis_on'] == null ? null : json['metis_on'] as String,
  );

  Map<String, dynamic> toJson() => {
    'metis_off': metis_off == null ? null : metis_off!,
    'metis_on': metis_on == null ? null : metis_on!,
  };
}

/// What happened on one demo run so far, from public telemetry and events.
class RunOutcome {
  const RunOutcome({
    required this.run_id,
    required this.plan,
    required this.name,
    required this.metis_on,
    required this.alert,
    required this.committed_min,
    required this.complete,
    required this.threshold_wh,
    required this.limit_soc,
    required this.batch_start_min,
    required this.margin,
    required this.solar_w,
    required this.min_wh,
    required this.min_at_min,
    required this.first_negative_min,
    required this.capture_end_wh,
    required this.downlink_start_wh,
    required this.downlink_end_wh,
    required this.downlink_start_soc,
    required this.capture,
    required this.batch,
    required this.downlink,
    required this.downlink_progress,
    required this.delivered_at_min,
  });

  final String run_id;
  final String plan;
  final String name;
  final bool metis_on;
  final MetisAlert? alert;
  final double committed_min;
  final bool complete;
  final double threshold_wh;
  final double limit_soc;
  final double batch_start_min;
  final MinuteSeries margin;
  final MinuteSeries solar_w;
  final double? min_wh;
  final double? min_at_min;
  final double? first_negative_min;
  final double? capture_end_wh;
  final double? downlink_start_wh;
  final double? downlink_end_wh;
  final double? downlink_start_soc;
  final String capture;
  final String batch;
  final String downlink;
  final double downlink_progress;
  final double? delivered_at_min;

  factory RunOutcome.fromJson(Map<String, dynamic> json) => RunOutcome(
    run_id: json['run_id'] as String,
    plan: json['plan'] as String,
    name: json['name'] as String,
    metis_on: json['metis_on'] as bool,
    alert: json['alert'] == null ? null : MetisAlert.fromJson(Map<String, dynamic>.from(json['alert'] as Map)),
    committed_min: (json['committed_min'] as num).toDouble(),
    complete: json['complete'] as bool,
    threshold_wh: (json['threshold_wh'] as num).toDouble(),
    limit_soc: (json['limit_soc'] as num).toDouble(),
    batch_start_min: (json['batch_start_min'] as num).toDouble(),
    margin: MinuteSeries.fromJson(Map<String, dynamic>.from(json['margin'] as Map)),
    solar_w: MinuteSeries.fromJson(Map<String, dynamic>.from(json['solar_w'] as Map)),
    min_wh: json['min_wh'] == null ? null : (json['min_wh'] as num).toDouble(),
    min_at_min: json['min_at_min'] == null ? null : (json['min_at_min'] as num).toDouble(),
    first_negative_min: json['first_negative_min'] == null ? null : (json['first_negative_min'] as num).toDouble(),
    capture_end_wh: json['capture_end_wh'] == null ? null : (json['capture_end_wh'] as num).toDouble(),
    downlink_start_wh: json['downlink_start_wh'] == null ? null : (json['downlink_start_wh'] as num).toDouble(),
    downlink_end_wh: json['downlink_end_wh'] == null ? null : (json['downlink_end_wh'] as num).toDouble(),
    downlink_start_soc: json['downlink_start_soc'] == null ? null : (json['downlink_start_soc'] as num).toDouble(),
    capture: json['capture'] as String,
    batch: json['batch'] as String,
    downlink: json['downlink'] as String,
    downlink_progress: (json['downlink_progress'] as num).toDouble(),
    delivered_at_min: json['delivered_at_min'] == null ? null : (json['delivered_at_min'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'run_id': run_id,
    'plan': plan,
    'name': name,
    'metis_on': metis_on,
    'alert': alert == null ? null : alert!.toJson(),
    'committed_min': committed_min,
    'complete': complete,
    'threshold_wh': threshold_wh,
    'limit_soc': limit_soc,
    'batch_start_min': batch_start_min,
    'margin': margin.toJson(),
    'solar_w': solar_w.toJson(),
    'min_wh': min_wh == null ? null : min_wh!,
    'min_at_min': min_at_min == null ? null : min_at_min!,
    'first_negative_min': first_negative_min == null ? null : first_negative_min!,
    'capture_end_wh': capture_end_wh == null ? null : capture_end_wh!,
    'downlink_start_wh': downlink_start_wh == null ? null : downlink_start_wh!,
    'downlink_end_wh': downlink_end_wh == null ? null : downlink_end_wh!,
    'downlink_start_soc': downlink_start_soc == null ? null : downlink_start_soc!,
    'capture': capture,
    'batch': batch,
    'downlink': downlink,
    'downlink_progress': downlink_progress,
    'delivered_at_min': delivered_at_min == null ? null : delivered_at_min!,
  };
}

/// One task in simulator seconds from T0.
class TaskWindow {
  const TaskWindow({
    required this.task_id,
    required this.start_s,
    required this.end_s,
    required this.added_load_w,
  });

  final String task_id;
  final int start_s;
  final int end_s;
  final double added_load_w;

  factory TaskWindow.fromJson(Map<String, dynamic> json) => TaskWindow(
    task_id: json['task_id'] as String,
    start_s: json['start_s'] as int,
    end_s: json['end_s'] as int,
    added_load_w: (json['added_load_w'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'task_id': task_id,
    'start_s': start_s,
    'end_s': end_s,
    'added_load_w': added_load_w,
  };
}

/// Fly one plan of the wildfire mission.
class ViewerMissionRunRequest {
  const ViewerMissionRunRequest({
    required this.plan,
    this.proposal_id,
    this.watch,
  });

  final String plan;
  final String? proposal_id;
  final bool? watch;

  factory ViewerMissionRunRequest.fromJson(Map<String, dynamic> json) => ViewerMissionRunRequest(
    plan: json['plan'] as String,
    proposal_id: json['proposal_id'] == null ? null : json['proposal_id'] as String,
    watch: (json['watch'] ?? false) == null ? null : (json['watch'] ?? false) as bool,
  );

  Map<String, dynamic> toJson() => {
    'plan': plan,
    if (proposal_id != null) 'proposal_id': proposal_id == null ? null : proposal_id!,
    if (watch != null) 'watch': watch!,
  };
}
