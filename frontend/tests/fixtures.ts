import type { MeasurementFrame, PublicRunStatus } from '../src/api/generated';

export const EPOCH = '2026-09-21T00:00:00Z';
export function statusAt(
  tick: number,
  state: PublicRunStatus['status'] = 'running',
  speed: 1 | 5 | 20 = 20,
): PublicRunStatus {
  return {
    run_id: 'test-run',
    status: state,
    epoch_utc: EPOCH,
    duration_s: 21600,
    committed_tick: tick,
    status_revision: tick + 1,
    committed_at: new Date(Date.parse(EPOCH) + tick * 1000).toISOString(),
    requested_speed: speed,
    effective_speed: state === 'running' ? speed : 0,
    wall_lag_s: 0,
    source_kind: 'synthetic',
    frame_count: (tick + 1) * 3,
    diagnostic: null,
    model_provenance: { orbit_model: 'j2_cartesian' },
    satellites: [
      {
        satellite_id: 'METIS-01',
        name: 'Metis One',
        color: '#8FD3FF',
        stream_id: 'test-stream-1',
        capacity_wh: 400,
        panel_area_m2: 0.9,
        public_limits: [],
      },
      {
        satellite_id: 'METIS-02',
        name: 'Metis Two',
        color: '#F7C873',
        stream_id: 'test-stream-2',
        capacity_wh: 400,
        panel_area_m2: 0.9,
        public_limits: [],
      },
      {
        satellite_id: 'METIS-03',
        name: 'Metis Three',
        color: '#A8E6B5',
        stream_id: 'test-stream-3',
        capacity_wh: 400,
        panel_area_m2: 0.9,
        public_limits: [],
      },
    ],
  };
}

export function frameAt(tick: number, satellite = 1): MeasurementFrame {
  return {
    schema_version: 'telemetry.v1',
    source_id: 'test-synthetic',
    stream_id: `test-stream-${satellite}`,
    sequence: tick,
    satellite_id: `METIS-0${satellite}`,
    source_kind: 'synthetic',
    time_domain: 'simulation_utc',
    observed_at: new Date(Date.parse(EPOCH) + tick * 1000).toISOString(),
    emitted_at: '2026-09-23T00:00:00Z',
    sample_window_s: tick === 0 ? 0 : 1,
    catalog_version: 'power-leo.v1',
    mode: 'nominal',
    interval_mode: 'nominal',
    channels: {
      'orbit.position_itrf_m': { value: [-3200000, 5600000, 2500000], quality: 'valid' },
      'orbit.velocity_itrf_m_s': { value: [1000, -2000, 5000], quality: 'valid' },
      'orbit.latitude_deg': { value: 21.2, quality: 'valid' },
      'orbit.longitude_deg': { value: 120.5, quality: 'valid' },
      'orbit.altitude_m': { value: 550200, quality: 'valid' },
      'environment.illumination_fraction': { value: 1, quality: 'valid' },
      'eps.solar_power_w': { value: 322.4, quality: 'valid' },
      'eps.load_requested_w': { value: 150, quality: 'valid' },
      'eps.load_served_w': { value: 150, quality: 'valid' },
      'eps.battery_power_w': { value: -172.4, quality: 'valid' },
      'eps.battery_energy_wh': { value: 320 + tick * 0.01, quality: 'valid' },
      'eps.battery_soc': { value: 0.8 + tick * 0.000025, quality: 'valid' },
      'eps.curtailed_power_w': { value: 0, quality: 'valid' },
      'eps.unserved_power_w': { value: 0, quality: 'valid' },
    },
  };
}

export function framesBetween(first: number, last: number): MeasurementFrame[] {
  return Array.from({ length: last - first + 1 }, (_, offset) =>
    [1, 2, 3].map((id) => frameAt(first + offset, id)),
  ).flat();
}
