import {
  ArrowDownLeft,
  ArrowUpRight,
  BatteryMedium,
  ChevronDown,
  Moon,
  Radio,
  Sun,
  Zap,
} from 'lucide-react';
import type { MeasurementFrame, PublicRunStatus } from '../api/generated';
import { scalar } from '../scene/playback';

export function reading(value: number | null | undefined, digits = 1): string {
  return value === null || value === undefined
    ? '—'
    : value.toLocaleString('en-US', {
        maximumFractionDigits: digits,
        minimumFractionDigits: digits,
      });
}

export function clockTime(utc: string | undefined | null): string {
  return utc ? new Date(utc).toISOString().slice(11, 19) : '—';
}

export function environment(frame: MeasurementFrame | undefined): string {
  const illumination = scalar(frame, 'environment.illumination_fraction');
  return illumination === null
    ? 'Awaiting sample'
    : illumination <= 0.001
      ? 'In eclipse'
      : illumination >= 0.999
        ? 'Sunlit'
        : 'Penumbra';
}

export function TelemetryPanel({
  descriptor,
  frame,
}: {
  descriptor: PublicRunStatus['satellites'][number] | undefined;
  frame: MeasurementFrame | undefined;
}) {
  const soc = scalar(frame, 'eps.battery_soc');
  const energy = scalar(frame, 'eps.battery_energy_wh');
  const solar = scalar(frame, 'eps.solar_power_w');
  const load = scalar(frame, 'eps.load_requested_w');
  const served = scalar(frame, 'eps.load_served_w');
  const battery = scalar(frame, 'eps.battery_power_w');
  const illumination = scalar(frame, 'environment.illumination_fraction');
  const batteryCharging = battery !== null && battery < -0.01;
  const maxPower = Math.max(solar ?? 0, load ?? 0, Math.abs(battery ?? 0), 1);
  const modes: Record<string, string> = {
    nominal: 'Nominal',
    payload_active: 'Payload active',
    safe: 'Safe',
  };
  return (
    <aside className="inspector" aria-label="Selected satellite measurements">
      <div className="inspector-top">
        <span className="eyebrow">SPACECRAFT DETAIL</span>
        <Radio size={14} />
      </div>
      <div className="satellite-identity">
        <div
          className="satellite-symbol"
          style={{ '--sat-color': descriptor?.color ?? '#88cde4' } as React.CSSProperties}
          aria-hidden="true"
        >
          <span />
          <i />
          <span />
        </div>
        <div>
          <h2>{descriptor?.satellite_id ?? 'Select a satellite'}</h2>
          <p>{descriptor?.name ?? 'Mission telemetry'}</p>
        </div>
        <ChevronDown size={14} className="muted" />
      </div>
      <div className="mode-row">
        <span className="mode-dot" />
        {frame ? (modes[frame.mode] ?? 'Unknown mode') : 'Awaiting measurements'}
        <span className="text-pill">LEO</span>
      </div>

      <section className="telemetry-section battery-section">
        <div className="section-label">
          <span>
            <BatteryMedium size={14} /> Battery state
          </span>
          <span className={batteryCharging ? 'positive' : 'muted'}>
            {battery === null
              ? '—'
              : batteryCharging
                ? 'Charging'
                : battery > 0.01
                  ? 'Discharging'
                  : 'Balanced'}
          </span>
        </div>
        <div className="large-reading">
          {reading(soc === null ? null : soc * 100)}
          <span>%</span>
        </div>
        <div
          className="battery-track"
          role="meter"
          aria-label="Battery state of charge"
          aria-valuenow={soc === null ? undefined : soc * 100}
          aria-valuemin={0}
          aria-valuemax={100}
        >
          <div style={{ width: `${Math.max(0, Math.min(100, (soc ?? 0) * 100))}%` }} />
        </div>
        <div className="reading-caption">
          <span>{reading(energy)} Wh stored</span>
          <span>{reading(descriptor?.capacity_wh, 0)} Wh capacity</span>
        </div>
      </section>

      <section className="telemetry-section">
        <div className="section-label">
          <span>
            <Zap size={14} /> Power balance
          </span>
          <span className="unit-label">WATTS</span>
        </div>
        <div className="power-main">
          <div>
            <span>Solar generation</span>
            <strong>
              {reading(solar, 1)}
              <small>W</small>
            </strong>
          </div>
          <Sun size={22} className="sun-color" />
        </div>
        {[
          { name: 'Solar', value: solar, color: '#e0c083' },
          { name: 'Requested load', value: load, color: '#8396ab' },
          {
            name: batteryCharging ? 'To battery' : 'From battery',
            value: battery === null ? null : Math.abs(battery),
            color: '#8bcaba',
          },
        ].map((item) => (
          <div className="power-bar-row" key={item.name}>
            <span>{item.name}</span>
            <div className="power-bar">
              <i
                style={{
                  width: `${((item.value ?? 0) / maxPower) * 100}%`,
                  backgroundColor: item.color,
                }}
              />
            </div>
            <b>{reading(item.value, 0)}</b>
          </div>
        ))}
        <div className="power-foot">
          <span>
            <ArrowDownLeft size={12} /> Load served
          </span>
          <strong>{reading(served)} W</strong>
        </div>
        <div className="power-foot">
          <span>
            <ArrowUpRight size={12} /> Curtailed / unmet
          </span>
          <strong>
            {reading(scalar(frame, 'eps.curtailed_power_w'))} /{' '}
            {reading(scalar(frame, 'eps.unserved_power_w'))} W
          </strong>
        </div>
        <p className="micro-copy">
          {frame?.sample_window_s === 0
            ? 'Initial instantaneous allocation'
            : `${frame?.sample_window_s ?? 1} s mean · ${frame?.interval_mode ? (modes[frame.interval_mode] ?? frame.interval_mode) : 'unknown interval mode'}`}
        </p>
      </section>

      <section className="telemetry-section environment-section">
        <div className="section-label">
          <span>
            {illumination !== null && illumination < 0.01 ? <Moon size={14} /> : <Sun size={14} />}{' '}
            Illumination
          </span>
          <strong>{environment(frame)}</strong>
        </div>
        <div className="illumination-track">
          <i style={{ width: `${(illumination ?? 0) * 100}%` }} />
        </div>
        <div className="reading-caption">
          <span>Visible solar disk</span>
          <span>{reading(illumination === null ? null : illumination * 100)}%</span>
        </div>
      </section>

      <section className="telemetry-section position-section">
        <div className="section-label">
          <span>Position</span>
          <span className="unit-label">EARTH FIXED</span>
        </div>
        <dl>
          <div>
            <dt>Altitude</dt>
            <dd>
              {reading(
                scalar(frame, 'orbit.altitude_m') === null
                  ? null
                  : scalar(frame, 'orbit.altitude_m')! / 1000,
              )}
              <small>km</small>
            </dd>
          </div>
          <div>
            <dt>Latitude</dt>
            <dd>
              {reading(scalar(frame, 'orbit.latitude_deg'), 2)}
              <small>°</small>
            </dd>
          </div>
          <div>
            <dt>Longitude</dt>
            <dd>
              {reading(scalar(frame, 'orbit.longitude_deg'), 2)}
              <small>°</small>
            </dd>
          </div>
        </dl>
      </section>
      <div className="sample-stamp" data-observed-at={frame?.observed_at}>
        <span className="live-dot" />
        <span>Sample {clockTime(frame?.observed_at)} UTC</span>
        <span>#{frame?.sequence ?? '—'}</span>
      </div>
    </aside>
  );
}
