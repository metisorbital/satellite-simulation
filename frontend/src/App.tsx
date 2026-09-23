import { lazy, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import {
  Activity,
  ArrowUpRight,
  ChevronDown,
  CircleHelp,
  Crosshair,
  Expand,
  Globe2,
  Info,
  Layers3,
  Minus,
  Orbit,
  Pause,
  Play,
  Plus,
  Radio,
  Satellite,
  Square,
  Wifi,
  WifiOff,
} from 'lucide-react';
import { useMission } from './api/useMission';
import type { SceneControls } from './scene/Globe';
import type { SceneDiagnostics } from './scene/render-rate';
import { frameSeconds, scalar } from './scene/playback';
import { TelemetryPanel, clockTime, environment, reading } from './panels/TelemetryPanel';
import { Sparkline } from './components/Sparkline';
import { ModelInfo } from './components/ModelInfo';

const Globe = lazy(() => import('./scene/Globe').then((module) => ({ default: module.Globe })));

function duration(seconds: number): string {
  const value = Math.max(0, Math.floor(seconds));
  return `${Math.floor(value / 3600)
    .toString()
    .padStart(2, '0')}:${Math.floor((value % 3600) / 60)
    .toString()
    .padStart(2, '0')}:${(value % 60).toString().padStart(2, '0')}`;
}

export function App() {
  const mission = useMission();
  const { playback, status } = mission;
  const [selected, setSelected] = useState('');
  const [displaySeconds, setDisplaySeconds] = useState<number | null>(null);
  const [stale, setStale] = useState(false);
  const [follow, setFollow] = useState(false);
  const [renderRate, setRenderRate] = useState<SceneDiagnostics | null>(null);
  const [showInfo, setShowInfo] = useState(false);
  const closeInfo = useCallback(() => setShowInfo(false), []);
  const [chart, setChart] = useState<'soc' | 'solar'>('soc');
  const controls = useRef<SceneControls | null>(null);
  const receiveControls = useCallback((value: SceneControls) => {
    controls.current = value;
  }, []);
  useEffect(() => setFollow(false), [status?.run_id]);
  useEffect(() => {
    if (status && !status.satellites.some((s) => s.satellite_id === selected))
      setSelected(status.satellites[0]?.satellite_id ?? '');
  }, [status, selected]);
  useEffect(() => {
    let animation = 0;
    let last = 0;
    const update = (now: number) => {
      if (now - last >= 30) {
        setDisplaySeconds(playback.time(now));
        setStale(playback.isStale(now));
        last = now;
      }
      animation = requestAnimationFrame(update);
    };
    animation = requestAnimationFrame(update);
    return () => cancelAnimationFrame(animation);
  }, [playback]);
  const descriptor = status?.satellites.find((s) => s.satellite_id === selected);
  const frame = playback.frameAt(selected, displaySeconds);
  const history = (playback.history.get(selected) ?? []).filter(
    (f) => status && displaySeconds !== null && frameSeconds(f, status.epoch_utc) <= displaySeconds,
  );
  const samples = history.flatMap((f) => {
    const value = scalar(f, chart === 'soc' ? 'eps.battery_soc' : 'eps.solar_power_w');
    return value === null
      ? []
      : [{ time: Date.parse(f.observed_at), value: value * (chart === 'soc' ? 100 : 1) }];
  });
  const displayedUtc =
    status && displaySeconds !== null
      ? new Date(Date.parse(status.epoch_utc) + displaySeconds * 1000).toISOString()
      : status?.epoch_utc;
  const active = status?.status === 'running';
  const terminal = status && ['completed', 'stopped', 'failed', 'aborted'].includes(status.status);
  const starting = status?.status === 'created' || status?.committed_tick === -1;
  const runLabel = status?.status.replaceAll('_', ' ') ?? 'Connecting';
  const lag =
    status && displaySeconds !== null ? Math.max(0, status.committed_tick - displaySeconds) : 0;
  const resetCamera = () => {
    setFollow(false);
    controls.current?.reset();
  };
  return (
    <div className="app-shell">
      <nav className="rail" aria-label="Application navigation">
        <a href="/" className="brand-mark" aria-label="Metis Orbital home">
          <img src="/assets/metis-mark.svg" alt="" />
        </a>
        <button className="rail-item active" aria-label="Orbital overview" aria-current="page">
          <Orbit size={21} />
        </button>
        <button
          className="rail-item"
          aria-label="Focus telemetry history"
          onClick={() => document.getElementById('mission-history')?.focus()}
        >
          <Activity size={20} />
        </button>
        <button
          className="rail-item"
          aria-label="View simulation model information"
          onClick={() => setShowInfo(true)}
        >
          <Layers3 size={20} />
        </button>
        <div className="rail-spacer" />
        <button
          className="rail-item"
          aria-label="Help and model limitations"
          onClick={() => setShowInfo(true)}
        >
          <CircleHelp size={19} />
        </button>
        <div className="operator-avatar" title="Local mission control">
          M
        </div>
      </nav>

      <aside className="mission-sidebar">
        <div className="wordmark">
          metis<span>orbital</span>
        </div>
        <div className="mission-picker">
          <div className="mission-icon">
            <Orbit size={17} />
          </div>
          <div>
            <strong>LEO power mission</strong>
            <span>Simulation workspace</span>
          </div>
          <ChevronDown size={13} />
        </div>
        <div className="sidebar-heading">
          <span>MISSION WORKSPACE</span>
        </div>
        <button className="sidebar-nav selected">
          <Globe2 size={16} /> Orbital overview <span className="nav-key">01</span>
        </button>
        <button
          className="sidebar-nav"
          onClick={() => document.getElementById('mission-history')?.focus()}
        >
          <Activity size={16} /> Measurement history
        </button>
        <div className="sidebar-divider" />
        <div className="sidebar-heading">
          <span>CONSTELLATION</span>
          <span className="count-badge">{status?.satellites.length ?? '—'}</span>
        </div>
        <div className="satellite-list" aria-label="Select satellite">
          {status?.satellites.map((satellite) => {
            const current = playback.frameAt(satellite.satellite_id, displaySeconds);
            const soc = scalar(current, 'eps.battery_soc');
            return (
              <button
                key={satellite.satellite_id}
                className={`satellite-row ${selected === satellite.satellite_id ? 'selected' : ''}`}
                aria-pressed={selected === satellite.satellite_id}
                onClick={() => setSelected(satellite.satellite_id)}
                style={{ '--sat-color': satellite.color } as React.CSSProperties}
              >
                <div className="satellite-row-top">
                  <Satellite size={17} />
                  <strong>{satellite.satellite_id}</strong>
                  <span className="sat-status-dot" />
                </div>
                <div className="satellite-row-meta">
                  <span>{environment(current)}</span>
                  <span>{reading(soc === null ? null : soc * 100, 0)}% SOC</span>
                </div>
                <div className="mini-soc-track">
                  <i style={{ width: `${(soc ?? 0) * 100}%` }} />
                </div>
              </button>
            );
          })}
          {!status && <div className="sidebar-placeholder">Connecting to mission…</div>}
        </div>
        <div className="sidebar-bottom">
          <div className="synthetic-label">
            <span /> SYNTHETIC MISSION
          </div>
          <p>
            Explore how orbit and sunlight
            <br />
            shape spacecraft power.
          </p>
          <button className="text-link" onClick={() => setShowInfo(true)}>
            About this simulation <ArrowUpRight size={13} />
          </button>
          <div className="connection-label">
            {mission.connected ? <Wifi size={12} /> : <WifiOff size={12} />}{' '}
            {mission.connected ? 'Local stream connected' : 'Stream disconnected'}
          </div>
        </div>
      </aside>

      <main className="main-workspace">
        <header className="topbar">
          <div className="breadcrumb">
            Mission control <span>/</span> <strong>Orbital overview</strong>
          </div>
          <div className="topbar-right">
            <span className="synthetic-pill">SYNTHETIC</span>
            <div className="topbar-divider" />
            <span className={`run-state ${active ? 'running' : ''}`}>
              <span />
              {runLabel}
            </span>
            <span className="local-tag">LOCAL</span>
          </div>
        </header>
        <div className="mission-toolbar">
          <div>
            <div className="eyebrow">METIS / EARTH ORBIT</div>
            <h1>
              Orbital overview
              <span className="title-dot" />
            </h1>
          </div>
          <div className="mission-clock">
            <span>SIMULATION UTC</span>
            <strong>
              {clockTime(displayedUtc)}
              <small>{displayedUtc?.slice(0, 10) ?? '—'}</small>
            </strong>
          </div>
          <div className="run-controls" aria-label="Run controls">
            <button
              className="play-button"
              disabled={!status || mission.busy || !!terminal}
              onClick={() => void mission.control(active ? 'pause' : starting ? 'start' : 'resume')}
              aria-label={
                active ? 'Pause simulation' : starting ? 'Start simulation' : 'Resume simulation'
              }
            >
              {active ? (
                <Pause size={15} fill="currentColor" />
              ) : (
                <Play size={15} fill="currentColor" />
              )}
              <span>
                {mission.busy ? 'Applying…' : active ? 'Pause' : starting ? 'Start run' : 'Resume'}
              </span>
            </button>
            <div className="speed-switch" aria-label="Simulation speed">
              {[1, 5, 20].map((speed) => (
                <button
                  key={speed}
                  className={status?.requested_speed === speed ? 'selected' : ''}
                  aria-pressed={status?.requested_speed === speed}
                  disabled={!status || mission.busy || !!terminal}
                  onClick={() => void mission.control('set_speed', speed)}
                >
                  {speed}×
                </button>
              ))}
            </div>
            <button
              className="icon-button stop-button"
              aria-label="Stop simulation"
              title="Stop simulation"
              disabled={!status || mission.busy || !!terminal || !!starting}
              onClick={() => void mission.control('stop')}
            >
              <Square size={13} />
            </button>
          </div>
        </div>
        {mission.error && (
          <div className="error-banner" role="alert">
            <Info size={15} />
            <span>{mission.error}</span>
            <button onClick={mission.retry}>Reconnect</button>
          </div>
        )}
        <div className="simulation-layout">
          <section className="orbit-stage" aria-label="Orbit overview">
            <div className="scene-metrics">
              <div>
                <span>SPACECRAFT</span>
                <strong>
                  {String(status?.satellites.length ?? 0).padStart(2, '0')}
                  <small>in constellation</small>
                </strong>
              </div>
              <div>
                <span>SELECTED ALTITUDE</span>
                <strong>
                  {reading(
                    scalar(frame, 'orbit.altitude_m') === null
                      ? null
                      : scalar(frame, 'orbit.altitude_m')! / 1000,
                    1,
                  )}
                  <small>km</small>
                </strong>
              </div>
            </div>
            <Suspense fallback={null}>
              <Globe
                playback={playback}
                status={status}
                trajectory={mission.trajectory}
                revision={mission.revision}
                displaySeconds={displaySeconds}
                selected={selected}
                onSelect={setSelected}
                onControls={receiveControls}
                onRenderRate={setRenderRate}
              />
            </Suspense>
            <div className="scene-top-right">
              <span className="view-tag">
                <Globe2 size={12} /> Earth fixed
              </span>
              <span className="model-tag">J2 ORBIT MODEL</span>
            </div>
            <div className="scene-bottom-left">
              <div className="scene-legend">
                <i /> Predicted orbit <span>·</span> Symbols enlarged
              </div>
              <span className="lighting-note">Approximate visual lighting · WGS84 Earth</span>
            </div>
            <div className="camera-tools" aria-label="Camera controls">
              <button onClick={() => controls.current?.zoom('in')} aria-label="Zoom in">
                <Plus size={17} />
              </button>
              <button onClick={() => controls.current?.zoom('out')} aria-label="Zoom out">
                <Minus size={17} />
              </button>
              <span />
              <button
                className={follow ? 'selected' : ''}
                onClick={() => {
                  const value = !follow;
                  setFollow(value);
                  controls.current?.follow(value);
                }}
                aria-label="Follow selected satellite"
                aria-pressed={follow}
                disabled={!frame}
              >
                <Crosshair size={17} />
              </button>
              <button onClick={resetCamera} aria-label="Reset Earth view">
                <Expand size={16} />
              </button>
            </div>
            <div
              className={`stream-indicator ${stale && status ? 'stale' : ''}`}
              aria-live="polite"
            >
              <span />
              {!status
                ? 'Establishing mission link'
                : stale
                  ? 'Data stale · view frozen'
                  : active
                    ? 'Live simulation'
                    : `${runLabel} · committed state`}
              <b>{reading(lag, 1)} s behind</b>
            </div>
            {!status && (
              <div className="connecting-overlay">
                <div className="loader-orbit">
                  <Satellite size={22} />
                </div>
                <strong>Establishing mission link</strong>
                <span>The Earth view is ready. Waiting for the simulation.</span>
              </div>
            )}
            <section
              className="history-panel"
              id="mission-history"
              tabIndex={-1}
              aria-label="Measured telemetry history"
            >
              <div className="history-header">
                <div>
                  <Activity size={14} />
                  <strong>Power history</strong>
                  <span>{selected || 'Waiting for selection'}</span>
                </div>
                <div className="chart-toggle">
                  <button
                    className={chart === 'soc' ? 'selected' : ''}
                    onClick={() => setChart('soc')}
                  >
                    Battery SOC
                  </button>
                  <button
                    className={chart === 'solar' ? 'selected' : ''}
                    onClick={() => setChart('solar')}
                  >
                    Solar power
                  </button>
                </div>
              </div>
              <div className="history-chart">
                <div className="chart-value">
                  <strong>
                    {reading(samples.at(-1)?.value)}
                    <small>{chart === 'soc' ? '%' : 'W'}</small>
                  </strong>
                  <span>Measured {chart === 'soc' ? 'state of charge' : 'generation'}</span>
                </div>
                <div className="chart-plot">
                  <Sparkline
                    points={samples}
                    color={chart === 'soc' ? '#8ccab9' : '#e0c083'}
                    domain={chart === 'soc' ? [0, 100] : undefined}
                    label={`${selected} ${chart === 'soc' ? 'battery state of charge' : 'solar generation'} measured history`}
                    height={55}
                  />
                  <div className="chart-axis">
                    <span>{clockTime(history[0]?.observed_at)}</span>
                    <span>Actual committed samples · UTC</span>
                    <span>{clockTime(history.at(-1)?.observed_at)}</span>
                  </div>
                </div>
              </div>
            </section>
          </section>
          <TelemetryPanel descriptor={descriptor} frame={frame} />
        </div>
        <footer className="statusbar">
          <span>
            <Radio size={11} />
            {status
              ? `${status.frame_count.toLocaleString()} committed frames`
              : 'Waiting for backend'}
          </span>
          <span>
            T+ {duration(displaySeconds ?? 0)}
            <i>/</i>
            {duration(status?.duration_s ?? 0)}
          </span>
          <span>
            Effective {reading(status?.effective_speed ?? 0, 1)}×<i>·</i>1 Hz telemetry
          </span>
          <output
            className="scene-fps"
            aria-label="Cesium scene frame rate"
            title={`Completed Cesium scene renders per wall second. ${renderRate ? `${renderRate.positionedSatelliteIds.length} positioned spacecraft: ${renderRate.positionedSatelliteIds.join(', ') || 'none'}` : 'Positioned spacecraft unavailable.'}`}
            data-positioned-spacecraft={renderRate?.positionedSatelliteIds.join(',')}
            data-positioned-count={renderRate?.positionedSatelliteIds.length}
            data-frames={renderRate?.frames}
            data-window-ms={renderRate?.windowMs}
            data-observed-at={renderRate?.observedAt}
            data-fps={renderRate?.fps ?? undefined}
          >
            Scene {renderRate?.fps == null ? 'unavailable' : `${reading(renderRate.fps, 0)} FPS`}
          </output>
          <button onClick={() => setShowInfo(true)}>
            <Info size={11} /> Model & credits
          </button>
        </footer>
      </main>

      {showInfo && <ModelInfo onClose={closeInfo} onReset={resetCamera} />}
    </div>
  );
}
