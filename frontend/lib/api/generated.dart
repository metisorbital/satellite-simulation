// Generated from Pydantic v2 contracts. Do not edit by hand.
// dart format off
// Regenerate: uv run python scripts/generate_contracts.py
// ignore_for_file: non_constant_identifier_names, unnecessary_non_null_assertion, prefer_null_aware_operators, use_null_aware_elements

/// One allowlisted channel value and its measurement quality.
class ChannelReading {
  const ChannelReading({
    required this.value,
    required this.quality,
  });

  final Object? value;
  final String quality;

  factory ChannelReading.fromJson(Map<String, dynamic> json) => ChannelReading(
    value: json['value'] == null ? null : json['value'] as Object,
    quality: json['quality'] as String,
  );

  Map<String, dynamic> toJson() => {
    'value': value,
    'quality': quality,
  };
}

/// A run command; speed is meaningful only for ``set_speed``.
class ControlRequest {
  const ControlRequest({
    required this.action,
    this.speed,
  });

  final String action;
  final int? speed;

  factory ControlRequest.fromJson(Map<String, dynamic> json) => ControlRequest(
    action: json['action'] as String,
    speed: json['speed'] == null ? null : json['speed'] as int,
  );

  Map<String, dynamic> toJson() => {
    'action': action,
    if (speed != null) 'speed': speed == null ? null : speed!,
  };
}

/// Allowlisted observed public SOC limit transition details.
class LowEnergyLimitDetails {
  const LowEnergyLimitDetails({
    required this.channel_id,
    required this.operator,
    required this.value,
    required this.clear_value,
  });

  final String channel_id;
  final String operator;
  final double value;
  final double clear_value;

  factory LowEnergyLimitDetails.fromJson(Map<String, dynamic> json) => LowEnergyLimitDetails(
    channel_id: json['channel_id'] as String,
    operator: json['operator'] as String,
    value: (json['value'] as num).toDouble(),
    clear_value: (json['clear_value'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'channel_id': channel_id,
    'operator': operator,
    'value': value,
    'clear_value': clear_value,
  };
}

/// Allowlisted producer-neutral telemetry measurement frame.
class MeasurementFrame {
  const MeasurementFrame({
    required this.schema_version,
    required this.source_id,
    required this.stream_id,
    required this.sequence,
    required this.satellite_id,
    required this.source_kind,
    required this.time_domain,
    required this.observed_at,
    required this.sample_window_s,
    required this.emitted_at,
    required this.catalog_version,
    required this.mode,
    required this.interval_mode,
    required this.channels,
  });

  final String schema_version;
  final String source_id;
  final String stream_id;
  final int sequence;
  final String satellite_id;
  final String source_kind;
  final String time_domain;
  final String observed_at;
  final double sample_window_s;
  final String emitted_at;
  final String catalog_version;
  final String mode;
  final String? interval_mode;
  final Map<String, ChannelReading> channels;

  factory MeasurementFrame.fromJson(Map<String, dynamic> json) => MeasurementFrame(
    schema_version: json['schema_version'] as String,
    source_id: json['source_id'] as String,
    stream_id: json['stream_id'] as String,
    sequence: json['sequence'] as int,
    satellite_id: json['satellite_id'] as String,
    source_kind: json['source_kind'] as String,
    time_domain: json['time_domain'] as String,
    observed_at: json['observed_at'] as String,
    sample_window_s: (json['sample_window_s'] as num).toDouble(),
    emitted_at: json['emitted_at'] as String,
    catalog_version: json['catalog_version'] as String,
    mode: json['mode'] as String,
    interval_mode: json['interval_mode'] == null ? null : json['interval_mode'] as String,
    channels: (json['channels'] as Map<String, dynamic>).map((key, item) => MapEntry(key, ChannelReading.fromJson(Map<String, dynamic>.from(item as Map)))),
  );

  Map<String, dynamic> toJson() => {
    'schema_version': schema_version,
    'source_id': source_id,
    'stream_id': stream_id,
    'sequence': sequence,
    'satellite_id': satellite_id,
    'source_kind': source_kind,
    'time_domain': time_domain,
    'observed_at': observed_at,
    'sample_window_s': sample_window_s,
    'emitted_at': emitted_at,
    'catalog_version': catalog_version,
    'mode': mode,
    'interval_mode': interval_mode == null ? null : interval_mode!,
    'channels': channels.map((key, item) => MapEntry(key, item.toJson())),
  };
}

/// Allowlisted observed mode transition details.
class ModeChangedDetails {
  const ModeChangedDetails({
    required this.from_mode,
    required this.to_mode,
  });

  final String from_mode;
  final String to_mode;

  factory ModeChangedDetails.fromJson(Map<String, dynamic> json) => ModeChangedDetails(
    from_mode: json['from_mode'] as String,
    to_mode: json['to_mode'] as String,
  );

  Map<String, dynamic> toJson() => {
    'from_mode': from_mode,
    'to_mode': to_mode,
  };
}

/// Allowlisted observable operational event envelope.
class OperationalEvent {
  const OperationalEvent({
    required this.schema_version,
    required this.source_id,
    required this.stream_id,
    required this.event_sequence,
    required this.satellite_id,
    required this.source_kind,
    required this.time_domain,
    required this.observed_at,
    required this.emitted_at,
    required this.event_type,
    required this.reason_code,
    required this.details,
  });

  final String schema_version;
  final String source_id;
  final String stream_id;
  final int event_sequence;
  final String satellite_id;
  final String source_kind;
  final String time_domain;
  final String observed_at;
  final String emitted_at;
  final String event_type;
  final String reason_code;
  final Object details;

  factory OperationalEvent.fromJson(Map<String, dynamic> json) => OperationalEvent(
    schema_version: json['schema_version'] as String,
    source_id: json['source_id'] as String,
    stream_id: json['stream_id'] as String,
    event_sequence: json['event_sequence'] as int,
    satellite_id: json['satellite_id'] as String,
    source_kind: json['source_kind'] as String,
    time_domain: json['time_domain'] as String,
    observed_at: json['observed_at'] as String,
    emitted_at: json['emitted_at'] as String,
    event_type: json['event_type'] as String,
    reason_code: json['reason_code'] as String,
    details: json['details'] as Object,
  );

  Map<String, dynamic> toJson() => {
    'schema_version': schema_version,
    'source_id': source_id,
    'stream_id': stream_id,
    'event_sequence': event_sequence,
    'satellite_id': satellite_id,
    'source_kind': source_kind,
    'time_domain': time_domain,
    'observed_at': observed_at,
    'emitted_at': emitted_at,
    'event_type': event_type,
    'reason_code': reason_code,
    'details': details,
  };
}

/// One authoritative Earth-fixed orbit state without predicted health.
class OrbitPoint {
  const OrbitPoint({
    required this.elapsed_s,
    required this.observed_at,
    required this.position_itrs_m,
    required this.velocity_itrs_m_s,
  });

  final int elapsed_s;
  final String observed_at;
  final List<double> position_itrs_m;
  final List<double> velocity_itrs_m_s;

  factory OrbitPoint.fromJson(Map<String, dynamic> json) => OrbitPoint(
    elapsed_s: json['elapsed_s'] as int,
    observed_at: json['observed_at'] as String,
    position_itrs_m: (json['position_itrs_m'] as List).map((item) => (item as num).toDouble()).toList(),
    velocity_itrs_m_s: (json['velocity_itrs_m_s'] as List).map((item) => (item as num).toDouble()).toList(),
  );

  Map<String, dynamic> toJson() => {
    'elapsed_s': elapsed_s,
    'observed_at': observed_at,
    'position_itrs_m': position_itrs_m.map((item) => item).toList(),
    'velocity_itrs_m_s': velocity_itrs_m_s.map((item) => item).toList(),
  };
}

/// Allowlisted observed unserved-power state details.
class PowerUnservedDetails {
  const PowerUnservedDetails({
    required this.active,
    required this.value_w,
    required this.sample_window_s,
  });

  final bool active;
  final double value_w;
  final double sample_window_s;

  factory PowerUnservedDetails.fromJson(Map<String, dynamic> json) => PowerUnservedDetails(
    active: json['active'] as bool,
    value_w: (json['value_w'] as num).toDouble(),
    sample_window_s: (json['sample_window_s'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'active': active,
    'value_w': value_w,
    'sample_window_s': sample_window_s,
  };
}

/// A disclosed operational limit with hysteresis.
class PublicLimit {
  const PublicLimit({
    required this.channel_id,
    required this.operator,
    required this.value,
    required this.clear_value,
  });

  final String channel_id;
  final String operator;
  final double value;
  final double clear_value;

  factory PublicLimit.fromJson(Map<String, dynamic> json) => PublicLimit(
    channel_id: json['channel_id'] as String,
    operator: json['operator'] as String,
    value: (json['value'] as num).toDouble(),
    clear_value: (json['clear_value'] as num).toDouble(),
  );

  Map<String, dynamic> toJson() => {
    'channel_id': channel_id,
    'operator': operator,
    'value': value,
    'clear_value': clear_value,
  };
}

/// Allowlisted public model and Earth-orientation provenance.
class PublicModelProvenance {
  const PublicModelProvenance({
    this.frame,
    this.inertial_frame,
    this.earth_orientation_source,
    this.iers_sha256,
    this.leap_seconds_sha256,
    this.iers_first_mjd,
    this.iers_last_mjd,
    this.iers_values,
    this.leap_seconds_expiry,
    this.coverage_validated,
    this.network_updates,
    this.time_advance_scale,
    this.astropy_version,
    this.astropy_iers_data_version,
    this.erfa_version,
    this.numpy_version,
    this.earth_model,
    this.orbit_model,
    this.integrator,
    this.midpoint_model,
    this.sun_model,
    this.eclipse_model,
    this.panel_model,
    this.force_model_limits,
    this.eps_model_limits,
    this.accuracy_claim,
  });

  final String? frame;
  final String? inertial_frame;
  final String? earth_orientation_source;
  final String? iers_sha256;
  final String? leap_seconds_sha256;
  final double? iers_first_mjd;
  final double? iers_last_mjd;
  final String? iers_values;
  final String? leap_seconds_expiry;
  final bool? coverage_validated;
  final bool? network_updates;
  final String? time_advance_scale;
  final String? astropy_version;
  final String? astropy_iers_data_version;
  final String? erfa_version;
  final String? numpy_version;
  final String? earth_model;
  final String? orbit_model;
  final String? integrator;
  final String? midpoint_model;
  final String? sun_model;
  final String? eclipse_model;
  final String? panel_model;
  final String? force_model_limits;
  final String? eps_model_limits;
  final String? accuracy_claim;

  factory PublicModelProvenance.fromJson(Map<String, dynamic> json) => PublicModelProvenance(
    frame: json['frame'] == null ? null : json['frame'] as String,
    inertial_frame: json['inertial_frame'] == null ? null : json['inertial_frame'] as String,
    earth_orientation_source: json['earth_orientation_source'] == null ? null : json['earth_orientation_source'] as String,
    iers_sha256: json['iers_sha256'] == null ? null : json['iers_sha256'] as String,
    leap_seconds_sha256: json['leap_seconds_sha256'] == null ? null : json['leap_seconds_sha256'] as String,
    iers_first_mjd: json['iers_first_mjd'] == null ? null : (json['iers_first_mjd'] as num).toDouble(),
    iers_last_mjd: json['iers_last_mjd'] == null ? null : (json['iers_last_mjd'] as num).toDouble(),
    iers_values: json['iers_values'] == null ? null : json['iers_values'] as String,
    leap_seconds_expiry: json['leap_seconds_expiry'] == null ? null : json['leap_seconds_expiry'] as String,
    coverage_validated: json['coverage_validated'] == null ? null : json['coverage_validated'] as bool,
    network_updates: json['network_updates'] == null ? null : json['network_updates'] as bool,
    time_advance_scale: json['time_advance_scale'] == null ? null : json['time_advance_scale'] as String,
    astropy_version: json['astropy_version'] == null ? null : json['astropy_version'] as String,
    astropy_iers_data_version: json['astropy_iers_data_version'] == null ? null : json['astropy_iers_data_version'] as String,
    erfa_version: json['erfa_version'] == null ? null : json['erfa_version'] as String,
    numpy_version: json['numpy_version'] == null ? null : json['numpy_version'] as String,
    earth_model: json['earth_model'] == null ? null : json['earth_model'] as String,
    orbit_model: json['orbit_model'] == null ? null : json['orbit_model'] as String,
    integrator: json['integrator'] == null ? null : json['integrator'] as String,
    midpoint_model: json['midpoint_model'] == null ? null : json['midpoint_model'] as String,
    sun_model: json['sun_model'] == null ? null : json['sun_model'] as String,
    eclipse_model: json['eclipse_model'] == null ? null : json['eclipse_model'] as String,
    panel_model: json['panel_model'] == null ? null : json['panel_model'] as String,
    force_model_limits: json['force_model_limits'] == null ? null : json['force_model_limits'] as String,
    eps_model_limits: json['eps_model_limits'] == null ? null : json['eps_model_limits'] as String,
    accuracy_claim: json['accuracy_claim'] == null ? null : json['accuracy_claim'] as String,
  );

  Map<String, dynamic> toJson() => {
    if (frame != null) 'frame': frame!,
    if (inertial_frame != null) 'inertial_frame': inertial_frame!,
    if (earth_orientation_source != null) 'earth_orientation_source': earth_orientation_source!,
    if (iers_sha256 != null) 'iers_sha256': iers_sha256!,
    if (leap_seconds_sha256 != null) 'leap_seconds_sha256': leap_seconds_sha256!,
    if (iers_first_mjd != null) 'iers_first_mjd': iers_first_mjd!,
    if (iers_last_mjd != null) 'iers_last_mjd': iers_last_mjd!,
    if (iers_values != null) 'iers_values': iers_values!,
    if (leap_seconds_expiry != null) 'leap_seconds_expiry': leap_seconds_expiry!,
    if (coverage_validated != null) 'coverage_validated': coverage_validated!,
    if (network_updates != null) 'network_updates': network_updates!,
    if (time_advance_scale != null) 'time_advance_scale': time_advance_scale!,
    if (astropy_version != null) 'astropy_version': astropy_version!,
    if (astropy_iers_data_version != null) 'astropy_iers_data_version': astropy_iers_data_version!,
    if (erfa_version != null) 'erfa_version': erfa_version!,
    if (numpy_version != null) 'numpy_version': numpy_version!,
    if (earth_model != null) 'earth_model': earth_model!,
    if (orbit_model != null) 'orbit_model': orbit_model!,
    if (integrator != null) 'integrator': integrator!,
    if (midpoint_model != null) 'midpoint_model': midpoint_model!,
    if (sun_model != null) 'sun_model': sun_model!,
    if (eclipse_model != null) 'eclipse_model': eclipse_model!,
    if (panel_model != null) 'panel_model': panel_model!,
    if (force_model_limits != null) 'force_model_limits': force_model_limits!,
    if (eps_model_limits != null) 'eps_model_limits': eps_model_limits!,
    if (accuracy_claim != null) 'accuracy_claim': accuracy_claim!,
  };
}

/// Committed run status containing no configuration or scenario identity.
class PublicRunStatus {
  const PublicRunStatus({
    required this.run_id,
    required this.status,
    required this.epoch_utc,
    required this.duration_s,
    required this.committed_tick,
    required this.status_revision,
    required this.committed_at,
    required this.requested_speed,
    required this.effective_speed,
    required this.wall_lag_s,
    required this.satellites,
    required this.source_kind,
    required this.model_provenance,
    required this.frame_count,
    required this.diagnostic,
  });

  final String run_id;
  final String status;
  final String epoch_utc;
  final int duration_s;
  final int committed_tick;
  final int status_revision;
  final String? committed_at;
  final int requested_speed;
  final double effective_speed;
  final double wall_lag_s;
  final List<PublicSpacecraft> satellites;
  final String source_kind;
  final PublicModelProvenance model_provenance;
  final int frame_count;
  final String? diagnostic;

  factory PublicRunStatus.fromJson(Map<String, dynamic> json) => PublicRunStatus(
    run_id: json['run_id'] as String,
    status: json['status'] as String,
    epoch_utc: json['epoch_utc'] as String,
    duration_s: json['duration_s'] as int,
    committed_tick: json['committed_tick'] as int,
    status_revision: json['status_revision'] as int,
    committed_at: json['committed_at'] == null ? null : json['committed_at'] as String,
    requested_speed: json['requested_speed'] as int,
    effective_speed: (json['effective_speed'] as num).toDouble(),
    wall_lag_s: (json['wall_lag_s'] as num).toDouble(),
    satellites: (json['satellites'] as List).map((item) => PublicSpacecraft.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    source_kind: json['source_kind'] as String,
    model_provenance: PublicModelProvenance.fromJson(Map<String, dynamic>.from(json['model_provenance'] as Map)),
    frame_count: json['frame_count'] as int,
    diagnostic: json['diagnostic'] == null ? null : json['diagnostic'] as String,
  );

  Map<String, dynamic> toJson() => {
    'run_id': run_id,
    'status': status,
    'epoch_utc': epoch_utc,
    'duration_s': duration_s,
    'committed_tick': committed_tick,
    'status_revision': status_revision,
    'committed_at': committed_at == null ? null : committed_at!,
    'requested_speed': requested_speed,
    'effective_speed': effective_speed,
    'wall_lag_s': wall_lag_s,
    'satellites': satellites.map((item) => item.toJson()).toList(),
    'source_kind': source_kind,
    'model_provenance': model_provenance.toJson(),
    'frame_count': frame_count,
    'diagnostic': diagnostic == null ? null : diagnostic!,
  };
}

/// Public nameplate and display properties of one spacecraft.
class PublicSpacecraft {
  const PublicSpacecraft({
    required this.satellite_id,
    required this.name,
    required this.color,
    required this.stream_id,
    required this.capacity_wh,
    required this.panel_area_m2,
    required this.public_limits,
  });

  final String satellite_id;
  final String name;
  final String color;
  final String stream_id;
  final double capacity_wh;
  final double panel_area_m2;
  final List<PublicLimit> public_limits;

  factory PublicSpacecraft.fromJson(Map<String, dynamic> json) => PublicSpacecraft(
    satellite_id: json['satellite_id'] as String,
    name: json['name'] as String,
    color: json['color'] as String,
    stream_id: json['stream_id'] as String,
    capacity_wh: (json['capacity_wh'] as num).toDouble(),
    panel_area_m2: (json['panel_area_m2'] as num).toDouble(),
    public_limits: (json['public_limits'] as List).map((item) => PublicLimit.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'satellite_id': satellite_id,
    'name': name,
    'color': color,
    'stream_id': stream_id,
    'capacity_wh': capacity_wh,
    'panel_area_m2': panel_area_m2,
    'public_limits': public_limits.map((item) => item.toJson()).toList(),
  };
}

/// Orbit samples for one spacecraft.
class SatelliteTrajectory {
  const SatelliteTrajectory({
    required this.satellite_id,
    required this.samples,
  });

  final String satellite_id;
  final List<OrbitPoint> samples;

  factory SatelliteTrajectory.fromJson(Map<String, dynamic> json) => SatelliteTrajectory(
    satellite_id: json['satellite_id'] as String,
    samples: (json['samples'] as List).map((item) => OrbitPoint.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'satellite_id': satellite_id,
    'samples': samples.map((item) => item.toJson()).toList(),
  };
}

/// A delivered stream's inclusive sequence bounds.
class SequenceRange {
  const SequenceRange({
    required this.stream_id,
    required this.first,
    required this.last,
  });

  final String stream_id;
  final int first;
  final int last;

  factory SequenceRange.fromJson(Map<String, dynamic> json) => SequenceRange(
    stream_id: json['stream_id'] as String,
    first: json['first'] as int,
    last: json['last'] as int,
  );

  Map<String, dynamic> toJson() => {
    'stream_id': stream_id,
    'first': first,
    'last': last,
  };
}

/// A consistent committed status and bounded measurement history.
class Snapshot {
  const Snapshot({
    required this.status,
    required this.frames,
  });

  final PublicRunStatus status;
  final List<MeasurementFrame> frames;

  factory Snapshot.fromJson(Map<String, dynamic> json) => Snapshot(
    status: PublicRunStatus.fromJson(Map<String, dynamic>.from(json['status'] as Map)),
    frames: (json['frames'] as List).map((item) => MeasurementFrame.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'status': status.toJson(),
    'frames': frames.map((item) => item.toJson()).toList(),
  };
}

/// Bounded orbit-only prediction with explicit coordinates.
class Trajectory {
  const Trajectory({
    required this.run_id,
    required this.kind,
    required this.frame,
    required this.satellites,
  });

  final String run_id;
  final String kind;
  final String frame;
  final List<SatelliteTrajectory> satellites;

  factory Trajectory.fromJson(Map<String, dynamic> json) => Trajectory(
    run_id: json['run_id'] as String,
    kind: json['kind'] as String,
    frame: json['frame'] as String,
    satellites: (json['satellites'] as List).map((item) => SatelliteTrajectory.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
  );

  Map<String, dynamic> toJson() => {
    'run_id': run_id,
    'kind': kind,
    'frame': frame,
    'satellites': satellites.map((item) => item.toJson()).toList(),
  };
}

/// One prepared run and session-bound CSRF token for the browser.
class ViewerBootstrap {
  const ViewerBootstrap({
    required this.csrf_token,
    required this.allowed_actions,
    required this.run,
    required this.operator,
  });

  final String csrf_token;
  final List<String> allowed_actions;
  final PublicRunStatus run;
  final ViewerOperator? operator;

  factory ViewerBootstrap.fromJson(Map<String, dynamic> json) => ViewerBootstrap(
    csrf_token: json['csrf_token'] as String,
    allowed_actions: (json['allowed_actions'] as List).map((item) => item as String).toList(),
    run: PublicRunStatus.fromJson(Map<String, dynamic>.from(json['run'] as Map)),
    operator: json['operator'] == null ? null : ViewerOperator.fromJson(Map<String, dynamic>.from(json['operator'] as Map)),
  );

  Map<String, dynamic> toJson() => {
    'csrf_token': csrf_token,
    'allowed_actions': allowed_actions.map((item) => item).toList(),
    'run': run.toJson(),
    'operator': operator == null ? null : operator!.toJson(),
  };
}

/// Mock operator identity disclosed only to its own browser session.
class ViewerOperator {
  const ViewerOperator({
    required this.user_id,
    required this.login,
    required this.display_name,
  });

  final String user_id;
  final String login;
  final String display_name;

  factory ViewerOperator.fromJson(Map<String, dynamic> json) => ViewerOperator(
    user_id: json['user_id'] as String,
    login: json['login'] as String,
    display_name: json['display_name'] as String,
  );

  Map<String, dynamic> toJson() => {
    'user_id': user_id,
    'login': login,
    'display_name': display_name,
  };
}

/// Bounded public presentation transport; never a durable consumer offset.
class VisualMessage {
  const VisualMessage({
    required this.visual_schema_version,
    required this.type,
    required this.sent_at,
    required this.run_id,
    required this.status,
    required this.frames,
    required this.ranges,
    required this.message,
  });

  final String visual_schema_version;
  final String type;
  final String sent_at;
  final String run_id;
  final PublicRunStatus? status;
  final List<MeasurementFrame> frames;
  final List<SequenceRange> ranges;
  final String? message;

  factory VisualMessage.fromJson(Map<String, dynamic> json) => VisualMessage(
    visual_schema_version: json['visual_schema_version'] as String,
    type: json['type'] as String,
    sent_at: json['sent_at'] as String,
    run_id: json['run_id'] as String,
    status: json['status'] == null ? null : PublicRunStatus.fromJson(Map<String, dynamic>.from(json['status'] as Map)),
    frames: (json['frames'] as List).map((item) => MeasurementFrame.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    ranges: (json['ranges'] as List).map((item) => SequenceRange.fromJson(Map<String, dynamic>.from(item as Map))).toList(),
    message: json['message'] == null ? null : json['message'] as String,
  );

  Map<String, dynamic> toJson() => {
    'visual_schema_version': visual_schema_version,
    'type': type,
    'sent_at': sent_at,
    'run_id': run_id,
    'status': status == null ? null : status!.toJson(),
    'frames': frames.map((item) => item.toJson()).toList(),
    'ranges': ranges.map((item) => item.toJson()).toList(),
    'message': message == null ? null : message!,
  };
}
