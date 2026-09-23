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
 */
export interface ChannelReading {
  quality: Quality;
  value: Value;
}
/**
 * A run command; speed is meaningful only for set_speed.
 */
export interface ControlRequest {
  action: Action;
  speed?: Speed;
}
/**
 * Allowlisted producer-neutral telemetry measurement frame.
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
 */
export interface ModeChangedDetails {
  from_mode: FromMode;
  to_mode: ToMode;
}
/**
 * Allowlisted observed public SOC limit transition details.
 */
export interface LowEnergyLimitDetails {
  channel_id: ChannelId;
  clear_value: ClearValue;
  operator: Operator;
  value: Value1;
}
/**
 * Allowlisted observed unserved-power state details.
 */
export interface PowerUnservedDetails {
  active: Active;
  sample_window_s: SampleWindowS1;
  value_w: ValueW;
}
/**
 * One authoritative Earth-fixed orbit state without predicted health.
 */
export interface OrbitPoint {
  elapsed_s: ElapsedS;
  observed_at: ObservedAt2;
  position_itrs_m: PositionItrsM;
  velocity_itrs_m_s: VelocityItrsMS;
}
/**
 * A disclosed operational limit with hysteresis.
 */
export interface PublicLimit {
  channel_id: ChannelId1;
  clear_value: ClearValue1;
  operator: Operator1;
  value: Value2;
}
/**
 * Committed run status containing no configuration or scenario identity.
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
 */
export interface SatelliteTrajectory {
  samples: Samples;
  satellite_id: SatelliteId3;
}
/**
 * A delivered stream's inclusive sequence bounds.
 */
export interface SequenceRange {
  first: First;
  last: Last;
  stream_id: StreamId3;
}
/**
 * Complete validated P0 simulation input configuration.
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
 */
export interface PointingConfiguration {
  type: Type1;
}
/**
 * Observable SOC threshold with explicit hysteresis.
 */
export interface ConfiguredPublicLimit {
  channel_id: ChannelId2;
  clear_value: ClearValue2;
  operator: Operator2;
  value: Value3;
}
/**
 * Public channel catalog and sensor-noise policy.
 */
export interface SensorConfiguration {
  catalog: Catalog;
  noise: NoiseConfiguration;
}
/**
 * Supported sensor noise selection.
 */
export interface NoiseConfiguration {
  type: Type2;
}
/**
 * Simulation timing, seed, and versioned model selections.
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
 */
export interface Operation {
  end_s: EndS;
  mode: Mode1;
  start_s: StartS;
}
/**
 * Osculating classical orbit elements at the run epoch.
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
 */
export interface VisualConfiguration {
  asset_id?: AssetId;
  color?: Color1;
}
/**
 * Private piecewise-linear solar derating scenario.
 */
export interface SolarDeratingScenario {
  outcome: ReserveOutcome;
  points: Points;
  satellite_id: SatelliteId5;
  type: Type4;
}
/**
 * Private state-triggered operational reserve outcome rule.
 */
export interface ReserveOutcome {
  dwell_s?: DwellS;
  reserve_soc: ReserveSoc;
  type: Type3;
}
/**
 * Elapsed run time and solar generation multiplier control point.
 */
export interface DeratingPoint {
  at_s: AtS;
  multiplier: Multiplier;
}
/**
 * A consistent committed status and bounded measurement history.
 */
export interface Snapshot {
  frames: Frames;
  status: PublicRunStatus;
}
/**
 * Bounded orbit-only prediction with explicit coordinates.
 */
export interface Trajectory {
  frame: Frame1;
  kind: Kind;
  run_id: RunId1;
  satellites: Satellites2;
}
/**
 * One prepared run and session-bound CSRF token for the browser.
 */
export interface ViewerBootstrap {
  csrf_token: CsrfToken;
  run: PublicRunStatus;
}
/**
 * Bounded public presentation transport; never a durable consumer offset.
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
