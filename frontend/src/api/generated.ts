/* Generated from Pydantic v2 contracts. Do not edit by hand. */

export type Quality = "valid" | "missing" | "invalid" | "saturated";
export type Value = number | [number, number, number] | null;
export type Action = "start" | "pause" | "resume" | "stop" | "set_speed";
export type Speed = (1 | 5 | 20) | null;
export type CatalogVersion = "power-leo.v1";
export type EmittedAt = string;
export type IntervalMode = ("nominal" | "payload_active" | "safe") | null;
export type Mode = "nominal" | "payload_active" | "safe";
export type ObservedAt = string;
export type SampleWindowS = number;
export type SatelliteId = string;
export type SchemaVersion = "telemetry.v1";
export type Sequence = number;
export type SourceId = string;
export type SourceKind = "synthetic" | "observed";
export type StreamId = string;
export type TimeDomain = "simulation_utc" | "mission_utc";
export type Details = ModeChangedDetails | LowEnergyLimitDetails | PowerUnservedDetails;
export type FromMode = "nominal" | "payload_active" | "safe";
export type ToMode = "nominal" | "payload_active" | "safe";
export type ChannelId = "eps.battery_soc";
export type ClearValue = number;
export type Operator = "lt" | "gt";
export type Value1 = number;
export type Active = boolean;
export type SampleWindowS1 = number;
export type ValueW = number;
export type EmittedAt1 = string;
export type EventSequence = number;
export type EventType = "mode_changed" | "low_energy_limit_entered" | "low_energy_limit_cleared" | "power_unserved";
export type ObservedAt1 = string;
export type ReasonCode = string;
export type SatelliteId1 = string;
export type SchemaVersion1 = "operational_event.v1";
export type SourceId1 = string;
export type SourceKind1 = "synthetic" | "observed";
export type StreamId1 = string;
export type TimeDomain1 = "simulation_utc" | "mission_utc";
export type ElapsedS = number;
export type ObservedAt2 = string;
/**
 * @minItems 3
 * @maxItems 3
 */
export type PositionItrsM = [number, number, number];
/**
 * @minItems 3
 * @maxItems 3
 */
export type VelocityItrsMS = [number, number, number];
export type ChannelId1 = "eps.battery_soc";
export type ClearValue1 = number;
export type Operator1 = "lt" | "gt";
export type Value2 = number;
export type CommittedAt = string | null;
export type CommittedTick = number;
export type Diagnostic = string | null;
export type DurationS = number;
export type EffectiveSpeed = number;
export type EpochUtc = string;
export type FrameCount = number;
export type AccuracyClaim = string;
export type AstropyIersDataVersion = string;
export type AstropyVersion = string;
export type CoverageValidated = boolean;
export type EarthModel = string;
export type EarthOrientationSource = string;
export type EclipseModel = string;
export type EpsModelLimits = string;
export type ErfaVersion = string;
export type ForceModelLimits = string;
export type Frame = string;
export type IersFirstMjd = number;
export type IersLastMjd = number;
export type IersSha256 = string;
export type IersValues = "observed" | "predicted";
export type InertialFrame = string;
export type Integrator = string;
export type LeapSecondsExpiry = string;
export type LeapSecondsSha256 = string;
export type MidpointModel = string;
export type NetworkUpdates = boolean;
export type NumpyVersion = string;
export type OrbitModel = string;
export type PanelModel = string;
export type SunModel = string;
export type TimeAdvanceScale = string;
export type RequestedSpeed = 1 | 5 | 20;
export type RunId = string;
export type CapacityWh = number;
export type Color = string;
export type Name = string;
export type PanelAreaM2 = number;
export type PublicLimits = PublicLimit[];
export type SatelliteId2 = string;
export type StreamId2 = string;
export type Satellites = PublicSpacecraft[];
export type SourceKind2 = "synthetic";
export type Status = "created" | "running" | "paused" | "completed" | "stopped" | "failed" | "aborted";
export type StatusRevision = number;
export type WallLagS = number;
export type Samples = OrbitPoint[];
export type SatelliteId3 = string;
export type First = number;
export type Last = number;
export type StreamId3 = string;
export type ConstellationId = string;
export type SatelliteIds = string[];
export type Constellations = ConstellationDefinition[];
export type ChargeEfficiency = number;
export type DischargeEfficiency = number;
export type InitialSoc = number;
export type MaxChargeW = number;
export type MaxDischargeW = number;
export type Type = "energy_store";
export type UsableCapacityWh = number;
export type AreaM2 = number;
export type ConversionEfficiency = number;
export type Efficiency = number;
export type Irradiance1AuWM2 = number;
export type Type1 = "ideal_sun_tracking";
export type ChannelId2 = "eps.battery_soc";
export type ClearValue2 = number;
export type Operator2 = "lt" | "gt";
export type Value3 = number;
export type PublicLimits1 = ConfiguredPublicLimit[];
export type Catalog = "power-leo.v1";
export type Type2 = "none";
export type DurationS1 = number;
export type EarthModel1 = "wgs84_j2_v1";
export type EpochUtc1 = string;
export type OrbitModel1 = "j2_cartesian";
export type Seed = number;
export type Speed1 = 1 | 5 | 20;
export type SunModel1 = "astropy_builtin";
export type TelemetryPeriodS = 1;
export type TickS = 1;
export type InitialMode = "nominal" | "payload_active" | "safe";
export type Name1 = string;
export type EndS = number;
export type Mode1 = "nominal" | "payload_active" | "safe";
export type StartS = number;
export type Operations = Operation[];
export type AM = number;
export type ArgpDeg = number;
export type E = number;
export type IDeg = number;
export type RaanDeg = number;
export type TrueAnomalyDeg = number;
export type ProfileId = string;
export type SatelliteId4 = string;
export type AssetId = string | null;
export type Color1 = string;
export type Satellites1 = SatelliteDefinition[];
export type DwellS = number;
export type ReserveSoc = number;
export type Type3 = "energy_reserve_violation";
export type AtS = number;
export type Multiplier = number;
export type Points = DeratingPoint[];
export type SatelliteId5 = string;
export type Type4 = "solar_derating";
export type Scenario = SolarDeratingScenario[];
export type SchemaVersion2 = "simulation.v1";
export type Frames = MeasurementFrame[];
export type Frame1 = "ITRS";
export type Kind = "predicted_orbit";
export type RunId1 = string;
export type Satellites2 = SatelliteTrajectory[];
export type CsrfToken = string;
export type Frames1 = MeasurementFrame[];
export type Message = string | null;
export type Ranges = SequenceRange[];
export type RunId2 = string;
export type SentAt = string;
export type Type5 = "snapshot" | "samples" | "clock" | "lifecycle" | "resync_required" | "error";
export type VisualSchemaVersion = "visual.v1";

export interface MetisPublicContracts {
  ChannelReading: ChannelReading;
  ControlRequest: ControlRequest;
  MeasurementFrame: MeasurementFrame;
  OperationalEvent: OperationalEvent;
  OrbitPoint: OrbitPoint;
  PublicLimit: PublicLimit;
  PublicRunStatus: PublicRunStatus;
  PublicSpacecraft: PublicSpacecraft;
  SatelliteTrajectory: SatelliteTrajectory;
  SequenceRange: SequenceRange;
  SimulationConfig: SimulationConfig;
  Snapshot: Snapshot;
  Trajectory: Trajectory;
  ViewerBootstrap: ViewerBootstrap;
  VisualMessage: VisualMessage;
}
/**
 * One allowlisted channel value and its measurement quality.
 *
 * Attributes
 * ----------
 * value : float, tuple of float, or None
 *     Scalar or fixed three-vector reading. Failed readings use ``None``.
 * quality : {"valid", "missing", "invalid", "saturated"}
 *     Quality state that explains whether ``value`` is usable.
 *
 * Notes
 * -----
 * Valid and saturated readings require a value; missing and invalid
 * readings require ``None``.
 */
export interface ChannelReading {
  quality: Quality;
  value: Value;
}
/**
 * A run command; speed is meaningful only for ``set_speed``.
 *
 * Attributes
 * ----------
 * action : Action
 *     Lifecycle command to apply to the run.
 * speed : {1, 5, 20} or None
 *     Requested pacing multiplier for ``set_speed``; omitted otherwise.
 */
export interface ControlRequest {
  action: Action;
  speed?: Speed;
}
/**
 * Allowlisted producer-neutral telemetry measurement frame.
 *
 * Attributes
 * ----------
 * schema_version : str
 *     Breaking-contract identifier, currently ``telemetry.v1``.
 * source_id : str
 *     Stable producer identity.
 * stream_id : UUID
 *     Monotonic sequence namespace for one spacecraft stream.
 * sequence : int
 *     Zero-based stream sequence, bounded by the exact JSON integer range.
 * satellite_id : str
 *     Logical spacecraft identity.
 * source_kind : {"synthetic", "observed"}
 *     Provenance of the producer data.
 * time_domain : {"simulation_utc", "mission_utc"}
 *     Meaning of ``observed_at``.
 * observed_at, emitted_at : datetime
 *     UTC represented sample time and producer emission time.
 * sample_window_s : float
 *     Interval length ending at ``observed_at`` for interval-average
 *     channels; zero denotes the initial instantaneous frame.
 * catalog_version : str
 *     Versioned channel catalog identifier.
 * mode, interval_mode : Mode or None
 *     Endpoint mode and mode used for interval-average channels.
 * channels : mapping of str to ChannelReading
 *     Allowlisted measured or derived public channel values.
 *
 * Notes
 * -----
 * Timestamps are normalized to UTC and channel mappings are frozen after
 * validation. Private scenario parameters, seeds, and future outcomes do
 * not belong in this envelope.
 */
export interface MeasurementFrame {
  catalog_version: CatalogVersion;
  channels: Channels;
  emitted_at: EmittedAt;
  interval_mode: IntervalMode;
  mode: Mode;
  observed_at: ObservedAt;
  sample_window_s: SampleWindowS;
  satellite_id: SatelliteId;
  schema_version: SchemaVersion;
  sequence: Sequence;
  source_id: SourceId;
  source_kind: SourceKind;
  stream_id: StreamId;
  time_domain: TimeDomain;
}
export interface Channels {
  [k: string]: ChannelReading;
}
/**
 * Allowlisted observable operational event envelope.
 *
 * Attributes
 * ----------
 * schema_version : str
 *     Breaking-contract identifier, currently ``operational_event.v1``.
 * source_id : str
 *     Stable producer identity.
 * stream_id : UUID
 *     Stream namespace associated with the event.
 * event_sequence : int
 *     Monotonic sequence within the stream's event namespace.
 * satellite_id : str
 *     Logical spacecraft identity.
 * source_kind : {"synthetic", "observed"}
 *     Provenance of the producer data.
 * time_domain : {"simulation_utc", "mission_utc"}
 *     Meaning of ``observed_at``.
 * observed_at, emitted_at : datetime
 *     UTC event time and producer emission time.
 * event_type : EventType
 *     Allowlisted observable event discriminator.
 * reason_code : str
 *     Stable ASCII reason code for the event.
 * details : EventDetails
 *     Typed details matching ``event_type`` exactly.
 *
 * Notes
 * -----
 * Event details describe an observed condition or transition. Private
 * injection schedules and evaluator-only outcome labels are excluded.
 */
export interface OperationalEvent {
  details: Details;
  emitted_at: EmittedAt1;
  event_sequence: EventSequence;
  event_type: EventType;
  observed_at: ObservedAt1;
  reason_code: ReasonCode;
  satellite_id: SatelliteId1;
  schema_version: SchemaVersion1;
  source_id: SourceId1;
  source_kind: SourceKind1;
  stream_id: StreamId1;
  time_domain: TimeDomain1;
}
/**
 * Allowlisted observed mode transition details.
 *
 * Attributes
 * ----------
 * from_mode, to_mode : Mode
 *     Endpoint modes on either side of the public transition.
 */
export interface ModeChangedDetails {
  from_mode: FromMode;
  to_mode: ToMode;
}
/**
 * Allowlisted observed public SOC limit transition details.
 *
 * Attributes
 * ----------
 * channel_id : str
 *     Public SOC channel associated with the limit.
 * operator : {"lt", "gt"}
 *     Comparison used to enter or clear the limit.
 * value, clear_value : float
 *     Entry and hysteresis-clear SOC thresholds.
 */
export interface LowEnergyLimitDetails {
  channel_id: ChannelId;
  clear_value: ClearValue;
  operator: Operator;
  value: Value1;
}
/**
 * Allowlisted observed unserved-power state details.
 *
 * Attributes
 * ----------
 * active : bool
 *     Whether requested load was not fully served.
 * value_w : float
 *     Unserved requested load in watts.
 * sample_window_s : float
 *     Interval represented by the value in seconds.
 */
export interface PowerUnservedDetails {
  active: Active;
  sample_window_s: SampleWindowS1;
  value_w: ValueW;
}
/**
 * One authoritative Earth-fixed orbit state without predicted health.
 *
 * Attributes
 * ----------
 * elapsed_s : int
 *     Simulated elapsed time from the run epoch.
 * observed_at : datetime
 *     UTC timestamp represented by the state.
 * position_itrs_m : tuple of float
 *     Earth-fixed position in metres.
 * velocity_itrs_m_s : tuple of float
 *     Earth-fixed velocity in metres per second.
 */
export interface OrbitPoint {
  elapsed_s: ElapsedS;
  observed_at: ObservedAt2;
  position_itrs_m: PositionItrsM;
  velocity_itrs_m_s: VelocityItrsMS;
}
/**
 * A disclosed operational limit with hysteresis.
 *
 * Attributes
 * ----------
 * channel_id : str
 *     Public channel monitored by this limit.
 * operator : {"lt", "gt"}
 *     Comparison used to enter the limit.
 * value, clear_value : float
 *     Entry and clear thresholds exposed to a viewer or consumer.
 */
export interface PublicLimit {
  channel_id: ChannelId1;
  clear_value: ClearValue1;
  operator: Operator1;
  value: Value2;
}
/**
 * Committed run status containing no configuration or scenario identity.
 *
 * Attributes
 * ----------
 * run_id : str
 *     Identifier for this execution.
 * status : RunState
 *     Public lifecycle state.
 * epoch_utc : datetime
 *     Run start epoch in UTC.
 * duration_s : int
 *     Configured simulated duration.
 * committed_tick : int
 *     Latest durably committed simulated second, or ``-1`` before the
 *     first commit.
 * status_revision : int
 *     Monotonic status revision used to order same-tick responses.
 * committed_at : datetime or None
 *     Simulation UTC timestamp of the latest committed sample; ``None``
 *     before the first sample.
 * requested_speed, effective_speed : float or int
 *     Requested pacing multiplier and measured effective multiplier.
 * wall_lag_s : float
 *     Difference between requested simulated progress and wall pacing.
 * satellites : list of PublicSpacecraft
 *     Public spacecraft descriptors and stream identities.
 * source_kind : str
 *     Provenance label; P0 runs are ``synthetic``.
 * model_provenance : PublicModelProvenance
 *     Allowlisted model and Earth-orientation metadata.
 * frame_count : int
 *     Number of committed public frames.
 * diagnostic : str or None
 *     Safe terminal or health diagnostic, when present.
 *
 * Notes
 * -----
 * Seeds, scenario parameters, private manifests, and future outcome labels
 * are intentionally excluded from this projection.
 */
export interface PublicRunStatus {
  committed_at: CommittedAt;
  committed_tick: CommittedTick;
  diagnostic: Diagnostic;
  duration_s: DurationS;
  effective_speed: EffectiveSpeed;
  epoch_utc: EpochUtc;
  frame_count: FrameCount;
  model_provenance: PublicModelProvenance;
  requested_speed: RequestedSpeed;
  run_id: RunId;
  satellites: Satellites;
  source_kind: SourceKind2;
  status: Status;
  status_revision: StatusRevision;
  wall_lag_s: WallLagS;
}
/**
 * Allowlisted public model and Earth-orientation provenance.
 *
 * Notes
 * -----
 * Fields may be absent when the producer has not supplied that metadata.
 * Unknown fields are rejected so private manifest parameters cannot cross
 * the public response boundary through an unrestricted metadata mapping.
 */
export interface PublicModelProvenance {
  accuracy_claim?: AccuracyClaim;
  astropy_iers_data_version?: AstropyIersDataVersion;
  astropy_version?: AstropyVersion;
  coverage_validated?: CoverageValidated;
  earth_model?: EarthModel;
  earth_orientation_source?: EarthOrientationSource;
  eclipse_model?: EclipseModel;
  eps_model_limits?: EpsModelLimits;
  erfa_version?: ErfaVersion;
  force_model_limits?: ForceModelLimits;
  frame?: Frame;
  iers_first_mjd?: IersFirstMjd;
  iers_last_mjd?: IersLastMjd;
  iers_sha256?: IersSha256;
  iers_values?: IersValues;
  inertial_frame?: InertialFrame;
  integrator?: Integrator;
  leap_seconds_expiry?: LeapSecondsExpiry;
  leap_seconds_sha256?: LeapSecondsSha256;
  midpoint_model?: MidpointModel;
  network_updates?: NetworkUpdates;
  numpy_version?: NumpyVersion;
  orbit_model?: OrbitModel;
  panel_model?: PanelModel;
  sun_model?: SunModel;
  time_advance_scale?: TimeAdvanceScale;
}
/**
 * Public nameplate and display properties of one spacecraft.
 *
 * Attributes
 * ----------
 * satellite_id : str
 *     Stable spacecraft identity.
 * name, color : str
 *     Human-readable label and viewer marker color.
 * stream_id : str
 *     Durable public telemetry stream identity.
 * capacity_wh, panel_area_m2 : float
 *     Disclosed battery capacity and panel area.
 * public_limits : list of PublicLimit
 *     Configured limits safe to disclose to consumers.
 */
export interface PublicSpacecraft {
  capacity_wh: CapacityWh;
  color: Color;
  name: Name;
  panel_area_m2: PanelAreaM2;
  public_limits: PublicLimits;
  satellite_id: SatelliteId2;
  stream_id: StreamId2;
}
/**
 * Orbit samples for one spacecraft.
 *
 * Attributes
 * ----------
 * satellite_id : str
 *     Spacecraft identity.
 * samples : list of OrbitPoint
 *     Ordered Earth-fixed orbit samples.
 */
export interface SatelliteTrajectory {
  samples: Samples;
  satellite_id: SatelliteId3;
}
/**
 * A delivered stream's inclusive sequence bounds.
 *
 * Attributes
 * ----------
 * stream_id : str
 *     Public stream identity.
 * first, last : int
 *     Inclusive sequence numbers represented by a delivery batch.
 */
export interface SequenceRange {
  first: First;
  last: Last;
  stream_id: StreamId3;
}
/**
 * Complete validated P0 simulation input configuration.
 *
 * Attributes
 * ----------
 * schema_version : str
 *     Configuration contract revision, currently ``simulation.v1``.
 * run : RunConfiguration
 *     Timing, seed, and selected model versions.
 * profiles : mapping of str to SpacecraftProfile
 *     Reusable spacecraft subsystem definitions.
 * satellites : tuple of SatelliteDefinition
 *     One to ten configured spacecraft.
 * constellations : tuple of ConstellationDefinition
 *     Optional display groupings with validated membership.
 * scenario : tuple of SolarDeratingScenario
 *     Zero or one private P0 derating scenario.
 *
 * Notes
 * -----
 * Cross-object references and nested mappings are validated and frozen
 * before the configuration is normalized or hashed.
 */
export interface SimulationConfig {
  constellations: Constellations;
  profiles: Profiles;
  run: RunConfiguration;
  satellites: Satellites1;
  scenario: Scenario;
  schema_version: SchemaVersion2;
}
/**
 * Display grouping containing unique satellite identities.
 *
 * Attributes
 * ----------
 * constellation_id : str
 *     Stable grouping identifier.
 * satellite_ids : tuple of str
 *     Unique member IDs retained in display order.
 */
export interface ConstellationDefinition {
  constellation_id: ConstellationId;
  satellite_ids: SatelliteIds;
}
export interface Profiles {
  [k: string]: SpacecraftProfile;
}
/**
 * Reusable spacecraft subsystem configuration.
 *
 * Attributes
 * ----------
 * panel : PanelConfiguration
 *     Equivalent solar-array model.
 * battery : BatteryConfiguration
 *     Bounded energy-store model.
 * loads_w : mapping
 *     Requested load in watts for every supported satellite mode.
 * sensors : SensorConfiguration
 *     Public channel catalog and sensor policy.
 * public_limits : tuple of ConfiguredPublicLimit
 *     Limits that may appear in the public spacecraft descriptor.
 */
export interface SpacecraftProfile {
  battery: BatteryConfiguration;
  loads_w: LoadsW;
  panel: PanelConfiguration;
  public_limits?: PublicLimits1;
  sensors: SensorConfiguration;
}
/**
 * Ideal bounded energy-store nameplate and starting condition.
 *
 * Attributes
 * ----------
 * type : str
 *     P0 battery model, currently ``energy_store``.
 * usable_capacity_wh : float
 *     Fixed usable energy capacity in watt-hours.
 * initial_soc : float
 *     Initial state of charge as a fraction of usable capacity.
 * charge_efficiency, discharge_efficiency : float
 *     Energy conversion efficiencies in ``(0, 1]``.
 * max_charge_w, max_discharge_w : float
 *     Bus-power limits in watts.
 */
export interface BatteryConfiguration {
  charge_efficiency: ChargeEfficiency;
  discharge_efficiency: DischargeEfficiency;
  initial_soc: InitialSoc;
  max_charge_w: MaxChargeW;
  max_discharge_w: MaxDischargeW;
  type: Type;
  usable_capacity_wh: UsableCapacityWh;
}
export interface LoadsW {
  [k: string]: number;
}
/**
 * Equivalent solar-array nameplate and conversion parameters.
 *
 * Attributes
 * ----------
 * area_m2 : float
 *     Equivalent panel area in square metres.
 * efficiency, conversion_efficiency : float
 *     Panel and bus-conversion efficiencies in ``(0, 1]``.
 * irradiance_1au_w_m2 : float
 *     Reference solar irradiance in watts per square metre.
 * pointing : PointingConfiguration
 *     Declared panel pointing policy.
 */
export interface PanelConfiguration {
  area_m2: AreaM2;
  conversion_efficiency: ConversionEfficiency;
  efficiency: Efficiency;
  irradiance_1au_w_m2: Irradiance1AuWM2;
  pointing: PointingConfiguration;
}
/**
 * Supported panel pointing policy.
 *
 * Attributes
 * ----------
 * type : str
 *     P0 panel policy, currently ``ideal_sun_tracking``.
 */
export interface PointingConfiguration {
  type: Type1;
}
/**
 * Observable SOC threshold with explicit hysteresis.
 *
 * Attributes
 * ----------
 * channel_id : str
 *     Public channel monitored by the limit, currently battery SOC.
 * operator : {"lt", "gt"}
 *     Comparison used to enter the limit.
 * value, clear_value : float
 *     Entry and hysteresis-clear thresholds as SOC fractions.
 */
export interface ConfiguredPublicLimit {
  channel_id: ChannelId2;
  clear_value: ClearValue2;
  operator: Operator2;
  value: Value3;
}
/**
 * Public channel catalog and sensor-noise policy.
 *
 * Attributes
 * ----------
 * catalog : str
 *     Versioned public channel catalog identifier.
 * noise : NoiseConfiguration
 *     Noise policy applied after the physical calculation.
 */
export interface SensorConfiguration {
  catalog: Catalog;
  noise: NoiseConfiguration;
}
/**
 * Supported sensor noise selection.
 *
 * Attributes
 * ----------
 * type : str
 *     P0 uses ``none`` so numerical evidence remains deterministic.
 */
export interface NoiseConfiguration {
  type: Type2;
}
/**
 * Simulation timing, seed, and versioned model selections.
 *
 * Attributes
 * ----------
 * epoch_utc : datetime
 *     UTC-normalized instant at which the run starts.
 * duration_s : int
 *     Configured elapsed duration in simulated seconds; samples include
 *     both tick zero and the endpoint.
 * tick_s, telemetry_period_s : int
 *     Fixed physical and telemetry cadence; both are one second in P0.
 * speed : {1, 5, 20}
 *     Requested wall-clock multiplier.
 * seed : int
 *     Reproducibility seed within JavaScript's exact integer range.
 * earth_model, orbit_model, sun_model : str
 *     Versioned model identifiers used by the run.
 */
export interface RunConfiguration {
  duration_s?: DurationS1;
  earth_model: EarthModel1;
  epoch_utc: EpochUtc1;
  orbit_model: OrbitModel1;
  seed: Seed;
  speed?: Speed1;
  sun_model: SunModel1;
  telemetry_period_s: TelemetryPeriodS;
  tick_s: TickS;
}
/**
 * Stable spacecraft identity, orbit, profile reference, and schedule.
 *
 * Attributes
 * ----------
 * satellite_id : str
 *     Stable ASCII identity used in streams and public frames.
 * name : str
 *     Human-readable spacecraft name.
 * profile_id : str
 *     Reference to a reusable :class:`SpacecraftProfile`.
 * orbit : OrbitConfiguration
 *     Initial osculating orbit.
 * initial_mode : SatelliteMode
 *     Default mode whenever no scheduled operation is active, including
 *     tick zero unless an operation starts there.
 * operations : tuple of Operation
 *     Non-overlapping scheduled mode intervals.
 * visual : VisualConfiguration
 *     Allowlisted marker metadata.
 */
export interface SatelliteDefinition {
  initial_mode: InitialMode;
  name: Name1;
  operations: Operations;
  orbit: OrbitConfiguration;
  profile_id: ProfileId;
  satellite_id: SatelliteId4;
  visual?: VisualConfiguration;
}
/**
 * Half-open scheduled operational mode interval.
 *
 * Attributes
 * ----------
 * start_s, end_s : int
 *     Simulated-second bounds of the half-open interval ``[start_s, end_s)``.
 * mode : SatelliteMode
 *     Mode active during the interval.
 */
export interface Operation {
  end_s: EndS;
  mode: Mode1;
  start_s: StartS;
}
/**
 * Osculating classical orbit elements at the run epoch.
 *
 * Attributes
 * ----------
 * a_m : float
 *     Semi-major axis in metres.
 * e : float
 *     Dimensionless eccentricity.
 * i_deg, raan_deg, argp_deg, true_anomaly_deg : float
 *     Inclination, right ascension of ascending node, argument of
 *     periapsis, and true anomaly in degrees.
 *
 * Notes
 * -----
 * The model validates the initial perigee and apogee against the supported
 * 300--1500 km P0 radial envelope.
 */
export interface OrbitConfiguration {
  a_m: AM;
  argp_deg: ArgpDeg;
  e: E;
  i_deg: IDeg;
  raan_deg: RaanDeg;
  true_anomaly_deg: TrueAnomalyDeg;
}
/**
 * Allowlisted visual marker metadata for a spacecraft.
 *
 * Attributes
 * ----------
 * color : str
 *     Six-digit hexadecimal marker color.
 * asset_id : str or None
 *     Optional identifier resolved by the allowlisted visual asset catalog.
 */
export interface VisualConfiguration {
  asset_id?: AssetId;
  color?: Color1;
}
/**
 * Private piecewise-linear solar derating scenario.
 *
 * Attributes
 * ----------
 * satellite_id : str
 *     Spacecraft affected by the scenario.
 * type : str
 *     P0 scenario type, currently ``solar_derating``.
 * points : tuple of DeratingPoint
 *     Strictly increasing multiplier control points.
 * outcome : ReserveOutcome
 *     Private state-based outcome rule.
 */
export interface SolarDeratingScenario {
  outcome: ReserveOutcome;
  points: Points;
  satellite_id: SatelliteId5;
  type: Type4;
}
/**
 * Private state-triggered operational reserve outcome rule.
 *
 * Attributes
 * ----------
 * type : str
 *     P0 outcome type, currently ``energy_reserve_violation``.
 * reserve_soc : float
 *     SOC threshold used by the private evaluator.
 * dwell_s : int
 *     Consecutive simulated seconds required below the threshold.
 */
export interface ReserveOutcome {
  dwell_s?: DwellS;
  reserve_soc: ReserveSoc;
  type: Type3;
}
/**
 * Elapsed run time and solar generation multiplier control point.
 *
 * Attributes
 * ----------
 * at_s : int
 *     Simulated-second location of the control point.
 * multiplier : float
 *     Solar-generation multiplier in ``[0, 1]``.
 */
export interface DeratingPoint {
  at_s: AtS;
  multiplier: Multiplier;
}
/**
 * A consistent committed status and bounded measurement history.
 *
 * Attributes
 * ----------
 * status : PublicRunStatus
 *     Status and committed endpoint corresponding to the history.
 * frames : list of MeasurementFrame
 *     Public frames in the bounded history window, all at or before the
 *     committed endpoint.
 */
export interface Snapshot {
  frames: Frames;
  status: PublicRunStatus;
}
/**
 * Bounded orbit-only prediction with explicit coordinates.
 *
 * Attributes
 * ----------
 * run_id : str
 *     Run whose prepared engine produced the samples.
 * kind : str
 *     Explicit ``predicted_orbit`` discriminator.
 * frame : str
 *     Coordinate frame, fixed to ``ITRS`` in P0.
 * satellites : list of SatelliteTrajectory
 *     Per-spacecraft orbit samples.
 *
 * Notes
 * -----
 * This projection contains no future electrical or health state.
 */
export interface Trajectory {
  frame: Frame1;
  kind: Kind;
  run_id: RunId1;
  satellites: Satellites2;
}
/**
 * One prepared run and session-bound CSRF token for the browser.
 *
 * Attributes
 * ----------
 * csrf_token : str
 *     Token required on browser control requests for this session.
 * run : PublicRunStatus
 *     Public status of the session's one scoped run.
 */
export interface ViewerBootstrap {
  csrf_token: CsrfToken;
  run: PublicRunStatus;
}
/**
 * Bounded public presentation transport; never a durable consumer offset.
 *
 * Attributes
 * ----------
 * visual_schema_version : str
 *     Version of the presentation message envelope.
 * type : str
 *     Presentation message kind, such as ``snapshot`` or ``samples``.
 * sent_at : datetime
 *     Wall-clock send time in UTC.
 * run_id : str
 *     Run associated with the presentation update.
 * status : PublicRunStatus or None
 *     Latest public status when supplied.
 * frames : list of MeasurementFrame
 *     Coalesced public frames delivered to the viewer.
 * ranges : list of SequenceRange
 *     Inclusive sequence bounds for delivered streams.
 * message : str or None
 *     Safe human-readable error or resynchronization message.
 *
 * Notes
 * -----
 * Consumers requiring durable delivery must use the HTTP replay routes and
 * their opaque cursors.
 */
export interface VisualMessage {
  frames: Frames1;
  message: Message;
  ranges: Ranges;
  run_id: RunId2;
  sent_at: SentAt;
  status: PublicRunStatus | null;
  type: Type5;
  visual_schema_version: VisualSchemaVersion;
}
